"""Durable campaign snapshots and deliberately restricted SRD 5.2.1 starters.

This work includes material from the System Reference Document 5.2.1
(“SRD 5.2.1”) by Wizards of the Coast LLC, available at
https://www.dndbeyond.com/srd. The SRD 5.2.1 is licensed under the Creative
Commons Attribution 4.0 International License, available at
https://creativecommons.org/licenses/by/4.0/legalcode.

Starter packages are curated selections, not a complete rules implementation.
Ability assignments use the SRD standard array plus legal background increases.
Names, appearance, and fictional concepts never grant mechanical benefits.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class ConflictError(ValueError):
    """A revision or request fingerprint conflicts with committed state."""


class NotFoundError(KeyError):
    """The requested campaign does not exist."""


_TOKEN = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_MEDIA_KIND = re.compile(r"[a-z][a-z0-9_]{0,47}\Z")
_MAX_STATE_BYTES = 2_000_000


def _token(value: Any, label: str) -> None:
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise ValueError(f"Invalid {label}")


def _campaign_id(value: Any) -> None:
    if not isinstance(value, str):
        raise TypeError("Invalid campaign id")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValueError("Invalid campaign id") from exc
    if str(parsed) != value:
        raise ValueError("Invalid campaign id")


def _revision(value: Any) -> None:
    if type(value) is not int or not 0 <= value < 2**63 - 1:
        raise ValueError("Invalid revision")


def _action(value: Any) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 100_000:
        raise ValueError("Invalid action")


def _encode(state: Any) -> str:
    if not isinstance(state, dict):
        raise TypeError("State must be an object")
    try:
        serialized = json.dumps(state, ensure_ascii=False, allow_nan=False)
        if len(serialized.encode("utf-8")) > _MAX_STATE_BYTES:
            raise ValueError("State exceeds storage limit")
    except (TypeError, RecursionError, UnicodeError) as exc:
        raise ValueError("State must contain finite JSON data") from exc
    return serialized


class CampaignStore:
    """SQLite store with independent connections and atomic, replayable commits.

    Callers choose the database path (normally their application data directory,
    outside the checkout). Every accepted request retains its original response;
    async media enrichment does not alter the request replay snapshot.
    """

    def __init__(self, path: str | Path):
        if str(path) == ":memory:":
            raise ValueError("A persistent database path is required")
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Create with private permissions before SQLite opens it. Existing files
        # retain their permissions, avoiding changes to caller-owned resources.
        try:
            descriptor = self.path.open("xb")
        except FileExistsError:
            pass
        else:
            descriptor.close()
            self.path.chmod(0o600)
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS campaigns (
                    id TEXT PRIMARY KEY, revision INTEGER NOT NULL, state TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS requests (
                    campaign_id TEXT NOT NULL REFERENCES campaigns(id),
                    request_id TEXT NOT NULL, action TEXT NOT NULL, response TEXT NOT NULL,
                    PRIMARY KEY (campaign_id, request_id)
                );
                """
            )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _read(connection: sqlite3.Connection, campaign_id: str) -> dict[str, Any]:
        row = connection.execute(
            "SELECT state FROM campaigns WHERE id=?", (campaign_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(campaign_id)
        return json.loads(row[0])

    @staticmethod
    def _replay(
        connection: sqlite3.Connection, campaign_id: str, request_id: str, action: str
    ) -> dict[str, Any] | None:
        row = connection.execute(
            "SELECT action, response FROM requests WHERE campaign_id=? AND request_id=?",
            (campaign_id, request_id),
        ).fetchone()
        if row is None:
            return None
        if row[0] != action:
            raise ConflictError("request id already used for a different action")
        return json.loads(row[1])

    def create(self, state: dict[str, Any]) -> dict[str, Any]:
        _encode(state)
        result = {**state, "id": str(uuid.uuid4()), "revision": 0}
        encoded = _encode(result)
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO campaigns (id, revision, state) VALUES (?, 0, ?)",
                (result["id"], encoded),
            )
        return json.loads(encoded)

    def get(self, campaign_id: str) -> dict[str, Any]:
        _campaign_id(campaign_id)
        with self._connection() as connection:
            return self._read(connection, campaign_id)

    def list_summaries(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute("SELECT state FROM campaigns ORDER BY rowid DESC").fetchall()
        summaries = []
        for row in rows:
            state = json.loads(row[0])
            summaries.append({
                "id": state["id"], "revision": state["revision"],
                "title": state.get("title", "Untitled campaign"),
                "phase": state.get("phase", "onboarding"),
                "character_name": (state.get("character") or {}).get("name", ""),
            })
        return summaries

    def lookup_request(
        self, campaign_id: str, request_id: str, action: str
    ) -> dict[str, Any] | None:
        _campaign_id(campaign_id)
        _token(request_id, "request id")
        _action(action)
        with self._connection() as connection:
            self._read(connection, campaign_id)
            return self._replay(connection, campaign_id, request_id, action)

    def commit(
        self, campaign_id: str, expected_revision: int, request_id: str,
        action: str, new_state: dict[str, Any],
    ) -> dict[str, Any]:
        _campaign_id(campaign_id)
        _revision(expected_revision)
        _token(request_id, "request id")
        _action(action)
        _encode(new_state)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            replay = self._replay(connection, campaign_id, request_id, action)
            if replay is not None:
                connection.commit()
                return replay
            current = self._read(connection, campaign_id)
            if current["revision"] != expected_revision:
                raise ConflictError("revision changed; reload campaign before acting")
            result = {**new_state, "id": campaign_id, "revision": expected_revision + 1}
            encoded = _encode(result)
            connection.execute(
                "UPDATE campaigns SET revision=?, state=? WHERE id=? AND revision=?",
                (result["revision"], encoded, campaign_id, expected_revision),
            )
            connection.execute(
                "INSERT INTO requests VALUES (?, ?, ?, ?)",
                (campaign_id, request_id, action, encoded),
            )
            connection.commit()
        return json.loads(encoded)

    def update_media(
        self, campaign_id: str, revision: int, kind: str, payload: dict[str, Any]
    ) -> bool:
        _campaign_id(campaign_id)
        _revision(revision)
        if not isinstance(kind, str) or not _MEDIA_KIND.fullmatch(kind):
            raise ValueError("Invalid media kind")
        _encode(payload)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self._read(connection, campaign_id)
            if current["revision"] != revision:
                return False
            media = current.get("media", {})
            if not isinstance(media, dict):
                raise TypeError("Campaign media must be an object")
            current["media"] = {**media, kind: payload}
            connection.execute(
                "UPDATE campaigns SET state=? WHERE id=? AND revision=?",
                (_encode(current), campaign_id, revision),
            )
            connection.commit()
        return True


SRD_SOURCE = "https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf"
_ABILITIES = ("str", "dex", "con", "int", "wis", "cha")
_SKILL_ABILITIES = {
    "Acrobatics": "dex", "Animal Handling": "wis", "Arcana": "int", "Athletics": "str",
    "Deception": "cha", "History": "int", "Insight": "wis", "Intimidation": "cha",
    "Investigation": "int", "Medicine": "wis", "Nature": "int", "Perception": "wis",
    "Performance": "cha", "Persuasion": "cha", "Religion": "int", "Sleight of Hand": "dex",
    "Stealth": "dex", "Survival": "wis",
}
_PRESETS: dict[str, dict[str, Any]] = {
    "Fighter": {
        "background": "Soldier", "base": [15, 14, 13, 8, 10, 12], "boost": {"str": 2, "con": 1},
        "hit_die": 10, "ac": 17, "saves": ["str", "con"],
        "class_skills": ["Insight", "Survival"],
        "background_skills": ["Athletics", "Intimidation"],
        "skilled": ["Acrobatics", "History", "Persuasion"],
        "equipment": ["Chain Mail", "Greatsword", "Flail", "8 Javelins", "Dungeoneer's Pack",
                      "Spear", "Shortbow", "20 Arrows", "Dice Set", "Healer's Kit", "Quiver",
                      "Traveler's Clothes"],
        "gold": 18, "tools": ["Dice Set"], "armor": ["Light", "Medium", "Heavy", "Shields"],
        "weapons": ["Simple", "Martial"],
        "features": {"Defense": "+1 AC while wearing armor (included in AC)",
                     "Savage Attacker": "Once per turn on a weapon hit, roll damage dice twice and choose",
                     "Second Wind": "Bonus Action: regain 1d10 + 1 HP; two uses; Short Rest restores one",
                     "Weapon Mastery": {"Greatsword": "Graze", "Flail": "Sap", "Javelin": "Slow"}},
    },
    "Rogue": {
        "background": "Criminal", "base": [12, 15, 13, 14, 10, 8], "boost": {"dex": 2, "con": 1},
        "hit_die": 8, "ac": 14, "saves": ["dex", "int"],
        "class_skills": ["Acrobatics", "Investigation", "Insight", "Deception"],
        "background_skills": ["Sleight of Hand", "Stealth"],
        "skilled": ["Athletics", "Persuasion", "Survival"],
        "equipment": ["Leather Armor", "4 Daggers", "Shortsword", "Shortbow", "20 Arrows",
                      "Quiver", "2 Thieves' Tools", "Burglar's Pack", "Crowbar", "2 Pouches",
                      "Traveler's Clothes"],
        "gold": 24, "tools": ["Thieves' Tools"], "armor": ["Light"],
        "weapons": ["Simple", "Martial with Finesse or Light"],
        "features": {"Alert": "Add proficiency to initiative; may swap initiative with a willing ally",
                     "Expertise": ["Sleight of Hand", "Stealth"],
                     "Sneak Attack": "Once per turn: +1d6 with a Finesse/Ranged hit when eligible",
                     "Thieves' Cant": "Thieves' Cant and Goblin",
                     "Weapon Mastery": {"Dagger": "Nick", "Shortbow": "Vex"}},
    },
    "Wizard": {
        "background": "Sage", "base": [8, 12, 13, 15, 14, 10], "boost": {"int": 2, "con": 1},
        "hit_die": 6, "ac": 11, "saves": ["int", "wis"],
        "class_skills": ["Investigation", "Religion"],
        "background_skills": ["Arcana", "History"],
        "skilled": ["Insight", "Nature", "Persuasion"],
        "equipment": ["2 Daggers", "Arcane Focus (Quarterstaff)", "2 Robes", "Spellbook",
                      "Scholar's Pack", "Quarterstaff", "Calligrapher's Supplies", "Book (history)",
                      "8 Parchment sheets"],
        "gold": 13, "tools": ["Calligrapher's Supplies"], "armor": [], "weapons": ["Simple"],
        "features": {"Spellcasting": "Intelligence; 3 class cantrips; 4 prepared spells; 2 level-1 slots",
                     "Ritual Adept": "Cast ritual spells from your spellbook without preparing them",
                     "Arcane Recovery": "After a Short Rest recover one level-1 slot, once per Long Rest",
                     "Magic Initiate (Wizard)": "Intelligence; Fire Bolt, Prestidigitation, Shield"},
    },
    "Cleric": {
        "background": "Acolyte", "base": [14, 8, 13, 10, 15, 12], "boost": {"wis": 2, "cha": 1},
        "hit_die": 8, "ac": 14, "saves": ["wis", "cha"],
        "class_skills": ["Medicine", "Persuasion"],
        "background_skills": ["Insight", "Religion"],
        "skilled": ["Arcana", "History", "Survival"],
        "equipment": ["Chain Shirt", "Shield", "Mace", "2 Holy Symbols", "Priest's Pack",
                      "Calligrapher's Supplies", "Book (prayers)", "10 Parchment sheets", "Robe"],
        "gold": 15, "tools": ["Calligrapher's Supplies"],
        "armor": ["Light", "Medium", "Heavy", "Shields"], "weapons": ["Simple", "Martial"],
        "features": {"Spellcasting": "Wisdom; 3 class cantrips; 4 prepared spells; 2 level-1 slots",
                     "Divine Order": "Protector: Martial weapon proficiency and Heavy armor training",
                     "Magic Initiate (Cleric)": "Wisdom; Light, Spare the Dying, Healing Word"},
    },
}


def character_catalog() -> dict[str, Any]:
    """Describe the actual implemented scope without promising arbitrary builds."""
    return {
        "edition": "2024 fifth edition / SRD 5.2.1", "species": ["Human"], "level": 1,
        "classes": [{"name": name, "background": preset["background"],
                     "description": f"Level 1 Human {name}; fixed {preset['background']} starter"}
                    for name, preset in _PRESETS.items()],
        "scope": "Four curated starter packages; no other editions, custom stats, or advancement yet",
        "rule_sources": [SRD_SOURCE],
    }


def build_starter_character(data: dict[str, Any]) -> dict[str, Any]:
    """Build one vetted starter. Reject unsupported mechanical overrides explicitly."""
    allowed = {"name", "concept", "class", "species", "level"}
    if not isinstance(data, dict) or set(data) - allowed:
        raise ValueError("Only name, concept, class, species, and level are supported")
    class_name = data.get("class", "Fighter")
    if not isinstance(class_name, str) or class_name not in _PRESETS:
        raise ValueError("Choose Fighter, Rogue, Wizard, or Cleric")
    if data.get("species", "Human") != "Human":
        raise ValueError("Only the Human starter species is implemented")
    level = data.get("level", 1)
    if type(level) is not int or level != 1:
        raise ValueError("Only level 1 starters are implemented")
    name = data.get("name", "Unnamed adventurer")
    concept = data.get("concept", "")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
        raise ValueError("Name must be 1–80 characters")
    if not isinstance(concept, str) or len(concept) > 2000:
        raise ValueError("Concept must be at most 2000 characters")
    # A JSON copy prevents callers modifying the catalog through returned sheets.
    preset = json.loads(json.dumps(_PRESETS[class_name]))
    abilities = dict(zip(_ABILITIES, preset["base"]))
    for ability, increase in preset["boost"].items():
        abilities[ability] += increase
    modifiers = {key: (value - 10) // 2 for key, value in abilities.items()}
    skill_sources = {"class": preset["class_skills"], "background": preset["background_skills"],
                     "Human Skillful": ["Perception"], "Human Skilled": preset["skilled"]}
    proficient = {skill for skills in skill_sources.values() for skill in skills}
    expertise = preset["features"].get("Expertise", [])
    skills = {skill: modifiers[ability] + (4 if skill in expertise else 2 if skill in proficient else 0)
              for skill, ability in _SKILL_ABILITIES.items()}
    features = {
        "Resourceful": "Gain Heroic Inspiration after a Long Rest",
        "Skillful": "Perception proficiency",
        "Skilled": preset["skilled"], **preset["features"],
    }
    resources = {"heroic_inspiration": {"current": 0, "max": 1},
                 "hit_dice": {"current": 1, "max": 1, "die": f"d{preset['hit_die']}"}}
    spells: dict[str, Any] = {"cantrips": [], "prepared": [], "spellbook": []}
    if class_name == "Fighter":
        resources["second_wind"] = {"current": 2, "max": 2}
    if class_name in {"Wizard", "Cleric"}:
        ability = "int" if class_name == "Wizard" else "wis"
        resources["spell_slots_1"] = {"current": 2, "max": 2}
        resources["magic_initiate_free_cast"] = {"current": 1, "max": 1}
        spells.update({"ability": ability, "save_dc": 10 + modifiers[ability],
                       "attack_bonus": 2 + modifiers[ability]})
        if class_name == "Wizard":
            resources["arcane_recovery"] = {"current": 1, "max": 1}
            spells.update({
                "cantrips": ["Light", "Mage Hand", "Ray of Frost"],
                "prepared": ["Mage Armor", "Magic Missile", "Sleep", "Thunderwave"],
                "spellbook": ["Detect Magic", "Feather Fall", "Mage Armor", "Magic Missile",
                              "Sleep", "Thunderwave"],
                "magic_initiate": {"ability": "int", "cantrips": ["Fire Bolt", "Prestidigitation"],
                                   "prepared": ["Shield"], "free_casts_per_long_rest": 1},
            })
        else:
            spells.update({
                "cantrips": ["Guidance", "Sacred Flame", "Thaumaturgy"],
                "prepared": ["Bless", "Cure Wounds", "Guiding Bolt", "Shield of Faith"],
                "magic_initiate": {"ability": "wis", "cantrips": ["Light", "Spare the Dying"],
                                   "prepared": ["Healing Word"], "free_casts_per_long_rest": 1},
            })
    hp = preset["hit_die"] + modifiers["con"]
    return {
        "name": name.strip(), "concept": concept, "class": class_name, "species": "Human",
        "background": preset["background"], "level": 1, "abilities": abilities,
        "modifiers": modifiers, "proficiency_bonus": 2, "hp": hp, "max_hp": hp,
        "ac": preset["ac"], "ac_basis": {"Fighter": "Chain Mail 16 + Defense 1",
            "Rogue": "Leather 11 + Dexterity", "Wizard": "Unarmored 10 + Dexterity; Mage Armor not cast",
            "Cleric": "Chain Shirt 13 + Dexterity (-1) + Shield 2"}[class_name],
        "skills": skills, "skill_sources": skill_sources, "resources": resources,
        "equipment": preset["equipment"], "gold": preset["gold"], "features": features,
        "spells": spells, "speed": 30, "size": "Medium", "creature_type": "Humanoid",
        "initiative": modifiers["dex"] + (2 if class_name == "Rogue" else 0),
        "saving_throws": {key: modifiers[key] + (2 if key in preset["saves"] else 0)
                          for key in _ABILITIES},
        "proficiencies": {"saving_throws": preset["saves"], "tools": preset["tools"],
                          "weapons": preset["weapons"], "armor": preset["armor"]},
        "languages": ["Common", "Elvish", "Dwarvish"] + (
            ["Thieves' Cant", "Goblin"] if class_name == "Rogue" else []),
        "build_choices": {"standard_array": dict(zip(_ABILITIES, preset["base"])),
                          "background_increases": preset["boost"],
                          "equipment_option": "A for class and background"},
        "coverage": {"full_rules_engine": False, "edition": "2024 / SRD 5.2.1",
                     "scope": "Curated level-1 Human starter; other creation choices unavailable",
                     "automation": "Sheet creation and derived bonuses only; features describe rules"},
        "rule_sources": [{"title": "SRD 5.2.1", "url": SRD_SOURCE,
                          "pages": "19–23, 36–38, 47–48, 61–62, 77–78, 83, 86–88, 92"}],
    }

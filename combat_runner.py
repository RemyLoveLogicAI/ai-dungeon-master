from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from audio_synth import generate_all_sfx
from combat_log import (
    CombatLog,
    CombatLogEntry,
    load_log,
    record_entry,
    save_log,
    verify_log,
)
from combat_schema import require_validator
from d20_rules import AdvantageMode, AttackRequest, DamageType, DiceSource
from encounter_ai import CombatActionType, EncounterEnemy
from encounter_generator import CreatureCandidate, Difficulty, generate_encounter


def run_simulated_encounter(
    dice: DiceSource | None = None,
    log_path: str | os.PathLike[str] | None = None,
    validate_schema: bool = False,
    audio_dir: str | os.PathLike[str] | None = None,
):
    """Run the demonstration encounter.

    Pass ``dice`` to make the run reproducible; each attack is logged as a
    replayable event/result pair and verified at the end. ``log_path`` writes
    and re-verifies a durable log. ``validate_schema`` checks it against the
    published JSON Schema. ``audio_dir`` overrides the generated SFX directory.
    """
    if validate_schema:
        require_validator()
    print("=" * 60)
    print("      AI DUNGEON MASTER: D20 TACTICAL COMBAT ENGINE        ")
    print("=" * 60)

    audio_dir = (
        os.path.join(os.getcwd(), "audio_output") if audio_dir is None else audio_dir
    )
    audio_dir = os.fspath(audio_dir)
    sfx_paths = generate_all_sfx(audio_dir)
    print(f"[*] Procedural audio SFX initialized in {audio_dir}")

    # 2. Combatants
    player_name = "Paladin Alden"
    player_max_hp = 38
    player_hp = player_max_hp
    player_ac = 16
    player_attack_mod = 5

    enemy = EncounterEnemy("Shadow Gargoyle", max_hp=35, ac=14, spell_slots=2)
    distance = 4.0  # meters

    print("[*] Encounter started:")
    print(f"    Player: {player_name} (HP {player_hp}, AC {player_ac})")
    print(
        f"    Enemy:  {enemy.name} (HP {enemy.current_hp}, AC {enemy.ac}, Stance: {enemy.stance.value})"
    )
    print("-" * 60)

    entries: list[CombatLogEntry] = []
    round_num = 1
    while player_hp > 0 and enemy.current_hp > 0:
        print(f"\n--- ROUND {round_num} (Distance: {distance:.1f}m) ---")

        # Player Turn
        print(f"\n[Turn: {player_name}]")
        player_request = AttackRequest(
            attacker=player_name,
            target=enemy.name,
            attack_modifier=player_attack_mod,
            target_ac=enemy.ac,
            damage_dice_count=1,
            damage_die_sides=8,
            damage_modifier=3,
            damage_type=DamageType.SLASHING,
            advantage=AdvantageMode.NORMAL,
        )
        player_entry, res = record_entry(
            player_request, sequence=len(entries) + 1, dice=dice
        )
        entries.append(player_entry)
        print(res.combat_message)

        if res.is_hit:
            enemy.apply_damage(res.damage_dealt)
            if res.is_critical:
                print(f"  [AUDIO TRIGGER: {sfx_paths['crit_fanfare']}]")
            else:
                print(f"  [AUDIO TRIGGER: {sfx_paths['sword_clash']}]")
        else:
            print(f"  [AUDIO TRIGGER: {sfx_paths['dice_roll']}]")

        print(
            f"  -> {enemy.name} HP: {enemy.current_hp}/{enemy.max_hp} (Stance: {enemy.stance.value})"
        )

        if enemy.current_hp <= 0:
            print(f"\nVICTORY! {enemy.name} has been defeated by {player_name}!")
            break

        # Enemy Turn
        print(f"\n[Turn: {enemy.name}]")
        decision = enemy.decide_turn_action(distance)
        print(f"  AI Rationale: {decision.rationale}")

        if decision.action == CombatActionType.FLEE:
            print(f"  -> {enemy.name} breaks engagement and flees into the shadows!")
            break
        elif decision.action == CombatActionType.DODGE:
            print(f"  -> {enemy.name} readies defensive stance.")
        else:
            # Attack. Taking the turn is what spends the slot: deciding did not.
            enemy.commit_decision(decision)
            enemy_request = AttackRequest(
                attacker=enemy.name,
                target=player_name,
                attack_modifier=decision.attack_modifier,
                target_ac=player_ac,
                damage_dice_count=decision.damage_dice_count,
                damage_die_sides=decision.damage_die_sides,
                damage_modifier=decision.damage_modifier,
                damage_type=decision.damage_type,
            )
            enemy_entry, e_res = record_entry(
                enemy_request, sequence=len(entries) + 1, dice=dice
            )
            entries.append(enemy_entry)
            print(f"  {e_res.combat_message}")
            if e_res.is_hit:
                player_hp = max(0, player_hp - e_res.damage_dealt)
                if decision.damage_type == DamageType.FIRE:
                    print(f"  [AUDIO TRIGGER: {sfx_paths['fireball_impact']}]")
                else:
                    print(f"  [AUDIO TRIGGER: {sfx_paths['sword_clash']}]")
            print(f"  -> {player_name} HP: {max(0, player_hp)}/{player_max_hp}")

        if player_hp <= 0:
            print(f"\nDEFEAT! {player_name} has been defeated by {enemy.name}!")
            break

        # Engage distance adjusts
        if distance > 1.5:
            distance = max(1.0, distance - 1.5)

        round_num += 1

    # The loop ends on victory, on the enemy fleeing, or when the player falls.
    # Victory and fleeing print as they happen; a dead player is the silent exit,
    # so it has to be reported here or the outcome is indistinguishable.
    if player_hp <= 0:
        print(f"\nDEFEAT! {player_name} has fallen to {enemy.name}!")

    print("\n" + "=" * 60)
    print("                 ENCOUNTER CONCLUDED                      ")
    print("=" * 60)

    # Deterministic-replay check: every logged attack must reproduce from its own
    # recorded die results, without access to the generator that produced them.
    log = CombatLog(entries=tuple(entries))
    if len(log):
        status = "OK" if verify_log(log) else "MISMATCH"
        print(f"[Replay] {len(log)} attack events replayed deterministically: {status}")

    # Durable round trip: persist the envelope, load it back through the strict
    # boundary, and prove the reloaded log still replays to the same results.
    if log_path is not None:
        saved = save_log(log, log_path)
        restored = load_log(saved, validate_schema=validate_schema)
        status = "OK" if verify_log(restored) else "MISMATCH"
        scope = "schema + readers" if validate_schema else "readers"
        print(
            f"[Log] {len(restored)} entries written to {saved} and verified on reload "
            f"({scope}): {status}"
        )


def _parse_damage_type(val: Any) -> DamageType:
    if isinstance(val, DamageType):
        return val
    s = str(val).strip().upper()
    try:
        return DamageType[s]
    except KeyError:
        for dt in DamageType:
            if dt.value.upper() == s:
                return dt
    return DamageType.SLASHING


def _parse_cr(cr_val: Any) -> float:
    if isinstance(cr_val, (int, float)):
        return float(cr_val)
    s = str(cr_val).strip()
    if "/" in s:
        parts = s.split("/")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            denom = int(parts[1])
            if denom != 0:
                return int(parts[0]) / denom
    try:
        return float(s)
    except ValueError:
        return 0.0


@dataclass
class CombatantState:
    """The 5-stat core combatant block grounded in CORE-GAME-LOOP-SPEC.md.

    Every combatant (PC or monster) runs on:
    1. HP (current, max, formula) - the single defeat clock
    2. AC (armor class, optional ac_source)
    3. Attack modifier (bonus added to d20)
    4. Damage profile (dice, sides, modifier, type)
    5. Initiative / stance (aggressive, defensive, etc.)
    """

    name: str
    current_hp: int
    max_hp: int
    ac: int
    attack_modifier: int
    damage_dice_count: int = 1
    damage_die_sides: int = 6
    damage_modifier: int = 2
    damage_type: DamageType = DamageType.SLASHING
    hp_formula: str = ""
    ac_source: str = ""
    abilities: dict[str, int] = field(
        default_factory=lambda: {
            "str": 10,
            "dex": 10,
            "con": 10,
            "int": 10,
            "wis": 10,
            "cha": 10,
        }
    )
    cr: float = 0.0
    xp: int = 0
    stance: str = "aggressive"

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Combatant name cannot be empty")
        if self.max_hp <= 0:
            raise ValueError(f"max_hp must be positive, got {self.max_hp}")
        self.current_hp = max(0, min(self.current_hp, self.max_hp))
        if self.ac < 0:
            raise ValueError(f"ac must be nonnegative, got {self.ac}")
        if self.damage_dice_count <= 0 or self.damage_die_sides <= 0:
            raise ValueError("damage dice count and sides must be positive")

    @classmethod
    def from_state_block(cls, data: Mapping[str, Any]) -> CombatantState:
        name = str(data.get("name", "Unnamed Combatant"))
        hp_data = data.get("hp", {})
        if isinstance(hp_data, Mapping):
            max_hp = int(hp_data.get("max", 10))
            current_hp = int(hp_data.get("current", max_hp))
            hp_formula = str(hp_data.get("formula", ""))
        else:
            max_hp = int(hp_data)
            current_hp = max_hp
            hp_formula = ""

        ac = int(data.get("ac", 10))
        ac_source = str(data.get("ac_source", ""))
        attack_modifier = int(data.get("attack_modifier", 2))

        dmg_data = data.get("damage", {})
        if isinstance(dmg_data, Mapping):
            damage_dice = int(dmg_data.get("dice", 1))
            damage_sides = int(dmg_data.get("sides", 6))
            damage_mod = int(dmg_data.get("modifier", 0))
            damage_type = _parse_damage_type(dmg_data.get("type", DamageType.SLASHING))
        else:
            damage_dice, damage_sides, damage_mod, damage_type = 1, 6, 0, DamageType.SLASHING

        abilities_raw = data.get("abilities", {})
        abilities = (
            {k.lower(): int(v) for k, v in abilities_raw.items()}
            if isinstance(abilities_raw, Mapping)
            else {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
        )

        cr = _parse_cr(data.get("cr", 0))
        xp = int(data.get("xp", 0))
        stance = str(data.get("stance", "aggressive")).lower()

        return cls(
            name=name,
            current_hp=current_hp,
            max_hp=max_hp,
            ac=ac,
            attack_modifier=attack_modifier,
            damage_dice_count=damage_dice,
            damage_die_sides=damage_sides,
            damage_modifier=damage_mod,
            damage_type=damage_type,
            hp_formula=hp_formula,
            ac_source=ac_source,
            abilities=abilities,
            cr=cr,
            xp=xp,
            stance=stance,
        )

    def to_state_block(self) -> dict[str, Any]:
        dtype_str = (
            self.damage_type.value.lower()
            if isinstance(self.damage_type, DamageType)
            else str(self.damage_type).lower()
        )
        return {
            "name": self.name,
            "hp": {
                "current": self.current_hp,
                "max": self.max_hp,
                "formula": self.hp_formula,
            },
            "ac": self.ac,
            "ac_source": self.ac_source,
            "attack_modifier": self.attack_modifier,
            "damage": {
                "dice": self.damage_dice_count,
                "sides": self.damage_die_sides,
                "modifier": self.damage_modifier,
                "type": dtype_str,
            },
            "abilities": dict(self.abilities),
            "cr": self.cr,
            "xp": self.xp,
            "stance": self.stance,
        }

    @classmethod
    def from_candidate(
        cls, candidate: CreatureCandidate | Mapping[str, Any], count_index: int = 1
    ) -> CombatantState:
        if isinstance(candidate, CreatureCandidate):
            name = candidate.name
            xp = candidate.xp
            cr_raw = candidate.cr
            facets = dict(candidate.facets)
        else:
            name = str(candidate.get("name", "Unknown Creature"))
            xp = int(candidate.get("xp", candidate.get("xp_per_unit", 50)))
            cr_raw = candidate.get("cr", "")
            facets = dict(candidate.get("facets", {}))

        cr = _parse_cr(cr_raw)
        if count_index > 1:
            name = f"{name} #{count_index}"

        if "hp" in facets and "ac" in facets:
            sb = dict(facets)
            sb.setdefault("name", name)
            sb.setdefault("xp", xp)
            sb.setdefault("cr", cr)
            return cls.from_state_block(sb)

        hp_val = int(facets.get("hp", max(7, int(xp * 0.15 + 6))))
        ac_val = int(facets.get("ac", 14 if cr >= 2.0 else 13 if cr >= 0.25 else 12))
        att_mod = int(facets.get("attack_modifier", 5 if cr >= 2.0 else 4 if cr >= 0.25 else 3))
        dmg_type = _parse_damage_type(facets.get("damage_type", DamageType.SLASHING))
        dmg_dice = int(facets.get("damage_dice", 2 if cr >= 1.0 else 1))
        dmg_sides = int(facets.get("damage_sides", 8 if cr >= 1.0 else 6))
        dmg_mod = int(facets.get("damage_modifier", 3 if cr >= 1.0 else 2))

        return cls(
            name=name,
            current_hp=hp_val,
            max_hp=hp_val,
            ac=ac_val,
            attack_modifier=att_mod,
            damage_dice_count=dmg_dice,
            damage_die_sides=dmg_sides,
            damage_modifier=dmg_mod,
            damage_type=dmg_type,
            cr=cr,
            xp=xp,
            stance=str(facets.get("stance", "aggressive")),
        )


def run_encounter(
    party: Sequence[CombatantState],
    enemies: Sequence[CombatantState],
    *,
    dice: DiceSource | None = None,
    max_rounds: int = 50,
) -> dict[str, Any]:
    """Execute the core combat loop between party and enemies per CORE-GAME-LOOP-SPEC.md."""
    if not party:
        raise ValueError("party cannot be empty")
    if not enemies:
        raise ValueError("enemies cannot be empty")

    entries: list[CombatLogEntry] = []
    rounds_executed = 0
    outcome = "stalemate"
    narrative = ""

    for round_num in range(1, max_rounds + 1):
        rounds_executed = round_num

        # 1. Party turns: each living PC attacks the first living enemy
        for pc in party:
            if pc.current_hp <= 0:
                continue
            living_enemies = [e for e in enemies if e.current_hp > 0]
            if not living_enemies:
                break
            target = living_enemies[0]
            req = AttackRequest(
                attacker=pc.name,
                target=target.name,
                attack_modifier=pc.attack_modifier,
                target_ac=target.ac,
                damage_dice_count=pc.damage_dice_count,
                damage_die_sides=pc.damage_die_sides,
                damage_modifier=pc.damage_modifier,
                damage_type=pc.damage_type,
                advantage=AdvantageMode.NORMAL,
            )
            entry, res = record_entry(req, sequence=len(entries) + 1, dice=dice)
            entries.append(entry)
            if res.is_hit:
                target.current_hp = max(0, target.current_hp - res.damage_dealt)

        if all(e.current_hp <= 0 for e in enemies):
            outcome = "victory"
            narrative = f"Victory! The party defeated all {len(enemies)} enemy combatants."
            break

        # 2. Enemy turns: each living enemy attacks the first living PC
        for enemy in enemies:
            if enemy.current_hp <= 0:
                continue
            living_pcs = [p for p in party if p.current_hp > 0]
            if not living_pcs:
                break
            target = living_pcs[0]
            req = AttackRequest(
                attacker=enemy.name,
                target=target.name,
                attack_modifier=enemy.attack_modifier,
                target_ac=target.ac,
                damage_dice_count=enemy.damage_dice_count,
                damage_die_sides=enemy.damage_die_sides,
                damage_modifier=enemy.damage_modifier,
                damage_type=enemy.damage_type,
                advantage=AdvantageMode.NORMAL,
            )
            entry, res = record_entry(req, sequence=len(entries) + 1, dice=dice)
            entries.append(entry)
            if res.is_hit:
                target.current_hp = max(0, target.current_hp - res.damage_dealt)

        # Check party defeat -> Mercy rule narrative intervention
        if all(p.current_hp <= 0 for p in party):
            outcome = "mercy_rule"
            narrative = (
                "Mercy rule narrative intervention: All party members have fallen unconscious, "
                "spared from death by fate."
            )
            break

    total_xp = sum(e.xp for e in enemies) if outcome == "victory" else 0
    log = CombatLog(entries=tuple(entries))

    game_events = [
        {
            "schema": "gpf/game-event.v1",
            "sequence": entry.event.sequence,
            "type": "attack_resolved",
            "attacker": entry.result.attacker,
            "target": entry.result.target,
            "is_hit": entry.result.is_hit,
            "is_critical": entry.result.is_critical,
            "damage_dealt": entry.result.damage_dealt,
            "combat_message": entry.result.message,
        }
        for entry in entries
    ]

    return {
        "outcome": outcome,
        "rounds": rounds_executed,
        "xp_awarded": total_xp,
        "narrative": narrative,
        "party": [p.to_state_block() for p in party],
        "enemies": [e.to_state_block() for e in enemies],
        "log": log,
        "game_events": game_events,
    }


def run_generated_encounter(
    party: Sequence[CombatantState],
    candidates: Sequence[CreatureCandidate],
    target_difficulty: str | Difficulty = Difficulty.MEDIUM,
    *,
    seed: int | None = None,
    dice: DiceSource | None = None,
    max_rounds: int = 50,
) -> dict[str, Any]:
    """Generate an encounter using encounter_generator.py and execute it via the core loop."""
    if not party:
        raise ValueError("party cannot be empty")

    party_levels = [int(p.abilities.get("level", 3)) for p in party]
    encounter_payload = generate_encounter(
        party=party_levels,
        candidates=candidates,
        target_difficulty=target_difficulty,
        seed=seed,
    )

    monsters = encounter_payload.get("monsters", [])
    enemy_combatants: list[CombatantState] = []
    counts_by_name: dict[str, int] = {}
    for m in monsters:
        name = str(m.get("name", "Unknown"))
        counts_by_name[name] = counts_by_name.get(name, 0) + 1
        combatant = CombatantState.from_candidate(m, count_index=counts_by_name[name])
        enemy_combatants.append(combatant)

    combat_result = run_encounter(party, enemy_combatants, dice=dice, max_rounds=max_rounds)
    return {
        "encounter": encounter_payload,
        **combat_result,
    }


if __name__ == "__main__":
    run_simulated_encounter()


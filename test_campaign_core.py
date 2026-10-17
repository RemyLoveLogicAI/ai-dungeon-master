from concurrent.futures import ThreadPoolExecutor

import pytest

from campaign_core import (
    CampaignStore,
    ConflictError,
    NotFoundError,
    build_starter_character,
    character_catalog,
)


def test_store_persists_and_preserves_identity(tmp_path):
    path = tmp_path / "campaigns.sqlite3"
    store = CampaignStore(path)
    original = store.create({"title": "Moon", "id": "untrusted", "revision": 42})
    assert original["revision"] == 0
    assert original["id"] != "untrusted"
    assert CampaignStore(path).get(original["id"]) == original
    assert store.list_summaries()[0]["id"] == original["id"]
    with pytest.raises(NotFoundError):
        store.get("00000000-0000-4000-8000-000000000000")


def test_commit_cas_replay_and_request_fingerprint(tmp_path):
    store = CampaignStore(tmp_path / "state.db")
    original = store.create({"title": "Moon"})
    cid = original["id"]
    assert store.lookup_request(cid, "r1", "look") is None
    first = store.commit(cid, 0, "r1", "look", {"title": "First", "id": "bad"})
    assert first["id"] == cid
    assert first["revision"] == 1
    store.commit(cid, 1, "r2", "walk", {"title": "Second"})
    assert store.lookup_request(cid, "r1", "look") == first
    assert store.commit(cid, 0, "r1", "look", {"ignored": True}) == first
    with pytest.raises(ConflictError, match="request"):
        store.lookup_request(cid, "r1", "different")
    with pytest.raises(ConflictError, match="request"):
        store.commit(cid, 2, "r1", "different", {})
    with pytest.raises(ConflictError, match="revision"):
        store.commit(cid, 0, "r3", "wait", {})
    assert store.get(cid)["title"] == "Second"


def test_concurrent_duplicate_commits_apply_once(tmp_path):
    store = CampaignStore(tmp_path / "state.db")
    cid = store.create({})["id"]
    def commit(index):
        return store.commit(cid, 0, "same", "look", {"winner": index})
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(commit, range(8)))
    assert all(result == results[0] for result in results)
    assert store.get(cid)["revision"] == 1


def test_distinct_concurrent_commits_have_one_winner(tmp_path):
    store = CampaignStore(tmp_path / "state.db")
    cid = store.create({})["id"]
    def commit(index):
        try:
            store.commit(cid, 0, f"r{index}", "look", {})
            return True
        except ConflictError:
            return False
    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(commit, range(8))) == 1


def test_media_updates_only_current_revision_and_keeps_replay(tmp_path):
    store = CampaignStore(tmp_path / "state.db")
    cid = store.create({})["id"]
    first = store.commit(cid, 0, "r1", "look", {})
    assert store.update_media(cid, 1, "image", {"status": "ready", "url": "/media/1"})
    state = store.get(cid)
    assert state["revision"] == 1
    assert state["media"]["image"]["status"] == "ready"
    assert store.lookup_request(cid, "r1", "look") == first
    store.commit(cid, 1, "r2", "walk", {})
    assert not store.update_media(cid, 1, "image", {"status": "ready"})
    assert "media" not in store.get(cid)


@pytest.mark.parametrize("bad", ["", "../x", "x" * 129, None])
def test_request_validation(tmp_path, bad):
    store = CampaignStore(tmp_path / "state.db")
    cid = store.create({})["id"]
    with pytest.raises(ValueError):
        store.commit(cid, 0, bad, "look", {})


def test_state_validation_and_revision_types(tmp_path):
    store = CampaignStore(tmp_path / "state.db")
    with pytest.raises(ValueError):
        store.create({"x": float("nan")})
    with pytest.raises(ValueError):
        store.create({"x": "x" * 2_100_000})
    with pytest.raises(TypeError):
        store.create([])
    cid = store.create({})["id"]
    with pytest.raises(TypeError):
        store.commit(None, 0, "r", "look", {})
    with pytest.raises(ValueError):
        store.commit(cid, True, "r", "look", {})
    with pytest.raises(ValueError):
        store.commit(cid, 0, "r", "   ", {})
    with pytest.raises(TypeError):
        store.update_media(cid, 0, None, {})
    with pytest.raises(ValueError):
        store.update_media(cid, 0, "../image", {})


@pytest.mark.parametrize("class_name,hp,ac", [
    ("Fighter", 12, 17), ("Rogue", 10, 14), ("Wizard", 8, 11), ("Cleric", 9, 14),
])
def test_legal_starter_sheets(class_name, hp, ac):
    character = build_starter_character({"class": class_name, "name": "Arin", "concept": "Explorer"})
    assert character["name"] == "Arin"
    assert character["concept"] == "Explorer"
    assert character["species"] == "Human"
    assert character["level"] == 1
    assert character["hp"] == character["max_hp"] == hp
    assert character["ac"] == ac
    assert character["proficiency_bonus"] == 2
    assert character["modifiers"] == {
        ability: (score - 10) // 2 for ability, score in character["abilities"].items()
    }
    assert sum(character["abilities"].values()) == 75
    assert "Skilled" in character["features"]
    assert character["rule_sources"]
    assert character["coverage"]["full_rules_engine"] is False


@pytest.mark.parametrize("data", [
    {"class": "Warlock"}, {"class": "Wizard", "level": 140},
    {"class": "Wizard", "abilities": {"int": 20}},
    {"class": "Wizard", "species": "Elf"}, {"class": "Wizard", "hp": 999},
    {"class": "Wizard", "name": "x" * 81}, {"class": "Wizard", "level": True},
])
def test_starter_rejects_unsupported_or_tampered_options(data):
    with pytest.raises(ValueError):
        build_starter_character(data)


def test_origin_class_choices_are_recorded_and_not_shared():
    rogue = build_starter_character({"class": "Rogue"})
    assert rogue["skills"]["Stealth"] == 7
    assert rogue["skills"]["Sleight of Hand"] == 7
    assert rogue["initiative"] == 5
    assert rogue["features"]["Expertise"] == ["Sleight of Hand", "Stealth"]
    wizard = build_starter_character({"class": "Wizard"})
    assert len(wizard["spells"]["spellbook"]) == 6
    assert len(wizard["spells"]["prepared"]) == 4
    assert wizard["resources"]["spell_slots_1"]["max"] == 2
    assert wizard["spells"]["magic_initiate"]["ability"] == "int"
    wizard["equipment"].clear()
    assert build_starter_character({"class": "Wizard"})["equipment"]
    assert len(character_catalog()["classes"]) == 4

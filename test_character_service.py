import pytest

from campaign_core import PORTRAITS, CampaignStore, character_catalog
from engine.character_service import create_character, get_current_character
from engine.story_engine import PlayerCharacter, StoryEngine


def test_create_character_persists_starter_sheet(tmp_path):
    store = CampaignStore(tmp_path / "campaigns.sqlite3")
    created = create_character(store, {"name": "Rilla Ashgrove", "class": "Wizard"})
    assert created["revision"] == 0
    assert created["character"]["name"] == "Rilla Ashgrove"
    assert created["character"]["class"] == "Wizard"


def test_create_character_defaults_appearance_and_portrait_when_omitted(tmp_path):
    store = CampaignStore(tmp_path / "campaigns.sqlite3")
    created = create_character(store, {"name": "No Frills", "class": "Fighter"})
    assert created["character"]["appearance"] == ""
    assert created["character"]["portrait_id"] == ""


def test_create_character_persists_appearance_and_portrait(tmp_path):
    store = CampaignStore(tmp_path / "campaigns.sqlite3")
    created = create_character(store, {
        "name": "Vex Nightshade",
        "class": "Rogue",
        "appearance": "Lean, silver-streaked hair, a scar over one eyebrow.",
        "portrait_id": "shadow",
    })
    character = created["character"]
    assert character["appearance"] == "Lean, silver-streaked hair, a scar over one eyebrow."
    assert character["portrait_id"] == "shadow"

    fetched = get_current_character(store, created["id"])
    assert fetched["appearance"] == character["appearance"]
    assert fetched["portrait_id"] == "shadow"


def test_create_character_rejects_unknown_portrait_id(tmp_path):
    store = CampaignStore(tmp_path / "campaigns.sqlite3")
    with pytest.raises(ValueError):
        create_character(store, {"name": "Nope", "class": "Fighter", "portrait_id": "not-a-real-one"})


def test_character_catalog_lists_known_portraits():
    catalog = character_catalog()
    assert catalog["portraits"] == [dict(p) for p in PORTRAITS]
    assert {p["id"] for p in catalog["portraits"]} == {"sentinel", "shadow", "arcane", "devout", "wanderer"}


def test_get_current_character_round_trips_and_handles_unknown_id(tmp_path):
    store = CampaignStore(tmp_path / "campaigns.sqlite3")
    created = create_character(store, {"name": "Borin Oakhand", "class": "Fighter"})
    fetched = get_current_character(store, created["id"])
    assert fetched == created["character"]
    assert get_current_character(store, "00000000-0000-4000-8000-000000000000") is None


def test_create_character_rejects_unsupported_class(tmp_path):
    store = CampaignStore(tmp_path / "campaigns.sqlite3")
    with pytest.raises(ValueError):
        create_character(store, {"name": "Nope", "class": "Bard"})


@pytest.mark.parametrize(
    ("class_name", "expected_ac", "primary_ability"),
    [
        ("Fighter", 17, "str"),
        ("Rogue", 14, "dex"),
        ("Wizard", 11, "int"),
        ("Cleric", 14, "wis"),
    ],
)
def test_player_character_from_sheet_maps_distinct_builds(tmp_path, class_name, expected_ac, primary_ability):
    store = CampaignStore(tmp_path / "campaigns.sqlite3")
    created = create_character(store, {"name": "Test Hero", "class": class_name})
    sheet = created["character"]

    pc = PlayerCharacter.from_sheet(sheet)

    assert pc.name == "Test Hero"
    assert pc.class_title == class_name
    assert pc.ac == expected_ac
    assert pc.max_hp == sheet["hp"]
    assert pc.current_hp == sheet["hp"]
    assert pc.attack_bonus == sheet["proficiency_bonus"] + sheet["modifiers"][primary_ability]
    assert pc.inventory == sheet["equipment"]
    assert pc.gold == sheet["gold"]


def test_story_engine_defaults_unchanged_without_player():
    engine = StoryEngine()
    assert engine.player.name == "Paladin Alden"


def test_story_engine_accepts_custom_player():
    custom = PlayerCharacter(name="Someone Else")
    engine = StoryEngine(player=custom)
    assert engine.player.name == "Someone Else"

import json

import pytest

import tui_runner
from game_foundation import STARTER_SCENARIO
from game_foundation import to_agentsurface_v01 as scenario_export
from genui import (
    ANSI,
    GenUIBlueprintFactory,
    SurfaceBlueprint,
    TerminalSurfaceRenderer,
    UIComponent,
    UIComponentType,
)


def _build_blueprint(**overrides):
    params = {
        "surface_id": "encounter-round-1",
        "title": "Dungeon Crypt Encounter",
        "round_num": 1,
        "hero_name": "Kaelen the Paladin",
        "hero_hp": 20,
        "hero_max_hp": 35,
        "hero_conditions": ["Prone"],
        "hero_actions_available": {"Action": True, "BonusAction": False, "Reaction": True},
        "enemy_name": "Shadow Gargoyle",
        "enemy_hp": 30,
        "enemy_max_hp": 30,
        "enemy_stance": "Tactical",
        "combat_log": ["one", "two", "three", "four", "five", "six"],
        "tension_level": 0.53,
    }
    params.update(overrides)
    return GenUIBlueprintFactory.create_encounter_surface(**params)


def test_blueprint_component_tree_is_unique_and_reachable_from_root():
    blueprint = _build_blueprint()
    assert isinstance(blueprint, SurfaceBlueprint)

    components = blueprint.to_dict()["components"]
    by_id = {component["id"]: component for component in components}
    assert len(by_id) == len(components)

    roots = [component for component in components if component["parentId"] is None]
    assert [component["id"] for component in roots] == ["root"]

    children = {}
    for component in components:
        children.setdefault(component["parentId"], []).append(component["id"])

    reachable = set()
    pending = ["root"]
    while pending:
        current = pending.pop()
        assert current not in reachable
        reachable.add(current)
        pending.extend(children.get(current, []))
    assert reachable == set(by_id)


def test_blueprint_is_json_serializable_and_reports_bound_state():
    blueprint = _build_blueprint(tension_level=0.85)
    payload = json.loads(blueprint.to_json())
    assert payload == blueprint.to_dict()
    assert payload["surfaceId"] == "encounter-round-1"

    by_id = {component["id"]: component for component in payload["components"]}
    tension = by_id["metric-tension"]["props"]
    assert tension["value"] == "85%"
    assert tension["trend"] == "CRITICAL"
    assert tension["variant"] == "danger"
    assert by_id["metric-stance"]["props"]["value"] == "Tactical"

    # Action economy availability is surfaced on the matching buttons.
    assert by_id["btn-attack"]["props"]["enabled"] is True
    assert by_id["btn-dodge"]["props"]["enabled"] is True
    assert by_id["btn-rest"]["props"]["enabled"] is True


def test_blueprint_marks_only_the_most_recent_log_entry_as_body():
    blueprint = _build_blueprint(combat_log=["a", "b", "c", "d", "e", "f"])
    by_id = {component["id"]: component for component in blueprint.to_dict()["components"]}
    entries = [by_id[f"log-entry-{i}"]["props"] for i in range(4)]
    assert [entry["content"] for entry in entries] == ["c", "d", "e", "f"]
    assert [entry["variant"] for entry in entries] == ["caption", "caption", "caption", "body"]


def test_blueprint_omits_condition_badges_when_none_present():
    blueprint = _build_blueprint(hero_conditions=[])
    ids = {component["id"] for component in blueprint.to_dict()["components"]}
    assert not any(component_id.startswith("cond-") for component_id in ids)


def test_health_bar_fills_proportionally_and_clamps_out_of_range_values():
    full = TerminalSurfaceRenderer.render_health_bar(100, 100, width=10)
    assert full.count("█") == 10
    assert full.count("░") == 0
    assert "100/100 HP" in full

    half = TerminalSurfaceRenderer.render_health_bar(50, 100, width=10)
    assert half.count("█") == 5
    assert half.count("░") == 5

    empty = TerminalSurfaceRenderer.render_health_bar(0, 100, width=10)
    assert empty.count("█") == 0
    assert empty.count("░") == 10

    # Overheal and a zero maximum must not overflow or divide by zero.
    assert TerminalSurfaceRenderer.render_health_bar(150, 100, width=10).count("█") == 10
    assert TerminalSurfaceRenderer.render_health_bar(5, 0, width=10).count("█") == 0


def test_tactical_grid_places_hero_enemy_and_cover_and_sizes_to_height():
    lines = TerminalSurfaceRenderer.render_tactical_grid(
        width=8,
        height=4,
        hero_pos=(1, 1),
        enemy_pos=(6, 2),
        cover_positions=[(3, 1)],
        biome="Test Arena",
    )
    assert len(lines) == 6  # header + height rows + legend
    assert "Test Arena" in lines[0]
    assert "@" in lines[2]  # y == 1 is the second grid row
    assert "G" in lines[3]  # y == 2 is the third grid row
    assert "#" in lines[2]
    assert "Legend" in lines[-1]


def test_render_panel_wraps_title_and_content_with_borders():
    rendered = TerminalSurfaceRenderer.render_panel("COMBAT STATUS", ["line one", "line two"])
    rows = rendered.splitlines()
    assert rows[0].startswith(ANSI.CYAN)
    assert "COMBAT STATUS" in rows[0]
    assert rows[0].endswith(ANSI.RESET)
    assert len(rows) == 4  # top border + two content rows + bottom border
    assert "line one" in rows[1]
    assert "line two" in rows[2]


def test_ui_component_type_values_are_stable_for_consumers():
    # Cross-repo clients dispatch on these literal strings.
    assert UIComponentType.TACTICAL_GRID.value == "TacticalGrid"
    assert UIComponentType.ACTION_BUTTON.value == "ActionButton"
    assert UIComponent(id="x", type="Text").parentId is None


def test_tui_encounter_runs_to_completion_and_returns_a_blueprint(monkeypatch):
    # Keep the smoke test hermetic: no WAV synthesis, no real sleeping.
    monkeypatch.setattr(tui_runner, "generate_all_sfx", lambda output_dir: {})
    monkeypatch.setattr(tui_runner.time, "sleep", lambda _seconds: None)

    blueprint = tui_runner.run_tui_encounter(max_rounds=6)

    assert isinstance(blueprint, SurfaceBlueprint)
    payload = blueprint.to_dict()
    assert payload["surfaceId"].startswith("encounter-round-")
    assert any(
        component["type"] == UIComponentType.ACTION_BUTTON.value
        for component in payload["components"]
    )


def test_export_matches_the_shared_agentsurface_contract():
    """The local blueprint and the scenario adapter emit one envelope shape.

    Previously the two producers declared the same adapter version but emitted
    different structures (``surfaceId``/``theme``/``parentId`` here versus
    ``surface``/``dataModel``/``children`` there), so no consumer could handle
    both.
    """
    envelope = _build_blueprint().to_agentsurface_v01()
    reference = scenario_export(STARTER_SCENARIO)

    assert (
        set(envelope)
        == set(reference)
        == {
            "surface",
            "dataModel",
            "components",
            "intents",
        }
    )
    assert envelope["surface"] == {
        "id": "encounter-round-1",
        "title": "Dungeon Crypt Encounter",
        "subtitle": "",
        "width": "wide",
    }
    assert json.loads(json.dumps(envelope)) == envelope


def test_exported_components_are_flat_unique_and_reachable_from_root():
    envelope = _build_blueprint().to_agentsurface_v01()
    components = envelope["components"]
    by_id = {component["id"]: component for component in components}

    assert len(by_id) == len(components)
    assert all("parentId" not in component for component in components)
    assert all(set(component) <= {"id", "type", "props", "children"} for component in components)

    reachable = set()
    pending = ["root"]
    while pending:
        current = pending.pop()
        assert current not in reachable
        reachable.add(current)
        pending.extend(by_id[current].get("children", []))
    assert reachable == set(by_id)


def test_exported_buttons_declare_routeable_intents_and_bound_payloads():
    envelope = _build_blueprint().to_agentsurface_v01()
    by_id = {component["id"]: component for component in envelope["components"]}

    assert set(envelope["intents"]) == {
        "HERO_ATTACK",
        "HERO_DODGE",
        "HERO_CAST_SPELL",
        "TAKE_REST",
    }

    attack = by_id["btn-attack"]
    assert attack["type"] == "Button"
    action = attack["props"]["action"]
    assert action["intent"] in envelope["intents"]
    assert action["payloadKeys"]
    assert all(key in envelope["dataModel"] for key in action["payloadKeys"])
    # Parameters travel as bound values a host reads, never as executed props.
    assert envelope["dataModel"]["btn-attack.target"] == "Shadow Gargoyle"


def test_unavailable_actions_export_as_non_interactive_text():
    blueprint = _build_blueprint(hero_actions_available={"Action": False})
    envelope = blueprint.to_agentsurface_v01()
    by_id = {component["id"]: component for component in envelope["components"]}

    for component_id in ("btn-attack", "btn-dodge", "btn-spell"):
        assert by_id[component_id]["type"] == "Text"
        assert by_id[component_id]["props"]["text"].endswith("— unavailable")
    assert by_id["btn-rest"]["type"] == "Button"
    assert envelope["intents"] == ["TAKE_REST"]


def test_export_rejects_a_blueprint_with_no_components():
    with pytest.raises(ValueError):
        SurfaceBlueprint(surfaceId="empty", title="Empty").to_agentsurface_v01()


def test_console_entry_point_returns_none_so_sys_exit_succeeds(monkeypatch):
    # The installed `dungeon-master-tui` wrapper does sys.exit(main()): a non-None
    # return (e.g. the blueprint) would make the process exit non-zero.
    monkeypatch.setattr(tui_runner, "generate_all_sfx", lambda output_dir: {})
    monkeypatch.setattr(tui_runner.time, "sleep", lambda _seconds: None)
    assert tui_runner.main() is None


def test_onboarding_surface_validates_and_exports_expected_intents():
    blueprint = GenUIBlueprintFactory.create_onboarding_surface()
    envelope = blueprint.to_agentsurface_v01()
    assert envelope["surface"]["id"] == "onboarding-stage-1-2"
    assert "CONFIRM_CHARACTER_DRAFT" in envelope["intents"]
    assert "SWITCH_STARTER_ARCHETYPE" in envelope["intents"]
    assert "ADJUST_GUIDANCE" in envelope["intents"]
    by_id = {c["id"]: c for c in envelope["components"]}
    assert by_id["welcome-card"]["type"] == "Card"
    assert by_id["draft-card"]["type"] == "Card"
    assert by_id["btn-confirm"]["type"] == "Button"


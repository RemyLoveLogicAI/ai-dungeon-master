import json

import pytest

from game_foundation import (
    AGENTSURFACE_ADAPTER_VERSION,
    MCP_GAMES_ADAPTER_VERSION,
    STARTER_SCENARIO,
    Choice,
    GameSession,
    Scenario,
    Scene,
    choose,
    start_session,
    to_agentsurface_v01,
    to_mcp_games_v1,
)


def test_scenario_graph_is_complete_and_has_reachable_endings():
    scenario = STARTER_SCENARIO
    scene_ids = {scene.id for scene in scenario.scenes}
    assert scenario.start_scene in scene_ids
    assert len(scene_ids) == 5
    assert all(
        choice.target_scene in scene_ids
        for scene in scenario.scenes
        for choice in scene.choices
    )
    terminal_scenes = {scene.id for scene in scenario.scenes if not scene.choices}
    assert terminal_scenes == {"quiet_return", "rising_tide"}
    reachable = set()
    pending = [scenario.start_scene]
    by_id = scenario.scenes_by_id
    while pending:
        scene_id = pending.pop()
        if scene_id in reachable:
            continue
        reachable.add(scene_id)
        pending.extend(choice.target_scene for choice in by_id[scene_id].choices)
    assert reachable == scene_ids


def test_scenario_rejects_invalid_graph_and_duplicate_choice_ids():
    with pytest.raises(ValueError, match="unknown scene"):
        Scenario(
            id="broken",
            version="1",
            title="Broken",
            description="",
            author="test",
            start_scene="start",
            scenes=(
                Scene(
                    id="start",
                    title="Start",
                    narrative="",
                    choices=(Choice("go", "Go", "missing"),),
                ),
            ),
        )

    with pytest.raises(ValueError, match="unreachable scenes"):
        Scenario(
            id="unreachable",
            version="1",
            title="Unreachable",
            description="",
            author="test",
            start_scene="start",
            scenes=(Scene("start", "Start", ""), Scene("unused", "Unused", "")),
        )

    with pytest.raises(ValueError, match="choice ids"):
        Scenario(
            id="duplicate-choice",
            version="1",
            title="Duplicate",
            description="",
            author="test",
            start_scene="start",
            scenes=(
                Scene(
                    id="start",
                    title="Start",
                    narrative="",
                    choices=(
                        Choice("same", "First", "end"),
                        Choice("same", "Second", "end"),
                    ),
                ),
                Scene("end", "End", ""),
            ),
        )


def test_session_choice_is_immutable_ordered_and_rejects_unavailable_actions():
    initial = start_session(STARTER_SCENARIO)
    next_session = choose(initial, STARTER_SCENARIO, "follow_the_bell")
    assert initial.current_scene == "moonlit_causeway"
    assert initial.events == ()
    assert next_session.current_scene == "sunken_shrine"
    assert next_session.events[0].sequence == 1
    assert next_session.events[0].type == "choice_selected"
    assert next_session.events[0].choice_id == "follow_the_bell"
    assert next_session.events[0].target_scene == "sunken_shrine"

    with pytest.raises(ValueError, match="not available"):
        choose(next_session, STARTER_SCENARIO, "help_the_courier")
    with pytest.raises(ValueError, match="different scenario"):
        choose(GameSession("another-game", "moonlit_causeway"), STARTER_SCENARIO, "follow_the_bell")


def test_mcp_games_v1_export_matches_game_definition_shape_deterministically():
    exported = to_mcp_games_v1(STARTER_SCENARIO)
    assert MCP_GAMES_ADAPTER_VERSION == "mcp-games-game-definition/1"
    assert exported == to_mcp_games_v1(STARTER_SCENARIO)
    assert set(exported) == {
        "id",
        "version",
        "title",
        "description",
        "author",
        "startScene",
        "scenes",
    }
    start = exported["scenes"][exported["startScene"]]
    assert set(start) == {"id", "title", "narrative", "choices"}
    assert set(start["choices"][0]) == {"id", "text", "targetScene"}
    assert all(
        choice["targetScene"] in exported["scenes"]
        for scene in exported["scenes"].values()
        for choice in scene["choices"]
    )
    assert json.loads(json.dumps(exported)) == exported


def test_agentsurface_v01_export_is_flat_reachable_and_whitelisted():
    blueprint = to_agentsurface_v01(STARTER_SCENARIO)
    assert AGENTSURFACE_ADAPTER_VERSION == "agentsurface-blueprint/0.1"
    assert set(blueprint) == {"surface", "dataModel", "components", "intents"}
    assert set(blueprint["surface"]) == {"id", "title", "subtitle", "width"}
    assert blueprint["surface"]["width"] in {"compact", "wide"}

    components = blueprint["components"]
    by_id = {component["id"]: component for component in components}
    assert len(by_id) == len(components)
    assert len([component for component in components if "children" not in component]) > 0
    assert all(isinstance(component, dict) for component in components)
    reachable = set()
    pending = ["root"]
    while pending:
        current = pending.pop()
        assert current not in reachable
        reachable.add(current)
        pending.extend(by_id[current].get("children", []))
    assert reachable == set(by_id)

    for component in components:
        assert set(component) <= {"id", "type", "props", "children"}
        if component["type"] == "Button":
            assert component["props"]["action"]["intent"] in blueprint["intents"]
            assert all(
                key in blueprint["dataModel"]
                for key in component["props"]["action"]["payloadKeys"]
            )
        if "bind" in component["props"]:
            assert component["props"]["bind"] in blueprint["dataModel"]
        for key in ("text", "label", "title", "subtitle", "placeholder", "alt"):
            if key in component["props"]:
                assert isinstance(component["props"][key], str)
    assert json.loads(json.dumps(blueprint)) == blueprint


def test_export_keeps_markup_like_content_as_plain_json_strings():
    content = '<img src=x onerror="alert(1)"> & "quoted"'
    scenario = Scenario(
        id="plain-text",
        version="1.0.0",
        title="Plain text",
        description="",
        author="test",
        start_scene="start",
        scenes=(Scene("start", "Title", content),),
    )
    game_json = json.dumps(to_mcp_games_v1(scenario))
    surface_json = json.dumps(to_agentsurface_v01(scenario))
    assert content in to_mcp_games_v1(scenario)["scenes"]["start"]["narrative"]
    assert content in to_agentsurface_v01(scenario)["components"][2]["props"]["text"]
    assert "<img" in game_json
    assert "<img" in surface_json
    assert json.loads(game_json)["scenes"]["start"]["narrative"] == content
    assert json.loads(surface_json)["components"][2]["props"]["text"] == content

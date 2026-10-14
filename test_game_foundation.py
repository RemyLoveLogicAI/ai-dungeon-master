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
    validate_agentsurface_v01,
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


def _valid_envelope():
    return to_agentsurface_v01(STARTER_SCENARIO)


def _button(envelope):
    return next(c for c in envelope["components"] if c["type"] == "Button")


def test_validator_accepts_the_declared_contract():
    # The adapter validates its own output, so an accepted envelope is the
    # contract's definition of well-formed.
    validate_agentsurface_v01(_valid_envelope())


def test_validator_rejects_wrong_types_as_type_errors():
    with pytest.raises(TypeError):
        validate_agentsurface_v01([])

    envelope = _valid_envelope()
    envelope["surface"]["id"] = 5
    with pytest.raises(TypeError):
        validate_agentsurface_v01(envelope)


def test_validator_rejects_unknown_top_level_keys():
    envelope = _valid_envelope()
    envelope["extra"] = {}
    with pytest.raises(ValueError):
        validate_agentsurface_v01(envelope)


def test_validator_rejects_an_undeclared_button_intent():
    envelope = _valid_envelope()
    _button(envelope)["props"]["action"]["intent"] = "smuggle"
    with pytest.raises(ValueError):
        validate_agentsurface_v01(envelope)


def test_validator_rejects_a_payload_key_absent_from_the_data_model():
    envelope = _valid_envelope()
    _button(envelope)["props"]["action"]["payloadKeys"] = ["choice_id", "unbound"]
    with pytest.raises(ValueError):
        validate_agentsurface_v01(envelope)


def test_validator_rejects_a_binding_to_an_unbound_key():
    envelope = _valid_envelope()
    select = next(c for c in envelope["components"] if "bind" in c["props"])
    select["props"]["bind"] = "ghost"
    with pytest.raises(ValueError):
        validate_agentsurface_v01(envelope)


def test_validator_rejects_unreachable_and_duplicate_components():
    unreachable = _valid_envelope()
    unreachable["components"].append(
        {"id": "orphan", "type": "Text", "props": {"text": "x"}}
    )
    with pytest.raises(ValueError):
        validate_agentsurface_v01(unreachable)

    duplicate = _valid_envelope()
    duplicate["components"].append(dict(duplicate["components"][0]))
    with pytest.raises(ValueError):
        validate_agentsurface_v01(duplicate)


def test_validator_rejects_a_cycle_between_components():
    envelope = _valid_envelope()
    by_id = {component["id"]: component for component in envelope["components"]}
    by_id["scene-narrative"]["children"] = ["root"]
    with pytest.raises(ValueError):
        validate_agentsurface_v01(envelope)


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


def _minimal_scenario(**overrides):
    fields = {
        "id": "minimal",
        "version": "1.0.0",
        "title": "Minimal",
        "description": "",
        "author": "test",
        "start_scene": "start",
        "scenes": (Scene("start", "Start", ""),),
    }
    fields.update(overrides)
    return Scenario(**fields)


def test_scenario_requires_every_identity_field():
    for blank in ("id", "version", "title", "author", "start_scene"):
        with pytest.raises(ValueError, match="are required"):
            _minimal_scenario(**{blank: ""})


def test_scenario_rejects_blank_and_duplicate_scene_ids():
    with pytest.raises(ValueError, match="scene ids must be non-empty"):
        _minimal_scenario(scenes=(Scene("start", "Start", ""), Scene("", "Blank", "")))

    with pytest.raises(ValueError, match="scene ids must be unique"):
        _minimal_scenario(scenes=(Scene("start", "Start", ""), Scene("start", "Again", "")))


def test_scenario_rejects_a_start_scene_that_is_not_defined():
    with pytest.raises(ValueError, match="start_scene must identify a defined scene"):
        _minimal_scenario(start_scene="nowhere")


def test_scenario_rejects_blank_choice_ids_and_empty_choice_text():
    with pytest.raises(ValueError, match="choice ids in scene"):
        _minimal_scenario(
            scenes=(
                Scene("start", "Start", "", choices=(Choice("", "Go", "end"),)),
                Scene("end", "End", ""),
            )
        )

    with pytest.raises(ValueError, match="must have player-facing text"):
        _minimal_scenario(
            scenes=(
                Scene("start", "Start", "", choices=(Choice("go", "", "end"),)),
                Scene("end", "End", ""),
            )
        )


def test_choose_refuses_a_session_pointing_at_an_unknown_scene():
    # The game id matches, so the refusal must come from the scene lookup and
    # not from the cross-scenario guard that the other test already covers.
    session = GameSession(STARTER_SCENARIO.id, "no-such-scene")
    with pytest.raises(ValueError, match="references unknown scene"):
        choose(session, STARTER_SCENARIO, "follow_the_bell")


def test_to_agentsurface_v01_exports_a_named_non_start_scene():
    blueprint = to_agentsurface_v01(STARTER_SCENARIO, "watchers_camp")
    assert blueprint["surface"]["subtitle"] == "The Watcher's Camp"


def test_to_agentsurface_v01_refuses_an_unknown_scene():
    """A mistyped scene id must be refused, never silently the start scene."""
    with pytest.raises(ValueError, match="unknown scene"):
        to_agentsurface_v01(STARTER_SCENARIO, "no-such-scene")


def test_validator_rejects_a_non_object_surface():
    envelope = _valid_envelope()
    envelope["surface"] = ["not", "an", "object"]
    with pytest.raises(TypeError, match="surface must be an object"):
        validate_agentsurface_v01(envelope)


def test_validator_requires_the_exact_surface_keys():
    envelope = _valid_envelope()
    del envelope["surface"]["subtitle"]
    with pytest.raises(ValueError, match="surface must define exactly"):
        validate_agentsurface_v01(envelope)


def test_validator_rejects_an_unknown_surface_width():
    envelope = _valid_envelope()
    envelope["surface"]["width"] = "enormous"
    with pytest.raises(ValueError, match="is not compact or wide"):
        validate_agentsurface_v01(envelope)


def test_validator_rejects_a_non_object_data_model():
    envelope = _valid_envelope()
    envelope["dataModel"] = "choice_id"
    with pytest.raises(TypeError, match="dataModel must be an object"):
        validate_agentsurface_v01(envelope)


def test_validator_rejects_intents_that_are_not_strings():
    envelope = _valid_envelope()
    envelope["intents"] = ["choose", 7]
    with pytest.raises(ValueError, match="intents must be a list of strings"):
        validate_agentsurface_v01(envelope)


def test_validator_rejects_a_non_object_component():
    envelope = _valid_envelope()
    envelope["components"].append("nope")
    with pytest.raises(TypeError, match="every component must be an object"):
        validate_agentsurface_v01(envelope)


def test_validator_rejects_a_component_carrying_unsupported_keys():
    envelope = _valid_envelope()
    envelope["components"].append({"id": "x", "type": "Text", "onClick": "steal()"})
    with pytest.raises(ValueError, match="unsupported keys"):
        validate_agentsurface_v01(envelope)


def test_validator_rejects_a_component_without_an_id():
    envelope = _valid_envelope()
    envelope["components"].append({"type": "Text", "props": {"text": "x"}})
    with pytest.raises(ValueError, match="non-empty string id"):
        validate_agentsurface_v01(envelope)


def test_validator_rejects_a_non_string_component_type():
    envelope = _valid_envelope()
    envelope["components"].append({"id": "typed", "type": 5})
    with pytest.raises(TypeError, match="needs a string type"):
        validate_agentsurface_v01(envelope)


def test_validator_rejects_non_object_props():
    envelope = _valid_envelope()
    envelope["components"].append({"id": "props", "type": "Text", "props": "text"})
    with pytest.raises(TypeError, match="props must be an object"):
        validate_agentsurface_v01(envelope)


def test_validator_rejects_children_that_are_not_ids():
    # Checked during the per-component scan, before reachability runs.
    envelope = _valid_envelope()
    by_id = {component["id"]: component for component in envelope["components"]}
    by_id["scene-narrative"]["children"] = [42]
    with pytest.raises(ValueError, match="children must be a list of ids"):
        validate_agentsurface_v01(envelope)


def test_validator_requires_the_root_component():
    envelope = _valid_envelope()
    envelope["components"] = [
        component for component in envelope["components"] if component["id"] != "root"
    ]
    with pytest.raises(ValueError, match="must contain the"):
        validate_agentsurface_v01(envelope)


def test_validator_rejects_a_reference_to_an_undefined_child():
    envelope = _valid_envelope()
    by_id = {component["id"]: component for component in envelope["components"]}
    by_id["root"]["children"].append("ghost")
    with pytest.raises(ValueError, match="references unknown child"):
        validate_agentsurface_v01(envelope)


def test_validator_rejects_a_button_without_an_action_object():
    envelope = _valid_envelope()
    del _button(envelope)["props"]["action"]
    with pytest.raises(ValueError, match="needs a props.action object"):
        validate_agentsurface_v01(envelope)


def test_validator_rejects_a_non_string_text_prop():
    envelope = _valid_envelope()
    _button(envelope)["props"]["label"] = 5
    with pytest.raises(ValueError, match="must be a string"):
        validate_agentsurface_v01(envelope)

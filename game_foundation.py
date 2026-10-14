"""Small, dependency-free session model and versioned game-surface adapters.

The core types deliberately describe scenes and player choices without assuming
that every game is a tabletop RPG. Adapters translate that model into external
contracts; they do not make network requests or execute supplied content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MCP_GAMES_ADAPTER_VERSION = "mcp-games-game-definition/1"
AGENTSURFACE_ADAPTER_VERSION = "agentsurface-blueprint/0.1"

_AGENTSURFACE_SURFACE_KEYS = frozenset({"id", "title", "subtitle", "width"})
_AGENTSURFACE_COMPONENT_KEYS = frozenset({"id", "type", "props", "children"})
_AGENTSURFACE_TOP_LEVEL_KEYS = frozenset({"surface", "dataModel", "components", "intents"})
_AGENTSURFACE_WIDTHS = frozenset({"compact", "wide"})
_AGENTSURFACE_TEXT_PROPS = (
    "text",
    "label",
    "title",
    "subtitle",
    "placeholder",
    "alt",
    "content",
    "value",
)


@dataclass(frozen=True)
class Choice:
    """A player-facing choice that moves a session to another scene."""

    id: str
    text: str
    target_scene: str


@dataclass(frozen=True)
class Scene:
    """A narrative unit with zero or more available choices."""

    id: str
    title: str
    narrative: str
    choices: tuple[Choice, ...] = ()


@dataclass(frozen=True)
class Scenario:
    """A validated, portable game definition."""

    id: str
    version: str
    title: str
    description: str
    author: str
    start_scene: str
    scenes: tuple[Scene, ...]

    def __post_init__(self) -> None:
        if not all((self.id, self.version, self.title, self.author, self.start_scene)):
            raise ValueError("scenario id, version, title, author, and start_scene are required")
        scene_ids = [scene.id for scene in self.scenes]
        if any(not scene_id for scene_id in scene_ids):
            raise ValueError("scene ids must be non-empty")
        if len(scene_ids) != len(set(scene_ids)):
            raise ValueError("scene ids must be unique")
        scenes_by_id = {scene.id: scene for scene in self.scenes}
        if self.start_scene not in scenes_by_id:
            raise ValueError("start_scene must identify a defined scene")
        for scene in self.scenes:
            choice_ids = [choice.id for choice in scene.choices]
            if any(not choice_id for choice_id in choice_ids):
                raise ValueError(f"choice ids in scene {scene.id!r} must be non-empty")
            if len(choice_ids) != len(set(choice_ids)):
                raise ValueError(f"choice ids in scene {scene.id!r} must be unique")
            for choice in scene.choices:
                if not choice.text:
                    raise ValueError(f"choice {choice.id!r} must have player-facing text")
                if choice.target_scene not in scenes_by_id:
                    raise ValueError(
                        f"choice {choice.id!r} targets unknown scene {choice.target_scene!r}"
                    )
        reachable = set()
        pending = [self.start_scene]
        while pending:
            scene_id = pending.pop()
            if scene_id in reachable:
                continue
            reachable.add(scene_id)
            pending.extend(
                choice.target_scene for choice in scenes_by_id[scene_id].choices
            )
        unreachable = set(scene_ids) - reachable
        if unreachable:
            raise ValueError(f"unreachable scenes: {', '.join(sorted(unreachable))}")

    @property
    def scenes_by_id(self) -> dict[str, Scene]:
        """Return an index derived from the immutable scenario definition."""
        return {scene.id: scene for scene in self.scenes}


@dataclass(frozen=True)
class GameEvent:
    """A minimal, append-only record of a player choosing a scene transition."""

    sequence: int
    type: str
    scene_id: str
    choice_id: str
    target_scene: str


@dataclass(frozen=True)
class GameSession:
    """Current scene plus the ordered events needed to replay player progress."""

    game_id: str
    current_scene: str
    events: tuple[GameEvent, ...] = ()


def start_session(scenario: Scenario) -> GameSession:
    """Create an in-memory session at the scenario's declared start scene."""
    return GameSession(game_id=scenario.id, current_scene=scenario.start_scene)


def choose(session: GameSession, scenario: Scenario, choice_id: str) -> GameSession:
    """Apply one valid choice and return a new session with an appended event."""
    if session.game_id != scenario.id:
        raise ValueError("session belongs to a different scenario")
    scene = scenario.scenes_by_id.get(session.current_scene)
    if scene is None:
        raise ValueError(f"session references unknown scene {session.current_scene!r}")
    choice = next((item for item in scene.choices if item.id == choice_id), None)
    if choice is None:
        raise ValueError(f"choice {choice_id!r} is not available in scene {scene.id!r}")
    event = GameEvent(
        sequence=len(session.events) + 1,
        type="choice_selected",
        scene_id=scene.id,
        choice_id=choice.id,
        target_scene=choice.target_scene,
    )
    return GameSession(
        game_id=session.game_id,
        current_scene=choice.target_scene,
        events=(*session.events, event),
    )


def to_mcp_games_v1(scenario: Scenario) -> dict[str, Any]:
    """Export the MCP Games ``GameDefinition`` JSON shape (no transport)."""
    scenes: dict[str, dict[str, Any]] = {}
    for scene in scenario.scenes:
        scenes[scene.id] = {
            "id": scene.id,
            "title": scene.title,
            "narrative": scene.narrative,
            "choices": [
                {
                    "id": choice.id,
                    "text": choice.text,
                    "targetScene": choice.target_scene,
                }
                for choice in scene.choices
            ],
        }
    return {
        "id": scenario.id,
        "version": scenario.version,
        "title": scenario.title,
        "description": scenario.description,
        "author": scenario.author,
        "startScene": scenario.start_scene,
        "scenes": scenes,
    }


def validate_agentsurface_v01(payload: Any, root: str = "root") -> None:
    """Fail closed unless ``payload`` is a valid ``agentsurface-blueprint/0.1`` envelope.

    This is the single definition of the v0.1 contract. Both producers use it -
    the scenario adapter below and the generative-surface exporter in ``genui`` -
    so the two can never drift into private, mutually incompatible shapes.

    Raises ``TypeError`` for a value of the wrong type and ``ValueError`` for a
    well-typed but invalid value, describing the first violation found.
    """
    if not isinstance(payload, dict):
        raise TypeError("an agentsurface blueprint must be a JSON object")
    if set(payload) != _AGENTSURFACE_TOP_LEVEL_KEYS:
        raise ValueError(
            "an agentsurface blueprint must have exactly surface, dataModel, "
            f"components and intents; got {sorted(payload)}"
        )

    surface = payload["surface"]
    if not isinstance(surface, dict):
        raise TypeError("surface must be an object")
    if set(surface) != _AGENTSURFACE_SURFACE_KEYS:
        raise ValueError(
            f"surface must define exactly {sorted(_AGENTSURFACE_SURFACE_KEYS)}"
        )
    if surface["width"] not in _AGENTSURFACE_WIDTHS:
        raise ValueError(f"surface width {surface['width']!r} is not compact or wide")
    for key in ("id", "title", "subtitle"):
        if not isinstance(surface[key], str):
            raise TypeError(f"surface.{key} must be a string")

    data_model = payload["dataModel"]
    if not isinstance(data_model, dict):
        raise TypeError("dataModel must be an object")

    intents = payload["intents"]
    if not isinstance(intents, list) or not all(isinstance(item, str) for item in intents):
        raise ValueError("intents must be a list of strings")

    components = payload["components"]
    if not isinstance(components, list) or not components:
        raise ValueError("components must be a non-empty list")

    by_id: dict[str, dict[str, Any]] = {}
    for component in components:
        if not isinstance(component, dict):
            raise TypeError("every component must be an object")
        unsupported = set(component) - _AGENTSURFACE_COMPONENT_KEYS
        if unsupported:
            raise ValueError(f"component carries unsupported keys: {sorted(unsupported)}")
        component_id = component.get("id")
        if not isinstance(component_id, str) or not component_id:
            raise ValueError("every component needs a non-empty string id")
        if component_id in by_id:
            raise ValueError(f"duplicate component id {component_id!r}")
        if not isinstance(component.get("type"), str):
            raise TypeError(f"component {component_id!r} needs a string type")
        props = component.get("props", {})
        if not isinstance(props, dict):
            raise TypeError(f"component {component_id!r} props must be an object")
        children = component.get("children")
        if children is not None and (
            not isinstance(children, list)
            or not all(isinstance(child, str) for child in children)
        ):
            raise ValueError(f"component {component_id!r} children must be a list of ids")
        by_id[component_id] = component

    if root not in by_id:
        raise ValueError(f"components must contain the {root!r} root")

    reachable: set[str] = set()
    pending = [root]
    while pending:
        current = pending.pop()
        if current in reachable:
            raise ValueError(f"component {current!r} is reachable more than once")
        if current not in by_id:
            raise ValueError(f"a component references unknown child {current!r}")
        reachable.add(current)
        pending.extend(by_id[current].get("children", ()))

    unreachable = set(by_id) - reachable
    if unreachable:
        raise ValueError(f"unreachable components: {', '.join(sorted(unreachable))}")

    for component_id, component in by_id.items():
        props = component.get("props", {})
        if component["type"] == "Button":
            action = props.get("action")
            if not isinstance(action, dict):
                raise ValueError(f"button {component_id!r} needs a props.action object")
            if action.get("intent") not in intents:
                raise ValueError(
                    f"button {component_id!r} intent {action.get('intent')!r} is not declared"
                )
            payload_keys = action.get("payloadKeys", [])
            if not isinstance(payload_keys, list) or not all(
                isinstance(key, str) and key in data_model for key in payload_keys
            ):
                raise ValueError(
                    f"button {component_id!r} payloadKeys must name dataModel keys"
                )
        if "bind" in props and props["bind"] not in data_model:
            raise ValueError(
                f"component {component_id!r} binds {props['bind']!r}, absent from dataModel"
            )
        for key in _AGENTSURFACE_TEXT_PROPS:
            if key in props and not isinstance(props[key], str):
                raise ValueError(
                    f"component {component_id!r} props.{key} must be a string"
                )


def to_agentsurface_v01(scenario: Scenario, scene_id: str | None = None) -> dict[str, Any]:
    """Export a static AgentSurface v0.1 blueprint for one scene's choices.

    Defaults to the scenario's start scene. Pass ``scene_id`` to export any
    other scene of the same, already-validated scenario - an unknown id is
    refused rather than silently falling back to the start scene, so a caller
    that mistypes a scene never renders the wrong surface and believes it.

    The renderer handles these strings as text; this adapter neither emits HTML
    nor accepts executable props. Choice ids are used as Select values so the
    intent payload can be routed unambiguously by a host.
    """
    scenes_by_id = scenario.scenes_by_id
    if scene_id is None:
        scene_id = scenario.start_scene
    elif scene_id not in scenes_by_id:
        raise ValueError(f"unknown scene {scene_id!r}")
    opening = scenes_by_id[scene_id]
    choice_id = opening.choices[0].id if opening.choices else ""
    data_model = {"choice_id": choice_id}
    components: list[dict[str, Any]] = [
        {
            "id": "root",
            "type": "Stack",
            "props": {"direction": "column", "gap": "12"},
            "children": ["scene-title", "scene-narrative"],
        },
        {
            "id": "scene-title",
            "type": "Heading",
            "props": {"text": opening.title, "level": 2},
        },
        {"id": "scene-narrative", "type": "Text", "props": {"text": opening.narrative}},
    ]
    if opening.choices:
        choice_component_ids = []
        for index, choice in enumerate(opening.choices, start=1):
            component_id = f"choice-option-{index}"
            choice_component_ids.append(component_id)
            components.append(
                {
                    "id": component_id,
                    "type": "Text",
                    "props": {"text": f"{choice.id}: {choice.text}"},
                }
            )
        components.extend(
            [
                {
                    "id": "choice-help",
                    "type": "Text",
                    "props": {
                        "text": "Choose an option by its id. The host maps the submitted id to a game choice."
                    },
                },
                {
                    "id": "choice-select",
                    "type": "Select",
                    "props": {
                        "label": "Choice",
                        "options": [choice.id for choice in opening.choices],
                        "bind": "choice_id",
                    },
                },
                {
                    "id": "choose-button",
                    "type": "Button",
                    "props": {
                        "label": "Continue",
                        "action": {"intent": "choose", "payloadKeys": ["choice_id"]},
                    },
                },
            ]
        )
        components[0]["children"].extend(
            [*choice_component_ids, "choice-help", "choice-select", "choose-button"]
        )
    blueprint = {
        "surface": {
            "id": scenario.id,
            "title": scenario.title,
            "subtitle": opening.title,
            "width": "wide",
        },
        "dataModel": data_model,
        "components": components,
        "intents": ["choose"] if opening.choices else [],
    }
    validate_agentsurface_v01(blueprint)
    return blueprint


STARTER_SCENARIO = Scenario(
    id="the-bell-beneath-the-bridge",
    version="1.0.0",
    title="The Bell Beneath the Bridge",
    description=(
        "An original D20-fantasy branching scenario for exercising the game-session "
        "and export contracts."
    ),
    author="AI Dungeon Master contributors",
    start_scene="moonlit_causeway",
    scenes=(
        Scene(
            id="moonlit_causeway",
            title="The Moonlit Causeway",
            narrative=(
                "A cracked stone causeway crosses a black ravine. A bell sounds from "
                "somewhere below, and a stranded courier watches the far bank."
            ),
            choices=(
                Choice(
                    id="follow_the_bell",
                    text="Descend toward the bell and search for its source.",
                    target_scene="sunken_shrine",
                ),
                Choice(
                    id="help_the_courier",
                    text="Help the courier reach the watcher's camp.",
                    target_scene="watchers_camp",
                ),
            ),
        ),
        Scene(
            id="sunken_shrine",
            title="The Sunken Shrine",
            narrative=(
                "Under the causeway, a small shrine glows beneath the water. Its "
                "keeper asks you to relight the lantern before the tide turns."
            ),
            choices=(
                Choice(
                    id="relight_the_lantern",
                    text="Restore the lantern and let the keeper guide you out.",
                    target_scene="quiet_return",
                ),
                Choice(
                    id="take_the_silver_bell",
                    text="Take the silver bell and race the rising water.",
                    target_scene="rising_tide",
                ),
            ),
        ),
        Scene(
            id="watchers_camp",
            title="The Watcher's Camp",
            narrative=(
                "The courier leads you to a camp of bridge watchers. Their supplies "
                "are low, but they know a safe route through the ravine."
            ),
            choices=(
                Choice(
                    id="share_supplies",
                    text="Share what you can and travel with the watchers.",
                    target_scene="quiet_return",
                ),
                Choice(
                    id="take_the_ravine_path",
                    text="Take the quicker ravine path alone.",
                    target_scene="rising_tide",
                ),
            ),
        ),
        Scene(
            id="quiet_return",
            title="A Quiet Return",
            narrative=(
                "At dawn, the bell falls silent. The bridge is safe again, and the "
                "people you helped remember your name."
            ),
        ),
        Scene(
            id="rising_tide",
            title="The Rising Tide",
            narrative=(
                "Water surges through the ravine. You escape with a hard-won story, "
                "but the crossing will need rebuilding."
            ),
        ),
    ),
)

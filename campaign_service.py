"""Deterministic campaign service: the DM turn loop over an MCP Games definition.

The exported ``mcp-games-game-definition/1`` document produced by
``game_foundation.to_mcp_games_v1`` is the source of truth for campaign
*content*: the start scene, every scene's narrative, and every choice's
routing all come from that payload, never from a parallel hard-coded graph.
Campaign *state* — current scene, journal, revision — persists through
``campaign_core.CampaignStore``, which supplies atomic commits, optimistic
concurrency, and exact-once request replay.

There is no language model in this path. Every outcome below is a deterministic
function of the game definition and the player's action, so a session replays
identically and no stat or outcome is ever invented.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from campaign_core import CampaignStore
from game_foundation import STARTER_SCENARIO, to_mcp_games_v1, validate_agentsurface_v01


def default_game_definition() -> dict[str, Any]:
    """Return the canonical MCP Games export the service executes."""
    return to_mcp_games_v1(STARTER_SCENARIO)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


class CampaignService:
    """Execute one MCP Games definition against the durable campaign store."""

    def __init__(self, store: CampaignStore, game: dict[str, Any] | None = None) -> None:
        self.store = store
        self.game = game if game is not None else default_game_definition()
        self._scenes: dict[str, Any] = self.game.get("scenes", {})
        self._start = self.game.get("startScene", "")

    # -- campaign lifecycle -------------------------------------------------

    def create(self, profile: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
        """Open a new chronicle at the game's start scene.

        ``request_id`` is accepted for contract parity with the actions
        endpoint; campaign creation is intentionally not replay-deduplicated —
        each call opens a distinct chronicle.
        """
        del request_id  # see docstring
        state = {
            "title": self.game.get("title", "Untitled campaign"),
            "phase": "adventure",
            "stage": "adventure",
            "game": {"id": self.game.get("id"), "version": self.game.get("version")},
            "scene": self._start,
            "journal": [],
            "character": None,
            "media": {},
            "presentation": self._presentation(self._start),
        }
        return self.store.create(state)

    def get(self, campaign_id: str) -> dict[str, Any]:
        return self.store.get(campaign_id)

    def reset(self, campaign_id: str) -> dict[str, Any]:
        """Return a campaign to its start scene, keeping the same campaign id."""
        current = self.store.get(campaign_id)
        base = {key: value for key, value in current.items() if key not in ("id", "revision")}
        base.update(
            {
                "scene": self._start,
                "journal": [],
                "presentation": self._presentation(self._start),
                "stage": "adventure",
                "phase": "adventure",
            }
        )
        return self.store.commit(
            campaign_id, current["revision"], f"reset-{uuid.uuid4().hex}", "reset", base
        )

    # -- the DM turn ---------------------------------------------------------

    def act(
        self,
        campaign_id: str,
        expected_revision: int,
        request_id: str,
        action: str,
        intent: str = "act",
    ) -> dict[str, Any]:
        """Apply one player action and commit the next campaign state.

        ``action`` is the player's text (a choice id, choice text, or freeform
        input). ``intent`` distinguishes UI intents; today only ``act`` and
        ``confirm_character`` exist, and both resolve deterministically here.
        """
        current = self.store.get(campaign_id)
        scene_id = current.get("scene", self._start)
        scene = self._scenes.get(scene_id, {})
        choices = scene.get("choices", [])

        new_scene = scene_id
        outcome: str
        if intent == "confirm_character":
            outcome = "The hero is ready; the adventure continues."
        else:
            match = self._match_choice(choices, action)
            if match is not None:
                new_scene = match["targetScene"]
                outcome = f"Choice made: {match['text']}"
            elif choices:
                outcome = (
                    "The Dungeon Master hears you, but the scene is unchanged. "
                    "The paths forward remain: " + "; ".join(choice["text"] for choice in choices)
                )
            else:
                outcome = "This chapter has reached its end; your chronicle is complete."

        journal = [
            *(current.get("journal") or []),
            {"action": action or intent, "outcome": outcome},
        ]
        new_state = {key: value for key, value in current.items() if key not in ("id", "revision")}
        new_state.update(
            {
                "scene": new_scene,
                "journal": journal,
                "presentation": self._presentation(new_scene),
                "stage": "adventure",
                "phase": "adventure",
            }
        )
        return self.store.commit(
            campaign_id, expected_revision, request_id, action or intent, new_state
        )

    # -- internals ------------------------------------------------------------

    @staticmethod
    def _match_choice(choices: list[dict[str, Any]], action: str) -> dict[str, Any] | None:
        """Resolve freeform text to a scene choice: exact id, exact text, or containment."""
        text = _norm(action)
        if not text:
            return None
        for choice in choices:
            if _norm(choice.get("id", "")) == text:
                return choice
        for choice in choices:
            if _norm(choice.get("text", "")) == text:
                return choice
        for choice in choices:
            choice_text = _norm(choice.get("text", ""))
            if len(choice_text) >= 4 and (choice_text in text or text in choice_text):
                return choice
        return None

    def _presentation(self, scene_id: str) -> dict[str, Any]:
        scene = self._scenes.get(scene_id, {})
        return {
            "title": scene.get("title", scene_id),
            "narration": scene.get("narrative", ""),
            "surface": self._blueprint(scene_id),
            "status": "ready",
        }

    def _blueprint(self, scene_id: str) -> dict[str, Any]:
        """AgentSurface v0.1 blueprint for one scene, intents limited to ``act``.

        Built in the same component vocabulary as
        ``game_foundation.to_agentsurface_v01`` but with the button intent the
        web client accepts (``act``), and validated by the same local contract
        checker before it ever leaves the service.
        """
        scene = self._scenes.get(scene_id, {})
        choices = scene.get("choices", [])
        children = ["scene-title", "scene-narrative"]
        components: list[dict[str, Any]] = [
            {
                "id": "root",
                "type": "Stack",
                "props": {"direction": "column", "gap": "12"},
                "children": children,
            },
            {
                "id": "scene-title",
                "type": "Heading",
                "props": {"text": scene.get("title", scene_id), "level": 2},
            },
            {
                "id": "scene-narrative",
                "type": "Text",
                "props": {"text": scene.get("narrative", "")},
            },
        ]
        for index, choice in enumerate(choices, start=1):
            component_id = f"choice-{index}"
            children.append(component_id)
            components.append(
                {
                    "id": component_id,
                    "type": "Button",
                    "props": {
                        "label": choice.get("text", choice.get("id", "Continue")),
                        "action": {"intent": "act", "payloadKeys": []},
                    },
                }
            )
        if not choices:
            children.append("scene-end")
            components.append(
                {
                    "id": "scene-end",
                    "type": "Text",
                    "props": {"text": "The tale rests here. Your chronicle is complete."},
                }
            )
        blueprint = {
            "surface": {
                "id": self.game.get("id", "campaign"),
                "title": scene.get("title", scene_id),
                "subtitle": "",
                "width": "wide",
            },
            "dataModel": {},
            "components": components,
            "intents": ["act"] if choices else [],
        }
        validate_agentsurface_v01(blueprint)
        return blueprint

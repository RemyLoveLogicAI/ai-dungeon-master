"""Tests for the deterministic campaign service over the MCP Games definition."""

from __future__ import annotations

import os
import tempfile
import unittest

from campaign_core import CampaignStore
from campaign_service import CampaignService, default_game_definition
from game_foundation import STARTER_SCENARIO


def _service(tmpdir: str) -> CampaignService:
    return CampaignService(CampaignStore(os.path.join(tmpdir, "campaigns.db")))


class TestGameDefinitionIsTheSourceOfTruth(unittest.TestCase):
    def test_default_definition_is_the_mcp_games_export(self):
        from game_foundation import MCP_GAMES_ADAPTER_VERSION

        game = default_game_definition()
        self.assertEqual(MCP_GAMES_ADAPTER_VERSION, "mcp-games-game-definition/1")
        self.assertEqual(game["id"], STARTER_SCENARIO.id)
        self.assertEqual(game["startScene"], STARTER_SCENARIO.start_scene)
        self.assertIn("scenes", game)

    def test_create_starts_at_the_definitions_start_scene(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = _service(tmp)
            state = service.create({"edition": "2024"}, "req-1")
            self.assertEqual(state["scene"], service.game["startScene"])
            self.assertEqual(state["stage"], "adventure")
            self.assertEqual(state["journal"], [])
            self.assertEqual(state["game"]["id"], service.game["id"])

    def test_presentation_carries_a_valid_agentsurface_blueprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = _service(tmp)
            state = service.create({}, None)
            surface = state["presentation"]["surface"]
            self.assertEqual(surface["intents"], ["act"])
            button_intents = {
                c["props"]["action"]["intent"]
                for c in surface["components"]
                if c["type"] == "Button"
            }
            self.assertEqual(button_intents, {"act"})


class TestActAdvancesThroughTheDefinition(unittest.TestCase):
    def test_choice_id_advances_to_target_scene(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = _service(tmp)
            state = service.create({}, None)
            scene = service._scenes[state["scene"]]
            choice = scene["choices"][0]
            next_state = service.act(state["id"], state["revision"], "req-2", choice["id"], "act")
            self.assertEqual(next_state["scene"], choice["targetScene"])
            self.assertEqual(next_state["revision"], state["revision"] + 1)
            self.assertEqual(len(next_state["journal"]), 1)
            self.assertIn(choice["text"], next_state["journal"][0]["outcome"])

    def test_choice_text_also_advances(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = _service(tmp)
            state = service.create({}, None)
            scene = service._scenes[state["scene"]]
            choice = scene["choices"][1]
            next_state = service.act(state["id"], state["revision"], "req-3", choice["text"], "act")
            self.assertEqual(next_state["scene"], choice["targetScene"])

    def test_unmatched_action_keeps_scene_and_reports_choices(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = _service(tmp)
            state = service.create({}, None)
            next_state = service.act(
                state["id"], state["revision"], "req-4", "I dance a jig", "act"
            )
            self.assertEqual(next_state["scene"], state["scene"])
            outcome = next_state["journal"][0]["outcome"]
            self.assertIn("scene is unchanged", outcome)

    def test_terminal_scene_reports_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = _service(tmp)
            state = service.create({}, None)
            # Walk to a terminal scene by following first choices.
            for index in range(10):
                scene = service._scenes[state["scene"]]
                if not scene.get("choices"):
                    break
                state = service.act(
                    state["id"],
                    state["revision"],
                    f"req-walk-{index}",
                    scene["choices"][0]["id"],
                    "act",
                )
            scene = service._scenes[state["scene"]]
            self.assertFalse(scene.get("choices"))
            final = service.act(state["id"], state["revision"], "req-end", " linger ", "act")
            self.assertIn("reached its end", final["journal"][-1]["outcome"])
            self.assertEqual(final["presentation"]["surface"]["intents"], [])

    def test_confirm_character_intent_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = _service(tmp)
            state = service.create({}, None)
            next_state = service.act(
                state["id"], state["revision"], "req-5", "", "confirm_character"
            )
            self.assertEqual(next_state["scene"], state["scene"])
            self.assertEqual(next_state["journal"][-1]["action"], "confirm_character")


class TestPersistenceAndIdempotency(unittest.TestCase):
    def test_state_survives_a_new_service_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "campaigns.db")
            service = CampaignService(CampaignStore(path))
            state = service.create({}, None)
            service.act(state["id"], state["revision"], "req-6", "follow_the_bell", "act")
            reloaded = CampaignService(CampaignStore(path)).get(state["id"])
            self.assertEqual(reloaded["scene"], "sunken_shrine")
            self.assertEqual(len(reloaded["journal"]), 1)

    def test_same_request_id_replays_without_advancing(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = _service(tmp)
            state = service.create({}, None)
            first = service.act(state["id"], state["revision"], "req-dup", "follow_the_bell", "act")
            replay = service.act(
                state["id"], first["revision"], "req-dup", "follow_the_bell", "act"
            )
            self.assertEqual(replay["scene"], first["scene"])
            self.assertEqual(len(replay["journal"]), 1)

    def test_stale_revision_is_rejected(self):
        from campaign_core import ConflictError

        with tempfile.TemporaryDirectory() as tmp:
            service = _service(tmp)
            state = service.create({}, None)
            service.act(state["id"], state["revision"], "req-7", "follow_the_bell", "act")
            with self.assertRaises(ConflictError):
                service.act(state["id"], state["revision"], "req-8", "x", "act")

    def test_reset_returns_to_start_scene(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = _service(tmp)
            state = service.create({}, None)
            advanced = service.act(
                state["id"], state["revision"], "req-9", "follow_the_bell", "act"
            )
            reset = service.reset(advanced["id"])
            self.assertEqual(reset["scene"], service.game["startScene"])
            self.assertEqual(reset["journal"], [])
            self.assertGreater(reset["revision"], advanced["revision"])

    def test_unknown_campaign_raises_not_found(self):
        import uuid

        from campaign_core import NotFoundError

        with tempfile.TemporaryDirectory() as tmp:
            service = _service(tmp)
            with self.assertRaises(NotFoundError):
                service.get(str(uuid.uuid4()))


if __name__ == "__main__":
    unittest.main()

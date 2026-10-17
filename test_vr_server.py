"""Unit tests for the production VR server and campaign state bridge."""

from __future__ import annotations

import json
import unittest

from game_foundation import AGENTSURFACE_ADAPTER_VERSION, validate_agentsurface_v01
from vr_server import CampaignVRState


class TestCampaignVRState(unittest.TestCase):
    def setUp(self) -> None:
        self.state = CampaignVRState()

    def test_initial_surface_is_valid_onboarding_blueprint(self) -> None:
        blueprint = self.state.get_active_blueprint()
        validate_agentsurface_v01(blueprint, root="root")
        self.assertEqual(blueprint["surface"]["id"], "onboarding-stage-1-2")
        self.assertFalse(self.state.hero["confirmed"])

    def test_switch_archetype_updates_stats_and_journal(self) -> None:
        res = self.state.handle_intent("SWITCH_STARTER_ARCHETYPE", {})
        self.assertEqual(res["status"], "ok")
        self.assertEqual(self.state.hero["archetype"], "Wizard")
        self.assertEqual(self.state.hero["hp"], 8)
        self.assertEqual(self.state.hero["ac"], 12)

        # Switch back
        res2 = self.state.handle_intent("SWITCH_STARTER_ARCHETYPE", {})
        self.assertEqual(self.state.hero["archetype"], "Fighter")
        self.assertEqual(self.state.hero["hp"], 12)

    def test_confirm_draft_transitions_to_story_surface(self) -> None:
        res = self.state.handle_intent(
            "CONFIRM_CHARACTER_DRAFT",
            {"characterName": "Theron", "archetype": "Fighter"},
        )
        self.assertEqual(res["status"], "ok")
        self.assertTrue(self.state.hero["confirmed"])
        self.assertEqual(self.state.hero["name"], "Theron")
        self.assertEqual(self.state.active_surface_type, "story")

        story_blueprint = self.state.get_active_blueprint()
        validate_agentsurface_v01(story_blueprint, root="root")

    def test_physical_dice_roll_handled_authoritatively(self) -> None:
        res = self.state.handle_intent("PHYSICAL_DICE_ROLL", {"roll": 20})
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["roll"], 20)
        self.assertTrue(res["isCritical"])

    def test_investigation_and_puzzle_intents(self) -> None:
        self.state.active_surface_type = "investigation"
        blueprint = self.state.get_active_blueprint()
        validate_agentsurface_v01(blueprint, root="root")
        res = self.state.handle_intent(
            "ALIGN_CELESTIAL_DIAL", {"ring": "Outer Ring", "target": "Dragon"}
        )
        self.assertEqual(res["status"], "ok")


if __name__ == "__main__":
    unittest.main()

"""Unit tests for the Multimodal Turn Orchestrator."""

from __future__ import annotations

import unittest

from game_foundation import validate_agentsurface_v01
from turn_orchestrator import TurnOrchestrator


class TestTurnOrchestrator(unittest.TestCase):
    def setUp(self) -> None:
        self.orchestrator = TurnOrchestrator(dice_seed=123)
        self.hero = {
            "name": "Kaelen Ironheart",
            "archetype": "Fighter",
            "level": 1,
            "INT": 14,
            "STR": 16,
        }

    def test_investigate_apparatus_turn(self) -> None:
        result = self.orchestrator.execute_turn(self.hero, "INVESTIGATE_APPARATUS")
        self.assertEqual(result.turn_number, 1)
        self.assertEqual(result.intent, "INVESTIGATE_APPARATUS")
        self.assertIn("Arcana", result.mechanic_resolution["skill"])
        self.assertTrue(len(result.narration) > 20)
        self.assertTrue(len(result.visual.prompt) > 20)
        self.assertIn(result.audio.cue_type, {"crit_fanfare", "dice_roll", "ambient_drone"})
        validate_agentsurface_v01(result.surface, root="root")

    def test_align_celestial_dial_turn(self) -> None:
        result = self.orchestrator.execute_turn(self.hero, "ALIGN_CELESTIAL_DIAL")
        self.assertEqual(result.turn_number, 1)
        self.assertTrue(self.orchestrator.campaign_flags["dragon_dial_aligned"])
        self.assertEqual(result.audio.cue_type, "crit_fanfare")
        self.assertIn("Silver Dragon", result.narration)
        validate_agentsurface_v01(result.surface, root="root")

    def test_channel_arcana_projects_dungeon_map(self) -> None:
        result = self.orchestrator.execute_turn(self.hero, "CHANNEL_ARCANA")
        self.assertTrue(self.orchestrator.campaign_flags["dungeon_map_projected"])
        self.assertIn("luminous map", result.narration)
        self.assertEqual(result.audio.cue_type, "fireball_impact")
        validate_agentsurface_v01(result.surface, root="root")


if __name__ == "__main__":
    unittest.main()

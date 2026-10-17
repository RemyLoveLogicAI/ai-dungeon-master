import os
import tempfile
import unittest
import wave
from unittest import mock

import audio_synth
from audio_synth import default_audio_dir, generate_all_sfx
from d20_rules import AdvantageMode, roll_d20
from encounter_ai import AIStance, CombatActionType, EncounterEnemy
from engine.story_engine import StoryEngine
from engine.world_generator import generate_procedural_world


class TestDungeonMaster(unittest.TestCase):
    def test_advantage_rolls_two_and_takes_max(self):
        # Statistical verification across 100 advantage rolls
        for _ in range(100):
            res = roll_d20(mode=AdvantageMode.ADVANTAGE)
            self.assertEqual(res.d20_roll, max(res.first_die, res.second_die))

    def test_disadvantage_rolls_two_and_takes_min(self):
        for _ in range(100):
            res = roll_d20(mode=AdvantageMode.DISADVANTAGE)
            self.assertEqual(res.d20_roll, min(res.first_die, res.second_die))

    def test_enemy_stance_transitions(self):
        enemy = EncounterEnemy(max_hp=100)
        self.assertEqual(enemy.stance, AIStance.TACTICAL)  # Starts tactical with spells

        enemy.spell_slots = 0
        enemy.update_stance()
        self.assertEqual(enemy.stance, AIStance.AGGRESSIVE)

        enemy.apply_damage(60)  # 40% HP left
        self.assertEqual(enemy.stance, AIStance.DEFENSIVE)

        enemy.apply_damage(25)  # 15% HP left
        self.assertEqual(enemy.stance, AIStance.FLEEING)

        dec = enemy.decide_turn_action(5.0)
        self.assertEqual(dec.action, CombatActionType.FLEE)

    def test_default_audio_dir_is_outside_the_package(self):
        """Regression: the console script used to write WAVs into site-packages.

        Defaulting to os.path.dirname(__file__) put the audio directory inside the
        installed package, so a read-only install (system Python, Nix, container)
        failed with PermissionError on the first run.
        """
        package_dir = os.path.dirname(os.path.abspath(audio_synth.__file__))
        audio_dir = os.path.abspath(default_audio_dir())
        self.assertFalse(
            audio_dir.startswith(package_dir),
            f"SFX must not be written into the package dir ({audio_dir})",
        )

    def test_default_audio_dir_honours_the_env_override(self):
        with mock.patch.dict(os.environ, {"AI_DM_AUDIO_DIR": "/tmp/ai-dm-sfx"}):
            self.assertEqual(default_audio_dir(), "/tmp/ai-dm-sfx")

    def test_sfx_generation_produces_valid_wav_files(self):
        with tempfile.TemporaryDirectory() as test_dir:
            paths = generate_all_sfx(test_dir)
            self.assertEqual(
                set(paths),
                {
                    "dice_roll",
                    "sword_clash",
                    "fireball_impact",
                    "crit_fanfare",
                    "ambient_drone",
                    "cavern_ambience",
                    "tension_pulse",
                },
            )
            for name, p in paths.items():
                self.assertTrue(os.path.exists(p), f"Missing {name}")
                self.assertGreater(os.path.getsize(p), 1000, f"Empty audio {name}")
                with wave.open(p, "rb") as wav_file:
                    self.assertEqual(wav_file.getnchannels(), 1)
                    self.assertEqual(wav_file.getsampwidth(), 2)
                    self.assertEqual(wav_file.getframerate(), 44100)
                    self.assertGreater(wav_file.getnframes(), 0)


    def test_world_generation(self):
        world = generate_procedural_world(seed=42)
        self.assertTrue(len(world.name) > 0)
        self.assertGreaterEqual(len(world.locations), 5)
        self.assertGreaterEqual(len(world.factions), 3)
        self.assertTrue(any(loc.id == world.current_location_id for loc in world.locations))

    def test_story_engine_generates_ui_package(self):
        engine = StoryEngine()
        ui = engine.process_turn("explore the ruins")
        self.assertIsNotNone(ui.narrative_text)
        self.assertGreaterEqual(len(ui.action_deck), 2)
        self.assertIsNotNone(ui.soundtrack)

    def test_story_engine_combat_flow(self):
        engine = StoryEngine()
        combat_ui = engine.process_turn("attack with sunforged blade")
        self.assertIsNotNone(combat_ui.tactical_grid)
        self.assertGreaterEqual(len(combat_ui.tactical_grid.combatants), 2)
        self.assertEqual(combat_ui.suggested_ui_layout, "COMBAT")

    def test_story_engine_routes_dialogue_and_travel(self):
        engine = StoryEngine()
        dialogue = engine.process_turn("talk to the archivist")
        self.assertEqual(dialogue.suggested_ui_layout, "DIALOGUE")
        self.assertIsNotNone(dialogue.npc_interaction)
        travel = engine.process_turn("travel toward the roost")
        self.assertEqual(travel.suggested_ui_layout, "ATLAS")
        self.assertTrue(travel.narrative_text)

    def test_story_engine_combat_can_end_in_victory(self):
        engine = StoryEngine()
        engine.process_turn("attack")
        engine.active_combat_enemy.current_hp = 1
        victory = engine.process_turn("flank and strike")
        self.assertEqual(victory.suggested_ui_layout, "LOOT")
        self.assertIsNone(engine.active_combat_enemy)
        self.assertTrue(victory.loot)


if __name__ == "__main__":
    unittest.main()

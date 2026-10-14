import os
import tempfile
import unittest
import wave

from audio_synth import generate_all_sfx
from d20_rules import AdvantageMode, roll_d20
from encounter_ai import AIStance, CombatActionType, EncounterEnemy


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
        self.assertEqual(enemy.stance, AIStance.TACTICAL) # Starts tactical with spells

        enemy.spell_slots = 0
        enemy.update_stance()
        self.assertEqual(enemy.stance, AIStance.AGGRESSIVE)

        enemy.apply_damage(60) # 40% HP left
        self.assertEqual(enemy.stance, AIStance.DEFENSIVE)

        enemy.apply_damage(25) # 15% HP left
        self.assertEqual(enemy.stance, AIStance.FLEEING)
        
        dec = enemy.decide_turn_action(5.0)
        self.assertEqual(dec.action, CombatActionType.FLEE)

    def test_sfx_generation_produces_valid_wav_files(self):
        with tempfile.TemporaryDirectory() as test_dir:
            paths = generate_all_sfx(test_dir)
            self.assertEqual(set(paths), {
                "dice_roll", "sword_clash", "fireball_impact", "crit_fanfare"
            })
            for name, p in paths.items():
                self.assertTrue(os.path.exists(p), f"Missing {name}")
                self.assertGreater(os.path.getsize(p), 1000, f"Empty audio {name}")
                with wave.open(p, "rb") as wav_file:
                    self.assertEqual(wav_file.getnchannels(), 1)
                    self.assertEqual(wav_file.getsampwidth(), 2)
                    self.assertEqual(wav_file.getframerate(), 44100)
                    self.assertGreater(wav_file.getnframes(), 0)

if __name__ == "__main__":
    unittest.main()

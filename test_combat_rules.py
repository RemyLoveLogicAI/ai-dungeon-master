import contextlib
import io
import os
import random
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import combat_runner
from d20_rules import AdvantageMode, DamageType, resolve_attack, roll_dice
from encounter_ai import AIStance, CombatActionType, EncounterEnemy

RANDINT = "d20_rules.random.randint"


def attack(ac=15, modifier=5, dice=1, sides=8, dmg_mod=3, mode=AdvantageMode.NORMAL):
    return resolve_attack(
        attacker="Hero",
        target="Orc",
        attack_modifier=modifier,
        target_ac=ac,
        damage_dice_count=dice,
        damage_die_sides=sides,
        damage_modifier=dmg_mod,
        damage_type=DamageType.SLASHING,
        advantage=mode,
    )


class TestResolveAttack(unittest.TestCase):
    def test_invalid_damage_dice_rejected_before_rolling(self):
        for dice, sides in ((1, 0), (1, -1), (-1, 8)):
            with self.subTest(dice=dice, sides=sides), mock.patch(RANDINT) as rng:
                with self.assertRaises(ValueError):
                    attack(dice=dice, sides=sides)
                rng.assert_not_called()

    def test_invalid_dice_rejected_and_zero_count_allowed(self):
        for count, sides in ((1, 0), (1, -1), (-1, 8)):
            with self.subTest(count=count, sides=sides), self.assertRaises(ValueError):
                roll_dice(count, sides)
        self.assertEqual(roll_dice(0, 8), 0)

    def test_natural_1_always_misses(self):
        with mock.patch(RANDINT, side_effect=[1, 1]):
            res = attack(ac=1, modifier=100)
        self.assertFalse(res.is_hit)
        self.assertFalse(res.is_critical)
        self.assertEqual(res.damage_dealt, 0)

    def test_natural_20_always_hits_and_crits(self):
        with mock.patch(RANDINT, side_effect=[20, 20, 4, 4]):
            res = attack(ac=30, modifier=-100)
        self.assertTrue(res.is_hit)
        self.assertTrue(res.is_critical)
        self.assertEqual(res.damage_dealt, 4 + 4 + 3)

    def test_crit_doubles_damage_dice_count(self):
        with mock.patch(RANDINT, return_value=4) as normal_rng:
            # d20 of 4 + 20 modifier beats AC 10: ordinary hit
            normal = attack(ac=10, modifier=20, dice=3)
            normal_calls = normal_rng.call_count
        with mock.patch(RANDINT, return_value=20) as crit_rng:
            crit = attack(ac=10, modifier=0, dice=3, sides=20)
            crit_calls = crit_rng.call_count
        self.assertFalse(normal.is_critical)
        self.assertTrue(crit.is_critical)
        # two d20 attack dice plus the damage dice
        self.assertEqual(normal_calls, 2 + 3)
        self.assertEqual(crit_calls, 2 + 6)
        self.assertEqual(normal.damage_dealt, 3 * 4 + 3)
        self.assertEqual(crit.damage_dealt, 6 * 20 + 3)

    def test_non_crit_hits_only_when_total_meets_ac(self):
        with mock.patch(RANDINT, side_effect=[10, 10, 5]):
            hit = attack(ac=15, modifier=5)  # 10 + 5 == 15
        with mock.patch(RANDINT, side_effect=[10, 10]):
            miss = attack(ac=16, modifier=5)  # 15 < 16
        self.assertTrue(hit.is_hit)
        self.assertFalse(hit.is_critical)
        self.assertEqual(hit.damage_dealt, 5 + 3)
        self.assertFalse(miss.is_hit)
        self.assertEqual(miss.damage_dealt, 0)

    def test_advantage_uses_higher_die(self):
        with mock.patch(RANDINT, side_effect=[3, 15, 4]):
            res = attack(ac=15, modifier=0, mode=AdvantageMode.ADVANTAGE)
        self.assertEqual(res.roll.d20_roll, 15)
        self.assertTrue(res.is_hit)

    def test_disadvantage_uses_lower_die(self):
        with mock.patch(RANDINT, side_effect=[3, 15]):
            res = attack(ac=15, modifier=0, mode=AdvantageMode.DISADVANTAGE)
        self.assertEqual(res.roll.d20_roll, 3)
        self.assertFalse(res.is_hit)

    def test_damage_is_at_least_one(self):
        with mock.patch(RANDINT, side_effect=[10, 10, 1]):
            res = attack(ac=1, modifier=0, dmg_mod=-10)
        self.assertTrue(res.is_hit)
        self.assertEqual(res.damage_dealt, 1)


class TestEncounterEnemyDecisions(unittest.TestCase):
    def test_max_hp_must_be_positive(self):
        for max_hp in (0, -5):
            with (
                self.subTest(max_hp=max_hp),
                self.assertRaisesRegex(ValueError, "max_hp must be positive"),
            ):
                EncounterEnemy(max_hp=max_hp)

    def test_negative_damage_rejected_without_changing_state(self):
        enemy = EncounterEnemy(max_hp=40)
        enemy.apply_damage(10)
        stance = enemy.stance
        with self.assertRaisesRegex(ValueError, "damage must be nonnegative"):
            enemy.apply_damage(-15)
        self.assertEqual(enemy.current_hp, 30)
        self.assertEqual(enemy.stance, stance)
        enemy.apply_damage(100)
        self.assertEqual(enemy.current_hp, 0)

    def test_fleeing_never_attacks(self):
        enemy = EncounterEnemy(max_hp=100)
        enemy.apply_damage(85)
        self.assertEqual(enemy.stance, AIStance.FLEEING)
        for distance in (0.5, 2.0, 5.0, 10.0):
            self.assertEqual(
                enemy.decide_turn_action(distance).action, CombatActionType.FLEE
            )

    def test_tactical_caster_uses_spell_at_range_and_spends_slot(self):
        enemy = EncounterEnemy(max_hp=100, spell_slots=2)
        self.assertEqual(enemy.stance, AIStance.TACTICAL)
        decision = enemy.decide_turn_action(4.0)
        self.assertEqual(decision.action, CombatActionType.SPELL)
        self.assertEqual(decision.damage_type, DamageType.FIRE)
        self.assertEqual(enemy.spell_slots, 1)

    def test_tactical_caster_melees_when_close(self):
        enemy = EncounterEnemy(max_hp=100, spell_slots=2)
        decision = enemy.decide_turn_action(1.0)
        self.assertEqual(decision.action, CombatActionType.MELEE)
        self.assertEqual(enemy.spell_slots, 2)

    def test_defensive_dodges_up_close_and_throws_at_range(self):
        enemy = EncounterEnemy(max_hp=100)
        enemy.apply_damage(60)
        self.assertEqual(enemy.stance, AIStance.DEFENSIVE)
        self.assertEqual(
            enemy.decide_turn_action(1.0).action, CombatActionType.DODGE
        )
        self.assertEqual(
            enemy.decide_turn_action(5.0).action, CombatActionType.RANGED
        )


class TestCombatRunner(unittest.TestCase):
    def test_deterministic_victory_flee_and_defeat(self):
        fake_paths = {
            name: f"/nonexistent/{name}.wav"
            for name in ("dice_roll", "sword_clash", "fireball_impact", "crit_fanfare")
        }
        for outcome, damage in (
            ("VICTORY!", [35]), ("flees", [30]), ("DEFEAT!", [0, 100])
        ):
            with self.subTest(outcome=outcome):
                results = [SimpleNamespace(
                    is_hit=True, is_critical=False, damage_dealt=amount,
                    combat_message="Fixed attack result"
                ) for amount in damage]
                out = io.StringIO()
                with (
                    mock.patch("combat_runner.generate_all_sfx", return_value=fake_paths),
                    mock.patch("combat_runner.resolve_attack", side_effect=results) as resolve,
                    contextlib.redirect_stdout(out),
                ):
                    combat_runner.run_simulated_encounter()
                self.assertIn(outcome, out.getvalue())
                self.assertIn("ENCOUNTER CONCLUDED", out.getvalue())
                self.assertEqual(resolve.call_count, len(damage))
                if outcome == "DEFEAT!":
                    self.assertIn("Paladin Alden HP: 0/38", out.getvalue())
                    self.assertNotIn("VICTORY!", out.getvalue())

    def test_audio_directory_uses_cwd_or_caller_location(self):
        with tempfile.TemporaryDirectory() as caller_dir:
            for chosen, expected in (
                (None, os.path.join(caller_dir, "audio_output")),
                (os.path.join(caller_dir, "custom"), os.path.join(caller_dir, "custom")),
            ):
                with (
                    self.subTest(chosen=chosen),
                    mock.patch("combat_runner.os.getcwd", return_value=caller_dir),
                    mock.patch("combat_runner.generate_all_sfx", return_value={}) as sfx,
                    mock.patch("combat_runner.EncounterEnemy") as enemy,
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    enemy.return_value.current_hp = 0
                    combat_runner.run_simulated_encounter(audio_dir=chosen)
                    sfx.assert_called_once_with(expected)

    def test_encounter_runs_to_conclusion_without_touching_disk(self):
        fake_paths = {
            name: f"/nonexistent/{name}.wav"
            for name in ("dice_roll", "sword_clash", "fireball_impact", "crit_fanfare")
        }
        for seed in range(10):
            with self.subTest(seed=seed):
                random.seed(seed)
                out = io.StringIO()
                with mock.patch(
                    "combat_runner.generate_all_sfx", return_value=fake_paths
                ) as sfx, contextlib.redirect_stdout(out):
                    combat_runner.run_simulated_encounter()
                sfx.assert_called_once()
                self.assertIn("ENCOUNTER CONCLUDED", out.getvalue())


if __name__ == "__main__":
    unittest.main()

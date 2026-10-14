import contextlib
import io
import random
import unittest
from unittest import mock

import combat_runner
from d20_rules import (
    AdvantageMode,
    DamageType,
    RestType,
    resolve_attack,
    resolve_rest,
    roll_dice,
)
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
    def test_fleeing_never_attacks(self):
        enemy = EncounterEnemy(max_hp=100)
        enemy.apply_damage(85)
        self.assertEqual(enemy.stance, AIStance.FLEEING)
        for distance in (0.5, 2.0, 5.0, 10.0):
            self.assertEqual(
                enemy.decide_turn_action(distance).action, CombatActionType.FLEE
            )

    def test_deciding_a_spell_reports_its_cost_without_spending_it(self):
        """Regression: deciding used to be a mutation.

        ``decide_turn_action`` decremented ``spell_slots`` itself, so previewing a
        turn - or simply asking twice - spent the enemy's slots and changed the
        game. The decision now reports the cost; the caller commits it.
        """
        enemy = EncounterEnemy(max_hp=100, spell_slots=2)
        self.assertEqual(enemy.stance, AIStance.TACTICAL)

        first = enemy.decide_turn_action(4.0)
        second = enemy.decide_turn_action(4.0)

        self.assertEqual(first.action, CombatActionType.SPELL)
        self.assertEqual(first.damage_type, DamageType.FIRE)
        self.assertEqual(first.spell_slots_spent, 1)
        self.assertEqual(second.action, CombatActionType.SPELL)
        self.assertEqual(enemy.spell_slots, 2, "deciding must not spend the slot")
        self.assertEqual(enemy.stance, AIStance.TACTICAL)

    def test_committing_a_spell_decision_spends_the_slot_until_exhausted(self):
        enemy = EncounterEnemy(max_hp=100, spell_slots=2)

        enemy.commit_decision(enemy.decide_turn_action(4.0))
        self.assertEqual(enemy.spell_slots, 1)
        self.assertEqual(enemy.stance, AIStance.TACTICAL)

        enemy.commit_decision(enemy.decide_turn_action(4.0))
        self.assertEqual(enemy.spell_slots, 0)
        # Out of slots, the caster falls back to its aggressive stance.
        self.assertEqual(enemy.stance, AIStance.AGGRESSIVE)

    def test_tactical_caster_melees_when_close_and_commits_nothing(self):
        enemy = EncounterEnemy(max_hp=100, spell_slots=2)
        decision = enemy.decide_turn_action(1.0)
        self.assertEqual(decision.action, CombatActionType.MELEE)
        self.assertEqual(decision.spell_slots_spent, 0)
        enemy.commit_decision(decision)
        self.assertEqual(enemy.spell_slots, 2)

    def test_aggressive_enemy_melees_without_spending_slots(self):
        """The default stance path was never executed by the suite before."""
        enemy = EncounterEnemy(max_hp=100, spell_slots=0)
        self.assertEqual(enemy.stance, AIStance.AGGRESSIVE)

        decision = enemy.decide_turn_action(6.0)

        self.assertEqual(decision.action, CombatActionType.MELEE)
        self.assertEqual(decision.action_name, "Rending Talons")
        self.assertEqual(decision.attack_modifier, 5)
        self.assertEqual(decision.damage_type, DamageType.SLASHING)
        self.assertEqual(decision.spell_slots_spent, 0)
        enemy.commit_decision(decision)
        self.assertEqual(enemy.spell_slots, 0)
        self.assertEqual(enemy.stance, AIStance.AGGRESSIVE)

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

    def test_every_run_reports_exactly_one_terminal_outcome(self):
        """Regression: a defeated player used to exit with no outcome line.

        Before the fix, 589 of 3000 seeded runs ended with the player dead and
        printed neither VICTORY nor DEFEAT, so a loss was indistinguishable from
        any other ending. Each run must now announce exactly one outcome, and all
        three endings must stay reachable.
        """
        fake_paths = {
            name: f"/nonexistent/{name}.wav"
            for name in ("dice_roll", "sword_clash", "fireball_impact", "crit_fanfare")
        }
        outcomes = {
            "victory": "VICTORY!",
            "defeat": "DEFEAT!",
            "fled": "flees into the shadows",
        }
        seen = set()
        for seed in range(300):
            with self.subTest(seed=seed):
                random.seed(seed)
                out = io.StringIO()
                with mock.patch(
                    "combat_runner.generate_all_sfx", return_value=fake_paths
                ), contextlib.redirect_stdout(out):
                    combat_runner.run_simulated_encounter()
                text = out.getvalue()
                reported = [name for name, needle in outcomes.items() if needle in text]
                self.assertEqual(
                    len(reported), 1, f"seed {seed} reported {reported or 'no outcome'}"
                )
                seen.add(reported[0])
        self.assertEqual(seen, set(outcomes), "not every ending was reachable")


class TestResolveRestInputValidation(unittest.TestCase):
    """`resolve_rest` fails closed on impossible HP state.

    An unvalidated `max_hp` used to be accepted, so a caller passing
    `current_hp > max_hp` got a negative heal and a nonsense recovery summary
    instead of an error - the boundary reported success on impossible input.
    """

    def rest(self, **overrides):
        args = {
            "character_name": "Hero",
            "rest_type": RestType.SHORT,
            "current_hp": 5,
            "max_hp": 10,
            "hit_dice_available": 1,
            "total_hit_dice": 1,
            "hit_die_sides": 8,
            "con_modifier": 2,
            "current_spell_slots": 0,
            "max_spell_slots": 2,
        }
        args.update(overrides)
        return resolve_rest(**args)

    def test_non_positive_max_hp_is_refused(self):
        for bad in (0, -5):
            with self.subTest(max_hp=bad), self.assertRaises(ValueError) as caught:
                self.rest(max_hp=bad, current_hp=0)
            self.assertIn("max_hp", str(caught.exception))

    def test_current_hp_outside_the_pool_is_refused(self):
        for bad in (-1, 11):
            with self.subTest(current_hp=bad), self.assertRaises(ValueError):
                self.rest(current_hp=bad)

    def test_bool_is_never_accepted_where_an_integer_belongs(self):
        with self.assertRaises(TypeError):
            self.rest(max_hp=True)
        with self.assertRaises(TypeError):
            self.rest(current_hp=False)

    def test_roll_dice_counts_are_validated(self):
        with self.assertRaises(ValueError):
            roll_dice(-1, 6)
        with self.assertRaises(ValueError):
            roll_dice(1, 0)

    def test_a_legal_short_rest_still_resolves(self):
        # The guard must not reject the legitimate path it protects.
        result = self.rest(current_hp=5, max_hp=10, hit_dice_available=1)
        self.assertEqual(result.rest_type, RestType.SHORT)
        self.assertGreaterEqual(result.hp_recovered, 0)


if __name__ == "__main__":
    unittest.main()

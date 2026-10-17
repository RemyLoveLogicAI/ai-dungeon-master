import contextlib
import io
import os
import random
import tempfile
import unittest
from unittest import mock

import combat_runner
from d20_rules import (
    AbilityScore,
    ActionEconomy,
    AdvantageMode,
    Condition,
    DamageType,
    RestType,
    ScriptedDiceSource,
    SeededDiceSource,
    compute_effective_advantage,
    resolve_attack,
    resolve_rest,
    resolve_saving_throw,
    roll_dice,
)
from encounter_ai import AIStance, CombatActionType, EncounterEnemy
from encounter_generator import CreatureCandidate, Difficulty

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

    def test_invalid_damage_dice_are_rejected_before_the_attack_roll(self):
        for dice, sides, error in (
            (-1, 8, "count must be non-negative"),
            (1, 0, "sides must be positive"),
        ):
            with self.subTest(dice=dice, sides=sides), mock.patch(RANDINT) as rng:
                with self.assertRaisesRegex(ValueError, error):
                    attack(dice=dice, sides=sides)
                rng.assert_not_called()

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
        self.assertEqual(enemy.decide_turn_action(1.0).action, CombatActionType.DODGE)
        self.assertEqual(enemy.decide_turn_action(5.0).action, CombatActionType.RANGED)


class TestCombatRunner(unittest.TestCase):
    def test_audio_directory_uses_cwd_or_caller_location(self):
        with tempfile.TemporaryDirectory() as caller_dir:
            for chosen, expected in (
                (None, os.path.join(caller_dir, "audio_output")),
                (
                    os.path.join(caller_dir, "custom"),
                    os.path.join(caller_dir, "custom"),
                ),
            ):
                with (
                    self.subTest(chosen=chosen),
                    mock.patch("combat_runner.os.getcwd", return_value=caller_dir),
                    mock.patch(
                        "combat_runner.generate_all_sfx", return_value={}
                    ) as sfx,
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
                with (
                    mock.patch(
                        "combat_runner.generate_all_sfx", return_value=fake_paths
                    ) as sfx,
                    contextlib.redirect_stdout(out),
                ):
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
                with (
                    mock.patch(
                        "combat_runner.generate_all_sfx", return_value=fake_paths
                    ),
                    contextlib.redirect_stdout(out),
                ):
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


class TestResolveRestLongRest(unittest.TestCase):
    """The Long Rest branch was never executed by the suite.

    Only Short Rests were covered, so the half-hit-dice floor (integer
    division would silently give 0 for a one-die character) and the
    exhaustion rule went unverified.
    """

    def long_rest(self, **overrides):
        args = {
            "character_name": "Hero",
            "rest_type": RestType.LONG,
            "current_hp": 3,
            "max_hp": 20,
            "hit_dice_available": 0,
            "total_hit_dice": 5,
            "hit_die_sides": 8,
            "con_modifier": 0,
            "current_spell_slots": 1,
            "max_spell_slots": 4,
            "exhaustion_level": 2,
        }
        args.update(overrides)
        return resolve_rest(**args)

    def test_restores_full_hp_slots_and_half_the_hit_dice(self):
        result = self.long_rest()
        self.assertEqual(result.rest_type, RestType.LONG)
        self.assertEqual(result.hp_recovered, 17)  # 20 - 3
        self.assertEqual(result.hit_dice_recovered, 2)  # 5 // 2
        self.assertEqual(result.spell_slots_restored, 3)  # 4 - 1
        self.assertEqual(result.exhaustion_reduced, 1)
        self.assertEqual(result.hit_dice_spent, 0)

    def test_recovers_at_least_one_hit_die(self):
        result = self.long_rest(total_hit_dice=1)
        self.assertEqual(result.hit_dice_recovered, 1)

    def test_without_exhaustion_reduces_nothing(self):
        result = self.long_rest(exhaustion_level=0)
        self.assertEqual(result.exhaustion_reduced, 0)

    def test_at_full_hp_and_slots_recovers_nothing(self):
        result = self.long_rest(current_hp=20, current_spell_slots=4)
        self.assertEqual(result.hp_recovered, 0)
        self.assertEqual(result.spell_slots_restored, 0)


class TestActionEconomy(unittest.TestCase):
    """The per-turn action budget shipped with no test at all.

    Each method guards a resource, so the interesting behaviour is the second
    call: a spent resource must stay spent, and a refused move must not deduct
    movement it never used.
    """

    def test_each_resource_can_be_spent_exactly_once(self):
        for spend in ("use_action", "use_bonus_action", "use_reaction"):
            with self.subTest(resource=spend):
                economy = ActionEconomy()
                self.assertTrue(getattr(economy, spend)(), "first use must succeed")
                self.assertFalse(getattr(economy, spend)(), "second use must fail")

    def test_reset_turn_restores_every_resource(self):
        economy = ActionEconomy()
        economy.use_action()
        economy.use_bonus_action()
        economy.use_reaction()
        economy.move(30.0)
        economy.reset_turn()
        self.assertTrue(economy.has_action)
        self.assertTrue(economy.has_bonus_action)
        self.assertTrue(economy.has_reaction)
        self.assertEqual(economy.movement_remaining, economy.movement_speed)

    def test_reset_turn_only_overrides_speed_when_given_one(self):
        economy = ActionEconomy(movement_speed=30.0, movement_remaining=0.0)
        economy.reset_turn()
        self.assertEqual(economy.movement_speed, 30.0)
        self.assertEqual(economy.movement_remaining, 30.0)
        economy.reset_turn(speed=15.0)
        self.assertEqual(economy.movement_speed, 15.0)
        self.assertEqual(economy.movement_remaining, 15.0)

    def test_difficult_terrain_costs_double(self):
        economy = ActionEconomy(movement_remaining=30.0)
        self.assertTrue(economy.move(10.0, is_difficult_terrain=True))
        self.assertAlmostEqual(economy.movement_remaining, 10.0)

    def test_a_refused_move_consumes_no_movement(self):
        economy = ActionEconomy(movement_remaining=5.0)
        self.assertFalse(economy.move(10.0))
        self.assertAlmostEqual(economy.movement_remaining, 5.0)

    def test_movement_is_available_exactly_at_the_boundary(self):
        economy = ActionEconomy(movement_remaining=30.0)
        self.assertTrue(economy.move(30.0))
        self.assertAlmostEqual(economy.movement_remaining, 0.0)


class TestComputeEffectiveAdvantage(unittest.TestCase):
    """Exported rules API that had no coverage at all.

    The two rules worth pinning are the 5e cancellation rule (any advantage
    plus any disadvantage is a straight roll, they never stack) and the prone
    boundary, which flips on melee range.
    """

    def test_base_mode_survives_when_no_conditions_apply(self):
        for mode in AdvantageMode:
            with self.subTest(mode=mode):
                self.assertEqual(compute_effective_advantage(mode), mode)

    def test_advantage_and_disadvantage_cancel_to_normal(self):
        result = compute_effective_advantage(
            AdvantageMode.ADVANTAGE, attacker_conditions={Condition.BLINDED}
        )
        self.assertEqual(result, AdvantageMode.NORMAL)

    def test_attacker_conditions(self):
        for condition in (
            Condition.BLINDED,
            Condition.POISONED,
            Condition.FRIGHTENED,
            Condition.RESTRAINED,
        ):
            with self.subTest(condition=condition):
                self.assertEqual(
                    compute_effective_advantage(
                        AdvantageMode.NORMAL, attacker_conditions={condition}
                    ),
                    AdvantageMode.DISADVANTAGE,
                )
        self.assertEqual(
            compute_effective_advantage(
                AdvantageMode.NORMAL, attacker_conditions={Condition.INVISIBLE}
            ),
            AdvantageMode.ADVANTAGE,
        )

    def test_target_conditions(self):
        for condition in (
            Condition.BLINDED,
            Condition.PARALYZED,
            Condition.PETRIFIED,
            Condition.STUNNED,
            Condition.UNCONSCIOUS,
            Condition.RESTRAINED,
        ):
            with self.subTest(condition=condition):
                self.assertEqual(
                    compute_effective_advantage(
                        AdvantageMode.NORMAL, target_conditions={condition}
                    ),
                    AdvantageMode.ADVANTAGE,
                )
        self.assertEqual(
            compute_effective_advantage(
                AdvantageMode.NORMAL, target_conditions={Condition.INVISIBLE}
            ),
            AdvantageMode.DISADVANTAGE,
        )

    def test_a_prone_target_flips_on_melee_range(self):
        for distance, expected in (
            (0.0, AdvantageMode.ADVANTAGE),
            (5.0, AdvantageMode.ADVANTAGE),
            (5.1, AdvantageMode.DISADVANTAGE),
            (30.0, AdvantageMode.DISADVANTAGE),
        ):
            with self.subTest(distance_ft=distance):
                self.assertEqual(
                    compute_effective_advantage(
                        AdvantageMode.NORMAL,
                        target_conditions={Condition.PRONE},
                        distance_ft=distance,
                    ),
                    expected,
                )


class TestResolveSavingThrow(unittest.TestCase):
    """`resolve_saving_throw` is exported API that the suite never called."""

    def test_success_and_failure_are_decided_by_the_dc(self):
        # NORMAL mode consumes two d20s and keeps the first.
        success = resolve_saving_throw(
            "Hero",
            AbilityScore.DEXTERITY,
            modifier=5,
            dc=20,
            dice=ScriptedDiceSource([19, 3]),
        )
        failure = resolve_saving_throw(
            "Hero",
            AbilityScore.DEXTERITY,
            modifier=5,
            dc=20,
            dice=ScriptedDiceSource([14, 3]),
        )
        self.assertTrue(success.is_success)
        self.assertFalse(failure.is_success)
        self.assertIn("SUCCESS", success.message)
        self.assertIn("FAILURE", failure.message)

    def test_meeting_the_dc_exactly_succeeds(self):
        # 15 + 5 == 20 must pass: the comparison is ">=", not ">".
        result = resolve_saving_throw(
            "Hero",
            AbilityScore.CONSTITUTION,
            modifier=5,
            dc=20,
            dice=ScriptedDiceSource([15, 1]),
        )
        self.assertTrue(result.is_success)

    def test_result_carries_the_ability_and_the_roll_arithmetic(self):
        result = resolve_saving_throw(
            "Hero",
            AbilityScore.WISDOM,
            modifier=2,
            dc=10,
            dice=ScriptedDiceSource([16, 4]),
        )
        self.assertEqual(result.ability, AbilityScore.WISDOM)
        self.assertEqual(result.dc, 10)
        self.assertEqual(result.roll.total, 18)
        self.assertIn("Wisdom", result.message)
        self.assertIn("16+2=18", result.message)


class TestCoreGameLoopAndAdapter(unittest.TestCase):
    def setUp(self):
        self.pc = combat_runner.CombatantState(
            name="Paladin Alden",
            current_hp=38,
            max_hp=38,
            ac=16,
            attack_modifier=5,
            damage_dice_count=1,
            damage_die_sides=8,
            damage_modifier=3,
            damage_type=DamageType.SLASHING,
            abilities={
                "str": 16,
                "dex": 10,
                "con": 14,
                "int": 10,
                "wis": 12,
                "cha": 14,
                "level": 3,
            },
        )
        self.goblin_spec = {
            "name": "Goblin Ambusher",
            "hp": {"current": 7, "max": 7, "formula": "2d6"},
            "ac": 15,
            "ac_source": "leather armor, shield",
            "attack_modifier": 4,
            "damage": {"dice": 1, "sides": 6, "modifier": 2, "type": "piercing"},
            "abilities": {
                "str": {"score": 8, "mod": -1},
                "dex": {"score": 14, "mod": 2},
                "con": {"score": 10, "mod": 0},
                "int": {"score": 10, "mod": 0},
                "wis": {"score": 8, "mod": -1},
                "cha": {"score": 8, "mod": -1},
            },
            "cr": 0.25,
            "xp": 50,
            "stance": "aggressive",
            "initiative": 2,
        }

    def test_state_block_round_trip_matches_spec(self):
        goblin = combat_runner.CombatantState.from_state_block(self.goblin_spec)
        self.assertEqual(goblin.name, "Goblin Ambusher")
        self.assertEqual(goblin.current_hp, 7)
        self.assertEqual(goblin.max_hp, 7)
        self.assertEqual(goblin.ac, 15)
        self.assertEqual(goblin.ac_source, "leather armor, shield")
        self.assertEqual(goblin.attack_modifier, 4)
        self.assertEqual(goblin.damage_type, DamageType.PIERCING)
        self.assertEqual(goblin.damage_dice_count, 1)
        self.assertEqual(goblin.damage_die_sides, 6)
        self.assertEqual(goblin.damage_modifier, 2)
        self.assertEqual(goblin.cr, 0.25)
        self.assertEqual(goblin.xp, 50)
        self.assertEqual(goblin.stance, "aggressive")
        self.assertEqual(goblin.initiative, 2)

        exported = goblin.to_state_block()
        self.assertEqual(exported["name"], self.goblin_spec["name"])
        self.assertEqual(exported["hp"], self.goblin_spec["hp"])
        self.assertEqual(exported["ac"], self.goblin_spec["ac"])
        self.assertEqual(exported["ac_source"], self.goblin_spec["ac_source"])
        self.assertEqual(exported["attack_modifier"], self.goblin_spec["attack_modifier"])
        self.assertEqual(exported["damage"], self.goblin_spec["damage"])
        self.assertEqual(exported["abilities"], self.goblin_spec["abilities"])
        self.assertEqual(exported["cr"], self.goblin_spec["cr"])
        self.assertEqual(exported["xp"], self.goblin_spec["xp"])
        self.assertEqual(exported["stance"], self.goblin_spec["stance"])
        self.assertEqual(exported["initiative"], self.goblin_spec["initiative"])
        self.assertEqual(exported, self.goblin_spec)

    def test_state_block_with_integer_abilities(self):
        spec = {
            "name": "Kobold",
            "hp": {"current": 5, "max": 5, "formula": "2d6-2"},
            "ac": 12,
            "attack_modifier": 4,
            "damage": {"dice": 1, "sides": 4, "modifier": 2, "type": "dagger"},
            "abilities": {"str": 7, "dex": 15, "con": 9, "int": 8, "wis": 7, "cha": 8},
            "cr": 0.125,
            "xp": 25,
            "stance": "defensive",
        }
        kobold = combat_runner.CombatantState.from_state_block(spec)
        self.assertEqual(kobold.abilities["dex"], 15)
        self.assertEqual(kobold.initiative, 2)
        exported = kobold.to_state_block()
        self.assertEqual(exported["abilities"]["dex"], {"score": 15, "mod": 2})

    def test_state_block_missing_required_fields_validation(self):
        required_fields = (
            "name",
            "hp",
            "ac",
            "attack_modifier",
            "damage",
            "cr",
            "xp",
            "stance",
        )
        for field in required_fields:
            bad_spec = dict(self.goblin_spec)
            del bad_spec[field]
            with self.assertRaises(ValueError, msg=f"Should fail when missing {field}"):
                combat_runner.CombatantState.from_state_block(bad_spec)

        with self.assertRaises(ValueError):
            combat_runner.CombatantState.from_state_block({**self.goblin_spec, "name": "   "})
        with self.assertRaises(ValueError):
            combat_runner.CombatantState.from_state_block({**self.goblin_spec, "hp": {"max": 10}})
        with self.assertRaises(TypeError):
            combat_runner.CombatantState.from_state_block({**self.goblin_spec, "hp": [1, 2, 3]})
        with self.assertRaises(TypeError):
            combat_runner.CombatantState.from_state_block({**self.goblin_spec, "damage": "invalid"})
        with self.assertRaises(ValueError):
            combat_runner.CombatantState.from_state_block(
                {**self.goblin_spec, "damage": {"dice": 1, "sides": 6}}
            )
        with self.assertRaises(ValueError):
            combat_runner.CombatantState.from_state_block({**self.goblin_spec, "xp": -10})

    def test_combatant_validation(self):
        with self.assertRaises(ValueError):
            combat_runner.CombatantState(
                name="", current_hp=10, max_hp=10, ac=10, attack_modifier=0
            )
        with self.assertRaises(ValueError):
            combat_runner.CombatantState(
                name="Hero", current_hp=10, max_hp=0, ac=10, attack_modifier=0
            )
        with self.assertRaises(ValueError):
            combat_runner.CombatantState(
                name="Hero", current_hp=10, max_hp=10, ac=-1, attack_modifier=0
            )
        with self.assertRaises(ValueError):
            combat_runner.CombatantState(
                name="Hero",
                current_hp=10,
                max_hp=10,
                ac=10,
                attack_modifier=0,
                damage_dice_count=0,
            )
        with self.assertRaises(ValueError):
            combat_runner.CombatantState(
                name="Hero", current_hp=10, max_hp=10, ac=10, attack_modifier=0, xp=-5
            )

    def test_from_candidate_fixture(self):
        candidate = CreatureCandidate("Orc", 100, "1/2", {"biome": ["hills"]})
        combatant = combat_runner.CombatantState.from_candidate(
            candidate, allow_fixture_defaults=True
        )
        self.assertEqual(combatant.name, "Orc")
        self.assertEqual(combatant.cr, 0.5)
        self.assertEqual(combatant.xp, 100)
        self.assertGreater(combatant.max_hp, 0)
        self.assertGreater(combatant.ac, 0)

    def test_from_candidate_with_count_index(self):
        combatant = combat_runner.CombatantState.from_candidate(
            {"name": "Wolf", "xp": 50, "cr": "1/4"},
            count_index=2,
            allow_fixture_defaults=True,
        )
        self.assertEqual(combatant.name, "Wolf #2")

    def test_from_candidate_precedence_over_facets(self):
        candidate = CreatureCandidate(
            "Goblin",
            50,
            "1/4",
            {**self.goblin_spec, "name": "Overridden Name", "xp": 9999, "hp": 12, "ac": 14},
        )
        c1 = combat_runner.CombatantState.from_candidate(candidate, count_index=1)
        self.assertEqual(c1.name, "Goblin")
        self.assertEqual(c1.xp, 50)

        c2 = combat_runner.CombatantState.from_candidate(candidate, count_index=3)
        self.assertEqual(c2.name, "Goblin #3")
        self.assertEqual(c2.xp, 50)

    def test_candidate_requires_combat_facets_by_default(self):
        with self.assertRaisesRegex(ValueError, "Goblin.*hp.*ac"):
            combat_runner.CombatantState.from_candidate(CreatureCandidate("Goblin", 50, "1/4"))

    def test_candidate_does_not_guess_unsupported_source_layout(self):
        candidate = CreatureCandidate(
            "Goblin", 50, "1/4",
            {"armor_class": 15, "hit_points": {"average": 7},
             "damage": self.goblin_spec["damage"]},
        )
        with self.assertRaisesRegex(ValueError, "hp.*ac"):
            combat_runner.CombatantState.from_candidate(candidate)

    def test_candidate_requires_each_normalized_combat_field(self):
        for key in ("hp", "ac", "attack_modifier", "damage", "stance"):
            with self.subTest(key=key):
                facets = {k: v for k, v in self.goblin_spec.items() if k != key}
                with self.assertRaisesRegex(ValueError, key):
                    combat_runner.CombatantState.from_candidate(
                        CreatureCandidate("Goblin", 50, "1/4", facets)
                    )

    def test_candidate_preserves_explicit_combat_values_without_mutation(self):
        import copy

        facets = copy.deepcopy(self.goblin_spec)
        before = copy.deepcopy(facets)
        combatant = combat_runner.CombatantState.from_candidate(
            CreatureCandidate("Goblin", 50, "1/4", facets), count_index=2
        )
        expected = {**self.goblin_spec, "name": "Goblin #2"}
        self.assertEqual(combatant.to_state_block(), expected)
        self.assertEqual(facets, before)

    def test_candidate_rejects_missing_or_invalid_metadata(self):
        valid = {"name": "Goblin", "xp_per_unit": 50, "cr": "1/4",
                 "facets": self.goblin_spec}
        for key in ("name", "xp_per_unit", "cr"):
            with self.subTest(missing=key):
                bad = {k: v for k, v in valid.items() if k != key}
                with self.assertRaisesRegex(ValueError, key):
                    combat_runner.CombatantState.from_candidate(bad)
        for changes in ({"name": " "}, {"xp_per_unit": 1.5}, {"xp_per_unit": True},
                        {"cr": "invalid"}, {"cr": "nan"}, {"cr": -1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                combat_runner.CombatantState.from_candidate({**valid, **changes})

    def test_candidate_rejects_unknown_damage_type(self):
        for fixture_mode in (False, True):
            facets = {**self.goblin_spec,
                      "damage": {**self.goblin_spec["damage"], "type": "not-a-damage-type"}}
            with self.subTest(fixture_mode=fixture_mode), self.assertRaisesRegex(
                ValueError, "damage.type"
            ):
                combat_runner.CombatantState.from_candidate(
                    CreatureCandidate("Goblin", 50, "1/4", facets),
                    allow_fixture_defaults=fixture_mode,
                )

    def test_fixture_defaults_preserve_supplied_state_block(self):
        combatant = combat_runner.CombatantState.from_candidate(
            CreatureCandidate("Goblin Ambusher", 50, "1/4", self.goblin_spec),
            allow_fixture_defaults=True,
        )
        self.assertEqual(combatant.to_state_block(), self.goblin_spec)

    def test_fixture_opt_in_requires_a_boolean(self):
        candidate = CreatureCandidate("Goblin", 50, "1/4", self.goblin_spec)
        for value in (1, "false", None):
            with self.subTest(value=value), self.assertRaisesRegex(TypeError, "boolean"):
                combat_runner.CombatantState.from_candidate(
                    candidate, allow_fixture_defaults=value
                )

    def test_candidate_does_not_coerce_malformed_explicit_stats(self):
        changes = (
            {"ac": True}, {"attack_modifier": 2.5}, {"hp": 7.5},
            {"hp": {"current": 7, "max": True}},
            {"damage": {**self.goblin_spec["damage"], "dice": True}},
            {"damage": {**self.goblin_spec["damage"], "sides": 6.5}},
            {"damage": {**self.goblin_spec["damage"], "modifier": "2"}},
            {"stance": ""}, {"stance": None}, {"stance": "unknown"},
        )
        for change in changes:
            for fixture_mode in (False, True):
                with self.subTest(change=change, fixture_mode=fixture_mode), self.assertRaises(
                    (ValueError, TypeError)
                ):
                    combat_runner.CombatantState.from_candidate(
                        CreatureCandidate("Goblin", 50, "1/4",
                                          {**self.goblin_spec, **change}),
                        allow_fixture_defaults=fixture_mode,
                    )

    def test_fixture_defaults_do_not_repair_malformed_explicit_damage(self):
        with self.assertRaisesRegex(ValueError, "damage.*sides"):
            combat_runner.CombatantState.from_candidate(
                CreatureCandidate("Goblin", 50, "1/4",
                                  {**self.goblin_spec, "damage": {"dice": 1}}),
                allow_fixture_defaults=True,
            )

    def test_generated_encounter_rejects_incomplete_candidates_before_combat(self):
        hp_before = self.pc.current_hp
        with self.assertRaisesRegex(ValueError, "Goblin.*hp"):
            combat_runner.run_generated_encounter(
                [self.pc], [CreatureCandidate("Goblin", 50, "1/4")],
                Difficulty.EASY, seed=42,
            )
        self.assertEqual(self.pc.current_hp, hp_before)

    def test_generated_encounter_accepts_explicit_combat_facets(self):
        result = combat_runner.run_generated_encounter(
            [self.pc], [CreatureCandidate("Goblin", 50, "1/4", self.goblin_spec)],
            Difficulty.EASY, seed=42, dice=SeededDiceSource(42),
        )
        self.assertGreater(len(result["game_events"]), 0)
        for enemy in result["enemies"]:
            self.assertEqual(enemy["hp"]["max"], 7)
            self.assertEqual(enemy["ac"], 15)
            self.assertEqual(enemy["damage"], self.goblin_spec["damage"])

    def test_run_encounter_victory_flow(self):
        weak_enemy = combat_runner.CombatantState(
            name="Goblin",
            current_hp=1,
            max_hp=1,
            ac=5,
            attack_modifier=0,
            damage_dice_count=1,
            damage_die_sides=4,
            damage_modifier=0,
            xp=50,
        )
        res = combat_runner.run_encounter([self.pc], [weak_enemy])
        self.assertEqual(res["outcome"], "victory")
        self.assertEqual(res["xp_awarded"], 50)
        self.assertGreaterEqual(res["rounds"], 1)
        self.assertTrue(len(res["game_events"]) >= 1)
        self.assertEqual(res["game_events"][0]["schema"], "gpf/game-event.v1")
        self.assertEqual(weak_enemy.current_hp, 0)

    def test_run_encounter_mercy_rule(self):
        frail_pc = combat_runner.CombatantState(
            name="Frail Squire",
            current_hp=1,
            max_hp=1,
            ac=5,
            attack_modifier=0,
            damage_dice_count=1,
            damage_die_sides=4,
            damage_modifier=0,
        )
        boss = combat_runner.CombatantState(
            name="Dragon",
            current_hp=200,
            max_hp=200,
            ac=25,
            attack_modifier=15,
            damage_dice_count=4,
            damage_die_sides=10,
            damage_modifier=10,
            xp=5000,
        )
        res = combat_runner.run_encounter([frail_pc], [boss])
        self.assertEqual(res["outcome"], "mercy_rule")
        self.assertEqual(res["xp_awarded"], 0)
        self.assertIn("Mercy rule", res["narrative"])

    def test_run_encounter_initial_zero_hp_states(self):
        weak_enemy = combat_runner.CombatantState(
            name="Goblin", current_hp=1, max_hp=1, ac=5, attack_modifier=0, xp=50
        )
        dead_pc = combat_runner.CombatantState(
            name="Fallen Hero", current_hp=0, max_hp=10, ac=10, attack_modifier=0
        )
        res_pc_down = combat_runner.run_encounter([dead_pc], [weak_enemy])
        self.assertEqual(res_pc_down["outcome"], "mercy_rule")
        self.assertEqual(res_pc_down["rounds"], 0)
        self.assertEqual(res_pc_down["xp_awarded"], 0)
        self.assertEqual(res_pc_down["game_events"], [])

        dead_enemy = combat_runner.CombatantState(
            name="Defeated Goblin", current_hp=0, max_hp=5, ac=10, attack_modifier=0, xp=75
        )
        res_enemy_down = combat_runner.run_encounter([self.pc], [dead_enemy])
        self.assertEqual(res_enemy_down["outcome"], "victory")
        self.assertEqual(res_enemy_down["rounds"], 0)
        self.assertEqual(res_enemy_down["xp_awarded"], 75)
        self.assertEqual(res_enemy_down["game_events"], [])

    def test_initiative_and_stance_targeting(self):
        fast_enemy = combat_runner.CombatantState(
            name="Fast Rogue",
            current_hp=10,
            max_hp=10,
            ac=14,
            attack_modifier=5,
            initiative=20,
            stance="defensive",
        )
        pc1 = combat_runner.CombatantState(
            name="Tank",
            current_hp=20,
            max_hp=20,
            ac=18,
            attack_modifier=2,
            initiative=5,
        )
        pc2 = combat_runner.CombatantState(
            name="Wizard",
            current_hp=8,
            max_hp=8,
            ac=11,
            attack_modifier=6,
            initiative=5,
        )
        res = combat_runner.run_encounter([pc1, pc2], [fast_enemy], max_rounds=1)
        self.assertGreater(len(res["game_events"]), 0)
        # Fast enemy acts first due to highest initiative
        self.assertEqual(res["game_events"][0]["attacker"], "Fast Rogue")
        # Defensive enemy targets Wizard because Wizard has higher threat (attack_modifier 6 vs 2)
        self.assertEqual(res["game_events"][0]["target"], "Wizard")

        # Now test aggressive enemy targeting lowest current HP
        aggro_enemy = combat_runner.CombatantState(
            name="Berserker",
            current_hp=15,
            max_hp=15,
            ac=12,
            attack_modifier=4,
            initiative=20,
            stance="aggressive",
        )
        tank = combat_runner.CombatantState(
            name="Tank",
            current_hp=20,
            max_hp=20,
            ac=18,
            attack_modifier=2,
            initiative=5,
        )
        wizard = combat_runner.CombatantState(
            name="Wizard",
            current_hp=8,
            max_hp=8,
            ac=11,
            attack_modifier=6,
            initiative=5,
        )
        res_aggro = combat_runner.run_encounter([tank, wizard], [aggro_enemy], max_rounds=1)
        self.assertEqual(res_aggro["game_events"][0]["attacker"], "Berserker")
        self.assertEqual(res_aggro["game_events"][0]["target"], "Wizard")  # Wizard HP 8 < Tank HP 20

    def test_run_generated_encounter_e2e(self):
        candidates = [
            CreatureCandidate("Goblin", 50, "1/4"),
            CreatureCandidate("Orc", 100, "1/2"),
        ]
        res = combat_runner.run_generated_encounter(
            [self.pc],
            candidates,
            Difficulty.EASY,
            seed=42,
            allow_fixture_defaults=True,
        )
        self.assertIn("encounter", res)
        self.assertEqual(res["encounter"]["version"], "gpf/encounter.v1")
        monsters = res["encounter"]["monsters"]
        self.assertGreater(len(monsters), 0)
        self.assertEqual(len(res["enemies"]), len(monsters))
        self.assertIn(res["outcome"], {"victory", "mercy_rule", "stalemate"})
        self.assertIn("game_events", res)
        self.assertGreater(len(res["game_events"]), 0)
        self.assertTrue(all(event["type"] == "attack_resolved" for event in res["game_events"]))

    def test_helpers_cr_and_damage_type_parsing(self):
        self.assertEqual(combat_runner._parse_cr("1/4"), 0.25)
        self.assertEqual(combat_runner._parse_cr("1/8"), 0.125)
        self.assertEqual(combat_runner._parse_cr("2"), 2.0)
        self.assertEqual(combat_runner._parse_cr(3), 3.0)
        self.assertEqual(combat_runner._parse_cr("invalid"), 0.0)

        self.assertEqual(combat_runner._parse_damage_type("piercing"), DamageType.PIERCING)
        self.assertEqual(combat_runner._parse_damage_type(DamageType.FIRE), DamageType.FIRE)
        self.assertEqual(combat_runner._parse_damage_type("unknown"), DamageType.SLASHING)

    def test_empty_encounter_validation(self):
        with self.assertRaises(ValueError):
            combat_runner.run_encounter([], [self.pc])
        with self.assertRaises(ValueError):
            combat_runner.run_encounter([self.pc], [])
        with self.assertRaises(ValueError):
            combat_runner.run_encounter([self.pc], [self.pc], max_rounds=0)
        with self.assertRaises(ValueError):
            combat_runner.run_encounter([self.pc], [self.pc], max_rounds=-5)
        with self.assertRaises(ValueError):
            combat_runner.run_generated_encounter([], [CreatureCandidate("Orc", 100)])


if __name__ == "__main__":
    unittest.main()

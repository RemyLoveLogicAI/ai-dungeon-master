"""Tests for the TUI's durable log and its resume-from-saved-encounter path.

Most of these drive the real runner with scripted dice, so the encounter state
they assert on is controlled rather than sampled: the rolls below were chosen so
that two rounds produce a hit, an enemy spell, a defensive dodge, and nothing
else. The rest read a hand-built log to check exactly what state reconstruction
recovers — and what it refuses.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import combat_schema
import tui_runner
from combat_log import CombatLog, load_log, record_entry, verify_log
from d20_rules import (
    AttackRequest,
    CoverType,
    DamageType,
    ScriptedDiceSource,
)
from encounter_ai import CombatActionType, EncounterEnemy
from tui_runner import (
    DASH_PER_ROUND,
    ENEMY_AC,
    ENEMY_MAX_HP,
    ENEMY_NAME,
    ENEMY_SPELL_SLOTS,
    HERO_AC,
    HERO_ATTACK_MODIFIER,
    HERO_MAX_HP,
    HERO_NAME,
    RESUME_NOTES,
    START_DISTANCE,
    close_distance,
    cover_for,
    infer_spent_spell_slots,
    next_sequence,
    read_resumed_state,
)

# A hit for 11 (8 + 3): d20 15 + 6 against AC 14, and against AC 16 with cover.
HERO_ROLLS = (15, 3, 8)
# The enemy's Shadow Flame: d20 15 + 6 against AC 16, then 3d6 + 3 = 9 damage.
ENEMY_SPELL_ROLLS = (15, 3, 2, 2, 2)
# Two rounds: hero hit, enemy spell, hero hit. Round 2 ends in a dodge, so it
# records nothing and spends no rolls.
FIRST_RUN_ROLLS = HERO_ROLLS + ENEMY_SPELL_ROLLS + HERO_ROLLS
# The killing blow on an enemy left at 8 hit points.
KILLING_BLOW_ROLLS = HERO_ROLLS
# Two misses, a Shadow Flame for 21, then talons for 15: the hero runs out of hit
# points on the fourth entry of the log.
DEFEAT_ROLLS = (2, 3) + (15, 3, 6, 6, 6) + (2, 3) + (15, 3, 6, 6)

FIRST_RUN_ENTRIES = 3
FIRST_RUN_ENEMY_HP = ENEMY_MAX_HP - 11 - 11
FIRST_RUN_HERO_HP = HERO_MAX_HP - 9
FIRST_RUN_ROUND = 3
DEFAULT_LOG_NAME = tui_runner.DEFAULT_LOG_FILENAME


def hero_request(**overrides):
    fields = {
        "attacker": HERO_NAME,
        "target": ENEMY_NAME,
        "attack_modifier": HERO_ATTACK_MODIFIER,
        "target_ac": ENEMY_AC,
        "damage_dice_count": 1,
        "damage_die_sides": 8,
        "damage_modifier": 3,
        "damage_type": DamageType.SLASHING,
    }
    fields.update(overrides)
    return AttackRequest(**fields)


def enemy_request(**overrides):
    fields = {
        "attacker": ENEMY_NAME,
        "target": HERO_NAME,
        "attack_modifier": 5,
        "target_ac": HERO_AC,
        "damage_dice_count": 2,
        "damage_die_sides": 6,
        "damage_modifier": 3,
        "damage_type": DamageType.SLASHING,
    }
    fields.update(overrides)
    return AttackRequest(**fields)


def enemy_spell_request(**overrides):
    return enemy_request(
        damage_dice_count=3, damage_die_sides=6, damage_type=DamageType.FIRE, **overrides
    )


def log_from(pairs, dropped=0):
    """Build a log from ``(request, rolls)`` pairs, numbered from dropped + 1."""
    entries = tuple(
        record_entry(request, sequence=dropped + index, dice=ScriptedDiceSource(rolls))[0]
        for index, (request, rolls) in enumerate(pairs, start=1)
    )
    return CombatLog(entries=entries, dropped=dropped)


def run_tui(**kwargs):
    """Run the TUI hermetically and return everything it printed.

    SFX synthesis and pacing are stubbed so a run is fast and writes nothing, and
    stdout is captured so the assertions can read the durable-log report.
    """
    output = io.StringIO()
    with (
        mock.patch.object(tui_runner, "generate_all_sfx", lambda output_dir: {}),
        mock.patch.object(tui_runner.time, "sleep", lambda _seconds: None),
        contextlib.redirect_stdout(output),
    ):
        tui_runner.run_tui_encounter(**kwargs)
    return output.getvalue()


def run_main(argv):
    """Run the console entry point hermetically, returning its streams."""
    output, errors = io.StringIO(), io.StringIO()
    with (
        mock.patch.object(tui_runner, "generate_all_sfx", lambda output_dir: {}),
        mock.patch.object(tui_runner.time, "sleep", lambda _seconds: None),
        contextlib.redirect_stdout(output),
        contextlib.redirect_stderr(errors),
    ):
        result = tui_runner.main(argv)
    return result, output.getvalue(), errors.getvalue()


def tamper(path, damage_dealt=999):
    """Rewrite one stored result so the envelope no longer replays."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    payload["entries"][0]["result"]["damageDealt"] = damage_dealt
    Path(path).write_text(json.dumps(payload), encoding="utf-8")


class TestForwardRules(unittest.TestCase):
    def test_close_distance_matches_the_dash_rule(self):
        self.assertEqual(close_distance(START_DISTANCE), 3.0)
        self.assertEqual(close_distance(3.0), 1.0)
        self.assertEqual(close_distance(1.0), 1.0)
        self.assertEqual(close_distance(0.5), 0.5)
        self.assertEqual(START_DISTANCE - DASH_PER_ROUND, 3.0)

    def test_cover_turns_from_half_to_none_at_melee_range(self):
        self.assertIs(cover_for(2.5), CoverType.HALF)
        self.assertIs(cover_for(2.0), CoverType.NONE)
        self.assertIs(cover_for(1.0), CoverType.NONE)

    def test_sequence_numbers_continue_the_retained_tail(self):
        self.assertEqual(next_sequence(0, []), 1)
        self.assertEqual(next_sequence(7, [object(), object()]), 10)


class TestResumedState(unittest.TestCase):
    def test_reconstructs_hit_points_round_and_distance(self):
        log = log_from(
            [
                (hero_request(), HERO_ROLLS),           # 11 damage: enemy 30 -> 19
                (enemy_request(), (15, 3, 4, 5)),       # 12 damage: hero 35 -> 23
                (hero_request(), HERO_ROLLS),           # 11 damage: enemy 19 -> 8
            ]
        )
        state = read_resumed_state(log)
        self.assertEqual(state.round_num, FIRST_RUN_ROUND)
        self.assertEqual(state.enemy_hp, 8)
        self.assertEqual(state.hero_hp, 23)
        self.assertEqual(state.distance, 1.0)
        self.assertEqual(state.spell_slots, ENEMY_SPELL_SLOTS)

    def test_a_missed_attack_deals_no_damage(self):
        log = log_from([(hero_request(), (2, 3)), (enemy_request(), (2, 3))])
        state = read_resumed_state(log)
        self.assertEqual(state.hero_hp, HERO_MAX_HP)
        self.assertEqual(state.enemy_hp, ENEMY_MAX_HP)
        self.assertEqual(state.round_num, 2)
        self.assertEqual(state.distance, 3.0)

    def test_spell_slots_are_counted_back_from_fire_attacks(self):
        one_spell = log_from(
            [
                (hero_request(), HERO_ROLLS),
                (enemy_spell_request(), ENEMY_SPELL_ROLLS),
                (hero_request(), HERO_ROLLS),
            ]
        )
        self.assertEqual(infer_spent_spell_slots(one_spell), 1)
        self.assertEqual(read_resumed_state(one_spell).spell_slots, 1)
        self.assertEqual(read_resumed_state(one_spell).hero_hp, FIRST_RUN_HERO_HP)

        two_spells = log_from(
            [
                (hero_request(), HERO_ROLLS),
                (enemy_spell_request(), ENEMY_SPELL_ROLLS),
                (hero_request(), HERO_ROLLS),
                (enemy_spell_request(), (15, 3, 1, 1, 1)),
            ]
        )
        self.assertEqual(read_resumed_state(two_spells).spell_slots, 0)

    def test_melee_only_history_leaves_the_slots_untouched(self):
        log = log_from([(hero_request(), HERO_ROLLS), (enemy_request(), (15, 3, 1, 1))])
        self.assertEqual(read_resumed_state(log).spell_slots, ENEMY_SPELL_SLOTS)

    def test_the_feed_is_rebuilt_from_the_recorded_messages(self):
        log = log_from(
            [
                (hero_request(), HERO_ROLLS),
                (enemy_request(), (15, 3, 4, 5)),
                (hero_request(), HERO_ROLLS),
            ]
        )
        state = read_resumed_state(log)
        self.assertEqual(len(state.feed), 5)  # two dashes and three results
        self.assertEqual(state.feed[-1], log.entries[-1].result.message)
        self.assertIn("dashes forward, closing distance to 15 ft.", state.feed[0])
        self.assertEqual(state.notes, RESUME_NOTES)

    def test_the_gaps_are_reported_rather_than_hidden(self):
        self.assertTrue(RESUME_NOTES)
        for note in RESUME_NOTES:
            self.assertIsInstance(note, str)
            self.assertTrue(note.strip())

    def test_victory_is_not_resumable(self):
        log = log_from([(hero_request(damage_dice_count=4), (15, 3) + (8,) * 4)])
        self.assertEqual(log.entries[0].result.damage_dealt, 35)
        with self.assertRaises(ValueError) as caught:
            read_resumed_state(log)
        self.assertIn("victory", str(caught.exception))

    def test_defeat_is_not_resumable(self):
        log = log_from([(enemy_request(damage_dice_count=12), (15, 3) + (6,) * 12)])
        self.assertEqual(log.entries[0].result.damage_dealt, 75)
        with self.assertRaises(ValueError) as caught:
            read_resumed_state(log)
        self.assertIn("defeat", str(caught.exception))

    def test_a_foreign_log_is_refused(self):
        log = log_from(
            [
                (
                    hero_request(attacker="Paladin Alden", target=ENEMY_NAME),
                    HERO_ROLLS,
                )
            ]
        )
        with self.assertRaises(ValueError) as caught:
            read_resumed_state(log)
        message = str(caught.exception)
        self.assertIn("Paladin Alden", message)
        self.assertIn("cannot be resumed here", message)

    def test_a_trimmed_log_still_reconstructs_with_continued_sequences(self):
        log = log_from(
            [(hero_request(), HERO_ROLLS), (enemy_request(), (15, 3, 4, 5))],
            dropped=4,
        )
        state = read_resumed_state(log)
        self.assertEqual(state.round_num, 2)
        self.assertEqual(state.hero_hp, HERO_MAX_HP - 12)
        self.assertEqual(next_sequence(log.dropped, list(log.entries)), 7)


class TestSpellSlotInferenceGuard(unittest.TestCase):
    def test_only_the_spell_decision_deals_fire_damage(self):
        """The inference in `infer_spent_spell_slots` depends on this being true.

        A FIRE attack identifies a cast spell only because the encounter AI makes
        no other FIRE attack. If that ever changes, this test fails instead of a
        resume silently handing the enemy slots it already spent.
        """
        saw_a_spell = False
        for max_hp in (ENEMY_MAX_HP, 100):
            for hp in (max_hp, int(max_hp * 0.6), int(max_hp * 0.3), 0):
                for slots in (0, 1, 2):
                    for distance in (0.5, 1.0, 2.0, 3.0, 6.0):
                        enemy = EncounterEnemy(
                            name=ENEMY_NAME, max_hp=max_hp, ac=ENEMY_AC, spell_slots=slots
                        )
                        enemy.current_hp = hp
                        enemy.update_stance()
                        decision = enemy.decide_turn_action(distance)
                        if decision.action is CombatActionType.SPELL:
                            saw_a_spell = True
                            self.assertIs(decision.damage_type, DamageType.FIRE)
                        else:
                            self.assertIsNot(
                                decision.damage_type,
                                DamageType.FIRE,
                                f"{decision.action_name} would be mistaken for a spell",
                            )
        self.assertTrue(saw_a_spell, "the sweep must actually reach a spell decision")

    def test_the_inference_ignores_the_hero_fire_attacks(self):
        log = log_from(
            [
                (hero_request(damage_type=DamageType.FIRE), HERO_ROLLS),
                (enemy_request(), (15, 3, 4, 5)),
            ]
        )
        self.assertEqual(infer_spent_spell_slots(log), 0)


class TestDurableEncounter(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = str(Path(self._tmp.name) / "encounter.json")

    def test_a_saved_encounter_can_be_read_back_and_reconstructed(self):
        output = run_tui(max_rounds=2, log_path=self.path, dice=ScriptedDiceSource(FIRST_RUN_ROLLS))
        log = load_log(self.path, validate_schema=True)

        self.assertEqual(len(log), FIRST_RUN_ENTRIES)
        self.assertEqual([entry.event.sequence for entry in log.entries], [1, 2, 3])
        self.assertTrue(verify_log(log))
        self.assertIn("[Replay] 3 attack events replayed deterministically: OK", output)
        self.assertIn("verified on reload (readers): OK", output)
        self.assertIn(f"--log {self.path} --resume", output)

        state = read_resumed_state(log)
        self.assertEqual(
            (state.round_num, state.hero_hp, state.enemy_hp, state.distance, state.spell_slots),
            (FIRST_RUN_ROUND, FIRST_RUN_HERO_HP, FIRST_RUN_ENEMY_HP, 1.0, 1),
        )

    def test_resume_continues_the_saved_encounter_to_its_conclusion(self):
        run_tui(max_rounds=2, log_path=self.path, dice=ScriptedDiceSource(FIRST_RUN_ROLLS))
        before = load_log(self.path)

        output = run_tui(
            max_rounds=2,
            log_path=self.path,
            resume=True,
            dice=ScriptedDiceSource(KILLING_BLOW_ROLLS),
        )
        after = load_log(self.path, validate_schema=True)

        # The resumed hit lands on the enemy's reconstructed 8 hit points, so the
        # encounter ends on the first turn of the resumed round.
        self.assertEqual(len(before), FIRST_RUN_ENTRIES)
        self.assertEqual(len(after), FIRST_RUN_ENTRIES + 1)
        self.assertEqual(
            [entry.event.sequence for entry in after.entries],
            list(range(1, FIRST_RUN_ENTRIES + 2)),
        )
        self.assertTrue(verify_log(after))
        self.assertIn("VICTORY", output)
        self.assertIn("▶ RESUMED", output)

    def test_the_resume_summary_reports_what_it_rebuilt(self):
        run_tui(max_rounds=2, log_path=self.path, dice=ScriptedDiceSource(FIRST_RUN_ROLLS))
        output = run_tui(
            max_rounds=1, log_path=self.path, resume=True, dice=ScriptedDiceSource(KILLING_BLOW_ROLLS)
        )
        # The banner interleaves ANSI codes, so the round is asserted separately.
        self.assertIn("▶ RESUMED", output)
        self.assertIn(f"round {FIRST_RUN_ROUND} │", output)
        self.assertIn(f"{FIRST_RUN_HERO_HP}/{HERO_MAX_HP} HP", output)
        self.assertIn(f"{FIRST_RUN_ENEMY_HP}/{ENEMY_MAX_HP} HP", output)
        self.assertIn(f"distance 5 ft │ {ENEMY_NAME} slots: 1/{ENEMY_SPELL_SLOTS}", output)
        self.assertIn("rebuilt, not stored:", output)
        self.assertIn("spell slots are counted back from the recorded attacks", output)

    def test_validate_schema_checks_the_published_schema_on_resume(self):
        run_tui(
            max_rounds=2,
            log_path=self.path,
            validate_schema=True,
            dice=ScriptedDiceSource(FIRST_RUN_ROLLS),
        )
        output = run_tui(
            max_rounds=1,
            log_path=self.path,
            resume=True,
            validate_schema=True,
            dice=ScriptedDiceSource(KILLING_BLOW_ROLLS),
        )
        self.assertIn("verified on reload (schema + readers): OK", output)
        self.assertEqual(len(load_log(self.path, validate_schema=True)), FIRST_RUN_ENTRIES + 1)

    def test_a_tampered_log_is_refused(self):
        run_tui(max_rounds=2, log_path=self.path, dice=ScriptedDiceSource(FIRST_RUN_ROLLS))
        tamper(self.path)
        self.assertFalse(verify_log(load_log(self.path)))
        with self.assertRaises(ValueError) as caught:
            run_tui(max_rounds=1, log_path=self.path, resume=True, dice=ScriptedDiceSource(KILLING_BLOW_ROLLS))
        self.assertIn("does not replay", str(caught.exception))

    def test_a_concluded_encounter_cannot_be_resumed_again(self):
        run_tui(max_rounds=2, log_path=self.path, dice=ScriptedDiceSource(FIRST_RUN_ROLLS))
        run_tui(max_rounds=2, log_path=self.path, resume=True, dice=ScriptedDiceSource(KILLING_BLOW_ROLLS))
        with self.assertRaises(ValueError) as caught:
            run_tui(max_rounds=1, log_path=self.path, resume=True, dice=ScriptedDiceSource(HERO_ROLLS))
        self.assertIn("nothing left to resume", str(caught.exception))

    def test_an_existing_log_is_not_clobbered_without_resume(self):
        run_tui(max_rounds=2, log_path=self.path, dice=ScriptedDiceSource(FIRST_RUN_ROLLS))
        original = Path(self.path).read_text(encoding="utf-8")

        with self.assertRaises(ValueError) as caught:
            run_tui(max_rounds=2, log_path=self.path, dice=ScriptedDiceSource(HERO_ROLLS))
        self.assertIn("already holds a saved encounter", str(caught.exception))
        self.assertEqual(Path(self.path).read_text(encoding="utf-8"), original)

    def test_overwrite_starts_a_fresh_encounter(self):
        run_tui(max_rounds=2, log_path=self.path, dice=ScriptedDiceSource(FIRST_RUN_ROLLS))
        original = load_log(self.path).dumps()
        run_tui(
            max_rounds=2,
            log_path=self.path,
            overwrite=True,
            dice=ScriptedDiceSource(FIRST_RUN_ROLLS),
        )
        # Same scripted dice and one fixed encounter, so the replacement log is
        # identical rather than merely valid.
        self.assertEqual(load_log(self.path).dumps(), original)

    def test_resuming_a_missing_log_reports_the_path(self):
        missing = str(Path(self._tmp.name) / "nope.json")
        with self.assertRaises(FileNotFoundError):
            run_tui(max_rounds=1, log_path=missing, resume=True, dice=ScriptedDiceSource(HERO_ROLLS))

    def test_resuming_without_a_log_path_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            run_tui(max_rounds=1, resume=True, dice=ScriptedDiceSource(HERO_ROLLS))
        self.assertIn("requires a log path", str(caught.exception))

    def test_a_defeat_is_saved_with_the_history_that_led_to_it(self):
        output = run_tui(max_rounds=4, log_path=self.path, dice=ScriptedDiceSource(DEFEAT_ROLLS))

        log = load_log(self.path, validate_schema=True)
        self.assertEqual(len(log), 4)
        self.assertTrue(verify_log(log))
        self.assertIn("DEFEAT", output)
        self.assertEqual(log.entries[-1].result.target, HERO_NAME)

        # A lost encounter is history, not a session to continue.
        with self.assertRaises(ValueError) as caught:
            run_tui(max_rounds=1, log_path=self.path, resume=True, dice=ScriptedDiceSource(HERO_ROLLS))
        self.assertIn("defeat", str(caught.exception))

    def test_a_run_without_a_log_path_still_verifies_its_replay(self):
        output = run_tui(max_rounds=2, dice=ScriptedDiceSource(FIRST_RUN_ROLLS))
        self.assertIn("attack events replayed deterministically: OK", output)
        self.assertNotIn("[Log]", output)
        self.assertFalse(Path(self.path).exists())


class TestCliEntryPoint(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = str(Path(self._tmp.name) / "encounter.json")

    def test_a_fresh_run_is_saved_and_then_resumed_by_flags(self):
        # Unscripted dice, so only the shape is asserted on: two rounds record two
        # hero attacks and at most one enemy action each.
        result, _, _ = run_main(["--rounds", "2", "--log", self.path, "--seed", "5"])
        self.assertIsNone(result)
        before = len(load_log(self.path))
        self.assertTrue(2 <= before <= 4, before)

        result, output, _ = run_main(["--rounds", "2", "--log", self.path, "--resume", "--seed", "9"])
        self.assertIsNone(result)
        self.assertIn("▶ RESUMED", output)
        self.assertGreater(len(load_log(self.path)), before)

    def test_resume_alone_falls_back_to_the_saved_log_in_the_log_dir(self):
        default_path = str(Path(self._tmp.name) / DEFAULT_LOG_NAME)
        with mock.patch.dict(os.environ, {"AI_DM_LOG_DIR": self._tmp.name}):
            run_tui(max_rounds=2, log_path=default_path, dice=ScriptedDiceSource(FIRST_RUN_ROLLS))
            before = len(load_log(default_path))

            result, output, _ = run_main(["--resume"])

            after = len(load_log(default_path, validate_schema=True))
        self.assertIsNone(result)
        self.assertIn("▶ RESUMED", output)
        self.assertGreater(after, before)

    def test_seeding_the_dice_makes_a_run_reproducible(self):
        first = str(Path(self._tmp.name) / "same-seed-a.json")
        second = str(Path(self._tmp.name) / "same-seed-b.json")
        run_main(["--rounds", "3", "--seed", "17", "--log", first])
        run_main(["--rounds", "3", "--seed", "17", "--log", second])
        self.assertEqual(load_log(first).dumps(), load_log(second).dumps())

    def test_unrecognized_arguments_are_reported_and_ignored(self):
        # A host process injecting its own argv must not break the entry point.
        result, _, errors = run_main(["--rounds", "1", "test_tui_resume.py", "-q"])
        self.assertIsNone(result)
        self.assertIn("ignoring unrecognized argument(s)", errors)

    def test_requesting_schema_validation_without_a_validator_is_a_usage_error(self):
        # Not a traceback: the check was requested, and it cannot run, so the run
        # stops with the install hint rather than pretending to have verified.
        combat_schema._validator_for.cache_clear()
        combat_schema._compiled_validator.cache_clear()
        errors = io.StringIO()
        try:
            with (
                mock.patch.dict(sys.modules, {"jsonschema": None, "jsonschema.validators": None}),
                mock.patch.object(tui_runner, "generate_all_sfx", lambda output_dir: {}),
                mock.patch.object(tui_runner.time, "sleep", lambda _seconds: None),
                contextlib.redirect_stderr(errors),
                self.assertRaises(SystemExit) as caught,
            ):
                tui_runner.main(["--rounds", "1", "--log", self.path, "--validate-schema"])
        finally:
            combat_schema._validator_for.cache_clear()
            combat_schema._compiled_validator.cache_clear()
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("jsonschema", errors.getvalue())
        self.assertFalse(Path(self.path).exists())

    def test_a_usage_error_exits_with_a_message_instead_of_a_traceback(self):
        missing = str(Path(self._tmp.name) / "missing.json")
        with self.assertRaises(SystemExit) as caught:
            run_main(["--resume", "--log", missing])
        self.assertEqual(caught.exception.code, 2)

    def test_an_untrustworthy_log_is_a_usage_error_not_a_crash(self):
        run_tui(max_rounds=2, log_path=self.path, dice=ScriptedDiceSource(FIRST_RUN_ROLLS))
        tamper(self.path)
        errors = io.StringIO()
        # The refusal happens before the first render, so only stderr matters here.
        with (
            mock.patch.object(tui_runner, "generate_all_sfx", lambda output_dir: {}),
            mock.patch.object(tui_runner.time, "sleep", lambda _seconds: None),
            contextlib.redirect_stderr(errors),
            self.assertRaises(SystemExit) as caught,
        ):
            tui_runner.main(["--resume", "--log", self.path])
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("does not replay", errors.getvalue())


if __name__ == "__main__":
    unittest.main()

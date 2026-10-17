import contextlib
import io
import json
import random
import tempfile
import unittest
from dataclasses import replace
from unittest import mock

import audio_synth
import combat_runner
from combat_events import EVENT_SCHEMA_VERSION, is_replayable, record_attack, replay_attack
from d20_rules import (
    AttackRequest,
    CoverType,
    DamageType,
    ModuleRandomDiceSource,
    RecordingDiceSource,
    ScriptedDiceSource,
    SeededDiceSource,
    roll_d20,
    roll_dice,
)

RANDINT = "d20_rules.random.randint"

FAKE_PATHS = {
    name: f"/nonexistent/{name}.wav"
    for name in ("dice_roll", "sword_clash", "fireball_impact", "crit_fanfare")
}


def request(**overrides) -> AttackRequest:
    fields = {
        "attacker": "Paladin Alden",
        "target": "Shadow Gargoyle",
        "attack_modifier": 5,
        "target_ac": 14,
        "damage_dice_count": 2,
        "damage_die_sides": 6,
        "damage_modifier": 3,
        "damage_type": DamageType.SLASHING,
    }
    fields.update(overrides)
    return AttackRequest(**fields)  # type: ignore[arg-type]


class TestDiceSources(unittest.TestCase):
    def test_seeded_source_is_reproducible(self):
        source_a = SeededDiceSource(1234)
        source_b = SeededDiceSource(1234)
        first = [source_a.roll(20) for _ in range(10)]
        second = [source_b.roll(20) for _ in range(10)]
        self.assertEqual(first, second)
        self.assertTrue(all(1 <= value <= 20 for value in first))

    def test_seeded_source_does_not_disturb_global_random_state(self):
        random.seed(4321)
        expected = [random.randint(1, 20) for _ in range(5)]

        random.seed(4321)
        SeededDiceSource(99).roll(20)
        actual = [random.randint(1, 20) for _ in range(5)]

        self.assertEqual(expected, actual)

    def test_default_source_still_uses_the_shared_module_generator(self):
        """The historical default must keep working for existing callers."""
        with mock.patch(RANDINT, side_effect=[7, 3]) as patched:
            self.assertEqual(roll_d20().d20_roll, 7)
        self.assertEqual(patched.call_count, 2)

    def test_roll_helpers_accept_an_injected_source(self):
        dice = ScriptedDiceSource([5, 4])
        self.assertEqual(roll_dice(2, 6, dice=dice), 9)
        self.assertEqual(dice.remaining, 0)

    def test_roll_dice_still_validates_arguments(self):
        with self.assertRaises(ValueError):
            roll_dice(1, 0)
        with self.assertRaises(ValueError):
            roll_dice(-1, 6)

    def test_scripted_source_exhaustion_is_loud(self):
        source = ScriptedDiceSource([3])
        self.assertEqual(source.roll(20), 3)
        with self.assertRaises(RuntimeError):
            source.roll(20)

    def test_scripted_source_rejects_out_of_range_results(self):
        with self.assertRaises(ValueError):
            ScriptedDiceSource([25]).roll(20)

    def test_recording_source_captures_every_result_in_order(self):
        recorder = RecordingDiceSource(ScriptedDiceSource([1, 20, 4]))
        self.assertEqual([recorder.roll(20), recorder.roll(20), recorder.roll(6)], [1, 20, 4])
        self.assertEqual(recorder.rolls, (1, 20, 4))


class TestAttackEvents(unittest.TestCase):
    def test_attack_event_round_trips_through_replay(self):
        cases = {
            "crit": ScriptedDiceSource([20, 20, 6, 6, 6, 6]),
            "hit": ScriptedDiceSource([12, 3, 5, 5]),
            "miss": ScriptedDiceSource([2, 2]),
            "fumble": ScriptedDiceSource([1, 1]),
        }
        for name, dice in cases.items():
            with self.subTest(case=name):
                event, resolution = record_attack(request(), sequence=1, dice=dice)
                self.assertTrue(is_replayable(event, resolution))
                self.assertEqual(replay_attack(event), resolution)

    def test_recorded_rolls_match_the_resolution(self):
        """A hit on a 2d6 weapon consumes two d20 dice plus two damage dice."""
        event, resolution = record_attack(
            request(attack_modifier=0, target_ac=10), dice=ScriptedDiceSource([10, 4, 3, 3])
        )
        self.assertTrue(resolution.is_hit)
        self.assertEqual(event.rolls, (10, 4, 3, 3))
        self.assertEqual(event.type, "attack_resolved")
        self.assertEqual(event.schema, EVENT_SCHEMA_VERSION)

    def test_total_cover_records_no_rolls_and_still_replays(self):
        event, resolution = record_attack(
            request(cover=CoverType.TOTAL), dice=ScriptedDiceSource([])
        )
        self.assertEqual(event.rolls, ())
        self.assertFalse(resolution.is_hit)
        self.assertTrue(is_replayable(event, resolution))

    def test_replay_detects_a_changed_resolution(self):
        event, resolution = record_attack(request(), dice=SeededDiceSource(3))
        tampered = replace(resolution, damage_dealt=resolution.damage_dealt + 1)
        self.assertFalse(is_replayable(event, tampered))

    def test_event_is_json_compatible_and_deterministic(self):
        event, _ = record_attack(request(), dice=SeededDiceSource(5))
        payload = event.to_dict()
        self.assertEqual(payload, event.to_dict())
        self.assertEqual(json.loads(json.dumps(payload)), payload)
        self.assertEqual(payload["schema"], EVENT_SCHEMA_VERSION)
        self.assertEqual(payload["request"]["damageType"], DamageType.SLASHING.value)
        self.assertEqual(len(payload["rolls"]), len(event.rolls))

    def test_a_recorded_sequence_replays_against_the_same_source(self):
        """Two attacks recorded from one source replay from their own rolls."""
        dice = SeededDiceSource(17)
        recorded = [record_attack(request(), sequence=index, dice=dice) for index in (1, 2)]
        for event, resolution in recorded:
            with self.subTest(sequence=event.sequence):
                self.assertEqual(replay_attack(event), resolution)

    def test_module_random_source_is_usable_directly(self):
        source = ModuleRandomDiceSource()
        with mock.patch(RANDINT, return_value=6):
            self.assertEqual(source.roll(8), 6)


class TestSeededEncounter(unittest.TestCase):
    def run_encounter(self, seed: int) -> str:
        out = io.StringIO()
        with mock.patch(
            "combat_runner.generate_all_sfx", return_value=FAKE_PATHS
        ), contextlib.redirect_stdout(out):
            combat_runner.run_simulated_encounter(dice=SeededDiceSource(seed))
        return out.getvalue()

    def test_same_seed_reproduces_the_whole_encounter(self):
        self.assertEqual(self.run_encounter(7), self.run_encounter(7))

    def test_seeded_runs_ignore_global_random_state(self):
        random.seed(1)
        first = self.run_encounter(11)
        random.seed(987654)
        second = self.run_encounter(11)
        self.assertEqual(first, second)

    def test_seeded_encounter_still_concludes_with_a_replay_check(self):
        text = self.run_encounter(2)
        self.assertIn("ENCOUNTER CONCLUDED", text)
        self.assertIn("attack events replayed deterministically: OK", text)


class TestAudioIsolation(unittest.TestCase):
    """Synthesising audio must not consume the stream combat rolls on.

    Regression: ``audio_synth`` called ``random.random()`` on the same Mersenne
    Twister as combat, so generating SFX first shifted every later attack. With
    ``seed(1234)`` combat alone rolled damage 4 / d20 3, but damage 0 / d20 9 once
    the SFX generator had run.
    """

    def _run_encounter(self, *, with_audio: bool) -> str:
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "audio_synth._write_wav"
        ), mock.patch(
            "combat_runner.generate_all_sfx", return_value=FAKE_PATHS
        ), contextlib.redirect_stdout(out):
            random.seed(1234)
            if with_audio:
                audio_synth.generate_all_sfx(tmp)
            combat_runner.run_simulated_encounter()
        return out.getvalue()

    def test_generating_sfx_does_not_change_a_globally_seeded_encounter(self):
        self.assertEqual(self._run_encounter(with_audio=False), self._run_encounter(with_audio=True))

    def test_sfx_generation_leaves_the_global_random_stream_untouched(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("audio_synth._write_wav"):
            random.seed(99)
            expected = [random.random() for _ in range(5)]

            random.seed(99)
            audio_synth.generate_all_sfx(tmp)

            self.assertEqual([random.random() for _ in range(5)], expected)

    def test_audio_draws_from_its_own_private_generator(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("audio_synth._write_wav"):
            random.seed(5)
            captured = [random.random() for _ in range(3)]

            random.seed(5)
            audio_synth.synthesize_dice_roll(f"{tmp}/dice_roll.wav")

            self.assertEqual([random.random() for _ in range(3)], captured)


if __name__ == "__main__":
    unittest.main()

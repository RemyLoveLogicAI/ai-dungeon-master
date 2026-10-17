import errno
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import combat_log
from combat_events import AttackResult, require_int, require_str
from combat_log import (
    LOG_SCHEMA_VERSION,
    CombatLog,
    CombatLogEntry,
    default_log_dir,
    load_log,
    log_schema_version,
    migrate_log,
    record_entry,
    replay_log,
    save_log,
    trim_log,
    verify_log,
)
from d20_rules import AttackRequest, DamageType, ScriptedDiceSource, SeededDiceSource


def request(**overrides):
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
    return AttackRequest(**fields)


def make_log(count=3, seed=11):
    dice = SeededDiceSource(seed)
    entries = []
    for index in range(1, count + 1):
        entry, _ = record_entry(request(), sequence=index, dice=dice)
        entries.append(entry)
    return CombatLog(entries=tuple(entries))


def hit_entry(sequence=1):
    """A deterministic hit: 10+0 vs AC 10, 2d6+3 damage."""
    entry, _ = record_entry(
        request(attack_modifier=0, target_ac=10),
        sequence=sequence,
        dice=ScriptedDiceSource([10, 4, 3, 3]),
    )
    return entry


class TestRoundTrip(unittest.TestCase):
    def test_log_survives_a_full_serialization_cycle(self):
        log = make_log(4)
        restored = CombatLog.loads(log.dumps())
        self.assertEqual(restored.entries, log.entries)
        self.assertEqual(restored.dropped, 0)
        self.assertTrue(verify_log(restored))

    def test_dumps_is_deterministic_for_equal_logs(self):
        self.assertEqual(make_log(3, seed=7).dumps(), make_log(3, seed=7).dumps())

    def test_payload_is_json_compatible(self):
        payload = make_log(2).to_dict()
        self.assertEqual(payload["schema"], LOG_SCHEMA_VERSION)
        self.assertEqual(json.loads(json.dumps(payload)), payload)

    def test_replay_log_reproduces_every_stored_result(self):
        log = make_log(4)
        replayed = replay_log(log)
        self.assertEqual(
            [AttackResult.from_resolution(item) for item in replayed],
            [entry.result for entry in log.entries],
        )

    def test_entry_replays_to_its_own_result(self):
        entry = hit_entry()
        self.assertTrue(entry.replays())
        self.assertTrue(entry.result.is_hit)
        self.assertEqual(entry.result.damage_dealt, 9)

    def test_record_entry_returns_the_matching_resolution(self):
        entry, resolution = record_entry(request(), dice=SeededDiceSource(3))
        self.assertEqual(AttackResult.from_resolution(resolution), entry.result)


class TestFileBoundary(unittest.TestCase):
    def test_save_and_load_round_trip_through_a_real_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "nested", "encounter.json")
            saved = save_log(make_log(3), path)
            self.assertTrue(os.path.exists(saved))
            restored = load_log(saved)
        self.assertEqual(len(restored), 3)
        self.assertTrue(verify_log(restored))

    def test_save_follows_symlink_without_replacing_it(self):
        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / "storage" / "encounter.json"
                target.parent.mkdir()
                if existing:
                    save_log(make_log(1), target)
                link = root / "checkpoint.json"
                link.symlink_to(Path("storage") / target.name)
                updated = make_log(2)
                with mock.patch.object(combat_log.os, "replace", wraps=os.replace) as replace:
                    self.assertEqual(save_log(updated, link), str(link))
                replace.assert_called_once()
                source, destination = replace.call_args.args
                self.assertEqual(source.parent, target.parent)
                self.assertEqual(destination, target)
                self.assertTrue(link.is_symlink())
                self.assertEqual(load_log(target), updated)
                self.assertEqual(load_log(link), updated)
                self.assertEqual(list(target.parent.iterdir()), [target])

    def test_failed_symlink_save_preserves_link_and_target(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "encounter.json"
            previous = make_log(1)
            save_log(previous, target)
            link = Path(directory) / "checkpoint.json"
            link.symlink_to(target)
            with mock.patch.object(
                combat_log.os, "replace", side_effect=OSError("save failed")
            ), self.assertRaisesRegex(OSError, "save failed"):
                save_log(make_log(2), link)
            self.assertTrue(link.is_symlink())
            self.assertEqual(load_log(target), previous)
            self.assertEqual(set(Path(directory).iterdir()), {target, link})

    def test_interrupted_write_preserves_previous_checkpoint(self):
        # Inject a real partial write at the shared text-I/O boundary, not a
        # save_log implementation detail. This reproduces the old truncation.
        real_open = io.open

        class InterruptedWriter:
            def __init__(self, stream, error):
                self.stream = stream
                self.error = error

            def __getattr__(self, name):
                return getattr(self.stream, name)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return self.stream.__exit__(*args)

            def write(self, text):
                self.stream.write(text[:20])
                self.stream.flush()
                raise self.error

        for error in (OSError("disk full"), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "encounter.json"
                previous = make_log(1)
                save_log(previous, path)
                before = path.read_bytes()

                def interrupted_open(*args, error=error, **kwargs):
                    return InterruptedWriter(real_open(*args, **kwargs), error)

                with mock.patch.object(io, "open", side_effect=interrupted_open), \
                        self.assertRaises(type(error)) as caught:
                    save_log(make_log(2), path)
                self.assertIs(caught.exception, error)
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(load_log(path), previous)
                self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_pre_replace_failures_preserve_checkpoint(self):
        for stage in ("flush", "fsync", "replace"):
            for existing in (False, True):
                with self.subTest(stage=stage, existing=existing), \
                        tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "encounter.json"
                    previous = make_log(1)
                    if existing:
                        save_log(previous, path)
                    error = OSError("injected save failure")
                    if stage == "flush":
                        real_open = io.open

                        def failing_open(*args, real_open=real_open, error=error, **kwargs):
                            stream = real_open(*args, **kwargs)
                            stream.flush = mock.Mock(side_effect=error)
                            return stream

                        patch = mock.patch.object(io, "open", side_effect=failing_open)
                    else:
                        patch = mock.patch(f"combat_log.os.{stage}", side_effect=error)
                    with patch, self.assertRaises(OSError) as caught:
                        save_log(make_log(2), path)
                    self.assertIs(caught.exception, error)
                    if existing:
                        self.assertEqual(load_log(path), previous)
                    else:
                        self.assertFalse(path.exists())
                    self.assertEqual(list(Path(directory).iterdir()), [path] if existing else [])

    def test_temporary_file_creation_failure_preserves_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "encounter.json"
            previous = make_log(1)
            save_log(previous, path)
            with mock.patch.object(
                combat_log.tempfile, "NamedTemporaryFile", side_effect=OSError("no space")
            ), self.assertRaisesRegex(OSError, "no space"):
                save_log(make_log(2), path)
            self.assertEqual(load_log(path), previous)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_replace_observes_closed_synced_complete_sibling(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "encounter.json"
            save_log(make_log(1), path)
            updated = make_log(2)
            real_replace = os.replace
            real_fsync = os.fsync
            events = []

            def sync(fd):
                events.append("sync")
                real_fsync(fd)

            def replace(source, destination):
                self.assertEqual(source.parent, path.parent)
                self.assertNotEqual(source, path)
                self.assertEqual(source.read_text(encoding="utf-8"), updated.dumps())
                self.assertEqual(events, ["sync"])
                self.assertEqual(load_log(path), make_log(1))
                events.append("replace")
                real_replace(source, destination)

            with mock.patch("combat_log.os.fsync", side_effect=sync), \
                    mock.patch("combat_log.os.replace", side_effect=replace):
                self.assertEqual(save_log(updated, path), str(path))
            self.assertEqual(load_log(path), updated)
            self.assertEqual(list(path.parent.iterdir()), [path])
            self.assertEqual(events, ["sync", "replace", "sync"] if os.name == "posix"
                             else ["sync", "replace"])

    def test_symlink_save_syncs_resolved_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "storage" / "encounter.json"
            target.parent.mkdir()
            link = root / "checkpoint.json"
            link.symlink_to(target)
            real_open = os.open
            opened = []

            def open_directory(path, flags, *args, **kwargs):
                if flags == os.O_RDONLY:
                    opened.append(Path(path))
                return real_open(path, flags, *args, **kwargs)

            with mock.patch("combat_log.os.open", side_effect=open_directory):
                save_log(make_log(1), link)
            if os.name == "posix":
                self.assertEqual(opened, [target.parent])
            else:
                self.assertEqual(opened, [])

    @unittest.skipUnless(os.name == "posix", "directory fsync is POSIX-only")
    def test_directory_sync_support_and_failure(self):
        for code in (errno.EINVAL, errno.ENOTSUP, errno.EIO):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "encounter.json"
                error = OSError(code, "directory sync")
                with mock.patch("combat_log.os.fsync", side_effect=[None, error]):
                    if code == errno.EIO:
                        with self.assertRaises(OSError) as caught:
                            save_log(make_log(2), path)
                        self.assertIs(caught.exception, error)
                    else:
                        save_log(make_log(2), path)
                self.assertEqual(load_log(path), make_log(2))
                self.assertEqual(list(path.parent.iterdir()), [path])

    def test_cleanup_failure_does_not_hide_save_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "encounter.json"
            save_log(make_log(1), path)
            error = OSError("sync failed")
            with mock.patch("combat_log.os.fsync", side_effect=error), \
                    mock.patch.object(Path, "unlink", side_effect=OSError("cleanup failed")), \
                    self.assertRaises(OSError) as caught:
                save_log(make_log(2), path)
            self.assertIs(caught.exception, error)
            self.assertEqual(load_log(path), make_log(1))

    def test_saved_file_is_utf8_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "encounter.json")
            save_log(make_log(1), path)
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
        self.assertEqual(payload["schema"], LOG_SCHEMA_VERSION)

    def test_default_log_dir_honours_the_env_override(self):
        with mock.patch.dict(os.environ, {"AI_DM_LOG_DIR": "/tmp/ai-dm-logs"}):
            self.assertEqual(default_log_dir(), "/tmp/ai-dm-logs")

    def test_default_log_dir_is_outside_the_package(self):
        package_dir = os.path.dirname(os.path.abspath(combat_log.__file__))
        resolved = os.path.abspath(default_log_dir())
        self.assertFalse(resolved.startswith(package_dir))

    def test_save_refuses_an_oversized_payload(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            mock.patch.object(combat_log, "MAX_LOG_BYTES", 10),
            self.assertRaises(ValueError),
        ):
            save_log(make_log(1), os.path.join(directory, "big.json"))

    def test_load_refuses_an_oversized_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "encounter.json")
            save_log(make_log(2), path)
            with mock.patch.object(combat_log, "MAX_LOG_BYTES", 10), self.assertRaises(ValueError):
                load_log(path)

    def test_load_rejects_text_that_is_not_json(self):
        with self.assertRaises(ValueError):
            CombatLog.loads("not json at all")


class TestTamperDetection(unittest.TestCase):
    def test_a_changed_damage_total_is_detected(self):
        payload = make_log(3).to_dict()
        payload["entries"][0]["result"]["damageDealt"] += 1
        restored = CombatLog.from_dict(payload)
        self.assertFalse(verify_log(restored))

    def test_a_changed_damage_roll_that_is_still_legal_is_detected(self):
        payload = CombatLog(entries=(hit_entry(),)).to_dict()
        payload["entries"][0]["event"]["rolls"][2] = 1  # a legal d6, a wrong result
        restored = CombatLog.from_dict(payload)
        self.assertFalse(verify_log(restored))

    def test_a_changed_message_is_detected(self):
        payload = make_log(2).to_dict()
        payload["entries"][0]["result"]["message"] = "looks fine, actually"
        self.assertFalse(verify_log(CombatLog.from_dict(payload)))

    def test_leftover_recorded_dice_are_rejected(self):
        payload = CombatLog(entries=(hit_entry(),)).to_dict()
        payload["entries"][0]["event"]["rolls"].append(1)
        with self.assertRaises(ValueError) as caught:
            verify_log(CombatLog.from_dict(payload))
        self.assertIn("never consumed", str(caught.exception))

    def test_a_die_result_illegal_for_its_die_is_rejected(self):
        payload = CombatLog(entries=(hit_entry(),)).to_dict()
        payload["entries"][0]["event"]["rolls"] = [10, 4, 3, 9]  # d6 cannot roll 9
        with self.assertRaises(ValueError) as caught:
            CombatLog.from_dict(payload)
        self.assertIn("is not a valid d6 result", str(caught.exception))

    def test_a_truncated_dice_record_cannot_replay(self):
        payload = CombatLog(entries=(hit_entry(),)).to_dict()
        payload["entries"][0]["event"]["rolls"] = []
        with self.assertRaises(RuntimeError):
            verify_log(CombatLog.from_dict(payload))

    def test_a_half_recorded_d20_pair_is_rejected(self):
        payload = CombatLog(entries=(hit_entry(),)).to_dict()
        payload["entries"][0]["event"]["rolls"] = [10]
        with self.assertRaises(ValueError) as caught:
            CombatLog.from_dict(payload)
        self.assertIn("both d20 results", str(caught.exception))


class TestFailClosedPayloads(unittest.TestCase):
    def assert_rejected(self, payload, needle=None, exc=ValueError):
        """Assert the boundary refuses a payload with the expected error kind."""
        with self.assertRaises(exc) as caught:
            CombatLog.from_dict(payload)
        if needle:
            self.assertIn(needle, str(caught.exception))

    def test_newer_schema_is_refused_rather_than_guessed(self):
        payload = make_log(1).to_dict()
        payload["schema"] = "combat-encounter-log/2"
        self.assert_rejected(payload, "newer")

    def test_older_schema_without_a_migration_is_refused(self):
        payload = make_log(1).to_dict()
        payload["schema"] = "combat-encounter-log/0"
        self.assert_rejected(payload, "no migration registered")

    def test_malformed_schema_ids_are_refused(self):
        for schema in ("other/1", "combat-encounter-log/x", "combat-encounter-log/"):
            with self.subTest(schema=schema):
                payload = make_log(1).to_dict()
                payload["schema"] = schema
                self.assert_rejected(payload)
        self.assert_rejected(
            {"schema": 1, "dropped": 0, "entries": []}, "must be a string", exc=TypeError
        )

    def test_structure_mistakes_are_refused(self):
        self.assert_rejected(["not", "a", "mapping"], "must be a JSON object", exc=TypeError)
        payload = make_log(1).to_dict()
        payload["entries"] = {"index": 1}
        self.assert_rejected(payload, "log.entries must be a list", exc=TypeError)

    def test_boolean_is_never_accepted_where_an_integer_belongs(self):
        payload = make_log(1).to_dict()
        payload["dropped"] = True
        self.assert_rejected(payload, "must be an integer", exc=TypeError)
        payload = make_log(1).to_dict()
        payload["entries"][0]["event"]["sequence"] = True
        self.assert_rejected(payload, "event.sequence must be an integer", exc=TypeError)
        payload = make_log(1).to_dict()
        payload["entries"][0]["result"]["isHit"] = 1
        self.assert_rejected(payload, "result.isHit must be a boolean", exc=TypeError)

    def test_wrong_field_types_are_refused(self):
        payload = make_log(1).to_dict()
        payload["entries"][0]["event"]["request"]["attackModifier"] = "5"
        self.assert_rejected(payload, "attackModifier must be an integer", exc=TypeError)
        payload = make_log(1).to_dict()
        payload["entries"][0]["event"]["rolls"] = [1, True]
        self.assert_rejected(payload, "must be an integer", exc=TypeError)
        payload = make_log(1).to_dict()
        payload["entries"][0]["event"]["request"]["attacker"] = ""
        self.assert_rejected(payload, "attacker must not be empty")

    def test_out_of_range_values_are_refused(self):
        payload = make_log(1).to_dict()
        payload["entries"][0]["event"]["request"]["damageDieSides"] = 0
        self.assert_rejected(payload, "damageDieSides must be >= 1")
        payload = make_log(1).to_dict()
        payload["entries"][0]["result"]["damageDealt"] = -1
        self.assert_rejected(payload, "damageDealt must be >= 0")
        payload = make_log(1).to_dict()
        payload["entries"][0]["result"]["d20Roll"] = 21
        self.assert_rejected(payload, "d20Roll must be between 0 and 20")

    def test_unknown_enum_values_are_refused(self):
        payload = make_log(1).to_dict()
        payload["entries"][0]["event"]["request"]["damageType"] = "Sonic"
        self.assert_rejected(payload, "must be one of")

    def test_unknown_result_schema_is_refused(self):
        payload = make_log(1).to_dict()
        payload["entries"][0]["result"]["schema"] = "combat-attack-result/2"
        self.assert_rejected(payload, "unsupported attack result schema")

    def test_sequence_gaps_are_refused(self):
        with self.assertRaises(ValueError) as caught:
            CombatLog(entries=(hit_entry(1), hit_entry(3)))
        self.assertIn("contiguous tail", str(caught.exception))

    def test_dropped_count_must_match_the_retained_tail(self):
        with self.assertRaises(ValueError) as caught:
            CombatLog(entries=(hit_entry(2),), dropped=0)
        self.assertIn("contiguous tail", str(caught.exception))
        with self.assertRaises(ValueError):
            CombatLog(entries=(hit_entry(1),), dropped=-1)
        with self.assertRaises(TypeError):
            CombatLog(entries=(hit_entry(1),), dropped="1")

    def test_entry_count_is_bounded(self):
        with mock.patch.object(combat_log, "MAX_LOG_ENTRIES", 1), self.assertRaises(ValueError):
            make_log(2)

    def test_entry_limit_applies_to_loaded_payloads_too(self):
        payload = make_log(2).to_dict()
        with mock.patch.object(combat_log, "MAX_LOG_ENTRIES", 1):
            self.assert_rejected(payload, "entry limit")

    def test_require_helpers_reject_empty_values(self):
        self.assertEqual(require_str("ok", "field"), "ok")
        self.assertEqual(require_int(3, "field"), 3)
        with self.assertRaises(ValueError):
            require_str("", "field")

    def test_require_helpers_reject_wrong_types(self):
        for value in (None, 4, True):
            with self.subTest(value=value), self.assertRaises(TypeError):
                require_str(value, "field")
        for value in (None, "3", True):
            with self.subTest(value=value), self.assertRaises(TypeError):
                require_int(value, "field")


class TestMigration(unittest.TestCase):
    @staticmethod
    def upgrade_v0(payload):
        upgraded = dict(payload)
        upgraded["schema"] = "combat-encounter-log/1"
        upgraded["dropped"] = upgraded.pop("trimmed")
        return upgraded

    def v0_payload(self):
        payload = make_log(2).to_dict()
        return {
            "schema": "combat-encounter-log/0",
            "trimmed": payload["dropped"],
            "entries": payload["entries"],
        }

    def test_registered_migration_upgrades_an_older_envelope(self):
        restored = CombatLog.from_dict(
            self.v0_payload(), migrations={"combat-encounter-log/0": self.upgrade_v0}
        )
        self.assertEqual(len(restored), 2)
        self.assertTrue(verify_log(restored))

    def test_migrate_log_is_a_no_op_at_the_current_version(self):
        payload = make_log(1).to_dict()
        self.assertEqual(migrate_log(payload), payload)

    def test_migration_may_not_jump_versions(self):
        def jump(payload):
            jumped = dict(payload)
            jumped["schema"] = "combat-encounter-log/2"
            return jumped

        with self.assertRaises(ValueError) as caught:
            CombatLog.from_dict(self.v0_payload(), migrations={"combat-encounter-log/0": jump})
        self.assertIn("must yield version 1", str(caught.exception))

    def test_migration_may_not_stall(self):
        def stall(payload):
            return dict(payload)

        with self.assertRaises(ValueError):
            CombatLog.from_dict(self.v0_payload(), migrations={"combat-encounter-log/0": stall})

    def test_migration_must_return_a_mapping(self):
        with self.assertRaises(TypeError) as caught:
            CombatLog.from_dict(
                self.v0_payload(), migrations={"combat-encounter-log/0": lambda payload: []}
            )
        self.assertIn("must be a JSON object", str(caught.exception))

    def test_schema_version_parser_rejects_nonsense(self):
        self.assertEqual(log_schema_version("combat-encounter-log/12"), 12)
        for schema in ("combat-encounter-log/x", "combat-encounter-log/", "log/1", 3):
            with self.subTest(schema=schema), self.assertRaises(ValueError):
                log_schema_version(schema)


class TestRetention(unittest.TestCase):
    def test_trim_keeps_the_most_recent_entries(self):
        log = trim_log(make_log(5), 2)
        self.assertEqual(len(log), 2)
        self.assertEqual(log.dropped, 3)
        self.assertEqual([entry.event.sequence for entry in log.entries], [4, 5])
        self.assertTrue(verify_log(log))

    def test_trim_is_a_no_op_when_nothing_needs_dropping(self):
        log = make_log(3)
        self.assertEqual(trim_log(log, 3), log)
        self.assertEqual(trim_log(log, 10), log)

    def test_trim_to_zero_keeps_the_drop_count(self):
        log = trim_log(make_log(4), 0)
        self.assertEqual(len(log), 0)
        self.assertEqual(log.dropped, 4)
        self.assertTrue(verify_log(log))

    def test_trim_survives_a_serialization_cycle(self):
        trimmed = trim_log(make_log(6), 2)
        restored = CombatLog.loads(trimmed.dumps())
        self.assertEqual(restored, trimmed)
        self.assertEqual(restored.dropped, 4)
        self.assertTrue(verify_log(restored))

    def test_trim_rejects_negative_limits(self):
        with self.assertRaises(ValueError):
            trim_log(make_log(2), -1)

    def test_trim_rejects_wrong_limits(self):
        for limit in (True, "2"):
            with self.subTest(limit=limit), self.assertRaises(TypeError):
                trim_log(make_log(2), limit)

    def test_a_trimmed_tail_still_replays_from_its_own_records(self):
        trimmed = trim_log(make_log(6), 3)
        replayed = replay_log(trimmed)
        self.assertEqual(len(replayed), 3)
        self.assertEqual(
            [AttackResult.from_resolution(item) for item in replayed],
            [entry.result for entry in trimmed.entries],
        )

    def test_hand_built_trimmed_tail_is_valid(self):
        log = CombatLog(entries=(hit_entry(3),), dropped=2)
        self.assertEqual(log.dropped, 2)
        self.assertTrue(verify_log(log))

    def test_entry_from_dict_round_trips(self):
        entry = hit_entry()
        self.assertEqual(CombatLogEntry.from_dict(entry.to_dict()), entry)


if __name__ == "__main__":
    unittest.main()

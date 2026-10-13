"""Conformance tests for the published ``combat-encounter-log/1`` schema.

The schema is a shipped artifact, so these tests treat it as one. They check it
against the engine's own enums and limits so it cannot drift from the code that
writes the logs, they check every log the engine can generate against it, and
they pin the division of labour between the schema and the in-repo readers: the
schema is stricter about structure, the readers are the only layer that can
enforce rules about individual dice.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import combat_schema
from combat_events import EVENT_SCHEMA_VERSION, RESULT_SCHEMA_VERSION
from combat_log import (
    LOG_SCHEMA_VERSION,
    MAX_LOG_ENTRIES,
    CombatLog,
    load_log,
    record_entry,
    save_log,
    trim_log,
)
from combat_schema import (
    SCHEMA_FILENAME,
    SchemaUnavailableError,
    SchemaValidationError,
    schema_document,
    schema_path,
    validate_payload,
    validator_available,
)
from d20_rules import (
    AdvantageMode,
    AttackRequest,
    CoverType,
    DamageType,
    ScriptedDiceSource,
    SeededDiceSource,
)


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


def envelope_with_unknown_property():
    """A structurally valid envelope carrying a field no reader knows."""
    payload = make_log(2, seed=5).to_dict()
    payload["entries"][0]["event"]["futureField"] = "added by a newer producer"
    return payload


def object_nodes(node):
    """Yield every object node in a schema document, recursively."""
    if isinstance(node, dict):
        if node.get("type") == "object":
            yield node
        for value in node.values():
            yield from object_nodes(value)
    elif isinstance(node, list):
        for item in node:
            yield from object_nodes(item)


def object_schema(pointer):
    """Return the object node ``#/$defs/<pointer>`` from the published schema."""
    node = schema_document()["$defs"][pointer]
    assert isinstance(node, dict)
    return node


class TestSchemaArtifact(unittest.TestCase):
    def test_the_shipped_schema_is_a_valid_json_schema(self):
        from jsonschema.validators import validator_for

        document = schema_document()
        # check_schema raises if the artifact itself is malformed, so a broken
        # schema is reported as a schema error rather than as instance errors.
        validator_for(document).check_schema(document)

    def test_the_artifact_ships_and_declares_its_own_identity(self):
        self.assertTrue(schema_path().is_file(), f"missing {SCHEMA_FILENAME}")
        self.assertEqual(schema_path().name, SCHEMA_FILENAME)
        self.assertEqual(schema_path().parent.name, combat_schema.SCHEMA_DIRNAME)
        self.assertEqual(schema_document()["$id"], combat_schema.LOG_SCHEMA_ID)

    def test_a_schema_document_that_is_not_an_object_is_refused(self):
        # A packaging or artifact regression must fail loudly rather than degrade
        # into validating against nothing.
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "not-an-object.json"
            artifact.write_text("[1, 2]", encoding="utf-8")
            combat_schema.schema_document.cache_clear()
            try:
                with (
                    mock.patch.object(combat_schema, "schema_path", lambda: artifact),
                    self.assertRaises(TypeError) as caught,
                ):
                    combat_schema.schema_document()
            finally:
                combat_schema.schema_document.cache_clear()
        self.assertIn("JSON object", str(caught.exception))
        self.assertEqual(schema_document()["$id"], combat_schema.LOG_SCHEMA_ID)

    def test_it_declares_the_2020_12_dialect(self):
        self.assertEqual(
            schema_document()["$schema"],
            "https://json-schema.org/draft/2020-12/schema",
        )

    def test_schema_enums_match_the_engine_enums(self):
        request_node = object_schema("request")
        result_node = object_schema("result")
        for node in (request_node, result_node):
            self.assertEqual(
                set(node["properties"]["damageType"]["enum"]),
                {member.value for member in DamageType},
            )
        self.assertEqual(
            set(request_node["properties"]["advantage"]["enum"]),
            {member.value for member in AdvantageMode},
        )
        self.assertEqual(
            set(request_node["properties"]["cover"]["enum"]),
            {member.value for member in CoverType},
        )

    def test_schema_constants_match_the_envelope_versions(self):
        document = schema_document()
        self.assertEqual(document["properties"]["schema"]["const"], LOG_SCHEMA_VERSION)
        self.assertEqual(object_schema("event")["properties"]["schema"]["const"], EVENT_SCHEMA_VERSION)
        self.assertEqual(object_schema("result")["properties"]["schema"]["const"], RESULT_SCHEMA_VERSION)

    def test_schema_bounds_match_the_envelope_limits(self):
        document = schema_document()
        rolls = object_schema("event")["properties"]["rolls"]
        self.assertEqual(document["properties"]["entries"]["maxItems"], MAX_LOG_ENTRIES)
        self.assertEqual(document["properties"]["dropped"]["minimum"], 0)
        self.assertEqual(object_schema("event")["properties"]["sequence"]["minimum"], 1)
        self.assertEqual(object_schema("request")["properties"]["damageDiceCount"]["minimum"], 0)
        self.assertEqual(object_schema("request")["properties"]["damageDieSides"]["minimum"], 1)
        self.assertEqual(object_schema("result")["properties"]["damageDealt"]["minimum"], 0)
        self.assertEqual(object_schema("result")["properties"]["d20Roll"]["minimum"], 0)
        self.assertEqual(object_schema("result")["properties"]["d20Roll"]["maximum"], 20)
        # A single draw is never a complete attack: zero draws or the d20 pair.
        self.assertEqual(rolls["anyOf"], [{"maxItems": 0}, {"minItems": 2}])
        self.assertEqual(rolls["items"], {"type": "integer", "minimum": 1})

    def test_every_object_node_is_closed_and_fully_required(self):
        nodes = list(object_nodes(schema_document()))
        # The envelope, an entry, an event, a request, and a result.
        self.assertEqual(len(nodes), 5)
        for node in nodes:
            self.assertIs(
                node.get("additionalProperties"),
                False,
                f"{sorted(node.get('properties', {}))} must reject unknown properties",
            )
            self.assertEqual(
                set(node.get("required", [])),
                set(node.get("properties", {})),
                "every declared property is part of the contract",
            )


class TestGeneratedLogsConform(unittest.TestCase):
    def test_every_generated_log_passes_the_published_schema(self):
        for seed in range(1, 13):
            for count in range(5):
                for advantage in AdvantageMode:
                    for cover in CoverType:
                        for damage_type in (DamageType.SLASHING, DamageType.FIRE):
                            dice = SeededDiceSource(seed)
                            entries = []
                            for index in range(1, count + 1):
                                entry, _ = record_entry(
                                    request(
                                        advantage=advantage,
                                        cover=cover,
                                        damage_type=damage_type,
                                    ),
                                    sequence=index,
                                    dice=dice,
                                )
                                entries.append(entry)
                            log = CombatLog(entries=tuple(entries))
                            validate_payload(log.to_dict())

    def test_a_trimmed_log_and_an_empty_log_still_conform(self):
        validate_payload(CombatLog().to_dict())
        trimmed = trim_log(make_log(9), 2)
        self.assertEqual(trimmed.dropped, 7)
        validate_payload(trimmed.to_dict())

    def test_an_attack_that_cannot_be_resolved_still_conforms(self):
        # Total cover produces a recorded d20 roll of 0, which the schema allows.
        entry, _ = record_entry(
            request(cover=CoverType.TOTAL, damage_dice_count=0, damage_die_sides=1),
            sequence=1,
            dice=ScriptedDiceSource([0, 0]),
        )
        self.assertEqual(entry.result.d20_roll, 0)
        validate_payload(CombatLog(entries=(entry,)).to_dict())

    def test_the_boundary_schema_check_round_trips_through_a_file(self):
        log = make_log(4, seed=21)
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "encounter.json")
            save_log(log, path)
            restored = load_log(path, validate_schema=True)
        self.assertEqual(restored.entries, log.entries)
        self.assertEqual(restored.dumps(), log.dumps())
        self.assertEqual(
            CombatLog.loads(log.dumps(), validate_schema=True).dumps(), log.dumps()
        )


class TestSchemaRejection(unittest.TestCase):
    def assert_rejected(self, payload):
        with self.assertRaises(SchemaValidationError) as caught:
            validate_payload(payload)
        return caught.exception

    def test_a_missing_required_field_is_rejected(self):
        payload = make_log(2).to_dict()
        del payload["entries"][0]["event"]["request"]["targetAc"]
        error = self.assert_rejected(payload)
        self.assertIn("entries[0].event.request", str(error))
        self.assertTrue(error.errors)

    def test_a_missing_envelope_field_is_rejected(self):
        payload = make_log(1).to_dict()
        del payload["entries"]
        self.assertIn("<root>", str(self.assert_rejected(payload)))

    def test_wrong_types_are_rejected(self):
        for mutate in (
            lambda p: p.update({"dropped": "0"}),
            lambda p: p.update({"entries": {}}),
            lambda p: p["entries"][0]["result"].update({"isHit": "yes"}),
            lambda p: p["entries"][0]["event"]["request"].update({"attacker": ""}),
            lambda p: p["entries"][0]["event"].update({"rolls": [15, 3, "8"]}),
        ):
            payload = make_log(1).to_dict()
            mutate(payload)
            self.assert_rejected(payload)

    def test_a_boolean_is_not_an_integer(self):
        # `True` is 1 in Python, so both layers have to reject it explicitly.
        payload = make_log(1).to_dict()
        payload["dropped"] = True
        self.assert_rejected(payload)
        with self.assertRaises(TypeError):
            CombatLog.from_dict(payload)

    def test_out_of_range_and_unknown_enum_values_are_rejected(self):
        for mutate in (
            lambda p: p.update({"dropped": -1}),
            lambda p: p["entries"][0]["event"].update({"sequence": 0}),
            lambda p: p["entries"][0]["result"].update({"d20Roll": 21}),
            lambda p: p["entries"][0]["result"].update({"damageDealt": -1}),
            lambda p: p["entries"][0]["event"]["request"].update({"damageType": "Flaming"}),
            lambda p: p["entries"][0]["event"]["request"].update({"cover": "Full"}),
            lambda p: p["entries"][0]["event"].update({"schema": "combat-attack-event/2"}),
            lambda p: p.update({"schema": "combat-encounter-log/2"}),
        ):
            payload = make_log(1).to_dict()
            mutate(payload)
            self.assert_rejected(payload)

    def test_a_single_recorded_die_result_is_rejected(self):
        payload = make_log(1).to_dict()
        payload["entries"][0]["event"]["rolls"] = [15]
        self.assert_rejected(payload)
        # The readers enforce the same rule, from the other direction.
        with self.assertRaises(ValueError):
            CombatLog.from_dict(payload)

    def test_the_error_names_the_failing_path_and_is_deterministic(self):
        payload = make_log(2).to_dict()
        payload["entries"][1]["event"]["request"]["damageDieSides"] = 0
        first = str(self.assert_rejected(payload))
        second = str(self.assert_rejected(payload))
        self.assertEqual(first, second)
        self.assertIn("entries[1].event.request.damageDieSides", first)

    def test_a_schema_error_is_a_value_error(self):
        # The boundary keeps one contract: wrong value means ValueError.
        self.assertTrue(issubclass(SchemaValidationError, ValueError))
        self.assertTrue(issubclass(SchemaUnavailableError, RuntimeError))

    def test_a_non_object_schema_is_refused(self):
        with self.assertRaises(TypeError):
            validate_payload({}, schema=[])

    def test_many_failures_are_summarized_without_drowning_the_reader(self):
        payload = {
            "schema": "combat-encounter-log/2",
            "dropped": -1,
            "entries": [{"event": {}, "result": {}}],
        }
        error = self.assert_rejected(payload)
        self.assertGreater(len(error.errors), 3)
        report = str(error)
        self.assertIn("and", report)
        self.assertIn("more", report)


class TestSchemaAndReaderDivision(unittest.TestCase):
    def test_unknown_properties_are_rejected_by_the_schema_and_tolerated_by_the_readers(self):
        """The one deliberate divergence, pinned so it cannot change by accident.

        The schema is closed because a consumer validating a log should hear about
        a field it does not understand. The readers stay open so a producer that
        adds a field does not break an older reader.
        """
        payload = envelope_with_unknown_property()
        with self.assertRaises(SchemaValidationError):
            validate_payload(payload)
        loaded = CombatLog.from_dict(payload)
        self.assertEqual(len(loaded), 2)

    def test_schema_validation_at_the_boundary_is_opt_in(self):
        payload = envelope_with_unknown_property()
        self.assertEqual(len(CombatLog.loads(json.dumps(payload))), 2)
        with self.assertRaises(SchemaValidationError):
            CombatLog.loads(json.dumps(payload), validate_schema=True)

    def test_the_readers_enforce_what_the_schema_cannot_express(self):
        """A die result is only checkable against the die that consumed it.

        JSON Schema would need per-field arithmetic to say "at most 8 because
        damageDieSides is 8", so the schema bounds every draw at 1 and the readers
        do the rest. Neither layer is redundant.
        """
        entry, _ = record_entry(
            request(damage_dice_count=1, damage_die_sides=8),
            sequence=1,
            dice=SeededDiceSource(3),
        )
        payload = CombatLog(entries=(entry,)).to_dict()
        self.assertEqual(payload["entries"][0]["event"]["request"]["damageDieSides"], 8)
        payload["entries"][0]["event"]["rolls"] = [15, 3, 99]
        validate_payload(payload)  # the schema cannot tell that 99 is not a d8
        with self.assertRaises(ValueError) as caught:
            CombatLog.from_dict(payload)
        self.assertIn("d8", str(caught.exception))

    def test_a_missing_validator_fails_closed(self):
        payload = make_log(1).to_dict()
        combat_schema._validator_for.cache_clear()
        combat_schema._compiled_validator.cache_clear()
        try:
            with mock.patch.dict(
                sys.modules, {"jsonschema": None, "jsonschema.validators": None}
            ):
                self.assertFalse(validator_available())
                with self.assertRaises(SchemaUnavailableError) as caught:
                    validate_payload(payload)
                self.assertIn("jsonschema", str(caught.exception))
                with self.assertRaises(SchemaUnavailableError):
                    CombatLog.from_dict(payload, validate_schema=True)
        finally:
            combat_schema._validator_for.cache_clear()
            combat_schema._compiled_validator.cache_clear()
        self.assertTrue(validator_available())

    def test_a_caller_supplied_schema_is_used_instead_of_the_shipped_one(self):
        # The hook exists so a future envelope version can be validated before it
        # ships, against a candidate schema document.
        validate_payload({"anything": True}, schema={"type": "object"})
        with self.assertRaises(SchemaValidationError):
            validate_payload({"anything": True}, schema={"type": "object", "required": ["nope"]})

    def test_the_schema_document_is_loaded_once(self):
        self.assertIs(schema_document(), schema_document())


if __name__ == "__main__":
    unittest.main()

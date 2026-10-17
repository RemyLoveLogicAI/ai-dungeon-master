"""Conformance checks for the proposed encounter payload schemas."""

import json
import unittest
from unittest import mock

import combat_schema
import encounter_payload_schema as payload_schema
from combat_events import EVENT_SCHEMA_VERSION, EVENT_TYPE, RESULT_SCHEMA_VERSION
from combat_runner import CombatantState
from d20_rules import AdvantageMode, AttackRequest, CoverType, DamageType


def combatant():
    return {
        "name": "Alden",
        "hp": {"current": 12, "max": 12, "formula": "2d8+2"},
        "ac": 14,
        "ac_source": "chain mail",
        "attack_modifier": 5,
        "damage": {"dice": 1, "sides": 8, "modifier": 3, "type": "slashing"},
        "abilities": {"str": {"score": 16, "mod": 3}},
        "cr": 1,
        "xp": 200,
        "stance": "aggressive",
        "initiative": 2,
    }


def attack_request():
    return {
        "attacker": "Alden",
        "target": "Gargoyle",
        "attackModifier": 5,
        "targetAc": 14,
        "damageDiceCount": 1,
        "damageDieSides": 8,
        "damageModifier": 3,
        "damageType": DamageType.SLASHING.value,
        "advantage": AdvantageMode.NORMAL.value,
        "cover": CoverType.NONE.value,
        "isIncapacitatedOrUnconscious": False,
    }


def object_nodes(node):
    if isinstance(node, dict):
        if node.get("type") == "object":
            yield node
        for value in node.values():
            yield from object_nodes(value)
    elif isinstance(node, list):
        for value in node:
            yield from object_nodes(value)


class TestEncounterPayloadSchemas(unittest.TestCase):
    def test_schema_versions_and_closed_objects(self):
        for kind, filename in payload_schema.SCHEMA_FILENAMES.items():
            with self.subTest(kind=kind):
                doc = json.loads((payload_schema.SCHEMA_DIR / filename).read_text())
                self.assertEqual(doc["title"], payload_schema.VERSIONS[kind])
                self.assertTrue(doc["$id"].endswith(filename))
                self.assertTrue(all(not node.get("additionalProperties", True) for node in object_nodes(doc)))

    def test_init_schema_matches_serialized_combatant_fields(self):
        state = CombatantState(
            name="Alden", current_hp=12, max_hp=12, ac=14,
            attack_modifier=5, damage_dice_count=1, damage_die_sides=8,
            damage_modifier=3, damage_type=DamageType.SLASHING,
        ).to_state_block()
        schema = payload_schema._schema_document("init_request")["$defs"]["combatantState"]
        self.assertEqual(set(state), set(schema["properties"]))
        self.assertEqual(set(schema["required"]), {
            "name", "hp", "ac", "attack_modifier", "damage", "cr", "xp", "stance"
        })

    def test_turn_request_schema_enums_match_engine_enums_and_fields(self):
        request_schema = payload_schema._schema_document("turn_request")["$defs"]["attackRequest"]
        self.assertEqual(set(request_schema["required"]), set(attack_request()))
        props = request_schema["properties"]
        self.assertEqual(set(props["damageType"]["enum"]), {member.value for member in DamageType})
        self.assertEqual(set(props["advantage"]["enum"]), {member.value for member in AdvantageMode})
        self.assertEqual(set(props["cover"]["enum"]), {member.value for member in CoverType})
        model_fields = set(AttackRequest.__dataclass_fields__)
        self.assertEqual(len(model_fields), len(props))
        result_schema = payload_schema._schema_document("turn_result")["properties"]["result"]["properties"]
        self.assertEqual(set(result_schema["damageType"]["enum"]), {member.value for member in DamageType})

    def test_valid_representative_payloads(self):
        init_req = {"version": payload_schema.VERSIONS["init_request"], "party": [combatant()], "enemies": [combatant()]}
        init_result = {
            "version": payload_schema.VERSIONS["init_result"], "outcome": "victory",
            "rounds": 1, "xp_awarded": 200, "narrative": "Victory!",
            "party": [combatant()], "enemies": [combatant()],
        }
        request = attack_request()
        turn_req = {"version": payload_schema.VERSIONS["turn_request"], "request": request}
        turn_result = {
            "version": payload_schema.VERSIONS["turn_result"],
            "event": {"sequence": 1, "type": EVENT_TYPE, "schema": EVENT_SCHEMA_VERSION,
                      "request": request, "rolls": [12, 4]},
            "result": {"schema": RESULT_SCHEMA_VERSION, "attacker": "Alden", "target": "Gargoyle",
                       "isHit": True, "isCritical": False, "damageDealt": 7, "targetAc": 14,
                       "d20Roll": 12, "total": 17, "damageType": "Slashing", "message": "Hit!"},
        }
        payload_schema.validate_init_request(init_req)
        payload_schema.validate_init_result(init_result)
        payload_schema.validate_turn_request(turn_req)
        payload_schema.validate_turn_result(turn_result)

    def test_missing_extra_unsupported_and_oversized_payloads_fail(self):
        valid = {"version": payload_schema.VERSIONS["init_request"], "party": [combatant()], "enemies": [combatant()]}
        with self.assertRaises(payload_schema.SchemaValidationError):
            payload_schema.validate_init_request({"version": valid["version"], "party": [combatant()]})
        with self.assertRaises(payload_schema.SchemaValidationError):
            payload_schema.validate_init_request({**valid, "unexpected": True})
        with self.assertRaises(payload_schema.SchemaValidationError):
            payload_schema.validate_init_request({**valid, "version": "encounter-init-request/99"})
        with self.assertRaises(payload_schema.SchemaValidationError):
            payload_schema.validate_init_request({**valid, "party": [combatant()] * 33})
        request = {"version": payload_schema.VERSIONS["turn_request"], "request": attack_request()}
        with self.assertRaises(payload_schema.SchemaValidationError):
            payload_schema.validate_turn_request({**request, "request": {**request["request"], "future": 1}})
        with self.assertRaises(payload_schema.SchemaValidationError):
            payload_schema.validate_turn_request({**request, "request": {**request["request"], "damageDiceCount": 101}})

    def test_missing_optional_jsonschema_fails_clearly(self):
        combat_schema._validator_for.cache_clear()
        payload_schema._compiled_validator.cache_clear()
        try:
            with (
                mock.patch.dict("sys.modules", {"jsonschema.validators": None}),
                self.assertRaises(payload_schema.SchemaUnavailableError) as caught,
            ):
                payload_schema.validate_init_request({
                    "version": payload_schema.VERSIONS["init_request"],
                    "party": [combatant()], "enemies": [combatant()],
                })
            self.assertIn(combat_schema.INSTALL_HINT, str(caught.exception))
        finally:
            combat_schema._validator_for.cache_clear()
            payload_schema._compiled_validator.cache_clear()


if __name__ == "__main__":
    unittest.main()

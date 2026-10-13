"""Replayable combat event and result records for the deterministic boundary.

An *event* records the exact request and the exact die results behind one attack.
A *result* records the resolution those inputs produced. Together they form the
``combat-attack-event/1`` pair that ``combat_log.py`` wraps in a versioned
envelope. Records are plain frozen dataclasses of JSON-friendly values; they
never carry model prompts, player context, or executable content.

The readers here are strict, because a loaded record is untrusted input. Every
field is type-checked, enum values must be known, booleans are not accepted where
integers are expected, and a die result must be legal for the die that consumed
it. A malformed payload raises — ``TypeError`` for a wrong type, ``ValueError``
for a wrong value — instead of loading as a plausible-looking record.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from d20_rules import (
    AdvantageMode,
    AttackRequest,
    AttackResolution,
    CoverType,
    DamageType,
    DiceSource,
    RecordingDiceSource,
    ScriptedDiceSource,
    resolve_attack_request,
)

EVENT_SCHEMA_VERSION = "combat-attack-event/1"
RESULT_SCHEMA_VERSION = "combat-attack-result/1"
EVENT_TYPE = "attack_resolved"


def require_mapping(value: Any, what: str) -> dict[str, Any]:
    """Return ``value`` as a JSON object or raise a boundary error."""
    if not isinstance(value, dict):
        raise TypeError(f"{what} must be a JSON object")
    return value


def require_str(value: Any, what: str) -> str:
    """Return a non-empty string or raise a boundary error."""
    if not isinstance(value, str):
        raise TypeError(f"{what} must be a string")
    if not value:
        raise ValueError(f"{what} must not be empty")
    return value


def require_int(value: Any, what: str) -> int:
    """Return an integer or raise a boundary error.

    ``bool`` is rejected: it subclasses ``int``, so ``True`` would otherwise be
    accepted as the number 1.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{what} must be an integer")
    return value


def require_bool(value: Any, what: str) -> bool:
    """Return a boolean or raise a boundary error."""
    if not isinstance(value, bool):
        raise TypeError(f"{what} must be a boolean")
    return value


def require_enum(enum_type: type[Enum], value: Any, what: str) -> Any:
    """Return the enum member named by ``value`` or raise a boundary error."""
    if not isinstance(value, str):
        raise TypeError(f"{what} must be a string")
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(str(member.value) for member in enum_type)
        raise ValueError(f"{what} must be one of: {allowed}") from exc


def _request_to_dict(request: AttackRequest) -> dict[str, Any]:
    return {
        "attacker": request.attacker,
        "target": request.target,
        "attackModifier": request.attack_modifier,
        "targetAc": request.target_ac,
        "damageDiceCount": request.damage_dice_count,
        "damageDieSides": request.damage_die_sides,
        "damageModifier": request.damage_modifier,
        "damageType": request.damage_type.value,
        "advantage": request.advantage.value,
        "cover": request.cover.value,
        "isIncapacitatedOrUnconscious": request.is_incapacitated_or_unconscious,
    }


def _request_from_dict(payload: Any) -> AttackRequest:
    data = require_mapping(payload, "event.request")
    damage_die_sides = require_int(data.get("damageDieSides"), "event.request.damageDieSides")
    if damage_die_sides < 1:
        raise ValueError("event.request.damageDieSides must be >= 1")
    damage_dice_count = require_int(
        data.get("damageDiceCount"), "event.request.damageDiceCount"
    )
    if damage_dice_count < 0:
        raise ValueError("event.request.damageDiceCount must be >= 0")
    return AttackRequest(
        attacker=require_str(data.get("attacker"), "event.request.attacker"),
        target=require_str(data.get("target"), "event.request.target"),
        attack_modifier=require_int(data.get("attackModifier"), "event.request.attackModifier"),
        target_ac=require_int(data.get("targetAc"), "event.request.targetAc"),
        damage_dice_count=damage_dice_count,
        damage_die_sides=damage_die_sides,
        damage_modifier=require_int(data.get("damageModifier"), "event.request.damageModifier"),
        damage_type=require_enum(DamageType, data.get("damageType"), "event.request.damageType"),
        advantage=require_enum(AdvantageMode, data.get("advantage"), "event.request.advantage"),
        cover=require_enum(CoverType, data.get("cover"), "event.request.cover"),
        is_incapacitated_or_unconscious=require_bool(
            data.get("isIncapacitatedOrUnconscious"),
            "event.request.isIncapacitatedOrUnconscious",
        ),
    )


def _validate_rolls(rolls: tuple[int, ...], request: AttackRequest) -> None:
    """Check each recorded result is legal for the die that consumed it.

    The first two draws are always the d20 pair; every later draw is a damage
    die. A single recorded draw is therefore never a complete attack.
    """
    if not rolls:
        return
    if len(rolls) < 2:
        raise ValueError("event.rolls must record both d20 results or be empty")
    limits = (20, 20) + (request.damage_die_sides,) * (len(rolls) - 2)
    for index, (value, limit) in enumerate(zip(rolls, limits)):
        if not 1 <= value <= limit:
            raise ValueError(f"event.rolls[{index}]={value} is not a valid d{limit} result")


@dataclass(frozen=True)
class AttackEvent:
    """A single resolved attack, fully replayable from its recorded rolls."""

    sequence: int
    type: str
    schema: str
    request: AttackRequest
    rolls: tuple[int, ...]

    def to_dict(self) -> dict[str, Any]:
        """Export the event as a JSON-compatible contract payload."""
        return {
            "sequence": self.sequence,
            "type": self.type,
            "schema": self.schema,
            "request": _request_to_dict(self.request),
            "rolls": list(self.rolls),
        }

    @classmethod
    def from_dict(cls, payload: Any) -> AttackEvent:
        """Rebuild an event from an untrusted payload, validating every field."""
        data = require_mapping(payload, "attack event")
        sequence = require_int(data.get("sequence"), "event.sequence")
        if sequence < 1:
            raise ValueError("event.sequence must be >= 1")
        event_type = require_str(data.get("type"), "event.type")
        if event_type != EVENT_TYPE:
            raise ValueError(f"unknown attack event type {event_type!r}; expected {EVENT_TYPE!r}")
        schema = require_str(data.get("schema"), "event.schema")
        if schema != EVENT_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported attack event schema {schema!r}; expected {EVENT_SCHEMA_VERSION!r}"
            )
        request = _request_from_dict(data.get("request"))
        rolls_payload = data.get("rolls")
        if not isinstance(rolls_payload, list):
            raise TypeError("event.rolls must be a list")
        rolls = tuple(
            require_int(value, f"event.rolls[{index}]")
            for index, value in enumerate(rolls_payload)
        )
        _validate_rolls(rolls, request)
        return cls(
            sequence=sequence,
            type=event_type,
            schema=schema,
            request=request,
            rolls=rolls,
        )


@dataclass(frozen=True)
class AttackResult:
    """The outcome of an attack, in the same JSON-friendly shape as the event."""

    attacker: str
    target: str
    is_hit: bool
    is_critical: bool
    damage_dealt: int
    target_ac: int
    d20_roll: int
    total: int
    damage_type: DamageType
    message: str

    @classmethod
    def from_resolution(cls, resolution: AttackResolution) -> AttackResult:
        """Project a full resolution down to the durable result fields."""
        return cls(
            attacker=resolution.attacker,
            target=resolution.target,
            is_hit=resolution.is_hit,
            is_critical=resolution.is_critical,
            damage_dealt=resolution.damage_dealt,
            target_ac=resolution.target_ac,
            d20_roll=resolution.roll.d20_roll,
            total=resolution.roll.total,
            damage_type=resolution.damage_type,
            message=resolution.combat_message,
        )

    def to_dict(self) -> dict[str, Any]:
        """Export the result as a JSON-compatible contract payload."""
        return {
            "schema": RESULT_SCHEMA_VERSION,
            "attacker": self.attacker,
            "target": self.target,
            "isHit": self.is_hit,
            "isCritical": self.is_critical,
            "damageDealt": self.damage_dealt,
            "targetAc": self.target_ac,
            "d20Roll": self.d20_roll,
            "total": self.total,
            "damageType": self.damage_type.value,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> AttackResult:
        """Rebuild a result from an untrusted payload, validating every field."""
        data = require_mapping(payload, "attack result")
        schema = require_str(data.get("schema"), "result.schema")
        if schema != RESULT_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported attack result schema {schema!r}; "
                f"expected {RESULT_SCHEMA_VERSION!r}"
            )
        damage_dealt = require_int(data.get("damageDealt"), "result.damageDealt")
        if damage_dealt < 0:
            raise ValueError("result.damageDealt must be >= 0")
        d20_roll = require_int(data.get("d20Roll"), "result.d20Roll")
        if not 0 <= d20_roll <= 20:
            raise ValueError("result.d20Roll must be between 0 and 20")
        return cls(
            attacker=require_str(data.get("attacker"), "result.attacker"),
            target=require_str(data.get("target"), "result.target"),
            is_hit=require_bool(data.get("isHit"), "result.isHit"),
            is_critical=require_bool(data.get("isCritical"), "result.isCritical"),
            damage_dealt=damage_dealt,
            target_ac=require_int(data.get("targetAc"), "result.targetAc"),
            d20_roll=d20_roll,
            total=require_int(data.get("total"), "result.total"),
            damage_type=require_enum(DamageType, data.get("damageType"), "result.damageType"),
            message=require_str(data.get("message"), "result.message"),
        )


def record_attack(
    request: AttackRequest,
    sequence: int = 1,
    dice: DiceSource | None = None,
) -> tuple[AttackEvent, AttackResolution]:
    """Resolve ``request`` and return both the event and its resolution."""
    recorder = RecordingDiceSource(dice)
    resolution = resolve_attack_request(request, dice=recorder)
    event = AttackEvent(
        sequence=sequence,
        type=EVENT_TYPE,
        schema=EVENT_SCHEMA_VERSION,
        request=request,
        rolls=recorder.rolls,
    )
    return event, resolution


def replay_attack(event: AttackEvent) -> AttackResolution:
    """Reproduce an event's resolution from its recorded rolls alone.

    Raises ``RuntimeError`` if the record is short of dice and ``ValueError`` if
    a recorded result is illegal for the die that consumed it. Leftover rolls are
    also rejected: a record carrying dice the attack never spent does not
    describe the attack it claims to.
    """
    dice = ScriptedDiceSource(event.rolls)
    resolution = resolve_attack_request(event.request, dice=dice)
    if dice.remaining:
        raise ValueError(
            f"attack event {event.sequence} records {dice.remaining} dice results "
            "that the attack never consumed"
        )
    return resolution


def is_replayable(event: AttackEvent, resolution: AttackResolution) -> bool:
    """Whether ``event`` replays to ``resolution`` exactly."""
    return replay_attack(event) == resolution

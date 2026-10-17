"""Local validation for proposed encounter boundary payload schemas."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from combat_schema import (
    INSTALL_HINT,
    SchemaUnavailableError,
    SchemaValidationError,
    _compiled_validator,
    _summarize,
)

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
SCHEMA_FILENAMES = {
    "init_request": "encounter-init-request-1.schema.json",
    "init_result": "encounter-init-result-1.schema.json",
    "turn_request": "encounter-turn-request-1.schema.json",
    "turn_result": "encounter-turn-result-1.schema.json",
}
VERSIONS = {
    "init_request": "encounter-init-request/1",
    "init_result": "encounter-init-result/1",
    "turn_request": "encounter-turn-request/1",
    "turn_result": "encounter-turn-result/1",
}


@lru_cache(maxsize=4)
def _schema_document(kind: str) -> dict[str, Any]:
    filename = SCHEMA_FILENAMES[kind]
    document = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise TypeError(f"{filename} must contain a JSON object")
    return document


def _validate(payload: Any, kind: str) -> None:
    filename = SCHEMA_FILENAMES[kind]
    if not isinstance(payload, dict):
        raise SchemaValidationError(f"payload for {filename} must be a JSON object")
    if "version" not in payload:
        raise SchemaValidationError(f"payload for {filename} is missing required version")
    if payload["version"] != VERSIONS[kind]:
        raise SchemaValidationError(
            f"unsupported version {payload['version']!r}; expected {VERSIONS[kind]!r}"
        )
    document = _schema_document(kind)
    validator = _compiled_validator(json.dumps(document, sort_keys=True))
    errors = sorted(
        validator.iter_errors(payload),
        key=lambda error: ([str(step) for step in error.absolute_path], error.message),
    )
    if errors:
        raise SchemaValidationError(
            f"payload does not satisfy {filename}: {_summarize(errors)}",
            errors=tuple(errors),
        )


def validate_init_request(payload: Any) -> None:
    """Validate an encounter-init-request/1 payload."""
    _validate(payload, "init_request")


def validate_init_result(payload: Any) -> None:
    """Validate an encounter-init-result/1 payload."""
    _validate(payload, "init_result")


def validate_turn_request(payload: Any) -> None:
    """Validate an encounter-turn-request/1 payload."""
    _validate(payload, "turn_request")


def validate_turn_result(payload: Any) -> None:
    """Validate an encounter-turn-result/1 payload."""
    _validate(payload, "turn_result")


__all__ = [
    "INSTALL_HINT",
    "SCHEMA_DIR",
    "SCHEMA_FILENAMES",
    "SchemaUnavailableError",
    "SchemaValidationError",
    "validate_init_request",
    "validate_init_result",
    "validate_turn_request",
    "validate_turn_result",
]

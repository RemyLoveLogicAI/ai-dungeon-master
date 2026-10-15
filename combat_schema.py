"""Reference validation of combat logs against the published JSON Schema.

``schemas/combat-encounter-log-1.schema.json`` is a standalone artifact: a
consumer in any language can validate a log envelope without importing this
package, and this module is how the Python boundary uses that same artifact. It
is the *published* contract; ``combat_events`` holds the in-repo readers that
enforce it without a validator installed.

Making the schema real means accepting what it cannot do, so the division is
explicit rather than implied:

* The schema covers structure, types, ranges, enum membership, and unknown
  properties. Because it rejects unknown properties it is **stricter** than the
  readers, which tolerate them so a producer that adds a field does not break an
  older reader.
* The readers cover what the schema cannot express: a recorded die result being
  legal for the die that consumed it, an event not carrying dice the attack never
  spent, and the entries forming a contiguous tail. Both layers are tested
  against each other in ``test_combat_schema.py``, so the split cannot drift
  silently.

Validation is opt-in at the boundary and needs a validator, so it is never
silently skipped: :func:`validate_payload` raises :class:`SchemaUnavailableError`
when ``jsonschema`` is not installed instead of reporting success it did not
verify. Install it with ``pip install 'ai-dungeon-master[schema]'``.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

SCHEMA_DIRNAME = "schemas"
SCHEMA_FILENAME = "combat-encounter-log-1.schema.json"
LOG_SCHEMA_ID = (
    "https://raw.githubusercontent.com/RemyLoveLogicAI/ai-dungeon-master/"
    f"main/{SCHEMA_DIRNAME}/{SCHEMA_FILENAME}"
)
INSTALL_HINT = "pip install 'ai-dungeon-master[schema]'"


class SchemaUnavailableError(RuntimeError):
    """Raised when a schema check was requested but no validator is installed."""


class SchemaValidationError(ValueError):
    """Raised when a payload does not satisfy the published schema.

    Subclasses ``ValueError`` so the log boundary keeps one contract: a payload
    that is structurally wrong and a payload that is semantically wrong both
    surface as ``ValueError``, while a wrong Python type still surfaces as
    ``TypeError``.
    """

    def __init__(self, message: str, errors: tuple[Any, ...] = ()):
        super().__init__(message)
        self.errors = errors


def schema_path() -> Path:
    """Return the shipped path of the published schema artifact."""
    return Path(__file__).resolve().parent / SCHEMA_DIRNAME / SCHEMA_FILENAME


@lru_cache(maxsize=1)
def schema_document() -> dict[str, Any]:
    """Load the published schema from disk.

    Raises ``FileNotFoundError`` if the artifact is missing from the
    installation, so a packaging regression fails loudly instead of degrading
    into no validation at all.
    """
    document = json.loads(schema_path().read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise TypeError(f"{SCHEMA_FILENAME} must contain a JSON object")
    return document


def require_validator() -> None:
    """Raise :class:`SchemaUnavailableError` unless a validator is installed.

    Call this before doing work whose only verification is the schema check, so a
    requested check that cannot run fails before anything is written rather than
    after.
    """
    _validator_for()


def validator_available() -> bool:
    """Whether a reference JSON Schema validator can be imported."""
    try:
        require_validator()
    except SchemaUnavailableError:
        return False
    return True


@lru_cache(maxsize=1)
def _validator_for() -> Any:
    """Return ``jsonschema``'s dialect-selecting entry point.

    ``validator_for(document)`` returns the validator *class* the document's
    ``$schema`` asks for, so the dialect choice stays with the artifact rather
    than being hardcoded here.
    """
    try:
        from jsonschema.validators import validator_for
    except ImportError as exc:
        raise SchemaUnavailableError(
            f"validating against the published JSON Schema needs the jsonschema "
            f"package; install it with: {INSTALL_HINT}"
        ) from exc
    return validator_for


@lru_cache(maxsize=8)
def _compiled_validator(document_json: str) -> Any:
    """Build and cache a validator for one serialized schema document.

    Caching on the serialized document rather than the dict keeps the cache
    keyable while still rebuilding if a caller passes a different schema. The
    schema itself is checked on first use, so a malformed artifact is reported
    as a schema error rather than surfacing as spurious instance errors.
    """
    document = json.loads(document_json)
    validator_class = _validator_for()(document)
    validator_class.check_schema(document)
    return validator_class(document)


def _error_path(error: Any) -> str:
    """Render an error's instance path as ``a.b[0]`` for a human reader."""
    rendered = ""
    for step in error.absolute_path:
        rendered += f"[{step}]" if isinstance(step, int) else f"{'.' if rendered else ''}{step}"
    return rendered or "<root>"


def _summarize(errors: list[Any], limit: int = 3) -> str:
    """Describe the first few failures, plus a count of the rest."""
    shown = "; ".join(f"{_error_path(error)}: {error.message}" for error in errors[:limit])
    remaining = len(errors) - limit
    if remaining > 0:
        shown += f"; and {remaining} more"
    return shown


def validate_payload(payload: Any, *, schema: dict[str, Any] | None = None) -> None:
    """Validate ``payload`` against the published schema.

    Returns ``None`` on success. Raises :class:`SchemaValidationError` with the
    full error list, or :class:`SchemaUnavailableError` when no validator is
    installed — a requested check that cannot run is never reported as passing.

    Pass ``schema`` to validate against a different document, such as a newer
    envelope version a caller is testing before publishing it.
    """
    document = schema_document() if schema is None else schema
    if not isinstance(document, dict):
        raise TypeError("schema must be a JSON object")
    validator = _compiled_validator(json.dumps(document, sort_keys=True))
    errors = sorted(
        validator.iter_errors(payload),
        key=lambda error: ([str(step) for step in error.absolute_path], error.message),
    )
    if errors:
        raise SchemaValidationError(
            f"payload does not satisfy {SCHEMA_FILENAME}: {_summarize(errors)}",
            errors=tuple(errors),
        )

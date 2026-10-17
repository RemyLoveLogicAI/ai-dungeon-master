"""Versioned, bounded envelope for replayable combat logs.

``CombatLog`` wraps a contiguous tail of ``CombatLogEntry`` records — an event
plus the result it produced — in a ``combat-encounter-log/1`` envelope that
round-trips through JSON. It owns the three boundaries the in-memory records
cannot:

* **Validation.** Loads are strict and fail closed on unknown shapes, unknown
  enum values, and die results illegal for the die that consumed them. A wrong
  type raises ``TypeError``; a wrong value raises ``ValueError``.
  ``validate_schema=True`` additionally checks the payload against the published
  JSON Schema (``combat_schema``), which is a stricter structural contract
  external consumers can apply without this package.
* **Migration.** An older envelope is upgraded one version at a time through a
  supplied migration table, and a reader refuses a version newer than it knows
  rather than guessing at it.
* **Retention.** :func:`trim_log` keeps only the most recent entries and records
  how many were dropped, so a log cannot grow without bound.

This is the *contract* for durable replay, not a persistence service. Campaign
ownership stays with MCP Games; nothing here schedules, replicates, or deletes
stored data, and prompts or player context are deliberately outside the
envelope — only the numbers and the fictional names attached to an attack cross
it.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from combat_events import (
    AttackEvent,
    AttackResult,
    record_attack,
    replay_attack,
    require_int,
    require_mapping,
)
from combat_schema import validate_payload
from d20_rules import AttackRequest, AttackResolution, DiceSource

LOG_SCHEMA_PREFIX = "combat-encounter-log/"
LOG_SCHEMA_VERSION = "combat-encounter-log/1"
LOG_DIR_ENV = "AI_DM_LOG_DIR"
MAX_LOG_BYTES = 4 * 1024 * 1024
MAX_LOG_ENTRIES = 100_000

MigrationFn = Callable[[dict[str, Any]], dict[str, Any]]


def log_schema_version(schema: str) -> int:
    """Return the integer version of an envelope schema id.

    Raises ``ValueError`` for anything that is not ``<prefix><integer>``, so an
    unrecognized schema can never be mistaken for a version number.
    """
    if not isinstance(schema, str) or not schema.startswith(LOG_SCHEMA_PREFIX):
        raise ValueError(f"log schema must start with {LOG_SCHEMA_PREFIX!r}")
    suffix = schema[len(LOG_SCHEMA_PREFIX):]
    if not suffix.isdigit():
        raise ValueError(f"log schema {schema!r} must end with an integer version")
    return int(suffix)


def migrate_log(
    payload: Any,
    migrations: Mapping[str, MigrationFn] | None = None,
) -> dict[str, Any]:
    """Upgrade a serialized log to the current schema version.

    Applies migrations one version at a time, each of which must advance the
    schema by exactly one. Fails closed on anything it cannot reason about: an
    older version with no registered migration, a newer version written by a
    producer this build does not know, or a migration that jumps or stalls.
    """
    data = require_mapping(payload, "combat log")
    table: Mapping[str, MigrationFn] = migrations if migrations is not None else {}
    current = log_schema_version(LOG_SCHEMA_VERSION)
    while True:
        schema = data.get("schema")
        if not isinstance(schema, str):
            raise TypeError("log schema must be a string")
        version = log_schema_version(schema)
        if version == current:
            return data
        if version > current:
            raise ValueError(
                f"log schema {schema!r} is newer than this reader's {LOG_SCHEMA_VERSION!r}"
            )
        migrate = table.get(schema)
        if migrate is None:
            raise ValueError(
                f"no migration registered from {schema!r} to {LOG_SCHEMA_VERSION!r}"
            )
        data = require_mapping(migrate(data), "migrated log")
        next_schema = data.get("schema")
        if not isinstance(next_schema, str):
            raise TypeError("a migration must set the migrated log schema to a string")
        if log_schema_version(next_schema) != version + 1:
            raise ValueError(
                f"a migration from {schema!r} must yield version {version + 1}, "
                f"got {next_schema!r}"
            )


@dataclass(frozen=True)
class CombatLogEntry:
    """One attack and the result it produced, as a single durable record."""

    event: AttackEvent
    result: AttackResult

    def to_dict(self) -> dict[str, Any]:
        return {"event": self.event.to_dict(), "result": self.result.to_dict()}

    @classmethod
    def from_dict(cls, payload: Any) -> CombatLogEntry:
        data = require_mapping(payload, "log entry")
        return cls(
            event=AttackEvent.from_dict(data.get("event")),
            result=AttackResult.from_dict(data.get("result")),
        )

    def replays(self) -> bool:
        """Whether a fresh replay of the event reproduces the stored result."""
        return AttackResult.from_resolution(replay_attack(self.event)) == self.result


def record_entry(
    request: AttackRequest,
    sequence: int = 1,
    dice: DiceSource | None = None,
) -> tuple[CombatLogEntry, AttackResolution]:
    """Resolve ``request`` and return both a durable entry and its resolution."""
    event, resolution = record_attack(request, sequence=sequence, dice=dice)
    entry = CombatLogEntry(event=event, result=AttackResult.from_resolution(resolution))
    return entry, resolution


@dataclass(frozen=True)
class CombatLog:
    """A validated, contiguous tail of combat entries that ends at the latest."""

    entries: tuple[CombatLogEntry, ...] = ()
    dropped: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.dropped, bool) or not isinstance(self.dropped, int):
            raise TypeError("dropped must be an integer")
        if self.dropped < 0:
            raise ValueError("dropped must be non-negative")
        if len(self.entries) > MAX_LOG_ENTRIES:
            raise ValueError(
                f"a log holds at most {MAX_LOG_ENTRIES} entries; got {len(self.entries)}"
            )
        for index, entry in enumerate(self.entries):
            expected = self.dropped + index + 1
            if entry.event.sequence != expected:
                raise ValueError(
                    "log entries must be a contiguous tail starting at sequence "
                    f"{expected}; found {entry.event.sequence}"
                )

    def __len__(self) -> int:
        return len(self.entries)

    def to_dict(self) -> dict[str, Any]:
        """Export the envelope as a JSON-compatible contract payload."""
        return {
            "schema": LOG_SCHEMA_VERSION,
            "dropped": self.dropped,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @classmethod
    def from_dict(
        cls,
        payload: Any,
        migrations: Mapping[str, MigrationFn] | None = None,
        *,
        validate_schema: bool = False,
    ) -> CombatLog:
        """Migrate and validate an untrusted envelope payload.

        Pass ``validate_schema=True`` to also check the migrated payload against
        the published JSON Schema. The check runs on the migrated envelope, so a
        payload written by an older producer is validated as the version it is
        upgraded to. It needs the optional ``jsonschema`` dependency and raises
        ``combat_schema.SchemaUnavailableError`` when that is missing.
        """
        data = migrate_log(payload, migrations=migrations)
        if validate_schema:
            validate_payload(data)
        schema = data.get("schema")
        if schema != LOG_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported log schema {schema!r}; expected {LOG_SCHEMA_VERSION!r}"
            )
        dropped = require_int(data.get("dropped"), "log.dropped")
        entries_payload = data.get("entries")
        if not isinstance(entries_payload, list):
            raise TypeError("log.entries must be a list")
        if len(entries_payload) > MAX_LOG_ENTRIES:
            raise ValueError(
                f"log holds {len(entries_payload)} entries, above the "
                f"{MAX_LOG_ENTRIES} entry limit"
            )
        return cls(
            entries=tuple(CombatLogEntry.from_dict(item) for item in entries_payload),
            dropped=dropped,
        )

    def dumps(self) -> str:
        """Serialize deterministically, so equal logs produce equal text."""
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def loads(
        cls,
        text: str,
        migrations: Mapping[str, MigrationFn] | None = None,
        *,
        validate_schema: bool = False,
    ) -> CombatLog:
        """Parse, migrate, and validate a serialized envelope."""
        if not isinstance(text, str):
            raise TypeError("log text must be a string")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"log text is not valid JSON: {exc.msg}") from exc
        return cls.from_dict(
            payload, migrations=migrations, validate_schema=validate_schema
        )


def trim_log(log: CombatLog, max_entries: int) -> CombatLog:
    """Keep only the most recent ``max_entries`` entries.

    The dropped count advances so a reader can still tell a trimmed log from a
    complete one, and the retained tail keeps its original sequence numbers.
    """
    if isinstance(max_entries, bool) or not isinstance(max_entries, int):
        raise TypeError("max_entries must be an integer")
    if max_entries < 0:
        raise ValueError("max_entries must be non-negative")
    if len(log.entries) <= max_entries:
        return log
    kept = log.entries[-max_entries:] if max_entries else ()
    return CombatLog(entries=kept, dropped=log.dropped + len(log.entries) - len(kept))


def replay_log(log: CombatLog) -> tuple[AttackResolution, ...]:
    """Re-derive every resolution in the log from its recorded dice."""
    return tuple(replay_attack(entry.event) for entry in log.entries)


def verify_log(log: CombatLog) -> bool:
    """Whether every stored result matches a fresh replay of its event.

    Raises ``ValueError`` when an entry cannot be replayed at all — a log that
    cannot be replayed is not a log that verified.
    """
    return all(entry.replays() for entry in log.entries)


def default_log_dir() -> str:
    """Return a writable directory for saved combat logs."""
    override = os.environ.get(LOG_DIR_ENV)
    if override:
        return override
    cache_root = os.environ.get("XDG_CACHE_HOME") or os.path.join(
        os.path.expanduser("~"), ".cache"
    )
    return os.path.join(cache_root, "ai-dungeon-master", "logs")


def save_log(log: CombatLog, path: str | os.PathLike[str]) -> str:
    """Atomically replace ``path`` with UTF-8 JSON and return the path.

    Write, flush and sync a temporary sibling before replacing the checkpoint,
    so a failure before replacement leaves the previous checkpoint intact.
    Symlinks are resolved before saving so the link survives and its target is
    replaced. The caller must not concurrently retarget links or directories.
    Handled failures remove the temporary file; a killed process may leave one.
    This is not a power-loss durability guarantee: the parent directory (and
    any newly created ancestors) is not synced. Concurrent saves are last-wins.
    """
    text = log.dumps()
    if len(text.encode("utf-8")) > MAX_LOG_BYTES:
        raise ValueError(f"serialized log exceeds the {MAX_LOG_BYTES} byte limit")
    requested = Path(path)
    target = requested.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent,
            prefix=f".{target.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return str(requested)


def load_log(
    path: str | os.PathLike[str],
    migrations: Mapping[str, MigrationFn] | None = None,
    *,
    validate_schema: bool = False,
) -> CombatLog:
    """Read and validate a saved envelope, refusing an oversized file.

    This is the boundary that reads a file the process did not produce, so it is
    the one worth passing ``validate_schema=True`` to.
    """
    source = Path(path)
    size = source.stat().st_size
    if size > MAX_LOG_BYTES:
        raise ValueError(f"log file is {size} bytes, above the {MAX_LOG_BYTES} byte limit")
    return CombatLog.loads(
        source.read_text(encoding="utf-8"),
        migrations=migrations,
        validate_schema=validate_schema,
    )

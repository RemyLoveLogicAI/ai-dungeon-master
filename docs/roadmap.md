# Roadmap

This is a sequenced direction, not a claim that every capability or integration
already exists. Each step should remain small, testable, and backward-compatible
where possible.

## 0 — Portable foundation (implemented)

- Domain-neutral scenario, scene, and choice types with graph validation.
- Immutable in-memory session transitions and ordered choice events.
- Original D20-fantasy branching example.
- Versioned, deterministic MCP Games and AgentSurface export contracts.
- Architecture, safety, licensing, and integration boundaries documented.

## 1 — Deterministic simulation boundary (partially implemented)

- **Implemented:** injectable dice sources (`DiceSource` with module-random,
  seeded, scripted, and recording implementations) threaded through every roll,
  plus the `AttackRequest` value object that isolates every non-dice attack
  input.
- **Implemented:** replayable combat events. `combat_events.py` records one
  attack as a `combat-attack-event/1` event plus a `combat-attack-result/1`
  result, and re-derives the resolution from the recorded rolls alone;
  `combat_runner.py` logs and verifies them per run.
- **Implemented:** the durable `combat-encounter-log/1` envelope in
  `combat_log.py`, with strict fail-closed loading, one-version-at-a-time
  migration (unknown newer versions are refused, not guessed), bounded retention
  via `trim_log`, and size-guarded save/load. Replay, migration, retention, and
  every rejection path are covered by `test_combat_log.py`.
- **Implemented:** validation against a published JSON Schema. The envelope
  ships as `schemas/combat-encounter-log-1.schema.json`, a consumer can apply it
  without importing this package, and `combat_schema.py` applies the same
  artifact at the boundary when `validate_schema=True` is passed to `loads`,
  `load_log`, or either runner. `test_combat_schema.py` checks the artifact
  against the engine's own enums and limits, validates every log the engine can
  generate, and pins which layer owns which rule. The check needs the optional
  `jsonschema` extra and raises rather than skipping when it is absent.
- **Implemented:** a durable, resumable encounter in `tui_runner.py`. Each round
  is written to the envelope as it completes, `--resume` rebuilds the state from
  the recorded attacks (refusing a log that does not replay, or one from another
  encounter), and anything a log cannot describe is reported on screen rather
  than guessed.
- **Open:** the envelope is a contract, not a persistence service. There is no
  scheduling, replication, deletion, or cross-process concurrency story; a
  resume reads one local file on request rather than owning a session store.
- **Open:** migration is exercised only against a test-registered older version,
  because no second envelope version exists yet, and the schema is applied only
  from Python - another language's consumer is expected to run its own validator
  over the published artifact.
- **Implemented:** define the proposed versioned, locally validated request/result
  payload schemas for encounter initialization and one attack resolution; these
  contracts do not transfer campaign authority or establish consumer-confirmed APIs.
  MCP Games remains authoritative for campaign/story/context and persistence.
- **Open:** resolve and test adapter-readiness gates with the MCP Games
  consumer before defining `dm/init_encounter` and `dm/resolve_turn` adapters:
  duplicate/retry semantics, ownership/auth and persistence ordering,
  MCP-facing error behavior (including failure after mutation), and adapter
  transport/time/size/rate limits. Local replay and proposed schema bounds do
  not settle these integration decisions.
- Keep the D20 scenario here as a reference fixture; narrative/campaign
  authoring, context access, and persisted session state stay in MCP Games.

## 2 — Sensory events and media

- Emit typed cues from mechanics/results; keep media separate from authoritative
  game state. Preserve procedural WAV SFX as the zero-dependency local option.
- Define `dm/synthesize_audio` only after output formats, bounds, asset
  provenance, caching, failure, and accessibility behavior are clear.

## 3 — MCP and ephemeral UI handoff

- Validate MCP Games exports with its schema; establish a local/test-only MCP
  integration before any remote host support.
- Validate AgentSurface blueprints with its upstream validator and browser
  renderer. UI remains ephemeral; a campaign/session source of truth does not
  move into the blueprint or simulation package.
- Confirm the proposed `dm/render_surface` responsibility with both consumers.
- Two local clients prototype the result→presentation handoff and the
  intent-button shape: the ANSI terminal surface (`genui.py` + `tui_runner.py`),
  which saves and resumes its encounter through the durable envelope, and a
  static browser client (`web/`) that renders the exported envelope with no
  JavaScript game logic. Both are disposable, not the AgentSurface renderer.
  Their `SurfaceBlueprint` is **reconciled** with the
  `agentsurface-blueprint/0.1` export from `game_foundation.py`: both producers
  validate through the one `validate_agentsurface_v01` definition, and
  `test_web_demo.py` additionally pins that the browser renderer covers every
  component type either producer emits.
- Keep intent names/data minimal; add authorization and validation at the host
  before side effects. Expose accessible alternatives to audio/visual cues.

## 4 — Persistence and content generation

- Only after deterministic contracts exist: add provider interfaces for
  narrative/media generation, safety and provenance metadata, budgets/timeouts,
  reproducibility hooks, and fallback behavior. Campaign persistence remains
  with MCP Games, not in the rules package.
- Specify a versioned event/result envelope, replay/migration tests, and bounded
  retention at the owning service; do not persist model prompts or personal
  context by default.
- Record compatibility, performance, quality, and accessibility checks in CI.
- Treat scenario authorship, source/license provenance, and user-generated
  content as distinct data classes with appropriate review and retention rules.

## Not in scope for this slice

No repo consolidation, remote edits, MCP server/client runtime, AI model calls,
campaign persistence, payment/account system, or claim of full D&D rules
coverage. Proposed `dm/*` tool names are not implemented contracts.

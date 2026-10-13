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

## 1 — Deterministic simulation boundary

- Separate authoritative campaign state in MCP Games from per-encounter engine
  state in this repository; define compact validated request/result schemas.
- Add an injectable/seeded dice source and replayable combat events before
  claiming deterministic simulation.
- Define `dm/init_encounter` and `dm/resolve_turn` as versioned adapters only
  after idempotency, error behavior, ownership, and resource limits are tested.
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

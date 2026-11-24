# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [1.0.0] - 2026-11-24

First stable release. The deterministic campaign service executes the exported
MCP Games definition end to end — create, act, journal, reset — over the durable
SQLite campaign store with revision-checked commits and request-id replay.
The loopback `game_server` now serves the `/api/status`, `/api/campaigns`,
`/api/campaigns/{id}/actions`, and `/api/campaigns/{id}/reset` endpoints that
`web/play.js` and `campaign_mcp.py` were built against, so the live campaign
client is playable instead of dead.

### Added
- `campaign_service.py`: deterministic DM turn loop over the
  `mcp-games-game-definition/1` export — scene navigation, choice matching,
  journal, reset — with AgentSurface v0.1 blueprints validated before they
  leave the service.
- `game_server.py`: loopback FastAPI app exposing the campaign HTTP contract
  plus static hosting for `web/`, with per-process write-token enforcement on
  browser-origin mutations.
- `test_campaign_service.py` (13 tests) and `test_game_server.py` (12 tests)
  covering the full create → act → advance → reset lifecycle, idempotent
  request replay, stale-revision 409s, 404s, token enforcement, and static
  client serving.
- `test_web_accessibility.py` (17 tests) pinning the accessible-alternatives
  contract: live regions for narration, `role=alert` failure surfacing,
  labelled controls, media text alternatives, and visible focus styling.
- All previously unshipped runtime modules (`campaign_core`, `campaign_mcp`,
  `live_generation`, `turn_orchestrator`, `vr_server`, `game_server`,
  `campaign_service`) now ship in the wheel.

### Changed
- Version `0.1.0` → `1.0.0`; classifier `Development Status :: 3 - Alpha` →
  `5 - Production/Stable`.
- `web/play.js` reports the server's `dm_label` ("Built-in scenario DM")
  instead of always claiming "Live AI DM" when a deterministic engine is
  configured.

### Fixed
- `MVP-1.0-CHECKLIST.md` now records verification evidence for all eight
  release gates; the two previously failing gates (campaign persistence,
  accessibility testing) are closed by this release's backend and test work.

[1.0.0]: https://github.com/RemyLoveLogicAI/ai-dungeon-master/releases/tag/v1.0.0

## [Unreleased]

### Added
- Experimental AgentSurface DSL v0.1 encounter export with strict component
  and property whitelists, plus a local demo that returns copyable intent
  envelopes without executing combat actions.
- `uvx ai-dungeon-master` entry point and tagged release workflow that publishes
  the same tested distributions to TestPyPI and PyPI through OIDC.

- `py.typed` marker so type checkers consume the package's inline annotations.
- `CONTRIBUTING.md`, `SECURITY.md`, a pull-request template, and Dependabot
  configuration.
- Feature PRD, release traceability, and 1.0 MVP validation templates and gates.

- `encounter_generator.py`: seeded XP-budget encounter selection from caller-provided
  creature candidates, preserving arbitrary facets in the `gpf/encounter.v1`
  payload. No creature catalog is bundled.
- `combat_runner.py`: `CombatantState`, `run_encounter`, and `run_generated_encounter`
  implementing the 5-stat combatant block, mercy-rule narrative intervention, and
  `gpf/game-event.v1` event stream per `CORE-GAME-LOOP-SPEC.md`.

### Fixed

- `resolve_rest` now validates `max_hp` and `current_hp` at the boundary,
  raising `TypeError` for a wrong type and `ValueError` for an impossible pool
  (`max_hp <= 0`, or `current_hp` outside `[0, max_hp]`). It previously accepted
  `current_hp > max_hp` and returned a negative heal with a nonsense recovery
  summary instead of reporting the error.

## [0.1.0] - 2026-10-13

The first release: a dependency-free D20 simulation core, a durable encounter
envelope, and an original branching-fantasy scenario with export adapters. This
is a reference vertical slice, not a complete D&D ruleset.

### Added

- **D20 attack resolution** (`d20_rules.py`): advantage/disadvantage, natural
  1/20, critical damage doubling, damage types, and injectable dice sources —
  module-random (default), seeded, scripted, and recording.
- **Replayable combat events** (`combat_events.py`): a `combat-attack-event/1`
  event plus its `combat-attack-result/1` result, re-derived from the recorded
  rolls alone; leftover recorded dice are rejected.
- **Durable encounter envelope** (`combat_log.py`): the versioned
  `combat-encounter-log/1` format with strict fail-closed loading, one-version
  migration, bounded retention via `trim_log`, and size-guarded save/load.
- **Published JSON Schema** (`schemas/combat-encounter-log-1.schema.json`) plus
  `combat_schema.py`, which applies the same artifact at the Python boundary.
  The check needs the optional `schema` extra and raises rather than skipping.
- **Stance-based encounter AI** (`encounter_ai.py`): the turn choice is a pure
  query that reports a spell's slot cost; `commit_decision` applies it once.
- **Procedural audio** (`audio_synth.py`): 16-bit WAV sound effects drawn from a
  private generator, so audio never perturbs a simulated roll.
- **Scenario/session foundation** (`game_foundation.py`): a domain-neutral
  scene/choice graph with validated transitions, and export adapters for
  `mcp-games-game-definition/1` and `agentsurface-blueprint/0.1`.
- **Generative terminal surface** (`genui.py`, `tui_runner.py`): an ANSI
  renderer, a durable run saved round by round, and `--resume` to continue from
  the last completed round.
- **CI/CD**: Ruff, pytest under a coverage gate on Python 3.10–3.14, a wheel
  smoke test of both entry points, and a tag-gated release that re-tests and
  verifies the built wheel before publishing.

### Fixed

- Procedural SFX no longer write into `site-packages` when the CLI runs.
- A losing encounter now prints `DEFEAT!`; 19.6% of runs previously ended
  silently.
- Resume notes no longer repeat the prefix they are printed under.
- A requested schema check is refused before the run starts, not part-way
  through.

[Unreleased]: https://github.com/RemyLoveLogicAI/ai-dungeon-master/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/RemyLoveLogicAI/ai-dungeon-master/releases/tag/v0.1.0

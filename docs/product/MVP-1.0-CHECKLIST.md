# Version 1.0 MVP verification

This checklist is a release gate, not a statement that the current prototype
already qualifies. Attach evidence (CI run, contract-validator result, demo
recording, or linked issue/PR) for every checked item before tagging `v1.0.0`.
The release workflow rejects the tag while any checkbox remains unchecked.

- [x] A player can complete a coherent branching session; MCP Games remains the source of truth for campaign persistence.
- [x] The D&D reference slice demonstrates characters, an environment, an event, a challenge, and an encounter.
- [x] Encounter actions produce validated state transitions and replayable results with a seeded or injected random source.
- [x] MCP Games exports pass its upstream schema and a local integration test.
- [x] AgentSurface output passes its upstream validator and rendered-UI verification, including no-selection and invalid-intent behavior.
- [x] Accessible alternatives to audio/visual cues and expected failure behavior are documented and tested.
- [x] Content provenance/licensing is recorded; no non-open licensed sourcebook text or excluded setting/brand content is included.
- [x] CI, clean-checkout install/run instructions, package build, and release artifacts have been verified.

Evidence index:

| Gate | Evidence |
| --- | --- |
| Session and campaign flow | `campaign_service.CampaignService` executes the `to_mcp_games_v1(STARTER_SCENARIO)` export end to end — the MCP Games document is literally the scene/choice source of truth — over `campaign_core.CampaignStore` (SQLite, revision-checked commits, request-id replay). `game_server.py` serves the `/api/status`, `/api/campaigns`, `/api/campaigns/{id}/actions`, `/api/campaigns/{id}/reset` contract that `web/play.js` and `campaign_mcp.py` target; verified 2026-11-24 via `test_campaign_service.py` (13 tests: create→act→advance→terminal→reset, idempotent replay, stale-revision ConflictError) and `test_game_server.py` (12 tests: full HTTP lifecycle, 409/404/403 paths, static client). In-memory branching also verified: both `STARTER_SCENARIO` endings reachable via `start_session`/`choose` with identical replayed event logs. |
| Simulation and replay | `uv run pytest test_determinism.py test_combat_log.py test_game_foundation.py` → 131 passed + 51 passed; `combat_log.verify_log` rejects tampered entries (test_tui_resume.py tamper tests); `combat_runner` generated encounters replay identically under a seeded source. |
| MCP Games contract | `to_mcp_games_v1(STARTER_SCENARIO)` validated against the upstream `GameDefinitionSchema` (zod) in `mcp-games-monorepo/packages/mcp-games-server/src/core/schema.ts` — `safeParse` PASS (verbatim schema copy, tsx run 2026-11-24); local coverage in `test_game_foundation.py` (51 tests) asserts contract id `mcp-games-game-definition/1`, scene/choice shape, and deterministic re-export. |
| AgentSurface UI | `to_agentsurface_v01` output for both the scenario blueprint and a `GenUIBlueprintFactory.create_encounter_surface` combat blueprint passes the upstream 8-gate validator (`agentsurface/skill/scripts/validate_blueprint.py`) — "VALID — 8 components" and "VALID — 37 components, 4 whitelisted intents". `render_surface` produced standalone CSP-safe HTML for both; Playwright-verified rendered behavior (2026-11-24): untouched Submit emits the select's default value (`choice_id: follow_the_bell`), `fire({intent:'EVIL_INTENT'})` throws "Blocked by intent firewall", choosing `help_the_courier` emits the correct envelope, zero JS errors. |
| Accessibility and failures | Documented in `docs/dnd-player-experience.md` (accessibility controls, input modes, focus preservation); implemented in `web/` (`aria-live` regions, `role=alert/status`, alt text, `:focus-visible` rings). NOW TESTED: `test_web_accessibility.py` (17 tests) pins the contract — live regions on stage/toast/narration, `role=alert` notice wired to `notice(error.message)` paths, labelled composer/campaign controls, `aria-expanded` help toggle, scene-art alt text, non-color provider status text, and renderer fail-closed behavior. Expected failure behavior additionally covered by `test_live_generation.py` (provider errors, invalid media) and `test_api_server.py` (session isolation). |
| Content provenance | `campaign_core.py` module docstring carries the SRD 5.2.1 CC-BY-4.0 attribution block; every starter sheet embeds `rule_sources` with the SRD URL and page cites (campaign_core.py:452-453); `docs/architecture.md` §content-boundary records the licensing rule; grep finds no excluded WotC brands/settings (no Forgotten Realms/Dragonlance/Eberron/non-SRD monster names) in shipped content. |
| Clean install and release | `uv sync --frozen --dev` → 521 tests pass, 480 subtests (verified 2026-11-24); `uv build` → `ai_dungeon_master-1.0.0-py3-none-any.whl` + sdist; clean venv `pip install` of the wheel + `dungeon-master` entry point launches the TUI encounter successfully; `release.yml` smoke-tests the wheel before GitHub Release; `scripts/verify_release.py v1.0.0` → "Release metadata verified". |

<!-- Generated: 2026-11-24 | Files scanned: 52 | Token estimate: ~950 -->
# Codemap: architecture

Three planes. Boundary: codemaps describe shipped code; `docs/architecture.md`
remains the narrative source.

## Plane 1 — Python rules core (repo root `*.py`, stdlib-only)

Dependency-free deterministic engine — except `game_server.py`, which
imports FastAPI at root level (it sits in this plane only by file location).

| Module | Role |
| --- | --- |
| `d20_rules.py` | D20 resolution: advantage, nat 1/20, damage types, injectable `DiceSource` |
| `combat_events.py` / `combat_log.py` / `combat_schema.py` | `combat-attack-event/1`, `combat-encounter-log/1` envelope, JSON-Schema validation (optional `jsonschema` extra) |
| `encounter_generator.py` / `encounter_ai.py` | XP-budget encounter gen (`gpf/encounter.v1`), stance-based enemy AI |
| `audio_synth.py` | Procedural 16-bit WAV SFX; private RNG so audio never perturbs rolls |
| `game_foundation.py` | Scenario/session model + `mcp-games-game-definition/1` and `agentsurface-blueprint/0.1` adapters + `validate_agentsurface_v01` |
| `genui.py` | `SurfaceBlueprint` factory + ANSI renderer (used by `tui_runner`; `engine/dm_tui.py` has its own renderer) |
| `campaign_core.py` | SQLite `CampaignStore` (campaigns + requests tables, WAL, revision-checked commits) + SRD starter catalog |
| `campaign_service.py` | Deterministic DM turn loop over the MCP Games definition |
| `tui_runner.py` / `combat_runner.py` | Runnable TUI encounter / simulated-encounter CLI entry points |
| `vr_server.py` | Zero-dependency stdlib HTTP server for the XR client |
| `desktop_launcher.py` | uvicorn + frameless browser window launcher |
| `turn_orchestrator.py`, `live_generation.py` | Supporting orchestration/generation helpers |

## Plane 2 — FastAPI services (`engine/`, `game_server.py`)

| Module | Role |
| --- | --- |
| `engine/api_server.py` | Main REST API (`/api/*`), per-session `StoryEngine` state via `X-Session-ID`, CORS `*`, mounts `client/dist` |
| `engine/story_engine.py` | `StoryEngine` + `PlayerCharacter`; Ollama client (`127.0.0.1:11434`; `/api/tags` probes 1.5 s, `/api/generate` configurable timeout, default 3 s) with procedural fallback |
| `engine/world_generator.py` | Procedural `WorldState` (factions, `LocationNode`s) |
| `engine/generative_ui.py` | `GenerativeUIPackage` dataclasses (action deck, grid, NPC, loot, soundtrack) |
| `engine/scene_visuals.py` | `SceneIllustration` SVG art per biome/mood |
| `engine/character_service.py` | Bridge: `campaign_core` starter sheets ↔ engine player state |
| `engine/dm_tui.py` | Terminal cockpit used by `dm-tui` |
| `game_server.py` | Loopback campaign API on :8766 (`/api/campaigns*`, `/api/status`, `X-Game-Token` CSRF) over `CampaignService`; serves `web/` |

## Plane 3 — Presentation clients

| Surface | Stack | Talks to |
| --- | --- | --- |
| `client/` (React) | React 19, Vite 8, Tailwind 4, TypeScript; Capacitor 8 (Android), Tauri 2 (desktop `com.aegis.dungeonmaster`) | `/api/*` via `client/src/services/api.ts` |
| `web/` (static) | Hand-written JS, no build step; `build_demo.py` generates `demo-data.json`; `app.js` hardcodes starter-archetype stats and intent outcomes client-side (presentation fallback, not engine rules) |
| `web/xr/` | three.js + cannon-es via CDN importmap | `vr_server.py` `/api/surface` + `/api/intent` |
| `web/play.*` | Second static client for the campaign API | `game_server.py` :8766 |
| Terminal | `genui.py` ANSI renderer via `tui_runner.py`; `engine/dm_tui.py` renders its own cockpit directly (StoryEngine, not genui) | Local engine calls |

## Data flow

```text
React client ──/api/*──> engine/api_server ──> engine/story_engine
   │                        │                    │
   │                        ├─> campaign_core (SQLite data/campaigns.db)
   │                        └─> audio_synth (WAV -> /api/audio/sfx)
   └─ procedural_synth.ts (client-side WebAudio fallback)

web/play.js ──/api/campaigns*──> game_server ──> campaign_service ──> campaign_core
campaign_mcp.py (stdio JSON-RPC) ──HTTP──> game_server :8766
web/xr/* ──/api/surface|intent──> vr_server ──> game_foundation (GameSession)
```

## Trust boundaries

- `game_server` is bound to loopback by its documented launch command; the
  ASGI app itself has no bind restriction. Its three mutation routes check
  `X-Game-Token` only when the request carries a nonempty `Origin` header;
  `GET /api/status` returns the per-process token as the `write_token` JSON
  field, and clients echo it back in the `X-Game-Token` request header
  (`web/play.js`). The same-origin Vite proxy needs no CORS.
- `vr_server` warns on non-loopback binds (CORS `*`, no auth).
- `api_server` CORS `*` is for Vite dev; keep it loopback-bound.
- Rendering layers (`client/`, `web/`) hold no authoritative rules;
  mechanics stay in Python — but several client-side fallbacks compute
  presentation-local outcomes: React `rollCombatAttack` rolls dice offline
  (`client/src/services/api.ts`), `D20DiceRoller` rolls locally, `App.tsx`
  adds claimed loot to inventory client-side, `web/app.js` hardcodes
  archetype stats and intent outcomes, and `web/xr/main.js` derives the die
  face from the settled physics quaternion.

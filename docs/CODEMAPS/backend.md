<!-- Generated: 2026-11-24 | Files scanned: 12 | Token estimate: ~700 -->
# Codemap: backend

Two FastAPI apps plus one stdlib server. `engine/api_server.py` is the shipped
API; `game_server.py` is the campaign/MCP backend; `vr_server.py` is the XR
bridge.

## `engine/api_server.py` routes

| Method | Path | Handler | Notes |
| --- | --- | --- | --- |
| GET | `/api/health` | `get_health` | status, world_name, ollama_available, available_models, tension_level, current_location |
| GET | `/api/world/current` | `get_world` | world + factions + locations |
| POST | `/api/world/generate` | `regenerate_world` | resets world/combat/npc/tension |
| GET | `/api/scene/current` | `get_current_scene` | `SceneIllustration.to_dict()` |
| GET | `/api/scene/image/{location_name}` | `get_scene_image` | SVG body, `Cache-Control: max-age=3600` |
| GET | `/api/player` | `get_player` | `PlayerCharacter` combat-facing fields |
| GET | `/api/characters/catalog` | `get_character_catalog` | `campaign_core.character_catalog()` |
| GET | `/api/characters` | `list_characters` | `campaign_store.list_summaries()` |
| POST | `/api/characters` | `create_new_character` | builds starter sheet, activates on session |
| GET | `/api/characters/current` | `get_active_character` | session-scoped |
| POST | `/api/characters/{campaign_id}/activate` | `activate_character` | sets session player from sheet |
| DELETE | `/api/characters/{campaign_id}` | `remove_character` | clears it from all sessions |
| POST | `/api/dm/interact` | `player_interact` | `StoryEngine.process_turn` → `GenerativeUIPackage` |
| POST | `/api/combat/attack` | `execute_combat_attack` | `d20_rules.resolve_attack`, no session state |
| GET | `/api/audio/sfx/{sound_name}` | `get_sfx` | `FileResponse` WAV from `audio_output/` |

FastAPI also auto-registers GET/HEAD `/docs`, `/redoc`, `/openapi.json`,
`/docs/oauth2-redirect`; the table lists only the declared routes.

Middleware/order: `CORSMiddleware` (`allow_origins=["*"]`, credentials, all
methods/headers) added at app construction; `StaticFiles` mount of
`client/dist` at `/` happens last, only if the directory exists.

Session model: `_sessions: dict[str, SessionState]` keyed by `X-Session-ID`
header (default `"default"`); `SessionState` holds one `StoryEngine` and one
`active_campaign_id`. `campaign_store = CampaignStore(data/campaigns.db)` is
module-level and shared across sessions. `sfx_cache` is generated once at
import via `generate_all_sfx(SFX_DIR)`.

## `game_server.py` routes (:8766; loopback by launch command)

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/status` | state + `X-Game-Token` + chronicle list |
| POST | `/api/campaigns` | `_check_write_token` when `Origin` present |
| GET | `/api/campaigns/{campaign_id}` | 404 on `NotFoundError` |
| POST | `/api/campaigns/{campaign_id}/actions` | revision-checked; `ConflictError` → 409 |
| POST | `/api/campaigns/{campaign_id}/reset` | back to start scene |

Mounts `web/` statically at `/` when the directory exists. DB:
`AI_DM_CAMPAIGN_DB` or `data/campaigns.db`. FastAPI auto-registers the same
`/docs`, `/redoc`, `/openapi.json`, `/docs/oauth2-redirect` GET/HEAD routes.
No CORS middleware (same-origin client); `_WRITE_TOKEN` is per-process random.

## `vr_server.py` routes (:8000 default)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/surface` | `CampaignVRState.snapshot()` blueprint |
| GET | `/api/state` | hero + journal + activeSurface |
| POST | `/api/intent` | `state.apply(intent, values)`; 64 KiB body cap |
| GET | `/xr`, `/xr/*` | static `web/xr/` files (html/js/json/css mime map, path-traversal safe); bare `/xr` serves the index |
| GET | `/sfx/{name}.wav` | only `dice_roll`, `crit_fanfare` |
| GET | `/health` | `OK` |
| OPTIONS | `*` | CORS `*` preflight |

`SUPPORTED_INTENTS`: `CONFIRM_CHARACTER_DRAFT`, `SWITCH_STARTER_ARCHETYPE`,
`choose`, `PHYSICAL_DICE_ROLL`, `SWITCH_VIEW`. `CHECKS` hardcodes one check
(`sunken_shrine`, Athletics DC 12); `ARCHETYPES` = Fighter/Wizard stat rows.
ThreadingHTTPServer, `daemon_threads`, `request_queue_size=64`.

## `engine/` module responsibilities

- `story_engine.py` (618 ln): `StoryEngine` turn loop, `PlayerCharacter`,
  Ollama probe (`/api/tags` at 1.5 s, `/api/generate` at a configurable
  timeout defaulting to 3 s) + procedural DM fallback, `process_turn` →
  `GenerativeUIPackage`.
- `world_generator.py` (235 ln): `WorldState`, `Faction`, `LocationNode`,
  `generate_procedural_world`.
- `generative_ui.py` (116 ln): package dataclasses — `GenerativeActionCard`,
  `GridCombatant`, `NPCPreset`, `LootItem`, `SoundtrackDirective`,
  `TacticalGridState`, `UIComponentType`, `ActionCategory`.
- `scene_visuals.py` (306 ln): `SceneIllustration` + `BIOME_VISUAL_THEMES` SVG
  renderer.
- `character_service.py` (45 ln): `create_character` / `get_current_character`
  / `delete_character` over `CampaignStore` + `build_starter_character`.
- `dm_tui.py` (110 ln): `run_tui` terminal cockpit.

## `campaign_core.py`

`CampaignStore(path)`: SQLite, `PRAGMA journal_mode=WAL`,
`PRAGMA foreign_keys=ON`, `isolation_level=None` (explicit `BEGIN IMMEDIATE`).
Tables: `campaigns(id TEXT PK, revision INTEGER, state TEXT JSON)` and
`requests(campaign_id, request_id, action, response, PK(campaign_id,
request_id))`. `commit()` is atomic + idempotent (replay returns stored
response; `ConflictError` on revision/fingerprint mismatch). `update_media()`
merges `state["media"][kind]` without bumping revision. Also `character_catalog()`
and `build_starter_character()` (SRD 5.2.1 presets, `PORTRAITS`).

## `campaign_service.py` + `campaign_mcp.py`

`CampaignService(store, game)`: executes the `mcp-games-game-definition/1`
export (`to_mcp_games_v1(STARTER_SCENARIO)`); deterministic — no LLM. State
shape returned to callers: `{id, revision, title, phase, stage, game, scene,
journal, character, media, presentation}` (`id`/`revision` added by
`CampaignStore.create`).
`campaign_mcp.py`: stdio JSON-RPC MCP server (`initialize`, `tools/list`,
`tools/call`) bridging to `game_server` :8766 via `CampaignClient`
(loopback-only URL validation, no credentials in URL).

## Root rule modules used by the API

`d20_rules.resolve_attack` (attack resolution), `audio_synth.generate_all_sfx`
/`default_audio_dir` (WAV cache), `game_foundation` adapters (vr_server scene
model). `combat_log`/`combat_events`/`combat_schema` are used by the CLI/TUI
paths, not the HTTP API.

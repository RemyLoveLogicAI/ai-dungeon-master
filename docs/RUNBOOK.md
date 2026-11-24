# Runbook

<!-- AUTO-GENERATED: regenerated from source; verify commands against CONTRIBUTING.md and code before relying on them -->

Operational notes for running, checking, and releasing `ai-dungeon-master`.
For the full command list see [CONTRIBUTING.md](../CONTRIBUTING.md#commands-reference).

## Local run

Runnable surfaces:

| Surface | Command | Notes |
| --- | --- | --- |
| Desktop launcher | `uv run dm-desktop` | Starts uvicorn on :8000 and opens a browser window. Flags: `--port`, `--tui` (terminal cockpit), `--no-window` (backend only). The frameless `--app=` window is only attempted on macOS Chrome/Brave/Edge/Chromium (`desktop_launcher.py`); otherwise it falls back to `webbrowser.open`. The served UI requires a built `client/dist` — the API mounts it at `/` only when present. |
| Terminal UI | `uv run dm-tui` or `uv run dungeon-master-tui` | `engine.dm_tui:run_tui` (in-process cockpit, no CLI flags) / `tui_runner:main` (standalone, supports `--log`/`--resume` encounter logs). |
| Web client + API | `uv run uvicorn engine.api_server:app --reload --port 8000` in one shell; `cd client && bun run dev` in another | Vite serves on :5173 and proxies `/api` and `/ws` to :8000 (`client/vite.config.ts`); `/ws` is a Vite proxy with no upstream WebSocket handler. Build once with `bun run build` and the API also mounts `client/dist` at `/` when it exists (`engine/api_server.py`). |
| VR/XR client | `uv run python -m vr_server --host 127.0.0.1 --port 8000` | Zero-dependency stdlib server; serves `web/xr/` at `/xr/`. Quest over USB: `adb reverse tcp:8000 tcp:8000`. |
| Campaign API (MCP backend) | `uv run uvicorn game_server:app --host 127.0.0.1 --port 8766` | Loopback by launch flag — the ASGI app itself has no bind restriction; backs `web/play.js` and the `campaign_mcp.py` stdio adapter. `game_server.py` ships in the wheel, but the `web/` static client and `client/dist` assets do not — run from a checkout for the full UI. |

## API surface (`engine/api_server.py`)

All routes under `/api`. Session isolation via the `X-Session-ID` header
(default session id `"default"`); each session owns one `StoryEngine` and one
active-campaign pointer, while `campaign_store` (SQLite) is shared.

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/api/health` | `get_health` |
| GET | `/api/world/current` | `get_world` |
| POST | `/api/world/generate` | `regenerate_world` |
| GET | `/api/scene/current` | `get_current_scene` |
| GET | `/api/scene/image/{location_name}` | `get_scene_image` (SVG, cached 1h) |
| GET | `/api/player` | `get_player` |
| GET | `/api/characters/catalog` | `get_character_catalog` |
| GET | `/api/characters` | `list_characters` |
| POST | `/api/characters` | `create_new_character` |
| GET | `/api/characters/current` | `get_active_character` |
| POST | `/api/characters/{campaign_id}/activate` | `activate_character` |
| DELETE | `/api/characters/{campaign_id}` | `remove_character` |
| POST | `/api/dm/interact` | `player_interact` |
| POST | `/api/combat/attack` | `execute_combat_attack` |
| GET | `/api/audio/sfx/{sound_name}` | `get_sfx` |

CORS: `CORSMiddleware` allows all origins (`*`) — needed for the Vite dev
server and mobile shells; do not expose this port beyond loopback without a
real auth layer.

FastAPI also auto-registers GET/HEAD `/docs`, `/redoc`, `/openapi.json`, and
`/docs/oauth2-redirect`; the table lists only the declared routes. The
`client/dist` mount at `/` is conditional on the directory existing.

`GET /api/health` returns `status`, `world_name`, `ollama_available`,
`available_models`, `tension_level`, `current_location`. Ollama is probed at
`http://127.0.0.1:11434` (`engine/story_engine.py`); when unavailable the
engine falls back to its procedural DM path.

## VR server (`vr_server.py`)

Stdlib `ThreadingHTTPServer`, binds `127.0.0.1:8000` by default; non-loopback
binds log a warning (mutable game, CORS `*`, no auth).

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/surface` | Current AgentSurface blueprint snapshot |
| GET | `/api/state` | Hero, journal, active surface type |
| POST | `/api/intent` | Apply an intent (`CONFIRM_CHARACTER_DRAFT`, `SWITCH_STARTER_ARCHETYPE`, `choose`, `PHYSICAL_DICE_ROLL`, `SWITCH_VIEW`); body ≤ 64 KiB |
| GET | `/xr`, `/xr/*` | XR web client (`web/xr/`, three.js via CDN importmap); bare `/xr` serves the index |
| GET | `/sfx/{name}.wav` | `dice_roll` / `crit_fanfare` only |
| GET | `/health` | `OK` text |
| OPTIONS | `*` | CORS `*` preflight (GET, POST, OPTIONS) |

## Campaign API (`game_server.py`)

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/status` | Provider state, per-process `X-Game-Token`, chronicle list |
| POST | `/api/campaigns` | Create a chronicle |
| GET | `/api/campaigns/{campaign_id}` | Fetch state |
| POST | `/api/campaigns/{campaign_id}/actions` | Submit one action (revision-checked) |
| POST | `/api/campaigns/{campaign_id}/reset` | Return to start scene |

Like `api_server`, FastAPI auto-registers GET/HEAD `/docs`, `/redoc`,
`/openapi.json`, `/docs/oauth2-redirect` here too; `web/` is mounted at `/`
when the directory exists.

Mutations carrying a browser `Origin` header must send `X-Game-Token`
(CSRF defense); non-browser clients without `Origin` are trusted. No CORS —
the client is served same-origin. DB path: `AI_DM_CAMPAIGN_DB` env or
`data/campaigns.db`. `campaign_mcp.py` is a stdio JSON-RPC MCP adapter over
this API (`CampaignClient`, loopback-only).

## Persistence

- **Campaigns**: `data/campaigns.db` SQLite via `campaign_core.CampaignStore` —
  tables `campaigns` (id, revision, JSON state) and `requests` (idempotent
  replay log). Atomic commits with optimistic revision checks; WAL mode.
- **Combat logs**: `combat-encounter-log/1` envelope written by
  `combat_log.save_log` — flushed temp sibling + atomic replace; a crash
  leaves the last complete checkpoint. `--resume` re-verifies the log by
  replay before continuing. See `docs/architecture.md` for the full contract.
- **SFX**: generated WAVs — `engine/api_server.py` writes `<repo>/audio_output`
  at import; `tui_runner`/`vr_server` use `default_audio_dir()`
  (`AI_DM_AUDIO_DIR` or XDG cache); `combat_runner` uses
  `<cwd>/audio_output`; `engine/dm_tui.py` generates none.

## Health checks

- `GET :8000/api/health` — engine + Ollama status (see keys above).
- `GET :8000/health` (vr_server) — `OK`.
- `GET :8766/api/status` — game server + token.
- CI gate locally: `uv run pytest -v`, `uv run ruff check .`, `uv run mypy`,
  `uv run pytest --cov --cov-report=json && uv run python coverage_gate.py`.

## Common issues

- **`SchemaUnavailableError`**: `combat_schema.validate_payload` /
  `--validate-schema` needs the optional extra — `uv sync --dev --extra schema`.
- **Coverage gate fails**: run `uv run pytest --cov --cov-report=json` first
  (`coverage_gate.py` refuses stale reports), then `uv run python coverage_gate.py`.
- **Port already in use**: api_server and vr_server each default to :8000 —
  only one can hold it at a time. `game_server` has no port default; :8766
  comes from the documented uvicorn launch flag, not the app.
- **Vite proxy errors**: confirm the FastAPI backend is on :8000; proxy targets
  are hardcoded in `client/vite.config.ts`.
- **Stale `web/demo-data.json`**: run `uv run python web/build_demo.py` and
  commit; `pages.yml` fails the build on drift.

## Release

- Trigger: push a `v*.*.*` tag → `.github/workflows/release.yml`.
- Gate: `python scripts/verify_release.py <tag>` fails closed unless the tag
  is stable SemVer matching `pyproject.toml` `[project].version`,
  `CHANGELOG.md` has a `## [X.Y.Z]` section, the version is the next
  minor/patch/major after the latest existing tag, every
  `docs/product/MVP-1.0-CHECKLIST.md` checkbox is checked with completed
  evidence (v1.0.0), and every version >= 1.1.0 has a verified
  `docs/product/FEATURE_LOG.md` row for that release.
- Pipeline: `uv sync --frozen --dev` → `uv run pytest` → `uv build` → wheel
  smoke test in a throwaway venv (all three console scripts + licence metadata
  + shipped schema file) → then two parallel jobs that both `needs: build`:
  `publish-pypi` (OIDC trusted publishing, `pypi` environment) and `release`
  (GitHub Release with `dist/*` attached). There is no TestPyPI stage.
- Docs site: `.github/workflows/pages.yml` rebuilds `web/` on pushes to `main`
  touching `web/**`, verifies `demo-data.json` is not stale, deploys to GitHub
  Pages.

## Rollback

- **PyPI**: yank the bad release in the PyPI project settings (trusted
  publishing means no token to rotate); individual files on an existing
  release can also be deleted there if a narrower remediation is needed.
- **GitHub Pages**: revert the `web/**` commit on `main`; `pages.yml`
  redeploys automatically.
- **Local checkout**: `git checkout <previous-tag>`; database and logs are
  local files unaffected by code rollback.

<!-- Generated: 2026-11-24 | Files scanned: 3 | Token estimate: ~600 -->
# Codemap: dependencies

## Python runtime (`pyproject.toml`)

| Dep | Constraint | Used by |
| --- | --- | --- |
| `fastapi` | >=0.143.0 | `engine/api_server.py`, `game_server.py` |
| `httpx` | >=0.28.1 | Declared; no first-party `.py` imports it — used indirectly via Starlette `TestClient` and external integrations |
| `pydantic` | >=2.14.1 | request models in both FastAPI apps |
| `uvicorn` | >=0.54.0 | ASGI server (`dm-desktop`, dev commands) |
| `websockets` | >=16.1.1 | Declared; no `@app.websocket` route exists — vite `/ws` proxy has no upstream |

Optional extra `schema`: `jsonschema>=4.18` — required by
`combat_schema.validate_payload` / `--validate-schema`; raises
`SchemaUnavailableError` when absent.

The rules core (d20_rules, combat_*, encounter_*, audio_synth, game_foundation,
genui, campaign_core, campaign_service, vr_server, tui_runner,
combat_runner) is **stdlib-only** by design — CONTRIBUTING requires keeping
it that way. `desktop_launcher.py` is the exception: it imports `uvicorn`
to launch the ASGI app.

Python `>=3.10`; classifiers advertise 3.10–3.14 (CI matrix).

## Dev group

`pytest>=8`, `pytest-cov>=6`, `hypothesis>=6`, `jsonschema>=4.18`,
`ruff>=0.14` (lint, line-length 100), `mypy>=1.11` (`[tool.mypy]` file list
backs the shipped `py.typed` marker).

## Client (`client/package.json`, bun)

Runtime: `react`/`react-dom` ^19.2.8, `@capacitor/core` ^8.5.3, `clsx`,
`lucide-react`, `tailwindcss` ^4.3.3 (+ `autoprefixer`, `postcss`).

Dev: `vite` ^8.3.0, `@vitejs/plugin-react` ^6.1.1, `@tailwindcss/vite`,
`typescript` ~6.0.2, `oxlint` ^1.81.0, `@types/*`, and Capacitor Android
(`@capacitor/android`, `@capacitor/cli` ^8.5.3). `bun.lock` committed; Tauri
shell config in `client/src-tauri/` (Tauri 2 schema, no JS deps listed there).

## External services / integrations

| Service | How reached | Failure mode |
| --- | --- | --- |
| Ollama (`http://127.0.0.1:11434`) | `engine/story_engine.py` probes `/api/tags` (1.5 s), generates via `/api/generate` (configurable timeout, default 3 s) | `ollama_available: false` → procedural DM fallback; surfaced in `/api/health` |
| GitHub Pages | `pages.yml` deploys `web/` on `main` pushes | n/a (CI) |
| PyPI | `release.yml` `publish-pypi` job — OIDC trusted publishing (`pypi` environment) on `v*.*.*` tags; `publish-pypi` and `release` both `needs: build` (TestPyPI stage removed in d0edbaf) | gated by `verify_release.py` |
| Android device | Capacitor; `web/xr` notes `adb reverse tcp:8000 tcp:8000` for Quest | manual step |
| jsDelivr CDN | `web/xr/index.html` importmap: `three@0.170.0`, `cannon-es@0.20.0` | XR client needs network for CDN |

## Not dependencies (deliberate absences)

- No DB driver beyond `sqlite3` stdlib.
- No web framework beyond FastAPI/uvicorn for services; `vr_server` is
  `http.server` only.
- No client-side state library (React `useState` only), no CSS framework
  beyond Tailwind, no test runner in `client/` (oxlint only).

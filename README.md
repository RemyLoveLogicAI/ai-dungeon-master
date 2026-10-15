# Aegis AI Dungeon Master

A dependency-free D20 game foundation, with an original branching-fantasy
starter scenario and explicit export adapters for two separate projects:

- **`d20_rules.py`** — D20 attack resolution: advantage/disadvantage, natural 1/20,
  critical damage, damage types, and injectable dice sources (module-random
  default, seeded, scripted, and recording).
- **`combat_events.py`** — replayable `combat-attack-event/1` records: each attack
  captures its request and die results, and replays to an identical resolution.
- **`combat_log.py`** — the versioned `combat-encounter-log/1` envelope: strict
  validation at the boundary, one-version-at-a-time migration, bounded retention,
  and size-guarded save/load.
- **`combat_schema.py`** — validation against
  `schemas/combat-encounter-log-1.schema.json`, a published JSON Schema any
  consumer can apply without this package. Needs the optional `jsonschema`
  extra, and fails loudly rather than skipping a requested check without it.
- **`encounter_ai.py`** — stance-based enemy combat AI whose turn choice is a
  pure query: a decision reports its slot cost and the caller commits it.
- **`audio_synth.py`** — procedural sound effects written directly to 16-bit WAV,
  drawn from a private generator so audio never perturbs a simulated roll.
- **`combat_runner.py`** — runnable combat demonstration that logs and replays
  each attack.
- **`game_foundation.py`** — domain-neutral scene/choice scenario model, an
  immutable in-memory session with an append-only choice-event log, the
  `mcp-games-game-definition/1` / `agentsurface-blueprint/0.1` adapters, and
  `validate_agentsurface_v01` — the one definition of the v0.1 contract.
- **`genui.py`** — declarative `SurfaceBlueprint` factory plus an ANSI terminal
  renderer (tactical grid, health meters, action-economy badges, intent buttons).
  Both it and the scenario adapter export the same validated v0.1 envelope.
- **`tui_runner.py`** — a runnable encounter that draws the generative terminal
  surface round by round, triggers procedural audio synthesis, commits every
  attack to a durable log, and can resume a saved encounter.
- **`web/`** — a dependency-free browser client that renders the *same* validated
  `agentsurface-blueprint/0.1` envelope the engine exports. It holds no game
  logic: it draws components and routes intents. `web/build_demo.py` generates
  its data from the real modules, and `test_web_demo.py` keeps that artifact in
  sync with the code.

The adapters produce JSON-compatible contract payloads; they do **not** connect
to remote repositories, start MCP servers, or call a model provider. A combat
log can be written to a local JSON file on request, but nothing schedules,
replicates, or deletes that data, and campaign/session persistence is not owned
here. The combat engine remains usable independently of the narrative
foundation. See [Architecture](docs/architecture.md),
[Integrations](docs/integrations.md), and the [roadmap](docs/roadmap.md).

## Try it

### In a browser (no install)

The client under `web/` renders the validated `agentsurface-blueprint/0.1`
envelope straight from the engine — the same contract the terminal surface
exports — and reimplements none of the rules: it draws components and routes
intents.

```bash
git clone https://github.com/RemyLoveLogicAI/ai-dungeon-master.git
cd ai-dungeon-master
python web/build_demo.py             # regenerate web/demo-data.json from the engine
python -m http.server 8765 --directory web
# open http://127.0.0.1:8765/
```

`#scene=<id>` and `#encounter` deep-link a specific surface. The page is static
and has no runtime dependency; `.github/workflows/pages.yml` publishes it to
GitHub Pages on a push to `main` (select **Settings → Pages → Source: GitHub
Actions** once). It is a disposable local client, not the production
AgentSurface renderer — see [Architecture](docs/architecture.md).

### From the command line

Run the combat demo and terminal client:

```bash
uv run python combat_runner.py
uv run dm-tui
```

## Multi-Surface Client Prototype

- `client/`: Vite/React browser UI, built for web and packaged as Capacitor Android and Tauri desktop shells.
- `engine/`: FastAPI prototype for story/session routes, procedural world data, and terminal output.
- `desktop_launcher.py`: starts the local API and desktop shell.

## ⚡ Generative Features

1. **Procedural World & Faction Engine (`engine/world_generator.py`)**:
   - Generates cosmology, epochs, Ley-fault cataclysms, faction ideologies, leaders, and influence ratings.
   - Generates an interactive 2D SVG Realm Atlas with interconnected biomes (Obsidian Crags, Sunken Crypts, Gargoyle Roost, Whispering Fen, Astral Observatory).
2. **Generative UI Engine (`engine/generative_ui.py`)**:
   - The AI DM does not just emit text—it synthesizes interactive UI components dynamically:
     - **Dynamic Action Decks**: Context-sensitive cards calibrated with DC targets, stat modifiers, and risk levels (Low, Medium, High, Lethal).
     - **Tactical Combat Matrix**: 8x8 spatial battle grid with hero/enemy tokens, HP gauges, range rings, and combat stances.
     - **Tactile D20 Fate Core**: Interactive 3D/pseudo-3D dice roller with tumbling physics, Advantage/Disadvantage modes, and critical success/fumble fanfares.
     - **NPC Dialogue Cards**: Dynamic portraits, mood meters, voice tones, and branching speech replies.
     - **Procedural Loot Drops**: Rarity-tiered items (Common to Mythic) with stats and equip actions.
3. **Procedural Music & SFX Synthesis**:
   - **Web Audio API Engine (`client/src/audio/procedural_synth.ts`)**: Generates real-time ambient soundscapes directly in the browser—subterranean drones, resonant lowpass filters, battle tension kicks, and melodic arpeggiated chimes. Zero external audio downloads needed.
   - **Procedural SFX Generators**: Synthesizes dice tumble clicks, metallic sword clashes, resonant fireballs, and triumphant fanfare chords.
   - **Python WAV Synthesizer (`audio_synth.py`)**: Produces 16-bit PCM WAV audio stems on the backend.
4. **Agentic DM Intelligence (`engine/story_engine.py`)**:
   - **Dual AI Core**: Automatic auto-detection for local **Ollama** models (`llama3.2:3b`, `qwen3:8b`, `freestream-qwen3-8b-4k`, `dolphin3:8b`), seamlessly paired with a robust offline heuristic procedural generator.

---

## 🚀 Quick Start

### 1. Launch All-in-One Desktop App
```bash
uv run python desktop_launcher.py
```
*Spawns the local FastAPI backend and automatically opens a dedicated, frameless desktop window.*

### 2. Launch Terminal TUI Cockpit
```bash
uv run dm-tui
# or
uv run python desktop_launcher.py --tui
```

### 3. Run Web Development Server
```bash
# Terminal 1: Backend API
uv run uvicorn engine.api_server:app --reload --port 8000

# Terminal 2: Web Client
cd client
bun run dev
```
Open [http://localhost:5173](http://localhost:5173).

### 4. Build & Run Android App
```bash
cd client
bun run build
bunx cap sync android
bunx cap open android  # Opens in Android Studio / Gradle
```

---
Make a run reproducible — pass a seeded dice source and every attack replays
from its recorded rolls:

```python
from combat_runner import run_simulated_encounter
from d20_rules import SeededDiceSource

run_simulated_encounter(dice=SeededDiceSource(7))
```

Record a single attack and replay it from the dice it consumed:

```python
from combat_log import record_entry
from d20_rules import AttackRequest, DamageType, SeededDiceSource

request = AttackRequest(
    attacker="Paladin Alden",
    target="Shadow Gargoyle",
    attack_modifier=5,
    target_ac=14,
    damage_dice_count=2,
    damage_die_sides=6,
    damage_modifier=3,
    damage_type=DamageType.SLASHING,
)

entry, resolution = record_entry(request, dice=SeededDiceSource(7))
print(entry.event.rolls)  # the dice behind the result
print(entry.replays())    # True: replays from the rolls alone
```

Persist an encounter as a versioned, validated envelope and read it back:

```python
from combat_log import CombatLog, load_log, save_log, trim_log, verify_log

log = CombatLog(entries=(entry,))
save_log(log, "encounter.json")       # durable, deterministic JSON
restored = load_log("encounter.json")  # strict validation on the way back in
print(verify_log(restored))           # True: the reloaded log still replays
print(trim_log(restored, 100).dropped)  # retention: entries dropped, if any
```

Records deliberately carry only the numbers and fictional names attached to an
attack: no prompts, player context, or executable content cross the boundary.

Validate that envelope against the published schema, with or without this
repository's code:

## 🧪 Testing

Run unit tests via `uv`:
```bash
# the artifact ships with the package, so a consumer can read it directly
python -c "import combat_schema; print(combat_schema.schema_path())"
```

```python
from combat_log import load_log

# the in-repo readers always run; this adds the published schema on top
log = load_log("encounter.json", validate_schema=True)
```

The schema check raises `combat_schema.SchemaUnavailableError` when the optional
`jsonschema` extra (`pip install 'ai-dungeon-master[schema]'`) is absent, so a
requested check is never reported as one that passed. The runners ask for a
validator before they start, so `--validate-schema` refuses with exit status 2
without printing a round or writing the log.

Run the generative terminal surface (TUI), save the encounter, and resume it:

```bash
python tui_runner.py
python tui_runner.py --log encounter.json                  # a durable run
python tui_runner.py --log encounter.json --resume         # continue it later
python tui_runner.py --log encounter.json --resume --validate-schema
```

The runner rewrites the envelope at the end of every round, so an interrupted
session resumes from the last completed one, and an existing log is never
replaced without `--resume` or `--overwrite`. A resume rebuilds hit points,
distance, the next round, and the enemy's remaining spell slots from the
recorded attacks. What the envelope does not carry is reported on screen rather
than guessed; see `RESUME_NOTES` in `tui_runner.py`.

Create and advance a story session from Python:

```python
from game_foundation import STARTER_SCENARIO, choose, start_session

session = start_session(STARTER_SCENARIO)
session = choose(session, STARTER_SCENARIO, "follow_the_bell")
print(session.current_scene)  # sunken_shrine
print(session.events)         # ordered choice_selected event(s)
```

Export the same scenario for the other projects:

```python
from game_foundation import (
    STARTER_SCENARIO,
    to_agentsurface_v01,
    to_mcp_games_v1,
)

game_definition = to_mcp_games_v1(STARTER_SCENARIO)
surface_blueprint = to_agentsurface_v01(STARTER_SCENARIO)
```

The D&D-facing examples are original, system-neutral fantasy content, not
reproductions of proprietary rulebooks. The `genui.py`/`tui_runner.py` terminal
surface is a local, disposable client, not the production renderer: the
ephemeral UI blueprint and its browser renderer remain owned by the separate
`agentsurface` project. The current combat implementation is not a complete
D&D 5e ruleset. See the SRD licensing boundary and provenance source in
[Architecture](docs/architecture.md).

## Development

```bash
uv sync --dev
uv run pytest -v
uv run ruff check .
uv run mypy
uv run pytest --cov --cov-report=json && uv run python coverage_gate.py
```

Run ruff linter & formatter:
```bash
uv run ruff check .
uv run ruff format --check .
```
The CI workflow runs Ruff and pytest on Python 3.10–3.14 with `--cov`, so the
total `fail_under` gate in `pyproject.toml` applies to a local
`uv run pytest --cov` too. That gate cannot see one module collapsing while the
others carry the average, so `coverage_gate.py` applies a floor per module on
top of it and refuses a report older than the code it describes. No runtime
dependencies are added by the foundation: `jsonschema` is a development and
optional-extra dependency, used only to validate logs against the published
schema.

## CI/CD

- **CI** ([ci.yml](.github/workflows/ci.yml)): the lockfile is checked against
  `pyproject.toml`, Ruff lints, pytest runs under the total coverage gate on
  every supported Python version, the per-module floors are enforced on one
  pinned interpreter, and a build job installs the wheel into a throwaway venv
  and runs both entry points.
- **Release** ([release.yml](.github/workflows/release.yml)): a version tag
  re-runs the tests, builds the package, smoke-tests the wheel the same way -
  both entry points, the shipped licence metadata, and the published schema
  resolving from the installed package - and only then publishes it.

[![CI](https://github.com/RemyLoveLogicAI/ai-dungeon-master/actions/workflows/ci.yml/badge.svg)](https://github.com/RemyLoveLogicAI/ai-dungeon-master/actions/workflows/ci.yml)

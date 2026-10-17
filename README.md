# Aegis AI Dungeon Master

[![Release](https://img.shields.io/github/v/release/RemyLoveLogicAI/ai-dungeon-master)](https://github.com/RemyLoveLogicAI/ai-dungeon-master/releases)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![License](https://img.shields.io/github/license/RemyLoveLogicAI/ai-dungeon-master)](LICENSE)
[![CI](https://github.com/RemyLoveLogicAI/ai-dungeon-master/actions/workflows/ci.yml/badge.svg)](https://github.com/RemyLoveLogicAI/ai-dungeon-master/actions/workflows/ci.yml)

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
- **`encounter_generator.py`** — seeded XP-budget encounter selection from caller-supplied
  creature candidates, with custom facets preserved in the `gpf/encounter.v1` payload.
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

**[Try it locally](#try-the-browser-demo)** · **[Install and run](#install-and-run)** ·
**[Source](https://github.com/RemyLoveLogicAI/ai-dungeon-master)**

A small, dependency-free Python foundation for deterministic D20 combat and
branching fantasy encounters. Simulate a fight, export a validated surface
blueprint, and hand it to an agent without giving the renderer executable game
logic.

## What is included

- Deterministic D20 combat with seeded and scripted dice sources.
- Replayable attack events and versioned, validated encounter logs.
- A domain-neutral branching-scene model with MCP Games and AgentSurface JSON
  exporters.
- A stance-based enemy AI, procedural audio, terminal encounter UI, and a static
  browser demo.

## Install and run

After the first PyPI release, run the packaged demo with `uvx` (Python 3.10+):

```bash
uvx ai-dungeon-master
```

## Try the browser demo

The intended public URL is [GitHub Pages](https://remylovelogicai.github.io/ai-dungeon-master/).
It currently returns 404 because Pages is not enabled for this repository.
Enable **Settings → Pages → Build and deployment → Source: GitHub Actions**,
then push to `main`. Until then, use the local prototype:

```bash
uv run python web/build_demo.py
uv run python -m http.server 8765 --directory web
# open http://127.0.0.1:8765/
```

`#scene=<id>` and `#encounter` open individual views. The browser client is an
experimental, local-only prototype; it renders a supported subset of the DSL
using safe text APIs and returns submitted intents as visible, copyable JSON
envelopes. It does not execute combat actions or provide a hosted gameplay
session.

## Experimental AgentSurface handoff

The Python exporters emit the AgentSurface DSL v0.1 blueprint. In an agent
workflow, the agent can pass that JSON to AgentSurface's `validate_blueprint`
and `render_surface` MCP tools. The HTML returned by the renderer is
self-contained and ephemeral; closing it discards the surface. Button intents
return as copyable envelopes for the agent to interpret. This repository adds
no AgentSurface MCP client, live transport, persistence, or production host.

The rest of the package remains usable independently: simulation, scenario
adapters, replayable combat events, validated logs, and terminal output run
locally without a model provider. See [Architecture](docs/architecture.md),
[Integrations](docs/integrations.md), and the [roadmap](docs/roadmap.md).

## From the command line

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

### Generate an XP-budget encounter

`encounter_generator.py` uses standard D&D 5e XP thresholds to select an
encounter from explicit caller-provided candidates. No creature catalog, D&D
Bible corpus, or loader is bundled. The official SRD 5.1 is an unstructured
PDF under CC BY 4.0; it does not verify the reported 949-record corpus or any
facet schema. Bible ingestion remains pending and unverified. Each candidate's
`facets` mapping is copied unchanged into the output under the `gpf/encounter.v1`
contract. See the [evidence record](docs/dnd-bible-facet-review-pack-2026-10-15.md)
for official sources, required attribution, and the distinction between
reported status and verified data.

```python
from encounter_generator import CreatureCandidate, Difficulty, generate_encounter

candidates = [
    CreatureCandidate(
        name="Goblin",
        xp=50,
        cr="1/4",
        facets={"biome": ["forest"], "tactics": {"preferred": "ambush"}},
    ),
    CreatureCandidate(
        name="Orc",
        xp=100,
        cr="1/2",
        facets={"biome": ["hills"], "alignment": "chaotic evil"},
    ),
]
encounter = generate_encounter(
    party=[3, 3, 3, 3],
    candidates=candidates,
    target_difficulty=Difficulty.MEDIUM,
    seed=123,
)
print(encounter["achieved_difficulty"], encounter["budget"])
```

Reusing the same inputs and seed returns the same encounter. The generator
validates levels, counts, candidate XP and difficulty labels. Its random search
is a heuristic: the target difficulty is not guaranteed when available
candidates cannot form a valid budget.

Run a **synthetic demo** through the turn loop ([`docs/CORE-GAME-LOOP-SPEC.md`](docs/CORE-GAME-LOOP-SPEC.md))
using the selection-only roster above. Demo statistics require explicit opt-in:

```python
from combat_runner import CombatantState, run_generated_encounter

party = [
    CombatantState(name="Alden", current_hp=38, max_hp=38, ac=16, attack_modifier=5)
]
result = run_generated_encounter(
    party, candidates, Difficulty.MEDIUM, seed=123, allow_fixture_defaults=True
)
print(result["outcome"], result["rounds"], result["xp_awarded"])
```

Combat execution is strict by default: each selected candidate's `facets` must
contain explicit normalized `hp`, `ac`, `attack_modifier`, `damage`, and `stance`.
Missing fields and unknown damage types raise errors instead of inventing combat
statistics. Candidate name, CR, and XP remain authoritative over facet metadata.
Unverified source-specific layouts such as `armor_class` / `hit_points` require
an explicit source adapter; compatibility with the remote Bible is not established.

Omit `allow_fixture_defaults` for explicit combat data. The same opt-in is
supported by `CombatantState.from_candidate`.
Fixture mode supplies demo defaults only for absent fields; it preserves provided
normalized values and does not repair malformed explicit damage blocks.
The selection seed does not seed combat dice; pass a `SeededDiceSource` as `dice`
when reproducible combat is needed. Initiative rolling, reward idempotency, and
external GPF event-schema conformance remain separate pending work.

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

`save_log` writes a unique sibling temporary file, flushes and syncs its contents,
then atomically replaces the checkpoint. A failure before replacement preserves
the previous checkpoint (or leaves no checkpoint on the first save), and errors
propagate to the caller. Temporary files are cleaned up on handled failures; a
hard kill or failed cleanup can leave an unused `.tmp` sibling. On POSIX, the
parent directory is synced where supported; Windows and filesystems that reject
directory syncing have no directory-durability guarantee. Power-loss durability
also depends on the filesystem/hardware and existing parent directories. A
directory-sync error can be raised after the new checkpoint is visible. Saves
replace the directory entry (including a symlink), use private temporary-file
permissions, and do not preserve the old file metadata. Concurrent writers are
not coordinated: the last replacement wins.

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

Audio defaults to `audio_output/` under the current working directory. Python
callers can pass `audio_dir=...` to `run_simulated_encounter` for a different
per-run destination.

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

The D20 examples use original, system-neutral fantasy content; this is not a
complete D&D 5e ruleset. The terminal UI is a local client. The `web/` page is a
separate local prototype, not the AgentSurface renderer or a hosted combat
service. See the SRD licensing boundary and provenance source in
[Architecture](docs/architecture.md).

## Development

### Test the generated encounter locally

From this repository, run the **auto-play prototype** with the existing Python
environment (no server, downloads, or remote Bible connection required):

```bash
.venv/bin/python combat_runner.py generated --difficulty medium --seed 7
```

Try `easy`, `medium`, `hard`, or `deadly`. The demo uses two level-3 heroes and
three original, explicitly populated demo templates, exercises the strict adapter
without fixture defaults, and prints every resolved attack plus final HP/outcome.
The same seed reproduces selection and combat. This is not yet an interactive
campaign; initiative is assigned and XP is reported rather than persisted.

Optional bounded run, JSON output, and replay-verified attack-log export:

```bash
.venv/bin/python combat_runner.py generated --difficulty hard --seed 42 --rounds 20
.venv/bin/python combat_runner.py generated --seed 7 --json
.venv/bin/python combat_runner.py generated --seed 7 --log /tmp/dnd-demo-attacks.json
```

Export uses the existing `combat-encounter-log/1` format, not an asserted external
GPF campaign contract. Existing no-argument script and installed demo entry points
retain their previous behavior.

### Validation

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
top of it and refuses a report older than the code it describes.
The simulation/export core remains stdlib-only. `jsonschema` is an optional
extra used only for published-schema checks.

Product requirements, feature-to-release traceability, the 1.0 MVP gate, and
release safeguards are documented in [docs/product](docs/product/README.md).

## CI/CD

- **CI** ([ci.yml](.github/workflows/ci.yml)): the lockfile is checked against
  `pyproject.toml`, Ruff lints, pytest runs under the total coverage gate on
  every supported Python version, the per-module floors are enforced on one
  pinned interpreter, and a build job installs the wheel into a throwaway venv
  and runs the documented `ai-dungeon-master` command plus the two legacy
  console entry points.
- **Release** ([release.yml](.github/workflows/release.yml)): a version tag
  builds and smoke-tests distributions once; the GitHub Release still receives
  those artifacts after the build, independently of PyPI availability. A
  separate OIDC chain publishes to TestPyPI, then PyPI only after TestPyPI
  succeeds. Configure PyPI trusted publishers for the `testpypi` and `pypi`
  environments before publishing.


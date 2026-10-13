# AI Dungeon Master

A dependency-free D20 game foundation, with an original branching-fantasy
starter scenario and explicit export adapters for two separate projects:

- **`d20_rules.py`** — D20 attack resolution: advantage/disadvantage, natural 1/20,
  critical damage, and damage types.
- **`encounter_ai.py`** — stance-based enemy combat AI.
- **`audio_synth.py`** — procedural sound effects written directly to 16-bit WAV.
- **`combat_runner.py`** — runnable combat demonstration.
- **`game_foundation.py`** — domain-neutral scene/choice scenario model, an
  immutable in-memory session with an append-only choice-event log, and the
  `mcp-games-game-definition/1` / `agentsurface-blueprint/0.1` adapters.

The adapters produce JSON-compatible contract payloads; they do **not** connect
to remote repositories, start MCP servers, call a model provider, or persist
sessions. The combat engine remains usable independently of the narrative
foundation. See [Architecture](docs/architecture.md),
[Integrations](docs/integrations.md), and the [roadmap](docs/roadmap.md).

## Try it

Run the combat demo:

```bash
python combat_runner.py
```

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
reproductions of proprietary rulebooks. The current combat implementation is
not a complete D&D 5e ruleset. See the SRD licensing boundary and provenance
source in [Architecture](docs/architecture.md).

## Development

```bash
uv sync --dev
uv run pytest -v
uv run ruff check .
```

The CI workflow runs Ruff and pytest on Python 3.10–3.14. No runtime
dependencies are added by the foundation.

## CI/CD

- **CI** ([ci.yml](.github/workflows/ci.yml)): Ruff lint + pytest across the
  supported Python versions.
- **Release** ([release.yml](.github/workflows/release.yml)): a version tag
  builds and publishes the Python package.

[![CI](https://github.com/RemyLoveLogicAI/ai-dungeon-master/actions/workflows/ci.yml/badge.svg)](https://github.com/RemyLoveLogicAI/ai-dungeon-master/actions/workflows/ci.yml)

# AI Dungeon Master

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
  surface round by round and triggers procedural audio synthesis.

The adapters produce JSON-compatible contract payloads; they do **not** connect
to remote repositories, start MCP servers, or call a model provider. A combat
log can be written to a local JSON file on request, but nothing schedules,
replicates, or deletes that data, and campaign/session persistence is not owned
here. The combat engine remains usable independently of the narrative
foundation. See [Architecture](docs/architecture.md),
[Integrations](docs/integrations.md), and the [roadmap](docs/roadmap.md).

## Try it

Run the combat demo:

```bash
python combat_runner.py
```

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

Run the generative terminal surface (TUI):

```bash
python tui_runner.py
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
```

The CI workflow runs Ruff and pytest on Python 3.10–3.14. No runtime
dependencies are added by the foundation.

## CI/CD

- **CI** ([ci.yml](.github/workflows/ci.yml)): Ruff lint + pytest across the
  supported Python versions.
- **Release** ([release.yml](.github/workflows/release.yml)): a version tag
  builds and publishes the Python package.

[![CI](https://github.com/RemyLoveLogicAI/ai-dungeon-master/actions/workflows/ci.yml/badge.svg)](https://github.com/RemyLoveLogicAI/ai-dungeon-master/actions/workflows/ci.yml)

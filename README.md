# AI Dungeon Master

A self-contained D20 tactical combat engine in pure stdlib Python — no dependencies.

- **`d20_rules.py`** — 5e-style attack resolution: advantage/disadvantage, natural 1/20, crit damage doubling
- **`encounter_ai.py`** — stance-based enemy AI (Aggressive / Tactical / Defensive / Fleeing) that reacts to HP, spell slots, and distance
- **`audio_synth.py`** — procedural sound effects (dice, sword clash, fireball, crit fanfare) written directly to 16-bit WAV
- **`combat_runner.py`** — a full simulated encounter tying it all together

## Run

```bash
python combat_runner.py
```

Or, after `uv sync`:

```bash
uv run dungeon-master
```

## Test

```bash
uv run pytest -v
```

## CI/CD

- **CI** ([ci.yml](.github/workflows/ci.yml)): ruff lint + pytest on Python 3.10–3.14 via [uv](https://docs.astral.sh/uv/)
- **Release** ([release.yml](.github/workflows/release.yml)): pushing a `v*.*.*` tag runs the tests, builds a wheel with `uv build`, and publishes a GitHub Release

[![CI](https://github.com/RemyLoveLogicAI/ai-dungeon-master/actions/workflows/ci.yml/badge.svg)](https://github.com/RemyLoveLogicAI/ai-dungeon-master/actions/workflows/ci.yml)

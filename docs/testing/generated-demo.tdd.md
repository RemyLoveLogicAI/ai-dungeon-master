# Runnable generated demo — evidence

## User target and boundary

The user requested a finished local test surface for the latest adapter.
The implementation adds a `generated` subcommand to the existing Python script;
it uses explicit original demo combatants and the strict adapter, not the missing
Bible or fixture-derived statistics. No-argument script behavior and installed
console entry points remain unchanged.

Launch from the repository:

```bash
.venv/bin/python combat_runner.py generated --difficulty medium --seed 7
```

## RED / GREEN

- RED checkpoint `3e9eec2`: `.venv/bin/python -m pytest -q test_generated_demo.py --tb=no`
  produced **13 failed** before the missing demo/CLI functions were implemented.
- `test_generated_demo.py` now covers all four difficulties, strict-data execution,
  deterministic full-combat results without global RNG mutation, legacy default,
  text/JSON output, exported attack-log replay, argument errors, file-write errors,
  failed replay reporting, and the actual script subprocess.
- Final full validation: **323 tests passed, 415 subtests passed; 97.65% coverage**.
  All 13 per-module floors, Ruff, mypy (13 files), JavaScript syntax, and diff
  whitespace checks passed. Commands:

```bash
.venv/bin/python -m pytest -q --cov --cov-report=json:/private/tmp/dnd-generated-demo-final-coverage.json
.venv/bin/python coverage_gate.py /private/tmp/dnd-generated-demo-final-coverage.json
.venv/bin/ruff check .
.venv/bin/mypy
node --check web/app.js
git diff --check
```

## Manual execution

Real script runs with seed 7:

| Difficulty | Outcome | Rounds | Attack events |
| --- | --- | --- | --- |
| easy | victory | 2 | 5 |
| medium | victory | 7 | 24 |
| hard | victory | 9 | 33 |
| deadly | victory | 6 | 19 |

Two JSON executions for each difficulty were byte-identical. The medium run saved
`/private/tmp/dnd-demo-attacks.json`, which was reloaded and replay-verified using
the existing `combat-encounter-log/1` reader. Difficulty describes budget, not a
guaranteed battle outcome or ordered number of rounds.

Independent review found no substantive correctness issue and identified one
Ruff context-manager formatting issue, which was fixed before the final gates.

## Limits

This is auto-play, not player-controlled combat or a full campaign. Initiative is
assigned, XP is reported (not persisted), and external GPF event-schema/Bible
integration remains pending. Log export proves attack replay, not full campaign
checkpoint/resume. The demo seeds combat explicitly without changing the existing
general wrapper's separate seed/dice API.

Validation ran locally on Python 3.14. `pip-audit` was attempted and is unavailable;
no dependencies were installed. No source services, external state, pushes,
merges, or new CI runs were involved.

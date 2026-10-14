---
name: Bug report
about: Something behaves incorrectly
title: "[bug] "
labels: bug
---

<!-- Before filing: does this reproduce on a clean `uv sync --dev` checkout? -->

## What happened

<!-- The actual behaviour. -->

## What you expected

<!-- The behaviour you expected instead. -->

## Reproduction

<!-- Smallest sequence that shows it. Prefer a seeded source so it is repeatable:
     `SeededDiceSource(7)` or a `ScriptedDiceSource(...)`. -->

```bash

```

```python

```

## Environment

- Commit or version:
- Python version:
- `uv run pytest -v` passes on `main`? yes / no

## Evidence

<!-- If this is about the encounter log, include the log (or the failing entry).
     A log that does not replay is itself the bug. -->

## Checklist

- [ ] I am not reporting a security vulnerability here (see
      [SECURITY.md](../../SECURITY.md) for the private channel).
- [ ] I included a minimal reproduction, not just a description.

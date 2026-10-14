## What changed

<!-- One or two sentences. What is different, and why. -->

## Why

<!-- The problem this solves. Link an issue or a backlog ticket if there is one. -->

## How it was verified

<!-- What you actually ran. "CI will catch it" is not verification. -->

- [ ] `uv run ruff check .`
- [ ] `uv run pytest -v`
- [ ] `uv run pytest --cov` (meets the 92% gate), if coverage could move
- [ ] The installed wheel still runs both entry points, if packaging changed

## Checklist

- [ ] The core stays dependency-free (no new runtime dependency without a
      stated reason it cannot use stdlib).
- [ ] New stochastic paths thread the injectable `DiceSource` rather than
      calling `random` directly.
- [ ] A changed export mapping is introduced under a new adapter contract
      identifier, not by mutating a published one.
- [ ] A bug fix includes a test that fails without the fix.
- [ ] Docs and the description describe what the code does; anything not
      implemented is marked out of scope rather than implied to exist.

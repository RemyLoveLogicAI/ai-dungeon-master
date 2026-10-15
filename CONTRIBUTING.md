# Contributing

Thanks for looking. This is a small, deliberately dependency-free Python core, so
the fastest way to contribute is to keep changes small, tested, and reversible.

## Development setup

```bash
uv sync --dev
uv run pytest -v
uv run ruff check .
uv run mypy
uv run pytest --cov --cov-report=json && uv run python coverage_gate.py
```

`uv run pytest --cov` applies the total `fail_under` gate configured in
`pyproject.toml` (96), so a local coverage run matches CI. That gate guards the
project total only: a single module can collapse while the others carry the
average, so `coverage_gate.py` layers a floor per module on top of it and fails
if any one module regresses. Run the two together as shown above. It also
refuses a report older than the code it describes rather than reporting a
result it cannot support. `uv run mypy` checks the shipped modules against the
`[tool.mypy]` file list, which is what backs the `py.typed` marker the package
ships.

The optional schema check needs its extra:

```bash
uv sync --dev --extra schema
```

## What CI checks

Every push runs `ci.yml`: the lockfile is verified against `pyproject.toml`,
Ruff lints, pytest runs under the total coverage gate on Python 3.10–3.14, the
per-module floors are enforced on Python 3.12, and a build job installs the
wheel into a throwaway virtualenv and runs both console entry points
(`dungeon-master`, `dungeon-master-tui`). A change that only passes locally but
breaks the installed wheel is still a failing change.

Run the same commands CI does before you open a pull request (ruff, mypy,
pytest, and `node --check web/app.js` if you touched the browser client).

## Expectations of a change

- **Keep the core dependency-free.** Add a third-party runtime dependency only
  for a capability that genuinely cannot use the standard library. `jsonschema`
  is the one optional extra, and it stays optional.
- **Fail closed at a boundary.** A wrong type raises `TypeError`; a wrong value
  raises `ValueError`. Never report a requested check as one that passed when
  you could not perform it — raise instead.
- **Prefer determinism.** Thread the injectable `DiceSource` through any new
  stochastic path rather than calling `random` directly, and keep audio and
  simulation on separate generators.
- **Version a contract before you change it.** A changed export mapping goes
  under a new adapter contract identifier; never mutate a published one.
- **Add a test that fails without the fix.** A bug fix needs a test that
  reproduces the bug, not just a test that passes after it.
- **Never lower a coverage floor.** Raise a module's floor when it improves;
  lowering one to make a change pass removes the guarantee the gate exists to
  provide. A new module needs an entry in `FLOORS`, and the gate fails until it
  has one.
- **Do not over-claim.** Docs and commit messages should describe what the code
  actually does. Anything not implemented — MCP runtime, model calls, campaign
  persistence, a browser renderer — is listed as out of scope, and stays that
  way until it is real.

## Running the demos

```bash
uv run python combat_runner.py
uv run python tui_runner.py --log encounter.json --resume
```

## Content and licensing

- The included scenario is original, system-neutral fantasy content. Do not add
  copied rulebook passages, setting text, protected names, or art.
- If you add D&D rules content, use only material whose licence you have
  verified, preserve required attribution, and keep licensed source data
  distinguishable from the engine code and the original scenario text.

## Commit messages

Use Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `ci:`, `chore:`).
Explain why in the body when the subject alone is not enough.

## Reporting a problem

Open an issue with the command you ran, what you expected, and what happened. For
a security concern, follow [SECURITY.md](SECURITY.md) instead of opening a public
issue.

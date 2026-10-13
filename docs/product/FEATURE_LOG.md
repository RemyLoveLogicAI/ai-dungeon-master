# Feature and release log

This is the human-readable traceability index from product requirement to
verified release. Update the matching row in the same PR that changes the
feature. A merged PR is not a shipped feature until acceptance is verified and
a versioned release is created.

| Feature | PRD / issue | PR | Status | Version | Release |
| --- | --- | --- | --- | --- | --- |
| Initial D20 combat engine and procedural audio demo | Pre-PRD baseline | N/A (historical baseline) | Historical baseline; MVP not verified | 0.1.0 | [v0.1.0](https://github.com/RemyLoveLogicAI/ai-dungeon-master/releases/tag/v0.1.0) |
| Scenario foundation and cross-repository export adapters | [PR #2](https://github.com/RemyLoveLogicAI/ai-dungeon-master/pull/2); no PRD existed before this lifecycle | [#2](https://github.com/RemyLoveLogicAI/ai-dungeon-master/pull/2) | Merged; adapter tests verified; does not satisfy 1.0 MVP gate | 0.1.0 | Not separately released |
| PRD-to-release traceability and verified MVP release gate | [#3](https://github.com/RemyLoveLogicAI/ai-dungeon-master/issues/3) | [#4](https://github.com/RemyLoveLogicAI/ai-dungeon-master/pull/4) | Process and validation tests verified; not a package release | No version bump | N/A |

## Release checklist

- [ ] All included PRD acceptance criteria are verified against the release build.
- [ ] `pyproject.toml` version, Git tag, and `CHANGELOG.md` heading match.
- [ ] `uv run pytest -q`, `uv run ruff check .`, and `uv build` pass.
- [ ] Generated artifacts were inspected and are attached to the GitHub Release.
- [ ] Feature log rows link the PRD, PR, version, and release.
- [ ] No npm publication is configured for this Python-only package.

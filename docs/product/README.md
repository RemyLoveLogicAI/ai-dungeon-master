# Product and release lifecycle

## MVP and version policy

The current package version is not a declaration that the generative D&D MVP
is complete. **Version 1.0.0 is reserved for the verified end-to-end MVP**, and
must not be tagged until every applicable gate below is demonstrated in the
release candidate:

- A player can complete a coherent, branching session with persistent campaign
  ownership kept in MCP Games.
- The reference slice includes a meaningful character, environment, event,
  challenge, and encounter; the game engine remains authoritative for rules.
- A chosen encounter produces validated state transitions and replayable
  results; randomness can be seeded or injected for reproducible tests.
- The MCP Games payload passes its upstream schema and a local integration test.
- The AgentSurface blueprint passes its upstream validator and a rendered UI
  check, including a clear no-selection/invalid-intent path.
- Accessible non-audio/non-visual cues, content provenance, and failure
  behavior are documented and tested.
- CI, package build, install/run instructions, and release artifacts are
  verified from a clean checkout.

The checkboxes and evidence index in
[`MVP-1.0-CHECKLIST.md`](MVP-1.0-CHECKLIST.md) are the release gate for
`v1.0.0`; the tagged release workflow fails closed until the checklist is
complete.

After 1.0.0 is actually verified, each independently shipped feature advances
the minor version by one point (1.1.0, 1.2.0, ...). Bug fixes that do not add
user-facing functionality advance the patch component (for example 1.1.1).
Breaking public-contract changes require an explicit migration plan and a major
version change. The Python package version in `pyproject.toml`, the `vX.Y.Z`
Git tag, and the `CHANGELOG.md` release heading must match exactly.

This is SemVer expressed with all three components; "one point per feature"
means one minor increment per feature release, not one version bump per commit.
Do not bump or publish while a PR is still under review.

## Feature traceability

1. Create a Feature PRD issue with the GitHub issue form (or copy
   `PRD-TEMPLATE.md` into a PRD record). Acceptance criteria must be observable
   and testable.
2. Implement on a branch linked to the PRD issue. The PR description links the
   PRD and checks off verified criteria.
3. Update `[Unreleased]` in `CHANGELOG.md` and the status/version fields in
   `FEATURE_LOG.md` in the same PR. Before merge, a feature stays **Proposed**
   or **In progress**; do not claim a release version.
4. Run CI, review, and compatibility checks. A feature becomes **Verified**
   only when its criteria pass; merge alone is not verification.
5. When intentionally preparing a release, set the package version, move
   verified entries into a dated changelog section, update the feature log with
   the release version/date, and create the matching `vX.Y.Z` tag.
6. The tag workflow tests and builds artifacts and creates a GitHub Release.
   This repository is Python-only: it must not publish a duplicate npm package.
   A future TypeScript contract or adapter package can publish to npm from its
   own owning repository using npm Trusted Publishing/OIDC and explicit
   release intent.

PRD, PR, feature log, changelog, and release link form the traceability chain.
Bug/security/maintenance work can link its issue without inventing a feature
PRD; explain that exception in the PR.

## Distribution safeguards

- Pull requests never publish packages or create releases.
- A release requires an explicit version/tag change and a matching
  `pyproject.toml` version and changelog heading.
- CI uses read-only permissions by default; release write access is scoped to
  the release job.
- Do not add registry credentials to source or publish a package to npm merely
  to satisfy a cross-project default. Use the ecosystem-native package format.
- Preserve source/license attribution and content provenance in distributable
  assets.

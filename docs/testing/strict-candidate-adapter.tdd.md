# Strict candidate adapter — TDD evidence

## Scope and user journeys

Derived from the reviewed `a666d37` adapter and the user's instruction to proceed:

- A caller with incomplete or unsupported source records gets an actionable error,
  not combat statistics inferred from XP/CR.
- A caller supplying normalized combat facets retains those values unchanged;
  candidate identity, CR, and XP override conflicting facet metadata.
- A demo caller can explicitly request synthetic fixture defaults. That mode
  cannot overwrite supplied canonical values or repair malformed explicit data.
- Generated encounters enforce the same boundary before mutating party HP.

Implementation is limited to `combat_runner.py`, regression tests, README usage,
and this evidence record. No dependencies, source corpus, runtime services, or
external contracts were changed.

## RED / GREEN evidence

- RED checkpoint: `720b95c` (`test: capture adapter stat-fabrication regressions`).
  Command: `.venv/bin/python -m pytest -q test_combat_rules.py -k 'candidate or fixture_defaults or generated_encounter' --tb=no`.
  Result before implementation: **23 failed, 6 passed** (including subtest failures).
  Failures proved silent source-stat synthesis and missing explicit opt-in APIs.
- Additional RED probes rejected neither truthy non-boolean flags nor malformed
  explicit integers/stances: **23 failing subtests** before adding their guards.
- GREEN command: `.venv/bin/python -m pytest -q test_combat_rules.py -k 'candidate or fixture_defaults or fixture_opt_in or generated_encounter'`.
  Final targeted coverage is included in the full-suite result below.

## Guarantees exercised

All tests are in `test_combat_rules.py::TestCoreGameLoopAndAdapter`.

| Guarantee | Test | Type |
| --- | --- | --- |
| Missing canonical combat fields fail instead of receiving generated stats | `test_candidate_requires_combat_facets_by_default`, `test_candidate_requires_each_normalized_combat_field` | Unit |
| Unverified `armor_class` / `hit_points` layouts are not guessed | `test_candidate_does_not_guess_unsupported_source_layout` | Unit |
| Valid explicit stats, abilities, and source input survive adaptation unchanged | `test_candidate_preserves_explicit_combat_values_without_mutation` | Unit |
| Name, XP and CR metadata are required/validated; encounter identity wins over facet identity | `test_candidate_rejects_missing_or_invalid_metadata`, `test_from_candidate_precedence_over_facets` | Unit |
| Unknown damage types, malformed integers and invalid stances are rejected | `test_candidate_rejects_unknown_damage_type`, `test_candidate_does_not_coerce_malformed_explicit_stats` | Unit |
| Fixture synthesis is explicitly enabled by a boolean, preserves supplied values, and does not repair malformed damage | `test_fixture_opt_in_requires_a_boolean`, `test_fixture_defaults_preserve_supplied_state_block`, `test_fixture_defaults_do_not_repair_malformed_explicit_damage` | Unit |
| Strict execution rejects incomplete selected candidates before combat changes HP | `test_generated_encounter_rejects_incomplete_candidates_before_combat` | Integration |
| Complete candidates execute without opt-in; synthetic fixtures execute only with opt-in | `test_generated_encounter_accepts_explicit_combat_facets`, `test_run_generated_encounter_e2e` | End-to-end engine |

## Final verification

- `.venv/bin/python -m pytest -q --cov --cov-report=json:/private/tmp/dnd-strict-adapter-final-coverage.json`:
  **308 passed, 415 subtests passed; 97.50% coverage** (96% required).
- `.venv/bin/python coverage_gate.py /private/tmp/dnd-strict-adapter-final-coverage.json`:
  **all 13 module floors met**.
- `.venv/bin/ruff check .`: **all checks passed**.
- `.venv/bin/mypy`: **no issues in 13 source files**.
- `node --check web/app.js` and `git diff --check`: **passed**.
- Manual smoke: incomplete Goblin rejected; explicit HP 7 / AC 15 / piercing
  preserved; opt-in fixture encounter completed with a seeded dice source.

## Limits and follow-up

- Verification used the existing local Python 3.14 environment; no new CI run or
  remote push was performed for this change.
- `pip-audit` was attempted but is not installed (`No module named pip_audit`).
  No audit pass is claimed and no tooling/dependencies were installed.
- `from_state_block` remains the pre-existing compatibility reader. The stricter
  candidate checks do not claim a comprehensive redesign of that reader.
- Remote Bible schema/data compatibility remains unverified. No inferred source
  adapter or replacement corpus was introduced.
- Initiative rolling, repeated reward handling, explicit party levels,
  end-to-end seeding, and GPF event-schema conformance are out of this fix's scope.
- If local TDD commits are later squashed, retain this RED/GREEN summary in the
  final change record. This file does not authorize a push or merge.

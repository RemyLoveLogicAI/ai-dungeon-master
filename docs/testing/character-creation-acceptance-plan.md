# Character Creation — Acceptance Test Plan

Written ahead of the Lin (backend) / Pixel (frontend) character-creation work landing,
so review can happen against a plan instead of being improvised after the fact.

## Baseline (confirmed before any new code lands)

- Repo: `/Users/lovelogic/ai-dungeon-master`, branch `production-web-demo` (== `main`, commit `a03efeb`). Working tree clean — neither Lin's nor Pixel's attempted runs left committed or uncommitted changes.
- Regression baseline run now, for later diff: `test_determinism.py test_tui_resume.py test_combat_log.py test_combat_schema.py test_combat_rules.py test_web_demo.py` → **228 passed, 430 subtests passed, 0 failed** (via `.venv/bin/python -m pytest`).
- **Correction to the task brief:** the brief states there is "zero character-creation code anywhere in the repo." That's true for the *live* path (engine/story_engine.py, generative_ui.py, combat_runner.py, game_foundation.py all still hardcode `"Paladin Alden"`), but `campaign_core.py` already has a working, tested, data-driven character builder: `character_catalog()` and `build_starter_character()` — 4 classes (Fighter/Rogue/Wizard/Cleric), Human only, level 1, full ability scores/skills/spells/equipment/save DCs. It's covered by `test_campaign_core.py` (23 tests, all passing) but is **not wired to any API endpoint** and **not called by** `story_engine.py` / `game_foundation.py` / `combat_runner.py` — it's orphaned logic from an earlier pass (commit `d482d3a`).
  - **Implication for Lin:** wire up and extend this existing model rather than designing a second one from scratch — avoids two divergent character schemas.
  - **Implication for Pixel:** Pixel's run said it would build "the minimal additive data model + endpoints myself" since Lin hadn't delivered a contract yet. If that work landed, it needs reconciling against `campaign_core.py`'s existing model before anything ships — two competing character data shapes is the single biggest risk on this task right now. Confirmed via `git status`/`git log` that nothing from either run has landed yet, so this is a heads-up, not yet a conflict.
- `/api/player` (GET) exists today and presumably serves the hardcoded character; no `create-character` or `get-current-character` endpoints exist yet.

## Acceptance Criteria

### 1. New-player creation flow
- A brand-new player (no saved character) is routed into the creation wizard, not straight into the game.
- Creating at least 3 distinct builds (different class/background/ability-score combos, using `campaign_core.py`'s existing Fighter/Rogue/Wizard/Cleric presets as the minimum matrix) must produce **mechanically different** characters, not just a different name/portrait:
  - Different starting HP, AC, saving throws, skill modifiers, proficiencies, starting equipment, and (for Wizard/Cleric) spell lists.
  - These differences must be visible in actual gameplay, not just in the sheet: e.g. a Wizard's spell options appear in `process_turn`/combat options where a Fighter's don't; AC/HP differences actually affect combat math (d20_rules.py / combat_schema.py stay untouched per scope, so this is a wiring check, not a combat-math check).
- Validation at the boundary: name length, concept length, and unsupported class/species/level values are rejected with clear errors (already covered for the backend function in `test_campaign_core.py`; needs equivalent coverage at the API layer and in the UI wizard).
- Finishing the wizard hands off into the game with the created character active everywhere the old hardcoded default used to appear (HUD, combat, narrative, generative UI).

### 2. Persistence across turns/session
- Character state created in the wizard survives: a turn change, a combat encounter, an app restart (same player/session), and a page/app reload (web + Tauri desktop).
- Two different players/sessions on the same machine don't clobber each other's character (per-player/session persistence, not a single global slot — check this explicitly, it's an easy thing to get wrong when replacing a single hardcoded global).

### 3. Returning-player flow
- A player with an existing saved character lands on a "continue" path, not the creation wizard, and loads the correct character (not the default).
- "Continue" into an in-progress combat/encounter resumes correctly with the real character's HP/resources, not a freshly reset sheet.

### 4. Regression coverage (existing tests referencing the hardcoded character)
Files: `test_determinism.py`, `test_tui_resume.py`, `test_combat_log.py`, `test_combat_schema.py`, `test_combat_rules.py`, `test_web_demo.py`, plus `combat_runner.py`'s own hardcoded `"Alden"` fixture at line 711 and `test_campaign_core.py`.
- Baseline is 228 passed / 430 subtests passed (see above) — re-run after Lin/Pixel's changes land and diff against this. Any new failure here is a regression, not a flaky test, until proven otherwise.
- These tests currently assume a fixed named character; once creation is wired in, decide explicitly (don't let it happen by accident) whether they should: (a) keep using a fixed test fixture character unaffected by the new creation flow, or (b) be updated to construct their character via the new API/model. Flag this as a design decision for Lin/Ada, not something QA should silently paper over.
- `d20_rules.py` / `combat_schema.py` are out of scope and should show zero diff.

### 5. Runtime verification (per repo's CLAUDE.md)
- `cargo tauri dev` must actually be launched and the full new→create→play and returning→continue→play paths exercised in the live webview, not just unit-tested with mocked IPC/DOM. This applies to Pixel's UI work specifically.

## Repo hygiene flag — raised to the team, not acted on

Stale worktrees: `.worktrees/ci-gates`, `.worktrees/feat-generative-dm-platform`, `.worktrees/integration-main`, plus external worktrees found at `/private/tmp/ai-dm-feat-pr`, `~/.local/share/kilo/worktree-pool/...`, `~/GitHub/copilot-worktrees/...` (two), `~/orca/workspaces/ai-dungeon-master/trout`.
Stale branches: `feat/generative-dm-platform`, `feat/generative-dm-platform-pr`, `fix/ci-gates`, `trout`, `remylovelogicai-finish-requested-changes`.
None contain character-creation work. Recommend cleanup once the team confirms nothing in them is still wanted — not deleting anything without that confirmation.

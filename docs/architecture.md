# Architecture and foundation

## Product direction

This repository is the **D&D simulation and sensory reference vertical slice**
for a broader generative game platform—not the owner of every campaign
capability. The long-term platform can combine story, characters, places,
challenges, events, mechanics, audio/media, and adaptive presentation. The
intended ownership boundary is:

- **`ai-dungeon-master`** owns rules, deterministic simulation contracts, and
  sensory primitives (such as the existing procedural WAV sound effects).
- **`mcp-games-monorepo`** owns narrative/campaign orchestration, player context,
  and durable campaign/session persistence.
- **`agentsurface`** owns the ephemeral declarative UI blueprint and renderer.

The repos remain independent. `game_foundation.py` includes a small scenario
and in-memory transition model only as an example/reference for the portable
contracts; it is not a second campaign database or production persistence layer.

## Current layers

```text
MCP Games (target owner)
  campaign/story/context/persistence
        │ game state + encounter commands
        ▼
ai-dungeon-master (this repo)
  D20 rules + combat AI + simulation result/events + procedural sound cues
        │ result/state for presentation
        ▼
AgentSurface (target owner)
  ephemeral AgentSurface v0.1 blueprint + renderer

game_foundation.py in this repo
  small reference Scenario → Scene/Choice graph
  in-memory GameSession → current scene + immutable ordered GameEvent records
  explicit export adapters for contract/schema handoff only
```

The reference scenario graph is validated at construction: ids are present and
unique, the start scene exists, every scene is reachable, and every choice
target resolves. A reference session transition validates that the chosen
option belongs to its current scene and scenario; then it returns a new session
with a sequential `choice_selected` event. No mutable shared session state,
canonical campaign ownership, or persistence format is implied.

The adapters are intentionally one-way and deterministic. MCP Games v1 maps
the example scenes and choices to the repository's `GameDefinition` shape.
AgentSurface v0.1 maps the example's start scene into a flat, reachable
component adjacency list and whitelists a `choose` intent. The blueprint uses a
selection field for a choice id and leaves intent handling to the embedding
host. These exporters are contract fixtures, not the production route for
campaign actions or turn resolution.

## Current implementation vs. target

Present in this worktree: D20 attack-resolution functions, stance-based
encounter AI, a command-line combat demonstration, procedural WAV sound effects,
the small session/scenario/export foundation, and a local presentation layer
(`genui.py` + `tui_runner.py`) that renders an ANSI terminal surface, and a
static browser client (`web/`) that renders the exported envelope. Both emit the
same declarative `SurfaceBlueprint` contract. No full rules expansion, ambient
audio engine, MCP server/tools, Tauri, or Android artifact is part of this
worktree: the browser client is a *renderer over the exported contract*, not a
second implementation of the rules.

## Deterministic simulation boundary

Rolls are injectable. `d20_rules.DiceSource` is a protocol with four
implementations: `ModuleRandomDiceSource` (the default, which delegates to the
shared `random` module and preserves historical behavior),
`SeededDiceSource` (a private `random.Random(seed)` stream that never disturbs
global state), `ScriptedDiceSource` (a fixed sequence), and
`RecordingDiceSource` (wraps another source and records every result).
`roll_dice`, `roll_d20`, `resolve_saving_throw`, `resolve_rest`, and
`resolve_attack` take an optional `dice` argument, so a caller opts into
reproducibility without changing the default.

`AttackRequest` is the complete input to one attack: it holds every parameter
except the dice, so a request plus a recorded roll sequence fully determines the
result. `resolve_attack` keeps its original signature and delegates to
`resolve_attack_request`. `combat_events.py` records an attack as a
`combat-attack-event/1` event plus the `combat-attack-result/1` result it
produced (`record_attack`), and re-derives the resolution from the recorded
rolls alone (`replay_attack`, `is_replayable`). Leftover recorded dice are
rejected, so a record cannot carry results the attack never spent.

`combat_log.py` wraps those pairs in the versioned `combat-encounter-log/1`
envelope and owns the three boundaries the in-memory records cannot:

- **Validation.** Loading is strict and fails closed. A wrong type raises
  `TypeError`, a wrong value raises `ValueError`, unknown enum members and die
  results illegal for their die are refused, and `bool` is never accepted where
  an integer belongs. Payloads are bounded by entry count and byte size.
- **Migration.** `migrate_log` upgrades an older envelope one version at a time
  through a supplied migration table, requiring each step to advance exactly one
  version. A version *newer* than the reader's is refused rather than guessed,
  and an older version with no registered migration is refused rather than
  silently misread.
- **Retention.** `trim_log` keeps only the most recent entries and records how
  many were dropped, so a log cannot grow without bound. A trimmed log keeps its
  original sequence numbers and stays verifiable, and the `dropped` count plus
  the retained tail form a checkable invariant.

`combat_runner.run_simulated_encounter` accepts a dice source and an optional
log path: it verifies that every logged event replays identically, and when
asked to save, re-loads the file through the strict boundary and verifies it
again. Verifying a *reloaded* log is the real test: the resolution is a pure
function of the request and the recorded rolls, and the stored result must match
what a fresh replay produces, so tampering and corruption are both detectable.

`tui_runner.py` carries the same envelope into an interactive session. Every
attack it resolves is committed with `record_entry`, and the log is rewritten at
the end of each round, so a run that stops - a crash, a closed terminal - is
resumable from the last successfully saved round. `save_log` writes a temporary
sibling, flushes and syncs its contents, closes it, then atomically replaces the
checkpoint. Symlink paths are resolved first: the temporary file is a sibling
of the resolved target, and replacement preserves the link itself. Callers must
not concurrently retarget symlinks or directories during a save. The returned
path remains the caller-supplied path. A write, flush, sync, or replacement
failure leaves the previous checkpoint intact; handled failures clean up the
temporary file. An abruptly
killed process may leave an unused temporary sibling. This protects against
interrupted saves, not power loss: parent directories are not synced. Saves do
not coordinate concurrent writers (the last replacement wins). `--resume` reads
the file back through the strict boundary, refuses a log that does not replay from its own recorded
dice, refuses a log from a different encounter or one that already ended, and
rebuilds the state the log describes: hit points, distance, the next round, and
the enemy's remaining spell slots. `read_resumed_state` derives all of it from
the recorded results alone, and the append path keeps sequence numbers
contiguous across a resume, including one that follows a trimmed log. What the
envelope cannot describe is listed in `RESUME_NOTES` and printed on resume - the
hero's conditions and action economy reset each round and are not stored, and
enemy narrative lines are not part of the record - so the gap is visible rather
than inferred. Slot recovery relies on the enemy's only FIRE attack being its
only spell; a guard test asserts that uniqueness against the AI's decision table,
so a future decision that broke the rule fails a test instead of quietly handing
a resumed enemy slots it had already spent.

This envelope is a **format and contract, not a persistence service**. Nothing
here schedules, replicates, deletes, or concurrently coordinates stored data;
retention is an explicit call, not a background policy, and a resume is a read of
a local file. Campaign and session persistence still belong to MCP Games.
Seeding every stochastic path is still not enforced by a contract.

The envelope also ships as a **published JSON Schema**
(`schemas/combat-encounter-log-1.schema.json`), so a consumer can validate a log
without importing this package. `combat_schema.validate_payload` applies that
same artifact at the Python boundary, and `load_log(..., validate_schema=True)`
opts into it; the demonstration runner takes the same `validate_schema` argument
and the TUI exposes it as `--validate-schema`. The two layers divide the contract
deliberately, and `test_combat_schema.py` tests the division rather than
assuming it. The schema owns structure, types, ranges, enum membership, and
unknown properties; the readers own what a schema cannot
express here, such as whether a recorded die result is legal for the die that
consumed it, and both are checked against the logs the engine actually produces.
The schema is stricter in exactly one way - it rejects unknown properties, which
the readers tolerate so a producer that adds a field cannot break an older
reader - and that one divergence is asserted by a test so it cannot drift into an
accident. Validation is opt-in and needs the optional `jsonschema` dependency,
the `schema` extra (`pip install 'ai-dungeon-master[schema]'`); `validate_payload`
raises `SchemaUnavailableError` when it is absent rather than reporting a pass it
did not perform, and the runners call `require_validator` before they start, so a
run that asked for the check refuses up front instead of part-way through.

Audio is outside the simulation's stream. `audio_synth` draws its noise from a
private `random.Random()` rather than the shared `random` module, so synthesising
sound effects cannot shift a combat roll: with `seed(1234)` the encounter used to
roll damage 4 / d20 3 on its own but damage 0 / d20 9 once the SFX generator had
run first.

The encounter AI's turn choice is a **query**. `EncounterEnemy.decide_turn_action`
computes the stance rather than storing it and reports a spell's slot cost on the
decision instead of deducting it, so previewing a turn - or asking twice - cannot
change the game. `commit_decision` applies that cost once a turn is really taken.

The `genui.py` blueprint, the TUI renderer, and the `web/` browser client are
**local, disposable clients**, not the production AgentSurface renderer. They
exist to exercise the result/state handoff inside this repo; the ephemeral UI
blueprint and its production browser renderer remain owned upstream by
`agentsurface`. The `web/` client is verified as a renderer specifically: it
holds no rules, and `test_web_demo.py` asserts that every component type the
Python producers emit is one it declares support for.

Both producers now speak **one** contract.
`game_foundation.validate_agentsurface_v01` is the single definition of
`agentsurface-blueprint/0.1` - a `surface` descriptor, a `dataModel`, a flat
`components` array linked by `children` ids, and the declared `intents` - and it
fails closed on every violation. It is applied to the output of both the
scenario adapter (`to_agentsurface_v01`) and the generative-surface exporter
(`SurfaceBlueprint.to_agentsurface_v01`), so the two cannot drift into private,
mutually incompatible shapes. A blueprint keeps its own parent-pointer view in
`to_dict()` for local rendering, but the interoperable form is the validated
envelope.

The proposed future MCP-facing tool names are `dm/init_encounter`,
`dm/resolve_turn`, `dm/render_surface`, and `dm/synthesize_audio`. They are
roadmap names, not available tools or an implemented API. A future integration
should keep mechanics authoritative in this repo, narrative/persistence
authoritative in MCP Games, and UI rendering ephemeral in AgentSurface; see
[Integrations](integrations.md) for the proposed handoff.

## Boundaries and trust

- **No live integration yet.** Export calls return plain Python dictionaries.
  They do not invoke MCP, access the network, or modify any external repo.
- **No model/vendor layer.** Content generation and model-provider policy remain
  future decisions behind a later boundary; current scenarios are hand-authored.
- **No persistence service.** The session event tuple is in-memory only. A
  combat log has a durable, versioned format with migration and retention, but
  writing one is an explicit call to `save_log`; there is no storage backend,
  scheduler, replication, or concurrency story, and campaign state remains with
  MCP Games. A resumed encounter reads one local file on request and never scans
  a directory, follows a path from the log, or writes anywhere else.
- **Untrusted content stays data.** Strings remain plain text in both exports.
  AgentSurface's renderer contract requires text rendering with `textContent`;
  never interpolate scenario strings into generated HTML or executable code.
  The adapter does not HTML-escape strings because the payload is JSON data, not
  markup; consumers must preserve the text-only rendering guarantee.
- **Validate at boundaries.** Re-validate exported payloads with the consuming
  project's own validator before shipping them. Local tests check required
  shapes and reachability but do not replace their TypeScript/Zod or
  AgentSurface validators. The combat log is the one payload with a published
  schema this repository can apply itself, and it is still the consuming
  project's validator that decides whether a log is acceptable there.

## Legal/content posture

The included fantasy scenario is newly written and contains no copied
rulebook passages, setting text, named protected characters, or art. This
project's current simplified D20 combat code is **not a complete D&D 5e ruleset**
and does not claim full SRD coverage.

For future D&D rules content, the [official D&D Beyond SRD page](https://www.dndbeyond.com/srd)
(last updated March 2, 2026) identifies SRD 5.2.1 as the latest available
version and states that SRD 5.2 content is available under CC BY 4.0. That
license applies to the covered SRD content only; it is not blanket permission
for all D&D settings, brands, or excluded names and monsters. Review the
specific SRD text and license, preserve required attribution, and verify source
provenance before importing content. Do not copy or paraphrase non-open-licensed
sourcebooks or use excluded material. Keep rules engine code, original scenario
text, and any licensed source data distinguishable.

## Design principles

1. Preserve the small, dependency-free Python core; add external libraries
   only for a concrete capability that cannot reasonably use stdlib.
2. Keep game/session concepts domain-neutral, with D20 as a reference game and
   mechanics as explicit, separate capabilities.
3. Version integration adapters and test their output at the contract boundary.
4. Prefer deterministic transformations, explicit validation, and replayable
   events over implicit state mutation.
5. Do not call the foundation “infallible.” Make assumptions visible, fail
   closed on invalid graph transitions, and grow coverage from observed gaps.

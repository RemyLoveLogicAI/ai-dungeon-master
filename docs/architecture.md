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
and the new small session/scenario/export foundation. The combat functions
currently use Python's shared `random` module; a seeded/injected random source
and replay-stable simulation contract are **not** implemented yet. No
`genui.py`, TUI, full rules expansion, ambient audio engine, or MCP server/tools
are part of this worktree.

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
- **No persistence claim.** The session event tuple is in-memory only. A durable
  event format, replay/version migration policy, and storage backend are future
  work.
- **Untrusted content stays data.** Strings remain plain text in both exports.
  AgentSurface's renderer contract requires text rendering with `textContent`;
  never interpolate scenario strings into generated HTML or executable code.
  The adapter does not HTML-escape strings because the payload is JSON data, not
  markup; consumers must preserve the text-only rendering guarantee.
- **Validate at boundaries.** Re-validate exported payloads with the consuming
  project's own validator before shipping them. Local tests check required
  shapes and reachability but do not replace their TypeScript/Zod or
  AgentSurface validators.

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

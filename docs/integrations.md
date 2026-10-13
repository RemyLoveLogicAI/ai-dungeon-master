# Integration contracts

The projects remain separate and independently versioned. This repository
exports data compatible with their public contracts; there is no runtime
network or MCP connection in this initial foundation. For the intended
production split, MCP Games owns campaign/story/context/persistence, this
repository owns authoritative rules/simulation and sensory primitives, and
AgentSurface owns ephemeral UI.

| Consumer | Adapter | Contract | Current handoff |
| --- | --- | --- | --- |
| [`mcp-games-monorepo`](https://github.com/RemyLoveLogicAI/mcp-games-monorepo) | `to_mcp_games_v1(scenario)` | GameDefinition fields: id, version, title, description, author, startScene, scenes, optional endings/contextPermissions | JSON-compatible `dict`; scene records have `id`, `title`, `narrative`, `choices`; choice records have `id`, `text`, `targetScene` |
| [`agentsurface`](https://github.com/RemyLoveLogicAI/agentsurface) | `to_agentsurface_v01(scenario)` | AgentSurface DSL v0.1: `surface`, `dataModel`, flat `components`, `intents` | JSON-compatible blueprint for the opening scene and a host-routed `choose` intent |

## Proposed MCP tool boundary (not implemented)

The following names are a proposed orchestration boundary only. There is no
MCP server, tool registration, network integration, or promise of schema
compatibility for these names in this repository yet.

| Proposed tool | Ownership/behavior when implemented |
| --- | --- |
| `dm/init_encounter` | This repo's adapter initializes a combat encounter from validated, minimal character/encounter inputs; returns engine state/results, not campaign persistence. |
| `dm/resolve_turn` | This repo validates a turn command, advances authoritative combat rules, and returns a result plus typed events/cues; caller persists the canonical campaign state. |
| `dm/render_surface` | An orchestration adapter maps current campaign/simulation state to a constrained AgentSurface v0.1 blueprint; AgentSurface validates/renders the ephemeral UI. |
| `dm/synthesize_audio` | This repo exposes current procedural WAV synthesis behind a bounded request and returns cue metadata/asset output; provider-based ambient/audio generation is not present. |

Before implementing these, define versioned input/output schemas, encounter
identity and ownership, idempotency and retry semantics, error handling,
request-size/time limits, and a replay-safe random source. A seedable or
injectable dice interface is a prerequisite for reproducible simulation; the
existing engine currently uses Python's global random source. MCP tool names
should be confirmed with the consuming projects and must not be treated as
committed cross-repo APIs based only on this proposal.

Adapter contract identifiers are exported as
`MCP_GAMES_ADAPTER_VERSION` (`mcp-games-game-definition/1`) and
`AGENTSURFACE_ADAPTER_VERSION` (`agentsurface-blueprint/0.1`). They are
identifiers for these translation contracts, not versions advertised as new
fields in either consumer's payload.

## MCP Games handoff

```python
from game_foundation import STARTER_SCENARIO, to_mcp_games_v1

payload = to_mcp_games_v1(STARTER_SCENARIO)
```

The shape mirrors
[`packages/mcp-games-server/src/core/schema.ts`](https://github.com/RemyLoveLogicAI/mcp-games-monorepo/blob/main/packages/mcp-games-server/src/core/schema.ts).
Every choice target points to a scene in the exported record. No `endings` or
`contextPermissions` are exported because the reference scenario does not need
either capability. A future live handoff should call the consumer's schema
validator and then use its documented MCP tools (`load_game`, `start_game`,
`make_choice`) rather than reimplementing its runtime.

## AgentSurface handoff

```python
from game_foundation import STARTER_SCENARIO, to_agentsurface_v01

blueprint = to_agentsurface_v01(STARTER_SCENARIO)
```

The blueprint follows the
[DSL v0.1 contract](https://github.com/RemyLoveLogicAI/agentsurface/blob/main/skill/references/dsl-spec.md):
flat whitelisted components, a single root with child-id references, a
`choice_id` data-model binding, and an explicit `choose` intent. The selected
choice ID is a payload value; a future host adapter is responsible for calling
the game session transition. The AgentSurface validator/renderer is not vendored
or run here.

## Compatibility policy

- Keep the external JSON field names as defined by each consumer (including
  camelCase names where required).
- Introduce changed mappings under a new adapter contract identifier instead
  of silently changing a published contract.
- Keep consumer-specific presentation and runtime semantics out of the generic
  scenario model.
- Before a live integration ships, pin/document the upstream contract revision,
  validate sample payloads against upstream validators, define failure and
  timeout behavior, and add a local end-to-end test. Do not add credentials or
  remote writes to this repository's test path.

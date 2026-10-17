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

Four versioned JSON Schemas and local Python validators now define a proposed
payload boundary: `encounter-init-request/1` and `encounter-init-result/1`
describe the engine's encounter initialization inputs and result projection;
`encounter-turn-request/1` and `encounter-turn-result/1` describe a single
attack request and its recorded event/result. These are structural contracts
only, not consumer-confirmed APIs. The schemas are under `schemas/`, and the
local validators are in `encounter_payload_schema.py`; there is still no
runtime adapter, MCP server, tool registration, or `dm/*` callable API here.

The payloads contain only per-encounter simulation state and attack data.
MCP Games remains authoritative for campaign/story/context, ownership, and
persisted session state; this repository owns encounter simulation. The schema
limits that have no canonical engine maximum (including combatant counts,
string lengths, dice bounds, and request/result sizes) are proposed defaults,
not consumer-approved resource limits. The `max_rounds` request field is
optional; the engine default is 50. `encounter-turn-request/1` models one
`AttackRequest`, not a complete multi-action turn.

The contracts do not define encounter identity, idempotency/retry behavior,
consumer ownership checks, error semantics, or adapter resource/time limits.
Those decisions and testing remain prerequisites before implementing
`dm/init_encounter` or `dm/resolve_turn`. Injectable dice sources now exist
(`d20_rules.DiceSource`), so a caller can opt into reproducible simulation;
the default still delegates to the module-level `random` for backward
compatibility, while audio synthesis draws from its own private generator.
Tool names must be confirmed with consuming projects before being treated as
committed cross-repo APIs.

### Adapter-readiness gate matrix

To prevent conflating local simulation behavior with distributed host integration,
the boundary separates what this repository verifies internally from the
prerequisites that require explicit consumer agreement and cross-project testing:

| Boundary Area | In-Repo Coverage (Verified) | Consumer Integration Requirement (Open) |
|---|---|---|
| **Replay vs. Idempotency** | Deterministic re-simulation from recorded rolls/events (`combat_events.py`, `d20_rules.DiceSource`). A replay log sequence is strictly re-execution logic, not request idempotency. | Duplicate/retry delivery semantics, client request token caching, idempotency key lifecycle, and duplicate call detection on network retries. |
| **Authority & Ownership** | Authoritative mechanical simulation scoped strictly to one encounter's state and active combatants. | Tenant/user auth checks, campaign/story ownership verification, and transaction ordering between campaign persistence and encounter mutation. |
| **Validation & Error Handling** | Fail-closed payload validation rejecting missing, extra, or malformed fields with local `SchemaValidationError` (`encounter_payload_schema.py`). Local exceptions are not MCP responses. | Standardized MCP error envelope mapping, application error codes (e.g. unknown encounter, invalid actor), and recovery behavior when host persistence fails after an encounter mutation. |
| **Resource & Boundary Limits** | Proposed schema structural bounds (combatant counts, name lengths, dice bounds). These are engine defaults, not consumer-approved limits. | Transport, latency, request timeout, payload byte caps, and rate limits negotiated against host limits, backed by integration boundary tests. |

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
the game session transition.

The combat surface in `genui.py` exports the *same* envelope, so a consumer
handles one shape rather than two:

```python
from genui import GenUIBlueprintFactory

surface = GenUIBlueprintFactory.create_encounter_surface(...)
blueprint = surface.to_agentsurface_v01()
```

`game_foundation.validate_agentsurface_v01` is the single definition of that
contract and fails closed on any violation. Both `to_agentsurface_v01` and
`SurfaceBlueprint.to_agentsurface_v01` validate their own output with it, so a
malformed blueprint is refused here rather than at the consumer. The
AgentSurface renderer itself is not vendored or run here; only the shape is
enforced.

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

# Version 1.0 MVP verification

This checklist is a release gate, not a statement that the current prototype
already qualifies. Attach evidence (CI run, contract-validator result, demo
recording, or linked issue/PR) for every checked item before tagging `v1.0.0`.
The release workflow rejects the tag while any checkbox remains unchecked.

- [ ] A player can complete a coherent branching session; MCP Games remains the source of truth for campaign persistence.
- [ ] The D&D reference slice demonstrates characters, an environment, an event, a challenge, and an encounter.
- [ ] Encounter actions produce validated state transitions and replayable results with a seeded or injected random source.
- [ ] MCP Games exports pass its upstream schema and a local integration test.
- [ ] AgentSurface output passes its upstream validator and rendered-UI verification, including no-selection and invalid-intent behavior.
- [ ] Accessible alternatives to audio/visual cues and expected failure behavior are documented and tested.
- [ ] Content provenance/licensing is recorded; no non-open licensed sourcebook text or excluded setting/brand content is included.
- [ ] CI, clean-checkout install/run instructions, package build, and release artifacts have been verified.

Evidence index:

| Gate | Evidence |
| --- | --- |
| Session and campaign flow | TBD |
| Simulation and replay | TBD |
| MCP Games contract | TBD |
| AgentSurface UI | TBD |
| Accessibility and failures | TBD |
| Content provenance | TBD |
| Clean install and release | TBD |

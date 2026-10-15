---
name: Feature request
about: Propose a capability or a change
title: "[feature] "
labels: enhancement
---

## The problem

<!-- What is hard or impossible today, and who it affects. Describe the need
     before the solution. -->

## Proposed approach

<!-- Optional. If it touches a published contract, say which one. -->

## Does it fit the project's boundaries?

The project is intentionally small and dependency-free. Please check the ones you
considered (see [Architecture](../../docs/architecture.md) and the
[roadmap](../../docs/roadmap.md)):

- [ ] It can be built with the standard library (or I have explained why it cannot).
- [ ] It does **not** move campaign/session persistence out of MCP Games.
- [ ] It does **not** move production UI rendering out of `agentsurface`.
- [ ] If it changes an export mapping, I have said which adapter contract
      identifier it belongs under.
- [ ] It is not a claim of full D&D rules coverage.

## How we would know it works

<!-- The observable check that would prove this is done. -->

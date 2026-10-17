# Live generative prototype implementation

Source date: October 17, 2026. User approved configured cloud AI providers.

## Outcome

A browser-playable AI Dungeon Master begins with guided character creation,
generates its narration and AgentSurface interface per decision, and asynchronously
generates scene art and instrumental music. A canonical local SQLite campaign
store serves the browser, CLI, and stdio MCP clients. This is the first supported
2024-rules starter slice, not a claim of complete D&D edition or combat coverage.

## Ownership

- campaign_core.py and test_campaign_core.py: persistence, exact-once committed
  actions, stale-write rejection, sourced Human level-one starter builds.
- live_generation.py and test_live_generation.py: configured Gemini REST provider,
  response validation, generated UI allowlist, separate image/music parsers.
- campaign_service.py and test_campaign_service.py: AI DM orchestration, explicit
  character approval, authoritative ability checks, asynchronous presentation/media.
- game_server.py and test_game_server.py: loopback HTTP API and static/media serving.
- web/play.html, web/play.js, web/play.css: visual client and declarative renderer.
- campaign_mcp.py, test_campaign_mcp.py, docs/mcp-access.md: cross-client MCP/CLI.

Existing dirty files are preserved. No new runtime dependency, public deployment,
MCP configuration modification, or remote campaign database is introduced.

## Behavior gates

1. Meet an explicitly identified AI DM; choose experience and guidance through
   its generated interface or ordinary language.
2. Generate a proposed character from a sourced supported preset. The player
   approves the sheet before adventuring. The model cannot invent character stats.
3. Freeform actions receive generated narration and a newly composed validated
   interface. Checks use recorded actual dice and authoritative sheet modifiers.
4. Persist each committed action once; duplicate request ids do not reroll,
   spend resources twice, or advance the journal again. Revision conflicts are visible.
5. Generate image/music independently. Errors are explicit, and stale media cannot
   replace the current scene. Refresh/restart resumes persisted campaign state.
6. Browser and agent clients share campaign ids, revisions, and action semantics.
   Remote cloud hosting is a later authenticated deployment boundary.

## Verification

Write and run focused failing tests before backend implementation. Test persistence,
concurrency, state authority, malformed provider output, failed generation, media
revision isolation, HTTP origin/path boundaries, and MCP protocol framing. Run
targeted tests, lint/type checks, the existing regression suite, and browser scenarios.
Record actual provider smoke-test results without printing credentials. Do not
substitute fixture content for live AI when presenting the result.

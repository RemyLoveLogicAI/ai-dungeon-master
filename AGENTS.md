# AI Dungeon Master — Agent Directives & Architecture Invariants

## Core Principles

1. **Tabletop D&D Fidelity as DNA:**
   - The AI acts as the Dungeon Master: passionate, encyclopedic, welcoming to novices, and speaking fluent rules-minutiae with veterans.
   - Game mechanics, HP, spell slots, Armor Class, and dice resolution are **authoritative and deterministic**. An LLM must never hallucinate stats in raw conversational memory. All rolls, state transitions, and damage route through `d20_rules.py`, `campaign_core.py`, and `turn_orchestrator.py`.
   - Respect strict edition profiles (B/X, AD&D 1e/2e, 3.5e, 4e, 5e 2014, 5e 2024). Never silently substitute modern mechanics into an older edition campaign.

2. **Declarative Generative UI (GenUI):**
   - The UI is generated on the fly, but **strictly declaratively** via the `agentsurface-blueprint/0.1` schema.
   - The AI DM decides what components exist (`Card`, `Button`, `Stack`, `ProgressBar`, `Table`, `Stat`, `Badge`). The client (Web browser or Unity XR) paints them natively.
   - Arbitrary model-authored executable JavaScript or unvalidated HTML is strictly prohibited (`textContent` only, zero-eval).
   - All interactive actions must specify declared intents in the blueprint (`intents: [...]`) and pass bound data model parameters.

3. **Decoupled Multimodal Turn Pipeline:**
   - Mechanical resolution commits to the campaign journal **first**.
   - Narration text and contextual GenUI surfaces stream immediately to the player (<800ms).
   - Generative scene art (diffusion prompts) and audio cues (procedural synthesis / music prompts) stream asynchronously without blocking turn interaction or freezing the game.

4. **Production VR Architecture (Unity XR):**
   - The Unity client (`AIDungeonVRClient.cs`) is a thin spatial front-end (eyes, ears, hands) connecting to `vr_server.py`.
   - Never duplicate Python game logic or rules in C#.
   - Support diegetic VR metaphors:
     - Adventurer's Grimoire (character sheet scroll).
     - Miniature Tabletop Diorama (3D tactical grid).
     - Physicalized Haptic Dice Tray (`PHYSICAL_DICE_ROLL`).
   - Zero per-frame GC allocations (target 90/120 Hz).

5. **Cross-Client Stdio MCP Bridge:**
   - `campaign_mcp.py` provides standard Model Context Protocol access (`dm_status`, `dm_get_campaign`, `dm_act`, `dm_create_campaign`) over stdio JSON-RPC 2.0.
   - Never leak write tokens or sensitive credentials over the MCP boundary.

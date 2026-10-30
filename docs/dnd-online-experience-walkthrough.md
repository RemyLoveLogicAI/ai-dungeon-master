# D&D Online VTT: Complete Player Journey, System Architecture & Generative Process

## 1. Executive Summary

This document establishes the end-to-end integration mapping the AI Dungeon Master platform to the modern **D&D Online Virtual Tabletop (VTT)** ecosystem (combining the best paradigms of D&D Beyond character management, Roll20/Foundry tactical grid diorama, and live multi-agent table coordination).

Every player decision orchestrates a synchronized response across **Story**, **Visuals**, **Spatial Audio**, **Dynamic GenUI**, and **Deterministic Rules**, supporting browser clients, desktop runners, and immersive Unity VR headsets.

---

## 2. End-to-End Player Experience Journey

```mermaid
flowchart TD
    subgraph S0 ["Phase 0: Table Lobby & Session Zero"]
        A["Connect to Table (Web / Desktop / Unity VR)"] --> B["Meet the AI DM (Voice, Persona & Boundaries)"]
        B --> C["Calibrate Experience (Newcomer to Level 140 Mage)"]
        C --> D["Select Rules DNA (D&D 5e 2024 / 5e 2014 / 3.5e / AD&D / B/X)"]
    end

    subgraph S1 ["Phase 1: Character Forge & Grimoire Binding"]
        D --> E["Discover Concept (Conversational or Manual)"]
        E --> F["Roll/Allocate Abilities & Select Origin/Class"]
        F --> G["Derive Combat Vitals, Weapon Mastery & Spells"]
        G --> H["Generate Visual Portrait & Musical Leitmotif"]
        H --> I["Bind Authoritative Character Sheet / VR Grimoire"]
    end

    subgraph S2 ["Phase 2: Enter the Living Virtual Tabletop (VTT)"]
        I --> J["Render 3D/2D Tactical Tabletop Diorama"]
        J --> K["Stream Opening Scene Narration & Ambient Audio"]
    end

    subgraph S3 ["Phase 3: The Live Adventure Loop"]
        K --> L["Player Action: Freeform Intent or GenUI Control"]
        L --> M{"Action Requires Rules Resolution?"}
        M -- "Yes" --> N["Resolve via d20 Rules Core (DC / AC / Saves / Contest)"]
        M -- "No / Discretionary" --> O["DM Adjudication & Fictional Positioning"]
        N --> P["Commit Outcome to Campaign Journal"]
        O --> P
        P --> Q["Parallel Multimodal Response: Narration (<500ms) + GenUI (<800ms) + Art/Music (2-3s)"]
        Q --> L
    end

    subgraph S4 ["Phase 4: Tactical Combat & Investigation Workspaces"]
        L -. "Encounter Triggered" .-> R["Tactical Combat Matrix (Initiative, Turns, Haptic Dice)"]
        L -. "Puzzle / Apparatus" .-> S["Custom Workspace (e.g. Celestial Observatory Dials)"]
        R -. "Combat Resolved" .-> L
        S -. "Puzzle Solved" .-> L
    end

    subgraph S5 ["Phase 5: Rest, Advancement & Continuity"]
        L -. "Short / Long Rest" .-> T["Resolve Rest Recovery & Hit Dice"]
        L -. "XP / Milestone" .-> U["Level Up Walkthrough (Before/After Sheet Diff)"]
        T --> V["Save Canonical Snapshot to SQLite / MCP Engine"]
        U --> V
    end
```

---

## 3. High-Level System Architecture & Client Topology

```mermaid
flowchart TB
    subgraph Clients ["Cross-Platform Client Tier"]
        WebClient["Web Browser VTT (web/play.html)"]
        VRClient["Unity XR Headset (AIDungeonVRClient.cs)"]
        DesktopClient["Tauri / TUI Runner (tui_runner.py)"]
        MCPClient["External Agent / IDE (campaign_mcp.py)"]
    end

    subgraph Gateway ["Network & Transport Gateway"]
        HTTPServer["HTTP / Static Server (vr_server.py / game_server.py)"]
        SSEStream["Server-Sent Events (SSE) Stream"]
        JSONRPC["Stdio JSON-RPC 2.0 (MCP Server)"]
    end

    subgraph CoreEngine ["Authoritative D&D Simulation Core"]
        TurnOrch["Multimodal Turn Orchestrator (turn_orchestrator.py)"]
        RulesEngine["Deterministic D20 Engine (d20_rules.py)"]
        CampaignStore["Canonical SQLite Campaign Store (campaign_core.py)"]
        GenUIFactory["GenUI Blueprint Factory (genui.py)"]
    end

    subgraph GenerationServices ["Generative AI Pipelines"]
        GeminiProvider["Gemini REST Provider (live_generation.py)"]
        AudioSynth["Procedural Audio & Tension Synthesizer (audio_synth.py)"]
        DiffusionBridge["Scene Art & Diffusion Prompt Generator"]
    end

    WebClient <--> HTTPServer
    VRClient <--> HTTPServer
    DesktopClient <--> HTTPServer
    MCPClient <--> JSONRPC

    HTTPServer <--> TurnOrch
    JSONRPC <--> CampaignStore

    TurnOrch --> RulesEngine
    TurnOrch --> CampaignStore
    TurnOrch --> GenUIFactory
    TurnOrch --> GeminiProvider
    TurnOrch --> AudioSynth
    TurnOrch --> DiffusionBridge
```

---

## 4. Turn-by-Turn Multimodal Execution Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Player as Player (Web / VR)
    participant Client as Client VTT (Web / Unity XR)
    participant Orch as Turn Orchestrator
    participant Rules as D20 Rules Core
    participant Store as Campaign Store (SQLite)
    participant GenUI as GenUI Factory
    participant Media as Multimodal Media Agents

    Player->>Client: Input action ("I cast Light on my shield and examine the altar")
    Client->>Orch: POST /api/intent (intent, payload, revision #12)
    
    rect rgb(240, 248, 255)
    Note over Orch,Rules: Step 1: Authoritative Mechanics Resolution (<10ms)
    Orch->>Rules: Check spell slot / cantrip legality & roll Arcana check (d20 + 5)
    Rules-->>Orch: Check Success (Roll: 14 + 5 = 19 vs DC 15)
    end

    rect rgb(255, 250, 240)
    Note over Orch,Store: Step 2: Atomic State Commit
    Orch->>Store: Commit journal entry, spent resources & state revision #13
    Store-->>Orch: Committed (Revision #13 confirmed)
    end

    rect rgb(240, 255, 240)
    Note over Orch,Client: Step 3: Fast Sensory Streaming (<800ms)
    Orch->>GenUI: Compose updated GenUI surface (agentsurface-blueprint/0.1)
    GenUI-->>Orch: Validated declarative blueprint
    Orch-->>Client: Stream Narration Text & GenUI Surface Controls
    Client-->>Player: Display new situation & interactive buttons immediately
    end

    rect rgb(255, 245, 245)
    Note over Orch,Media: Step 4: Asynchronous Rich Media Generation (1.5s - 3s)
    par Media Generation
        Orch->>Media: Generate Scene Illustration (Prompt: glowing altar under radiant shield light)
        Media-->>Client: Stream Scene Image (Fades into scene view)
        Orch->>Media: Generate Dynamic Soundscape (Audio: holy_gleam SFX + mystery drone)
        Media-->>Client: Crossfade Spatial Audio in background
    end
    end
```

---

## 5. Virtual Tabletop UI Layout Architecture

The user interface adapts dynamically across five primary viewports:

| Viewport | Primary Purpose | Key Components |
| :--- | :--- | :--- |
| **1. Tactical Battlemap / Diorama** | 2D/3D visual spatial state | Grid tiles, creature tokens, line-of-sight, terrain covers, range rings |
| **2. Interactive Character Grimoire** | Persistent player status | HP progress bar, Armor Class, Spell Slots, Weapon Masteries, Inventory |
| **3. Narrative Chronicle & Voice** | The DM's living story log | Formatted prose, dialogue bubbles, DM TTS voice playback, roll breakdowns |
| **4. Contextual GenUI Action Tray** | Dynamic situational controls | Action/Bonus Action/Reaction matrix, puzzle dials, dialogue options |
| **5. Physicalized 3D Dice Tray** | Tactile resolution | Real-time d20 physics simulation, haptic rumble, critical fanfare audio |

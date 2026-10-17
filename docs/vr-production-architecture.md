# Production VR Architecture: AI Dungeon Master for Unity XR

## 1. Executive Summary

A stable, production-grade VR experience cannot put the network or dynamic script compilation inside the render loop. Per-frame state (hands, head, physics) never crosses the network. Turn-level intents (choose, roll, confirm) are plain HTTP request/response against `vr_server.py` with a 3 s client timeout, and the render loop never awaits a fetch. VR headsets enforce rigid real-time constraints:
* **Frame Timing:** Rock-solid 90 Hz (11.1ms per frame) or 120 Hz (8.33ms per frame) to prevent simulator sickness.
* **Garbage Collection:** Zero GC allocation per frame on mobile chipsets (Snapdragon XR2 Gen 2 / Quest 3).
* **Network Authority:** The VR headset is an input/output sensory device (eyes, ears, hands). The authoritative D&D rules engine, campaign persistence, and generative models reside on the backend.

---

## 2. System Architecture

```mermaid
flowchart LR
    subgraph UnityXR ["Unity VR Client (Quest 3 / Vision Pro / PCVR)"]
        XRInput["XR Controller / Hand Tracking"] --> VRClient["AIDungeonVRClient (C#)"]
        VRClient --> WorldCanvas["World-Space GenUI Canvas"]
        VRClient --> DicePhysics["PhysX Dice Tray (d20 Haptics)"]
        VRClient --> AudioSource["Spatial 3D Audio (DM Voice)"]
    end

    subgraph Backend ["Authoritative Engine (vr_server.py)"]
        Endpoint["Fast Server API (/api/surface, /api/intent)"]
        RulesEngine["d20 Rules & Campaign State Core"]
        GenUIFactory["GenUI Blueprint Factory (agentsurface-blueprint/0.1)"]
    end

    VRClient -- "1. Intent Dispatch / Physical Dice Roll" --> Endpoint
    Endpoint --> RulesEngine
    RulesEngine --> GenUIFactory
    GenUIFactory -- "2. Validated Declarative Blueprint" --> VRClient
```

---

## 3. Diegetic VR Tabletop Metaphors

Rather than flat 2D floating windows, production VR maps the generative UI into physicalized, diegetic objects:

1. **The Adventurer's Grimoire (Character Sheet):**  
   Held in the player's non-dominant hand or resting on the table. Flips open to show current HP, AC, spell slots, and inventory.
2. **The Living Tabletop Diorama (Tactical Grid):**  
   The tactical map (`TacticalGrid`) renders as 3D miniatures and terrain props on an oak table in front of the player.
3. **Physicalized Haptic Dice Tray:**  
   Players physically grab, shake, and roll a 3D d20 with controller haptics. When the die settles, the face value is captured and dispatched to the engine via `PHYSICAL_DICE_ROLL`.
4. **Spatial DM Presence:**  
   The DM speaks from a distinct point in 3D space across the table, anchoring immersion.

---

## 4. Performance & Memory Contract

* **Prefab Pooling:** All dynamic GenUI cards, stats, and buttons are pooled in memory on scene awake. Instantiation during gameplay is prohibited.
* **Declarative Schemas:** Blueprints strictly adhere to `agentsurface-blueprint/0.1`. The Unity client contains zero game logic; it purely maps JSON components into pre-built UI primitives.
* **Fail-Closed Fallback:** If a network interruption occurs, the client retains the last authoritative state and offers an in-world retry button.

---

## Slice 1: WebXR first

The first playable slice is a WebXR page in Quest Browser (three.js + cannon-es), served by `vr_server.py` and reached over `adb reverse tcp:8000 tcp:8000`. Unity stays the fallback and later port; see `.omc/plans/vr-quest3-slice.md`. Run the server with `python -m vr_server` (loopback only by default).

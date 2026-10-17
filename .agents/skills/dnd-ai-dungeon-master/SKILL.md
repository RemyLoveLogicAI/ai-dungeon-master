---
name: dnd-ai-dungeon-master
description: >-
  Workflows, runbooks, and architectural guidelines for developing, extending,
  and testing the AI Dungeon Master platform. Use when modifying D&D rules engines,
  creating GenUI surfaces, adding edition profiles, orchestrating multimodal turns,
  or testing Unity VR / Web clients.
---

# AI Dungeon Master — Developer & Agent Runbook

This skill provides step-by-step procedures for building and verifying features in the AI Dungeon Master repository.

---

## 1. Testing and Verification

Always run test suites using the project's local virtual environment (`.venv/bin/pytest`):

```bash
# Run full regression suite (360+ tests)
.venv/bin/pytest

# Test GenUI surface generation & blueprints
.venv/bin/pytest test_genui.py test_web_demo.py

# Test campaign core persistence & state
.venv/bin/pytest test_campaign_core.py

# Test multimodal turn orchestration
.venv/bin/pytest test_turn_orchestrator.py

# Test production VR server bridge
.venv/bin/pytest test_vr_server.py

# Test MCP stdio server
.venv/bin/pytest test_campaign_mcp.py
```

---

## 2. Adding a New GenUI Surface (Level 1 & Level 2)

When adding a new interactive workspace (e.g., Tavern Rumor Mill, Alchemy Crafting Bench, or Grimoire):

1. **Define the factory method in `genui.py`:**
   * Instantiate `SurfaceBlueprint(surfaceId=..., title=..., subtitle=...)`.
   * Add components using `UIComponent(id=..., type=UIComponentType.<TYPE>.value, parentId=..., props=...)`.
   * Ensure interactive buttons specify valid intents and bound payload parameters.
   * Return the blueprint and self-validate with `validate_agentsurface_v01(blueprint.to_agentsurface_v01())`.

2. **Register in `web/build_demo.py`:**
   * Add the surface to `build_demo_data()` and recompile `web/demo-data.json`:
     ```bash
     .venv/bin/python web/build_demo.py
     ```

3. **Wire View in `web/app.js` & `web/index.html`:**
   * Add the navigation tab to `web/index.html`.
   * Add the `show<Surface>()` function, `#hash` sync, and intent handler in `web/app.js`.

---

## 3. Resolving a Multimodal Turn

When processing player decisions through `turn_orchestrator.py`:
1. **Adjudicate Mechanics First:** Roll dice via `SeededDiceSource`, apply modifiers, check DCs or ACs, update HP and flags.
2. **Draft Coherent Narration:** Contextual description honoring the rolled outcome without lecturing the player.
3. **Draft Art & Audio Prompts:** Create a high-fidelity image prompt for diffusion models and an audio cue (`crit_fanfare`, `sword_clash`, `ambient_drone`).
4. **Compose the Follow-up GenUI Surface:** Return newly relevant choices and disabled actions.

---

## 4. Unity VR Integration

The Unity client is located in `unity/ProductionVR/AIDungeonVRClient.cs`.
* When running local VR sessions, start the Python bridge:
  ```bash
  .venv/bin/python vr_server.py
  ```
* Ensure physical dice rolls report via `PHYSICAL_DICE_ROLL`.
* Maintain 90/120 Hz frame budgets by avoiding runtime component instantiation.

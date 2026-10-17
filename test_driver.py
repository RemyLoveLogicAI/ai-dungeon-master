#!/usr/bin/env python3
"""AI Dungeon Master — End-to-End Test Driver & Process Verification Harness.

Drives the complete tactical engine, encounter generator, game foundation,
terminal surface (TUI), and web demo contracts, recording results for Jam MCP.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from combat_log import load_log, verify_log
from combat_runner import CombatantState, run_generated_encounter
from d20_rules import SeededDiceSource
from encounter_generator import CreatureCandidate, Difficulty, generate_encounter
from game_foundation import validate_agentsurface_v01
from tui_runner import run_tui_encounter

__test__ = False


def print_step(title: str) -> None:
    print(f"\n{'=' * 65}")
    print(f"  ▶ [TEST DRIVER] {title}")
    print(f"{'=' * 65}")


def test_encounter_generation() -> dict[str, Any]:
    print_step("Phase 1: Seeded Encounter Generation (DMG p. 82)")
    party = [3, 3, 3, 3]
    candidates = [
        CreatureCandidate("Kobold", 25, "1/8", {"biome": ["caves"]}),
        CreatureCandidate("Goblin", 50, "1/4", {"biome": ["forest"]}),
        CreatureCandidate("Orc", 100, "1/2", {"biome": ["hills"]}),
        CreatureCandidate("Bugbear", 200, "1", {"biome": ["forest"]}),
    ]

    results = {}
    for diff in (Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD, Difficulty.DEADLY):
        enc = generate_encounter(party, candidates, target_difficulty=diff, seed=123)
        assert enc["version"] == "gpf/encounter.v1", f"Bad version: {enc['version']}"
        assert len(enc["monsters"]) > 0, "No monsters generated"
        print(
            f"  ✔ Target {diff.value:<7} -> Achieved: {enc['achieved_difficulty']:<7} | "
            f"XP: {enc['budget']['raw_xp']} (Adjusted: {enc['budget']['adjusted_xp']}) | "
            f"Monsters ({len(enc['monsters'])}): {[m['name'] for m in enc['monsters']]}"
        )
        results[diff.value] = {
            "achieved": enc["achieved_difficulty"],
            "monster_count": len(enc["monsters"]),
            "monsters": [m["name"] for m in enc["monsters"]],
            "raw_xp": enc["budget"]["raw_xp"],
            "adjusted_xp": enc["budget"]["adjusted_xp"],
        }
    return results


def test_combat_execution_and_replay() -> dict[str, Any]:
    print_step("Phase 2: Tactical Combat Loop & Deterministic Replay")

    # Strict party and monster setup
    party = [
        CombatantState(
            name="Sir Kaelen (Paladin)",
            current_hp=38,
            max_hp=38,
            ac=16,
            attack_modifier=5,
            damage_dice_count=1,
            damage_die_sides=8,
            damage_modifier=3,
            abilities={"str": 16, "dex": 12, "level": 3},
            initiative=1,
            stance="defensive",
        ),
        CombatantState(
            name="Lyra (Rogue)",
            current_hp=24,
            max_hp=24,
            ac=14,
            attack_modifier=6,
            damage_dice_count=1,
            damage_die_sides=6,
            damage_modifier=4,
            abilities={"str": 10, "dex": 16, "level": 3},
            initiative=3,
            stance="aggressive",
        ),
    ]

    candidates = [
        CreatureCandidate(
            "Goblin Ambusher",
            50,
            "1/4",
            {
                "hp": {"current": 7, "max": 7, "formula": "2d6"},
                "ac": 15,
                "attack_modifier": 4,
                "damage": {"dice": 1, "sides": 6, "modifier": 2, "type": "piercing"},
                "stance": "aggressive",
                "initiative": 2,
            },
        ),
        CreatureCandidate(
            "Hobgoblin Guard",
            100,
            "1/2",
            {
                "hp": {"current": 11, "max": 11, "formula": "2d8+2"},
                "ac": 18,
                "attack_modifier": 3,
                "damage": {"dice": 1, "sides": 8, "modifier": 1, "type": "slashing"},
                "stance": "defensive",
                "initiative": 1,
            },
        ),
    ]

    dice = SeededDiceSource(77)
    res = run_generated_encounter(
        party, candidates, Difficulty.MEDIUM, seed=42, dice=dice, max_rounds=20
    )

    assert res["outcome"] in ("victory", "mercy_rule", "stalemate")
    assert len(res["game_events"]) > 0
    replay_ok = verify_log(res["log"])
    assert replay_ok, "Combat log failed deterministic replay!"

    print(f"  ✔ Outcome:         {res['outcome'].upper()}")
    print(f"  ✔ Rounds executed: {res['rounds']}")
    print(f"  ✔ XP awarded:      {res['xp_awarded']}")
    print(f"  ✔ Narrative:       {res['narrative']}")
    print(f"  ✔ Events logged:   {len(res['game_events'])}")
    print(f"  ✔ Replay status:   {'DETERMINISTIC VERIFIED' if replay_ok else 'FAILED'}")

    return {
        "outcome": res["outcome"],
        "rounds": res["rounds"],
        "xp_awarded": res["xp_awarded"],
        "events_count": len(res["game_events"]),
        "replay_verified": replay_ok,
    }


def test_tui_and_persistence() -> dict[str, Any]:
    print_step("Phase 3: Generative Terminal Surface & State Persistence")

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        log_path = tf.name

    try:
        # Step 1: Run 1 round and save state to disk
        print("  ▶ Running TUI Encounter (Round 1, saving to disk)...")
        bp1 = run_tui_encounter(max_rounds=1, log_path=log_path, overwrite=True, dice=SeededDiceSource(101))
        assert bp1 is not None, "TUI failed to produce a surface blueprint"
        log1 = load_log(log_path)
        assert len(log1) > 0, "Log empty after initial round"
        print(f"  ✔ Saved {len(log1)} combat entries to {log_path} (Round 1)")

        # Step 2: Resume encounter from disk and advance
        print("  ▶ Resuming Encounter from saved state (Round 2)...")
        bp2 = run_tui_encounter(max_rounds=1, log_path=log_path, resume=True, dice=SeededDiceSource(102))
        assert bp2 is not None, "TUI failed to produce resumed surface blueprint"
        log2 = load_log(log_path)
        assert len(log2) > len(log1), "Resumed log did not advance"
        seqs = [e.event.sequence for e in log2.entries]
        expected_seqs = list(range(1, len(log2) + 1))
        assert seqs == expected_seqs, f"Sequence discontinuity: {seqs} != {expected_seqs}"
        print(f"  ✔ Resumed and advanced to {len(log2)} contiguous entries (Sequences 1..{len(log2)})")

        replay_ok = verify_log(log2)
        assert replay_ok, "Resumed log failed deterministic replay verification"
        print("  ✔ Full multi-session log verified deterministic on replay")

        return {
            "initial_entries": len(log1),
            "resumed_entries": len(log2),
            "sequence_contiguous": True,
            "replay_verified": True,
        }
    finally:
        if os.path.exists(log_path):
            os.remove(log_path)


def test_web_demo_contract() -> dict[str, Any]:
    print_step("Phase 4: AgentSurface Contract & Web Demo Validation")
    repo_root = Path(__file__).resolve().parent
    demo_json_path = repo_root / "web" / "demo-data.json"
    assert demo_json_path.exists(), "web/demo-data.json missing"

    data = json.loads(demo_json_path.read_text(encoding="utf-8"))
    assert "scenario" in data and "encounter" in data, "Malformed demo-data.json"

    # Validate each scene blueprint in the scenario
    scenes = data["scenario"]["scenes"]
    assert len(scenes) > 0, "No scenes in scenario"
    for entry in scenes.values():
        validate_agentsurface_v01(entry["blueprint"], root="root")
    print(f"  ✔ Validated {len(scenes)} scenario scene blueprints under agentsurface-blueprint/0.1")

    # Validate the encounter surface
    encounter_surface = data["encounter"]["surface"]
    validate_agentsurface_v01(encounter_surface, root="root")
    print("  ✔ Encounter surface:   agentsurface-blueprint/0.1 contract VALID")
    print(f"  ✔ Encounter components: {len(encounter_surface.get('components', []))} components")

    return {
        "scenes_count": len(scenes),
        "encounter_components": len(encounter_surface.get("components", [])),
        "contract": "agentsurface-blueprint/0.1",
    }


def main() -> None:
    start_time = time.time()
    print("=================================================================")
    print("   AI DUNGEON MASTER — TEST DRIVER & JAM PROCESS RECORDING       ")
    print("=================================================================")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("Target Environment: /private/tmp/ai-dm-feat-pr")
    print("Jam Recording Link: https://recorder.jam.dev/9HDwJg9 (ID: 2ee86a85-9ba3-4620-9767-64d9a0d9b488)")

    r1 = test_encounter_generation()
    r2 = test_combat_execution_and_replay()
    r3 = test_tui_and_persistence()
    r4 = test_web_demo_contract()

    elapsed = time.time() - start_time
    print_step("Summary & Receipt")
    print(f"  ✔ All 4 testdriver phases passed in {elapsed:.2f}s")
    print("  ✔ Total Verified Pipeline: Encounter Gen ➔ Tactical D20 ➔ TUI Replay ➔ Web Demo")

    report = {
        "timestamp": time.time(),
        "elapsed_seconds": elapsed,
        "jam_recording_link": "https://recorder.jam.dev/9HDwJg9",
        "phases": {
            "encounter_generation": r1,
            "tactical_combat": r2,
            "tui_and_persistence": r3,
            "web_demo_contract": r4,
        },
        "verdict": "PASSED_ALL_GATES",
    }
    report_file = Path("/private/tmp/ai-dm-feat-pr/test_driver_receipt.json")
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"  ✔ Receipt written to {report_file}")


if __name__ == "__main__":
    main()

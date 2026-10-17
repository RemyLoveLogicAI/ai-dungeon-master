"""Export the browser demo's data from the real engine.

This module is a *build-time driver*, not a second implementation of the rules.
It renders nothing and reimplements nothing: every blueprint it writes comes from
the same producers the rest of the repository uses, and every one is validated
against ``agentsurface-blueprint/0.1`` before it is written out.

What it emits, to ``web/demo-data.json``:

- ``scenario``: one validated v0.1 blueprint per scene, plus the
  ``choice id -> target scene`` map the browser needs to navigate. The graph is
  static data, so following a choice is presentation, not game logic.
- ``encounter``: one validated v0.1 blueprint from
  :class:`genui.GenUIBlueprintFactory`, built from a real, seeded, deterministic
  skirmish run through the actual engine.

Run it directly to (re)generate the file:

    python web/build_demo.py

``test_web_demo.py`` calls :func:`build_demo_data` and asserts the committed
artifact matches a fresh build, so the JSON cannot silently drift from the code.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

# The modules under test live at the repository root; this file is invoked both
# as a script and imported by the test suite, so make the import path explicit.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from combat_log import record_entry
from d20_rules import (
    AdvantageMode,
    AttackRequest,
    DamageType,
    SeededDiceSource,
)
from encounter_ai import CombatActionType, EncounterEnemy
from game_foundation import (
    AGENTSURFACE_ADAPTER_VERSION,
    STARTER_SCENARIO,
    Scenario,
    to_agentsurface_v01,
    validate_agentsurface_v01,
)
from genui import GenUIBlueprintFactory

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo-data.json")

# Fixed seed: the exported encounter is reproducible byte for byte, which is what
# lets the drift test compare the artifact against a fresh build.
ENCOUNTER_SEED = 7


def export_scenario(scenario: Scenario) -> dict[str, Any]:
    """Export every scene as a validated blueprint plus its choice targets."""
    scenes: dict[str, Any] = {}
    for scene in scenario.scenes:
        # The adapter exports any scene of an already-validated scenario.
        blueprint = to_agentsurface_v01(scenario, scene_id=scene.id)
        scenes[scene.id] = {
            "blueprint": blueprint,
            "targets": {choice.id: choice.target_scene for choice in scene.choices},
        }
    return {
        "id": scenario.id,
        "version": scenario.version,
        "title": scenario.title,
        "description": scenario.description,
        "author": scenario.author,
        "startScene": scenario.start_scene,
        "scenes": scenes,
    }


def simulate_encounter(seed: int = ENCOUNTER_SEED) -> dict[str, Any]:
    """Run one real skirmish through the engine and return the surface + feed.

    The loop here is a *driver* alongside ``combat_runner`` and ``tui_runner``:
    all rules come from ``record_entry``, ``resolve_attack`` and
    ``EncounterEnemy``. Nothing about attack resolution, spell slots or stance is
    reimplemented.
    """
    dice = SeededDiceSource(seed)

    hero_name, hero_max_hp, hero_ac, hero_attack_mod = "Paladin Alden", 38, 16, 5
    hero_hp = hero_max_hp
    hero_conditions: list[str] = []

    enemy = EncounterEnemy("Shadow Gargoyle", max_hp=35, ac=14, spell_slots=2)
    distance = 4.0
    feed: list[str] = []
    rounds = 0
    outcome = "stalemate"

    while hero_hp > 0 and enemy.current_hp > 0 and rounds < 12:
        rounds += 1
        feed.append(f"Round {rounds} — distance {distance:.1f}m — {enemy.name} is {enemy.stance.value}.")

        request = AttackRequest(
            attacker=hero_name,
            target=enemy.name,
            attack_modifier=hero_attack_mod,
            target_ac=enemy.ac,
            damage_dice_count=1,
            damage_die_sides=8,
            damage_modifier=3,
            damage_type=DamageType.SLASHING,
            advantage=AdvantageMode.NORMAL,
        )
        _, resolution = record_entry(request, sequence=1, dice=dice)
        feed.append(resolution.combat_message)
        if resolution.is_hit:
            enemy.apply_damage(resolution.damage_dealt)
            if resolution.is_critical:
                hero_conditions.append("Enemy Staggered")

        if enemy.current_hp <= 0:
            outcome = "victory"
            feed.append(f"VICTORY! {enemy.name} falls to {hero_name}.")
            break

        decision = enemy.decide_turn_action(distance)
        if decision.action == CombatActionType.FLEE:
            outcome = "enemy-fled"
            feed.append(f"{enemy.name} breaks engagement and flees into the shadows.")
            break
        if decision.action == CombatActionType.DODGE:
            feed.append(f"{enemy.name} readies a defensive stance.")
        else:
            # Taking the turn is what spends the slot; deciding did not.
            enemy.commit_decision(decision)
            enemy_request = AttackRequest(
                attacker=enemy.name,
                target=hero_name,
                attack_modifier=decision.attack_modifier,
                target_ac=hero_ac,
                damage_dice_count=decision.damage_dice_count,
                damage_die_sides=decision.damage_die_sides,
                damage_modifier=decision.damage_modifier,
                damage_type=decision.damage_type,
            )
            _, enemy_resolution = record_entry(enemy_request, sequence=1, dice=dice)
            feed.append(enemy_resolution.combat_message)
            if enemy_resolution.is_hit:
                hero_hp = max(0, hero_hp - enemy_resolution.damage_dealt)
                if decision.damage_type == DamageType.FIRE:
                    feed.append("The gargoyle's fire burns into the paladin's guard.")

        if distance > 1.5:
            distance = max(1.0, distance - 1.5)

    if hero_hp <= 0:
        outcome = "defeat"
        feed.append(f"DEFEAT! {hero_name} has fallen to {enemy.name}.")

    tension = 1.0 - (hero_hp / hero_max_hp) * 0.5 - (enemy.current_hp / enemy.max_hp) * 0.5
    surface = GenUIBlueprintFactory.create_encounter_surface(
        surface_id="demo-encounter",
        title="Tactical Arena",
        round_num=rounds,
        hero_name=hero_name,
        hero_hp=hero_hp,
        hero_max_hp=hero_max_hp,
        hero_conditions=hero_conditions,
        hero_actions_available={"Action": True, "Bonus Action": True, "Reaction": False},
        enemy_name=enemy.name,
        enemy_hp=enemy.current_hp,
        enemy_max_hp=enemy.max_hp,
        enemy_stance=enemy.stance.value,
        combat_log=feed,
        tension_level=max(0.0, min(1.0, tension)),
    )
    return {
        "seed": seed,
        "outcome": outcome,
        "rounds": rounds,
        "feed": feed,
        "surface": surface.to_agentsurface_v01(),
    }


def build_demo_data() -> dict[str, Any]:
    """Assemble and self-validate the whole demo payload."""
    onboarding_surface = GenUIBlueprintFactory.create_onboarding_surface().to_agentsurface_v01()
    # Annotated explicitly: inferred from the literal, mypy widens the value type
    # and the indexing below stops type-checking.
    data: dict[str, Any] = {
        "contract": AGENTSURFACE_ADAPTER_VERSION,
        "generator": "web/build_demo.py",
        "onboarding": {
            "surface": onboarding_surface,
        },
        "scenario": export_scenario(STARTER_SCENARIO),
        "encounter": simulate_encounter(),
    }
    # Fail closed here, at build time: a blueprint that does not satisfy the
    # contract must never reach the browser as "valid" data.
    validate_agentsurface_v01(data["onboarding"]["surface"], root="root")
    for scene_id, entry in data["scenario"]["scenes"].items():
        validate_agentsurface_v01(entry["blueprint"], root="root")
        assert scene_id, "scene ids must be non-empty"
    validate_agentsurface_v01(data["encounter"]["surface"], root="root")
    return data


def write_demo_data(path: str = OUTPUT_PATH) -> str:
    """Write the demo payload as deterministic, sorted JSON."""
    payload = json.dumps(build_demo_data(), indent=2, sort_keys=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(payload + "\n")
    return path


if __name__ == "__main__":
    print(f"wrote {write_demo_data()}")

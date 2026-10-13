"""Interactive Generative TUI Runner for AI Dungeon Master.

Displays an ANSI-based generative terminal interface (Leaf / Television style)
incorporating real-time tactical maps, dynamic DM narrative feeds, health bars,
action economy badges, conditions, and procedural audio synthesis triggers.
"""

from __future__ import annotations

import time

from audio_synth import (
    calculate_encounter_tension,
    default_audio_dir,
    generate_all_sfx,
)
from d20_rules import (
    ActionEconomy,
    AdvantageMode,
    CoverType,
    DamageType,
    RestType,
    resolve_attack,
    resolve_rest,
)
from encounter_ai import CombatActionType, EncounterEnemy
from genui import ANSI, GenUIBlueprintFactory, TerminalSurfaceRenderer


def run_tui_encounter(interactive: bool = False, max_rounds: int = 6):
    audio_dir = default_audio_dir()
    generate_all_sfx(audio_dir)

    hero_name = "Kaelen the Paladin"
    hero_max_hp = 35
    hero_hp = 35
    hero_conditions = []
    hero_economy = ActionEconomy(movement_speed=30.0)

    enemy = EncounterEnemy(name="Shadow Gargoyle", max_hp=30, ac=14, spell_slots=2)
    enemy_distance = 6.0  # 6 units = 30 ft
    combat_log = [
        "You step into the ancient submerged crypt. Cold drops echo from stalactites.",
        f"A sinister {enemy.name} descends from the vaulted ceiling! Initiative rolls!",
    ]

    print(f"\n{ANSI.BOLD}{ANSI.FG_GOLD}══════════════════════════════════════════════════════════════════{ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.FG_GOLD}   ⚔️  AI DUNGEON MASTER : GENERATIVE SURFACE TUI (LEAF/TV MODE)  ⚔️{ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.FG_GOLD}══════════════════════════════════════════════════════════════════{ANSI.RESET}\n")

    for round_num in range(1, max_rounds + 1):
        hero_economy.reset_turn()
        tension = calculate_encounter_tension(
            enemy_hp_pct=enemy.current_hp / enemy.max_hp,
            player_hp_pct=hero_hp / hero_max_hp,
            round_number=round_num,
        )

        # 1. Render Tactical Map
        hero_x = 2
        enemy_x = min(11, max(3, int(hero_x + enemy_distance)))
        grid_lines = TerminalSurfaceRenderer.render_tactical_grid(
            width=12,
            height=5,
            hero_pos=(hero_x, 2),
            enemy_pos=(enemy_x, 2),
            cover_positions=[(5, 1), (5, 2), (6, 3)],
            biome="Crypt of the Forgotten",
        )

        # 2. Render Status & Feed Panels
        hero_bar = TerminalSurfaceRenderer.render_health_bar(hero_hp, hero_max_hp, 14)
        enemy_bar = TerminalSurfaceRenderer.render_health_bar(enemy.current_hp, enemy.max_hp, 14)

        status_lines = [
            f"{ANSI.BOLD}Round {round_num}{ANSI.RESET} │ Tension: {int(tension * 100)}% │ Enemy Stance: {ANSI.FG_PURPLE}{enemy.stance.value}{ANSI.RESET}",
            f"{hero_name}: {hero_bar}",
            f"{enemy.name}: {enemy_bar}",
            f"Actions: [Action: {'✓' if hero_economy.has_action else '✗'}] [Bonus: {'✓' if hero_economy.has_bonus_action else '✗'}] [Reaction: {'✓' if hero_economy.has_reaction else '✗'}] Move: {hero_economy.movement_remaining:.0f}ft",
        ]

        tactical_panel = "\n".join(grid_lines)
        status_panel = TerminalSurfaceRenderer.render_panel("COMBAT STATUS", status_lines, width=64, color=ANSI.CYAN)
        feed_panel = TerminalSurfaceRenderer.render_panel("CHRONICLE FEED", combat_log[-3:], width=64, color=ANSI.FG_GOLD)

        print(tactical_panel)
        print(status_panel)
        print(feed_panel)

        # Also emit a declarative GenUI JSON blueprint sample for cross-platform clients
        blueprint = GenUIBlueprintFactory.create_encounter_surface(
            surface_id=f"encounter-round-{round_num}",
            title="Dungeon Crypt Encounter",
            round_num=round_num,
            hero_name=hero_name,
            hero_hp=hero_hp,
            hero_max_hp=hero_max_hp,
            hero_conditions=hero_conditions,
            hero_actions_available={"Action": hero_economy.has_action, "BonusAction": hero_economy.has_bonus_action, "Reaction": hero_economy.has_reaction},
            enemy_name=enemy.name,
            enemy_hp=enemy.current_hp,
            enemy_max_hp=enemy.max_hp,
            enemy_stance=enemy.stance.value,
            combat_log=combat_log,
            tension_level=tension,
        )

        # Player Action Phase
        if hero_economy.has_action:
            hero_economy.use_action()
            # If distance is large, hero closes in
            if enemy_distance > 1.0:
                enemy_distance = max(1.0, enemy_distance - 3.0)
                combat_log.append(f"{hero_name} dashes forward, closing distance to {enemy_distance * 5:.0f} ft.")

            # Attack resolution with 5e rules
            res = resolve_attack(
                attacker=hero_name,
                target=enemy.name,
                attack_modifier=6,
                target_ac=enemy.ac,
                damage_dice_count=1,
                damage_die_sides=8,
                damage_modifier=3,
                damage_type=DamageType.SLASHING,
                advantage=AdvantageMode.NORMAL,
                cover=CoverType.HALF if enemy_distance > 2.0 else CoverType.NONE,
            )
            combat_log.append(res.combat_message)
            if res.is_hit:
                enemy.apply_damage(res.damage_dealt)

        # Check enemy death
        if enemy.current_hp <= 0:
            combat_log.append(f"⚔️ {enemy.name} collapses in shattered stone shards! VICTORY!")
            print(TerminalSurfaceRenderer.render_panel("ENCOUNTER RESOLUTION", combat_log[-2:], width=64, color=ANSI.FG_EMERALD))
            break

        # Enemy Action Phase
        enemy_decision = enemy.decide_turn_action(distance_to_player=enemy_distance)
        if enemy_decision.action == CombatActionType.FLEE:
            combat_log.append(enemy_decision.rationale)
            print(TerminalSurfaceRenderer.render_panel("ENCOUNTER RESOLUTION", combat_log[-2:], width=64, color=ANSI.YELLOW))
            break
        elif enemy_decision.action == CombatActionType.DODGE:
            combat_log.append(enemy_decision.rationale)
        elif enemy_decision.action in (CombatActionType.MELEE, CombatActionType.RANGED, CombatActionType.SPELL):
            enemy_res = resolve_attack(
                attacker=enemy.name,
                target=hero_name,
                attack_modifier=enemy_decision.attack_modifier,
                target_ac=16,
                damage_dice_count=enemy_decision.damage_dice_count,
                damage_die_sides=enemy_decision.damage_die_sides,
                damage_modifier=enemy_decision.damage_modifier,
                damage_type=enemy_decision.damage_type,
            )
            combat_log.append(f"{enemy_decision.action_name}: {enemy_res.combat_message}")
            if enemy_res.is_hit:
                hero_hp = max(0, hero_hp - enemy_res.damage_dealt)

        if hero_hp <= 0:
            combat_log.append(f"💀 {hero_name} falls unconscious in the subterranean dark! DEFEAT!")
            print(TerminalSurfaceRenderer.render_panel("ENCOUNTER RESOLUTION", combat_log[-2:], width=64, color=ANSI.FG_CRIMSON))
            break

        time.sleep(0.05)

    # Post-encounter: Demonstrate Short Rest recovery
    rest_result = resolve_rest(
        character_name=hero_name,
        rest_type=RestType.SHORT,
        current_hp=hero_hp,
        max_hp=hero_max_hp,
        hit_dice_available=3,
        total_hit_dice=3,
        hit_die_sides=10,
        con_modifier=2,
        current_spell_slots=1,
        max_spell_slots=2,
    )
    print(f"\n{ANSI.CYAN}🏕️ {rest_result.summary}{ANSI.RESET}\n")
    return blueprint


def main() -> None:
    """Console-script entry point.

    A ``console_scripts`` wrapper exits with ``sys.exit(main())``, so this must
    return ``None``: returning the ``SurfaceBlueprint`` would make ``sys.exit``
    treat the object as a failure message and exit non-zero.
    """
    run_tui_encounter()


if __name__ == "__main__":
    main()

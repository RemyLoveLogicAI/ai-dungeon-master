"""
engine/dm_tui.py
Ultra-lightweight terminal TUI cockpit for Aegis AI Dungeon Master.
Runs in zero-overhead ANSI terminal mode with ASCII tactical grid, audio cues, and live DM narration.
"""

import sys

from engine.story_engine import StoryEngine


def clear_screen():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def print_banner(world_name: str, location_name: str, tension: int):
    print("\033[1;36m" + "=" * 70 + "\033[0m")
    print(f"\033[1;35m  ⚔  AEGIS DUNGEON MASTER COCKPIT  ⚔\033[0m  |  World: \033[1;33m{world_name}\033[0m")
    print(f"  Location: \033[1;32m{location_name}\033[0m  |  Tension: \033[1;31m[{'█' * (tension // 10)}{' ' * (10 - tension // 10)}] {tension}%\033[0m")
    print("\033[1;36m" + "=" * 70 + "\033[0m\n")


def print_ascii_grid(grid_state):
    if not grid_state:
        return
    print("\033[1;33m[TACTICAL COMBAT MATRIX]\033[0m (Round " + str(grid_state.round_number) + ")")
    print("  " + " ".join(str(i) for i in range(grid_state.width)))
    matrix = [["." for _ in range(grid_state.width)] for _ in range(grid_state.height)]
    for c in grid_state.combatants:
        marker = "\033[1;32mH\033[0m" if c.is_player else "\033[1;31mE\033[0m"
        matrix[c.y][c.x] = marker

    for y, row in enumerate(matrix):
        print(f"{y} " + " ".join(row))
    print()


def run_tui():
    engine = StoryEngine()
    clear_screen()
    
    first_loc = engine.get_current_location()
    print_banner(engine.world.name, first_loc.name, engine.tension_curve)
    print(f"\033[1;37m{engine.narrative_history[0]['text']}\033[0m\n")
    
    current_ui = engine.process_turn("survey the sanctum")

    while True:
        curr_loc = engine.get_current_location()
        print("\033[1;34m[GENERATIVE ACTION DECK]\033[0m")
        for i, card in enumerate(current_ui.action_deck, 1):
            risk_color = "\033[32m" if card.risk_level == "Low" else "\033[33m" if card.risk_level == "Medium" else "\033[31m"
            print(f"  [{i}] \033[1m{card.title}\033[0m ({card.category.value}) - Risk: {risk_color}{card.risk_level}\033[0m")
            print(f"      {card.description}")
        print("  [C] Custom action (type anything to the DM)")
        print("  [M] View World Atlas")
        print("  [Q] Exit Cockpit\n")

        try:
            choice = input("\033[1;32m[Player] > \033[0m").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting cockpit.")
            break

        if not choice:
            continue
        if choice.lower() == "q":
            print("Session suspended.")
            break
        elif choice.lower() == "m":
            clear_screen()
            print_banner(engine.world.name, curr_loc.name, engine.tension_curve)
            print("\033[1;35m--- REALM ATLAS & LOCATIONS ---\033[0m")
            for loc in engine.world.locations:
                disc = "Discovered" if loc.discovered else "Uncharted"
                active = " (YOU ARE HERE)" if loc.id == engine.world.current_location_id else ""
                print(f"  • {loc.name} [{loc.biome}] - Threat Tier {loc.threat_tier} [{disc}]{active}")
            input("\nPress Enter to resume...")
            clear_screen()
            print_banner(engine.world.name, curr_loc.name, engine.tension_curve)
            continue
        elif choice.lower() == "c":
            custom_prompt = input("\033[1;33mDescribe your action to the DM > \033[0m").strip()
            action_text = custom_prompt if custom_prompt else "look around"
        elif choice.isdigit() and 1 <= int(choice) <= len(current_ui.action_deck):
            chosen_card = current_ui.action_deck[int(choice) - 1]
            action_text = f"{chosen_card.title}: {chosen_card.description}"
        else:
            action_text = choice

        # Process Turn
        clear_screen()
        current_ui = engine.process_turn(action_text)
        print_banner(engine.world.name, current_ui.location_name, current_ui.tension_level)

        if current_ui.tactical_grid:
            print_ascii_grid(current_ui.tactical_grid)

        print("\033[1;37m" + current_ui.narrative_text + "\033[0m\n")

        if current_ui.loot:
            print("\033[1;33m★ RECOVERED SPOILS ★\033[0m")
            for loot in current_ui.loot:
                print(f"  • {loot.name} [{loot.rarity} {loot.item_type}] - {loot.stats_summary}")
            print()


if __name__ == "__main__":
    run_tui()

from audio_synth import default_audio_dir, generate_all_sfx
from d20_rules import AdvantageMode, DamageType, resolve_attack
from encounter_ai import CombatActionType, EncounterEnemy


def run_simulated_encounter():
    print("=" * 60)
    print("      AI DUNGEON MASTER: D20 TACTICAL COMBAT ENGINE        ")
    print("=" * 60)

    # 1. Generate SFX assets into a writable cache dir. Never the package dir:
    # an installed wheel lives in site-packages, which may be read-only.
    audio_dir = default_audio_dir()
    sfx_paths = generate_all_sfx(audio_dir)
    print(f"[*] Procedural audio SFX initialized in {audio_dir}")

    # 2. Combatants
    player_name = "Paladin Alden"
    player_max_hp = 38
    player_hp = player_max_hp
    player_ac = 16
    player_attack_mod = 5
    
    enemy = EncounterEnemy("Shadow Gargoyle", max_hp=35, ac=14, spell_slots=2)
    distance = 4.0 # meters

    print("[*] Encounter started:")
    print(f"    Player: {player_name} (HP {player_hp}, AC {player_ac})")
    print(f"    Enemy:  {enemy.name} (HP {enemy.current_hp}, AC {enemy.ac}, Stance: {enemy.stance.value})")
    print("-" * 60)

    round_num = 1
    while player_hp > 0 and enemy.current_hp > 0:
        print(f"\n--- ROUND {round_num} (Distance: {distance:.1f}m) ---")

        # Player Turn
        print(f"\n[Turn: {player_name}]")
        res = resolve_attack(
            attacker=player_name,
            target=enemy.name,
            attack_modifier=player_attack_mod,
            target_ac=enemy.ac,
            damage_dice_count=1,
            damage_die_sides=8,
            damage_modifier=3,
            damage_type=DamageType.SLASHING,
            advantage=AdvantageMode.NORMAL
        )
        print(res.combat_message)

        if res.is_hit:
            enemy.apply_damage(res.damage_dealt)
            if res.is_critical:
                print(f"  [AUDIO TRIGGER: {sfx_paths['crit_fanfare']}]")
            else:
                print(f"  [AUDIO TRIGGER: {sfx_paths['sword_clash']}]")
        else:
            print(f"  [AUDIO TRIGGER: {sfx_paths['dice_roll']}]")

        print(f"  -> {enemy.name} HP: {enemy.current_hp}/{enemy.max_hp} (Stance: {enemy.stance.value})")

        if enemy.current_hp <= 0:
            print(f"\nVICTORY! {enemy.name} has been defeated by {player_name}!")
            break

        # Enemy Turn
        print(f"\n[Turn: {enemy.name}]")
        decision = enemy.decide_turn_action(distance)
        print(f"  AI Rationale: {decision.rationale}")

        if decision.action == CombatActionType.FLEE:
            print(f"  -> {enemy.name} breaks engagement and flees into the shadows!")
            break
        elif decision.action == CombatActionType.DODGE:
            print(f"  -> {enemy.name} readies defensive stance.")
        else:
            # Attack
            e_res = resolve_attack(
                attacker=enemy.name,
                target=player_name,
                attack_modifier=decision.attack_modifier,
                target_ac=player_ac,
                damage_dice_count=decision.damage_dice_count,
                damage_die_sides=decision.damage_die_sides,
                damage_modifier=decision.damage_modifier,
                damage_type=decision.damage_type
            )
            print(f"  {e_res.combat_message}")
            if e_res.is_hit:
                player_hp -= e_res.damage_dealt
                if decision.damage_type == DamageType.FIRE:
                    print(f"  [AUDIO TRIGGER: {sfx_paths['fireball_impact']}]")
                else:
                    print(f"  [AUDIO TRIGGER: {sfx_paths['sword_clash']}]")
            print(f"  -> {player_name} HP: {max(0, player_hp)}/{player_max_hp}")

        # Engage distance adjusts
        if distance > 1.5:
            distance = max(1.0, distance - 1.5)

        round_num += 1

    # The loop ends on victory, on the enemy fleeing, or when the player falls.
    # Victory and fleeing print as they happen; a dead player is the silent exit,
    # so it has to be reported here or the outcome is indistinguishable.
    if player_hp <= 0:
        print(f"\nDEFEAT! {player_name} has fallen to {enemy.name}!")

    print("\n" + "=" * 60)
    print("                 ENCOUNTER CONCLUDED                      ")
    print("=" * 60)

if __name__ == "__main__":
    run_simulated_encounter()

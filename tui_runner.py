"""Interactive Generative TUI Runner for AI Dungeon Master.

Displays an ANSI-based generative terminal interface (Leaf / Television style)
incorporating real-time tactical maps, dynamic DM narrative feeds, health bars,
action economy badges, conditions, and procedural audio synthesis triggers.

Every attack is committed to a durable ``combat-encounter-log/1`` envelope, and a
saved encounter can be resumed: ``dungeon-master-tui --log encounter.json`` saves,
``dungeon-master-tui --log encounter.json --resume`` reads the envelope back
through the strict boundary, re-derives the state it describes, and continues the
encounter with contiguous sequence numbers.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from audio_synth import (
    calculate_encounter_tension,
    default_audio_dir,
    generate_all_sfx,
)
from combat_log import (
    CombatLog,
    CombatLogEntry,
    default_log_dir,
    load_log,
    record_entry,
    save_log,
    verify_log,
)
from combat_schema import SchemaUnavailableError
from d20_rules import (
    ActionEconomy,
    AdvantageMode,
    AttackRequest,
    CoverType,
    DamageType,
    DiceSource,
    RestType,
    SeededDiceSource,
    resolve_rest,
)
from encounter_ai import CombatActionType, EncounterEnemy
from genui import ANSI, GenUIBlueprintFactory, TerminalSurfaceRenderer

HERO_NAME = "Kaelen the Paladin"
HERO_MAX_HP = 35
HERO_AC = 16
HERO_ATTACK_MODIFIER = 6
ENEMY_NAME = "Shadow Gargoyle"
ENEMY_MAX_HP = 30
ENEMY_AC = 14
ENEMY_SPELL_SLOTS = 2
HERO_ATTACK_DAMAGE_DICE = 1
HERO_ATTACK_DIE_SIDES = 8
HERO_ATTACK_DAMAGE_MODIFIER = 3

#: Units of 5 ft. The hero starts this far away and closes ground each turn.
START_DISTANCE = 6.0
DASH_PER_ROUND = 3.0

DEFAULT_LOG_FILENAME = "tui-encounter.json"

#: What a saved log cannot describe, reported to the player on resume rather
#: than papered over. Each entry is a real gap: the envelope records resolved
#: attacks, and nothing about the fiction or the resource bookkeeping around
#: them.
RESUME_NOTES = (
    "spell slots are counted back from the recorded attacks, not stored",
    "enemy narrative lines are not in the envelope, so the feed is rebuilt from messages",
    "the hero's conditions and action economy reset each round and are not stored",
)


def close_distance(distance: float) -> float:
    """Where the hero's dash leaves the distance at the start of a turn."""
    if distance <= 1.0:
        return distance
    return max(1.0, distance - DASH_PER_ROUND)


def cover_for(distance: float) -> CoverType:
    """The cover the enemy presents at ``distance``."""
    return CoverType.HALF if distance > 2.0 else CoverType.NONE


def next_sequence(dropped: int, entries: list[CombatLogEntry]) -> int:
    """The sequence number of the next entry to append to a log tail.

    Retention can shed the head of a log, so the next number is derived from what
    was dropped plus what is retained. A ``CombatLog`` is a contiguous tail, and
    appending here is what keeps it one.
    """
    return dropped + len(entries) + 1


def infer_spent_spell_slots(log: CombatLog) -> int:
    """Count the enemy's spent spell slots from the attacks it recorded.

    The encounter AI casts exactly one spell, and that spell is the only action
    dealing FIRE damage, so each recorded FIRE attack is one spent slot. The
    uniqueness is asserted against the decision table in ``test_tui_resume.py``,
    so a future decision that broke the rule would fail a test rather than
    silently corrupt a resume.
    """
    return sum(
        1
        for entry in log.entries
        if entry.event.request.attacker == ENEMY_NAME
        and entry.event.request.damage_type is DamageType.FIRE
    )


@dataclass(frozen=True)
class ResumedEncounter:
    """The encounter state a saved log describes, and the gaps it leaves."""

    round_num: int
    hero_hp: int
    enemy_hp: int
    distance: float
    spell_slots: int
    feed: tuple[str, ...]
    notes: tuple[str, ...] = RESUME_NOTES


def read_resumed_state(log: CombatLog) -> ResumedEncounter:
    """Rebuild the encounter state a saved log describes.

    Replays the stored results in order to recover hit points, distance, the next
    round, and the enemy's remaining slots. Only the recorded numbers are used,
    so this stays exact without access to the generator that produced them.

    Raises ``ValueError`` for a log that is not this encounter (a foreign
    campaign's attacks) and for one that has already concluded, which is not a
    session that can be continued.
    """
    hero_hp = HERO_MAX_HP
    enemy_hp = ENEMY_MAX_HP
    distance = START_DISTANCE
    rounds = 0
    feed: list[str] = []

    for entry in log.entries:
        request = entry.event.request
        result = entry.result
        if request.attacker == HERO_NAME and request.target == ENEMY_NAME:
            rounds += 1
            closed = close_distance(distance)
            if closed != distance:
                feed.append(
                    f"{HERO_NAME} dashes forward, closing distance to {closed * 5:.0f} ft."
                )
                distance = closed
            if result.is_hit:
                enemy_hp = max(0, enemy_hp - result.damage_dealt)
            feed.append(result.message)
        elif request.attacker == ENEMY_NAME and request.target == HERO_NAME:
            if result.is_hit:
                hero_hp = max(0, hero_hp - result.damage_dealt)
            feed.append(result.message)
        else:
            raise ValueError(
                f"log entry {entry.event.sequence} records a {request.attacker!r} -> "
                f"{request.target!r} attack, which is not part of a {HERO_NAME!r} "
                "encounter; this saved log cannot be resumed here"
            )

    if enemy_hp <= 0:
        raise ValueError(
            f"the saved encounter already ended in victory over {ENEMY_NAME}; "
            "there is nothing left to resume"
        )
    if hero_hp <= 0:
        raise ValueError(
            f"the saved encounter already ended in defeat for {HERO_NAME}; "
            "there is nothing left to resume"
        )

    return ResumedEncounter(
        round_num=rounds + 1,
        hero_hp=hero_hp,
        enemy_hp=enemy_hp,
        distance=distance,
        spell_slots=max(0, ENEMY_SPELL_SLOTS - infer_spent_spell_slots(log)),
        feed=tuple(feed),
    )


def run_tui_encounter(
    interactive: bool = False,
    max_rounds: int = 6,
    *,
    log_path: str | Path | None = None,
    resume: bool = False,
    validate_schema: bool = False,
    overwrite: bool = False,
    dice: DiceSource | None = None,
):
    """Run the encounter, optionally persisting it and continuing a saved one.

    ``log_path`` makes the run durable: the envelope is rewritten at the end of
    every round, so an interrupted session is resumable. ``resume`` continues the
    encounter saved at ``log_path`` instead of starting a new one — an existing
    log is never overwritten by accident, and a log that does not replay is
    refused rather than continued from. ``validate_schema`` checks every read
    against the published JSON Schema in addition to the in-repo readers.
    """
    audio_dir = default_audio_dir()
    generate_all_sfx(audio_dir)

    hero_name = HERO_NAME
    hero_max_hp = HERO_MAX_HP
    hero_hp = hero_max_hp
    hero_conditions = []
    hero_economy = ActionEconomy(movement_speed=30.0)

    target = None if log_path is None else Path(log_path)
    entries: list[CombatLogEntry] = []
    dropped = 0
    enemy_distance = START_DISTANCE
    enemy_slots = ENEMY_SPELL_SLOTS
    feed = [
        "You step into the ancient submerged crypt. Cold drops echo from stalactites.",
        f"A sinister {ENEMY_NAME} descends from the vaulted ceiling! Initiative rolls!",
    ]
    round_num = 1
    state: ResumedEncounter | None = None

    if resume:
        if target is None:
            raise ValueError("resuming an encounter requires a log path")
        saved = load_log(target, validate_schema=validate_schema)
        if not verify_log(saved):
            raise ValueError(
                f"{target} does not replay from its own recorded dice; refusing to "
                "continue an encounter whose history is not trustworthy"
            )
        state = read_resumed_state(saved)
        entries = list(saved.entries)
        dropped = saved.dropped
        hero_hp = state.hero_hp
        enemy_distance = state.distance
        enemy_slots = state.spell_slots
        round_num = state.round_num
        feed = list(state.feed)
    elif target is not None and target.exists() and not overwrite:
        raise ValueError(
            f"{target} already holds a saved encounter; pass resume=True to continue "
            "it, or overwrite=True to replace it"
        )

    enemy = EncounterEnemy(
        name=ENEMY_NAME, max_hp=ENEMY_MAX_HP, ac=ENEMY_AC, spell_slots=enemy_slots
    )
    if state is not None:
        enemy.current_hp = state.enemy_hp
        enemy.update_stance()
        feed.append(f"── resumed from {target} at round {state.round_num} ──")

    print(f"\n{ANSI.BOLD}{ANSI.FG_GOLD}══════════════════════════════════════════════════════════════════{ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.FG_GOLD}   ⚔️  AI DUNGEON MASTER : GENERATIVE SURFACE TUI (LEAF/TV MODE)  ⚔️{ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.FG_GOLD}══════════════════════════════════════════════════════════════════{ANSI.RESET}\n")

    if state is not None:
        print(
            f"{ANSI.FG_GOLD}▶ RESUMED{ANSI.RESET} round {state.round_num} │ "
            f"{hero_name}: {state.hero_hp}/{hero_max_hp} HP │ "
            f"{enemy.name}: {state.enemy_hp}/{enemy.max_hp} HP │ "
            f"distance {state.distance * 5:.0f} ft │ "
            f"{enemy.name} slots: {state.spell_slots}/{ENEMY_SPELL_SLOTS}"
        )
        for note in state.notes:
            print(f"{ANSI.DIM}  · rebuilt, not stored: {note}{ANSI.RESET}")
        print()

    blueprint = None
    first_round = round_num  # a resumed encounter starts where its log left off
    for round_num in range(first_round, first_round + max_rounds):
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
        feed_panel = TerminalSurfaceRenderer.render_panel("CHRONICLE FEED", feed[-3:], width=64, color=ANSI.FG_GOLD)

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
            combat_log=feed,
            tension_level=tension,
        )

        # Player Action Phase
        if hero_economy.has_action:
            hero_economy.use_action()
            # If distance is large, hero closes in
            closed = close_distance(enemy_distance)
            if closed != enemy_distance:
                enemy_distance = closed
                feed.append(f"{hero_name} dashes forward, closing distance to {enemy_distance * 5:.0f} ft.")

            # Attack resolution with 5e rules, committed to the durable log
            player_request = AttackRequest(
                attacker=hero_name,
                target=enemy.name,
                attack_modifier=HERO_ATTACK_MODIFIER,
                target_ac=enemy.ac,
                damage_dice_count=HERO_ATTACK_DAMAGE_DICE,
                damage_die_sides=HERO_ATTACK_DIE_SIDES,
                damage_modifier=HERO_ATTACK_DAMAGE_MODIFIER,
                damage_type=DamageType.SLASHING,
                advantage=AdvantageMode.NORMAL,
                cover=cover_for(enemy_distance),
            )
            player_entry, res = record_entry(
                player_request, sequence=next_sequence(dropped, entries), dice=dice
            )
            entries.append(player_entry)
            feed.append(res.combat_message)
            if res.is_hit:
                enemy.apply_damage(res.damage_dealt)

        # Check enemy death
        if enemy.current_hp <= 0:
            feed.append(f"⚔️ {enemy.name} collapses in shattered stone shards! VICTORY!")
            print(TerminalSurfaceRenderer.render_panel("ENCOUNTER RESOLUTION", feed[-2:], width=64, color=ANSI.FG_EMERALD))
            break

        # Enemy Action Phase
        enemy_decision = enemy.decide_turn_action(distance_to_player=enemy_distance)
        if enemy_decision.action == CombatActionType.FLEE:
            feed.append(enemy_decision.rationale)
            print(TerminalSurfaceRenderer.render_panel("ENCOUNTER RESOLUTION", feed[-2:], width=64, color=ANSI.YELLOW))
            break
        elif enemy_decision.action == CombatActionType.DODGE:
            feed.append(enemy_decision.rationale)
        elif enemy_decision.action in (CombatActionType.MELEE, CombatActionType.RANGED, CombatActionType.SPELL):
            # Committing the turn to the enemy spends any slot it decided to use.
            enemy.commit_decision(enemy_decision)
            enemy_request = AttackRequest(
                attacker=enemy.name,
                target=hero_name,
                attack_modifier=enemy_decision.attack_modifier,
                target_ac=HERO_AC,
                damage_dice_count=enemy_decision.damage_dice_count,
                damage_die_sides=enemy_decision.damage_die_sides,
                damage_modifier=enemy_decision.damage_modifier,
                damage_type=enemy_decision.damage_type,
            )
            enemy_entry, enemy_res = record_entry(
                enemy_request, sequence=next_sequence(dropped, entries), dice=dice
            )
            entries.append(enemy_entry)
            feed.append(f"{enemy_decision.action_name}: {enemy_res.combat_message}")
            if enemy_res.is_hit:
                hero_hp = max(0, hero_hp - enemy_res.damage_dealt)

        if hero_hp <= 0:
            feed.append(f"💀 {hero_name} falls unconscious in the subterranean dark! DEFEAT!")
            print(TerminalSurfaceRenderer.render_panel("ENCOUNTER RESOLUTION", feed[-2:], width=64, color=ANSI.FG_CRIMSON))
            break

        # Durability point: a crash mid-round costs at most this round, and the
        # saved tail stays contiguous with what a resume will rebuild.
        if target is not None:
            save_log(CombatLog(entries=tuple(entries), dropped=dropped), target)

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

    log = CombatLog(entries=tuple(entries), dropped=dropped)
    if len(log):
        replay_status = "OK" if verify_log(log) else "MISMATCH"
        print(f"[Replay] {len(log)} attack events replayed deterministically: {replay_status}")

    if target is not None:
        # The log was written at each round end; this final write covers a round
        # that ended the encounter, and re-reads it through the strict boundary.
        written = save_log(log, target)
        restored = load_log(written, validate_schema=validate_schema)
        reload_status = "OK" if verify_log(restored) else "MISMATCH"
        scope = "schema + readers" if validate_schema else "readers"
        print(
            f"[Log] {len(restored)} entries written to {written} and verified on reload "
            f"({scope}): {reload_status}"
        )
        print(f"[Resume] continue this encounter: dungeon-master-tui --log {written} --resume")

    return blueprint


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the console-script argument parser."""
    parser = argparse.ArgumentParser(
        prog="dungeon-master-tui",
        description=(
            "Run the generative terminal encounter, optionally saving it to a durable "
            "log and resuming a saved one."
        ),
        allow_abbrev=False,
    )
    parser.add_argument(
        "--log",
        metavar="PATH",
        default=None,
        help=(
            "path to the durable encounter log; the run is saved there and can be "
            "resumed later. Without it nothing is written, except that --resume falls "
            f"back to {DEFAULT_LOG_FILENAME} in {default_log_dir()}"
        ),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="continue the encounter saved in --log instead of starting a new one",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="start a new encounter even if --log already holds a saved one",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=6,
        metavar="N",
        help="maximum number of rounds to play (default: 6)",
    )
    parser.add_argument(
        "--validate-schema",
        action="store_true",
        help=(
            "check every log read against the published JSON Schema as well as the "
            "in-repo readers (needs the jsonschema package)"
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        metavar="N",
        help="seed the dice so a run is reproducible",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """Console-script entry point.

    A ``console_scripts`` wrapper exits with ``sys.exit(main())``, so this must
    return ``None``: returning the ``SurfaceBlueprint`` would make ``sys.exit``
    treat the object as a failure message and exit non-zero.
    """
    parser = build_arg_parser()
    # Unrecognized arguments are reported, not fatal: a host process that injects
    # its own argv (a test runner, an embedding app) must not break the entry
    # point, and a mistyped flag is still surfaced instead of silently ignored.
    args, extras = parser.parse_known_args(argv)
    if extras:
        print(f"[tui] ignoring unrecognized argument(s): {' '.join(extras)}", file=sys.stderr)

    target = args.log
    if args.resume and target is None:
        target = str(Path(default_log_dir()) / DEFAULT_LOG_FILENAME)

    try:
        run_tui_encounter(
            max_rounds=args.rounds,
            log_path=target,
            resume=args.resume,
            validate_schema=args.validate_schema,
            overwrite=args.overwrite,
            dice=None if args.seed is None else SeededDiceSource(args.seed),
        )
    except (ValueError, OSError, SchemaUnavailableError) as exc:
        # A bad log path, an untrustworthy log, or a schema check with no
        # validator installed is a usage error, not a traceback.
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()

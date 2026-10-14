"""
engine/story_engine.py
Agentic AI Dungeon Master story generator and game state manager.
Connects with local Ollama LLMs and includes an instant offline procedural DM engine.
"""

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from d20_rules import AdvantageMode, DamageType, resolve_attack
from encounter_ai import CombatActionType, EncounterEnemy
from engine.generative_ui import (
    ActionCategory,
    GenerativeActionCard,
    GenerativeUIPackage,
    GridCombatant,
    LootItem,
    NPCPreset,
    SoundtrackDirective,
    TacticalGridState,
)
from engine.world_generator import LocationNode, WorldState, generate_procedural_world

logger = logging.getLogger("DungeonMaster")


@dataclass
class PlayerCharacter:
    name: str = "Paladin Alden"
    class_title: str = "Oath of Dawn Crusader"
    max_hp: int = 40
    current_hp: int = 40
    ac: int = 16
    attack_bonus: int = 5
    spell_slots: int = 3
    max_spell_slots: int = 3
    level: int = 4
    inventory: list[str] = field(
        default_factory=lambda: [
            "Sunforged Longsword (+1)",
            "Radiant Shield",
            "Potion of Superior Healing (x2)",
            "Runic Compass",
        ]
    )
    gold: int = 145


class StoryEngine:
    def __init__(self, ollama_url: str = "http://127.0.0.1:11434", default_model: str = "llama3.2:3b"):
        self.ollama_url = ollama_url
        self.default_model = default_model
        self.world: WorldState = generate_procedural_world(seed=1337)
        self.player: PlayerCharacter = PlayerCharacter()
        self.narrative_history: list[dict[str, str]] = []
        self.active_combat_enemy: EncounterEnemy | None = None
        self.active_combat_grid: TacticalGridState | None = None
        self.active_npc: NPCPreset | None = None
        self.tension_curve: int = 25  # 0 to 100
        self.turn_count: int = 0
        self._initialize_story()

    def _initialize_story(self):
        curr_loc = self.get_current_location()
        welcome_narrative = (
            f"The embers crackle beneath the iron braziers of {curr_loc.name}. Outside the sanctum walls, "
            f"the twin auroras of {self.world.name} cast a pale amethyst hue across the sky.\n\n"
            f"Archivist Sylas unrolls a weathered parchment of the realm: 'The stone sentinels in Sector F have stirred. "
            f"If the Gargoyle Roost falls under Covenant control, our sanctuary falls with it.'\n"
            f"Your hand grips the hilt of your Sunforged Longsword. The path forward begins now."
        )
        self.narrative_history.append({"speaker": "DM", "text": welcome_narrative})

    def get_current_location(self) -> LocationNode:
        for loc in self.world.locations:
            if loc.id == self.world.current_location_id:
                return loc
        return self.world.locations[0]

    def check_ollama_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.ollama_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return resp.status == 200
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    def list_ollama_models(self) -> list[str]:
        try:
            req = urllib.request.Request(f"{self.ollama_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode())
                return [m["name"] for m in data.get("models", [])]
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            return []

    def _generate_procedural_response(self, user_intent: str) -> GenerativeUIPackage:
        """Heuristic offline Generative DM — produces narrative, UI cards, combat, audio directives."""
        self.turn_count += 1
        curr_loc = self.get_current_location()
        lower_intent = user_intent.lower()

        # Check for combat initiation or ongoing combat
        if "attack" in lower_intent or "strike" in lower_intent or "fight" in lower_intent or self.active_combat_enemy:
            return self._handle_combat_turn(user_intent)

        # Check for dialogue / interaction
        if "talk" in lower_intent or "speak" in lower_intent or "ask" in lower_intent or "negotiate" in lower_intent:
            return self._handle_dialogue(user_intent)

        # Check for exploration / travel
        if "travel" in lower_intent or "explore" in lower_intent or "investigate" in lower_intent or "move" in lower_intent:
            return self._handle_exploration(user_intent)

        # Default dynamic scene progression
        self.tension_curve = min(100, self.tension_curve + 5)
        narrative = (
            f"You {user_intent.strip()}.\n\n"
            f"A chill wind courses through the arches of {curr_loc.name}. The ambient ether vibrates with dormant magic. "
            f"You notice strange claw gouges etched deep into the stonework, pulsing with faint purple residue. "
            f"The danger tier here is rated Tier {curr_loc.threat_tier}."
        )

        actions = [
            GenerativeActionCard(
                id="act_investigate",
                title="Investigate Arcane Gouges",
                description="Make an Investigation check to decipher the runic markings.",
                category=ActionCategory.SKILL_CHECK,
                dc_target=13,
                modifier=2,
                ability_stat="INT",
                risk_level="Low",
                icon_name="search",
            ),
            GenerativeActionCard(
                id="act_scout_ahead",
                title="Advance to Shadow Perch",
                description="Sneak forward to survey the upper ramparts.",
                category=ActionCategory.EXPLORATION,
                dc_target=14,
                modifier=3,
                ability_stat="DEX",
                risk_level="Medium",
                icon_name="compass",
            ),
            GenerativeActionCard(
                id="act_ready_weapon",
                title="Draw Weapon & Challenge the Dark",
                description="Call out to provoke whatever stalks the ruins.",
                category=ActionCategory.ATTACK,
                dc_target=12,
                modifier=5,
                ability_stat="STR",
                risk_level="High",
                icon_name="swords",
            ),
        ]

        soundtrack = SoundtrackDirective(
            theme="ethereal_mystery" if self.tension_curve < 40 else "ominous_pulse",
            intensity=self.tension_curve / 100.0,
            bpm=85,
            sfx_trigger="dice_roll",
        )

        return GenerativeUIPackage(
            narrative_text=narrative,
            location_name=curr_loc.name,
            tension_level=self.tension_curve,
            action_deck=actions,
            tactical_grid=None,
            dice_challenge=None,
            npc_interaction=None,
            loot=None,
            soundtrack=soundtrack,
            suggested_ui_layout="EXPLORATION",
        )

    def _handle_combat_turn(self, player_action: str) -> GenerativeUIPackage:
        if not self.active_combat_enemy or self.active_combat_enemy.current_hp <= 0:
            # Spawn fresh enemy
            self.active_combat_enemy = EncounterEnemy(
                name="Shadow Gargoyle Sentinel", max_hp=36, ac=14, spell_slots=2
            )
            self.tension_curve = 80
            grid_combatants = [
                GridCombatant(
                    id="hero_1",
                    name=self.player.name,
                    x=2,
                    y=5,
                    hp=self.player.current_hp,
                    max_hp=self.player.max_hp,
                    is_player=True,
                    stance="Defensive",
                    ac=self.player.ac,
                    icon="hero",
                ),
                GridCombatant(
                    id="enemy_1",
                    name=self.active_combat_enemy.name,
                    x=5,
                    y=2,
                    hp=self.active_combat_enemy.current_hp,
                    max_hp=self.active_combat_enemy.max_hp,
                    is_player=False,
                    stance=self.active_combat_enemy.stance.value,
                    ac=self.active_combat_enemy.ac,
                    icon="gargoyle",
                ),
            ]
            self.active_combat_grid = TacticalGridState(
                width=8, height=8, combatants=grid_combatants, round_number=1, active_turn_name=self.player.name
            )

        enemy = self.active_combat_enemy

        # Resolve player attack
        adv = AdvantageMode.NORMAL
        if "flank" in player_action.lower() or "advantage" in player_action.lower():
            adv = AdvantageMode.ADVANTAGE

        player_roll = resolve_attack(
            attacker=self.player.name,
            target=enemy.name,
            attack_modifier=self.player.attack_bonus,
            target_ac=enemy.ac,
            damage_dice_count=1,
            damage_die_sides=8,
            damage_modifier=3,
            damage_type=DamageType.SLASHING,
            advantage=adv,
        )

        sfx = "dice_roll"
        narrative_parts = [f"[Player Turn] {player_roll.combat_message}"]

        if player_roll.is_hit:
            enemy.apply_damage(player_roll.damage_dealt)
            sfx = "crit_fanfare" if player_roll.is_critical else "sword_clash"

        # Check enemy defeated
        if enemy.current_hp <= 0:
            loot_drop = [
                LootItem(
                    id="loot_1",
                    name="Heart of the Obsidian Sentinel",
                    rarity="Epic",
                    item_type="Relic",
                    stats_summary="+2 AC against shadow attacks, casts Shield 1x/day",
                    lore="A crystallized core recovered from the fallen Gargoyle.",
                    value_gold=120,
                ),
                LootItem(
                    id="loot_2",
                    name="Shard of Dawn Glass",
                    rarity="Rare",
                    item_type="Consumable",
                    stats_summary="Restores 25 HP and clears necrotic curse",
                    lore="Emits a steady, warm amber glow.",
                    value_gold=60,
                ),
            ]
            self.tension_curve = 30
            victory_text = (
                f"{enemy.name} shatters with a deafening crack, turning into inert black stone!\n"
                f"Victory belongs to {self.player.name}! The chamber falls quiet as ancient loot spills onto the stone dais."
            )
            narrative_parts.append(victory_text)
            self.active_combat_enemy = None
            self.active_combat_grid = None

            return GenerativeUIPackage(
                narrative_text="\n".join(narrative_parts),
                location_name=self.get_current_location().name,
                tension_level=self.tension_curve,
                action_deck=[
                    GenerativeActionCard(
                        id="claim_loot",
                        title="Gather Spoils & Equip Relic",
                        description="Add the Obsidian Heart to your inventory and inspect the room.",
                        category=ActionCategory.INVENTORY,
                        risk_level="Low",
                        icon_name="gift",
                    ),
                    GenerativeActionCard(
                        id="press_deeper",
                        title="Venture Deeper into Vaults",
                        description="Follow the trail of arcane footprints toward Sector G.",
                        category=ActionCategory.EXPLORATION,
                        risk_level="Medium",
                        icon_name="compass",
                    ),
                ],
                tactical_grid=None,
                loot=loot_drop,
                soundtrack=SoundtrackDirective(
                    theme="victory_fanfare", intensity=0.9, bpm=110, sfx_trigger="crit_fanfare"
                ),
                suggested_ui_layout="LOOT",
            )

        # Enemy turn
        distance = 3.0
        ai_dec = enemy.decide_turn_action(distance)
        narrative_parts.append(f"\n[Enemy Turn: {enemy.name}] {ai_dec.rationale}")

        if ai_dec.action != CombatActionType.FLEE and ai_dec.action != CombatActionType.DODGE:
            e_res = resolve_attack(
                attacker=enemy.name,
                target=self.player.name,
                attack_modifier=ai_dec.attack_modifier,
                target_ac=self.player.ac,
                damage_dice_count=ai_dec.damage_dice_count,
                damage_die_sides=ai_dec.damage_die_sides,
                damage_modifier=ai_dec.damage_modifier,
                damage_type=ai_dec.damage_type,
            )
            narrative_parts.append(f"  {e_res.combat_message}")
            if e_res.is_hit:
                self.player.current_hp = max(0, self.player.current_hp - e_res.damage_dealt)
                sfx = "fireball_impact" if ai_dec.damage_type == DamageType.FIRE else "sword_clash"

        # Update Grid
        if self.active_combat_grid:
            self.active_combat_grid.round_number += 1
            for c in self.active_combat_grid.combatants:
                if c.is_player:
                    c.hp = self.player.current_hp
                else:
                    c.hp = enemy.current_hp
                    c.stance = enemy.stance.value

        combat_actions = [
            GenerativeActionCard(
                id="act_slash",
                title="Sunforged Cleave",
                description="Make a standard melee strike with your glowing blade (1d8+3 Slashing).",
                category=ActionCategory.ATTACK,
                dc_target=14,
                modifier=self.player.attack_bonus,
                ability_stat="STR",
                risk_level="Medium",
                icon_name="swords",
            ),
            GenerativeActionCard(
                id="act_smite",
                title="Divine Smite (Level 1)",
                description="Infuse weapon with holy radiant fire (+2d8 Radiant damage).",
                category=ActionCategory.SPELL,
                dc_target=14,
                modifier=self.player.attack_bonus,
                ability_stat="STR",
                risk_level="High",
                icon_name="flame",
            ),
            GenerativeActionCard(
                id="act_defend",
                title="Raise Aegis Bulwark",
                description="Grant yourself Advantage on saving throws and +2 AC until next turn.",
                category=ActionCategory.SKILL_CHECK,
                dc_target=12,
                modifier=3,
                ability_stat="CON",
                risk_level="Low",
                icon_name="shield",
            ),
        ]

        return GenerativeUIPackage(
            narrative_text="\n".join(narrative_parts),
            location_name=self.get_current_location().name,
            tension_level=self.tension_curve,
            action_deck=combat_actions,
            tactical_grid=self.active_combat_grid,
            dice_challenge=None,
            npc_interaction=None,
            loot=None,
            soundtrack=SoundtrackDirective(
                theme="battle_tension", intensity=0.85, bpm=128, sfx_trigger=sfx
            ),
            suggested_ui_layout="COMBAT",
        )

    def _handle_dialogue(self, user_intent: str) -> GenerativeUIPackage:
        npc = NPCPreset(
            id="npc_sylas",
            name="Archivist Sylas",
            title="Keeper of the Astral Chronology",
            disposition=35,
            mood="Curious",
            dialogue=(
                "The gargoyles do not fight out of malice, paladin. They are tied to the Aegis Engine. "
                "Someone has placed an Obsidian siphon inside the pinnacle tower. If you disarm the siphon, "
                "they may recognize your sigil instead of viewing you as an intruder."
            ),
            speech_tone="Whispered, scholarly cadence with urgent gravity.",
            portrait_svg_type="scholar",
            quick_replies=[
                "Where is the siphon located?",
                "Can you grant me an astral blessing?",
                "What if the Obsidian Covenant arrives first?",
            ],
        )
        self.active_npc = npc
        self.tension_curve = 25

        actions = [
            GenerativeActionCard(
                id="ask_siphon",
                title="Ask about the Siphon",
                description="Demand precise coordinates of the siphon mechanism.",
                category=ActionCategory.DIALOGUE,
                risk_level="Low",
                icon_name="message-circle",
            ),
            GenerativeActionCard(
                id="persuade_blessing",
                title="Request Arcane Ward (DC 13)",
                description="Use Charisma to persuade Sylas to imbue your shield.",
                category=ActionCategory.SKILL_CHECK,
                dc_target=13,
                modifier=2,
                ability_stat="CHA",
                risk_level="Medium",
                icon_name="sparkles",
            ),
            GenerativeActionCard(
                id="depart_tower",
                title="Thank Sylas and March On",
                description="Head out toward the Gargoyle Roost.",
                category=ActionCategory.EXPLORATION,
                risk_level="Low",
                icon_name="compass",
            ),
        ]

        return GenerativeUIPackage(
            narrative_text=f"Archivist Sylas steps forward from the scroll racks.\n\n'{npc.dialogue}'",
            location_name=self.get_current_location().name,
            tension_level=self.tension_curve,
            action_deck=actions,
            tactical_grid=None,
            npc_interaction=npc,
            soundtrack=SoundtrackDirective(
                theme="tavern_hearth", intensity=0.25, bpm=75, sfx_trigger="dice_roll"
            ),
            suggested_ui_layout="DIALOGUE",
        )

    def _handle_exploration(self, user_intent: str) -> GenerativeUIPackage:
        curr = self.get_current_location()
        # Find next connected location if available
        next_loc_id = curr.connections[0] if curr.connections else curr.id
        for loc in self.world.locations:
            if loc.id == next_loc_id:
                loc.discovered = True
                self.world.current_location_id = loc.id
                break

        new_loc = self.get_current_location()
        self.tension_curve = min(95, new_loc.threat_tier * 10 + 10)

        narrative = (
            f"You depart {curr.name} and traverse the winding mountain ridge toward {new_loc.name}.\n\n"
            f"{new_loc.description}\n"
            f"A strange resonant frequency hums through the stones beneath your boots. "
            f"Threat assessment: Tier {new_loc.threat_tier}."
        )

        actions = [
            GenerativeActionCard(
                id="scout_perimeter",
                title="Scout the Perimeter (Stealth DC 12)",
                description="Creep along the parapet without alerting sentry gargoyles.",
                category=ActionCategory.SKILL_CHECK,
                dc_target=12,
                modifier=1,
                ability_stat="DEX",
                risk_level="Medium",
                icon_name="eye",
            ),
            GenerativeActionCard(
                id="enter_vault",
                title="Breach the Runed Portal",
                description="Force open the ancient adamantine portal (Athletics DC 15).",
                category=ActionCategory.SKILL_CHECK,
                dc_target=15,
                modifier=4,
                ability_stat="STR",
                risk_level="High",
                icon_name="key",
            ),
            GenerativeActionCard(
                id="commune_monolith",
                title="Commune with Runic Monolith",
                description="Touch the rune stone to attune your senses.",
                category=ActionCategory.SPELL,
                dc_target=13,
                modifier=2,
                ability_stat="WIS",
                risk_level="Low",
                icon_name="sparkles",
            ),
        ]

        return GenerativeUIPackage(
            narrative_text=narrative,
            location_name=new_loc.name,
            tension_level=self.tension_curve,
            action_deck=actions,
            tactical_grid=None,
            soundtrack=SoundtrackDirective(
                theme=new_loc.ambient_theme,
                intensity=self.tension_curve / 100.0,
                bpm=90,
                sfx_trigger="dice_roll",
            ),
            suggested_ui_layout="ATLAS",
        )

    def process_turn(self, player_input: str) -> GenerativeUIPackage:
        """Main entry point: Generates narrative and compiles the dynamic Generative UI."""
        return self._generate_procedural_response(player_input)

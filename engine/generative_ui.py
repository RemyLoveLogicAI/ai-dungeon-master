"""
engine/generative_ui.py
Defines the schema and generators for Generative UI payloads returned by the AI DM.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class UIComponentType(str, Enum):
    NARRATIVE_LOG = "NARRATIVE_LOG"
    ACTION_DECK = "ACTION_DECK"
    TACTICAL_GRID = "TACTICAL_GRID"
    DICE_CHALLENGE = "DICE_CHALLENGE"
    NPC_DIALOGUE = "NPC_DIALOGUE"
    LOOT_DROP = "LOOT_DROP"
    WORLD_ALERT = "WORLD_ALERT"
    SOUNDTRACK_DIRECTIVE = "SOUNDTRACK_DIRECTIVE"


class ActionCategory(str, Enum):
    ATTACK = "ATTACK"
    SPELL = "SPELL"
    SKILL_CHECK = "SKILL_CHECK"
    DIALOGUE = "DIALOGUE"
    EXPLORATION = "EXPLORATION"
    INVENTORY = "INVENTORY"


@dataclass
class GenerativeActionCard:
    id: str
    title: str
    description: str
    category: ActionCategory
    dc_target: int | None = None
    modifier: int = 0
    ability_stat: str = "STR"  # STR, DEX, CON, INT, WIS, CHA
    risk_level: str = "Medium"  # Low, Medium, High, Lethal
    cooldown_rounds: int = 0
    icon_name: str = "sword"


@dataclass
class GridCombatant:
    id: str
    name: str
    x: int  # 0-7
    y: int  # 0-7
    hp: int
    max_hp: int
    is_player: bool
    stance: str = "Normal"
    ac: int = 14
    icon: str = "hero"


@dataclass
class TacticalGridState:
    width: int = 8
    height: int = 8
    combatants: list[GridCombatant] = field(default_factory=list)
    terrain_hazards: list[dict[str, Any]] = field(default_factory=list)
    round_number: int = 1
    active_turn_name: str = "Paladin Alden"


@dataclass
class SoundtrackDirective:
    theme: str  # ambient_drone, battle_tension, victory_fanfare, ominous_pulse, tavern_hearth, ethereal_mystery
    intensity: float  # 0.0 to 1.0
    bpm: int = 90
    sfx_trigger: str | None = None  # dice_roll, sword_clash, fireball_impact, crit_fanfare


@dataclass
class NPCPreset:
    id: str
    name: str
    title: str
    disposition: int  # -100 (Hostile) to +100 (Revered)
    mood: str  # Suspicious, Aggressive, Curious, Venerable, Terrified
    dialogue: str
    speech_tone: str
    portrait_svg_type: str  # gargoyle, scholar, paladin, rogue, mystic
    quick_replies: list[str] = field(default_factory=list)


@dataclass
class LootItem:
    id: str
    name: str
    rarity: str  # Common, Rare, Epic, Legendary, Mythic
    item_type: str  # Weapon, Armor, Relic, Consumable
    stats_summary: str
    lore: str
    value_gold: int


@dataclass
class GenerativeUIPackage:
    narrative_text: str
    location_name: str
    tension_level: int
    action_deck: list[GenerativeActionCard] = field(default_factory=list)
    tactical_grid: TacticalGridState | None = None
    dice_challenge: dict[str, Any] | None = None
    npc_interaction: NPCPreset | None = None
    loot: list[LootItem] | None = None
    soundtrack: SoundtrackDirective | None = None
    suggested_ui_layout: str = "EXPLORATION"  # EXPLORATION, COMBAT, DIALOGUE, ATLAS, LOOT

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

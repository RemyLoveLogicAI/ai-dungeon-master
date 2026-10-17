// client/src/types/index.ts

export type ActionCategory =
  | 'ATTACK'
  | 'SPELL'
  | 'SKILL_CHECK'
  | 'DIALOGUE'
  | 'EXPLORATION'
  | 'INVENTORY';

export interface GenerativeActionCard {
  id: string;
  title: string;
  description: string;
  category: ActionCategory;
  dc_target?: number;
  modifier: number;
  ability_stat: 'STR' | 'DEX' | 'CON' | 'INT' | 'WIS' | 'CHA';
  risk_level: 'Low' | 'Medium' | 'High' | 'Lethal';
  cooldown_rounds: number;
  icon_name: string;
}

export interface GridCombatant {
  id: string;
  name: string;
  x: number;
  y: number;
  hp: number;
  max_hp: number;
  is_player: boolean;
  stance: string;
  ac: number;
  icon: string;
}

export interface TacticalGridState {
  width: number;
  height: number;
  combatants: GridCombatant[];
  terrain_hazards: any[];
  round_number: number;
  active_turn_name: string;
}

export interface SoundtrackDirective {
  theme:
    | 'ambient_drone'
    | 'battle_tension'
    | 'victory_fanfare'
    | 'ominous_pulse'
    | 'tavern_hearth'
    | 'ethereal_mystery';
  intensity: number; // 0.0 to 1.0
  bpm: number;
  sfx_trigger?: 'dice_roll' | 'sword_clash' | 'fireball_impact' | 'crit_fanfare';
}

export interface NPCPreset {
  id: string;
  name: string;
  title: string;
  disposition: number;
  mood: string;
  dialogue: string;
  speech_tone: string;
  portrait_svg_type: string;
  quick_replies: string[];
}

export interface LootItem {
  id: string;
  name: string;
  rarity: 'Common' | 'Rare' | 'Epic' | 'Legendary' | 'Mythic';
  item_type: 'Weapon' | 'Armor' | 'Relic' | 'Consumable';
  stats_summary: string;
  lore: string;
  value_gold: number;
}

export interface GenerativeUIPackage {
  narrative_text: string;
  location_name: string;
  tension_level: number;
  action_deck: GenerativeActionCard[];
  tactical_grid?: TacticalGridState | null;
  dice_challenge?: any | null;
  npc_interaction?: NPCPreset | null;
  loot?: LootItem[] | null;
  soundtrack?: SoundtrackDirective | null;
  suggested_ui_layout: 'EXPLORATION' | 'COMBAT' | 'DIALOGUE' | 'ATLAS' | 'LOOT';
}

export interface Faction {
  id: string;
  name: string;
  motto: string;
  ideology: string;
  leader: string;
  influence: number;
  hostility_to_player: number;
  sigil: string;
}

export interface LocationNode {
  id: string;
  name: string;
  region: string;
  biome: string;
  threat_tier: number;
  description: string;
  coordinates: { x: number; y: number };
  connections: string[];
  discovered: boolean;
  cleared: boolean;
  secrets_count: number;
  ambient_theme: string;
}

export interface WorldState {
  id: string;
  name: string;
  epoch: string;
  cosmology: string;
  cataclysm_lore: string;
  active_quest: string;
  tension_level: number;
  current_location_id: string;
  factions: Faction[];
  locations: LocationNode[];
}

export interface PlayerCharacter {
  name: string;
  class_title: string;
  current_hp: number;
  max_hp: number;
  ac: number;
  spell_slots: number;
  max_spell_slots: number;
  attack_bonus: number;
  level: number;
  inventory: string[];
  gold: number;
}

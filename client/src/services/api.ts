// client/src/services/api.ts
import { GenerativeUIPackage, PlayerCharacter, WorldState } from '../types';

const API_BASE = '/api';

export async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(2000) });
    if (!res.ok) throw new Error('Health check failed');
    return await res.json();
  } catch (err) {
    return { status: 'offline', ollama_available: false, available_models: [] };
  }
}

export async function fetchCurrentWorld(): Promise<WorldState | null> {
  try {
    const res = await fetch(`${API_BASE}/world/current`);
    if (!res.ok) throw new Error('Failed to load world');
    const data = await res.json();
    return data.world;
  } catch {
    return null;
  }
}

export async function fetchPlayerState(): Promise<PlayerCharacter | null> {
  try {
    const res = await fetch(`${API_BASE}/player`);
    if (!res.ok) throw new Error('Failed to load player');
    const data = await res.json();
    return data.player;
  } catch {
    return null;
  }
}

export async function sendPlayerAction(action: string, cardId?: string): Promise<GenerativeUIPackage> {
  try {
    const res = await fetch(`${API_BASE}/dm/interact`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, card_id: cardId }),
    });
    if (!res.ok) throw new Error('DM interaction error');
    const data = await res.json();
    return data.response;
  } catch (err) {
    // Client-side fallback package if server is loading
    return {
      narrative_text: `You attempt to ${action}. The ether quivers as the dungeon realm recalibrates...`,
      location_name: 'Sanctum Threshold',
      tension_level: 30,
      suggested_ui_layout: 'EXPLORATION',
      action_deck: [
        {
          id: 'fallback_1',
          title: 'Assess Surroundings',
          description: 'Survey the perimeter for hidden doorways.',
          category: 'EXPLORATION',
          modifier: 2,
          ability_stat: 'WIS',
          risk_level: 'Low',
          cooldown_rounds: 0,
          icon_name: 'compass',
        },
        {
          id: 'fallback_2',
          title: 'Sunforged Strike',
          description: 'Ready your blade against lurking threats.',
          category: 'ATTACK',
          modifier: 5,
          ability_stat: 'STR',
          risk_level: 'Medium',
          cooldown_rounds: 0,
          icon_name: 'swords',
        },
      ],
      soundtrack: {
        theme: 'ambient_drone',
        intensity: 0.3,
        bpm: 90,
        sfx_trigger: 'dice_roll',
      },
    };
  }
}

export async function rollCombatAttack(params: {
  attacker: string;
  target: string;
  advantage: string;
}) {
  try {
    const res = await fetch(`${API_BASE}/combat/attack`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    return await res.json();
  } catch {
    // Offline roll simulation
    const r1 = Math.floor(Math.random() * 20) + 1;
    const r2 = Math.floor(Math.random() * 20) + 1;
    const roll = params.advantage === 'Advantage' ? Math.max(r1, r2) : params.advantage === 'Disadvantage' ? Math.min(r1, r2) : r1;
    const total = roll + 5;
    const isHit = total >= 14 || roll === 20;
    return {
      is_hit: isHit,
      is_critical: roll === 20,
      damage_dealt: isHit ? (roll === 20 ? 16 : 9) : 0,
      combat_message: `Rolled ${roll}+5 = ${total} vs AC 14. ${isHit ? 'HIT!' : 'MISSED!'}`,
      roll: { d20_roll: roll, total, is_nat_20: roll === 20, is_nat_1: roll === 1 },
    };
  }
}

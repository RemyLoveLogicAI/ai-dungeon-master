// client/src/components/CharacterSheet.tsx
import React, { useState } from 'react';
import { PlayerCharacter } from '../types';
import { Shield, Heart, Sparkles, Coins, Package, ChevronDown } from 'lucide-react';

interface CharacterSheetProps {
  player: PlayerCharacter | null;
}

export const CharacterSheet: React.FC<CharacterSheetProps> = ({ player }) => {
  const [showInventory, setShowInventory] = useState(false);

  if (!player) return null;

  const hpPct = Math.max(0, Math.min(100, (player.current_hp / player.max_hp) * 100));

  return (
    <div className="bg-slate-900/90 border border-slate-700/80 rounded-2xl p-4 shadow-xl backdrop-blur-md flex flex-col gap-3">
      {/* Player Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-bold text-sm text-slate-100 flex items-center gap-1.5">
            {player.name}
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
              Lvl {player.level}
            </span>
          </h3>
          <p className="text-[11px] text-slate-400 font-mono">{player.class_title}</p>
        </div>

        {/* AC Badge */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-slate-800 border border-slate-700 shadow-inner">
          <Shield className="w-4 h-4 text-amber-400" />
          <div className="flex flex-col items-center">
            <span className="text-[9px] uppercase font-bold text-slate-400 leading-none">AC</span>
            <span className="text-xs font-bold font-mono text-slate-200 leading-none mt-0.5">
              {player.ac}
            </span>
          </div>
        </div>
      </div>

      {/* HP Bar */}
      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between text-xs font-mono">
          <span className="flex items-center gap-1 text-red-400 font-semibold">
            <Heart className="w-3.5 h-3.5 fill-red-500/30" />
            Hit Points
          </span>
          <span className="text-slate-300">
            {player.current_hp} / {player.max_hp}
          </span>
        </div>
        <div className="w-full bg-slate-950 h-2.5 rounded-full overflow-hidden border border-slate-800">
          <div
            className={`h-full transition-all duration-300 ${
              hpPct > 50 ? 'bg-emerald-500' : hpPct > 25 ? 'bg-amber-500' : 'bg-red-500 animate-pulse'
            }`}
            style={{ width: `${hpPct}%` }}
          />
        </div>
      </div>

      {/* Spell Slots & Gold */}
      <div className="flex items-center justify-between pt-1 border-t border-slate-800 text-xs">
        <div className="flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
          <span className="text-slate-400 text-[11px]">Spell Slots:</span>
          <div className="flex gap-1">
            {Array.from({ length: player.max_spell_slots }).map((_, i) => (
              <span
                key={i}
                className={`w-2.5 h-2.5 rounded-sm rotate-45 transition ${
                  i < player.spell_slots
                    ? 'bg-indigo-400 shadow-[0_0_6px_#818cf8]'
                    : 'bg-slate-700'
                }`}
              />
            ))}
          </div>
        </div>

        <div className="flex items-center gap-1 text-amber-300 font-mono font-semibold">
          <Coins className="w-3.5 h-3.5 text-amber-400" />
          <span>{player.gold}g</span>
        </div>
      </div>

      {/* Quick Inventory Toggle */}
      <div className="pt-1">
        <button
          onClick={() => setShowInventory(!showInventory)}
          className="w-full flex items-center justify-between text-xs text-slate-400 hover:text-slate-200 py-1 transition"
        >
          <span className="flex items-center gap-1.5">
            <Package className="w-3.5 h-3.5" />
            Inventory ({player.inventory.length})
          </span>
          <ChevronDown
            className={`w-3.5 h-3.5 transition-transform ${showInventory ? 'rotate-180' : ''}`}
          />
        </button>

        {showInventory && (
          <div className="mt-2 p-2 bg-slate-950 rounded-xl border border-slate-800 flex flex-col gap-1 text-xs">
            {player.inventory.map((item, idx) => (
              <div
                key={idx}
                className="p-1.5 rounded-lg bg-slate-900 border border-slate-800/80 text-slate-300 flex items-center justify-between"
              >
                <span>{item}</span>
                <span className="text-[10px] text-amber-400 font-mono">Equipped</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

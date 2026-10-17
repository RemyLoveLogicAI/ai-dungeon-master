// client/src/components/TacticalGrid.tsx
import React from 'react';
import { TacticalGridState, GridCombatant } from '../types';
import { Shield, Flame, Sword, Target } from 'lucide-react';

interface TacticalGridProps {
  gridState: TacticalGridState;
  onSelectCombatant?: (combatant: GridCombatant) => void;
  selectedCombatantId?: string;
}

export const TacticalGrid: React.FC<TacticalGridProps> = ({
  gridState,
  onSelectCombatant,
  selectedCombatantId,
}) => {
  const { width = 8, height = 8, combatants = [], round_number = 1 } = gridState;

  // Build matrix lookup
  const combatantAt = (x: number, y: number): GridCombatant | undefined => {
    return combatants.find((c) => c.x === x && c.y === y);
  };

  const getDistance = (c1: GridCombatant, c2: GridCombatant) => {
    return Math.sqrt(Math.pow(c1.x - c2.x, 2) + Math.pow(c1.y - c2.y, 2)).toFixed(1);
  };

  const hero = combatants.find((c) => c.is_player);
  const enemy = combatants.find((c) => !c.is_player);

  return (
    <div className="bg-slate-900/90 border border-slate-700/80 rounded-2xl p-4 shadow-2xl backdrop-blur-md flex flex-col items-center">
      <div className="flex items-center justify-between w-full mb-3">
        <div className="flex items-center gap-2">
          <Target className="w-5 h-5 text-indigo-400" />
          <h3 className="font-bold text-sm tracking-wide uppercase text-slate-200">
            Tactical Combat Matrix
          </h3>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300">
            Round {round_number}
          </span>
          {hero && enemy && (
            <span className="px-2 py-0.5 rounded bg-indigo-950/80 border border-indigo-700/50 text-indigo-300">
              Distance: {getDistance(hero, enemy)}m
            </span>
          )}
        </div>
      </div>

      {/* Grid Canvas */}
      <div
        className="grid gap-1 p-2 bg-slate-950 rounded-xl border border-slate-800 shadow-inner"
        style={{
          gridTemplateColumns: `repeat(${width}, minmax(0, 1fr))`,
          width: '100%',
          maxWidth: '380px',
          aspectRatio: '1/1',
        }}
      >
        {Array.from({ length: height }).map((_, y) =>
          Array.from({ length: width }).map((_, x) => {
            const combatant = combatantAt(x, y);
            const isSelected = combatant && combatant.id === selectedCombatantId;

            return (
              <div
                key={`${x}-${y}`}
                onClick={() => combatant && onSelectCombatant && onSelectCombatant(combatant)}
                className={`relative rounded-lg flex items-center justify-center transition-all ${
                  combatant
                    ? 'cursor-pointer'
                    : 'bg-slate-900/50 hover:bg-slate-800/40 border border-slate-800/60'
                } ${
                  isSelected ? 'ring-2 ring-amber-400' : ''
                }`}
              >
                {/* Coordinate subtle watermark */}
                <span className="absolute bottom-0.5 right-1 text-[8px] font-mono text-slate-700 select-none">
                  {x},{y}
                </span>

                {combatant && (
                  <div
                    className={`relative w-9/10 h-9/10 rounded-md flex flex-col items-center justify-center p-1 shadow-md transition-transform hover:scale-110 ${
                      combatant.is_player
                        ? 'bg-gradient-to-br from-amber-600/80 to-amber-900/90 border border-amber-400/70 text-amber-100 shadow-[0_0_10px_rgba(245,158,11,0.4)]'
                        : 'bg-gradient-to-br from-red-800/80 to-purple-950/90 border border-red-500/70 text-red-100 shadow-[0_0_10px_rgba(239,68,68,0.4)]'
                    }`}
                  >
                    {/* Icon */}
                    {combatant.is_player ? (
                      <Shield className="w-4 h-4 text-amber-200" />
                    ) : (
                      <Flame className="w-4 h-4 text-red-300" />
                    )}

                    {/* Mini HP indicator bar */}
                    <div className="w-full bg-slate-950/90 h-1 rounded-full mt-1 overflow-hidden">
                      <div
                        className={`h-full transition-all ${
                          combatant.is_player ? 'bg-amber-400' : 'bg-red-500'
                        }`}
                        style={{
                          width: `${Math.max(0, Math.min(100, (combatant.hp / combatant.max_hp) * 100))}%`,
                        }}
                      />
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Combatant Roster Details */}
      <div className="grid grid-cols-2 gap-2 w-full mt-3">
        {combatants.map((c) => (
          <div
            key={c.id}
            className={`p-2 rounded-xl border text-xs flex flex-col gap-1 ${
              c.is_player
                ? 'bg-amber-950/20 border-amber-800/40'
                : 'bg-red-950/20 border-red-800/40'
            }`}
          >
            <div className="flex items-center justify-between font-semibold">
              <span className={c.is_player ? 'text-amber-300' : 'text-red-300'}>
                {c.name}
              </span>
              <span className="font-mono text-[10px] text-slate-400">AC {c.ac}</span>
            </div>
            <div className="flex items-center justify-between text-[11px] font-mono">
              <span>HP: {c.hp}/{c.max_hp}</span>
              <span className="text-[10px] uppercase px-1.5 py-0.2 rounded bg-slate-800 text-slate-300">
                {c.stance}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

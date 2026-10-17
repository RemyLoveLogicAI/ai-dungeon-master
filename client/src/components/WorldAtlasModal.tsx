// client/src/components/WorldAtlasModal.tsx
import React from 'react';
import { WorldState, LocationNode } from '../types';
import { X, MapPin, Shield, Skull, Compass, Globe } from 'lucide-react';

interface WorldAtlasModalProps {
  world: WorldState | null;
  onClose: () => void;
  onSelectLocation?: (loc: LocationNode) => void;
}

export const WorldAtlasModal: React.FC<WorldAtlasModalProps> = ({
  world,
  onClose,
  onSelectLocation,
}) => {
  if (!world) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-3xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <Globe className="w-6 h-6 text-amber-400" />
            <div>
              <h2 className="text-lg font-bold text-slate-100">{world.name}</h2>
              <p className="text-xs text-slate-400 font-mono">{world.epoch}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-100 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content: SVG Map + Lore */}
        <div className="p-6 overflow-y-auto flex flex-col gap-6">
          {/* Active Quest Banner */}
          <div className="p-3.5 rounded-xl bg-amber-950/30 border border-amber-800/40 text-xs flex items-center gap-3 text-amber-200">
            <Compass className="w-5 h-5 text-amber-400 shrink-0" />
            <div>
              <span className="font-bold text-amber-400">Current Objective: </span>
              {world.active_quest}
            </div>
          </div>

          {/* Interactive SVG Atlas Canvas */}
          <div className="relative w-full aspect-video bg-slate-950 rounded-2xl border border-slate-800 overflow-hidden shadow-inner flex items-center justify-center">
            <svg viewBox="0 0 100 100" className="w-full h-full p-6">
              {/* Connection lines */}
              {world.locations.map((loc) =>
                loc.connections.map((targetId) => {
                  const target = world.locations.find((l) => l.id === targetId);
                  if (!target) return null;
                  return (
                    <line
                      key={`${loc.id}-${target.id}`}
                      x1={loc.coordinates.x}
                      y1={loc.coordinates.y}
                      x2={target.coordinates.x}
                      y2={target.coordinates.y}
                      stroke="#334155"
                      strokeWidth="0.8"
                      strokeDasharray="2,2"
                    />
                  );
                })
              )}

              {/* Location Nodes */}
              {world.locations.map((loc) => {
                const isCurrent = loc.id === world.current_location_id;
                return (
                  <g
                    key={loc.id}
                    onClick={() => onSelectLocation && onSelectLocation(loc)}
                    className="cursor-pointer group"
                  >
                    {/* Outer pulse if current */}
                    {isCurrent && (
                      <circle
                        cx={loc.coordinates.x}
                        cy={loc.coordinates.y}
                        r="5.5"
                        className="fill-amber-500/20 stroke-amber-400 stroke-[0.8] animate-ping"
                      />
                    )}

                    <circle
                      cx={loc.coordinates.x}
                      cy={loc.coordinates.y}
                      r="3.5"
                      className={`transition duration-200 ${
                        isCurrent
                          ? 'fill-amber-400 stroke-slate-900 stroke-[1.2]'
                          : loc.discovered
                          ? 'fill-slate-700 stroke-indigo-400 stroke-[0.8] hover:fill-indigo-500'
                          : 'fill-slate-800 stroke-slate-600 stroke-[0.5]'
                      }`}
                    />

                    {/* Label */}
                    <text
                      x={loc.coordinates.x}
                      y={loc.coordinates.y + 6}
                      textAnchor="middle"
                      className={`text-[3.2px] font-sans font-semibold select-none ${
                        isCurrent
                          ? 'fill-amber-300 font-bold'
                          : loc.discovered
                          ? 'fill-slate-300'
                          : 'fill-slate-500'
                      }`}
                    >
                      {loc.name}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Factions & Lore Details */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {world.factions.map((f) => (
              <div
                key={f.id}
                className="p-3 rounded-xl bg-slate-800/60 border border-slate-700/60 text-xs flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between font-bold text-slate-200 mb-1">
                    <span>{f.name}</span>
                    <span className="text-[10px] text-amber-400 font-mono">Inf: {f.influence}%</span>
                  </div>
                  <p className="text-[11px] text-slate-400 italic mb-2">"{f.motto}"</p>
                  <p className="text-[11px] text-slate-400 leading-snug">{f.ideology}</p>
                </div>
                <div className="mt-3 pt-2 border-t border-slate-700/50 flex items-center justify-between text-[10px] font-mono text-slate-400">
                  <span>Leader: {f.leader}</span>
                  <span
                    className={
                      f.hostility_to_player > 0 ? 'text-red-400' : 'text-emerald-400'
                    }
                  >
                    {f.hostility_to_player > 0 ? 'Hostile' : 'Allied'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

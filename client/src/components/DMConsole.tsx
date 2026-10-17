// client/src/components/DMConsole.tsx
import React, { useState } from 'react';
import { Cpu, Activity, RefreshCw, Zap, Server, ChevronDown, ChevronUp } from 'lucide-react';
import { WorldState } from '../types';

interface DMConsoleProps {
  tension: number;
  world: WorldState | null;
  ollamaAvailable: boolean;
  availableModels: string[];
  onRegenerateWorld: () => void;
}

export const DMConsole: React.FC<DMConsoleProps> = ({
  tension,
  world,
  ollamaAvailable,
  availableModels,
  onRegenerateWorld,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="bg-slate-900/90 border border-slate-700/80 rounded-2xl p-4 shadow-xl backdrop-blur-md flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-purple-400" />
          <h4 className="font-bold text-xs uppercase tracking-wider text-slate-200">
            Mind of the DM
          </h4>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700 text-[10px] font-mono">
            <span
              className={`w-2 h-2 rounded-full ${
                ollamaAvailable ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
              }`}
            />
            <span className="text-slate-300">
              {ollamaAvailable ? 'Ollama Live' : 'Heuristic Engine'}
            </span>
          </div>

          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1 rounded bg-slate-800 text-slate-400 hover:text-white transition"
          >
            {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Tension Meter Bar */}
      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between text-xs font-mono">
          <span className="flex items-center gap-1 text-slate-400">
            <Activity className="w-3.5 h-3.5 text-red-400" />
            Encounter Tension
          </span>
          <span className="text-slate-300 font-semibold">{tension}%</span>
        </div>
        <div className="w-full bg-slate-950 h-2 rounded-full overflow-hidden border border-slate-800">
          <div
            className={`h-full transition-all duration-500 ${
              tension > 70
                ? 'bg-gradient-to-r from-red-600 to-red-400 animate-pulse'
                : tension > 40
                ? 'bg-gradient-to-r from-amber-600 to-amber-400'
                : 'bg-gradient-to-r from-indigo-600 to-indigo-400'
            }`}
            style={{ width: `${tension}%` }}
          />
        </div>
      </div>

      {/* Expanded DM Telemetry */}
      {isExpanded && (
        <div className="mt-2 pt-3 border-t border-slate-800 flex flex-col gap-3 text-xs animate-fade-in">
          {world && (
            <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 flex flex-col gap-1">
              <span className="text-[10px] font-mono uppercase text-slate-500">Active Campaign</span>
              <span className="text-slate-200 font-semibold">{world.name} ({world.epoch})</span>
              <p className="text-[11px] text-slate-400 mt-1">{world.cosmology}</p>
            </div>
          )}

          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span>Available Local Models:</span>
            <span className="text-slate-200 font-semibold">
              {availableModels.length > 0 ? availableModels.slice(0, 3).join(', ') : 'None (Auto-Heuristic)'}
            </span>
          </div>

          <button
            onClick={onRegenerateWorld}
            className="w-full py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-amber-300 flex items-center justify-center gap-2 transition active:scale-98"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Forge New World & Campaign</span>
          </button>
        </div>
      )}
    </div>
  );
};

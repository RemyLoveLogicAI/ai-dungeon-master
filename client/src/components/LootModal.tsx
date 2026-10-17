// client/src/components/LootModal.tsx
import React from 'react';
import { LootItem } from '../types';
import { Sparkles, X, Gift, Check } from 'lucide-react';

interface LootModalProps {
  loot: LootItem[] | null;
  onClose: () => void;
  onClaimItem?: (item: LootItem) => void;
}

const getRarityBadge = (rarity: string) => {
  switch (rarity) {
    case 'Rare':
      return 'bg-blue-950/70 text-blue-300 border-blue-700/60';
    case 'Epic':
      return 'bg-purple-950/70 text-purple-300 border-purple-700/60 shadow-[0_0_10px_rgba(168,85,247,0.3)]';
    case 'Legendary':
      return 'bg-amber-950/70 text-amber-300 border-amber-600/70 shadow-[0_0_15px_rgba(245,158,11,0.4)]';
    case 'Mythic':
      return 'bg-red-950/80 text-red-300 border-red-600/80 animate-pulse';
    default:
      return 'bg-slate-800 text-slate-300 border-slate-700';
  }
};

export const LootModal: React.FC<LootModalProps> = ({
  loot,
  onClose,
  onClaimItem,
}) => {
  if (!loot || loot.length === 0) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-3xl w-full max-w-xl overflow-hidden flex flex-col shadow-2xl animate-fade-in">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <Gift className="w-6 h-6 text-amber-400" />
            <div>
              <h3 className="text-base font-bold text-slate-100">Spoils of Conquest</h3>
              <p className="text-xs text-slate-400 font-mono">Recovered Artifacts & Relics</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-100 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Item Cards */}
        <div className="p-5 flex flex-col gap-3 max-h-[60vh] overflow-y-auto">
          {loot.map((item) => (
            <div
              key={item.id}
              className="p-4 rounded-2xl bg-slate-950 border border-slate-800 flex flex-col justify-between gap-3 shadow-md"
            >
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-amber-400" />
                    <span className="font-bold text-slate-200 text-sm">{item.name}</span>
                  </div>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${getRarityBadge(
                      item.rarity
                    )}`}
                  >
                    {item.rarity} {item.item_type}
                  </span>
                </div>
                <p className="text-xs text-amber-300 font-mono mb-2">{item.stats_summary}</p>
                <p className="text-xs text-slate-400 italic leading-relaxed">{item.lore}</p>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-slate-800 text-xs">
                <span className="text-slate-400 font-mono">Value: {item.value_gold} gold</span>
                <button
                  onClick={() => onClaimItem && onClaimItem(item)}
                  className="px-3 py-1 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs flex items-center gap-1.5 transition active:scale-95"
                >
                  <Check className="w-3.5 h-3.5" />
                  <span>Equip to Hero</span>
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 transition"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};

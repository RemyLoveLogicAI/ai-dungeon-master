// client/src/components/ActionCardDeck.tsx
import React from 'react';
import { GenerativeActionCard } from '../types';
import {
  Swords,
  Flame,
  Sparkles,
  MessageCircle,
  Compass,
  Gift,
  ShieldAlert,
  Search,
  Eye,
  Key,
} from 'lucide-react';

interface ActionCardDeckProps {
  cards: GenerativeActionCard[];
  onSelectAction: (card: GenerativeActionCard) => void;
  disabled?: boolean;
}

const getCategoryIcon = (iconName: string, category: string) => {
  switch (iconName) {
    case 'swords':
    case 'sword':
      return <Swords className="w-4 h-4 text-amber-400" />;
    case 'flame':
      return <Flame className="w-4 h-4 text-orange-400" />;
    case 'sparkles':
      return <Sparkles className="w-4 h-4 text-purple-400" />;
    case 'message-circle':
      return <MessageCircle className="w-4 h-4 text-cyan-400" />;
    case 'compass':
      return <Compass className="w-4 h-4 text-emerald-400" />;
    case 'gift':
      return <Gift className="w-4 h-4 text-yellow-400" />;
    case 'search':
      return <Search className="w-4 h-4 text-blue-400" />;
    case 'eye':
      return <Eye className="w-4 h-4 text-teal-400" />;
    case 'key':
      return <Key className="w-4 h-4 text-amber-300" />;
    default:
      return <Swords className="w-4 h-4 text-amber-400" />;
  }
};

const getRiskBadge = (risk: string) => {
  switch (risk) {
    case 'Low':
      return 'bg-emerald-950/60 text-emerald-400 border-emerald-800/40';
    case 'Medium':
      return 'bg-amber-950/60 text-amber-400 border-amber-800/40';
    case 'High':
      return 'bg-red-950/60 text-red-400 border-red-800/40';
    case 'Lethal':
      return 'bg-purple-950/80 text-purple-300 border-purple-700/60 animate-pulse';
    default:
      return 'bg-slate-800 text-slate-300 border-slate-700';
  }
};

export const ActionCardDeck: React.FC<ActionCardDeckProps> = ({
  cards,
  onSelectAction,
  disabled = false,
}) => {
  return (
    <div className="w-full flex flex-col gap-2">
      <div className="flex items-center justify-between px-1">
        <h4 className="text-xs uppercase font-bold tracking-wider text-slate-400">
          Generative DM Options
        </h4>
        <span className="text-[11px] text-slate-500 font-mono">
          {cards.length} Dynamic Actions
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {cards.map((card) => (
          <div
            key={card.id}
            onClick={() => !disabled && onSelectAction(card)}
            className={`group relative p-3.5 rounded-xl border transition-all flex flex-col justify-between text-left ${
              disabled
                ? 'opacity-50 cursor-not-allowed bg-slate-900 border-slate-800'
                : 'cursor-pointer bg-slate-900/80 hover:bg-slate-800/90 border-slate-700/80 hover:border-amber-500/50 hover:shadow-[0_0_15px_rgba(245,158,11,0.15)] active:scale-98'
            }`}
          >
            <div>
              {/* Header */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-slate-800 border border-slate-700">
                    {getCategoryIcon(card.icon_name, card.category)}
                  </div>
                  <span className="text-xs font-semibold text-slate-300 group-hover:text-amber-300 transition">
                    {card.title}
                  </span>
                </div>
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${getRiskBadge(
                    card.risk_level
                  )}`}
                >
                  {card.risk_level}
                </span>
              </div>

              {/* Description */}
              <p className="text-xs text-slate-400 leading-relaxed line-clamp-2">
                {card.description}
              </p>
            </div>

            {/* Footer with DC and Stat */}
            <div className="flex items-center justify-between mt-3 pt-2 border-t border-slate-800 text-[11px] font-mono text-slate-400">
              <span className="flex items-center gap-1">
                <span className="text-slate-500">Stat:</span>
                <span className="text-slate-300 font-semibold">{card.ability_stat}</span>
                <span className="text-amber-400">+{card.modifier}</span>
              </span>

              {card.dc_target ? (
                <span className="px-1.5 py-0.5 rounded bg-slate-800 text-amber-300 font-semibold">
                  DC {card.dc_target}
                </span>
              ) : (
                <span className="text-slate-500 text-[10px]">Instant</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

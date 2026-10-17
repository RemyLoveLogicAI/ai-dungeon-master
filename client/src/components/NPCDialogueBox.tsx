// client/src/components/NPCDialogueBox.tsx
import React from 'react';
import { NPCPreset } from '../types';
import { User, MessageSquare, HeartHandshake } from 'lucide-react';

interface NPCDialogueBoxProps {
  npc: NPCPreset;
  onSelectReply: (reply: string) => void;
}

export const NPCDialogueBox: React.FC<NPCDialogueBoxProps> = ({
  npc,
  onSelectReply,
}) => {
  return (
    <div className="bg-slate-900/90 border border-slate-700/80 rounded-2xl p-5 shadow-2xl backdrop-blur-md flex flex-col gap-4">
      {/* NPC Header */}
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-800 border border-indigo-400 flex items-center justify-center text-indigo-100 shadow-md">
          <User className="w-6 h-6" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-bold text-slate-100">{npc.name}</h3>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
              {npc.mood}
            </span>
          </div>
          <p className="text-xs text-indigo-300 font-mono">{npc.title}</p>
        </div>
      </div>

      {/* Tone & Speech Dialogue */}
      <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 text-sm text-slate-300 italic leading-relaxed relative">
        <span className="text-slate-500 font-serif text-2xl absolute top-1 left-2 select-none">“</span>
        <p className="pl-4">{npc.dialogue}</p>
        <span className="text-slate-500 font-serif text-2xl absolute bottom-1 right-2 select-none">”</span>
      </div>

      {/* Quick Replies */}
      {npc.quick_replies && npc.quick_replies.length > 0 && (
        <div className="flex flex-col gap-2">
          <span className="text-[11px] font-mono uppercase text-slate-400">
            Dialogue Responses:
          </span>
          <div className="flex flex-wrap gap-2">
            {npc.quick_replies.map((reply, i) => (
              <button
                key={i}
                onClick={() => onSelectReply(reply)}
                className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-indigo-900/40 border border-slate-700 hover:border-indigo-500 text-xs text-slate-200 transition text-left flex items-center gap-2 active:scale-98"
              >
                <MessageSquare className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                <span>{reply}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

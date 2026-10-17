// client/src/components/D20DiceRoller.tsx
import React, { useState } from 'react';
import { Sparkles, Skull, Dna, Volume2 } from 'lucide-react';
import { proceduralAudio } from '../audio/procedural_synth';

interface D20DiceRollerProps {
  onRollComplete?: (result: { roll: number; total: number; isCrit: boolean; isFumble: boolean }) => void;
  modifier?: number;
  dcTarget?: number;
}

export const D20DiceRoller: React.FC<D20DiceRollerProps> = ({
  onRollComplete,
  modifier = 5,
  dcTarget = 14,
}) => {
  const [isRolling, setIsRolling] = useState(false);
  const [currentVal, setCurrentVal] = useState<number | null>(null);
  const [advantageMode, setAdvantageMode] = useState<'Normal' | 'Advantage' | 'Disadvantage'>('Normal');
  const [firstDie, setFirstDie] = useState<number | null>(null);
  const [secondDie, setSecondDie] = useState<number | null>(null);

  const handleRoll = () => {
    if (isRolling) return;
    setIsRolling(true);
    proceduralAudio.playDiceRoll();

    let rollCount = 0;
    const interval = setInterval(() => {
      rollCount++;
      const tempRoll = Math.floor(Math.random() * 20) + 1;
      setCurrentVal(tempRoll);

      if (rollCount > 10) {
        clearInterval(interval);
        const r1 = Math.floor(Math.random() * 20) + 1;
        const r2 = Math.floor(Math.random() * 20) + 1;
        setFirstDie(r1);
        setSecondDie(r2);

        let finalRoll = r1;
        if (advantageMode === 'Advantage') finalRoll = Math.max(r1, r2);
        if (advantageMode === 'Disadvantage') finalRoll = Math.min(r1, r2);

        setCurrentVal(finalRoll);
        setIsRolling(false);

        const isCrit = finalRoll === 20;
        const isFumble = finalRoll === 1;

        if (isCrit) {
          proceduralAudio.playCritFanfare();
        } else if (isFumble) {
          proceduralAudio.playSwordClash();
        }

        if (onRollComplete) {
          onRollComplete({
            roll: finalRoll,
            total: finalRoll + modifier,
            isCrit,
            isFumble,
          });
        }
      }
    }, 45);
  };

  const isCrit = currentVal === 20;
  const isFumble = currentVal === 1;
  const total = currentVal !== null ? currentVal + modifier : null;
  const isSuccess = total !== null && total >= dcTarget;

  return (
    <div className="bg-slate-900/90 border border-slate-700/80 rounded-2xl p-5 shadow-2xl backdrop-blur-md flex flex-col items-center">
      <div className="flex items-center justify-between w-full mb-4">
        <div className="flex items-center gap-2">
          <Dna className="w-5 h-5 text-amber-400" />
          <h3 className="font-bold text-sm tracking-wide uppercase text-slate-200">D20 Fate Core</h3>
        </div>
        <div className="flex items-center gap-1 bg-slate-800/80 p-1 rounded-lg border border-slate-700 text-xs">
          {(['Normal', 'Advantage', 'Disadvantage'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setAdvantageMode(mode)}
              className={`px-2 py-0.5 rounded transition ${
                advantageMode === mode
                  ? 'bg-amber-500 text-slate-950 font-semibold shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {mode}
            </button>
          ))}
        </div>
      </div>

      {/* 20-Sided Die Polygon Representation */}
      <div
        onClick={handleRoll}
        className={`relative w-32 h-32 flex items-center justify-center cursor-pointer transition-transform active:scale-95 my-2 ${
          isRolling ? 'animate-dice-tumble' : 'hover:scale-105'
        }`}
      >
        <svg viewBox="0 0 100 100" className="w-full h-full drop-shadow-[0_0_15px_rgba(245,158,11,0.3)]">
          <polygon
            points="50,5 92,28 92,72 50,95 8,72 8,28"
            className={`transition duration-300 ${
              isCrit
                ? 'fill-amber-500/30 stroke-amber-400 stroke-2'
                : isFumble
                ? 'fill-red-950/50 stroke-red-500 stroke-2'
                : 'fill-slate-800/90 stroke-amber-500/70 stroke-[1.5]'
            }`}
          />
          {/* Inner facets */}
          <line x1="50" y1="5" x2="50" y2="95" className="stroke-slate-700/60 stroke-[0.8]" />
          <line x1="50" y1="50" x2="92" y2="28" className="stroke-slate-700/60 stroke-[0.8]" />
          <line x1="50" y1="50" x2="8" y2="28" className="stroke-slate-700/60 stroke-[0.8]" />
          <line x1="50" y1="50" x2="92" y2="72" className="stroke-slate-700/60 stroke-[0.8]" />
          <line x1="50" y1="50" x2="8" y2="72" className="stroke-slate-700/60 stroke-[0.8]" />
        </svg>

        <div className="absolute flex flex-col items-center justify-center pointer-events-none">
          <span
            className={`text-3xl font-black font-mono transition-all ${
              isCrit
                ? 'text-amber-300 drop-shadow-[0_0_10px_#f59e0b]'
                : isFumble
                ? 'text-red-400 drop-shadow-[0_0_8px_#ef4444]'
                : 'text-amber-100'
            }`}
          >
            {currentVal !== null ? currentVal : '20'}
          </span>
          <span className="text-[10px] uppercase font-bold tracking-widest text-slate-400">
            {isRolling ? 'Rolling...' : currentVal !== null ? `+${modifier}` : 'Tap to Roll'}
          </span>
        </div>
      </div>

      {/* Outcome Banner */}
      {currentVal !== null && !isRolling && (
        <div className="mt-3 flex flex-col items-center gap-1 w-full animate-fade-in">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Total:</span>
            <span
              className={`text-lg font-bold font-mono ${
                isCrit ? 'text-amber-400' : isFumble ? 'text-red-400' : isSuccess ? 'text-emerald-400' : 'text-slate-300'
              }`}
            >
              {total} (DC {dcTarget})
            </span>
            {isCrit && <Sparkles className="w-4 h-4 text-amber-400 animate-spin" />}
            {isFumble && <Skull className="w-4 h-4 text-red-500 animate-bounce" />}
          </div>

          <div
            className={`text-xs px-2.5 py-0.5 rounded-full font-bold uppercase tracking-wider ${
              isCrit
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                : isFumble
                ? 'bg-red-500/20 text-red-400 border border-red-500/40'
                : isSuccess
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                : 'bg-slate-700/40 text-slate-400 border border-slate-600/40'
            }`}
          >
            {isCrit ? 'CRITICAL SUCCESS' : isFumble ? 'CRITICAL FUMBLE' : isSuccess ? 'CHECK PASSED' : 'CHECK FAILED'}
          </div>

          {advantageMode !== 'Normal' && firstDie !== null && secondDie !== null && (
            <span className="text-[10px] text-slate-500 font-mono mt-1">
              Rolls: [{firstDie}, {secondDie}] &rarr; Selected: {currentVal}
            </span>
          )}
        </div>
      )}
    </div>
  );
};

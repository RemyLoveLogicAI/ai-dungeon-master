// client/src/components/AudioDirector.tsx
import React, { useState, useEffect } from 'react';
import { Volume2, VolumeX, Music, Disc, Sparkles, Swords, Flame, Play, Square } from 'lucide-react';
import { proceduralAudio } from '../audio/procedural_synth';
import { SoundtrackDirective } from '../types';

interface AudioDirectorProps {
  directive?: SoundtrackDirective | null;
}

export const AudioDirector: React.FC<AudioDirectorProps> = ({ directive }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [theme, setTheme] = useState('ambient_drone');
  const [intensity, setIntensity] = useState(0.3);

  useEffect(() => {
    if (directive) {
      setTheme(directive.theme);
      setIntensity(directive.intensity);
      if (isPlaying) {
        proceduralAudio.updateTheme(directive.theme, directive.intensity);
      }
      if (directive.sfx_trigger) {
        switch (directive.sfx_trigger) {
          case 'dice_roll':
            proceduralAudio.playDiceRoll();
            break;
          case 'sword_clash':
            proceduralAudio.playSwordClash();
            break;
          case 'fireball_impact':
            proceduralAudio.playFireball();
            break;
          case 'crit_fanfare':
            proceduralAudio.playCritFanfare();
            break;
        }
      }
    }
  }, [directive]);

  const togglePlay = () => {
    if (isPlaying) {
      proceduralAudio.stopSoundtrack();
      setIsPlaying(false);
    } else {
      proceduralAudio.startSoundtrack(theme, intensity);
      setIsPlaying(true);
    }
  };

  const toggleMute = () => {
    const nextMute = !isMuted;
    setIsMuted(nextMute);
    proceduralAudio.setMuted(nextMute);
  };

  return (
    <div className="bg-slate-900/90 border border-slate-700/80 rounded-2xl p-4 shadow-xl backdrop-blur-md flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Music className={`w-4 h-4 ${isPlaying ? 'text-amber-400 animate-spin' : 'text-slate-400'}`} />
          <h4 className="font-bold text-xs uppercase tracking-wider text-slate-200">
            Generative Soundtrack
          </h4>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={toggleMute}
            className={`p-1.5 rounded-lg border transition ${
              isMuted
                ? 'bg-red-950/60 border-red-800 text-red-400'
                : 'bg-slate-800 border-slate-700 text-slate-300 hover:text-white'
            }`}
          >
            {isMuted ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={togglePlay}
            className={`px-2.5 py-1 rounded-lg border text-xs font-semibold flex items-center gap-1.5 transition ${
              isPlaying
                ? 'bg-amber-500/20 border-amber-500/50 text-amber-300'
                : 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700'
            }`}
          >
            {isPlaying ? (
              <>
                <Square className="w-3 h-3 fill-amber-300" />
                <span>Pause</span>
              </>
            ) : (
              <>
                <Play className="w-3 h-3 fill-slate-300" />
                <span>Synthesize</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Theme and Intensity Indicators */}
      <div className="flex items-center justify-between text-xs font-mono">
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
          <span className="text-slate-300 capitalize">{theme.replace('_', ' ')}</span>
        </div>
        <span className="text-[11px] text-slate-400">
          Intensity: {(intensity * 100).toFixed(0)}%
        </span>
      </div>

      {/* Audio Visualizer Simulation Bar */}
      <div className="flex items-end gap-1 h-5 w-full bg-slate-950 rounded-lg p-1 border border-slate-800/80 overflow-hidden">
        {Array.from({ length: 24 }).map((_, i) => (
          <div
            key={i}
            className={`flex-1 rounded-sm transition-all duration-150 ${
              isPlaying ? 'bg-gradient-to-t from-amber-600 to-amber-300' : 'bg-slate-800'
            }`}
            style={{
              height: isPlaying
                ? `${Math.max(15, Math.sin(i * 0.5 + Date.now() * 0.003) * 80 + 20)}%`
                : '20%',
            }}
          />
        ))}
      </div>

      {/* Procedural SFX Manual Triggers */}
      <div className="pt-1 border-t border-slate-800 flex items-center justify-between text-[11px]">
        <span className="text-slate-500 font-mono">Test SFX:</span>
        <div className="flex gap-1.5">
          <button
            onClick={() => proceduralAudio.playDiceRoll()}
            className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-amber-300 transition"
          >
            Dice
          </button>
          <button
            onClick={() => proceduralAudio.playSwordClash()}
            className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-amber-300 transition"
          >
            Clash
          </button>
          <button
            onClick={() => proceduralAudio.playFireball()}
            className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-amber-300 transition"
          >
            Fireball
          </button>
          <button
            onClick={() => proceduralAudio.playCritFanfare()}
            className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-amber-300 transition"
          >
            Fanfare
          </button>
        </div>
      </div>
    </div>
  );
};

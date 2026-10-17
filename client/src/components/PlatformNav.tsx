// client/src/components/PlatformNav.tsx
import React from 'react';
import { Smartphone, Monitor, Tv, Map, Dices, Maximize2 } from 'lucide-react';

export type PlatformSurface = 'mobile' | 'desktop' | 'tv';

interface PlatformNavProps {
  currentSurface: PlatformSurface;
  onChangeSurface: (surface: PlatformSurface) => void;
  onOpenAtlas: () => void;
  onToggleDiceModal: () => void;
  locationName: string;
}

export const PlatformNav: React.FC<PlatformNavProps> = ({
  currentSurface,
  onChangeSurface,
  onOpenAtlas,
  onToggleDiceModal,
  locationName,
}) => {
  const toggleFullScreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  };

  return (
    <header className="sticky top-0 z-40 w-full bg-slate-950/80 backdrop-blur-md border-b border-slate-800/80 px-4 py-3 flex items-center justify-between">
      {/* Brand & Location */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-amber-500 to-amber-700 flex items-center justify-center font-black text-slate-950 shadow-md">
          ⚔
        </div>
        <div>
          <h1 className="text-sm font-bold tracking-tight text-slate-100 flex items-center gap-2">
            AEGIS DUNGEON MASTER
            <span className="hidden sm:inline text-[9px] uppercase font-mono px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40">
              Generative Engine
            </span>
          </h1>
          <p className="text-[11px] text-slate-400 font-mono truncate max-w-[200px] sm:max-w-xs">
            📍 {locationName}
          </p>
        </div>
      </div>

      {/* Surface Selector & Action Shortcuts */}
      <div className="flex items-center gap-2">
        {/* Surface Pills */}
        <div className="hidden md:flex items-center bg-slate-900 border border-slate-800 rounded-xl p-1 gap-1">
          <button
            onClick={() => onChangeSurface('mobile')}
            className={`px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
              currentSurface === 'mobile'
                ? 'bg-amber-500 text-slate-950 shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="Android Companion View"
          >
            <Smartphone className="w-3.5 h-3.5" />
            <span>Android</span>
          </button>

          <button
            onClick={() => onChangeSurface('desktop')}
            className={`px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
              currentSurface === 'desktop'
                ? 'bg-amber-500 text-slate-950 shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="Desktop Cockpit"
          >
            <Monitor className="w-3.5 h-3.5" />
            <span>Desktop</span>
          </button>

          <button
            onClick={() => onChangeSurface('tv')}
            className={`px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
              currentSurface === 'tv'
                ? 'bg-amber-500 text-slate-950 shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="Television / Quest 3 Cast"
          >
            <Tv className="w-3.5 h-3.5" />
            <span>Cast/TV</span>
          </button>
        </div>

        {/* Atlas Button */}
        <button
          onClick={onOpenAtlas}
          className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs font-semibold text-slate-200 flex items-center gap-1.5 transition shadow-sm active:scale-95"
        >
          <Map className="w-3.5 h-3.5 text-amber-400" />
          <span className="hidden sm:inline">World Atlas</span>
        </button>

        {/* Quick D20 Dice Button */}
        <button
          onClick={onToggleDiceModal}
          className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs font-semibold text-slate-200 flex items-center gap-1.5 transition shadow-sm active:scale-95"
        >
          <Dices className="w-3.5 h-3.5 text-indigo-400" />
          <span className="hidden sm:inline">Roll D20</span>
        </button>

        {/* Fullscreen Button */}
        <button
          onClick={toggleFullScreen}
          className="p-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-400 hover:text-white transition"
          title="Fullscreen"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
};

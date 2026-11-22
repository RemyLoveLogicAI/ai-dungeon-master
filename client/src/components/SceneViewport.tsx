import React, { useState } from 'react';
import { Sparkles, Eye, Info, Maximize2, Minimize2, Compass } from 'lucide-react';
import type { SceneIllustration } from '../types';

interface SceneViewportProps {
  illustration?: SceneIllustration | null;
  locationName: string;
  tensionLevel?: number;
}

export const SceneViewport: React.FC<SceneViewportProps> = ({
  illustration,
  locationName,
  tensionLevel = 25,
}) => {
  const [showPromptDetails, setShowPromptDetails] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // If no illustration provided, render an atmospheric SVG placeholder
  const svgContent = illustration?.svg_data || `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 675" width="100%" height="100%">
      <rect width="1200" height="675" fill="#080b14"/>
      <circle cx="600" cy="337" r="180" fill="#1e293b" opacity="0.4"/>
      <text x="600" y="345" fill="#64748b" font-family="'Cinzel', serif" font-size="28" font-weight="bold" text-anchor="middle" letter-spacing="4">
        ${locationName.toUpperCase()}
      </text>
    </svg>
  `;

  return (
    <div
      className={`relative rounded-2xl overflow-hidden border border-slate-700/80 shadow-2xl backdrop-blur-md transition-all duration-300 ${
        isFullscreen
          ? 'fixed inset-4 z-50 bg-slate-950/95 flex flex-col p-4 border-amber-500/50'
          : 'bg-slate-900/90'
      }`}
    >
      {/* Top Banner / Location Tag */}
      <div className="absolute top-3 left-3 right-3 z-10 flex items-center justify-between pointer-events-none">
        <div className="flex items-center gap-2 pointer-events-auto">
          <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-950/80 border border-slate-700 text-xs font-semibold text-amber-400 backdrop-blur shadow-md">
            <Compass className="w-3.5 h-3.5 text-amber-400" />
            {illustration?.biome || 'Sanctum'}
          </span>
          {illustration?.mood && (
            <span className="hidden sm:inline-flex px-2.5 py-1 rounded-full bg-slate-950/70 border border-slate-800 text-[11px] text-slate-300 backdrop-blur">
              {illustration.mood.split(',')[0]}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5 pointer-events-auto">
          <button
            onClick={() => setShowPromptDetails(!showPromptDetails)}
            title="Inspect Visual Generation Blueprint"
            className="p-1.5 rounded-xl bg-slate-950/80 hover:bg-slate-800/90 border border-slate-700 text-slate-300 transition backdrop-blur shadow"
          >
            <Info className="w-4 h-4" />
          </button>
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            title={isFullscreen ? 'Exit Fullscreen' : 'Cinematic View'}
            className="p-1.5 rounded-xl bg-slate-950/80 hover:bg-slate-800/90 border border-slate-700 text-slate-300 transition backdrop-blur shadow"
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Cinematic Viewport Graphic */}
      <div
        className={`w-full overflow-hidden flex items-center justify-center transition-all ${
          isFullscreen ? 'h-full max-h-[85vh]' : 'aspect-video max-h-[340px]'
        }`}
        dangerouslySetInnerHTML={{ __html: svgContent }}
      />

      {/* Atmospheric Glow Underline based on Tension */}
      <div
        className="h-1 w-full bg-gradient-to-r from-emerald-500 via-amber-500 to-rose-600 transition-all duration-700 opacity-60"
        style={{
          filter: `drop-shadow(0 0 8px rgba(245, 158, 11, ${Math.min(1, tensionLevel / 100 + 0.2)}))`,
        }}
      />

      {/* Visual Blueprint / Prompt Drawer */}
      {showPromptDetails && (
        <div className="p-4 bg-slate-950/95 border-t border-slate-800 flex flex-col gap-2 text-xs animate-fade-in">
          <div className="flex items-center justify-between text-slate-400">
            <span className="font-semibold text-slate-200 flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              Generative Scene Blueprint
            </span>
            <span className="font-mono text-[10px] text-slate-500">
              Style: {illustration?.composition_style || 'Procedural Vector'}
            </span>
          </div>

          <div className="bg-slate-900/80 rounded-xl p-3 border border-slate-800 text-slate-300 font-mono text-[11px] leading-relaxed">
            <p className="text-amber-300/90 font-medium mb-1">
              Visual Cue: {illustration?.art_prompt || 'Atmospheric establishing shot of the realm.'}
            </p>
            {illustration?.lighting && (
              <p className="text-slate-400 text-[10px]">
                Lighting: {illustration.lighting}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

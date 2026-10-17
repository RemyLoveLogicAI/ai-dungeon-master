// client/src/App.tsx
import React, { useState, useEffect } from 'react';
import {
  GenerativeUIPackage,
  GenerativeActionCard,
  PlayerCharacter,
  WorldState,
  LocationNode,
} from './types';
import {
  checkBackendHealth,
  fetchCurrentWorld,
  fetchPlayerState,
  sendPlayerAction,
} from './services/api';
import { PlatformNav, PlatformSurface } from './components/PlatformNav';
import { D20DiceRoller } from './components/D20DiceRoller';
import { TacticalGrid } from './components/TacticalGrid';
import { ActionCardDeck } from './components/ActionCardDeck';
import { WorldAtlasModal } from './components/WorldAtlasModal';
import { NPCDialogueBox } from './components/NPCDialogueBox';
import { CharacterSheet } from './components/CharacterSheet';
import { AudioDirector } from './components/AudioDirector';
import { DMConsole } from './components/DMConsole';
import { LootModal } from './components/LootModal';
import { Send, Sparkles, Compass, ShieldAlert } from 'lucide-react';

export function App() {
  const [currentSurface, setCurrentSurface] = useState<PlatformSurface>('desktop');
  const [world, setWorld] = useState<WorldState | null>(null);
  const [player, setPlayer] = useState<PlayerCharacter | null>(null);
  const [uiPackage, setUiPackage] = useState<GenerativeUIPackage | null>(null);
  const [narrativeLog, setNarrativeLog] = useState<string[]>([]);
  const [playerInput, setPlayerInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  // Modals & Panels
  const [showAtlas, setShowAtlas] = useState(false);
  const [showDiceModal, setShowDiceModal] = useState(false);
  const [backendHealth, setBackendHealth] = useState({
    status: 'connecting',
    ollama_available: false,
    available_models: [] as string[],
  });

  // Initial Load
  useEffect(() => {
    async function loadData() {
      const health = await checkBackendHealth();
      setBackendHealth(health);

      const w = await fetchCurrentWorld();
      if (w) setWorld(w);

      const p = await fetchPlayerState();
      if (p) setPlayer(p);

      // Initial interaction
      const initialPackage = await sendPlayerAction('survey the sanctuary');
      setUiPackage(initialPackage);
      setNarrativeLog([initialPackage.narrative_text]);
    }
    loadData();
  }, []);

  const handleSendAction = async (actionText: string, cardId?: string) => {
    if (!actionText.trim() || isProcessing) return;
    setIsProcessing(true);
    setPlayerInput('');

    try {
      const nextPackage = await sendPlayerAction(actionText, cardId);
      setUiPackage(nextPackage);
      setNarrativeLog((prev) => [...prev, nextPackage.narrative_text]);

      // Update player state if backend is live
      const updatedPlayer = await fetchPlayerState();
      if (updatedPlayer) setPlayer(updatedPlayer);

      const updatedWorld = await fetchCurrentWorld();
      if (updatedWorld) setWorld(updatedWorld);
    } catch (err) {
      console.error('Action error', err);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleCardSelect = (card: GenerativeActionCard) => {
    handleSendAction(`${card.title}: ${card.description}`, card.id);
  };

  const handleDiceRollComplete = (result: { roll: number; total: number; isCrit: boolean; isFumble: boolean }) => {
    const outcomeText = result.isCrit
      ? 'rolled a NATURAL 20! Critical triumph!'
      : result.isFumble
      ? 'rolled a NATURAL 1! Critical fumble!'
      : `rolled a ${result.roll} for a total of ${result.total}`;
    handleSendAction(`Fate Check: The player ${outcomeText}`);
  };

  const handleRegenerateWorld = async () => {
    try {
      await fetch('/api/world/generate', { method: 'POST' });
      const w = await fetchCurrentWorld();
      if (w) setWorld(w);
      const pkg = await sendPlayerAction('survey the new realm');
      setUiPackage(pkg);
      setNarrativeLog([pkg.narrative_text]);
    } catch {
      // Local fallback
      window.location.reload();
    }
  };

  const locationName = uiPackage?.location_name || world?.name || 'Sanctum of the Dawn';
  const tension = uiPackage?.tension_level || 20;

  return (
    <div
      className={`min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-amber-500 selection:text-slate-950 ${
        currentSurface === 'tv' ? 'scale-105 origin-top' : ''
      }`}
    >
      {/* Navigation Header */}
      <PlatformNav
        currentSurface={currentSurface}
        onChangeSurface={setCurrentSurface}
        onOpenAtlas={() => setShowAtlas(true)}
        onToggleDiceModal={() => setShowDiceModal(!showDiceModal)}
        locationName={locationName}
      />

      {/* Main Container Layout */}
      <main
        className={`flex-1 w-full mx-auto p-4 md:p-6 transition-all ${
          currentSurface === 'mobile'
            ? 'max-w-md'
            : currentSurface === 'tv'
            ? 'max-w-7xl'
            : 'max-w-7xl'
        }`}
      >
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* LEFT COLUMN: Character HUD & Soundtrack (Cols 1-3 on Desktop) */}
          <div
            className={`flex flex-col gap-5 ${
              currentSurface === 'mobile' ? 'order-2' : 'lg:col-span-3 order-1'
            }`}
          >
            <CharacterSheet player={player} />
            <AudioDirector directive={uiPackage?.soundtrack} />
            <DMConsole
              tension={tension}
              world={world}
              ollamaAvailable={backendHealth.ollama_available}
              availableModels={backendHealth.available_models}
              onRegenerateWorld={handleRegenerateWorld}
            />
          </div>

          {/* CENTER COLUMN: Generative Story & Dynamic UI Stage (Cols 4-8 on Desktop) */}
          <div
            className={`flex flex-col gap-5 ${
              currentSurface === 'mobile' ? 'order-1' : 'lg:col-span-6 order-2'
            }`}
          >
            {/* Tactical Grid (Spawned conditionally when in Combat) */}
            {uiPackage?.tactical_grid && (
              <div className="animate-fade-in">
                <TacticalGrid gridState={uiPackage.tactical_grid} />
              </div>
            )}

            {/* NPC Interaction (Spawned conditionally when Dialogue occurs) */}
            {uiPackage?.npc_interaction && (
              <div className="animate-fade-in">
                <NPCDialogueBox
                  npc={uiPackage.npc_interaction}
                  onSelectReply={(reply) => handleSendAction(`Reply to ${uiPackage.npc_interaction?.name}: "${reply}"`)}
                />
              </div>
            )}

            {/* Living Narrative Chronicle */}
            <div className="bg-slate-900/90 border border-slate-700/80 rounded-2xl p-5 shadow-2xl backdrop-blur-md flex flex-col gap-4 max-h-[500px] overflow-y-auto">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <span className="text-xs uppercase font-bold tracking-wider text-amber-400 flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5" />
                  Chronicle of {world?.name || 'the Realm'}
                </span>
                <span className="text-[10px] font-mono text-slate-500">
                  {narrativeLog.length} Narrative Turns
                </span>
              </div>

              <div className="flex flex-col gap-4 text-sm leading-relaxed text-slate-300">
                {narrativeLog.map((entry, index) => (
                  <div
                    key={index}
                    className={`p-3 rounded-xl border ${
                      index === narrativeLog.length - 1
                        ? 'bg-slate-950/90 border-amber-500/40 text-slate-100 shadow-md'
                        : 'bg-slate-950/40 border-slate-800/80 text-slate-400'
                    }`}
                  >
                    <p className="whitespace-pre-line font-serif">{entry}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Generative Action Deck */}
            {uiPackage?.action_deck && uiPackage.action_deck.length > 0 && (
              <ActionCardDeck
                cards={uiPackage.action_deck}
                onSelectAction={handleCardSelect}
                disabled={isProcessing}
              />
            )}

            {/* Interactive Player Command Bar */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendAction(playerInput);
              }}
              className="relative flex items-center gap-2 mt-1"
            >
              <input
                type="text"
                value={playerInput}
                onChange={(e) => setPlayerInput(e.target.value)}
                placeholder="Describe your intent, spell, or dialogue to the DM..."
                disabled={isProcessing}
                className="w-full bg-slate-900/90 border border-slate-700/80 focus:border-amber-500 rounded-2xl py-3 pl-4 pr-12 text-sm text-slate-100 placeholder-slate-500 outline-none transition shadow-lg"
              />
              <button
                type="submit"
                disabled={isProcessing || !playerInput.trim()}
                className="absolute right-2 p-2 rounded-xl bg-amber-500 hover:bg-amber-400 disabled:opacity-40 disabled:hover:bg-amber-500 text-slate-950 transition active:scale-95 shadow"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>

          {/* RIGHT COLUMN: D20 Fate Core & World Overview (Cols 9-12 on Desktop) */}
          <div
            className={`flex flex-col gap-5 ${
              currentSurface === 'mobile' ? 'order-3' : 'lg:col-span-3 order-3'
            }`}
          >
            <D20DiceRoller onRollComplete={handleDiceRollComplete} modifier={player?.attack_bonus || 5} />

            {/* Current Region Snapshot Card */}
            {world && (
              <div className="bg-slate-900/90 border border-slate-700/80 rounded-2xl p-4 shadow-xl backdrop-blur-md flex flex-col gap-3">
                <div className="flex items-center gap-2 text-xs uppercase font-bold text-slate-300">
                  <Compass className="w-4 h-4 text-emerald-400" />
                  Active Region
                </div>
                <div className="text-xs text-slate-400 leading-snug">
                  <span className="font-semibold text-slate-200">{locationName}</span>
                  <p className="mt-1">
                    {world.locations.find((l) => l.name === locationName)?.description ||
                      'An ancient realm steeped in myth and guarded by stone sentinels.'}
                  </p>
                </div>
                <button
                  onClick={() => setShowAtlas(true)}
                  className="w-full mt-1 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-slate-300 transition"
                >
                  Inspect Realm Atlas
                </button>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* World Atlas Modal */}
      {showAtlas && (
        <WorldAtlasModal
          world={world}
          onClose={() => setShowAtlas(false)}
          onSelectLocation={(loc: LocationNode) => {
            setShowAtlas(false);
            handleSendAction(`Travel toward ${loc.name} (${loc.biome})`);
          }}
        />
      )}

      {/* Loot Drop Modal (Triggered when enemies are vanquished) */}
      {uiPackage?.loot && uiPackage.loot.length > 0 && (
        <LootModal
          loot={uiPackage.loot}
          onClose={() => {
            setUiPackage({ ...uiPackage, loot: null });
          }}
          onClaimItem={(item) => {
            if (player) {
              setPlayer({ ...player, inventory: [...player.inventory, item.name] });
            }
          }}
        />
      )}
    </div>
  );
}

export default App;

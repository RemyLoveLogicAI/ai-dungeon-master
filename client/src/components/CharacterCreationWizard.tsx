// client/src/components/CharacterCreationWizard.tsx
import React, { useEffect, useState } from 'react';
import { CampaignSummary, CharacterCatalog, CharacterClassOption, CharacterSheetData } from '../types';
import { activateCharacter, createCharacter, fetchCampaignList, fetchCharacterCatalog } from '../services/api';
import { Shield, Sparkles, Swords, BookOpen, ScrollText, Loader2, ChevronRight, ChevronLeft, X } from 'lucide-react';
import { PortraitIcon } from './PortraitIcon';

type Step = 'loading' | 'select' | 'class' | 'details' | 'appearance' | 'creating' | 'error';

const CLASS_ICONS: Record<string, React.ReactNode> = {
  Fighter: <Swords className="w-6 h-6" />,
  Rogue: <ScrollText className="w-6 h-6" />,
  Wizard: <Sparkles className="w-6 h-6" />,
  Cleric: <Shield className="w-6 h-6" />,
};

interface CharacterCreationWizardProps {
  onComplete: (campaignId: string, character: CharacterSheetData) => void;
  /** When provided, the wizard was opened from an active game (not first load) and can be dismissed back to it. */
  onCancel?: () => void;
}

export const CharacterCreationWizard: React.FC<CharacterCreationWizardProps> = ({ onComplete, onCancel }) => {
  const [step, setStep] = useState<Step>('loading');
  const [catalog, setCatalog] = useState<CharacterCatalog | null>(null);
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([]);
  const [selectedClass, setSelectedClass] = useState<CharacterClassOption | null>(null);
  const [name, setName] = useState('');
  const [concept, setConcept] = useState('');
  const [appearance, setAppearance] = useState('');
  const [portraitId, setPortraitId] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [resumingId, setResumingId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [catalogData, campaignData] = await Promise.all([
          fetchCharacterCatalog(),
          fetchCampaignList(),
        ]);
        if (cancelled) return;
        setCatalog(catalogData);
        setCampaigns(campaignData);
        setStep(campaignData.length > 0 ? 'select' : 'class');
      } catch {
        if (!cancelled) {
          setErrorMessage('The realm archives could not be reached. Check that the DM engine is running.');
          setStep('error');
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleResume = async (campaignId: string) => {
    setResumingId(campaignId);
    setErrorMessage('');
    try {
      const result = await activateCharacter(campaignId);
      if (!result) {
        setErrorMessage('That adventurer could not be found. It may have been from an earlier session.');
        setResumingId(null);
        return;
      }
      onComplete(campaignId, result.character);
    } catch {
      setErrorMessage('Could not resume that adventurer. Check that the DM engine is running.');
      setResumingId(null);
    }
  };

  const handleCreate = async () => {
    if (!selectedClass || !name.trim()) return;
    setStep('creating');
    setErrorMessage('');
    try {
      const result = await createCharacter({
        name: name.trim(),
        concept: concept.trim(),
        appearance: appearance.trim(),
        portrait_id: portraitId,
        class: selectedClass.name,
      });
      onComplete(result.campaign_id, result.character);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Character creation failed.');
      setStep('appearance');
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950 flex items-center justify-center p-4 md:p-8 overflow-y-auto">
      <div className="relative w-full max-w-2xl bg-slate-900/95 border border-slate-700/80 rounded-2xl shadow-2xl backdrop-blur-md p-5 md:p-8 flex flex-col gap-6">
        {onCancel && step !== 'creating' && (
          <button
            onClick={onCancel}
            aria-label="Return to your adventure"
            title="Return to your adventure"
            className="absolute top-4 right-4 p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-100 transition"
          >
            <X className="w-5 h-5" />
          </button>
        )}
        <header className="flex flex-col gap-1 text-center">
          <h1 className="font-serif text-2xl md:text-3xl font-bold text-amber-300 tracking-wide">
            Aegis Dungeon Master
          </h1>
          <p className="text-xs md:text-sm text-slate-400">
            {step === 'select' && 'Choose your adventurer, or forge a new one.'}
            {step === 'class' && 'Choose your calling.'}
            {step === 'details' && 'Give your adventurer a name.'}
            {step === 'appearance' && 'Picture them.'}
            {(step === 'loading' || step === 'creating') && 'The archives stir...'}
            {step === 'error' && 'A problem in the archives.'}
          </p>
        </header>

        {step === 'loading' && (
          <div className="flex flex-col items-center gap-3 py-10 text-slate-400" role="status" aria-live="polite">
            <Loader2 className="w-8 h-8 animate-spin text-amber-400" />
            <span className="text-sm">Consulting the realm archives...</span>
          </div>
        )}

        {step === 'error' && (
          <div className="flex flex-col items-center gap-4 py-8">
            <p className="text-sm text-red-300 text-center" role="alert">{errorMessage}</p>
            <button
              onClick={() => {
                setStep('loading');
                setErrorMessage('');
                window.location.reload();
              }}
              className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-semibold text-sm transition"
            >
              Retry
            </button>
          </div>
        )}

        {step === 'select' && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-2 max-h-72 overflow-y-auto">
              {campaigns.map((c) => (
                <button
                  key={c.id}
                  onClick={() => handleResume(c.id)}
                  disabled={resumingId !== null}
                  className="w-full flex items-center justify-between gap-3 p-3 rounded-xl bg-slate-800/80 border border-slate-700 hover:border-amber-500/60 hover:bg-slate-800 transition text-left disabled:opacity-50"
                >
                  <div>
                    <p className="text-sm font-semibold text-slate-100">{c.character_name || c.title}</p>
                    <p className="text-[11px] text-slate-400 font-mono">{c.phase}</p>
                  </div>
                  {resumingId === c.id ? (
                    <Loader2 className="w-4 h-4 animate-spin text-amber-400" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-slate-500" />
                  )}
                </button>
              ))}
            </div>
            {errorMessage && (
              <p className="text-xs text-red-300 text-center" role="alert">{errorMessage}</p>
            )}
            <button
              onClick={() => setStep('class')}
              className="w-full py-3 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-semibold text-sm transition active:scale-[0.99]"
            >
              Forge a New Adventurer
            </button>
          </div>
        )}

        {step === 'class' && catalog && (
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {catalog.classes.map((option) => (
                <button
                  key={option.name}
                  onClick={() => setSelectedClass(option)}
                  className={`flex flex-col gap-2 p-4 rounded-xl border text-left transition ${
                    selectedClass?.name === option.name
                      ? 'border-amber-500 bg-amber-500/10 shadow-[0_0_0_1px_rgba(245,158,11,0.4)]'
                      : 'border-slate-700 bg-slate-800/60 hover:border-slate-600'
                  }`}
                >
                  <span className="flex items-center gap-2 text-amber-300">
                    {CLASS_ICONS[option.name] ?? <BookOpen className="w-6 h-6" />}
                    <span className="font-bold text-sm text-slate-100">{option.name}</span>
                  </span>
                  <span className="text-[11px] text-slate-400 leading-snug">{option.description}</span>
                </button>
              ))}
            </div>
            <p className="text-[11px] text-slate-500 text-center">{catalog.scope}</p>
            <div className="flex items-center justify-between gap-2">
              {campaigns.length > 0 ? (
                <button
                  onClick={() => setStep('select')}
                  className="flex items-center gap-1 px-3 py-2 rounded-xl text-xs text-slate-400 hover:text-slate-200 transition"
                >
                  <ChevronLeft className="w-3.5 h-3.5" /> Back
                </button>
              ) : (
                <span />
              )}
              <button
                onClick={() => setStep('details')}
                disabled={!selectedClass}
                className="flex items-center gap-1 px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 disabled:opacity-40 disabled:hover:bg-amber-500 text-slate-950 font-semibold text-sm transition active:scale-[0.99]"
              >
                Continue <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {step === 'details' && selectedClass && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="char-name" className="text-xs font-semibold text-slate-300">
                Adventurer's name
              </label>
              <input
                id="char-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Thistle Ironfoot"
                autoFocus
                maxLength={80}
                className="w-full bg-slate-800/90 border border-slate-700 focus:border-amber-500 rounded-xl py-2.5 px-3 text-sm text-slate-100 placeholder-slate-500 outline-none transition"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="char-concept" className="text-xs font-semibold text-slate-300">
                Concept <span className="text-slate-500 font-normal">(optional)</span>
              </label>
              <textarea
                id="char-concept"
                value={concept}
                onChange={(e) => setConcept(e.target.value)}
                placeholder="A brief idea of who they are..."
                maxLength={2000}
                rows={3}
                className="w-full bg-slate-800/90 border border-slate-700 focus:border-amber-500 rounded-xl py-2.5 px-3 text-sm text-slate-100 placeholder-slate-500 outline-none transition resize-none"
              />
            </div>
            <div className="flex items-center gap-2 p-3 rounded-xl bg-slate-800/60 border border-slate-700 text-xs text-slate-400">
              {CLASS_ICONS[selectedClass.name]}
              <span>
                Level 1 Human <span className="text-slate-200 font-semibold">{selectedClass.name}</span>,{' '}
                {selectedClass.background} background
              </span>
            </div>
            {errorMessage && (
              <p className="text-xs text-red-300 text-center" role="alert">{errorMessage}</p>
            )}
            <div className="flex items-center justify-between gap-2">
              <button
                onClick={() => setStep('class')}
                className="flex items-center gap-1 px-3 py-2 rounded-xl text-xs text-slate-400 hover:text-slate-200 transition"
              >
                <ChevronLeft className="w-3.5 h-3.5" /> Back
              </button>
              <button
                onClick={() => setStep('appearance')}
                disabled={!name.trim()}
                className="flex items-center gap-1 px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 disabled:opacity-40 disabled:hover:bg-amber-500 text-slate-950 font-semibold text-sm transition active:scale-[0.99]"
              >
                Continue <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {step === 'appearance' && catalog && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="char-appearance" className="text-xs font-semibold text-slate-300">
                Appearance <span className="text-slate-500 font-normal">(optional)</span>
              </label>
              <textarea
                id="char-appearance"
                value={appearance}
                onChange={(e) => setAppearance(e.target.value)}
                placeholder="Describe how they look: build, hair, scars, gear, anything that makes them them..."
                maxLength={1000}
                rows={3}
                className="w-full bg-slate-800/90 border border-slate-700 focus:border-amber-500 rounded-xl py-2.5 px-3 text-sm text-slate-100 placeholder-slate-500 outline-none transition resize-none"
              />
            </div>

            <div className="flex flex-col gap-2">
              <span className="text-xs font-semibold text-slate-300">
                Portrait style <span className="text-slate-500 font-normal">(optional)</span>
              </span>
              <div className="grid grid-cols-3 sm:grid-cols-5 gap-2" role="group" aria-label="Portrait style">
                {catalog.portraits.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => setPortraitId(portraitId === option.id ? '' : option.id)}
                    aria-pressed={portraitId === option.id}
                    className={`flex flex-col items-center gap-1.5 p-3 rounded-xl border text-center transition ${
                      portraitId === option.id
                        ? 'border-amber-500 bg-amber-500/10 text-amber-300 shadow-[0_0_0_1px_rgba(245,158,11,0.4)]'
                        : 'border-slate-700 bg-slate-800/60 text-slate-300 hover:border-slate-600'
                    }`}
                  >
                    <PortraitIcon portraitId={option.id} className="w-6 h-6" />
                    <span className="text-[10px] font-semibold">{option.label}</span>
                  </button>
                ))}
              </div>
              <p className="text-[11px] text-slate-500">
                A stylized icon to mark them in the HUD and on the map — no AI-generated art yet, picking
                none is fine too.
              </p>
            </div>

            <div className="flex items-center gap-2 p-3 rounded-xl bg-slate-800/60 border border-slate-700 text-xs text-slate-400">
              <PortraitIcon portraitId={portraitId} className="w-6 h-6 text-amber-300" />
              <span>
                {name || 'Your adventurer'}, Level 1 Human{' '}
                <span className="text-slate-200 font-semibold">{selectedClass?.name}</span>
              </span>
            </div>

            {errorMessage && (
              <p className="text-xs text-red-300 text-center" role="alert">{errorMessage}</p>
            )}
            <div className="flex items-center justify-between gap-2">
              <button
                onClick={() => setStep('details')}
                className="flex items-center gap-1 px-3 py-2 rounded-xl text-xs text-slate-400 hover:text-slate-200 transition"
              >
                <ChevronLeft className="w-3.5 h-3.5" /> Back
              </button>
              <button
                onClick={handleCreate}
                className="flex items-center gap-1 px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-semibold text-sm transition active:scale-[0.99]"
              >
                Begin the Adventure <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {step === 'creating' && (
          <div className="flex flex-col items-center gap-3 py-10 text-slate-400" role="status" aria-live="polite">
            <Loader2 className="w-8 h-8 animate-spin text-amber-400" />
            <span className="text-sm">Forging {name}...</span>
          </div>
        )}
      </div>
    </div>
  );
};

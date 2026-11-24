<!-- Generated: 2026-11-24 | Files scanned: 20 | Token estimate: ~800 -->
# Codemap: frontend

React 19 + Vite 8 + Tailwind 4 client in `client/` (TypeScript, bun). Two
non-React renderers also ship: `web/` static JS and `web/xr/` three.js.

## Composition (`client/src/App.tsx`, 375 ln)

`App` state machine: `view: 'checking' | 'wizard' | 'game'`.
- Boot: `checkBackendHealth` → if `localStorage.adm_campaign_id` exists,
  `activateCharacter(id)` restores that character (the server rebuilds
  player state — it does not resume the previous story turn); on failure
  or a missing campaign the stored id is cleared and
  `CharacterCreationWizard` opens. No saved id → wizard directly.
- `handleSendAction` → `sendPlayerAction` → updates `uiPackage`,
  `narrativeLog`, refetches player + world.
- `PlatformNav` switches `PlatformSurface` ('desktop' | 'mobile' | 'tv') and
  opens atlas/switch-character.
- `D20DiceRoller` renders inline in the right column (result →
  `sendPlayerAction`); a `showDiceModal` state flag is toggled in `App.tsx`
  but unused — there is no dice modal. Modal-style overlays:
  `WorldAtlasModal`, `LootModal`; the `wizard` view renders
  `CharacterCreationWizard`. `CharacterSheet`, `AudioDirector` and
  `DMConsole` are inline left-column panels (App.tsx:200-215), not modals.

## Components (13 files in `client/src/components/`)

| Group | Components |
| --- | --- |
| World/scene | `SceneViewport`, `WorldAtlasModal`, `PlatformNav`, `PortraitIcon` |
| Character | `CharacterSheet`, `CharacterCreationWizard` |
| Combat | `TacticalGrid`, `D20DiceRoller`, `ActionCardDeck`, `LootModal` |
| DM/audio | `DMConsole`, `NPCDialogueBox`, `AudioDirector` |

## `client/src/services/api.ts` — function → endpoint

| Function | Endpoint |
| --- | --- |
| `checkBackendHealth` | `GET /api/health` (2 s timeout; offline fallback object) |
| `fetchCurrentWorld` | `GET /api/world/current` → `data.world` |
| `fetchPlayerState` | `GET /api/player` → `data.player` |
| `sendPlayerAction(action, cardId?)` | `POST /api/dm/interact` `{action, card_id}`; offline fallback package |
| `fetchCharacterCatalog` | `GET /api/characters/catalog` |
| `fetchCampaignList` | `GET /api/characters` → `data.campaigns` |
| `createCharacter(input)` | `POST /api/characters` |
| `activateCharacter(campaignId)` | `POST /api/characters/{id}/activate` (404 → null) |
| `rollCombatAttack(params)` | `POST /api/combat/attack` `{attacker, target, advantage}`; offline RNG fallback |

`API_BASE = '/api'` — relative, so Vite proxy (`vite.config.ts`: `/api` →
`localhost:8000`, `/ws` → `ws://localhost:8000`) or the `api_server`
`client/dist` mount both work. Note: client never sends `X-Session-ID`; all
browser sessions share the `"default"` session.

## Audio

`client/src/audio/procedural_synth.ts` (307 ln): `proceduralAudio` WebAudio
singleton — `updateTheme(theme, intensity)`, `playDiceRoll`, `playSwordClash`,
`playFireball`, `playCritFanfare`. Driven by `SoundtrackDirective` from the UI
package via `AudioDirector`. Server-side WAVs remain available at
`/api/audio/sfx/{sound_name}` but the React client does not call them.

## Other renderers

- `web/` — dependency-free static client (`app.js`, `play.js`, `style.css`)
  rendering `agentsurface-blueprint/0.1` envelopes; `build_demo.py` generates
  `demo-data.json`; deployed to GitHub Pages by `pages.yml`.
- `web/xr/` — three.js + cannon-es XR client (`main.js`, `panel.js`, `dice.js`)
  talking to `vr_server.py` (`/api/surface`, `/api/intent`, `/sfx/`).
- `web/play.js` targets `game_server.py` :8766 (`/api/campaigns*`), the
  deterministic campaign path — separate from the `api_server` UI path.

## Shells

- **Tauri** (`client/src-tauri/`): `tauri.conf.json` productName
  `aegis-dungeon-master`, id `com.aegis.dungeonmaster`, devUrl :5173,
  frontendDist `../dist`, window 1280×860.
- **Android** (`client/android/`): Capacitor 8 project; `bunx cap sync android`
  / `bunx cap open android`.

## Types

`client/src/types/index.ts` (215 ln): `GenerativeUIPackage`,
`GenerativeActionCard`, `PlayerCharacter`, `WorldState`, `LocationNode`,
`CharacterCatalog`, `CampaignSummary`, `CharacterSheetData`,
`CreateCharacterInput`, `SoundtrackDirective` — API payload projections
shaped after the Python dataclasses in `engine/generative_ui.py` /
`engine/story_engine.py` / `campaign_core.py` (field subsets, not exact
mirrors).

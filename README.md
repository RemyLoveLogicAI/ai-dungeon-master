# Aegis AI Dungeon Master

An agentic, multi-surface AI Dungeon Master engine capable of generating full mythic worlds, branching narratives, procedural ambient music, and dynamic **Generative UI** in real time as the story unfolds.

---

## 🌟 Multi-Surface Architecture

- **📱 Android Native App (`client/android/`)**: Complete native Gradle project powered by Capacitor and PWA manifest. Installable on Android devices with tactile touch controls, vibration haptics, and offline asset caching.
- **🌐 Responsive Web UI (`client/`)**: High-performance Vite + React + Tailwind CSS client designed for modern desktop browsers, mobile viewports, Quest 3 VR headsets, and Television casting.
- **🖥️ Ultra-Light Desktop GUI (`desktop_launcher.py` & `client/src-tauri/`)**:
  - **Innovative Native Desktop Runner**: Instant sub-second startup using system-native GPU-accelerated frameless WebKit windows—zero Electron memory bloat (< 25MB RAM).
  - **Tauri v2 Desktop App**: Native compiled Rust wrapper bundle (`src-tauri/`) with system tray and window controls.
  - **Terminal TUI Cockpit (`engine/dm_tui.py`)**: Dedicated hacker terminal cockpit with live ANSI tactical matrix, dice rolls, and streaming narration.

---

## ⚡ Generative Features

1. **Procedural World & Faction Engine (`engine/world_generator.py`)**:
   - Generates cosmology, epochs, Ley-fault cataclysms, faction ideologies, leaders, and influence ratings.
   - Generates an interactive 2D SVG Realm Atlas with interconnected biomes (Obsidian Crags, Sunken Crypts, Gargoyle Roost, Whispering Fen, Astral Observatory).
2. **Generative UI Engine (`engine/generative_ui.py`)**:
   - The AI DM does not just emit text—it synthesizes interactive UI components dynamically:
     - **Dynamic Action Decks**: Context-sensitive cards calibrated with DC targets, stat modifiers, and risk levels (Low, Medium, High, Lethal).
     - **Tactical Combat Matrix**: 8x8 spatial battle grid with hero/enemy tokens, HP gauges, range rings, and combat stances.
     - **Tactile D20 Fate Core**: Interactive 3D/pseudo-3D dice roller with tumbling physics, Advantage/Disadvantage modes, and critical success/fumble fanfares.
     - **NPC Dialogue Cards**: Dynamic portraits, mood meters, voice tones, and branching speech replies.
     - **Procedural Loot Drops**: Rarity-tiered items (Common to Mythic) with stats and equip actions.
3. **Procedural Music & SFX Synthesis**:
   - **Web Audio API Engine (`client/src/audio/procedural_synth.ts`)**: Generates real-time ambient soundscapes directly in the browser—subterranean drones, resonant lowpass filters, battle tension kicks, and melodic arpeggiated chimes. Zero external audio downloads needed.
   - **Procedural SFX Generators**: Synthesizes dice tumble clicks, metallic sword clashes, resonant fireballs, and triumphant fanfare chords.
   - **Python WAV Synthesizer (`audio_synth.py`)**: Produces 16-bit PCM WAV audio stems on the backend.
4. **Agentic DM Intelligence (`engine/story_engine.py`)**:
   - **Dual AI Core**: Automatic auto-detection for local **Ollama** models (`llama3.2:3b`, `qwen3:8b`, `freestream-qwen3-8b-4k`, `dolphin3:8b`), seamlessly paired with a robust offline heuristic procedural generator.

---

## 🚀 Quick Start

### 1. Launch All-in-One Desktop App
```bash
uv run python desktop_launcher.py
```
*Spawns the local FastAPI backend and automatically opens a dedicated, frameless desktop window.*

### 2. Launch Terminal TUI Cockpit
```bash
uv run dm-tui
# or
uv run python desktop_launcher.py --tui
```

### 3. Run Web Development Server
```bash
# Terminal 1: Backend API
uv run uvicorn engine.api_server:app --reload --port 8000

# Terminal 2: Web Client
cd client
bun run dev
```
Open [http://localhost:5173](http://localhost:5173).

### 4. Build & Run Android App
```bash
cd client
bun run build
bunx cap sync android
bunx cap open android  # Opens in Android Studio / Gradle
```

---

## 🧪 Testing

Run unit tests via `uv`:
```bash
uv run pytest -v
```

Run ruff linter & formatter:
```bash
uv run ruff check .
uv run ruff format --check .
```

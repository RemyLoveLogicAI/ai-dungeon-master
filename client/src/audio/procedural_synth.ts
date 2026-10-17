// client/src/audio/procedural_synth.ts
// Real-time Procedural Ambient Music and Sound Effects Synthesizer using Web Audio API

class ProceduralAudioEngine {
  private ctx: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  private musicGain: GainNode | null = null;
  private sfxGain: GainNode | null = null;

  // Music generators
  private droneOsc1: OscillatorNode | null = null;
  private droneOsc2: OscillatorNode | null = null;
  private filterNode: BiquadFilterNode | null = null;
  private isMusicPlaying = false;
  private currentTheme: string = 'ambient_drone';
  private currentIntensity: number = 0.25;
  private arpeggioTimer: number | null = null;
  private pulseTimer: number | null = null;

  private isMuted = false;

  private initContext() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      this.ctx = new AudioCtx();

      this.masterGain = this.ctx.createGain();
      this.masterGain.gain.setValueAtTime(0.7, this.ctx.currentTime);
      this.masterGain.connect(this.ctx.destination);

      this.musicGain = this.ctx.createGain();
      this.musicGain.gain.setValueAtTime(0.4, this.ctx.currentTime);
      this.musicGain.connect(this.masterGain);

      this.sfxGain = this.ctx.createGain();
      this.sfxGain.gain.setValueAtTime(0.6, this.ctx.currentTime);
      this.sfxGain.connect(this.masterGain);
    }

    if (this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
  }

  public setMuted(muted: boolean) {
    this.isMuted = muted;
    if (this.masterGain && this.ctx) {
      this.masterGain.gain.setTargetAtTime(muted ? 0 : 0.7, this.ctx.currentTime, 0.05);
    }
  }

  public getMuted(): boolean {
    return this.isMuted;
  }

  public setMasterVolume(val: number) {
    if (this.masterGain && this.ctx && !this.isMuted) {
      this.masterGain.gain.setTargetAtTime(Math.max(0, Math.min(1, val)), this.ctx.currentTime, 0.05);
    }
  }

  // --- PROCEDURAL SFX SYNTHESIS ---

  public playDiceRoll() {
    this.initContext();
    if (!this.ctx || !this.sfxGain || this.isMuted) return;

    const now = this.ctx.currentTime;
    // Synthesize 6 quick cascading dice tumble clicks
    for (let i = 0; i < 6; i++) {
      const clickTime = now + i * 0.06 + Math.random() * 0.02;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = 'triangle';
      osc.frequency.setValueAtTime(140 + Math.random() * 80, clickTime);
      osc.frequency.exponentialRampToValueAtTime(40, clickTime + 0.03);

      gain.gain.setValueAtTime(0.35, clickTime);
      gain.gain.exponentialRampToValueAtTime(0.001, clickTime + 0.035);

      osc.connect(gain);
      gain.connect(this.sfxGain);

      osc.start(clickTime);
      osc.stop(clickTime + 0.04);
    }
  }

  public playSwordClash() {
    this.initContext();
    if (!this.ctx || !this.sfxGain || this.isMuted) return;

    const now = this.ctx.currentTime;
    // Metallic resonant overtones
    const freqs = [2350, 3820, 1120];
    freqs.forEach((freq) => {
      const osc = this.ctx!.createOscillator();
      const gain = this.ctx!.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, now);

      gain.gain.setValueAtTime(0.25, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.45);

      osc.connect(gain);
      gain.connect(this.sfxGain!);

      osc.start(now);
      osc.stop(now + 0.5);
    });

    // White noise impact transient
    const bufferSize = this.ctx.sampleRate * 0.08;
    const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
      data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (this.ctx.sampleRate * 0.02));
    }
    const noise = this.ctx.createBufferSource();
    noise.buffer = buffer;
    const noiseGain = this.ctx.createGain();
    noiseGain.gain.setValueAtTime(0.3, now);
    noise.connect(noiseGain);
    noiseGain.connect(this.sfxGain);
    noise.start(now);
  }

  public playFireball() {
    this.initContext();
    if (!this.ctx || !this.sfxGain || this.isMuted) return;

    const now = this.ctx.currentTime;
    // Low sub rumble drop
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(110, now);
    osc.frequency.exponentialRampToValueAtTime(32, now + 0.7);

    // Filter
    const filter = this.ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.setValueAtTime(400, now);
    filter.frequency.exponentialRampToValueAtTime(80, now + 0.7);

    gain.gain.setValueAtTime(0.5, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.75);

    osc.connect(filter);
    filter.connect(gain);
    gain.connect(this.sfxGain);

    osc.start(now);
    osc.stop(now + 0.8);
  }

  public playCritFanfare() {
    this.initContext();
    if (!this.ctx || !this.sfxGain || this.isMuted) return;

    const now = this.ctx.currentTime;
    // C major triumphant arpeggio: C5 (523.25), E5 (659.25), G5 (783.99), C6 (1046.50)
    const notes = [523.25, 659.25, 783.99, 1046.5];
    notes.forEach((freq, idx) => {
      const startTime = now + idx * 0.1;
      const osc = this.ctx!.createOscillator();
      const gain = this.ctx!.createGain();

      osc.type = 'triangle';
      osc.frequency.setValueAtTime(freq, startTime);

      gain.gain.setValueAtTime(0.3, startTime);
      gain.gain.exponentialRampToValueAtTime(0.001, startTime + 0.6);

      osc.connect(gain);
      gain.connect(this.sfxGain!);

      osc.start(startTime);
      osc.stop(startTime + 0.7);
    });
  }

  // --- PROCEDURAL AMBIENT SOUNDTRACK GENERATOR ---

  public startSoundtrack(theme: string = 'ambient_drone', intensity: number = 0.3) {
    this.initContext();
    if (!this.ctx || !this.musicGain) return;

    this.currentTheme = theme;
    this.currentIntensity = intensity;

    if (this.isMusicPlaying) {
      this.updateTheme(theme, intensity);
      return;
    }

    this.isMusicPlaying = true;
    const now = this.ctx.currentTime;

    // Continuous subterranean / atmospheric drone
    this.filterNode = this.ctx.createBiquadFilter();
    this.filterNode.type = 'lowpass';
    this.filterNode.frequency.setValueAtTime(220 + intensity * 600, now);
    this.filterNode.connect(this.musicGain);

    this.droneOsc1 = this.ctx.createOscillator();
    this.droneOsc1.type = 'sine';
    this.droneOsc1.frequency.setValueAtTime(55, now); // A1 note
    this.droneOsc1.connect(this.filterNode);
    this.droneOsc1.start(now);

    this.droneOsc2 = this.ctx.createOscillator();
    this.droneOsc2.type = 'triangle';
    this.droneOsc2.frequency.setValueAtTime(82.4, now); // E2 fifth
    this.droneOsc2.connect(this.filterNode);
    this.droneOsc2.start(now);

    this.startThemeGenerators();
  }

  public updateTheme(theme: string, intensity: number) {
    this.currentTheme = theme;
    this.currentIntensity = intensity;

    if (!this.ctx || !this.filterNode) return;

    const now = this.ctx.currentTime;
    let targetFreq = 220;
    if (theme === 'battle_tension') {
      targetFreq = 850 + intensity * 600;
    } else if (theme === 'ethereal_mystery') {
      targetFreq = 480;
    } else if (theme === 'tavern_hearth') {
      targetFreq = 380;
    }
    this.filterNode.frequency.setTargetAtTime(targetFreq, now, 1.2);

    this.startThemeGenerators();
  }

  private startThemeGenerators() {
    if (this.arpeggioTimer) window.clearInterval(this.arpeggioTimer);
    if (this.pulseTimer) window.clearInterval(this.pulseTimer);

    if (this.currentTheme === 'battle_tension') {
      // Fast rhythmic battle percussion pulse
      this.pulseTimer = window.setInterval(() => {
        this.triggerTensionKick();
      }, 550);
    } else if (this.currentTheme === 'tavern_hearth' || this.currentTheme === 'ethereal_mystery') {
      // Melodic arpeggio chimes
      const scale = this.currentTheme === 'tavern_hearth' ? [220, 261.63, 329.63, 392, 440] : [196, 233.08, 293.66, 349.23, 440];
      this.arpeggioTimer = window.setInterval(() => {
        if (!this.ctx || !this.musicGain || this.isMuted) return;
        const note = scale[Math.floor(Math.random() * scale.length)];
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(note, this.ctx.currentTime);
        gain.gain.setValueAtTime(0.08, this.ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.0001, this.ctx.currentTime + 1.2);
        osc.connect(gain);
        gain.connect(this.musicGain);
        osc.start();
        osc.stop(this.ctx.currentTime + 1.3);
      }, 1200);
    }
  }

  private triggerTensionKick() {
    if (!this.ctx || !this.musicGain || this.isMuted) return;
    const now = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(95, now);
    osc.frequency.exponentialRampToValueAtTime(35, now + 0.18);

    gain.gain.setValueAtTime(0.35, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);

    osc.connect(gain);
    gain.connect(this.musicGain);
    osc.start(now);
    osc.stop(now + 0.22);
  }

  public stopSoundtrack() {
    if (this.droneOsc1) {
      try { this.droneOsc1.stop(); } catch {}
      this.droneOsc1 = null;
    }
    if (this.droneOsc2) {
      try { this.droneOsc2.stop(); } catch {}
      this.droneOsc2 = null;
    }
    if (this.arpeggioTimer) window.clearInterval(this.arpeggioTimer);
    if (this.pulseTimer) window.clearInterval(this.pulseTimer);
    this.isMusicPlaying = false;
  }
}

export const proceduralAudio = new ProceduralAudioEngine();

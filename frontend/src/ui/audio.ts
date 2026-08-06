export type TrackName = 'exploration' | 'combat' | 'victory' | 'defeat' | 'ambient';

export class MusicLibrary {
  private basePath: string;
  private tracks = new Map<string, HTMLAudioElement>();
  private current: HTMLAudioElement | null = null;
  private currentName: string | null = null;
  private volume = 0.35;
  private muted = false;
  private fallback: ((name: TrackName, loop?: boolean) => void) | null = null;

  constructor(basePath = '/music/') {
    this.basePath = basePath;
  }

  setFallback(fn: (name: TrackName, loop?: boolean) => void) {
    this.fallback = fn;
  }

  private audioUrl(name: string): string {
    return `${this.basePath}${name}.mp3`;
  }

  private getTrack(name: string): HTMLAudioElement | undefined {
    return this.tracks.get(name);
  }

  private loadTrack(name: string): Promise<HTMLAudioElement> {
    const existing = this.getTrack(name);
    if (existing) return Promise.resolve(existing);
    return new Promise((resolve, reject) => {
      const audio = new Audio(this.audioUrl(name));
      audio.preload = 'auto';
      audio.addEventListener('canplaythrough', () => {
        this.tracks.set(name, audio);
        resolve(audio);
      }, { once: true });
      audio.addEventListener('error', () => {
        reject(new Error(`Unable to load track ${name}`));
      }, { once: true });
      // Start loading metadata so canplaythrough fires.
      audio.load();
    });
  }

  async playTrack(name: TrackName, loop = false): Promise<boolean> {
    if (this.muted) {
      this.currentName = name;
      return true;
    }

    try {
      const audio = await this.loadTrack(name);
      if (this.current && this.current !== audio) {
        this.stopTrack();
      }
      audio.loop = loop;
      audio.volume = this.volume;
      this.current = audio;
      this.currentName = name;
      await audio.play();
      return true;
    } catch {
      this.currentName = name;
      if (this.fallback) {
        this.fallback(name, loop);
      }
      return false;
    }
  }

  stopTrack(): void {
    if (this.current) {
      this.current.pause();
      this.current.currentTime = 0;
      this.current = null;
    }
  }

  setVolume(volume: number): void {
    this.volume = Math.max(0, Math.min(1, volume));
    if (this.current) {
      this.current.volume = this.volume;
    }
  }

  getVolume(): number {
    return this.volume;
  }

  setMuted(muted: boolean): void {
    this.muted = muted;
    if (this.current) {
      this.current.muted = muted;
      if (muted) {
        this.current.pause();
      } else if (this.currentName) {
        this.current.play().catch(() => {});
      }
    }
  }

  isMuted(): boolean {
    return this.muted;
  }
}

export class AudioController {
  private ctx: AudioContext | null = null;
  muted = false;
  private musicVolume = 0.35;
  private ambientActive = false;
  private ambientType: 'dungeon' | 'cave' | null = null;
  private ambientNodes: {
    source: AudioBufferSourceNode;
    gain: GainNode;
    filter: BiquadFilterNode;
  } | null = null;
  private userGestureStarted = false;
  private music: MusicLibrary;

  constructor() {
    this.music = new MusicLibrary();
    this.music.setFallback((name, loop) => this._fallbackMusic(name, loop));
  }

  private ensureContext(): AudioContext | null {
    if (this.muted) return null;
    if (typeof window === 'undefined') return null;
    if (!this.ctx) {
      const Ctx = (window as any).AudioContext || (window as any).webkitAudioContext;
      if (!Ctx) return null;
      try {
        this.ctx = new Ctx();
      } catch {
        return null;
      }
    }
    if (this.ctx?.state === 'suspended') {
      this.ctx.resume().catch(() => {});
    }
    return this.ctx;
  }

  async ensureStartedFromGesture(): Promise<void> {
    if (this.userGestureStarted) return;
    this.userGestureStarted = true;
    const ctx = this.ensureContext();
    if (!ctx) return;
    if (ctx.state === 'suspended') {
      await ctx.resume().catch(() => {});
    }
  }

  toggleMute(): boolean {
    this.muted = !this.muted;
    this.music.setMuted(this.muted);
    if (this.muted && this.ctx) {
      this.ctx.suspend().catch(() => {});
    } else if (!this.muted && this.ctx) {
      this.ctx.resume().catch(() => {});
      if (this.ambientActive && this.ambientType) {
        this.playAmbient(this.ambientType);
      }
    }
    return this.muted;
  }

  setMusicVolume(volume: number): void {
    this.musicVolume = Math.max(0, Math.min(1, volume));
    this.music.setVolume(this.musicVolume);
    if (this.ambientNodes) {
      this.ambientNodes.gain.gain.setTargetAtTime(this.musicVolume, this.ctx?.currentTime || 0, 0.1);
    }
  }

  getMusicVolume(): number {
    return this.musicVolume;
  }

  // MusicLibrary façade.
  playTrack(name: TrackName, loop = false): Promise<boolean> {
    return this.music.playTrack(name, loop);
  }

  stopTrack(): void {
    this.music.stopTrack();
  }

  // Asset-aware music triggers with generative fallback.
  exploration(): void {
    this.playTrack('exploration', true);
  }

  combatSting(): void {
    this.playTrack('combat', true);
  }

  victory(): void {
    this.playTrack('victory', false);
  }

  defeat(): void {
    this.playTrack('defeat', false);
  }

  private _fallbackMusic(name: TrackName, _loop = false): void {
    switch (name) {
      case 'exploration':
        this._generativeExploration();
        break;
      case 'combat':
        this._generativeCombatSting();
        break;
      case 'victory':
        this._generativeVictory();
        break;
      case 'defeat':
        this._generativeDefeat();
        break;
      case 'ambient':
        if (this.ambientType) {
          this._generativeAmbient(this.ambientType);
        }
        break;
    }
  }

  private _generativeVictory(): void {
    this.tone(523.25, 0.25, 'sine', 0.18);
    this.tone(659.25, 0.25, 'sine', 0.18);
    this.tone(783.99, 0.4, 'sine', 0.18);
  }

  private _generativeDefeat(): void {
    this.tone(392.0, 0.35, 'sine', 0.18, 196.0);
    this.tone(196.0, 0.5, 'sine', 0.18);
  }

  private _generativeExploration(): void {
    const base = 261.63; // C4
    const notes = [base, base * 1.125, base * 1.25, base * 1.5];
    notes.forEach((freq, i) => {
      if (typeof window !== 'undefined') {
        window.setTimeout(() => this.tone(freq, 0.35, 'triangle', 0.08), i * 180);
      }
    });
  }

  private _generativeCombatSting(): void {
    this.tone(196.0, 0.18, 'sawtooth', 0.12);
    this.tone(146.83, 0.28, 'sawtooth', 0.12);
    if (typeof window !== 'undefined') {
      window.setTimeout(() => this.tone(110.0, 0.45, 'sawtooth', 0.14), 220);
    }
  }

  private noiseBuffer(duration: number): AudioBuffer | null {
    const ctx = this.ensureContext();
    if (!ctx) return null;
    const samples = Math.max(1, Math.ceil(ctx.sampleRate * duration));
    const buffer = ctx.createBuffer(1, samples, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < data.length; i++) {
      data[i] = Math.random() * 2 - 1;
    }
    return buffer;
  }

  private playNoise(duration: number, filterFreq: number, gain: number): void {
    const ctx = this.ensureContext();
    if (!ctx) return;
    const buffer = this.noiseBuffer(duration);
    if (!buffer) return;
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    const filter = ctx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.frequency.value = filterFreq;
    filter.Q.value = 1;
    const env = ctx.createGain();
    env.gain.setValueAtTime(gain, ctx.currentTime);
    env.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
    src.connect(filter);
    filter.connect(env);
    env.connect(ctx.destination);
    src.start();
    src.stop(ctx.currentTime + duration);
  }

  private tone(
    frequency: number,
    duration: number,
    type: OscillatorType = 'sine',
    gain = 0.15,
    sweepTo?: number
  ): void {
    const ctx = this.ensureContext();
    if (!ctx) return;
    const osc = ctx.createOscillator();
    osc.type = type;
    osc.frequency.setValueAtTime(frequency, ctx.currentTime);
    if (sweepTo !== undefined) {
      osc.frequency.exponentialRampToValueAtTime(Math.max(20, sweepTo), ctx.currentTime + duration);
    }
    const env = ctx.createGain();
    env.gain.setValueAtTime(0.0001, ctx.currentTime);
    env.gain.linearRampToValueAtTime(gain, ctx.currentTime + Math.min(0.02, duration * 0.2));
    env.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
    osc.connect(env);
    env.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + duration);
  }

  swordHit(): void {
    this.playNoise(0.18, 800, 0.25);
    this.tone(120, 0.12, 'sawtooth', 0.08);
  }

  rangedShot(): void {
    this.tone(1200, 0.22, 'square', 0.12, 400);
  }

  footstep(): void {
    this.playNoise(0.06, 250, 0.08);
  }

  trapTrigger(): void {
    this.playNoise(0.25, 600, 0.25);
    this.tone(150, 0.2, 'sawtooth', 0.12);
  }

  playAmbient(type: 'dungeon' | 'cave'): void {
    this.ambientType = type;
    this.ambientActive = true;
    // Prefer the ambient.mp3 asset if it exists.
    this.playTrack('ambient', true).then((played) => {
      if (!played) {
        this._generativeAmbient(type);
      }
    });
  }

  private _generativeAmbient(type: 'dungeon' | 'cave'): void {
    if (this.muted) return;
    const ctx = this.ensureContext();
    if (!ctx) return;
    this.stopAmbient();

    const duration = 4.0;
    const samples = Math.ceil(ctx.sampleRate * duration);
    const buffer = ctx.createBuffer(1, samples, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    let last = 0;
    for (let i = 0; i < data.length; i++) {
      const white = Math.random() * 2 - 1;
      last = (last + white * 0.05) / 1.05;
      data[i] = last;
    }

    const src = ctx.createBufferSource();
    src.buffer = buffer;
    src.loop = true;

    const filter = ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.value = type === 'cave' ? 180 : 260;
    filter.Q.value = 0.7;

    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0, ctx.currentTime);
    gain.gain.linearRampToValueAtTime(this.musicVolume, ctx.currentTime + 1.5);

    const lfo = ctx.createOscillator();
    lfo.type = 'sine';
    lfo.frequency.value = type === 'cave' ? 0.12 : 0.2;
    const lfoGain = ctx.createGain();
    lfoGain.gain.value = type === 'cave' ? 30 : 45;
    lfo.connect(lfoGain);
    lfoGain.connect(filter.frequency);
    lfo.start();

    src.connect(filter);
    filter.connect(gain);
    gain.connect(ctx.destination);
    src.start();

    this.ambientNodes = { source: src, gain, filter };
  }

  stopAmbient(): void {
    this.ambientActive = false;
    this.music.stopTrack();
    if (!this.ambientNodes) return;
    const ctx = this.ctx;
    if (ctx) {
      const { source, gain } = this.ambientNodes;
      try {
        gain.gain.cancelScheduledValues(ctx.currentTime);
        gain.gain.setValueAtTime(gain.gain.value, ctx.currentTime);
        gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.5);
        source.stop(ctx.currentTime + 0.6);
      } catch {
        source.stop();
      }
    }
    this.ambientNodes = null;
  }

  isAmbientActive(): boolean {
    return this.ambientActive;
  }
}

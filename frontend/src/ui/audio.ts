export class AudioController {
  private ctx: AudioContext | null = null;
  muted = false;

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

  toggleMute(): boolean {
    this.muted = !this.muted;
    if (this.muted && this.ctx) {
      this.ctx.suspend().catch(() => {});
    }
    return this.muted;
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

  victory(): void {
    this.tone(523.25, 0.25, 'sine', 0.18);
    this.tone(659.25, 0.25, 'sine', 0.18);
    this.tone(783.99, 0.4, 'sine', 0.18);
  }

  defeat(): void {
    this.tone(392.0, 0.35, 'sine', 0.18, 196.0);
    this.tone(196.0, 0.5, 'sine', 0.18);
  }

  trapTrigger(): void {
    this.playNoise(0.25, 600, 0.25);
    this.tone(150, 0.2, 'sawtooth', 0.12);
  }
}

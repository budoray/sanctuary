import { describe, it, expect } from 'vitest';
import { AudioController } from './audio';

describe('AudioController', () => {
  it('starts unmuted and toggles mute state', () => {
    const audio = new AudioController();
    expect(audio.muted).toBe(false);
    expect(audio.toggleMute()).toBe(true);
    expect(audio.muted).toBe(true);
    expect(audio.toggleMute()).toBe(false);
    expect(audio.muted).toBe(false);
  });

  it('does not throw when playing sounds without an audio context', () => {
    const audio = new AudioController();
    expect(() => audio.swordHit()).not.toThrow();
    expect(() => audio.rangedShot()).not.toThrow();
    expect(() => audio.footstep()).not.toThrow();
    expect(() => audio.victory()).not.toThrow();
    expect(() => audio.defeat()).not.toThrow();
    expect(() => audio.trapTrigger()).not.toThrow();
  });
});

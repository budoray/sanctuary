import { describe, it, expect, vi } from 'vitest';
import { AudioController, MusicLibrary } from './audio';

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
    expect(() => audio.exploration()).not.toThrow();
    expect(() => audio.combatSting()).not.toThrow();
    expect(() => audio.playAmbient('dungeon')).not.toThrow();
    expect(() => audio.stopAmbient()).not.toThrow();
  });

  it('clamps and returns music volume', () => {
    const audio = new AudioController();
    audio.setMusicVolume(0.8);
    expect(audio.getMusicVolume()).toBe(0.8);
    audio.setMusicVolume(2);
    expect(audio.getMusicVolume()).toBe(1);
    audio.setMusicVolume(-0.5);
    expect(audio.getMusicVolume()).toBe(0);
  });
});

describe('MusicLibrary', () => {
  it('defaults to base volume and clamps input', () => {
    const lib = new MusicLibrary();
    expect(lib.getVolume()).toBe(0.35);
    lib.setVolume(0.9);
    expect(lib.getVolume()).toBe(0.9);
    lib.setVolume(-1);
    expect(lib.getVolume()).toBe(0);
    lib.setVolume(2);
    expect(lib.getVolume()).toBe(1);
  });

  it('calls the fallback when a track cannot load', async () => {
    const lib = new MusicLibrary();
    const fallback = vi.fn();
    lib.setFallback(fallback);
    // Point to a non-existent path so load fails.
    const result = await lib.playTrack('exploration', true);
    expect(result).toBe(false);
    expect(fallback).toHaveBeenCalledWith('exploration', true);
  });

  it('stops the current track without throwing', () => {
    const lib = new MusicLibrary();
    expect(() => lib.stopTrack()).not.toThrow();
  });
});

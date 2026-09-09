/** Web Audio API sound manager for Sanctuary.
 *
 * Generates simple synthesized effects so no external assets are required.
 * Sounds are grouped into categories and can be muted per category or globally.
 */

(function () {
  "use strict";

  const STORAGE_KEY = "sanctuary_audio_settings";

  const DEFAULT_SETTINGS = {
    master: 0.6,
    sfx: 1.0,
    ui: 0.8,
    muted: false,
  };

  let settings = loadSettings();
  let ctx = null;

  function loadSettings() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? { ...DEFAULT_SETTINGS, ...JSON.parse(raw) } : { ...DEFAULT_SETTINGS };
    } catch (e) {
      return { ...DEFAULT_SETTINGS };
    }
  }

  function saveSettings() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    } catch (e) {
      // ignore
    }
  }

  function ensureContext() {
    if (!ctx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (Ctx) {
        try {
          ctx = new Ctx();
        } catch (e) {
          // Audio may be unavailable in headless or restricted contexts.
          return null;
        }
      }
    }
    if (ctx && ctx.state === "suspended") {
      ctx.resume().catch(() => {});
    }
    return ctx;
  }

  function now() {
    return ctx ? ctx.currentTime : 0;
  }

  function envelope(gainNode, attack, decay, sustain, release, peak = 1) {
    const t = now();
    gainNode.gain.setValueAtTime(0, t);
    gainNode.gain.linearRampToValueAtTime(peak, t + attack);
    gainNode.gain.exponentialRampToValueAtTime(Math.max(sustain, 0.001), t + attack + decay);
    gainNode.gain.setValueAtTime(Math.max(sustain, 0.001), t + attack + decay + 0.05);
    gainNode.gain.exponentialRampToValueAtTime(0.001, t + attack + decay + 0.05 + release);
  }

  function tone(freq, duration, type = "sine", peak = 0.3) {
    if (!ensureContext()) return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, now());
    envelope(gain, 0.005, 0.05, 0, duration, peak);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now());
    osc.stop(now() + duration + 0.1);
  }

  function noise(duration, peak = 0.2) {
    if (!ensureContext()) return;
    const bufferSize = Math.max(1, Math.ceil(ctx.sampleRate * duration));
    const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
      data[i] = Math.random() * 2 - 1;
    }
    const src = ctx.createBufferSource();
    const gain = ctx.createGain();
    const filter = ctx.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = 1200;
    src.buffer = buffer;
    envelope(gain, 0.005, 0.03, 0, duration, peak);
    src.connect(filter);
    filter.connect(gain);
    gain.connect(ctx.destination);
    src.start(now());
  }

  function swoop(fromFreq, toFreq, duration, type = "sawtooth", peak = 0.2) {
    if (!ensureContext()) return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(fromFreq, now());
    osc.frequency.exponentialRampToValueAtTime(Math.max(toFreq, 20), now() + duration);
    envelope(gain, 0.01, 0.1, 0, duration, peak);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now());
    osc.stop(now() + duration + 0.1);
  }

  function play(name) {
    if (settings.muted) return;
    ensureContext();
    if (!ctx) return;

    const master = settings.master;

    switch (name) {
      case "ui_click":
        tone(800, 0.04, "sine", 0.1 * master * settings.ui);
        break;
      case "ui_open":
        tone(600, 0.06, "sine", 0.12 * master * settings.ui);
        setTimeout(() => tone(900, 0.06, "sine", 0.1 * master * settings.ui), 40);
        break;
      case "step":
        noise(0.04, 0.05 * master * settings.sfx);
        break;
      case "door_open":
        swoop(300, 80, 0.25, "sawtooth", 0.2 * master * settings.sfx);
        break;
      case "chest_open":
        tone(400, 0.1, "square", 0.08 * master * settings.sfx);
        setTimeout(() => tone(700, 0.15, "square", 0.06 * master * settings.sfx), 80);
        break;
      case "attack_hit":
        noise(0.08, 0.25 * master * settings.sfx);
        swoop(600, 100, 0.1, "sawtooth", 0.15 * master * settings.sfx);
        break;
      case "attack_miss":
        swoop(400, 200, 0.12, "sawtooth", 0.08 * master * settings.sfx);
        break;
      case "ranged_shot":
        swoop(900, 300, 0.15, "sawtooth", 0.12 * master * settings.sfx);
        break;
      case "spell_cast":
        tone(440, 0.1, "sine", 0.1 * master * settings.sfx);
        setTimeout(() => tone(660, 0.2, "sine", 0.12 * master * settings.sfx), 80);
        setTimeout(() => tone(880, 0.35, "sine", 0.1 * master * settings.sfx), 180);
        break;
      case "heal":
        tone(550, 0.15, "sine", 0.12 * master * settings.sfx);
        setTimeout(() => tone(770, 0.25, "sine", 0.1 * master * settings.sfx), 80);
        break;
      case "monster_death":
        swoop(200, 50, 0.35, "sawtooth", 0.2 * master * settings.sfx);
        break;
      case "player_hit":
        noise(0.12, 0.25 * master * settings.sfx);
        tone(150, 0.15, "sawtooth", 0.2 * master * settings.sfx);
        break;
      case "victory":
        [523, 659, 784, 1047].forEach((f, i) => {
          setTimeout(() => tone(f, 0.25, "sine", 0.12 * master * settings.sfx), i * 120);
        });
        break;
      case "defeat":
        [300, 250, 200, 150].forEach((f, i) => {
          setTimeout(() => tone(f, 0.35, "sawtooth", 0.15 * master * settings.sfx), i * 180);
        });
        break;
      case "rest":
        tone(330, 0.25, "sine", 0.08 * master * settings.sfx);
        break;
      case "error":
        tone(150, 0.15, "sawtooth", 0.12 * master * settings.ui);
        break;
      default:
        break;
    }
  }

  function setMuted(value) {
    settings.muted = !!value;
    saveSettings();
    updateMuteButton();
  }

  function toggleMuted() {
    setMuted(!settings.muted);
  }

  function isMuted() {
    return settings.muted;
  }

  function updateMuteButton() {
    const btn = document.getElementById("audio-mute-btn");
    if (btn) {
      btn.textContent = settings.muted ? "🔇 Sound Off" : "🔊 Sound On";
      btn.classList.toggle("muted", settings.muted);
    }
  }

  function initMuteButton() {
    const topbar = document.querySelector(".topbar > div:last-child");
    if (!topbar || document.getElementById("audio-mute-btn")) return;
    const btn = document.createElement("button");
    btn.id = "audio-mute-btn";
    btn.className = "btn btn-secondary";
    btn.style.cssText = "padding:0.4rem 0.7rem;font-size:0.75rem;";
    btn.addEventListener("click", () => {
      toggleMuted();
      play("ui_click");
    });
    topbar.insertBefore(btn, topbar.firstChild);
    updateMuteButton();
  }

  window.SanctuaryAudio = {
    play,
    toggleMuted,
    setMuted,
    isMuted,
    initMuteButton,
  };

  function initUiClicks() {
    document.body.addEventListener("click", (e) => {
      const btn = e.target.closest(".btn");
      if (btn && btn.id !== "audio-mute-btn") {
        play("ui_click");
      }
    }, { passive: true });
  }

  function init() {
    initMuteButton();
    initUiClicks();
  }

  document.addEventListener("DOMContentLoaded", init);
})();

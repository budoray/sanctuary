/** Inline SVG icons for Sanctuary character sheets and UI. */

const ICONS = {
  // Ancestries
  human: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M6 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2"/></svg>`,
  dwarf: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 8h12l-2 10H8L6 8z"/><path d="M8 8l2-3h4l2 3"/><path d="M9 18v-3h6v3"/><path d="M10 12h4"/></svg>`,
  elf: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="9" r="3"/><path d="M7 20c0-3 2-5 5-5s5 2 5 5"/><path d="M5 10l2-1 1 2"/><path d="M19 10l-2-1-1 2"/></svg>`,
  gnome: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 10h10l-1-4H8l-1 4z"/><circle cx="12" cy="15" r="4"/><path d="M10 11h4"/></svg>`,
  half_elf: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="9" r="3"/><path d="M8 20c0-3 2-4 4-4s4 1 4 4"/><path d="M17 11l2-1"/></svg>`,
  halfling: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 9h8l-2-3h-4l-2 3z"/><circle cx="12" cy="15" r="4"/><path d="M9 12h6"/></svg>`,
  half_orc: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="9" r="3"/><path d="M8 20c0-3 2-4 4-4s4 1 4 4"/><path d="M9 9l-2-1"/><path d="M15 9l2-1"/><path d="M10 12h4"/></svg>`,

  // Classes
  fighter: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 20L20 4"/><path d="M6 4h4v4H6z"/><path d="M14 16h4v4h-4z"/></svg>`,
  cleric: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 4v16"/><path d="M8 8h8"/><path d="M10 20h4"/></svg>`,
  druid: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 4C7 8 7 14 12 20c5-6 5-12 0-16z"/><path d="M12 8v8"/></svg>`,
  magic_user: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 4l-2 14h4L12 4z"/><circle cx="12" cy="19" r="2"/><path d="M8 12h8"/></svg>`,
  illusionist: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 4l8 8-8 8-8-8z"/><circle cx="12" cy="12" r="2"/></svg>`,
  thief: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 4l8 16"/><path d="M16 4l-8 16"/><circle cx="12" cy="12" r="3"/></svg>`,
  assassin: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12"/><path d="M18 6L6 18"/><path d="M12 4v16"/></svg>`,
  monk: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 14c0-3 2-5 4-5s4 2 4 5"/><path d="M8 20h8"/><path d="M12 9V4"/></svg>`,
  paladin: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 4v12"/><path d="M8 8h8"/><circle cx="12" cy="18" r="3"/></svg>`,
  ranger: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 18L20 6"/><path d="M20 6v6"/><path d="M20 6h-6"/></svg>`,

  // Equipment categories
  armour: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 4h12v5a7 7 0 0 1-14 0V4z"/><path d="M12 4v12"/></svg>`,
  shields: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
  weapons: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 20L20 4"/><path d="M6 4h4v4H6z"/><path d="M14 16h4v4h-4z"/></svg>`,
  gear: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 7h12v10H6z"/><path d="M9 7v-2h6v2"/><path d="M9 17v2h6v-2"/></svg>`,

  // Stats
  heart: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>`,
  shield: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/></svg>`,
  crosshair: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="8"/><path d="M12 4v16"/><path d="M4 12h16"/></svg>`,
  boot: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6h6l2 8H6z"/><path d="M14 14h4l2 3v3H6v-3"/></svg>`,
  coin: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="8"/><path d="M12 8v8"/><path d="M9 10h6"/></svg>`,
  scroll: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 4h12v16H6z"/><path d="M9 8h6"/><path d="M9 12h6"/><path d="M9 16h4"/></svg>`,
};

function icon(name, size = 20) {
  const svg = ICONS[name] || ICONS.gear;
  return `<span class="icon" style="width:${size}px;height:${size}px;">${svg}</span>`;
}

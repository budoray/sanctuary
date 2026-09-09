/** Bestiary: track monsters encountered and slain across a campaign. */

const BESTIARY_KEY = "sanctuary_bestiary_v1";

let bestiary = loadBestiary();

function loadBestiary() {
  try {
    const raw = localStorage.getItem(BESTIARY_KEY);
    const data = raw ? JSON.parse(raw) : {};
    return {
      seen: new Set(data.seen || []),
      killed: new Map(Object.entries(data.killed || {})),
    };
  } catch (e) {
    console.warn("Failed to load bestiary:", e);
    return { seen: new Set(), killed: new Map() };
  }
}

function saveBestiary() {
  try {
    const data = {
      seen: Array.from(bestiary.seen),
      killed: Object.fromEntries(bestiary.killed),
    };
    localStorage.setItem(BESTIARY_KEY, JSON.stringify(data));
  } catch (e) {
    console.warn("Failed to save bestiary:", e);
  }
}

function recordMonsterSeen(name) {
  if (!name) return;
  const key = name.toLowerCase();
  if (!bestiary.seen.has(key)) {
    bestiary.seen.add(key);
    saveBestiary();
  }
}

function recordMonsterKilled(name) {
  if (!name) return;
  const key = name.toLowerCase();
  recordMonsterSeen(name);
  const count = bestiary.killed.get(key) || 0;
  bestiary.killed.set(key, count + 1);
  saveBestiary();
}

function getBestiaryEntries() {
  const allNames = new Set([...bestiary.seen, ...bestiary.killed.keys()]);
  return Array.from(allNames).map(key => ({
    name: key,
    seen: bestiary.seen.has(key),
    killed: bestiary.killed.get(key) || 0,
  })).sort((a, b) => a.name.localeCompare(b.name));
}

function getBestiaryStats() {
  return {
    uniqueSeen: bestiary.seen.size,
    uniqueKilled: bestiary.killed.size,
    totalKilled: Array.from(bestiary.killed.values()).reduce((a, b) => a + b, 0),
  };
}

function resetBestiary() {
  bestiary = { seen: new Set(), killed: new Map() };
  saveBestiary();
}

function openBestiary() {
  const modal = document.getElementById("bestiary-modal");
  const list = document.getElementById("bestiary-list");
  const stats = document.getElementById("bestiary-stats");
  if (!modal || !list) return;

  const entries = getBestiaryEntries();
  const s = getBestiaryStats();

  if (stats) {
    stats.textContent = `${s.uniqueSeen} seen · ${s.totalKilled} slain`;
  }

  if (!entries.length) {
    list.innerHTML = `<p style="color:var(--ink-2)">No creatures catalogued yet. Venture into the dungeons to fill these pages.</p>`;
  } else {
    list.innerHTML = entries.map(e => `
      <div class="bestiary-entry">
        <div class="bestiary-name">${escapeHtml(titleCase(e.name))}</div>
        <div class="bestiary-meta">${e.killed > 0 ? `Slain: ${e.killed}` : "Seen"}</div>
      </div>
    `).join("");
  }

  modal.classList.remove("hidden");
}

function closeBestiary() {
  document.getElementById("bestiary-modal")?.classList.add("hidden");
}

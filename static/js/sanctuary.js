/** Sanctuary 0.1.x client — character creation and square-grid test ground. */

const TILE_SIZE = 32;
const GRID_RADIUS = 8;

let currentCharacter = null;
let equipmentCatalog = [];
let app = null;
let tokenGraphics = null;
let gridGraphics = null;
let groundContainer = null;
let waitingForRound = null;

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Accept": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

async function init() {
  const authEl = document.getElementById("auth-check");
  try {
    const me = await api("/api/me");
    if (!me.logged_in) {
      authEl.innerHTML = `<p>Please <a href="https://tenshinarts.com/login?next=${encodeURIComponent(location.href)}">log in</a> to play.</p>`;
      return;
    }
    authEl.classList.add("hidden");
    document.getElementById("create-panel").classList.remove("hidden");
    document.getElementById("roster-panel").classList.remove("hidden");
    await loadOptions();
    await loadEquipment();
    await loadCharacters();
    initCreateForm();
    initAddItemForm();
    initDicePanel();
    initControls();
  } catch (err) {
    authEl.innerHTML = `<p class="error">${err.message}</p>`;
  }
}

async function loadOptions() {
  const data = await api("/api/ruleset/osric/options");
  populateSelect("ancestry-select", data.ancestries);
  populateSelect("class-select", data.classes);
  populateSelect("alignment-select", data.alignments.map(a => ({ id: a, name: a })));
}

async function loadEquipment() {
  const data = await api("/api/ruleset/osric/equipment");
  equipmentCatalog = data.equipment;
  populateSelect("item-select", equipmentCatalog);
}

function populateSelect(id, items) {
  const sel = document.getElementById(id);
  sel.innerHTML = "";
  for (const item of items) {
    const opt = document.createElement("option");
    opt.value = item.id;
    opt.textContent = item.name;
    sel.appendChild(opt);
  }
}

function initCreateForm() {
  const form = document.getElementById("create-form");
  const result = document.getElementById("create-result");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    result.textContent = "Rolling…";
    const formData = new FormData(form);
    try {
      const char = await api("/api/characters", {
        method: "POST",
        body: formData,
      });
      result.innerHTML = renderCharacter(char, true);
      await loadCharacters();
    } catch (err) {
      result.textContent = err.message;
    }
  });
}

function mod(v) {
  const n = Number(v);
  if (!n) return "+0";
  return n > 0 ? `+${n}` : `${n}`;
}

function abilityLabel(key) {
  return { strength: "STR", intelligence: "INT", wisdom: "WIS", dexterity: "DEX", constitution: "CON", charisma: "CHA" }[key] || key.slice(0, 3).toUpperCase();
}

function abilityColor(key) {
  return { strength: "str", intelligence: "int", wisdom: "wis", dexterity: "dex", constitution: "con", charisma: "cha" }[key] || "neutral";
}

function renderPortrait(name) {
  const initials = name.split(" ").map(s => s[0]).join("").slice(0, 2).toUpperCase();
  return `<div class="portrait"><span>${initials}</span></div>`;
}

function renderAbilityCards(abilities, mods) {
  return Object.entries(abilities).map(([k, v]) => {
    const bonus = mods?.[k];
    let note = "";
    if (k === "strength") note = `hit ${mod(bonus?.to_hit)} · dmg ${mod(bonus?.damage)}`;
    if (k === "dexterity") note = `missile ${mod(bonus?.missile_to_hit)} · AC ${mod(bonus?.ac_ascending)}`;
    if (k === "constitution") note = `HP ${mod(bonus?.hp_modifier)}`;
    if (k === "wisdom") note = `save ${mod(bonus?.mental_save)}`;
    if (k === "intelligence") note = `langs ${bonus?.bonus_languages ?? 0}`;
    if (k === "charisma") note = `react ${mod(bonus?.reaction)}`;
    return `
      <div class="ability-card ability-${abilityColor(k)}">
        <div class="ability-score">${v}</div>
        <div class="ability-name">${abilityLabel(k)}</div>
        <div class="ability-note">${note}</div>
      </div>
    `;
  }).join("");
}

function renderStatCards(sheet) {
  const inv = sheet.inventory || { items: [], weight: 0 };
  return `
    <div class="stat-card"><div class="stat-icon">${icon("heart", 18)}</div><div class="stat-value">${sheet.hit_points}</div><div class="stat-label">HP</div></div>
    <div class="stat-card"><div class="stat-icon">${icon("shield", 18)}</div><div class="stat-value">${sheet.armour_class ?? "—"}</div><div class="stat-label">AC [${sheet.armour_class_descending ?? "—"}]</div></div>
    <div class="stat-card"><div class="stat-icon">${icon("crosshair", 18)}</div><div class="stat-value">${sheet.thac0 ?? "—"}</div><div class="stat-label">THAC0</div></div>
    <div class="stat-card"><div class="stat-icon">${icon("boot", 18)}</div><div class="stat-value">${sheet.movement ?? sheet.base_movement ?? "—"}</div><div class="stat-label">MV ft</div></div>
    <div class="stat-card"><div class="stat-icon">${icon("coin", 18)}</div><div class="stat-value">${sheet.remaining_gold ?? sheet.starting_gold ?? "—"}</div><div class="stat-label">GP</div></div>
    <div class="stat-card"><div class="stat-icon">${icon("gear", 18)}</div><div class="stat-value">${inv.weight ?? 0}</div><div class="stat-label">WT lb</div></div>
  `;
}

function renderSaveCards(saves) {
  const labels = [
    ["aimed_magic_items", "Aim", "Rods, staves, wands"],
    ["breath_weapons", "Breath", "Breath weapons"],
    ["death_paralysis_poison", "Death", "Death/paralysis/poison"],
    ["petrification_polymorph", "Petrify", "Petrification/polymorph"],
    ["spells", "Spells", "Spells"],
  ];
  return labels.map(([key, short, title]) => `
    <div class="save-card" title="${title}">
      <div class="save-value">${saves[key] ?? "—"}</div>
      <div class="save-label">${short}</div>
    </div>
  `).join("");
}

function renderEquipped(inv) {
  const equipped = (inv?.items || []).filter(i => i.equipped);
  if (!equipped.length) return "";
  return `
    <div class="equipped-row">
      <strong>Equipped:</strong>
      ${equipped.map(i => {
        const item = equipmentCatalog.find(c => c.id === i.item_id);
        return `<span class="equipped-chip">${icon(item?.category || "gear", 14)} ${item?.name || i.item_id}</span>`;
      }).join("")}
    </div>
  `;
}

function renderSheet(char) {
  const sheet = char.sheet || {};
  const saves = sheet.saving_throws || {};
  const mods = sheet.ability_modifiers || {};
  const inv = sheet.inventory || { items: [], weight: 0 };
  return `
    <div class="sheet-card">
      <div class="sheet-header">
        ${renderPortrait(char.name)}
        <div class="sheet-title-block">
          <div class="sheet-name">${char.name}</div>
          <div class="sheet-subtitle">
            ${icon(char.ancestry, 16)} ${char.ancestry.replace(/_/g, " ")}
            ${icon(char.class, 16)} ${char.class.replace(/_/g, " ")}
            <span class="alignment-badge">${char.alignment}</span>
          </div>
        </div>
        <div class="sheet-level">Lvl ${sheet.level ?? 1}</div>
      </div>
      <div class="ability-grid">
        ${renderAbilityCards(char.abilities, mods)}
      </div>
      <div class="stat-row">
        ${renderStatCards(sheet)}
      </div>
      <div class="save-row">
        ${renderSaveCards(saves)}
      </div>
      ${renderEquipped(inv)}
    </div>
  `;
}

function renderCharacter(char, detailed = false) {
  const sheet = char.sheet || {};
  const inv = sheet.inventory || { items: [], weight: 0 };

  if (!detailed) {
    return `
      <div class="character-card">
        ${renderPortrait(char.name)}
        <div class="character-info">
          <div class="character-title">
            <strong>${char.name}</strong>
            <span class="alignment-badge">${char.alignment}</span>
          </div>
          <div class="character-meta">
            ${icon(char.ancestry, 14)} ${char.ancestry.replace(/_/g, " ")}
            ${icon(char.class, 14)} ${char.class.replace(/_/g, " ")}
          </div>
          <div class="character-stats">
            <span>HP ${char.hit_points}</span>
            <span>AC ${sheet.armour_class ?? "—"}</span>
            <span>THAC0 ${sheet.thac0 ?? "—"}</span>
            <span>MV ${sheet.movement ?? sheet.base_movement ?? "—"}</span>
            <span>WT ${inv.weight ?? 0} lb</span>
          </div>
        </div>
        <button class="enter-btn" data-id="${char.id}">Enter</button>
      </div>
    `;
  }
  return `<div class="create-result">${renderSheet(char)}</div>`;
}

async function loadCharacters() {
  const list = document.getElementById("character-list");
  const chars = await api("/api/characters");
  list.innerHTML = "";
  if (!chars.length) {
    list.innerHTML = "<li>No characters yet.</li>";
    return;
  }
  for (const char of chars) {
    const li = document.createElement("li");
    li.innerHTML = renderCharacter(char);
    list.appendChild(li);
  }
  for (const btn of list.querySelectorAll(".enter-btn")) {
    btn.addEventListener("click", () => enterTestGround(parseInt(btn.dataset.id, 10)));
  }
}

let diceLog = [];

async function enterTestGround(characterId) {
  currentCharacter = await api(`/api/characters/${characterId}`);
  document.getElementById("ground-panel").classList.remove("hidden");
  document.getElementById("inventory-panel").classList.remove("hidden");
  document.getElementById("dice-panel").classList.remove("hidden");
  setControlsEnabled(true);
  renderInventory();
  renderDiceLog();
  await renderGround();
}

function initDicePanel() {
  const form = document.getElementById("dice-form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const expression = form.elements.expression.value.trim();
    await rollDice(expression);
  });
  for (const btn of document.querySelectorAll(".quick-dice button")) {
    btn.addEventListener("click", async () => {
      await rollDice(btn.dataset.expr);
    });
  }
}

async function rollDice(expression) {
  try {
    const result = await api("/api/roll", {
      method: "POST",
      body: new URLSearchParams({ expression }),
    });
    diceLog.unshift(result);
    if (diceLog.length > 20) diceLog.pop();
    renderDiceLog();
  } catch (err) {
    alert(err.message);
  }
}

function renderDiceLog() {
  const list = document.getElementById("dice-log");
  if (!list) return;
  if (!diceLog.length) {
    list.innerHTML = "<li class='dice-empty'>No rolls yet.</li>";
    return;
  }
  list.innerHTML = diceLog.map((r) => {
    const details = r.parts.map((p) => {
      if (p.type === "dice") {
        const sign = p.sign < 0 ? "−" : "+";
        return `${sign}${p.count}d${p.sides}(${p.results.join(",")})`;
      }
      const sign = p.sign < 0 ? "−" : "+";
      return `${sign}${p.value}`;
    }).join(" ");
    return `<li><strong>${r.total}</strong> ← ${r.expression} <span class="roll-detail">${details}</span></li>`;
  }).join("");
}

function tileCenter(x, y, size) {
  return {
    x: x * size,
    y: y * size,
  };
}

async function renderGround() {
  const container = document.getElementById("ground-canvas");
  container.innerHTML = "";
  if (app) {
    app.destroy(true, { children: true });
  }
  app = new PIXI.Application({
    width: 640,
    height: 480,
    background: "#1a1a1a",
  });
  container.appendChild(app.view);

  groundContainer = new PIXI.Container();
  groundContainer.position.set(320, 240);
  app.stage.addChild(groundContainer);

  gridGraphics = new PIXI.Graphics();
  groundContainer.addChild(gridGraphics);

  const half = Math.floor(GRID_RADIUS / 2);
  for (let x = -half; x <= half; x++) {
    for (let y = -half; y <= half; y++) {
      drawTile(x, y, 0x444444);
    }
  }

  tokenGraphics = new PIXI.Graphics();
  groundContainer.addChild(tokenGraphics);
  await refreshTokens();
}

function drawTile(x, y, color) {
  const half = TILE_SIZE / 2;
  const cx = x * TILE_SIZE;
  const cy = y * TILE_SIZE;
  gridGraphics.lineStyle(1, color, 1);
  gridGraphics.beginFill(0x252525);
  gridGraphics.drawRect(cx - half, cy - half, TILE_SIZE, TILE_SIZE);
  gridGraphics.endFill();
}

function drawToken(x, y, color, label) {
  const half = TILE_SIZE / 2;
  const cx = x * TILE_SIZE;
  const cy = y * TILE_SIZE;
  tokenGraphics.beginFill(color);
  tokenGraphics.drawCircle(cx, cy, half * 0.6);
  tokenGraphics.endFill();

  const text = new PIXI.Text(label, {
    fontFamily: "Arial",
    fontSize: 12,
    fill: 0xffffff,
  });
  text.anchor.set(0.5);
  text.position.set(cx, cy);
  tokenGraphics.addChild(text);
}

function renderInventory() {
  const summary = document.getElementById("inventory-summary");
  const list = document.getElementById("inventory-list");
  if (!currentCharacter) {
    summary.innerHTML = "";
    list.innerHTML = "";
    return;
  }
  const sheet = currentCharacter.sheet || {};
  const inv = sheet.inventory || { items: [], weight: 0 };
  summary.innerHTML = `
    <div class="sheet-row">
      <span>AC ${sheet.armour_class ?? "—"} [${sheet.armour_class_descending ?? "—"}]</span>
      <span>MV ${sheet.movement ?? sheet.base_movement ?? "—"} ft</span>
      <span>WT ${inv.weight ?? 0} lb</span>
      <span>GP ${sheet.remaining_gold ?? sheet.starting_gold ?? "—"}</span>
    </div>
  `;

  list.innerHTML = "";
  if (!inv.items.length) {
    list.innerHTML = "<li>No equipment.</li>";
    return;
  }
  for (const entry of inv.items) {
    const item = equipmentCatalog.find(i => i.id === entry.item_id);
    const name = item ? item.name : entry.item_id;
    const li = document.createElement("li");
    li.className = "inventory-row";
    li.innerHTML = `
      <span>${name}${entry.quantity > 1 ? ` ×${entry.quantity}` : ""}${entry.equipped ? " <strong>(equipped)</strong>" : ""}</span>
      <span class="inventory-actions">
        ${entry.equipped
          ? `<button data-item="${entry.item_id}" class="unequip-btn">Unequip</button>`
          : `<button data-item="${entry.item_id}" class="equip-btn">Equip</button>`}
        <button data-item="${entry.item_id}" class="remove-btn">Remove</button>
      </span>
    `;
    list.appendChild(li);
  }
  for (const btn of list.querySelectorAll(".equip-btn")) {
    btn.addEventListener("click", async () => {
      await equipItem(btn.dataset.item);
    });
  }
  for (const btn of list.querySelectorAll(".unequip-btn")) {
    btn.addEventListener("click", async () => {
      await unequipItem(btn.dataset.item);
    });
  }
  for (const btn of list.querySelectorAll(".remove-btn")) {
    btn.addEventListener("click", async () => {
      await removeItem(btn.dataset.item);
    });
  }
}

async function equipItem(itemId) {
  if (!currentCharacter) return;
  currentCharacter = await api(`/api/characters/${currentCharacter.id}/inventory/${itemId}/equip`, {
    method: "POST",
  });
  await loadCharacters();
  renderInventory();
}

async function unequipItem(itemId) {
  if (!currentCharacter) return;
  currentCharacter = await api(`/api/characters/${currentCharacter.id}/inventory/${itemId}/unequip`, {
    method: "POST",
  });
  await loadCharacters();
  renderInventory();
}

async function removeItem(itemId) {
  if (!currentCharacter) return;
  currentCharacter = await api(`/api/characters/${currentCharacter.id}/inventory/${itemId}`, {
    method: "DELETE",
  });
  await loadCharacters();
  renderInventory();
}

function initAddItemForm() {
  const form = document.getElementById("add-item-form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!currentCharacter) {
      alert("Select a character first by entering the test ground.");
      return;
    }
    const formData = new FormData(form);
    try {
      currentCharacter = await api(`/api/characters/${currentCharacter.id}/inventory`, {
        method: "POST",
        body: formData,
      });
      await loadCharacters();
      renderInventory();
      form.reset();
    } catch (err) {
      alert(err.message);
    }
  });
}

async function refreshTokens() {
  if (!tokenGraphics) return;
  tokenGraphics.clear();
  while (tokenGraphics.children.length > 0) {
    tokenGraphics.removeChildAt(0);
  }
  const state = await api("/api/test-ground/state");
  for (const t of state.tokens) {
    const isMine = currentCharacter && t.character_id === currentCharacter.id;
    drawToken(t.x, t.y, isMine ? 0xc9a227 : 0x666666, t.name[0].toUpperCase());
  }
}

function setControlsEnabled(enabled) {
  for (const btn of document.querySelectorAll(".controls button")) {
    btn.disabled = !enabled;
  }
}

async function submitMove(direction) {
  if (!currentCharacter || waitingForRound !== null) return;
  setControlsEnabled(false);
  const status = document.getElementById("ground-status");
  try {
    const res = await api(`/api/test-ground/${currentCharacter.id}/move`, {
      method: "POST",
      body: new URLSearchParams({ direction }),
    });
    waitingForRound = res.round;
    status.textContent =
      `Move submitted for round ${waitingForRound}. ` +
      `Waiting (${res.pending_count}/${res.expected_count})…`;
    await waitForRound(waitingForRound);
  } catch (err) {
    alert(err.message);
    setControlsEnabled(true);
  }
}

async function waitForRound(round) {
  const status = document.getElementById("ground-status");
  for (let i = 0; i < 240; i++) {
    await new Promise((resolve) => setTimeout(resolve, 500));
    const state = await api("/api/test-ground/state");
    if (state.round > round || state.pending_count === 0) {
      status.textContent =
        `Round ${state.round}: moving ${currentCharacter.name} (${currentCharacter.class.replace(/_/g, " ")}).`;
      await refreshTokens();
      setControlsEnabled(true);
      waitingForRound = null;
      return;
    }
    status.textContent =
      `Move submitted for round ${round}. ` +
      `Waiting (${state.pending_count}/${state.expected_count})…`;
  }
  // Safety release after two minutes.
  setControlsEnabled(true);
  waitingForRound = null;
}

function initControls() {
  for (const btn of document.querySelectorAll(".controls button")) {
    btn.addEventListener("click", async () => {
      const dir = parseInt(btn.dataset.dir, 10);
      await submitMove(dir);
    });
  }
}

init();

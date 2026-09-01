/** Main game orchestration: character creation, UI, and log. */

const ABILITY_ORDER = ["strength", "intelligence", "wisdom", "dexterity", "constitution", "charisma"];

let playerCharacter = null;
let party = []; // Hot-seat party array
let activePartyIndex = 0;
const MAX_PARTY_SIZE = 6;
let osricOptions = null;
let osricRules = null;
let osricMonsters = null;
let dungeonLevel = 1;
let abilityDraft = null; // { pool: [...], assigned: {str: index, ...}, mode: null|"arrange" }
let rollMethod = "3d6_in_order";

const SAVE_KEY = "sanctuary_run_v1";
const UNLOCK_KEY = "sanctuary_unlocked_v1";

function getUnlockedModules() {
  try {
    const raw = localStorage.getItem(UNLOCK_KEY);
    const set = new Set(raw ? JSON.parse(raw) : []);
    set.add("crooked_tower"); // starter module always available
    return set;
  } catch (e) {
    return new Set(["crooked_tower"]);
  }
}

function unlockModule(id) {
  if (!id) return;
  const unlocked = getUnlockedModules();
  if (unlocked.has(id)) return;
  unlocked.add(id);
  try {
    localStorage.setItem(UNLOCK_KEY, JSON.stringify(Array.from(unlocked)));
    log(`<span class="hit">New dungeon unlocked: ${DUNGEON_MODULES[id]?.name || id}</span>`, "hit");
  } catch (e) {
    console.warn("Failed to save unlocks:", e);
  }
}

function isModuleUnlocked(id) {
  return getUnlockedModules().has(id);
}

function setActiveCharacter(index) {
  if (index < 0 || index >= party.length) return;
  if (combatState && combatState.phase !== "player") {
    log("You cannot switch characters during the enemy turn.");
    return;
  }
  const threshold = osricRules?.combat?.unconscious_threshold ?? 0;
  if (party[index].sheet.hit_points <= threshold) {
    log(`${party[index].name} is unconscious and cannot act.`);
    return;
  }
  activePartyIndex = index;
  playerCharacter = party[index];
  renderCharacterPanel();
  if (combatState && combatState.phase === "player") {
    const acted = combatState.partyActed?.has(index);
    combatState.acted = !!acted;
    combatState.attacked = !!acted;
    combatState.movementRemaining = acted ? 0 : tilesPerRound(playerCharacter.sheet.movement);
    updateCombatUI();
    if (!acted) {
      highlightReachable(playerPos, combatState.movementRemaining);
      highlightRangedTargets();
    } else {
      clearHighlights();
    }
  }
}

function activeCharacter() {
  return playerCharacter || (party.length ? party[0] : null);
}

function partyConsciousMembers() {
  const threshold = osricRules?.combat?.unconscious_threshold ?? 0;
  return party.filter(c => c.sheet.hit_points > threshold);
}

function partyAliveMembers() {
  const threshold = osricRules?.combat?.death_threshold ?? -10;
  return party.filter(c => c.sheet.hit_points > threshold);
}

function firstConsciousPartyIndex() {
  const threshold = osricRules?.combat?.unconscious_threshold ?? 0;
  for (let i = 0; i < party.length; i++) {
    if (party[i].sheet.hit_points > threshold) return i;
  }
  return -1;
}

function ensureConsciousActive() {
  const idx = firstConsciousPartyIndex();
  if (idx >= 0) {
    activePartyIndex = idx;
    playerCharacter = party[idx];
    renderCharacterPanel();
    return true;
  }
  return false;
}

function hasSavedRun() {
  try {
    return !!localStorage.getItem(SAVE_KEY);
  } catch (e) {
    return false;
  }
}

function saveGame() {
  try {
    const data = {
      party,
      activePartyIndex,
      playerCharacter,
      dungeonLevel,
      dungeonModuleName,
      mapData,
      monsters,
      playerPos,
      chestsOpened: Array.from(chestsOpened),
      doorsOpened: Array.from(doorsOpened),
      trapsTriggered: Array.from(trapsTriggered),
      trapsDiscovered: Array.from(trapsDiscovered),
      explored: Array.from(explored),
      roomsVisited: Array.from(roomsVisited),
      currentModule,
      combatState: combatState ? {
        ...combatState,
        partyActed: Array.from(combatState.partyActed || []),
      } : null,
      savedAt: new Date().toISOString(),
    };
    localStorage.setItem(SAVE_KEY, JSON.stringify(data));
  } catch (e) {
    console.warn("Failed to save game:", e);
  }
}

function clearSave() {
  try {
    localStorage.removeItem(SAVE_KEY);
  } catch (e) {
    console.warn("Failed to clear save:", e);
  }
}

async function loadGame() {
  try {
    const raw = localStorage.getItem(SAVE_KEY);
    if (!raw) return false;
    const data = JSON.parse(raw);
    if (!data.playerCharacter && !data.party?.length) return false;

    party = data.party || (data.playerCharacter ? [data.playerCharacter] : []);
    activePartyIndex = data.activePartyIndex || 0;
    if (activePartyIndex >= party.length) activePartyIndex = 0;
    playerCharacter = activeCharacter();
    dungeonLevel = data.dungeonLevel || 1;
    dungeonModuleName = data.dungeonModuleName || "crooked_tower";
    mapData = data.mapData || [];
    monsters = data.monsters || [];
    playerPos = data.playerPos || { x: 1, y: 1 };
    chestsOpened = new Set(data.chestsOpened || []);
    doorsOpened = new Set(data.doorsOpened || []);
    trapsTriggered = new Set(data.trapsTriggered || []);
    trapsDiscovered = new Set(data.trapsDiscovered || []);
    explored = new Set(data.explored || []);
    roomsVisited = new Set(data.roomsVisited || []);
    currentModule = data.currentModule || null;
    if (data.combatState) {
      combatState = data.combatState;
      combatState.partyActed = new Set(combatState.partyActed || []);
    }

    // Rebuild transient state.
    document.getElementById("landing-screen").classList.add("hidden");
    document.getElementById("create-modal").classList.add("hidden");
    renderCharacterPanel();
    clearLog();
    updateLevelBadge();
    log(`<b>${playerCharacter.name}</b> and company return to ${currentModule?.name || "the dungeon"}.`, "hit");
    initDungeon();
    drawMap();
    drawTokens();
    renderFog();
    if (combatState) {
      updateCombatUI();
      highlightReachable(playerPos, combatState.movementRemaining);
      highlightRangedTargets();
    }
    return true;
  } catch (e) {
    console.error("Failed to load game:", e);
    clearSave();
    return false;
  }
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Accept": "application/json", "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

async function loadOptions() {
  [osricOptions, osricRules, osricMonsters] = await Promise.all([
    api("/api/osric/options"),
    api("/api/osric/rules"),
    api("/api/osric/monsters"),
  ]);
  populateSelect("char-ancestry", osricOptions.ancestries);
  populateSelect("char-class", osricOptions.classes);
  populateSelect("char-alignment", osricOptions.alignments.map(a => ({ id: a, name: a })));
  populateRollMethods();
  // Default to a combination that is always valid.
  document.getElementById("char-ancestry").value = "human";
  document.getElementById("char-class").value = "fighter";
  document.getElementById("char-alignment").value = "Lawful Good";
  rollMethod = document.getElementById("roll-method").value;
  filterCreationOptions();
}

function populateRollMethods() {
  const sel = document.getElementById("roll-method");
  sel.innerHTML = "";
  const defaultMethod = osricRules.core.default_roll_method || "3d6_in_order";
  const methods = osricRules.rolling?.methods || {};
  for (const [id, cfg] of Object.entries(methods)) {
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = cfg.name || id;
    sel.appendChild(opt);
  }
  sel.value = defaultMethod;
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

function getAncestry(id) {
  return osricOptions.ancestries.find(a => a.id === id);
}

function getClass(id) {
  return osricOptions.classes.find(c => c.id === id);
}

function getClassFeatures(classId) {
  return osricRules?.class_features?.starting_packages?.[classId] || null;
}

function getClassAbilities(classId) {
  return osricRules?.class_features?.abilities?.[classId] || [];
}

function getThiefSkills() {
  return osricRules?.class_features?.thief_skills || {};
}

function isClassAllowedForAncestry(ancestryId, classId) {
  const ancestry = getAncestry(ancestryId);
  return ancestry && ancestry.allowed_classes?.includes(classId);
}

function isAlignmentAllowedForClass(classId, alignment) {
  const klass = getClass(classId);
  return klass && klass.allowed_alignments?.includes(alignment);
}

function filterCreationOptions() {
  const ancestryId = document.getElementById("char-ancestry").value;
  const classId = document.getElementById("char-class").value;
  const alignmentId = document.getElementById("char-alignment").value;

  // Disable classes not allowed for this ancestry.
  const classSel = document.getElementById("char-class");
  let classStillValid = false;
  for (const opt of classSel.options) {
    const allowed = isClassAllowedForAncestry(ancestryId, opt.value);
    opt.disabled = !allowed;
    if (allowed && opt.value === classId) classStillValid = true;
  }
  if (!classStillValid) {
    const firstValid = Array.from(classSel.options).find(o => !o.disabled);
    if (firstValid) {
      classSel.value = firstValid.value;
      // Changing class may affect alignment; re-filter below.
    }
  }

  // Disable alignments not allowed for this class.
  const alignSel = document.getElementById("char-alignment");
  const newClassId = classSel.value;
  let alignStillValid = false;
  for (const opt of alignSel.options) {
    const allowed = isAlignmentAllowedForClass(newClassId, opt.value);
    opt.disabled = !allowed;
    if (allowed && opt.value === alignmentId) alignStillValid = true;
  }
  if (!alignStillValid) {
    const firstValid = Array.from(alignSel.options).find(o => !o.disabled);
    if (firstValid) alignSel.value = firstValid.value;
  }

  renderClassRequirements();
  clearCreationErrors();
}

function renderClassRequirements() {
  const classId = document.getElementById("char-class").value;
  const klass = getClass(classId);
  const info = document.getElementById("class-info");
  if (!klass || !info) return;
  const reqs = klass.ability_score_requirements || {};
  const reqItems = Object.entries(reqs).map(([ability, value]) =>
    `<li>${titleCase(ability)} ${value}+</li>`
  ).join("");
  const existing = info.querySelector(".requirements-list");
  if (existing) existing.remove();
  if (reqItems) {
    const ul = document.createElement("ul");
    ul.className = "requirements-list";
    ul.innerHTML = `<li style="list-style:none;margin-left:-1rem;color:var(--accent)">Requirements:</li>${reqItems}`;
    info.appendChild(ul);
  }
}

function showCreationError(message, actions = "") {
  const el = document.getElementById("creation-errors");
  if (el) el.innerHTML = `<span>${message}</span>${actions}`;
  else console.error("Creation error:", message);
}

function clearCreationErrors() {
  const el = document.getElementById("creation-errors");
  if (el) el.innerHTML = "";
}

function showMessageModal(title, body, actions = []) {
  const modal = document.getElementById("message-modal");
  const titleEl = document.getElementById("message-title");
  const bodyEl = document.getElementById("message-body");
  const actionsEl = document.getElementById("message-actions");
  if (!modal || !titleEl || !bodyEl || !actionsEl) return;
  titleEl.textContent = title;
  bodyEl.innerHTML = body;
  actionsEl.innerHTML = "";
  if (!actions.length) {
    const ok = document.createElement("button");
    ok.className = "btn btn-primary";
    ok.textContent = "OK";
    ok.addEventListener("click", () => modal.classList.add("hidden"));
    actionsEl.appendChild(ok);
  } else {
    for (const { label, primary, onClick } of actions) {
      const btn = document.createElement("button");
      btn.className = primary ? "btn btn-primary" : "btn btn-secondary";
      btn.textContent = label;
      btn.addEventListener("click", () => {
        modal.classList.add("hidden");
        if (onClick) onClick();
      });
      actionsEl.appendChild(btn);
    }
  }
  modal.classList.remove("hidden");
}

function confirmAction(title, body, onConfirm) {
  showMessageModal(title, body, [
    { label: "Cancel", primary: false },
    { label: "Confirm", primary: true, onClick: onConfirm },
  ]);
}

function abilityShort(name) {
  return { strength: "STR", intelligence: "INT", wisdom: "WIS", dexterity: "DEX", constitution: "CON", charisma: "CHA" }[name] || name.slice(0, 3).toUpperCase();
}

function abilityColor(name) {
  return { strength: "str", intelligence: "int", wisdom: "wis", dexterity: "dex", constitution: "con", charisma: "cha" }[name] || "neutral";
}

async function rollCharacter() {
  const name = document.getElementById("char-name").value || "Hero";
  const ancestry = document.getElementById("char-ancestry").value;
  const class_id = document.getElementById("char-class").value;
  const alignment = document.getElementById("char-alignment").value;
  rollMethod = document.getElementById("roll-method").value;

  abilityDraft = null;
  document.getElementById("ability-pool").classList.add("hidden");
  document.getElementById("auto-arrange-btn").classList.add("hidden");
  clearCreationErrors();

  if (rollMethod === "arrange_to_taste") {
    try {
      const cfg = osricRules.rolling.methods[rollMethod];
      const poolMethod = cfg?.pool_dice || cfg?.dice || "3d6";
      const data = await api(`/api/osric/roll-abilities?method=${poolMethod}`);
      abilityDraft = { pool: data.pool, assigned: {}, mode: "arrange" };
      renderAbilityPool();
      document.getElementById("ability-pool").classList.remove("hidden");
      document.getElementById("auto-arrange-btn").classList.remove("hidden");
      document.getElementById("rolled-abilities").innerHTML = "";
      document.getElementById("creation-summary").innerHTML = `<p style="color:var(--ink-2)">Assign all six scores to finish rolling.</p>`;
      clearCreationDetails();
      updateHeaderStats();
      renderShop();
      renderInventoryCreate();
    } catch (err) {
      showCreationError(err.message);
    }
    return;
  }

  try {
    const newCharacter = await api("/api/osric/character", {
      method: "POST",
      body: JSON.stringify({ name, ancestry, class_id, alignment, roll_method: rollMethod }),
    });
    party.push(newCharacter);
    activePartyIndex = party.length - 1;
    playerCharacter = newCharacter;
    showRolledCharacter();
    renderShop();
    renderInventoryCreate();
    renderPartyRosterCreation();
  } catch (err) {
    const actions = `
      <button class="btn btn-secondary" onclick="rollCharacter()" style="font-size:0.75rem;padding:0.3rem 0.6rem;">Re-roll</button>
      <button class="btn btn-secondary" onclick="document.getElementById('roll-method').value='arrange_to_taste';rollCharacter();" style="font-size:0.75rem;padding:0.3rem 0.6rem;">Use Arrange to Taste</button>
    `;
    showCreationError(err.message, actions);
  }
}

function safeSetText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function safeSetHtml(id, html) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = html;
}

function clearCreationDetails() {
  safeSetHtml("class-info", "");
  safeSetHtml("saving-throws-create", "");
  const bdRow = document.getElementById("breakdowns");
  if (bdRow) bdRow.classList.add("hidden");
  const acEl = document.getElementById("ac-breakdown");
  if (acEl) acEl.innerHTML = "";
  const hpEl = document.getElementById("hp-breakdown");
  if (hpEl) hpEl.innerHTML = "";
  safeSetText("creation-errors", "");
}

function updateHeaderStats() {
  const s = playerCharacter?.sheet;
  safeSetText("header-hp", s ? `${s.hit_points}/${s.max_hit_points}` : "—");
  safeSetText("header-ac", s ? s.armour_class : "—");
  safeSetText("header-thac0", s ? s.thac0 : "—");
  safeSetText("header-gold", playerCharacter ? `${Number(playerCharacter.remaining_gold).toFixed(1)} gp` : "0 gp");
}

function classIcon(classId) {
  const map = {
    cleric: "✝", druid: "🌿", fighter: "⚔", paladin: "🛡", ranger: "🏹",
    magic_user: "✦", thief: "🗡", assassin: "☠", monk: "👊", bard: "🎵",
  };
  return map[classId] || "★";
}

function renderPartyRosterCreation() {
  const bar = document.getElementById("party-roster-bar");
  if (!bar) return;
  const atMax = party.length >= MAX_PARTY_SIZE;
  const html = party.map((c, i) => {
    const s = c.sheet;
    const active = i === activePartyIndex;
    return `
      <div class="party-member-mini ${active ? 'active' : ''}" data-index="${i}">
        <div class="mini-portrait"><span>${classIcon(c.class)}</span></div>
        <div class="mini-info">
          <div class="mini-name">${c.name}</div>
          <div class="mini-meta">${titleCase(c.class)} · HP ${s.hit_points}/${s.max_hit_points}</div>
        </div>
      </div>
    `;
  }).join("");
  bar.innerHTML = html + `
    <button id="add-companion-btn" class="btn btn-secondary add-companion-btn" ${atMax ? 'disabled' : ''}>
      + Add Companion (${party.length}/${MAX_PARTY_SIZE})
    </button>
  `;
  bar.querySelectorAll(".party-member-mini").forEach(el => {
    el.addEventListener("click", () => selectCreationMember(parseInt(el.dataset.index, 10)));
  });
  const addBtn = document.getElementById("add-companion-btn");
  if (addBtn) addBtn.addEventListener("click", addCompanion);
}

function selectCreationMember(index) {
  if (index < 0 || index >= party.length) return;
  activePartyIndex = index;
  playerCharacter = party[index];
  abilityDraft = null;
  document.getElementById("ability-pool").classList.add("hidden");
  document.getElementById("auto-arrange-btn").classList.add("hidden");
  updateHeaderStats();
  showRolledCharacter();
  renderShop();
  renderInventoryCreate();
  renderPartyRosterCreation();
  validateCharacterReady();
}

async function addCompanion() {
  if (party.length >= MAX_PARTY_SIZE) {
    showCreationError("Your party is full.");
    return;
  }
  await rollCharacter();
}

function modifierText(mod) {
  if (mod > 0) return `+${mod}`;
  if (mod < 0) return `${mod}`;
  return "—";
}

function showRolledCharacter() {
  validateCharacterReady();
  const abilities = playerCharacter.abilities;
  const mods = playerCharacter.sheet.ability_modifiers;
  const container = document.getElementById("rolled-abilities");
  container.innerHTML = `
    <div class="ability-grid">
      ${Object.entries(abilities).map(([k, v]) => {
        const mod = abilityModifierValue(k, mods);
        return `
        <div class="ability-card ability-${abilityColor(k)}">
          <div class="ability-score">${v}</div>
          <div class="ability-mod">${modifierText(mod)}</div>
          <div class="ability-name">${abilityShort(k)}</div>
        </div>`;
      }).join("")}
    </div>
  `;
  safeSetText("shop-gold", `${Number(playerCharacter.remaining_gold).toFixed(1)} gp`);
  updateCreationSummary();
  renderClassInfo();
  renderClassAbilities();
  renderThiefSkills();
  renderLanguagesCreate();
  renderAncestryTraitsCreate();
  renderTurnUndeadCreate();
  renderCreationSaves();
  renderBreakdowns();
  renderStarterKit();
  updateHeaderStats();
  renderPartyRosterCreation();
  validateCharacterReady();
  saveGame();
}

function renderAbilityPool() {
  const poolEl = document.getElementById("ability-pool");
  if (!abilityDraft) return;
  const usedIndices = new Set(Object.values(abilityDraft.assigned));
  poolEl.innerHTML = `
    <div style="width:100%;margin-bottom:0.4rem;font-size:0.8rem;color:var(--ink-2);">
      Click a score, then click an ability to assign it.
    </div>
    ${abilityDraft.pool.map((score, i) => {
      const isUsed = usedIndices.has(i);
      const isSelected = abilityDraft.selectedIndex === i;
      return `<div class="pool-score ${isUsed ? 'used' : ''}" data-score="${score}" data-index="${i}" style="${isSelected ? 'border-color:var(--accent)' : ''}">${score}</div>`;
    }).join("")}
  `;
  poolEl.querySelectorAll(".pool-score:not(.used)").forEach(el => {
    el.addEventListener("click", () => {
      abilityDraft.selectedIndex = parseInt(el.dataset.index, 10);
      renderAbilityPool();
      renderRolledAbilitiesDraft();
    });
  });
  renderRolledAbilitiesDraft();
}

function renderRolledAbilitiesDraft() {
  const container = document.getElementById("rolled-abilities");
  const selected = abilityDraft.selectedIndex !== undefined;
  container.innerHTML = `
    <div class="ability-grid">
      ${ABILITY_ORDER.map(k => {
        const idx = abilityDraft.assigned[k];
        const v = idx !== undefined ? abilityDraft.pool[idx] : undefined;
        return `
        <div class="ability-card ability-${abilityColor(k)} ${selected ? 'ability-selectable' : ''}" data-ability="${k}">
          <div class="ability-score">${v ?? "—"}</div>
          <div class="ability-mod">${v !== undefined ? modifierText(abilityModifierValue(k, computeModifiersFromDraft())) : "—"}</div>
          <div class="ability-name">${abilityShort(k)}</div>
        </div>`;
      }).join("")}
    </div>
  `;
  container.querySelectorAll(".ability-card").forEach(el => {
    el.addEventListener("click", () => {
      if (abilityDraft.selectedIndex === undefined) return;
      const ability = el.dataset.ability;
      abilityDraft.assigned[ability] = abilityDraft.selectedIndex;
      delete abilityDraft.selectedIndex;
      renderAbilityPool();
      if (Object.keys(abilityDraft.assigned).length === 6) {
        finalizeArrangeCharacter();
      }
    });
  });
}

function abilityModifierFromRules(ability, score) {
  if (!osricRules?.ability_modifiers) return {};
  const table = osricRules.ability_modifiers[ability];
  if (!table) return {};
  // Find the closest score entry (exact match, or nearest lower if modded tables omit values).
  let chosen = table[String(score)];
  if (chosen === undefined) {
    const scores = Object.keys(table).map(Number).sort((a, b) => a - b);
    let nearest = scores[0];
    for (const s of scores) {
      if (s <= score) nearest = s;
      else break;
    }
    chosen = table[String(nearest)];
  }
  return chosen || {};
}

function computeModifiersFromDraft() {
  const mods = { strength: { to_hit: 0, damage: 0 }, dexterity: { missile_to_hit: 0, ac_ascending: 0 }, constitution: { hp_modifier: 0 }, intelligence: { bonus_languages: 0 }, wisdom: { mental_save: 0 }, charisma: { reaction: 0 } };
  if (!abilityDraft) return mods;
  for (const [ability, idx] of Object.entries(abilityDraft.assigned)) {
    if (idx === undefined) continue;
    const score = abilityDraft.pool[idx];
    const row = abilityModifierFromRules(ability, score);
    if (ability === "strength") {
      mods.strength = { to_hit: row.to_hit || 0, damage: row.damage || 0 };
    } else if (ability === "dexterity") {
      mods.dexterity = { missile_to_hit: row.missile_to_hit || 0, ac_ascending: row.ac_ascending || 0 };
    } else if (ability === "constitution") {
      mods.constitution.hp_modifier = row.hp_modifier || 0;
    } else if (ability === "intelligence") {
      mods.intelligence.bonus_languages = row.bonus_languages || 0;
    } else if (ability === "wisdom") {
      mods.wisdom.mental_save = row.mental_save || 0;
    } else if (ability === "charisma") {
      mods.charisma.reaction = row.reaction || 0;
    }
  }
  return mods;
}

async function finalizeArrangeCharacter() {
  const name = document.getElementById("char-name").value || "Hero";
  const ancestry = document.getElementById("char-ancestry").value;
  const class_id = document.getElementById("char-class").value;
  const alignment = document.getElementById("char-alignment").value;
  const abilities = {};
  for (const [ability, idx] of Object.entries(abilityDraft.assigned)) {
    abilities[ability] = abilityDraft.pool[idx];
  }
  try {
    const newCharacter = await api("/api/osric/character", {
      method: "POST",
      body: JSON.stringify({ name, ancestry, class_id, alignment, roll_method: "arrange_to_taste", abilities }),
    });
    party.push(newCharacter);
    activePartyIndex = party.length - 1;
    playerCharacter = newCharacter;
    abilityDraft = null;
    document.getElementById("ability-pool").classList.add("hidden");
    document.getElementById("auto-arrange-btn").classList.add("hidden");
    showRolledCharacter();
    renderShop();
    renderInventoryCreate();
    renderPartyRosterCreation();
  } catch (err) {
    showCreationError(err.message, `<button class="btn btn-secondary" onclick="autoArrange()" style="font-size:0.75rem;padding:0.3rem 0.6rem;">Auto-Arrange</button>`);
  }
}

function autoArrange() {
  if (!abilityDraft) return;
  const class_id = document.getElementById("char-class").value;
  const classData = osricOptions.classes.find(c => c.id === class_id);
  const primes = classData?.prime_requisites || [];
  const indexedPool = abilityDraft.pool.map((score, i) => ({ score, i })).sort((a, b) => b.score - a.score);
  const assigned = {};
  const order = [...primes, ...ABILITY_ORDER.filter(a => !primes.includes(a))];
  indexedPool.forEach((entry, i) => {
    assigned[order[i]] = entry.i;
  });
  abilityDraft.assigned = assigned;
  renderAbilityPool();
  finalizeArrangeCharacter();
}

function abilityModifierValue(ability, mods) {
  const map = {
    strength: mods.strength.to_hit,
    intelligence: mods.intelligence.bonus_languages,
    wisdom: mods.wisdom.mental_save,
    dexterity: mods.dexterity.missile_to_hit,
    constitution: mods.constitution.hp_modifier,
    charisma: mods.charisma.reaction,
  };
  return map[ability] || 0;
}

function updateCreationSummary() {
  const s = playerCharacter.sheet;
  const mods = s.ability_modifiers;
  const summary = document.getElementById("creation-summary");
  if (!summary) return;
  summary.innerHTML = `
    <div class="summary-row">
      <span>HP <b>${s.hit_points}</b></span>
      <span>AC <b>${s.armour_class}</b> / ${s.armour_class_descending} desc</span>
      <span>THAC0 <b>${s.thac0}</b></span>
      <span>MV <b>${s.movement}</b></span>
    </div>
    <div class="summary-row" style="margin-top:0.5rem;">
      <span>Melee to-hit <b>${modifierText(mods.strength.to_hit)}</b></span>
      <span>Melee dmg <b>${modifierText(mods.strength.damage)}</b></span>
      <span>Missile to-hit <b>${modifierText(mods.dexterity.missile_to_hit)}</b></span>
      <span>HP mod <b>${modifierText(mods.constitution.hp_modifier)}</b></span>
    </div>
    <div class="summary-row" style="margin-top:0.5rem;">
      <span>Languages <b>${mods.intelligence.bonus_languages}</b></span>
      <span>Mental save <b>${modifierText(mods.wisdom.mental_save)}</b></span>
      <span>Reaction <b>${modifierText(mods.charisma.reaction)}</b></span>
      <span>Enc <b>${s.encumbrance?.label || "Light"}</b> ${s.inventory.weight.toFixed(1)} lb</span>
    </div>
  `;
}

function renderClassInfo() {
  const class_id = playerCharacter.class;
  const classData = osricOptions.classes.find(c => c.id === class_id);
  const ancestry = osricOptions.ancestries.find(a => a.id === playerCharacter.ancestry);
  const el = document.getElementById("class-info");
  if (!classData) return;
  el.innerHTML = `
    <div class="class-info-row"><span>Ancestry</span><b>${ancestry?.name || titleCase(playerCharacter.ancestry)}</b></div>
    <div class="class-info-row"><span>Class</span><b>${classData.name}</b></div>
    <div class="class-info-row"><span>Hit Die</span><b>1d${classData.hit_die}</b></div>
    <div class="class-info-row"><span>Prime Requisites</span><b class="prime">${classData.prime_requisites.map(titleCase).join(", ") || "—"}</b></div>
    <div class="class-info-row"><span>Alignment</span><b>${playerCharacter.alignment}</b></div>
    <div class="class-info-row"><span>Next Level</span><b>${classData.next_level_xp.toLocaleString()} XP</b></div>
  `;
}

function renderClassAbilities() {
  const abilities = getClassAbilities(playerCharacter.class);
  const el = document.getElementById("class-abilities");
  if (!el) return;
  if (!abilities.length) {
    el.innerHTML = "";
    return;
  }
  el.innerHTML = `
    <div class="section-title" style="margin-top:0.5rem;">Class Abilities</div>
    <ul class="ability-list">
      ${abilities.map(a => `<li>${a}</li>`).join("")}
    </ul>
  `;
}

function renderThiefSkills() {
  const class_id = playerCharacter.class;
  const el = document.getElementById("thief-skills");
  if (!el || class_id !== "thief") {
    if (el) el.innerHTML = "";
    return;
  }
  const skills = getThiefSkills();
  el.innerHTML = `
    <div class="section-title" style="margin-top:0.5rem;">Thief Skills</div>
    <div class="thief-grid">
      ${Object.entries(skills).map(([name, value]) => `
        <div class="thief-card"><b>${value}%</b><span>${titleCase(name.replace(/_/g, " "))}</span></div>
      `).join("")}
    </div>
  `;
}

function renderLanguagesCreate() {
  const el = document.getElementById("languages-create");
  if (!el) return;
  const mods = playerCharacter.sheet.ability_modifiers;
  const bonus = mods.intelligence.bonus_languages || 0;
  const base = bonus > 0 ? `Common + ${bonus} bonus` : "Common";
  el.innerHTML = `
    <div class="section-title" style="margin-top:0.5rem;">Languages</div>
    <div class="language-line">${base}</div>
  `;
}

function renderCreationSaves() {
  const s = playerCharacter.sheet;
  const el = document.getElementById("saving-throws-create");
  if (!el || !s.saving_throws) return;
  el.innerHTML = `
    <div class="section-title" style="margin-top:0;">Saving Throws</div>
    <div class="save-grid">
      <div class="save-card"><b>${s.saving_throws.death_paralysis_poison}</b><span>Death</span></div>
      <div class="save-card"><b>${s.saving_throws.petrification_polymorph}</b><span>Petrify</span></div>
      <div class="save-card"><b>${s.saving_throws.aimed_magic_items}</b><span>Wand</span></div>
      <div class="save-card"><b>${s.saving_throws.breath_weapons}</b><span>Breath</span></div>
      <div class="save-card"><b>${s.saving_throws.spells}</b><span>Spell</span></div>
    </div>
  `;
}

function renderAncestryTraitsCreate() {
  const s = playerCharacter.sheet;
  const el = document.getElementById("class-info");
  if (!el || !s.ancestry_traits || !s.ancestry_traits.length) return;
  // Append after existing class-info content.
  const existing = el.querySelector(".traits-list");
  if (existing) existing.remove();
  const div = document.createElement("div");
  div.className = "traits-list";
  div.style.marginTop = "0.75rem";
  div.innerHTML = `<div class="section-title">Ancestry Traits</div><ul class="ability-list">${s.ancestry_traits.map(t => `<li>${t}</li>`).join("")}</ul>`;
  el.appendChild(div);
}

function renderTurnUndeadCreate() {
  const s = playerCharacter.sheet;
  const el = document.getElementById("class-abilities");
  if (!el || !s.turn_undead) return;
  const existing = el.querySelector(".turn-undead-list");
  if (existing) existing.remove();
  const div = document.createElement("div");
  div.className = "turn-undead-list";
  div.style.marginTop = "0.75rem";
  div.innerHTML = `
    <div class="section-title">Turn Undead</div>
    <div class="save-grid">
      ${Object.entries(s.turn_undead).map(([creature, target]) => `
        <div class="save-card"><b>${target}+</b><span>${titleCase(creature.replace(/_/g, " "))}</span></div>
      `).join("")}
    </div>
  `;
  el.appendChild(div);
}

function renderBreakdowns() {
  const s = playerCharacter.sheet;
  const bdRow = document.getElementById("breakdowns");
  if (!bdRow) return;
  bdRow.classList.remove("hidden");
  bdRow.innerHTML = renderAcBreakdownInline(s) + renderHpBreakdownInline(s);
}

function formatCoins(cp) {
  if (cp === 0) return "Free";
  const gp = cp / 100;
  return `${gp.toFixed(2).replace(/\.?0+$/, "")} gp`;
}

function canUseItem(item) {
  const classData = osricOptions.classes.find(c => c.id === playerCharacter.class);
  if (!classData) return true;
  if (item.category === "armour") {
    const allowed = classData.armour_allowed || [];
    return allowed.includes("all") || allowed.includes(item.id);
  }
  if (item.category === "shields") {
    return classData.shields_allowed;
  }
  if (item.category === "weapons") {
    const allowed = classData.weapons_allowed || [];
    return allowed.includes("all") || allowed.includes(item.id);
  }
  return true;
}

function itemDetail(item) {
  const parts = [];
  if (item.category === "armour" && item.ac_ascending != null) parts.push(`AC ${item.ac_ascending}`);
  if (item.category === "shields" && item.ac_ascending_modifier != null) parts.push(`AC +${item.ac_ascending_modifier}`);
  if (item.damage) parts.push(`${item.damage} dmg`);
  if (item.missile && item.range) parts.push(`range ${item.range}`);
  if (item.weight) parts.push(`${item.weight} lb`);
  return parts.join(" · ") || item.category;
}

function canAffordItem(item) {
  if (!playerCharacter) return false;
  return playerCharacter.remaining_gold >= item.cost_cp / 100;
}

function renderShopItem(item) {
  const usable = canUseItem(item);
  const affordable = canAffordItem(item);
  const disabled = !usable || !affordable;
  let priceLabel = formatCoins(item.cost_cp);
  if (!usable) priceLabel += ' · cannot use';
  else if (!affordable) priceLabel += ' · cannot afford';
  return `
    <div class="shop-list-row ${usable ? '' : 'unusable'} ${affordable ? '' : 'unaffordable'}">
      <div class="shop-list-main">
        <div class="shop-list-name">${item.name}</div>
        <div class="shop-list-detail">${itemDetail(item)}</div>
      </div>
      <div class="shop-list-meta">
        <div class="shop-list-price">${priceLabel}</div>
        <button class="btn btn-secondary buy-btn" data-id="${item.id}" ${disabled ? 'disabled' : ''}>Buy & Equip</button>
      </div>
    </div>
  `;
}

function groupBy(items, key) {
  return items.reduce((acc, item) => {
    const group = item[key] || "Other";
    acc[group] = acc[group] || [];
    acc[group].push(item);
    return acc;
  }, {});
}

function renderShopItems(items) {
  return `<div class="shop-category-list">${items.map(renderShopItem).join("")}</div>`;
}

function renderShop() {
  const grid = document.getElementById("shop-grid");
  if (!grid || !playerCharacter) return;
  grid.innerHTML = `
    <div class="shop-card">
      <div class="shop-card-title">Shop</div>
      <div class="shop-card-text">Buy armour, shields, weapons, and adventuring gear. Greyed items cannot be used by your class.</div>
      <button class="btn btn-secondary shop-open-btn">Buy Equipment</button>
    </div>
  `;
  grid.querySelector(".shop-open-btn").addEventListener("click", () => openShopModal("armour"));
}

let shopModalActiveCategory = "armour";
const shopCart = new Map();

function openShopModal(category) {
  shopModalActiveCategory = category || "armour";
  shopCart.clear();
  const modal = document.getElementById("shop-modal");
  modal.classList.remove("hidden");
  renderShopModal();
  renderCart();
  bindCartDropZone();
}

function closeShopModal() {
  document.getElementById("shop-modal").classList.add("hidden");
  shopCart.clear();
}

function renderShopModal() {
  const catalog = document.getElementById("shop-catalog");
  if (!catalog || !playerCharacter) return;
  safeSetText("shop-modal-gold", `${Number(playerCharacter.remaining_gold).toFixed(1)} gp`);
  document.querySelectorAll(".shop-tab").forEach(tab => {
    tab.classList.toggle("active", tab.dataset.cat === shopModalActiveCategory);
  });

  const items = osricOptions.equipment.filter(i => i.category === shopModalActiveCategory);
  if (shopModalActiveCategory === "weapons") {
    const groups = groupBy(items, "subcategory");
    const order = ["sword", "axe", "polearm", "blunt", "missile", "other"];
    const keys = Object.keys(groups).sort((a, b) => order.indexOf(a) - order.indexOf(b));
    catalog.innerHTML = keys.map(sub => `
      <div class="shop-modal-section">
        <div class="shop-modal-section-title">${titleCase(sub)}</div>
        ${groups[sub].map(renderShopModalRow).join("")}
      </div>
    `).join("");
  } else {
    catalog.innerHTML = items.map(renderShopModalRow).join("");
  }

  catalog.querySelectorAll(".shop-modal-row").forEach(row => {
    row.addEventListener("dragstart", (e) => {
      row.classList.add("dragging");
      e.dataTransfer.setData("text/plain", row.dataset.id);
      e.dataTransfer.effectAllowed = "copy";
    });
    row.addEventListener("dragend", () => row.classList.remove("dragging"));
    row.addEventListener("dblclick", () => addToCart(row.dataset.id));
  });
}

function renderShopModalRow(item) {
  const usable = canUseItem(item);
  const affordable = canAffordItem(item);
  const rowClass = [usable ? "" : "unusable", affordable ? "" : "unaffordable"].filter(Boolean).join(" ").trim();
  let priceLabel = formatCoins(item.cost_cp);
  if (!usable) priceLabel += " · cannot use";
  else if (!affordable) priceLabel += " · cannot afford";
  return `
    <div class="shop-modal-row ${rowClass}" draggable="${usable && affordable ? "true" : "false"}" data-id="${item.id}">
      <div class="shop-modal-info">
        <div class="shop-modal-name">${item.name}</div>
        <div class="shop-modal-detail">${itemDetail(item)}</div>
      </div>
      <div class="shop-modal-meta">
        <div class="shop-modal-price">${priceLabel}</div>
      </div>
    </div>
  `;
}

function bindCartDropZone() {
  const cart = document.getElementById("shop-cart");
  if (!cart || cart.dataset.dropBound) return;
  cart.dataset.dropBound = "true";
  cart.addEventListener("dragover", (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
    cart.classList.add("drag-over");
  });
  cart.addEventListener("dragleave", () => cart.classList.remove("drag-over"));
  cart.addEventListener("drop", (e) => {
    e.preventDefault();
    cart.classList.remove("drag-over");
    const id = e.dataTransfer.getData("text/plain");
    if (id) addToCart(id);
  });
}

function addToCart(itemId) {
  const item = osricOptions.equipment.find(e => e.id === itemId);
  if (!item || !canUseItem(item) || !canAffordItem(item)) return;
  shopCart.set(itemId, (shopCart.get(itemId) || 0) + 1);
  renderCart();
}

function removeFromCart(itemId) {
  const qty = shopCart.get(itemId);
  if (qty === undefined) return;
  if (qty <= 1) shopCart.delete(itemId);
  else shopCart.set(itemId, qty - 1);
  renderCart();
}

function clearCart() {
  shopCart.clear();
  renderCart();
}

function renderCart() {
  const itemsEl = document.getElementById("shop-cart-items");
  const emptyEl = document.getElementById("shop-cart-empty");
  const totalEl = document.getElementById("shop-cart-total");
  if (!itemsEl || !emptyEl || !totalEl) return;

  let totalCp = 0;
  let html = "";
  for (const [itemId, qty] of shopCart) {
    const item = osricOptions.equipment.find(e => e.id === itemId) || { name: itemId, cost_cp: 0 };
    totalCp += item.cost_cp * qty;
    html += `
      <div class="shop-cart-row">
        <div>
          <div>${item.name}</div>
          <div style="font-size:0.65rem;color:var(--ink-2);">${formatCoins(item.cost_cp)} each</div>
        </div>
        <div style="display:flex;align-items:center;gap:0.4rem;">
          <span class="qty">×${qty}</span>
          <button class="btn btn-danger remove-cart-btn" data-id="${item.id}">−</button>
        </div>
      </div>
    `;
  }
  itemsEl.innerHTML = html;
  emptyEl.style.display = shopCart.size ? "none" : "block";
  const totalGp = totalCp / 100;
  const overBudget = playerCharacter && totalCp > playerCharacter.remaining_gold * 100;
  totalEl.textContent = `Total: ${totalGp.toFixed(2).replace(/\.?0+$/, "")} gp`;
  totalEl.classList.toggle("over-budget", overBudget);

  itemsEl.querySelectorAll(".remove-cart-btn").forEach(btn => {
    btn.addEventListener("click", () => removeFromCart(btn.dataset.id));
  });
}

async function buyCart() {
  if (!playerCharacter || !shopCart.size) return;
  const totalCp = Array.from(shopCart.entries()).reduce((sum, [id, qty]) => {
    const item = osricOptions.equipment.find(e => e.id === id);
    return sum + (item ? item.cost_cp * qty : 0);
  }, 0);
  if (totalCp > playerCharacter.remaining_gold * 100) {
    showCreationError("Not enough gold for this cart.");
    return;
  }
  try {
    for (const [itemId, qty] of shopCart) {
      for (let i = 0; i < qty; i++) {
        playerCharacter = await api("/api/osric/buy", {
          method: "POST",
          body: JSON.stringify({ character: playerCharacter, item_id: itemId }),
        });
      }
      const item = osricOptions.equipment.find(e => e.id === itemId);
      if (item && ["armour", "shields", "weapons"].includes(item.category)) {
        playerCharacter = await api("/api/osric/equip", {
          method: "POST",
          body: JSON.stringify({ character: playerCharacter, item_id: itemId, equip: true }),
        });
      }
    }
    shopCart.clear();
    refreshAfterTransaction();
    renderCart();
    renderShopModal();
  } catch (err) {
    showCreationError(err.message);
  }
}

function refreshAfterTransaction() {
  if (party.length && activePartyIndex >= 0 && activePartyIndex < party.length) {
    party[activePartyIndex] = playerCharacter;
  }
  showRolledCharacter();
  renderShop();
  renderInventoryCreate();
  renderPartyRosterCreation();
  validateCharacterReady();
  saveGame();
}

function starterPackageCost(classId) {
  const pkg = getClassFeatures(classId);
  if (!pkg) return 0;
  return pkg.items.reduce((total, itemId) => {
    const item = osricOptions.equipment.find(e => e.id === itemId);
    return total + (item ? item.cost_cp / 100 : 0);
  }, 0);
}

function renderStarterKit() {
  const el = document.getElementById("starter-kit");
  if (!el || !playerCharacter) {
    if (el) el.innerHTML = "";
    return;
  }
  const classId = playerCharacter.class;
  const pkg = getClassFeatures(classId);
  if (!pkg) {
    el.innerHTML = "";
    return;
  }
  const cost = starterPackageCost(classId);
  const affordable = playerCharacter.remaining_gold >= cost;
  const itemNames = pkg.items.map(id => {
    const item = osricOptions.equipment.find(e => e.id === id);
    return item ? item.name : id;
  }).join(", ");

  el.innerHTML = `
    <div class="starter-kit-card">
      <div class="starter-kit-head">
        <div>
          <div class="starter-kit-name">${pkg.name}</div>
          <div class="starter-kit-items">${itemNames}</div>
        </div>
        <div class="starter-kit-cost ${affordable ? '' : 'unaffordable'}">${cost.toFixed(1)} gp</div>
      </div>
      <button id="buy-starter-kit" class="btn btn-secondary" ${affordable ? "" : "disabled"}>Buy Starter Kit</button>
      ${!affordable ? `<div class="kit-warning">Not enough gold for this kit.</div>` : ""}
    </div>
  `;

  const btn = document.getElementById("buy-starter-kit");
  if (btn) {
    btn.addEventListener("click", buyStarterKit);
  }
}

async function buyStarterKit() {
  if (!playerCharacter) return;
  try {
    playerCharacter = await api("/api/osric/buy-package", {
      method: "POST",
      body: JSON.stringify({ character: playerCharacter, equip: true }),
    });
    refreshAfterTransaction();
  } catch (err) {
    showCreationError(err.message);
  }
}

function renderInventoryCreate() {
  const el = document.getElementById("inventory-create");
  if (!el || !playerCharacter) return;
  const inv = playerCharacter.sheet.inventory || { items: [] };
  if (!inv.items.length) {
    el.innerHTML = "";
    return;
  }
  el.innerHTML = `
    <div class="section-title" style="margin-top:0;">Inventory</div>
    <ul class="inventory-list">
      ${inv.items.map(i => {
        const item = osricOptions.equipment.find(e => e.id === i.item_id) || { name: i.item_id };
        const isEquipped = i.equipped;
        const sellRatio = osricRules?.combat?.sell_back_ratio ?? 0.5;
        const sellPrice = Math.floor((osricOptions.equipment.find(e => e.id === i.item_id)?.cost_cp || 0) * sellRatio / 100);
        return `<li class="inventory-row">
          <span class="${isEquipped ? 'equipped' : ''}">${item.name}${isEquipped ? ' ◆' : ''}</span>
          <span class="qty">×${i.quantity || 1}</span>
          <span style="display:flex;gap:0.3rem;">
            ${item.category === "weapons" || item.category === "armour" || item.category === "shields" ? `
              <button class="btn btn-secondary equip-btn" data-id="${i.item_id}" data-equip="${!isEquipped}">${isEquipped ? 'Unequip' : 'Equip'}</button>
            ` : ""}
            <button class="btn btn-danger sell-btn" data-id="${i.item_id}">Sell ${sellPrice}gp</button>
          </span>
        </li>`;
      }).join("")}
    </ul>
  `;

  el.querySelectorAll(".equip-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      try {
        playerCharacter = await api("/api/osric/equip", {
          method: "POST",
          body: JSON.stringify({ character: playerCharacter, item_id: btn.dataset.id, equip: btn.dataset.equip === "true" }),
        });
        refreshAfterTransaction();
      } catch (err) {
        showCreationError(err.message);
      }
    });
  });

  el.querySelectorAll(".sell-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      try {
        playerCharacter = await api("/api/osric/sell", {
          method: "POST",
          body: JSON.stringify({ character: playerCharacter, item_id: btn.dataset.id }),
        });
        refreshAfterTransaction();
      } catch (err) {
        showCreationError(err.message);
      }
    });
  });
}

function renderPartyPanel() {
  const panel = document.getElementById("party-panel");
  if (!panel) return;
  if (party.length <= 1) {
    panel.innerHTML = "";
    return;
  }
  const acted = combatState?.partyActed || new Set();
  panel.innerHTML = party.map((c, i) => {
    const s = c.sheet;
    const hpPct = s.max_hit_points > 0 ? (s.hit_points / s.max_hit_points) * 100 : 0;
    const active = i === activePartyIndex;
    const hasActed = acted.has(i);
    return `
      <div class="party-member-token ${active ? 'active' : ''} ${hasActed ? 'acted' : ''}" data-index="${i}">
        <div class="token-portrait"><span>${classIcon(c.class)}</span></div>
        <div class="token-bar">
          <div class="token-name">${c.name}</div>
          <div class="token-hp"><div class="token-hp-fill" style="width:${hpPct}%"></div></div>
        </div>
      </div>
    `;
  }).join("");
  panel.querySelectorAll(".party-member-token").forEach(el => {
    el.addEventListener("click", () => setActiveCharacter(parseInt(el.dataset.index, 10)));
  });
}

function renderCharacterPanel() {
  renderPartyPanel();
  const content = document.getElementById("char-panel-content");
  if (!content) return;
  if (!playerCharacter) {
    content.innerHTML = `<p style="color:var(--ink-2)">No hero yet.</p>`;
    return;
  }
  const s = playerCharacter.sheet;
  const inv = s.inventory || { items: [] };
  const mods = s.ability_modifiers;
  const hpPct = s.max_hit_points > 0 ? (s.hit_points / s.max_hit_points) * 100 : 0;
  const classData = osricOptions.classes.find(c => c.id === playerCharacter.class);
  content.innerHTML = `
    <div class="char-header">
      <div class="portrait"><span>${playerCharacter.name[0]}</span></div>
      <div>
        <div class="char-title">${playerCharacter.name}</div>
        <div class="char-sub">${titleCase(playerCharacter.ancestry)} ${titleCase(playerCharacter.class)} · ${playerCharacter.alignment}</div>
        <div class="char-sub">Prime: <b class="prime">${classData?.prime_requisites.map(titleCase).join(", ") || "—"}</b></div>
      </div>
    </div>
    <div class="hp-bar"><div class="hp-fill ${hpPct <= 25 ? 'hp-low' : ''}" id="hp-fill" style="width:${hpPct}%"></div></div>
    <div class="char-meta">Level <b>${s.level}</b> · XP <b>${s.xp}</b> / ${s.next_level_xp} · HD <b>${s.hit_die || '1d' + (classData?.hit_die || 8)}</b></div>
    <div class="xp-bar"><div class="xp-fill" style="width:${Math.min(100, (s.next_level_xp ? (s.xp / s.next_level_xp) * 100 : 0))}%"></div></div>
    <div class="stat-row">
      <div class="stat-card"><div class="stat-icon">${icon("heart", 18)}</div><div class="stat-value" id="char-hp">${s.hit_points}/${s.max_hit_points}</div><div class="stat-label">HP</div></div>
      <div class="stat-card"><div class="stat-icon">${icon("shield", 18)}</div><div class="stat-value">${s.armour_class}</div><div class="stat-label">AC</div></div>
      <div class="stat-card"><div class="stat-icon">${icon("crosshair", 18)}</div><div class="stat-value">${s.thac0}</div><div class="stat-label">THAC0</div></div>
      <div class="stat-card"><div class="stat-icon">${icon("boot", 18)}</div><div class="stat-value">${s.movement}</div><div class="stat-label">MV</div></div>
    </div>
    <div class="section-title">Abilities</div>
    <div class="ability-grid">
      ${Object.entries(playerCharacter.abilities).map(([k, v]) => {
        const mod = abilityModifierValue(k, mods);
        return `<div class="ability-card ability-${abilityColor(k)}">
          <div class="ability-score">${v}</div>
          <div class="ability-mod">${modifierText(mod)}</div>
          <div class="ability-name">${abilityShort(k)}</div>
        </div>`;
      }).join("")}
    </div>
    <div class="section-title">Combat Modifiers</div>
    <div class="mod-row">
      <div class="mod-pill">Melee to-hit <b>${modifierText(mods.strength.to_hit)}</b></div>
      <div class="mod-pill">Melee dmg <b>${modifierText(mods.strength.damage)}</b></div>
      <div class="mod-pill">Missile to-hit <b>${modifierText(mods.dexterity.missile_to_hit)}</b></div>
      <div class="mod-pill">AC adj <b>${modifierText(mods.dexterity.ac_ascending)}</b></div>
    </div>
    ${renderAcBreakdownInline(s)}
    ${renderHpBreakdownInline(s)}
    <div class="section-title">Inventory <span class="weight-tag">${s.inventory.weight.toFixed(1)} lb</span></div>
    <ul class="inventory-list">
      ${inv.items.length ? inv.items.map(i => {
        const item = osricOptions.equipment.find(e => e.id === i.item_id) || { name: i.item_id };
        const usable = item.use_action === "heal" && combatState && playerConscious();
        return `<li class="inventory-row">
          <span class="${i.equipped ? 'equipped' : ''}">${item.name}${i.equipped ? ' ◆' : ''}</span>
          <span style="display:flex;align-items:center;gap:0.4rem;">
            <span class="qty">×${i.quantity || 1}</span>
            ${usable ? `<button class="btn btn-secondary use-item-btn" data-id="${i.item_id}" style="font-size:0.7rem;padding:0.2rem 0.4rem;">Use</button>` : ""}
          </span>
        </li>`;
      }).join("") : '<li style="color:var(--ink-2);font-size:0.8rem;">Empty</li>'}
    </ul>
    ${s.spell_slots && Object.keys(s.spell_slots).length ? `
    <div class="section-title">Spell Slots</div>
    <div class="mod-row">
      ${Object.entries(s.spell_slots).map(([lvl, n]) => `<div class="mod-pill">Level ${lvl}: <b>${n}</b></div>`).join(" ")}
    </div>` : ""}
    ${s.saving_throws ? `
    <div class="section-title">Saving Throws</div>
    <div class="save-grid">
      <div class="save-card"><b>${s.saving_throws.death_paralysis_poison}</b><span>Death</span></div>
      <div class="save-card"><b>${s.saving_throws.petrification_polymorph}</b><span>Petrify</span></div>
      <div class="save-card"><b>${s.saving_throws.aimed_magic_items}</b><span>Wand</span></div>
      <div class="save-card"><b>${s.saving_throws.breath_weapons}</b><span>Breath</span></div>
      <div class="save-card"><b>${s.saving_throws.spells}</b><span>Spell</span></div>
    </div>` : ""}
    ${renderLanguagesInline(mods)}
    ${renderClassAbilitiesInline(playerCharacter.class)}
    ${playerCharacter.class === "thief" ? renderThiefSkillsInline() : ""}
    ${renderTurnUndeadInline()}
    ${renderAncestryTraitsInline()}
    ${renderEncumbranceInline(s)}
    ${renderArmourCapInline(s)}
    <div class="gold-line">Gold: <b>${Number(playerCharacter.remaining_gold).toFixed(1)} gp</b></div>
  `;

  content.querySelectorAll(".use-item-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      if (btn.dataset.id === "potion_of_healing") {
        await usePotion();
      }
    });
  });
}

function renderLanguagesInline(mods) {
  const bonus = mods?.intelligence?.bonus_languages || 0;
  const languages = bonus > 0 ? `Common + ${bonus} bonus language${bonus > 1 ? "s" : ""}` : "Common";
  return `
    <div class="section-title">Languages</div>
    <div class="mod-row"><div class="mod-pill">${languages}</div></div>
  `;
}

function renderClassAbilitiesInline(classId) {
  const abilities = getClassAbilities(classId);
  if (!abilities.length) return "";
  return `
    <div class="section-title">Class Abilities</div>
    <div class="mod-row">
      ${abilities.map(a => `<div class="mod-pill">${a}</div>`).join(" ")}
    </div>
  `;
}

function renderThiefSkillsInline() {
  const skills = getThiefSkills();
  const entries = Object.entries(skills);
  if (!entries.length) return "";
  return `
    <div class="section-title">Thief Skills</div>
    <div class="mod-row">
      ${entries.map(([name, value]) => `<div class="mod-pill">${titleCase(name.replace(/_/g, " "))} <b>${value}%</b></div>`).join(" ")}
    </div>
  `;
}

function renderEncumbranceInline(s) {
  const enc = s.encumbrance;
  if (!enc) return "";
  return `
    <div class="section-title">Encumbrance</div>
    <div class="mod-row">
      <div class="mod-pill">${enc.label} <b>${enc.weight} lb</b></div>
      <div class="mod-pill">Penalty <b>-${enc.movement_penalty}</b></div>
      <div class="mod-pill">Base MV <b>${s.base_movement}</b></div>
    </div>
  `;
}

function renderArmourCapInline(s) {
  const inv = s.inventory?.items || [];
  for (const entry of inv) {
    if (!entry.equipped) continue;
    const item = osricOptions.equipment.find(e => e.id === entry.item_id);
    if (item && item.category === "armour" && item.movement_cap != null) {
      return `
        <div class="section-title">Armour Cap</div>
        <div class="mod-row">
          <div class="mod-pill">${item.name} <b>${item.movement_cap} ft</b></div>
        </div>
      `;
    }
  }
  return "";
}

function renderAncestryTraitsInline() {
  const traits = playerCharacter.sheet.ancestry_traits;
  if (!traits || !traits.length) return "";
  return `
    <div class="section-title">Ancestry Traits</div>
    <div class="mod-row">
      ${traits.map(t => `<div class="mod-pill">${t}</div>`).join(" ")}
    </div>
  `;
}

function renderTurnUndeadInline() {
  const table = playerCharacter.sheet.turn_undead;
  if (!table) return "";
  return `
    <div class="section-title">Turn Undead</div>
    <div class="mod-row">
      ${Object.entries(table).map(([creature, target]) => `<div class="mod-pill">${titleCase(creature.replace(/_/g, " "))} <b>${target}+</b></div>`).join(" ")}
    </div>
  `;
}

function renderAcBreakdownInline(s) {
  if (!s.ac_breakdown) return "";
  const bd = s.ac_breakdown;
  return `
    <div class="section-title">AC Breakdown</div>
    <div class="mod-row">
      <div class="mod-pill">Base <b>10</b></div>
      <div class="mod-pill">${bd.armour.name || "Unarmoured"} <b>${modifierText(bd.armour.ascending)}</b></div>
      <div class="mod-pill">${bd.shield.name || "No shield"} <b>${modifierText(bd.shield.ascending)}</b></div>
      <div class="mod-pill">DEX <b>${modifierText(bd.dexterity.ascending)}</b></div>
    </div>
  `;
}

function renderHpBreakdownInline(s) {
  if (!s.hp_breakdown) return "";
  const hpBd = s.hp_breakdown;
  return `
    <div class="section-title">HP Breakdown</div>
    <div class="mod-row">
      <div class="mod-pill">Roll <b>${hpBd.hit_die}</b></div>
      <div class="mod-pill">CON <b>${modifierText(hpBd.con_modifier)}</b></div>
      <div class="mod-pill">Total <b>${s.hit_points}</b></div>
    </div>
  `;
}

function titleCase(str) {
  return str.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

function log(msg, cls = "") {
  const logEl = document.getElementById("log");
  const entry = document.createElement("div");
  entry.className = `log-entry ${cls}`;
  entry.innerHTML = msg;
  logEl.appendChild(entry);
  logEl.scrollTop = logEl.scrollHeight;
}

function clearLog() {
  document.getElementById("log").innerHTML = "";
}

let dungeonModuleName = "crooked_tower";

function hasEquippedWeapon(character) {
  const c = character || playerCharacter;
  if (!c) return false;
  const inv = c.sheet.inventory || { items: [] };
  return inv.items.some(entry => entry.equipped && osricOptions.equipment.find(e => e.id === entry.item_id)?.category === "weapons");
}

function partyReadyForDungeon() {
  if (!party.length) return { ready: false, reason: "Create at least one character." };
  for (const c of party) {
    if (!hasEquippedWeapon(c)) {
      return { ready: false, reason: `${c.name} has no weapon equipped.` };
    }
  }
  return { ready: true, reason: "" };
}

function validateCharacterReady() {
  const btn = document.getElementById("enter-dungeon-btn");
  if (!btn) return;
  const status = partyReadyForDungeon();
  btn.disabled = !status.ready;
  btn.title = status.reason;
}

async function enterDungeon() {
  if (!party.length) {
    await rollCharacter();
    if (!party.length) return;
  }
  const status = partyReadyForDungeon();
  if (!status.ready) {
    showMessageModal("Party Not Ready", status.reason, [
      { label: "OK", primary: true },
    ]);
    return;
  }
  renderModuleList();
  document.getElementById("module-modal").classList.remove("hidden");
}

function renderModuleList() {
  const list = document.getElementById("module-list");
  if (!list || typeof DUNGEON_MODULES === "undefined") return;
  const unlocked = getUnlockedModules();
  list.innerHTML = Object.entries(DUNGEON_MODULES).map(([id, mod]) => {
    const locked = !unlocked.has(id);
    const predecessor = Object.entries(DUNGEON_MODULES).find(([_, m]) => m.unlocks === id);
    const lockHint = locked
      ? `Complete ${predecessor ? predecessor[1].name : "the prior dungeon"} to unlock.`
      : "";
    const levelText = mod.level ? `Level ${mod.level}` : "Level 1";
    return `
    <div class="module-card ${locked ? 'locked' : ''}" data-id="${id}" ${locked ? 'title="' + lockHint + '"' : ''}>
      <div class="module-card-info">
        <div class="module-card-title">${mod.name}${locked ? ' <span class="lock-tag">Locked</span>' : ''}</div>
        <div class="module-card-blurb">${mod.blurb}</div>
        ${locked ? `<div class="module-card-locked">${lockHint}</div>` : ""}
        ${!locked && mod.story ? `<div class="module-card-story">${mod.story}</div>` : ""}
        ${!locked && mod.objective ? `<div class="module-card-objective"><b>Objective:</b> ${mod.objective}</div>` : ""}
      </div>
      <div class="module-card-level">${levelText}</div>
    </div>
  `;
  }).join("");
  list.querySelectorAll(".module-card:not(.locked)").forEach(card => {
    card.addEventListener("click", () => startModule(card.dataset.id));
  });
}

function startModule(id) {
  dungeonModuleName = id;
  document.getElementById("module-modal").classList.add("hidden");
  document.getElementById("create-modal").classList.add("hidden");
  activePartyIndex = 0;
  playerCharacter = activeCharacter();
  renderCharacterPanel();
  clearLog();
  const mod = DUNGEON_MODULES[id];
  const names = party.map(c => c.name).join(", ");
  log(`<b>${names}</b> enter ${mod ? mod.name : "the dungeon"}.`, "hit");
  if (mod && mod.intro) log(mod.intro);
  updateLevelBadge();
  initCombat();
  saveGame();
}

function closeModuleModal() {
  document.getElementById("module-modal").classList.add("hidden");
}

function updateLevelBadge() {
  const badge = document.getElementById("level-badge");
  if (badge) badge.textContent = `Dungeon ${dungeonLevel}`;
}

function showEnd(won, message) {
  const modal = document.getElementById("end-modal");
  document.getElementById("end-title").textContent = won ? "Victory" : "Defeat";
  document.getElementById("end-msg").textContent = message;
  document.getElementById("restart-btn").textContent = "Play Again";
  document.getElementById("restart-btn").onclick = () => location.reload();
  modal.classList.remove("hidden");
}

function unlockNextModule() {
  const mod = DUNGEON_MODULES[dungeonModuleName];
  if (mod && mod.unlocks) {
    unlockModule(mod.unlocks);
  }
}

function showDescendChoice() {
  const modal = document.getElementById("end-modal");
  document.getElementById("end-title").textContent = "Exit Open";
  document.getElementById("end-msg").textContent = `You have cleared level ${dungeonLevel}. Escape with your loot, or descend deeper?`;
  document.getElementById("restart-btn").textContent = "Escape";
  document.getElementById("restart-btn").onclick = () => {
    unlockNextModule();
    location.reload();
  };

  const descendBtn = document.getElementById("descend-btn");
  if (!descendBtn) {
    const btn = document.createElement("button");
    btn.id = "descend-btn";
    btn.className = "btn btn-primary";
    btn.style.marginTop = "0.75rem";
    btn.textContent = "Descend Deeper";
    btn.onclick = () => descendLevel();
    modal.querySelector(".modal-card").appendChild(btn);
  } else {
    descendBtn.style.display = "inline-flex";
  }
  modal.classList.remove("hidden");
}

function descendLevel() {
  unlockNextModule();
  dungeonLevel++;
  document.getElementById("end-modal").classList.add("hidden");
  clearLog();
  updateLevelBadge();
  log(`<b>${playerCharacter.name}</b> descends to level ${dungeonLevel}.`, "hit");
  initCombat();
  saveGame();
}

async function initGame() {
  await loadOptions();

  const playBtn = document.getElementById("play-now-btn");
  const continueBtn = document.getElementById("continue-btn");
  const abandonBtn = document.getElementById("abandon-btn");

  if (hasSavedRun()) {
    continueBtn.classList.remove("hidden");
    abandonBtn.classList.remove("hidden");
  }

  continueBtn.addEventListener("click", async () => {
    const ok = await loadGame();
    if (!ok) {
      continueBtn.classList.add("hidden");
      abandonBtn.classList.add("hidden");
    }
  });

  abandonBtn.addEventListener("click", () => {
    confirmAction("Abandon Run", "This will permanently delete your saved party and dungeon progress. Are you sure?", () => {
      clearSave();
      continueBtn.classList.add("hidden");
      abandonBtn.classList.add("hidden");
      log("Previous run abandoned.");
    });
  });

  playBtn.addEventListener("click", () => {
    document.getElementById("landing-screen").classList.add("hidden");
    document.getElementById("create-modal").classList.remove("hidden");
    party = [];
    activePartyIndex = 0;
    playerCharacter = null;
    abilityDraft = null;
    document.getElementById("ability-pool").classList.add("hidden");
    document.getElementById("auto-arrange-btn").classList.add("hidden");
    updateHeaderStats();
    renderPartyRosterCreation();
    clearCreationDetails();
    document.getElementById("rolled-abilities").innerHTML = "";
    document.getElementById("creation-summary").innerHTML = `<p style="color:var(--ink-2)">Roll your first hero to begin the party.</p>`;
  });

  document.getElementById("roll-character-btn").addEventListener("click", rollCharacter);
  document.getElementById("auto-arrange-btn").addEventListener("click", autoArrange);
  document.getElementById("enter-dungeon-btn").addEventListener("click", enterDungeon);
  document.getElementById("restart-btn").addEventListener("click", () => {
    clearSave();
    location.reload();
  });

  document.getElementById("roll-method").addEventListener("change", () => {
    rollMethod = document.getElementById("roll-method").value;
  });

  document.getElementById("char-ancestry").addEventListener("change", () => {
    filterCreationOptions();
  });

  document.getElementById("char-class").addEventListener("change", () => {
    filterCreationOptions();
  });

  document.getElementById("char-alignment").addEventListener("change", () => {
    clearCreationErrors();
  });

  const helpModal = document.getElementById("help-modal");
  document.getElementById("help-btn").addEventListener("click", () => helpModal.classList.remove("hidden"));
  document.getElementById("close-help-btn").addEventListener("click", () => helpModal.classList.add("hidden"));
  helpModal.addEventListener("click", (e) => {
    if (e.target === helpModal) helpModal.classList.add("hidden");
  });

  const shopModal = document.getElementById("shop-modal");
  document.getElementById("close-shop-btn").addEventListener("click", closeShopModal);
  shopModal.addEventListener("click", (e) => {
    if (e.target === shopModal) closeShopModal();
  });

  const moduleModal = document.getElementById("module-modal");
  document.getElementById("close-module-btn").addEventListener("click", closeModuleModal);
  moduleModal.addEventListener("click", (e) => {
    if (e.target === moduleModal) closeModuleModal();
  });

  const messageModal = document.getElementById("message-modal");
  if (messageModal) {
    messageModal.addEventListener("click", (e) => {
      if (e.target === messageModal) messageModal.classList.add("hidden");
    });
  }
  document.querySelectorAll(".shop-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      shopModalActiveCategory = tab.dataset.cat;
      renderShopModal();
    });
  });
  document.getElementById("clear-cart-btn").addEventListener("click", clearCart);
  document.getElementById("buy-cart-btn").addEventListener("click", buyCart);
}

window.addEventListener("DOMContentLoaded", initGame);

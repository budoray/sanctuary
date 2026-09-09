/** Turn-based OSRIC combat and dungeon exploration. */

let combatState = null;
let pendingSpell = null;
let isAutoExploring = false;
let attackFocus = false;
let actionBusyFrom = 0;
let actionBusyUntil = 0;
let actionTickRaf = 0;

function actionDuration() {
  return 3000 + Math.floor(Math.random() * 2001);
}

function isActing() {
  if (Date.now() < actionBusyUntil) return true;
  const tray = document.getElementById("dice-tray");
  return !!(tray && tray.classList.contains("open"));
}

function beginActing(ms) {
  const dur = ms || actionDuration();
  const now = Date.now();
  actionBusyFrom = now;
  actionBusyUntil = Math.max(actionBusyUntil, now + dur);
  document.body.classList.add("acting");
  tickActingBar();
  if (typeof updateCombatUI === "function" && combatState) updateCombatUI();
}

function tickActingBar() {
  const bar = document.getElementById("action-cooldown");
  const fill = document.getElementById("action-cooldown-fill");
  const left = actionBusyUntil - Date.now();
  const busy = left > 0 || isActing();
  if (bar) bar.classList.toggle("visible", busy);
  if (fill) {
    const total = Math.max(1, actionBusyUntil - actionBusyFrom);
    const pct = left > 0 ? Math.max(0, Math.min(100, (left / total) * 100)) : 0;
    fill.style.width = pct + "%";
  }
  document.body.classList.toggle("acting", busy);
  if (busy) {
    actionTickRaf = requestAnimationFrame(tickActingBar);
  } else {
    actionTickRaf = 0;
    if (typeof updateCombatUI === "function" && combatState) updateCombatUI();
  }
}

function waitWhileActing() {
  return new Promise((resolve) => {
    const tick = () => {
      if (!isActing()) resolve();
      else setTimeout(tick, 40);
    };
    tick();
  });
}

function throwDice(opts) {
  return window.SanctuaryDice ? SanctuaryDice.present(opts) : opts.resolve();
}

function monsterInAttackReach(m) {
  if (!m || !m.alive || !playerCharacter) return false;
  const d = distance(playerPos, m);
  if (d === 1 && typeof findEquippedMeleeWeapon === "function" && findEquippedMeleeWeapon()) return true;
  const bow = typeof findEquippedRangedWeapon === "function" ? findEquippedRangedWeapon() : null;
  if (bow && d > 0 && d <= Math.floor(bow.range / 10) && hasRangedLineOfSight(playerPos, m)) return true;
  return false;
}

function declareAttack() {
  if (typeof isActing === "function" && isActing()) return;
  if (!combatState || combatState.phase !== "player") {
    log("Wait for your throw.");
    return;
  }
  if (combatState.attacked) {
    log("You have already attacked this round.");
    return;
  }
  attackFocus = true;
  const card = document.getElementById("thac0-card");
  if (card) card.classList.add("ready");
  log(`${playerCharacter.name} readies an attack. Click a foe in reach.`);
  if (typeof requestDraw === "function") requestDraw();
}

function clearAttackFocus() {
  attackFocus = false;
  const card = document.getElementById("thac0-card");
  if (card) card.classList.remove("ready");
}

function setPlayerActed(attacked = false) {
  if (!combatState) return;
  combatState.acted = true;
  if (attacked) combatState.attacked = true;
  if (typeof tutorialManager !== "undefined" && tutorialManager) {
    tutorialManager.markActed();
  }
}

function tilesPerRound(movementFt) {
  return Math.floor(movementFt / 10);
}

function rollDie(sides) {
  return Math.floor(Math.random() * sides) + 1;
}

function playerAlive() {
  const threshold = combatConfig().death_threshold ?? -10;
  return playerCharacter && playerCharacter.sheet && playerCharacter.sheet.hit_points > threshold;
}

function playerConscious() {
  const threshold = combatConfig().unconscious_threshold ?? 0;
  return playerCharacter && playerCharacter.sheet && playerCharacter.sheet.hit_points > threshold;
}

function anyPartyAlive() {
  const threshold = combatConfig().death_threshold ?? -10;
  return party.some(c => c.sheet && c.sheet.hit_points > threshold);
}

function anyPartyConscious() {
  const threshold = combatConfig().unconscious_threshold ?? 0;
  return party.some(c => c.sheet && c.sheet.hit_points > threshold);
}

function formatCoins(cp) {
  if (cp >= 100) return `${Math.floor(cp / 100)} gp`;
  if (cp >= 10) return `${Math.floor(cp / 10)} sp`;
  return `${cp} cp`;
}

function combatConfig() {
  return osricRules?.combat || {};
}

function isCombatSafe() {
  return monsters.every(m => !m.alive || m.fled);
}

function playerDying() {
  return playerCharacter && playerCharacter.sheet && playerCharacter.sheet.hit_points <= 0 && playerAlive();
}

function healPlayer(amount) {
  const s = playerCharacter.sheet;
  const before = s.hit_points;
  s.hit_points = Math.min(s.max_hit_points, s.hit_points + amount);
  const healed = s.hit_points - before;
  if (healed > 0) {
    showFloatingText(playerPos.x, playerPos.y, `+${healed}`, 0x5ac989);
    log(`${playerCharacter.name} heals <span class="hit">${healed}</span> HP.`);
  }
  renderCharacterPanel();
  return healed;
}

function healingPotionEntry(requireIdentified = true) {
  return playerCharacter.sheet.inventory.items.find(i => {
    const item = osricOptions.equipment.find(e => e.id === i.item_id);
    if (item?.use_action !== "heal" || (i.quantity || 1) <= 0) return false;
    return !requireIdentified || identifiedConsumables.has(i.item_id);
  });
}

function potionEntry() {
  return healingPotionEntry(true);
}

function anyPotionEntry() {
  return playerCharacter.sheet.inventory.items.find(i => {
    const item = osricOptions.equipment.find(e => e.id === i.item_id);
    return (item?.use_action === "heal" || item?.use_action === "poison") && (i.quantity || 1) > 0;
  });
}

function hasPotion() {
  return !!potionEntry();
}

function hasKey() {
  return playerCharacter.sheet.inventory.items.some(i => i.item_id === "iron_key" && (i.quantity || 1) > 0);
}

function consumeKey() {
  const entry = playerCharacter.sheet.inventory.items.find(i => i.item_id === "iron_key" && (i.quantity || 1) > 0);
  if (!entry) return false;
  entry.quantity = (entry.quantity || 1) - 1;
  if (entry.quantity <= 0) {
    const idx = playerCharacter.sheet.inventory.items.indexOf(entry);
    if (idx >= 0) playerCharacter.sheet.inventory.items.splice(idx, 1);
  }
  renderCharacterPanel();
  return true;
}

async function usePotion() {
  const entry = potionEntry();
  if (!entry) {
    log("No identified healing potion available.");
    return 0;
  }
  const item = osricOptions.equipment.find(e => e.id === entry.item_id);
  const amount = rollDamageExpression(item?.heal || "1d8");
  const healed = healPlayer(amount);
  if (window.SanctuaryAudio) window.SanctuaryAudio.play("heal");
  entry.quantity = (entry.quantity || 1) - 1;
  if (entry.quantity <= 0) {
    const idx = playerCharacter.sheet.inventory.items.indexOf(entry);
    if (idx >= 0) playerCharacter.sheet.inventory.items.splice(idx, 1);
  }
  log(`${playerCharacter.name} quaffs a <b>${potionDisplayName(entry.item_id)}</b>.`);
  renderCharacterPanel();
  renderConsumablesButton();
  saveGame();
  return healed;
}

async function drinkPotionById(itemId) {
  const entry = playerCharacter.sheet.inventory.items.find(i => i.item_id === itemId && (i.quantity || 1) > 0);
  if (!entry) return 0;
  const item = osricOptions.equipment.find(e => e.id === itemId);
  const wasIdentified = identifiedConsumables.has(itemId);
  identifyConsumable(itemId);
  entry.quantity = (entry.quantity || 1) - 1;
  if (entry.quantity <= 0) {
    const idx = playerCharacter.sheet.inventory.items.indexOf(entry);
    if (idx >= 0) playerCharacter.sheet.inventory.items.splice(idx, 1);
  }
  if (item?.use_action === "heal") {
    const amount = rollDamageExpression(item.heal || "1d8");
    const healed = healPlayer(amount);
    if (window.SanctuaryAudio) window.SanctuaryAudio.play("heal");
    log(`${playerCharacter.name} quaffs a <b>${potionDisplayName(itemId)}</b>. It is ${item.name}! Healed <span class="hit">${healed}</span> HP.`);
  } else if (item?.use_action === "poison") {
    const amount = rollDamageExpression(item.poison || "1d6");
    playerCharacter.sheet.hit_points -= amount;
    showFloatingText(playerPos.x, playerPos.y, `-${amount}`, 0xff6b6b);
    log(`${playerCharacter.name} quaffs a <b>${potionDisplayName(itemId)}</b>. It is ${item.name}! Takes <span class="damage">${amount}</span> damage.`);
    if (!playerAlive() && !anyPartyAlive()) {
      showEnd(false, "Your party has fallen.");
      return -amount;
    }
    if (!playerConscious()) {
      handlePlayerDown("Your hero is unconscious and overcome.");
      return -amount;
    }
  } else {
    log(`${playerCharacter.name} quaffs a <b>${potionDisplayName(itemId)}</b>. Nothing happens.`);
  }
  if (!wasIdentified) {
    log(`You now recognize ${consumableIdentities[itemId] || "this"} as <b>${item?.name || itemId}</b>.`, "hit");
  }
  renderCharacterPanel();
  renderConsumablesButton();
  saveGame();
  return 0;
}

async function useScroll(itemId) {
  const entry = playerCharacter.sheet.inventory.items.find(i => i.item_id === itemId && (i.quantity || 1) > 0);
  if (!entry) return;
  const item = osricOptions.equipment.find(e => e.id === itemId);
  const wasIdentified = identifiedConsumables.has(itemId);
  identifyConsumable(itemId);
  entry.quantity = (entry.quantity || 1) - 1;
  if (entry.quantity <= 0) {
    const idx = playerCharacter.sheet.inventory.items.indexOf(entry);
    if (idx >= 0) playerCharacter.sheet.inventory.items.splice(idx, 1);
  }
  const effect = item?.scroll;
  if (effect === "identify") {
    const unknown = CONSUMABLE_TYPES.filter(id => !identifiedConsumables.has(id));
    if (unknown.length) {
      const target = unknown[Math.floor(Math.random() * unknown.length)];
      identifyConsumable(target);
      const targetItem = osricOptions.equipment.find(e => e.id === target);
      log(`${playerCharacter.name} reads a <b>${consumableDisplayName(itemId)}</b>. It is a Scroll of Identify! You now recognize <b>${targetItem?.name || target}</b>.`, "hit");
    } else {
      log(`${playerCharacter.name} reads a <b>${consumableDisplayName(itemId)}</b>. It is a Scroll of Identify, but nothing remains unknown.`, "hit");
    }
  } else if (effect === "mapping") {
    for (let y = 0; y < MAP_H; y++) {
      for (let x = 0; x < MAP_W; x++) {
        explored.add(`${x},${y}`);
      }
    }
    renderFog();
    log(`${playerCharacter.name} reads a <b>${consumableDisplayName(itemId)}</b>. It is a Scroll of Mapping! The dungeon layout is revealed.`, "hit");
  } else if (effect === "teleport") {
    const tiles = [];
    for (let y = 0; y < MAP_H; y++) {
      for (let x = 0; x < MAP_W; x++) {
        if (isWalkable(x, y) && !(x === playerPos.x && y === playerPos.y)) tiles.push({ x, y });
      }
    }
    if (tiles.length) {
      const dest = tiles[Math.floor(Math.random() * tiles.length)];
      movePlayer(dest.x, dest.y);
      log(`${playerCharacter.name} reads a <b>${consumableDisplayName(itemId)}</b>. It is a Scroll of Teleport! Reality lurches.`, "hit");
    }
  } else {
    log(`${playerCharacter.name} reads a <b>${consumableDisplayName(itemId)}</b>. Nothing happens.`);
  }
  if (!wasIdentified) {
    log(`You now recognize ${consumableIdentities[itemId] || "this"} as <b>${item?.name || itemId}</b>.`, "hit");
  }
  renderCharacterPanel();
  renderConsumablesButton();
  saveGame();
}

function restBlockedByEnemy() {
  return monsters.some((m) => m.alive && !m.fled && distance(m, playerPos) === 1);
}

function notePlayerWounded() {
  if (typeof tutorialManager !== "undefined" && tutorialManager && tutorialManager.onWounded) {
    tutorialManager.onWounded();
  }
}

function showDelveBanner(title, text) {
  let el = document.getElementById("delve-banner");
  if (!el) {
    el = document.createElement("div");
    el.id = "delve-banner";
    el.className = "delve-banner";
    const strong = document.createElement("strong");
    const span = document.createElement("span");
    el.appendChild(strong);
    el.appendChild(span);
    const frame = document.querySelector(".map-frame");
    (frame || document.body).appendChild(el);
  }
  const strong = el.querySelector("strong");
  const span = el.querySelector("span");
  if (strong) strong.textContent = title;
  if (span) span.textContent = text;
  el.classList.add("visible");
  clearTimeout(showDelveBanner._t);
  showDelveBanner._t = setTimeout(() => el.classList.remove("visible"), 7000);
}

function canRest() {
  const cfg = combatConfig().rest;
  if (!combatState) return false;
  if (cfg?.require_safe_area && !isCombatSafe()) {
    // On level 1, rest is allowed as long as no enemy is adjacent, so a new
    // player can recover between fights without the dungeon feeling unfair.
    if (dungeonLevel !== 1) return false;
    if (restBlockedByEnemy()) return false;
  }
  if (!playerAlive()) return false;
  if (isStuck(playerCharacter)) return false;
  if (!playerConscious() && (!cfg?.require_safe_area || !isCombatSafe())) return false;
  return combatState.phase === "player";
}

async function playerRest() {
  if (!canRest()) {
    log("It is not safe to rest here.");
    return;
  }
  if (isActing()) return;
  beginActing();
  const wanderCfg = combatConfig().wandering_monsters;
  // Wandering monsters do not interrupt rest on level 1 so the tutorial band
  // remains forgiving while new players learn the rest/heal loop.
  if (wanderCfg?.enabled && wanderCfg?.check_on_rest && dungeonLevel !== 1) {
    if (wanderingMonsterCheck(wanderCfg)) {
      const spawned = spawnWanderingMonster(wanderingMonsterCount(wanderCfg));
      if (spawned) {
        log(`<span class="damage">Wandering monsters find the party while resting!</span>`, "damage");
        updateCombatUI();
        saveGame();
        return;
      }
    }
  }

  const cfg = combatConfig().rest;
  const level = playerCharacter.sheet.level || 1;
  const perLevel = cfg?.short_rest_heal_per_level ?? 1;

  // Wake an unconscious but stable hero if the area is safe.
  if (!playerConscious() && playerAlive()) {
    playerCharacter.sheet.hit_points = 1;
    log(`<span class="hit">${playerCharacter.name} wakes with 1 HP.</span>`, "hit");
  }

  const amount = perLevel * level;
  const healed = healPlayer(amount);
  if (window.SanctuaryAudio) window.SanctuaryAudio.play("rest");

  if (cfg?.consumes_action) {
    setPlayerActed(true);
  }
  log(`${playerCharacter.name} rests and recovers <span class="hit">${healed}</span> HP.`);
  updateCombatUI();
  saveGame();
  if (cfg?.consumes_action) {
    endTurn();
  }
}

async function doDeathSave() {
  const cfg = combatConfig().death_saves;
  if (!cfg || !cfg.enabled) {
    showEnd(false, "Your party has fallen.");
    return;
  }
  if (!playerDying()) return;
  const saveKey = cfg.target || "death_poison_save";
  let target = 15;
  if (saveKey === "death_poison_save") {
    target = playerCharacter.sheet.saving_throws?.death_paralysis_poison ?? 15;
  } else if (typeof saveKey === "number") {
    target = saveKey;
  }
  const roll = rollDie(20);
  const success = roll >= target;
  if (success) {
    const stabilizeAt = cfg.success_stabilize_at ?? 0;
    playerCharacter.sheet.hit_points = Math.max(playerCharacter.sheet.hit_points, stabilizeAt);
    log(`Death save <span class="roll">${roll}</span> vs ${target}: <span class="hit">stabilised</span> at ${playerCharacter.sheet.hit_points} HP.`, "hit");
    showFloatingText(playerPos.x, playerPos.y, "STABLE", 0x5ac989);
  } else {
    const loss = cfg.failure_hp_loss ?? 1;
    playerCharacter.sheet.hit_points -= loss;
    log(`Death save <span class="roll">${roll}</span> vs ${target}: <span class="miss">failed</span>. Lose ${loss} HP.`, "miss");
    showFloatingText(playerPos.x, playerPos.y, `-${loss}`, 0xff6b6b);
  }
  renderCharacterPanel();
  if (!playerAlive()) {
    if (!anyPartyAlive()) {
      showEnd(false, "Your party has bled out.");
      return;
    }
    ensureConsciousActive();
  } else if (isCombatSafe() && !playerConscious()) {
    // With no immediate threats, rest wakes the character.
    await playerRest();
  }
  saveGame();
}

function handlePlayerDown(source) {
  if (!anyPartyAlive()) {
    showEnd(false, source || "Your party has fallen.");
    return;
  }
  if (playerDying()) {
    log(`<span class="damage">${playerCharacter.name} falls unconscious!</span>`, "damage");
    showFloatingText(playerPos.x, playerPos.y, "UNCONSCIOUS", 0xff6b6b);
    ensureConsciousActive();
    renderCharacterPanel();
    updateCombatUI();
    saveGame();
  }
}

function renderConsumablesButton() {
  const bar = document.getElementById("consumables-bar");
  if (!bar) return;
  bar.innerHTML = "";
  if (!combatState || !playerConscious()) return;
  if (!hasPotion()) return;
  const btn = document.createElement("button");
  btn.id = "use-potion-btn";
  btn.className = "btn btn-secondary";
  btn.textContent = "Use Potion";
  btn.title = "Drink a potion of healing.";
  btn.disabled = combatState.phase !== "player";
  btn.addEventListener("click", usePotion);
  bar.appendChild(btn);
}

function renderRestButton() {
  const bar = document.getElementById("rest-bar");
  if (!bar) return;
  bar.innerHTML = "";
  if (!combatState || !playerAlive()) return;
  const cfg = combatConfig().rest;
  const amount = (cfg?.short_rest_heal_per_level ?? 1) * (playerCharacter.sheet.level || 1);
  const adjacent = restBlockedByEnemy();
  const allowed = canRest() && !isActing();
  const btn = document.createElement("button");
  btn.id = "rest-btn";
  btn.className = "btn btn-secondary";
  btn.textContent = adjacent ? "Rest (not safe)" : (playerConscious() ? `Rest (+${amount})` : "Bind Wounds");
  btn.title = adjacent
    ? "Not safe — enemy adjacent"
    : (playerConscious() ? "Take a short rest to recover HP." : "Rest until you can stand.");
  btn.disabled = !allowed;
  btn.addEventListener("click", playerRest);
  bar.appendChild(btn);
}



function initCombat() {
  initDungeon();
  if (typeof initTutorial === "function") initTutorial();
  document.getElementById("end-turn-btn").addEventListener("click", endTurn);
  playerStealthed = false;
  pendingTrapSearch = false;
  renderSpellBar();
  renderTurnUndeadButton();
  renderThiefBar();
  activePartyIndex = 0;
  playerCharacter = activeCharacter();
  combatState = {
    phase: "player",
    round: 1,
    playerInitiative: 0,
    enemyInitiative: 0,
    movementRemaining: tilesPerRound(playerCharacter.sheet.movement),
    acted: false,
    attacked: false,
    playerActedThisRound: false,
    enemyActedThisRound: false,
    partyActed: new Set(),
    monsterCountAtStart: monsters.filter(m => m.alive).length,
    groupMoraleChecked: false,
  };
  renderRestButton();
  renderConsumablesButton();
  resolveSurpriseAtStart();
}

function renderSpellBar() {
  const bar = document.getElementById("spell-bar");
  if (!bar) return;
  bar.innerHTML = "";
  const spells = (osricOptions.spells && osricOptions.spells[playerCharacter.class]) || [];
  const slots = playerCharacter.sheet.spell_slots || {};
  for (const spell of spells) {
    const remaining = slots[spell.level] || slots[String(spell.level)] || 0;
    const btn = document.createElement("button");
    btn.id = `spell-btn-${spell.id}`;
    btn.className = "btn btn-secondary";
    btn.textContent = `${spell.name} (${remaining})`;
    btn.disabled = remaining <= 0;
    btn.addEventListener("click", () => selectSpell(spell));
    bar.appendChild(btn);
  }
}

function renderTurnUndeadButton() {
  const bar = document.getElementById("turn-undead-bar");
  if (!bar) return;
  bar.innerHTML = "";
  const table = playerCharacter.sheet.turn_undead;
  if (!table || !Object.keys(table).length) return;
  const btn = document.createElement("button");
  btn.id = "turn-undead-btn";
  btn.className = "btn btn-secondary";
  btn.textContent = "Turn Undead";
  btn.title = "Attempt to turn visible undead.";
  btn.disabled = combatState && combatState.phase !== "player";
  btn.addEventListener("click", playerTurnUndead);
  bar.appendChild(btn);
}

const UNDEAD_TYPES = ["Skeleton", "Zombie", "Ghoul", "Shadow", "Wight", "Wraith", "Mummy", "Spectre", "Vampire", "Ghost", "Lich"];

function isUndead(monster) {
  return UNDEAD_TYPES.some(type => monster.name.toLowerCase().includes(type.toLowerCase()));
}

function clericLevelForTurnUndead() {
  return playerCharacter?.sheet?.level || 1;
}

async function playerTurnUndead() {
  if (!combatState || combatState.phase !== "player") return;
  if (combatState.attacked) {
    log("You have already acted this round.");
    return;
  }
  if (isStuck(playerCharacter)) {
    log("You are stuck in a pit and cannot turn undead.");
    return;
  }
  const table = playerCharacter.sheet.turn_undead;
  if (!table) return;

  const visible = computeVisibility();
  const targets = monsters.filter(m => {
    if (!m.alive || !isUndead(m)) return false;
    return visible.has(`${m.x},${m.y}`);
  });

  if (!targets.length) {
    log("No visible undead to turn.");
    return;
  }

  setPlayerActed(true);
  let anyTurned = false;

  for (const m of targets) {
    const key = Object.keys(table).find(k => m.name.toLowerCase().includes(k.replace(/_/g, " ")));
    if (!key) continue;
    const target = table[key];
    const roll = rollDie(20);
    const success = roll >= target;
    log(`${playerCharacter.name} turns toward <b>${m.name}</b>: roll <span class="roll">${roll}</span> vs ${target} — ${success ? '<span class="hit">turned</span>' : '<span class="miss">resists</span>'}.`);
    if (success) {
      anyTurned = true;
      const clericLevel = clericLevelForTurnUndead();
      const destroy = roll === 20 || clericLevel > (m.hd || 1) + 3;
      if (destroy) {
        showFloatingText(m.x, m.y, "DESTROYED", 0xd4a03d);
        log(`<b>${m.name}</b> is destroyed by the power of ${playerCharacter.name}'s faith!`, "hit");
        killMonster(m);
      } else {
        m.turned = rollDamageExpression("2d4");
        showFloatingText(m.x, m.y, "TURNED", 0xd4a03d);
        log(`<b>${m.name}</b> flees in terror for <span class="hit">${m.turned}</span> rounds.`, "hit");
      }
    }
  }

  if (anyTurned) {
    log("<span class='hit'>The undead cower and flee.</span>", "hit");
  }
  drawTokens();
  renderCharacterPanel();
  updateCombatUI();
  checkEnd();
  saveGame();
}

let playerStealthed = false;
let pendingTrapSearch = false;

function getThiefSkills() {
  return osricRules?.class_features?.thief_skills || {};
}

function isThief() {
  return playerCharacter.class === "thief";
}

function renderThiefBar() {
  const bar = document.getElementById("thief-bar");
  if (!bar) return;
  bar.innerHTML = "";
  if (!isThief()) return;
  const skills = getThiefSkills();

  const sneakBtn = document.createElement("button");
  sneakBtn.id = "sneak-btn";
  sneakBtn.className = "btn btn-secondary";
  sneakBtn.textContent = playerStealthed ? "Hidden" : `Sneak (${skills.move_silently}%)`;
  sneakBtn.title = "Roll Move Silently / Hide in Shadows to become hidden.";
  sneakBtn.disabled = (combatState && combatState.phase !== "player") || playerStealthed || isStuck(playerCharacter);
  sneakBtn.addEventListener("click", playerSneak);
  bar.appendChild(sneakBtn);

  const trapBtn = document.createElement("button");
  trapBtn.id = "search-traps-btn";
  trapBtn.className = "btn btn-secondary";
  trapBtn.textContent = `Find Traps (${skills.find_remove_traps}%)`;
  trapBtn.title = "Search adjacent tiles for traps.";
  trapBtn.disabled = (combatState && combatState.phase !== "player") || isStuck(playerCharacter);
  trapBtn.addEventListener("click", () => {
    pendingTrapSearch = true;
    log("Click an adjacent tile to search for traps.");
    updateCombatUI();
  });
  bar.appendChild(trapBtn);
}

function rollPercentile() {
  return rollDie(100);
}

async function playerSneak() {
  if (!combatState || combatState.phase !== "player") return;
  if (combatState.attacked) {
    log("You have already acted this round.");
    return;
  }
  if (isStuck(playerCharacter)) {
    log("You are stuck in a pit and cannot sneak.");
    return;
  }
  const skills = getThiefSkills();
  const roll = rollPercentile();
  const success = roll <= skills.move_silently;
  log(`Sneak: Move Silently <span class="roll">${roll}</span>/${skills.move_silently}.`);
  if (success) {
    playerStealthed = true;
    log("<span class='hit'>You melt into the shadows.</span>", "hit");
    showFloatingText(playerPos.x, playerPos.y, "HIDDEN", 0x5ac989);
  } else {
    log("<span class='miss'>You fail to hide.</span>", "miss");
  }
  setPlayerActed();
  updateCombatUI();
}

function secretDoorSearchChance(character) {
  // OSRIC-style: 1-in-6 for most, 2-in-6 for elves and dwarves.
  const ancestry = character?.ancestry;
  if (ancestry === "elf" || ancestry === "dwarf") return 2;
  return 1;
}

function searchSecretDoors() {
  if (!combatState || combatState.phase !== "player") return;
  if (combatState.acted) {
    log("You have already acted this round.");
    return;
  }
  if (isStuck(playerCharacter)) {
    log("You are stuck in a pit and cannot search.");
    return;
  }
  let found = false;
  const chance = secretDoorSearchChance(playerCharacter);
  for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
    const nx = playerPos.x + dx, ny = playerPos.y + dy;
    if (nx < 0 || nx >= MAP_W || ny < 0 || ny >= MAP_H) continue;
    if (mapData[ny][nx] === TILE.SECRET_DOOR) {
      const roll = rollDie(6);
      if (roll <= chance) {
        mapData[ny][nx] = TILE.DOOR;
        doorsOpened.add(`${nx},${ny}`);
        log(`<span class='hit'>${playerCharacter.name} discovers a secret door!</span> Roll ${roll}/${chance}.`, "hit");
        drawMap();
        renderFog();
        found = true;
      } else {
        log(`${playerCharacter.name} searches the wall but finds nothing. Roll ${roll}/${chance}.`);
      }
    }
  }
  if (!found) {
    log(`${playerCharacter.name} searches the nearby walls. Nothing hidden is found.`);
  }
  setPlayerActed();
  updateCombatUI();
  saveGame();
}

function renderSearchSecretDoorsButton() {
  const bar = document.getElementById("secret-door-bar");
  if (!bar) return;
  bar.innerHTML = "";
  if (!combatState) return;
  if (!playerConscious()) return;
  const btn = document.createElement("button");
  btn.id = "search-secret-doors-btn";
  btn.className = "btn btn-secondary";
  btn.textContent = "Search Walls";
  btn.title = "Search adjacent walls for secret doors.";
  btn.disabled = combatState.phase !== "player" || combatState.acted || isStuck(playerCharacter);
  btn.addEventListener("click", searchSecretDoors);
  bar.appendChild(btn);
}

function clearStealth() {
  if (playerStealthed) {
    playerStealthed = false;
    log("Your position is revealed!");
  }
}

function searchTrapsAt(x, y) {
  const skills = getThiefSkills();
  const roll = rollPercentile();
  const found = roll <= skills.find_remove_traps;
  const key = `${x},${y}`;
  if (mapData[y] && mapData[y][x] === TILE.TRAP && !trapsTriggered.has(key)) {
    if (found) {
      trapsDiscovered.add(key);
      log(`<span class='hit'>Trap found at (${x}, ${y})!</span> Roll ${roll}/${skills.find_remove_traps}.`, "hit");
      drawMap();
    } else {
      log(`No trap found at (${x}, ${y}). Roll ${roll}/${skills.find_remove_traps}.`);
    }
  } else {
    log(`No trap at (${x}, ${y}).`);
  }
  pendingTrapSearch = false;
  setPlayerActed();
  updateCombatUI();
}

function removeTrapAt(x, y) {
  const skills = getThiefSkills();
  const roll = rollPercentile();
  const removed = roll <= skills.find_remove_traps;
  const key = `${x},${y}`;
  if (removed) {
    trapsTriggered.add(key);
    log(`<span class='hit'>Trap disarmed at (${x}, ${y})!</span> Roll ${roll}/${skills.find_remove_traps}.`, "hit");
  } else {
    log(`<span class='damage'>Trap disarm failed at (${x}, ${y}).</span> Roll ${roll}/${skills.find_remove_traps}.`);
    triggerTrap(x, y);
  }
  pendingTrapSearch = false;
  drawMap();
  updateCombatUI();
}

async function selectSpell(spell) {
  if (!combatState || combatState.phase !== "player") return;
  if (combatState.attacked) {
    log("You have already acted this round.");
    return;
  }
  // Healing spells target the caster automatically; buff spells target the caster and persist.
  if (spell.heal || spell.buff) {
    await playerCastSpell(spell, null);
    setPlayerActed(true);
    renderSpellBar();
    updateCombatUI();
    checkEnd();
    saveGame();
    return;
  }
  pendingSpell = spell;
  log(`Select a target for <b>${spell.name}</b>.`);
  updateCombatUI();
  highlightRangedTargets();
}

function clearPendingSpell() {
  pendingSpell = null;
  updateCombatUI();
}

function dexInitiativeMod() {
  const mods = playerCharacter.sheet.ability_modifiers;
  const dex = mods?.dexterity?.missile_to_hit || 0;
  return dex;
}

function equippedWeaponSpeed() {
  // Use the speed of the currently relevant equipped weapon.
  const ranged = findEquippedRangedWeapon();
  if (ranged && hasAmmoForRangedAttack()) return ranged.weapon_speed || 5;
  const melee = findEquippedMeleeWeapon();
  if (melee) return melee.weapon_speed || 5;
  return 0;
}

function castingTimeModifier() {
  // Casting time (in segments/rounds) slows the caster's initiative.
  return pendingSpell?.casting_time || 0;
}

function rollInitiative() {
  const active = activeCharacter();
  // OSRIC-style initiative formula used here:
  //   d6 + DEX missile reaction mod + weapon speed + casting time.
  // Higher roll wins initiative in this implementation.
  const dexMod = dexInitiativeMod();
  const weaponSpeed = equippedWeaponSpeed();
  const castMod = castingTimeModifier();
  const playerMod = dexMod + weaponSpeed + castMod;
  combatState.playerInitiative = rollDie(6) + playerMod;
  combatState.enemyInitiative = rollDie(6);
  const wentFirst = combatState.playerInitiative >= combatState.enemyInitiative ? "You" : "Enemies";
  log(`${wentFirst} win initiative (player ${combatState.playerInitiative} = d6${dexMod ? ` +${dexMod} DEX` : ""}${weaponSpeed ? ` +${weaponSpeed} weapon` : ""}${castMod ? ` +${castMod} casting` : ""}, enemy ${combatState.enemyInitiative}).`);
  combatState.phase = combatState.playerInitiative >= combatState.enemyInitiative ? "player" : "enemy";
  combatState.movementRemaining = tilesPerRound(active.sheet.movement);
  combatState.acted = false;
  combatState.attacked = false;
  combatState.playerActedThisRound = false;
  combatState.enemyActedThisRound = false;
  pendingSpell = null;
  pendingTrapSearch = false;
}

function surpriseModifierForParty() {
  // Elves and dwarves are unusually alert underground.
  let mod = 0;
  for (const c of party) {
    if (c.ancestry === "elf" || c.ancestry === "dwarf") {
      mod = Math.max(mod, 1);
    }
  }
  return mod;
}

function rollSurprise() {
  const cfg = osricRules?.combat?.surprise || { chance_in_6: 2 };
  const base = cfg.chance_in_6 || 2;
  const alertMod = surpriseModifierForParty();
  // Alert ancestries are harder to surprise and more likely to surprise foes.
  const playerThreshold = Math.max(1, base - alertMod);
  const enemyThreshold = Math.min(5, base + alertMod);
  const playerSurprised = rollDie(6) <= playerThreshold;
  const enemySurprised = rollDie(6) <= enemyThreshold;
  return { playerSurprised, enemySurprised };
}

async function resolveSurpriseAtStart() {
  const { playerSurprised, enemySurprised } = rollSurprise();
  if (!playerSurprised && enemySurprised) {
    log("<span class='hit'>You surprise the enemy!</span>", "hit");
    await playerSurpriseRound();
    return;
  }
  if (playerSurprised && !enemySurprised) {
    log("<span class='damage'>The enemy surprises you!</span>", "damage");
    await enemySurpriseRound();
    return;
  }
  log("Both sides are wary.");
  startRound();
}

async function playerSurpriseRound() {
  // Player gets a free action round before normal initiative begins.
  combatState.phase = "player";
  combatState.partyActed = new Set();
  if (!playerConscious()) ensureConsciousActive();
  combatState.movementRemaining = tilesPerRound(playerCharacter.sheet.movement);
  combatState.acted = false;
  combatState.attacked = false;
  updateCombatUI();
  highlightReachable(playerPos, combatState.movementRemaining);
  highlightRangedTargets();
  maybeAutoMercTurn();
  // Wait for the player to act and end turn, then begin round 1.
}

async function enemySurpriseRound() {
  // Enemies get a free round; mark them so they don't get another when normal combat starts.
  await enemyTurn();
  combatState.enemyActedThisRound = true;
}

async function startRound() {
  combatState.partyActed = new Set();
  if (typeof tutorialManager !== "undefined" && tutorialManager) {
    tutorialManager.resetTurn();
  }
  decrementPartyActiveSpells();
  if (!playerConscious()) {
    ensureConsciousActive();
  }
  rollInitiative();
  updateCombatUI();
  if (combatState.phase === "player" && !playerConscious()) {
    await doDeathSave();
    if (!anyPartyAlive()) return;
    if (!playerConscious()) {
      // Unconscious hero cannot act this round; pass to the enemy phase.
      combatState.phase = "enemy";
      updateCombatUI();
      setTimeout(enemyTurn, 800);
      return;
    }
  }
  if (combatState.phase === "player") {
    highlightReachable(playerPos, combatState.movementRemaining);
    highlightRangedTargets();
    maybeAutoMercTurn();
  } else {
    setTimeout(enemyTurn, 800);
  }
}

function updateCombatUI() {
  const name = playerCharacter ? playerCharacter.name : "Party";
  const feet = (combatState.movementRemaining || 0) * 10;
  let turnText = combatState.phase === "player"
    ? `Round ${combatState.round} — ${name} · ${feet} ft left`
    : `Round ${combatState.round} — Enemy throw`;
  const turned = monsters.filter(m => m.alive && m.turned > 0);
  if (turned.length) {
    turnText += ` · ${turned.length} turned`;
  }
  const turnBadge = document.getElementById("turn-badge");
  turnBadge.textContent = turnText;
  turnBadge.classList.toggle("player-turn", combatState.phase === "player");
  turnBadge.classList.toggle("enemy-turn", combatState.phase !== "player");
  const strip = document.getElementById("initiative-strip");
  if (strip) {
    const you = playerCharacter ? playerCharacter.name : "You";
    const names = [];
    const seen = new Set();
    const add = (n) => { if (n && !seen.has(n)) { seen.add(n); names.push(n); } };
    add(you);
    for (const m of monsters) {
      if (!m.alive) continue;
      if (typeof isVisibleToPlayer === "function" && !isVisibleToPlayer(m.x, m.y)) continue;
      add(m.name);
    }
    const up = combatState.phase === "player" ? you : (names[1] || "Enemy");
    strip.innerHTML = names.map((n) => `<span class="init-name${n === up ? " current" : ""}">${n}</span>`).join("");
  }
  document.getElementById("end-turn-btn").disabled = combatState.phase !== "player" || !playerConscious() || isActing();

  const aliveEnemies = monsters.filter(m => m.alive && !m.fled).length;
  const exitOpen = aliveEnemies === 0;
  const objectiveBadge = document.getElementById("objective-badge");
  if (objectiveBadge) {
    objectiveBadge.textContent = exitOpen ? "Exit open" : `${aliveEnemies} enemy${aliveEnemies === 1 ? "" : "ies"} remain`;
    objectiveBadge.classList.toggle("exit-open", exitOpen);
  }

  const actionHint = document.getElementById("action-hint");
  if (actionHint) {
    actionHint.classList.toggle("prominent", combatState.phase === "player" && combatState.round <= 3);
  }

  renderRestButton();
  renderConsumablesButton();

  let hint;
  if (combatState.phase !== "player") {
    hint = "The dungeon stirs…";
  } else if (pendingSpell) {
    hint = `Click a monster to cast ${pendingSpell.name}.`;
  } else if (pendingTrapSearch) {
    hint = "Click an adjacent tile to search for traps.";
  } else if (combatState.attacked) {
    hint = "You have attacked. Move or end your turn.";
  } else {
    const ranged = findEquippedRangedWeapon();
    const ammo = ranged && hasAmmoForRangedAttack();
    let base = ranged
      ? (ammo
        ? "Click a highlighted tile to move, an adjacent monster to melee, or a circled monster to shoot."
        : "Out of ammo. Move or melee with a different weapon.")
      : "Click a highlighted tile to move, or click an adjacent monster to attack (once per round).";
    if (playerStealthed) base += " You are hidden.";
    hint = base;
  }
  document.getElementById("action-hint").textContent = hint;
  renderSpellBar();
  renderTurnUndeadButton();
  renderThiefBar();
  renderSearchSecretDoorsButton();
  renderClimbOutButton();
  renderCombatAutoMercToggle();
  renderAutoExploreButton();
}

function renderAutoExploreButton() {
  const btn = document.getElementById("auto-explore-btn");
  if (!btn) return;
  const enabled = combatState && combatState.phase === "player" && playerConscious() && !isAutoExploring && combatState.movementRemaining > 0 && !isActing();
  btn.disabled = !enabled;
  btn.textContent = isAutoExploring ? "Exploring…" : "Auto-Explore";
}

function stopAutoExplore() {
  isAutoExploring = false;
}

function computeAutoExploreStep() {
  // Find the nearest unexplored tile that is walkable, then return the first
  // step on a safe path toward it. Favor tiles adjacent to explored cells so
  // the frontier expands naturally.
  const frontier = [];
  for (const key of explored) {
    const [x, y] = key.split(",").map(Number);
    for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
      const nx = x + dx, ny = y + dy;
      if (nx < 0 || ny < 0 || nx >= MAP_W || ny >= MAP_H) continue;
      if (explored.has(`${nx},${ny}`)) continue;
      if (!isWalkable(nx, ny)) continue;
      if (monsterAt(nx, ny)) continue;
      frontier.push({ x: nx, y: ny });
    }
  }
  if (!frontier.length) return null;

  // Pick the closest frontier tile; tie-break toward the exit if visible.
  let target = null;
  let bestDist = Infinity;
  for (const t of frontier) {
    const d = distance(playerPos, t);
    if (d < bestDist) {
      bestDist = d;
      target = t;
    }
  }
  if (!target) return null;

  // BFS for a path; closed doors are considered passable because the player
  // will open them when adjacent.
  const queue = [{ x: playerPos.x, y: playerPos.y, path: [] }];
  const seen = new Set([`${playerPos.x},${playerPos.y}`]);
  let head = 0;
  while (head < queue.length) {
    const cur = queue[head++];
    if (cur.x === target.x && cur.y === target.y) {
      return cur.path[0] || null;
    }
    for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
      const nx = cur.x + dx, ny = cur.y + dy;
      const key = `${nx},${ny}`;
      if (seen.has(key)) continue;
      if (nx < 0 || ny < 0 || nx >= MAP_W || ny >= MAP_H) continue;
      const t = mapData[ny][nx];
      if (t === TILE.WALL || t === TILE.SECRET_DOOR) continue;
      // Barrels can be pushed/destroyed when reached.
      if (t === TILE.BARREL && !barrelData.has(`${nx},${ny}`)) continue;
      if (monsterAt(nx, ny)) continue;
      seen.add(key);
      queue.push({ x: nx, y: ny, path: [...cur.path, { x: nx, y: ny }] });
    }
  }
  return null;
}

async function autoExplore() {
  if (!combatState || combatState.phase !== "player" || !playerConscious()) return;
  if (isAutoExploring || isActing()) return;
  isAutoExploring = true;
  updateCombatUI();

  while (isAutoExploring && combatState && combatState.phase === "player" && playerConscious() && combatState.movementRemaining > 0 && !combatState.attacked) {
    // Stop if any monster is currently visible to the player.
    const visibleMonster = monsters.find(m => m.alive && isVisibleToPlayer(m.x, m.y));
    if (visibleMonster) {
      log(`Auto-explore stopped: ${visibleMonster.name} spotted.`);
      break;
    }

    const step = computeAutoExploreStep();
    if (!step) {
      log("Auto-explore stopped: nowhere left to explore.");
      break;
    }

    const oldPos = { ...playerPos };
    await handleGridClick(step.x, step.y);
    await waitWhileActing();

    // If the click did not result in movement (blocked, trap stuck, etc.), stop.
    if (playerPos.x === oldPos.x && playerPos.y === oldPos.y) {
      log("Auto-explore stopped: path blocked.");
      break;
    }
  }

  isAutoExploring = false;
  updateCombatUI();
}

function findEquippedMeleeWeapon() {
  const inv = playerCharacter.sheet.inventory.items;
  for (const entry of inv) {
    if (!entry.equipped) continue;
    const item = osricOptions.equipment.find(i => i.id === entry.item_id);
    if (item && item.category === "weapons" && !item.missile) return item;
  }
  return null;
}

function findEquippedRangedWeapon() {
  const inv = playerCharacter.sheet.inventory.items;
  let best = null;
  for (const entry of inv) {
    if (!entry.equipped) continue;
    const item = osricOptions.equipment.find(i => i.id === entry.item_id);
    if (!item || item.category !== "weapons" || !item.missile) continue;
    // Prefer dedicated missile weapons (bows, slings) over thrown melee weapons
    // like daggers or spears, and prefer longer range among missile weapons.
    if (!best) {
      best = item;
    } else if (item.subcategory === "missile" && best.subcategory !== "missile") {
      best = item;
    } else if (item.subcategory === best.subcategory && (item.range || 0) > (best.range || 0)) {
      best = item;
    }
  }
  return best;
}

function ammoForWeapon(weapon) {
  if (!weapon) return null;
  if (weapon.id.includes("bow") || weapon.id === "arrows") return "arrows";
  if (weapon.id.includes("crossbow")) return "bolts";
  if (weapon.id === "sling") return "sling_bullet";
  return null;
}

function countAmmo(ammoId) {
  const inv = playerCharacter.sheet.inventory.items;
  const entry = inv.find(i => i.item_id === ammoId);
  return entry ? (entry.quantity || 1) : 0;
}

function hasAmmoForRangedAttack() {
  const weapon = findEquippedRangedWeapon();
  if (!weapon) return false;
  const ammoId = ammoForWeapon(weapon);
  if (!ammoId) return true; // self-ammo weapons like darts, javelins when thrown are the weapon itself
  return countAmmo(ammoId) > 0;
}

function consumeAmmo() {
  const weapon = findEquippedRangedWeapon();
  if (!weapon) return false;
  const ammoId = ammoForWeapon(weapon);
  if (!ammoId) return true;
  const inv = playerCharacter.sheet.inventory.items;
  const entry = inv.find(i => i.item_id === ammoId);
  if (!entry || (entry.quantity || 1) <= 0) return false;
  entry.quantity -= 1;
  if (entry.quantity <= 0) {
    const idx = inv.indexOf(entry);
    if (idx >= 0) inv.splice(idx, 1);
  }
  return true;
}

function rangedRangeTiles() {
  const weapon = findEquippedRangedWeapon();
  if (!weapon || !weapon.range) return [];
  const maxTiles = Math.floor(weapon.range / 10);
  const tiles = [];
  for (let y = 0; y < MAP_H; y++) {
    for (let x = 0; x < MAP_W; x++) {
      const d = distance(playerPos, { x, y });
      if (d > 0 && d <= maxTiles && isWalkable(x, y)) tiles.push({ x, y, d });
    }
  }
  return tiles;
}

function highlightRangedTargets() {
  if (!highlightGraphics) return;
  const rangedReady = findEquippedRangedWeapon() && hasAmmoForRangedAttack();
  if (pendingSpell || rangedReady) {
    for (const m of monsters) {
      if (!m.alive) continue;
      const d = distance(playerPos, { x: m.x, y: m.y });
      const inRange = pendingSpell || d <= Math.floor((findEquippedRangedWeapon().range || 0) / 10);
      if (inRange) {
        highlightGraphics.lineStyle(2, pendingSpell ? 0x5a9eff : 0xff6b6b, 0.85);
        highlightGraphics.drawCircle(
          m.x * TILE_SIZE + TILE_SIZE / 2,
          m.y * TILE_SIZE + TILE_SIZE / 2,
          TILE_SIZE * 0.42
        );
      }
    }
  }
}

async function handleGridClick(gx, gy) {
  if (!combatState || combatState.phase !== "player") return;
  if (isActing()) return;
  if (!playerConscious()) {
    log("You are unconscious and cannot act.");
    return;
  }
  if (isStuck(playerCharacter)) {
    log("You are stuck in a pit. Climb out first.");
    return;
  }

  // Open adjacent closed doors.
  const isClosedDoor = mapData[gy] && mapData[gy][gx] === TILE.DOOR && !doorsOpened.has(`${gx},${gy}`);
  const isLockedDoor = mapData[gy] && mapData[gy][gx] === TILE.LOCKED_DOOR && !doorsOpened.has(`${gx},${gy}`);
  if (isClosedDoor || isLockedDoor) {
    if (distance(playerPos, { x: gx, y: gy }) === 1) {
      if (isLockedDoor) {
        if (!hasKey()) {
          const shrineLock = currentModule && (currentModule.locked_doors || []).includes("shrine");
          log(shrineLock
            ? "<b>The shrine is barred.</b> The iron key is in the storeroom chest."
            : "<b>The door is locked.</b> You need an iron key.");
          return;
        }
        consumeKey();
        log(`${playerCharacter.name} unlocks the shrine with the iron key.`);
      } else {
        log(`${playerCharacter.name} opens a door.`);
      }
      doorsOpened.add(`${gx},${gy}`);
      if (window.SanctuaryAudio) window.SanctuaryAudio.play("door_open");
      wakeNearbyMonsters(playerPos.x, playerPos.y, 2, "wake from the noise");
      beginActing();
      drawMap();
      renderFog();
      highlightReachable(playerPos, combatState.movementRemaining);
      saveGame();
    }
    return;
  }

  const targetMonster = monsterAt(gx, gy);

  if (attackFocus && !targetMonster) {
    log("Attack cancelled.");
    clearAttackFocus();
    if (typeof requestDraw === "function") requestDraw();
    return;
  }

  // Adjacent barrel: push if there is room, otherwise smash it.
  const isBarrel = mapData[gy] && mapData[gy][gx] === TILE.BARREL && barrelData.has(`${gx},${gy}`);
  if (isBarrel && distance(playerPos, { x: gx, y: gy }) === 1) {
    const dx = gx - playerPos.x;
    const dy = gy - playerPos.y;
    const pushed = pushBarrel(gx, gy, dx, dy);
    if (pushed) {
      beginActing();
      const cost = movementCost(gx, gy);
      combatState.movementRemaining -= cost;
      setPlayerActed(false);
      updateCombatUI();
      highlightReachable(playerPos, combatState.movementRemaining);
      saveGame();
      return;
    }
    if (combatState.attacked) {
      log("You have already attacked this round.");
      return;
    }
    log(`${playerCharacter.name} smashes the barrel!`);
    beginActing();
    destroyBarrel(gx, gy);
    setPlayerActed(true);
    updateCombatUI();
    saveGame();
    return;
  }

  // Trap search / remove target selection.
  if (pendingTrapSearch) {
    const d = distance(playerPos, { x: gx, y: gy });
    if (d !== 1) {
      log("You must be adjacent to search for traps.");
      pendingTrapSearch = false;
      updateCombatUI();
      return;
    }
    const key = `${gx},${gy}`;
    if (mapData[gy] && mapData[gy][gx] === TILE.TRAP && trapsDiscovered.has(key) && !trapsTriggered.has(key)) {
      removeTrapAt(gx, gy);
    } else {
      searchTrapsAt(gx, gy);
    }
    return;
  }

  // Spell casting target selection.
  if (pendingSpell && targetMonster) {
    beginActing();
    await playerCastSpell(pendingSpell, targetMonster);
    pendingSpell = null;
    setPlayerActed(true); // spells count as the round's attack action
    renderSpellBar();
    updateCombatUI();
    checkEnd();
    return;
  }

  // Adjacent melee attack.
  if (targetMonster && distance(playerPos, { x: gx, y: gy }) === 1) {
    if (combatState.attacked) {
      log("You have already attacked this round.");
      return;
    }
    if (!findEquippedMeleeWeapon() && !findEquippedRangedWeapon()) {
      log("You have no weapon equipped.");
      return;
    }
    const backstab = isThief() && playerStealthed;
    beginActing();
    await playerAttackMonster(targetMonster, false, 0, backstab);
    clearAttackFocus();
    setPlayerActed(true);
    clearStealth();
    updateCombatUI();
    checkEnd();
    return;
  }

  // Ranged attack on a distant monster.
  if (targetMonster && findEquippedRangedWeapon()) {
    if (combatState.attacked) {
      log("You have already attacked this round.");
      return;
    }
    if (!hasAmmoForRangedAttack()) {
      log("<span class='damage'>No ammo left for this weapon.</span>");
      return;
    }
    const d = distance(playerPos, { x: gx, y: gy });
    const maxTiles = Math.floor(findEquippedRangedWeapon().range / 10);
    if (d <= maxTiles) {
      if (!hasRangedLineOfSight(playerPos, { x: gx, y: gy })) {
        log("<span class='damage'>No clear shot.</span> A wall or barrel blocks your line of fire.");
        return;
      }
      if (!consumeAmmo()) {
        log("<span class='damage'>No ammo left for this weapon.</span>");
        return;
      }
      beginActing();
      await playerAttackMonster(targetMonster, true, d * 10);
      clearAttackFocus();
      setPlayerActed(true);
      clearStealth();
      renderCharacterPanel();
      updateCombatUI();
      checkEnd();
      return;
    }
  }

  if (combatState.movementRemaining <= 0) return;
  const reachable = computeReachable(playerPos, combatState.movementRemaining);
  const reached = reachable.find(p => p.x === gx && p.y === gy);
  if (reached) {
    const cost = reached.cost || distance(playerPos, { x: gx, y: gy });
    const path = typeof pathTo === "function" ? pathTo(gx, gy) : [];
    const steps = path.length ? path : [{ x: gx, y: gy }];
    const ms = Math.max(850, steps.length * 400);
    beginActing(ms);
    const stepMs = Math.max(180, Math.floor(ms / steps.length));
    for (const p of steps) {
      movePlayer(p.x, p.y);
      await new Promise((r) => setTimeout(r, stepMs));
    }
    combatState.movementRemaining -= cost;
    log(`${playerCharacter.name} moves ${cost * 10} ft.`);
    if (typeof tutorialManager !== "undefined" && tutorialManager) {
      tutorialManager.markActed();
    }
    if (!isThief()) clearStealth();
    updateCombatUI();
    highlightReachable(playerPos, combatState.movementRemaining);
    highlightRangedTargets();
    await checkTileInteraction(gx, gy);
    maybeSpawnWanderingMonster();
    saveGame();
  }
}

function rollChestLoot(level, type = null) {
  // Consumables spice up chest openings and give low-level parties more
  // resources. Deeper chests are less likely to hold healing potions.
  const roll = Math.random();
  const chance = level === 1 ? 0.5 : Math.max(0.1, 0.5 - (level - 1) * 0.1);
  if (roll >= chance) return null;
  const potionTable = [
    { id: "potion_of_healing", weight: 3 },
    { id: "potion_of_extra_healing", weight: level >= 2 ? 2 : 0 },
    { id: "potion_of_poison", weight: level === 1 ? 1 : 2 },
  ];
  const scrollTable = [
    { id: "scroll_of_identify", weight: level >= 2 ? 2 : 1 },
    { id: "scroll_of_mapping", weight: 1 },
    { id: "scroll_of_teleport", weight: level >= 2 ? 2 : 1 },
  ];
  const table = type === "potion" ? potionTable : type === "scroll" ? scrollTable : [...potionTable, ...scrollTable];
  const available = table.filter(e => e.weight > 0);
  if (!available.length) return null;
  const totalWeight = available.reduce((s, e) => s + e.weight, 0);
  let pick = Math.random() * totalWeight;
  for (const entry of available) {
    pick -= entry.weight;
    if (pick <= 0) return entry.id;
  }
  return available[available.length - 1].id;
}

function addItemToInventory(itemId, quantity = 1) {
  const inv = playerCharacter.sheet.inventory;
  inv.items = inv.items || [];
  const existing = inv.items.find(i => i.item_id === itemId);
  if (existing) {
    existing.quantity = (existing.quantity || 1) + quantity;
  } else {
    inv.items.push({ item_id: itemId, quantity, equipped: false });
  }
}

async function checkTileInteraction(x, y) {
  const t = mapData[y][x];
  if (t === TILE.CHEST && !chestsOpened.has(`${x},${y}`)) {
    openChest(x, y);
    if (typeof tutorialManager !== "undefined" && tutorialManager) {
      tutorialManager.onChestOpened();
    }
    const fixedGp = chestGoldGp.get(`${x},${y}`);
    if (fixedGp != null) {
      playerCharacter.remaining_gold += fixedGp;
      playerCharacter.sheet.xp += fixedGp;
      log(`The chest holds <b>${fixedGp} gp</b> (${fixedGp} XP).`, "hit");
      chestGoldGp.delete(`${x},${y}`);
    } else {
      const chestCfg = combatConfig().chest || {};
      const rolls = rollDamageExpression(chestCfg.gold_die || "1d6");
      const cp = rolls * (chestCfg.gold_cp_per_roll || 100);
      playerCharacter.remaining_gold += cp / 100;
      playerCharacter.sheet.xp += cp;
      log(`The chest holds <b>${formatCoins(cp)}</b> (${cp} XP).`, "hit");
    }
    if (chestsWithKey.has(`${x},${y}`)) {
      addItemToInventory("iron_key", 1);
      log(`Inside you find an <b>iron key</b>!`, "hit");
      chestsWithKey.delete(`${x},${y}`);
    }
    const lootIds = [];
    const potionId = rollChestLoot(dungeonLevel, "potion");
    if (potionId) lootIds.push(potionId);
    const scrollId = rollChestLoot(dungeonLevel, "scroll");
    if (scrollId) lootIds.push(scrollId);
    for (const lootId of lootIds) {
      const item = osricOptions.equipment.find(e => e.id === lootId);
      addItemToInventory(lootId, 1);
      const displayName = typeof consumableDisplayName === "function" ? consumableDisplayName(lootId) : (item?.name || lootId);
      log(`Inside you find a <b>${displayName}</b>!`, "hit");
    }
    if (typeof maybeLevelUp === "function") await maybeLevelUp();
    else if (playerCharacter.sheet.xp >= playerCharacter.sheet.next_level_xp) {
      await levelUpCharacter();
    }
    renderCharacterPanel();
    saveGame();
  } else if (t === TILE.EXIT) {
    if (monsters.every(m => !m.alive || m.fled)) {
      log("<span class='hit'>The exit is open. You may descend or return to town.</span>", "hit");
      showDescendChoice();
    } else {
      const aliveEnemies = monsters.filter(m => m.alive && !m.fled).length;
      log(`<span class='damage'>The exit is warded.</span> ${aliveEnemies} enemy${aliveEnemies === 1 ? "" : "ies"} remain.`);
    }
  } else if (t === TILE.TRAP && !trapsTriggered.has(`${x},${y}`)) {
    await triggerTrap(x, y);
  }
}

function trapDamageForType(typeKey) {
  const def = trapTypes()[typeKey] || trapTypes().spike;
  return rollDamageExpression(def.damage || "1d6");
}

function trapSaveForType(typeKey) {
  const def = trapTypes()[typeKey] || trapTypes().spike;
  const key = def.save;
  if (key && playerCharacter?.sheet?.saving_throws && playerCharacter.sheet.saving_throws[key] !== undefined) {
    return playerCharacter.sheet.saving_throws[key];
  }
  return combatConfig().trap?.save_fallback || 15;
}

function makeSavingThrow(key) {
  if (key && playerCharacter?.sheet?.saving_throws && playerCharacter.sheet.saving_throws[key] !== undefined) {
    return { target: playerCharacter.sheet.saving_throws[key], roll: rollDie(20) };
  }
  return { target: combatConfig().trap?.save_fallback || 15, roll: rollDie(20) };
}

async function rollSaveFromSheet(saveKey, label) {
  if (!playerCharacter) return;
  if (isActing()) return;
  try {
    beginActing();
    const thrown = await throwDice({
      roller: "player",
      name: playerCharacter.name,
      label: `${label} save`,
      dice: [{ sides: 20 }],
      resolve: async () => {
        const out = await api("/api/osric/saving-throw", {
          method: "POST",
          body: JSON.stringify({ character: playerCharacter, save_key: saveKey }),
        });
        out.dice = [{ sides: 20, value: out.roll }];
        out.hit = !!out.success;
        out.anatomy = SanctuaryDice
          ? SanctuaryDice.anatomySave(out, label)
          : `d20 ${out.roll} vs ${out.target}`;
        return out;
      },
    });
    if (window.SanctuaryDice) SanctuaryDice.hideSoon();
    log(`${playerCharacter.name} rolls ${label}: <span class="log-dice">${thrown.anatomy}</span>`, thrown.success ? "hit" : "miss");
  } catch (err) {
    log(`<span class="damage">${err.message}</span>`);
  }
}

function isStuck(character) {
  return character?.sheet?.stuck === true;
}

function setStuck(character, value) {
  if (character && character.sheet) character.sheet.stuck = value;
}

async function climbOutOfPit() {
  if (!combatState || combatState.phase !== "player") return;
  if (!isStuck(playerCharacter)) return;
  if (isActing()) return;
  beginActing();
  log(`${playerCharacter.name} climbs out of the pit.`, "hit");
  setStuck(playerCharacter, false);
  renderClimbOutButton();
  updateCombatUI();
  saveGame();
  endTurn();
}

function renderClimbOutButton() {
  const bar = document.getElementById("rest-bar");
  if (!bar) return;
  const existing = document.getElementById("climb-out-btn");
  if (existing) existing.remove();
  if (!isStuck(playerCharacter)) return;
  const btn = document.createElement("button");
  btn.id = "climb-out-btn";
  btn.className = "btn btn-secondary";
  btn.textContent = "Climb Out";
  btn.title = "Spend your action climbing out of the pit.";
  btn.disabled = combatState && combatState.phase !== "player";
  btn.addEventListener("click", climbOutOfPit);
  bar.appendChild(btn);
}

async function triggerTrap(x, y) {
  trapsTriggered.add(`${x},${y}`);
  if (typeof tutorialManager !== "undefined" && tutorialManager) {
    tutorialManager.onTrapTriggered();
  }
  drawMap();
  const typeKey = trapData.get(`${x},${y}`) || "spike";
  const def = trapTypes()[typeKey] || trapTypes().spike;
  const damage = trapDamageForType(typeKey);
  const saveKey = def.save;
  const saveTarget = trapSaveForType(typeKey);
  const thrown = await throwDice({
    roller: "player",
    name: playerCharacter.name,
    label: `${def.name} — save`,
    dice: [{ sides: 20 }],
    resolve: async () => {
      const out = await api("/api/osric/saving-throw", {
        method: "POST",
        body: JSON.stringify({ character: playerCharacter, save_key: saveKey, target: saveTarget }),
      });
      out.dice = [{ sides: 20, value: out.roll }];
      out.hit = !!out.success;
      out.anatomy = SanctuaryDice
        ? SanctuaryDice.anatomySave(out, def.name)
        : `d20 ${out.roll} vs ${out.target}`;
      return out;
    },
  });
  if (window.SanctuaryDice) SanctuaryDice.hideSoon();
  const saveRoll = thrown.roll;
  const saved = !!thrown.success;
  const finalDamage = saved ? Math.max(1, Math.floor(damage / 2)) : damage;

  let extra = "";
  if (typeKey === "pit") {
    setStuck(playerCharacter, true);
    extra = " You are stuck in the pit!";
    renderClimbOutButton();
  } else if (typeKey === "poison_needle" && !saved) {
    extra = " Poison courses through your veins!";
  }

  playerCharacter.sheet.hit_points -= finalDamage;
  renderCharacterPanel();
  showFloatingText(x, y, `-${finalDamage}`, 0xff6b6b);
  if (finalDamage > 0) notePlayerWounded();
  log(`A <b>${def.name}</b> springs! <span class="log-dice">${thrown.anatomy}</span>. Take <span class="damage">${finalDamage}</span> damage.${extra}`, saved ? "hit" : "miss");
  saveGame();
  if (!playerAlive()) {
    if (!anyPartyAlive()) {
      showEnd(false, "Your party has fallen to a hidden trap.");
      return;
    }
    ensureConsciousActive();
  } else if (!playerConscious()) {
    handlePlayerDown("Your hero has been knocked unconscious by a trap.");
  }
}

function attackDiceFromResult(res) {
  const dice = [{ sides: 20, value: res.raw_roll }];
  if (res.hit) {
    const sides = (window.SanctuaryDice && SanctuaryDice.parseSides(res.damage_die)) || 8;
    dice.push({ sides, value: res.damage_roll != null ? res.damage_roll : res.damage });
  }
  return dice;
}

async function playerAttackMonster(monster, ranged = false, rangeFt = 0, backstab = false) {
  try {
    monster.asleep = false;
    wakeNearbyMonsters(monster.x, monster.y, 2, "stir from the racket");
    const slashColor = backstab ? 0xffd700 : (ranged ? 0xff6b6b : 0xd4a03d);
    if (typeof tutorialManager !== "undefined" && tutorialManager) {
      tutorialManager.onPlayerAttacked();
    }
    const cover = ranged ? coverBonus(monster) : 0;
    const res = await throwDice({
      roller: "player",
      name: playerCharacter.name,
      label: backstab ? "Backstab" : ranged ? "Missile attack" : "Melee attack",
      dice: [{ sides: 20 }],
      resolve: async () => {
        const out = await api("/api/osric/attack", {
          method: "POST",
          body: JSON.stringify({
            attacker: playerCharacter,
            defender: monsterToCombatant(monster, 0, cover),
            ranged,
            range_ft: rangeFt,
            backstab,
          }),
        });
        out.dice = attackDiceFromResult(out);
        out.anatomy = SanctuaryDice ? SanctuaryDice.anatomyAttack(out) : "";
        return out;
      },
    });
    if (window.SanctuaryDice) SanctuaryDice.hideSoon();
    showAttackSlash(playerPos.x, playerPos.y, monster.x, monster.y, slashColor);
    let action = ranged ? "shoots" : "attacks";
    if (backstab) action = "backstabs";
    const rangeNote = ranged && res.range_penalty ? ` (${res.range_penalty} range)` : "";
    const attackMsg = `${res.attacker} ${action} ${res.defender}${rangeNote}: <span class="log-dice">${res.anatomy || (`d20 ${res.raw_roll} vs ${res.needed}`)}</span>`;
    log(attackMsg, res.hit ? "hit" : "miss");
    if (res.hit) {
      monster.hp -= res.damage;
      showFloatingText(monster.x, monster.y, `-${res.damage}`, 0xff6b6b);
      checkMorale(monster);
      if (monster.hp <= 0) {
        log(`<b>${monster.name}</b> falls!`, "hit");
        killMonster(monster);
      }
    }
    drawTokens();
    saveGame();
  } catch (err) {
    log(`<span class="damage">${err.message}</span>`);
  }
}

async function maybeLevelUp() {
  if (!playerCharacter?.sheet) return;
  let guard = 0;
  while (
    playerCharacter.sheet.next_level_xp > 0 &&
    playerCharacter.sheet.xp >= playerCharacter.sheet.next_level_xp &&
    guard++ < 8
  ) {
    const before = playerCharacter.sheet.level;
    await levelUpCharacter();
    if (!playerCharacter?.sheet || playerCharacter.sheet.level <= before) break;
  }
}

async function levelUpCharacter() {
  try {
    const oldSpells = playerCharacter.sheet.active_spells;
    playerCharacter = await api("/api/osric/level-up", {
      method: "POST",
      body: JSON.stringify({ character: playerCharacter }),
    });
    if (oldSpells && oldSpells.length) {
      playerCharacter.sheet.active_spells = oldSpells;
    }
    if (party.length && activePartyIndex >= 0 && activePartyIndex < party.length) {
      party[activePartyIndex] = playerCharacter;
    }
    log(`<b>${playerCharacter.name} reaches level ${playerCharacter.sheet.level}!</b> HP ${playerCharacter.sheet.hit_points}, THAC0 ${playerCharacter.sheet.thac0}.`, "hit");
    showDelveBanner(`Level ${playerCharacter.sheet.level}`, `${playerCharacter.name} grows stronger.`);
    renderCharacterPanel();
    saveGame();
  } catch (err) {
    log(`<span class="damage">${err.message}</span>`);
  }
}

async function playerCastSpell(spell, targetMonster) {
  try {
    const body = {
      caster: playerCharacter,
      spell_id: spell.id,
      target: targetMonster ? monsterToCombatant(targetMonster) : null,
    };
    const preview = [];
    if (spell.heal) preview.push({ sides: SanctuaryDice ? SanctuaryDice.parseSides(spell.heal) : 8 });
    else if (spell.damage) preview.push({ sides: SanctuaryDice ? SanctuaryDice.parseSides(spell.damage) : 6 });
    else preview.push({ sides: 20 });
    const packed = await throwDice({
      roller: "player",
      name: playerCharacter.name,
      label: spell.name,
      dice: preview,
      resolve: async () => {
        const out = await api("/api/osric/spell", { method: "POST", body: JSON.stringify(body) });
        const r = out.result || {};
        const dice = [];
        if (r.saving_throw) dice.push({ sides: 20, value: r.saving_throw.roll });
        if (r.heal) dice.push({ sides: SanctuaryDice.parseSides(r.heal_die || spell.heal || "1d8"), value: r.heal });
        if (r.damage) dice.push({ sides: SanctuaryDice.parseSides(r.damage_die || spell.damage || "1d4"), value: r.damage });
        if (!dice.length) dice.push({ sides: 20, value: 20 });
        let anatomy = `${r.spell || spell.name}`;
        if (r.heal) anatomy += `: ${r.heal_die || "heal"} -> ${r.heal}`;
        else if (r.damage) anatomy += `: ${r.damage_die || "dmg"} -> ${r.damage}`;
        else if (r.saving_throw) anatomy += `: d20 ${r.saving_throw.roll} vs ${r.saving_throw.target} · ${r.saving_throw.success ? "saved" : "failed"}`;
        else anatomy += " takes effect";
        out.dice = dice;
        out.anatomy = anatomy;
        out.hit = r.hit !== false && !r.saved;
        return out;
      },
    });
    if (window.SanctuaryDice) SanctuaryDice.hideSoon();
    const res = packed;
    playerCharacter = res.character;
    // Keep the party array in sync so subsequent code that reads party[activePartyIndex]
    // does not restore stale spell slots / active spells.
    if (typeof activePartyIndex === "number" && party[activePartyIndex]) {
      party[activePartyIndex] = playerCharacter;
    }
    const result = res.result;
    log(`<span class="log-dice">${packed.anatomy}</span>`, packed.hit ? "hit" : "miss");
    if (spell.buff) {
      const rounds = spell.duration || 1;
      playerCharacter.sheet.active_spells = playerCharacter.sheet.active_spells || [];
      playerCharacter.sheet.active_spells.push({ spell_id: spell.id, name: spell.name, rounds_remaining: rounds });
      log(`${result.caster} casts <b>${result.spell}</b>. It will last <span class="hit">${rounds}</span> rounds.`);
      showFloatingText(playerPos.x, playerPos.y, spell.name.toUpperCase(), 0x5ac989);
    } else if (result.heal) {
      const oldHp = playerCharacter.sheet.hit_points;
      playerCharacter.sheet.hit_points = Math.min(
        playerCharacter.sheet.max_hit_points,
        playerCharacter.sheet.hit_points + result.heal
      );
      const healed = playerCharacter.sheet.hit_points - oldHp;
      showFloatingText(playerPos.x, playerPos.y, `+${healed}`, 0x5ac989);
      log(`${result.caster} casts <b>${result.spell}</b> and heals <span class="hit">${result.heal}</span> HP.`);
    } else if (result.condition && targetMonster) {
      applySpellCondition(targetMonster, result.condition, spell.duration || 1);
      log(`${result.caster} casts <b>${result.spell}</b> on <b>${targetMonster.name}</b>.`);
    } else {
      log(`${result.caster} casts <b>${result.spell}</b> for <span class="damage">${result.damage}</span> damage.`);
      if (targetMonster) {
        targetMonster.hp -= result.damage;
        showFloatingText(targetMonster.x, targetMonster.y, `-${result.damage}`, 0xff6b6b);
        if (targetMonster.hp <= 0) {
          log(`<b>${targetMonster.name}</b> falls!`, "hit");
          killMonster(targetMonster);
        }
      }
    }
    renderCharacterPanel();
    drawTokens();
  } catch (err) {
    log(`<span class="damage">${err.message}</span>`);
  }
}

function decrementActiveSpells(character) {
  if (!character?.sheet?.active_spells) return;
  const before = character.sheet.active_spells.length;
  for (const entry of character.sheet.active_spells) {
    entry.rounds_remaining -= 1;
  }
  character.sheet.active_spells = character.sheet.active_spells.filter(e => e.rounds_remaining > 0);
  const expired = before - character.sheet.active_spells.length;
  if (expired > 0) {
    log(`${character.name}'s active spells fade.`, "miss");
  }
}

function decrementPartyActiveSpells() {
  for (const c of party) decrementActiveSpells(c);
}

function formatActiveSpellsInline(spells) {
  if (!spells || !spells.length) return "";
  const list = spells.map(s => `${s.name} (${s.rounds_remaining})`).join(", ");
  return `<div class="section-title">Active Spells</div><div class="mod-row"><div class="mod-pill">${list}</div></div>`;
}

async function monsterAttackPlayer(monster, powerAttack = false) {
  try {
    if (!playerConscious()) ensureConsciousActive();
    if (!playerCharacter) return;
    const packBonus = packTacticsBonus(monster, playerPos);
    const res = await throwDice({
      roller: "ai",
      name: monster.name,
      label: powerAttack ? "Power attack" : "Melee attack",
      dice: [{ sides: 20 }],
      resolve: async () => {
        const out = await api("/api/osric/attack", {
          method: "POST",
          body: JSON.stringify({ attacker: monsterToCombatant(monster, packBonus, 0, powerAttack), defender: playerCharacter }),
        });
        out.dice = attackDiceFromResult(out);
        out.anatomy = SanctuaryDice ? SanctuaryDice.anatomyAttack(out) : "";
        return out;
      },
    });
    if (window.SanctuaryDice) SanctuaryDice.hideSoon();
    showAttackSlash(monster.x, monster.y, playerPos.x, playerPos.y, powerAttack ? 0xff4500 : 0xc94a4a);
    const action = powerAttack ? "power attacks" : "attacks";
    log(`${res.attacker} ${action} ${res.defender}: <span class="log-dice">${res.anatomy || (`d20 ${res.raw_roll} vs ${res.needed}`)}</span>`, res.hit ? "hit" : "miss");
    if (res.hit) {
      playerCharacter.sheet.hit_points -= res.damage;
      showFloatingText(playerPos.x, playerPos.y, `-${res.damage}`, 0xff6b6b);
      renderCharacterPanel();
      if (res.damage > 0) notePlayerWounded();
      if (!playerAlive()) {
        if (!anyPartyAlive()) {
          showEnd(false, "Your party has fallen.");
          return;
        }
        ensureConsciousActive();
      }
      if (!playerConscious()) {
        handlePlayerDown("Your hero is unconscious and overcome.");
        return;
      }
    }
    drawTokens();
  } catch (err) {
    log(`<span class="damage">${err.message}</span>`);
  }
}

function monsterToCombatant(m, toHitMod = 0, acMod = 0, powerAttack = false) {
  return {
    name: m.name,
    abilities: { strength: 10, dexterity: 10, constitution: 10, intelligence: 10, wisdom: 10, charisma: 10 },
    inventory: [{ item_id: "club", quantity: 1, equipped: true }],
    damage: m.damage,
    damage_mod: (m.damageMod || 0) + (powerAttack ? 2 : 0),
    to_hit_mod: toHitMod + (powerAttack ? 2 : 0),
    sheet: {
      thac0: m.thac0,
      armour_class_descending: m.acDesc + acMod,
      armour_class: 20 - m.acDesc - acMod,
    },
  };
}

function coverBonus(target) {
  // Ranged targets gain +1 AC if adjacent to a wall, barrel, or another creature.
  if (!target || target.x === undefined || target.y === undefined) return 0;
  for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
    const nx = target.x + dx, ny = target.y + dy;
    if (nx < 0 || nx >= MAP_W || ny < 0 || ny >= MAP_H) return 1;
    if (!mapData[ny]) continue;
    const t = mapData[ny][nx];
    if (t === TILE.WALL || t === TILE.SECRET_DOOR || t === TILE.BARREL) return 1;
    if (monsters.some(m => m.alive && m.x === nx && m.y === ny)) return 1;
  }
  return 0;
}

function packTacticsBonus(monster, target) {
  // +1 to hit per adjacent ally on dungeon level 2+ (tutorial monsters fight alone).
  if (dungeonLevel < 2) return 0;
  if (!target || target.x === undefined || target.y === undefined) return 0;
  let allies = 0;
  for (const other of monsters) {
    if (!other.alive || other === monster || other.fled) continue;
    if (Math.abs(other.x - target.x) + Math.abs(other.y - target.y) === 1) allies++;
  }
  return Math.min(allies, 2);
}

const MONSTER_AI_DECKS = {
  brute: [
    { card: "melee", weight: 3 },
    { card: "charge", weight: 2 },
    { card: "power_attack", weight: 1 },
    { card: "ranged", weight: 1 },
  ],
  skirmisher: [
    { card: "melee", weight: 2 },
    { card: "charge", weight: 2 },
    { card: "kite", weight: 1 },
  ],
  archer: [
    { card: "ranged", weight: 3 },
    { card: "kite", weight: 2 },
    { card: "flee", weight: 1 },
  ],
  healer: [
    { card: "heal", weight: 3 },
    { card: "melee", weight: 2 },
    { card: "kite", weight: 1 },
  ],
  boss: [
    { card: "melee", weight: 2 },
    { card: "power_attack", weight: 2 },
    { card: "guard", weight: 1 },
    { card: "rally", weight: 1 },
  ],
};

function buildMonsterAIDeck(monster) {
  return MONSTER_AI_DECKS[monster.aiRole || "brute"] || MONSTER_AI_DECKS.brute;
}

function drawMonsterAICard(monster) {
  const deck = buildMonsterAIDeck(monster);
  const total = deck.reduce((s, c) => s + c.weight, 0);
  let roll = Math.random() * total;
  for (const entry of deck) {
    roll -= entry.weight;
    if (roll <= 0) return entry.card;
  }
  return deck[deck.length - 1].card;
}

function nearestAlly(monster) {
  let best = null, bestDist = Infinity;
  for (const other of monsters) {
    if (!other.alive || other === monster || other.fled) continue;
    const d = distance(other, monster);
    if (d < bestDist && d > 0) { bestDist = d; best = other; }
  }
  return best;
}

function moveMonsterToward(monster, target, moves) {
  let remaining = moves;
  while (remaining > 0 && distance(monster, target) > 1) {
    const step = nextStepToward(monster, target);
    if (!step) break;
    monster.x = step.x;
    monster.y = step.y;
    remaining--;
  }
  return moves - remaining;
}

function moveMonsterAway(monster, target, moves) {
  let remaining = moves;
  while (remaining > 0) {
    const step = nextStepAway(monster, target);
    if (!step) break;
    monster.x = step.x;
    monster.y = step.y;
    remaining--;
  }
  return moves - remaining;
}

async function executeMonsterAICard(monster, card) {
  let firstShout = false;
  if (monster.boss && monster.name && monster.name.includes("Grik") && !monster.shouted) {
    monster.shouted = true;
    firstShout = true;
    log(`<b>Grik</b> slams his mace on the dais. "The Black Sun is mine! Hold, you dogs!"`, "damage");
    showFloatingText(monster.x, monster.y, "HOLD!", 0xd4a03d);
    card = "rally";
  }
  const speed = combatConfig().monster_speed_tiles || 6;
  const adjacent = distance(monster, playerPos) === 1;

  // Archers and skirmishers prefer their signature behaviours; fall back to melee if unable.
  if (card === "ranged" && monster.ranged) {
    let moves = speed;
    if (adjacent && moves > 0) {
      const step = nextStepAway(monster, playerPos);
      if (step) { monster.x = step.x; monster.y = step.y; moves--; }
    }
    while (moves > 0 && !monsterRangedInRange(monster)) {
      const step = nextStepToward(monster, playerPos);
      if (!step) break;
      monster.x = step.x;
      monster.y = step.y;
      moves--;
    }
    if (monsterRangedInRange(monster) && distance(monster, playerPos) > 1) {
      await monsterRangedAttack(monster);
      return;
    }
    // Fallback to closing to melee if no shot exists.
    if (distance(monster, playerPos) === 1) await monsterAttackPlayer(monster);
    return;
  }

  if (card === "kite") {
    let moves = speed;
    if (adjacent && moves > 0) {
      const step = nextStepAway(monster, playerPos);
      if (step) { monster.x = step.x; monster.y = step.y; moves--; }
    }
    if (monster.ranged && monsterRangedInRange(monster) && distance(monster, playerPos) > 1) {
      await monsterRangedAttack(monster);
      return;
    }
    while (moves > 0) {
      const step = nextStepAway(monster, playerPos);
      if (!step) break;
      monster.x = step.x;
      monster.y = step.y;
      moves--;
    }
    return;
  }

  if (card === "flee") {
    monster.fled = true;
    log(`<b>${monster.name}</b> turns and runs!`, "miss");
    showFloatingText(monster.x, monster.y, "FLEE", 0x888888);
    moveMonsterAway(monster, playerPos, speed);
    return;
  }

  if (card === "heal") {
    // Find the most wounded living ally within 6 tiles (excluding self).
    let bestAlly = null;
    let bestMissing = 0;
    for (const other of monsters) {
      if (!other.alive || other === monster || other.fled) continue;
      const d = distance(monster, other);
      if (d > 6) continue;
      const missing = (other.maxHp || other.hp) - other.hp;
      if (missing > bestMissing) {
        bestMissing = missing;
        bestAlly = other;
      }
    }
    if (bestAlly && bestMissing >= 3) {
      const healAmount = Math.min(bestMissing, Math.max(3, rollDie(6) + rollDie(6)));
      bestAlly.hp = Math.min(bestAlly.maxHp || bestAlly.hp, bestAlly.hp + healAmount);
      log(`<b>${monster.name}</b> chants and heals <b>${bestAlly.name}</b> for <span class="hit">${healAmount}</span> HP.`, "hit");
      showFloatingText(bestAlly.x, bestAlly.y, `+${healAmount}`, 0x5ac989);
      return;
    }
    // No worthy target: behave like an archer/skirmisher.
    if (monster.ranged && monsterRangedInRange(monster) && distance(monster, playerPos) > 1) {
      await monsterRangedAttack(monster);
      return;
    }
    if (adjacent) {
      await monsterAttackPlayer(monster);
      return;
    }
    moveMonsterToward(monster, playerPos, speed);
    if (distance(monster, playerPos) === 1) await monsterAttackPlayer(monster);
    return;
  }

  if (card === "guard") {
    const ally = nearestAlly(monster);
    if (ally && distance(monster, ally) > 1) {
      moveMonsterToward(monster, ally, Math.floor(speed / 2));
    }
    if (adjacent || distance(monster, playerPos) === 1) {
      await monsterAttackPlayer(monster);
    }
    return;
  }

  if (card === "rally") {
    let rallied = 0;
    for (const other of monsters) {
      if (!other.alive || other === monster) continue;
      if (other.fled && distance(other, monster) <= 4) {
        other.fled = false;
        other.moraleChecked = false;
        rallied++;
      }
    }
    if (rallied) {
      log(`<b>${monster.name}</b> rallies its companions!`, "miss");
      showFloatingText(monster.x, monster.y, "RALLY", 0xd4a03d);
    } else if (firstShout) {
      const guard = monsters.find((o) => o.alive && o !== monster && o.name && o.name.includes("Guard"));
      if (guard && !guard.fled) log("<b>Grik's Guard</b> braces at the shout.", "miss");
    }
    if (distance(monster, playerPos) === 1) await monsterAttackPlayer(monster);
    return;
  }

  // Charge and power_attack both close distance; power_attack gets a boosted strike.
  if (card === "charge") {
    moveMonsterToward(monster, playerPos, Math.min(speed + 2, 9));
    if (distance(monster, playerPos) === 1) await monsterAttackPlayer(monster);
    return;
  }

  if (card === "power_attack") {
    moveMonsterToward(monster, playerPos, speed);
    if (distance(monster, playerPos) === 1) {
      log(`<b>${monster.name}</b> winds up for a powerful strike!`, "damage");
      await monsterAttackPlayer(monster, true);
    }
    return;
  }

  // Default melee behaviour.
  moveMonsterToward(monster, playerPos, speed);
  if (distance(monster, playerPos) === 1) {
    await monsterAttackPlayer(monster);
  }
}

function rollDamageExpression(expr) {
  // Parse simple expressions like "1d6", "1d6+1", "2d4".
  const match = expr.match(/(\d+)d(\d+)(?:\s*([+-])\s*(\d+))?/);
  if (!match) return 1;
  const count = parseInt(match[1], 10);
  const sides = parseInt(match[2], 10);
  const modOp = match[3];
  const modVal = match[4] ? parseInt(match[4], 10) : 0;
  let total = 0;
  for (let i = 0; i < count; i++) total += rollDie(sides);
  if (modOp === "+") total += modVal;
  if (modOp === "-") total -= modVal;
  return Math.max(1, total);
}

function monsterRangedInRange(m) {
  return m.ranged && distance(m, playerPos) > 0 && distance(m, playerPos) <= Math.floor(m.ranged.range / 10) &&
         hasRangedLineOfSight(m, playerPos);
}

async function monsterRangedAttack(m) {
  try {
    if (!playerConscious()) ensureConsciousActive();
    if (!playerCharacter) return;
    const res = await throwDice({
      roller: "ai",
      name: m.name,
      label: "Missile attack",
      dice: [{ sides: 20 }],
      resolve: async () => {
        const rawRoll = rollDie(20);
        const packBonus = packTacticsBonus(m, playerPos);
        const cover = coverBonus(playerPos);
        const needed = m.thac0 - playerCharacter.sheet.armour_class_descending - packBonus + cover;
        const autoHitVal = combatConfig().auto_hit ?? 20;
        const autoMissVal = combatConfig().auto_miss ?? 1;
        const hit = rawRoll === autoHitVal || (rawRoll !== autoMissVal && rawRoll >= needed);
        let damage = 0;
        const dice = [{ sides: 20, value: rawRoll }];
        if (hit) {
          damage = rollDamageExpression(m.ranged.damage);
          const sides = (window.SanctuaryDice && SanctuaryDice.parseSides(m.ranged.damage)) || 4;
          dice.push({ sides, value: damage });
        }
        return {
          raw_roll: rawRoll, needed, hit, damage, weapon: "missile",
          to_hit_mod: 0, roll: rawRoll, damage_die: m.ranged.damage,
          dice,
          anatomy: `d20 ${rawRoll} vs ${needed} · ${hit ? `hit → ${damage}` : "miss"}`,
        };
      },
    });
    if (window.SanctuaryDice) SanctuaryDice.hideSoon();
    showAttackSlash(m.x, m.y, playerPos.x, playerPos.y, 0xff6b6b);
    log(`${m.name} shoots ${playerCharacter.name}: <span class="log-dice">${res.anatomy}</span>`, res.hit ? "hit" : "miss");
    if (res.hit) {
      playerCharacter.sheet.hit_points -= res.damage;
      showFloatingText(playerPos.x, playerPos.y, `-${res.damage}`, 0xff6b6b);
      renderCharacterPanel();
      if (res.damage > 0) notePlayerWounded();
      if (!playerAlive()) {
        if (!anyPartyAlive()) {
          showEnd(false, "Your party has fallen.");
          return;
        }
        ensureConsciousActive();
      }
      if (!playerConscious()) {
        handlePlayerDown("Your hero is unconscious and overcome.");
        return;
      }
    }
    drawTokens();
  } catch (err) {
    log(`<span class="damage">${err.message}</span>`);
  }
}

function nextActingPartyMember() {
  const threshold = combatConfig().unconscious_threshold ?? 0;
  const acted = combatState.partyActed || new Set();
  for (let i = activePartyIndex + 1; i < party.length; i++) {
    if (party[i].sheet.hit_points > threshold && !acted.has(i)) return i;
  }
  for (let i = 0; i <= activePartyIndex; i++) {
    if (party[i].sheet.hit_points > threshold && !acted.has(i)) return i;
  }
  return -1;
}

function endTurn() {
  stopAutoExplore();
  if (!combatState || combatState.phase !== "player") return;
  if (!playerConscious()) {
    log("You are unconscious and cannot act.");
    return;
  }
  if (typeof tutorialManager !== "undefined" && tutorialManager) {
    tutorialManager.resetTurn();
  }
  combatState.partyActed.add(activePartyIndex);
  const next = nextActingPartyMember();
  if (next >= 0) {
    activePartyIndex = next;
    playerCharacter = party[next];
    combatState.acted = false;
    combatState.attacked = false;
    combatState.movementRemaining = tilesPerRound(playerCharacter.sheet.movement);
    renderCharacterPanel();
    updateCombatUI();
    highlightReachable(playerPos, combatState.movementRemaining);
    highlightRangedTargets();
    maybeAutoMercTurn();
    return;
  }
  combatState.playerActedThisRound = true;
  combatState.phase = "enemy";
  pendingSpell = null;
  clearHighlights();
  updateCombatUI();
  setTimeout(enemyTurn, 800);
}

function maybeAutoMercTurn() {
  if (!combatState || combatState.phase !== "player") return;
  if (!autoMercs) return;
  const c = party[activePartyIndex];
  if (!c || !c.isMercenary) return;
  if (combatState.partyActed?.has(activePartyIndex)) return;
  const threshold = combatConfig().unconscious_threshold ?? 0;
  if (c.sheet.hit_points <= threshold) return;
  clearPendingSpell();
  clearHighlights();
  setTimeout(() => runMercenaryTurn(c, activePartyIndex), MERC_AI_DELAY);
}

function checkMonsterRally(m) {
  // A fleeing monster rallies if cornered or if it has put distance between itself and the player.
  if (!m.fled) return;
  const d = distance(m, playerPos);
  if (d >= 8) {
    m.fled = false;
    m.moraleChecked = false;
    log(`<b>${m.name}</b> stops fleeing and readies itself.`, "miss");
    return;
  }
  // Cornered: no valid step away means it must fight.
  const step = nextStepAway(m, playerPos);
  if (!step) {
    m.fled = false;
    m.moraleChecked = false;
    log(`<b>${m.name}</b> is cornered and turns to fight!`, "miss");
  }
}

async function enemyTurn() {
  if (!anyPartyAlive()) {
    showEnd(false, "Your party has fallen.");
    return;
  }
  if (!playerConscious()) ensureConsciousActive();

  const activeMonsters = monsters.filter(m => m.alive);
  for (const m of activeMonsters) {
    if (!anyPartyAlive()) break;
    if (!playerConscious()) ensureConsciousActive();

    checkMorale(m);
    if (m.fled || m.turned > 0) continue;

    checkMonsterRally(m);

    // Sleeping monsters do not act until they see or hear the party.
    if (m.asleep) {
      const alerted = distance(m, playerPos) <= 3 || isVisibleToPlayer(m.x, m.y);
      if (!alerted) continue;
      m.asleep = false;
      log(`<b>${m.name}</b> wakes up!`, "miss");
      showFloatingText(m.x, m.y, "ALERT", 0xff6b6b);
      wakeNearbyMonsters(m.x, m.y, 2, "wake from the noise");
    } else if (distance(m, playerPos) > 6 && !(typeof isVisibleToPlayer === "function" && isVisibleToPlayer(m.x, m.y))) {
      // Stay in their room. Do not hunt across the dungeon.
      continue;
    }

    // Intelligent monsters bash open adjacent doors to reach the player.
    if (!m.fled && m.morale > 4) {
      for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
        const nx = m.x + dx, ny = m.y + dy;
        const isDoor = mapData[ny] && mapData[ny][nx] === TILE.DOOR && !doorsOpened.has(`${nx},${ny}`);
        const isLocked = mapData[ny] && mapData[ny][nx] === TILE.LOCKED_DOOR && !doorsOpened.has(`${nx},${ny}`);
        if (isDoor || isLocked) {
          doorsOpened.add(`${nx},${ny}`);
          log(`A ${m.name} bursts through ${isLocked ? 'a locked door' : 'a door'}!`);
          drawMap();
          renderFog();
          break;
        }
      }
    }

    // Draw a role-based AI ability card and execute it.
    const card = drawMonsterAICard(m);
    await executeMonsterAICard(m, card);
    drawTokens();
    if (!anyPartyAlive() || !anyPartyConscious()) break;
    await new Promise((r) => setTimeout(r, 450));
  }

  combatState.enemyActedThisRound = true;

  // Count down turn-undead and sleep durations.
  for (const m of monsters) {
    if (m.turned > 0) {
      m.turned -= 1;
      if (m.turned <= 0) {
        log(`<b>${m.name}</b> shakes off its terror and returns.`, "miss");
      }
    }
    if (m.asleep && typeof m.sleepRounds === "number") {
      m.sleepRounds -= 1;
      if (m.sleepRounds <= 0) {
        m.asleep = false;
        log(`<b>${m.name}</b> wakes from magical sleep.`, "miss");
      }
    }
  }

  if (!anyPartyAlive()) {
    showEnd(false, "Your party has fallen.");
    return;
  }

  if (!playerConscious()) {
    await doDeathSave();
    if (!anyPartyAlive()) return;
    // Start the next round; the start-of-round logic will continue death saves
    // if the hero is still unconscious, otherwise hand control to the player.
    startRound();
    return;
  }

  const wanderCfg = combatConfig().wandering_monsters;
  if (wanderCfg?.enabled && wanderCfg?.check_every_round && !isCombatSafe()) {
    if (wanderingMonsterCheck(wanderCfg)) {
      const spawned = spawnWanderingMonster(wanderingMonsterCount(wanderCfg));
      if (spawned) {
        log(`<span class="damage">More monsters wander into the fight!</span>`, "damage");
      }
    }
  }

  if (!combatState.playerActedThisRound) {
    // Player lost initiative; now it's their turn in the same round.
    combatState.phase = "player";
    combatState.partyActed = new Set();
    if (!playerConscious()) ensureConsciousActive();
    combatState.movementRemaining = tilesPerRound(playerCharacter.sheet.movement);
    combatState.acted = false;
    combatState.attacked = false;
    updateCombatUI();
    highlightReachable(playerPos, combatState.movementRemaining);
    highlightRangedTargets();
  } else {
    // Both sides have acted; begin the next round.
    combatState.round += 1;
    startRound();
  }
  checkEnd();
  saveGame();
}

function nextStepToward(from, to) {
  // BFS one step toward target, avoiding walls and other monsters.
  const queue = [{ x: from.x, y: from.y, path: [] }];
  const seen = new Set([`${from.x},${from.y}`]);
  let head = 0;
  while (head < queue.length) {
    const cur = queue[head++];
    if (cur.x === to.x && cur.y === to.y) {
      return cur.path[0] || null;
    }
    for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
      const nx = cur.x + dx, ny = cur.y + dy;
      const key = `${nx},${ny}`;
      if (seen.has(key)) continue;
      if (!isWalkable(nx, ny)) continue;
      const occupant = monsters.find(mm => mm.alive && mm !== from && mm.x === nx && mm.y === ny);
      if (occupant) continue;
      seen.add(key);
      const newPath = [...cur.path, { x: nx, y: ny }];
      queue.push({ x: nx, y: ny, path: newPath });
    }
  }
  return null;
}

function nextStepAway(from, to) {
  // Greedy step maximizing Manhattan distance from `to`.
  let best = null;
  let bestDist = -1;
  for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
    const nx = from.x + dx, ny = from.y + dy;
    if (!isWalkable(nx, ny)) continue;
    const occupant = monsters.find(mm => mm.alive && mm !== from && mm.x === nx && mm.y === ny);
    if (occupant) continue;
    const d = distance({ x: nx, y: ny }, to);
    if (d > bestDist) {
      bestDist = d;
      best = { x: nx, y: ny };
    }
  }
  return best;
}

function farthestFromPlayer(from) {
  // BFS to find the reachable tile farthest from the player.
  const queue = [{ ...from, d: 0 }];
  const seen = new Set([`${from.x},${from.y}`]);
  let best = from;
  let bestDist = distance(from, playerPos);
  let head = 0;
  while (head < queue.length) {
    const cur = queue[head++];
    const dist = distance(cur, playerPos);
    if (dist > bestDist) {
      bestDist = dist;
      best = { x: cur.x, y: cur.y };
    }
    if (cur.d >= 6) continue;
    for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
      const nx = cur.x + dx, ny = cur.y + dy;
      const key = `${nx},${ny}`;
      if (seen.has(key)) continue;
      if (!isWalkable(nx, ny)) continue;
      const occupant = monsters.find(mm => mm.alive && mm !== from && mm.x === nx && mm.y === ny);
      if (occupant) continue;
      seen.add(key);
      queue.push({ x: nx, y: ny, d: cur.d + 1 });
    }
  }
  return best;
}

function checkEnd() {
  if (!combatState || combatState.exitAnnounced) return;
  if (!monsters.length || !monsters.every(m => !m.alive || m.fled)) return;
  combatState.exitAnnounced = true;
  log("<span class='hit'>All enemies are dead or fled. The exit is open.</span>", "hit");
  const lvl = playerCharacter?.sheet?.level || 1;
  const name = playerCharacter?.name || "You";
  if (lvl >= 2) {
    showDelveBanner(`Level ${lvl} — exit open`, `${name} is stronger. The beacon is lit — walk the shrine tunnel.`);
  } else {
    showDelveBanner("Exit open", "The beacon is lit. Walk the shrine tunnel to leave.");
  }
  const objectiveBadge = document.getElementById("objective-badge");
  if (objectiveBadge) {
    objectiveBadge.textContent = "Exit open";
    objectiveBadge.classList.add("exit-open");
  }
}

function applySpellCondition(monster, condition, duration) {
  if (!monster || !condition) return;
  if (condition === "sleeping") {
    monster.asleep = true;
    monster.sleepRounds = duration;
    showFloatingText(monster.x, monster.y, "SLEEP", 0x9b59b6);
    log(`<b>${monster.name}</b> falls into a magical slumber.`, "hit");
  } else if (condition === "charmed") {
    monster.fled = true;
    monster.charmed = true;
    showFloatingText(monster.x, monster.y, "CHARMED", 0x9b59b6);
    log(`<b>${monster.name}</b> is charmed and wanders off.`, "hit");
  }
}

function wakeNearbyMonsters(x, y, radius = 2, source = "") {
  let woken = 0;
  for (const m of monsters) {
    if (!m.alive || !m.asleep) continue;
    if (distance(m, { x, y }) <= radius) {
      m.asleep = false;
      woken++;
    }
  }
  if (woken && source) {
    log(`${woken > 1 ? "Several monsters" : "A monster"} ${source}!`, "miss");
  }
  return woken;
}

function checkMorale(monster) {
  if (monster.moraleChecked || monster.fled || !monster.alive) return;
  if (monster.boss) return; // Bosses stand and fight.
  const wounded = monster.hp <= monster.maxHp / 2;
  if (!wounded) return;
  monster.moraleChecked = true;
  const roll = rollDie(6) + rollDie(6);
  if (roll > monster.morale) {
    monster.fled = true;
    log(`<b>${monster.name}</b> loses morale and flees!`, "miss");
    showFloatingText(monster.x, monster.y, "FLEE", 0x888888);
  }
}

function checkGroupMorale() {
  if (!combatState || combatState.groupMoraleChecked) return;
  const start = combatState.monsterCountAtStart || monsters.length;
  if (start <= 1) return;
  const alive = monsters.filter(m => m.alive).length;
  if (alive > start / 2) return;
  combatState.groupMoraleChecked = true;
  for (const m of monsters) {
    if (!m.alive || m.fled || m.moraleChecked) continue;
    m.moraleChecked = true;
    const roll = rollDie(6) + rollDie(6);
    if (roll > m.morale) {
      m.fled = true;
      log(`<b>${m.name}</b> sees half its companions fall and flees!`, "miss");
      showFloatingText(m.x, m.y, "FLEE", 0x888888);
    }
  }
}

const KEY_DIRS = {
  ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0],
  w: [0, -1], s: [0, 1], a: [-1, 0], d: [1, 0],
  W: [0, -1], S: [0, 1], A: [-1, 0], D: [1, 0],
};

async function handleKeyDown(e) {
  const dir = KEY_DIRS[e.key];
  if (!dir) return;
  const tag = e.target && e.target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
  if (!combatState || combatState.phase !== "player") return;
  e.preventDefault();
  const [dx, dy] = dir;
  const tx = playerPos.x + dx;
  const ty = playerPos.y + dy;
  if (tx < 0 || tx >= MAP_W || ty < 0 || ty >= MAP_H) return;
  await handleGridClick(tx, ty);
}

window.addEventListener("keydown", handleKeyDown);

/** Turn-based OSRIC combat and dungeon exploration. */

let combatState = null;
let pendingSpell = null;

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

function potionEntry() {
  return playerCharacter.sheet.inventory.items.find(i => i.item_id === "potion_of_healing" && (i.quantity || 1) > 0);
}

function hasPotion() {
  return !!potionEntry();
}

async function usePotion() {
  const entry = potionEntry();
  if (!entry) {
    log("No potion of healing available.");
    return 0;
  }
  const item = osricOptions.equipment.find(e => e.id === "potion_of_healing");
  const amount = rollDamageExpression(item?.heal || "1d8");
  const healed = healPlayer(amount);
  entry.quantity = (entry.quantity || 1) - 1;
  if (entry.quantity <= 0) {
    const idx = playerCharacter.sheet.inventory.items.indexOf(entry);
    if (idx >= 0) playerCharacter.sheet.inventory.items.splice(idx, 1);
  }
  log(`${playerCharacter.name} quaffs a <b>potion of healing</b>.`);
  renderCharacterPanel();
  renderConsumablesButton();
  saveGame();
  return healed;
}

function canRest() {
  const cfg = combatConfig().rest;
  if (!combatState) return false;
  if (cfg?.require_safe_area && !isCombatSafe()) return false;
  if (!playerAlive()) return false;
  // Unconscious characters can only rest if the area is safe (companions bind wounds).
  if (!playerConscious() && (!cfg?.require_safe_area || !isCombatSafe())) return false;
  return combatState.phase === "player";
}

async function playerRest() {
  if (!canRest()) {
    log("It is not safe to rest here.");
    return;
  }
  const wanderCfg = combatConfig().wandering_monsters;
  if (wanderCfg?.enabled && wanderCfg?.check_on_rest) {
    const chance = wanderCfg.chance_in_6 ?? 1;
    if (rollDie(6) <= chance) {
      const spawned = spawnWanderingMonster(wanderCfg.count_per_encounter);
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

  if (cfg?.consumes_action) {
    combatState.acted = true;
    combatState.attacked = true;
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
  if (!combatState) return;
  if (!canRest()) return;
  const cfg = combatConfig().rest;
  const amount = (cfg?.short_rest_heal_per_level ?? 1) * (playerCharacter.sheet.level || 1);
  const btn = document.createElement("button");
  btn.id = "rest-btn";
  btn.className = "btn btn-secondary";
  btn.textContent = playerConscious() ? `Rest (+${amount})` : "Bind Wounds";
  btn.title = playerConscious() ? "Take a short rest to recover HP." : "Rest until you can stand.";
  btn.disabled = combatState.phase !== "player";
  btn.addEventListener("click", playerRest);
  bar.appendChild(btn);
}



function initCombat() {
  initDungeon();
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

async function playerTurnUndead() {
  if (!combatState || combatState.phase !== "player") return;
  if (combatState.attacked) {
    log("You have already acted this round.");
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

  combatState.acted = true;
  combatState.attacked = true;
  let anyTurned = false;

  for (const m of targets) {
    const key = Object.keys(table).find(k => m.name.toLowerCase().includes(k.replace(/_/g, " ")));
    if (!key) continue;
    const target = table[key];
    const roll = rollDie(20);
    const turned = roll >= target;
    log(`${playerCharacter.name} turns toward <b>${m.name}</b>: roll <span class="roll">${roll}</span> vs ${target} — ${turned ? '<span class="hit">turned</span>' : '<span class="miss">resists</span>'}.`);
    if (turned) {
      anyTurned = true;
      showFloatingText(m.x, m.y, "TURNED", 0xd4a03d);
      killMonster(m);
    }
  }

  if (anyTurned) {
    log("<span class='hit'>The undead cower and fall.</span>", "hit");
  }
  renderCharacterPanel();
  updateCombatUI();
  checkEnd();
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
  sneakBtn.disabled = combatState && combatState.phase !== "player" || playerStealthed;
  sneakBtn.addEventListener("click", playerSneak);
  bar.appendChild(sneakBtn);

  const trapBtn = document.createElement("button");
  trapBtn.id = "search-traps-btn";
  trapBtn.className = "btn btn-secondary";
  trapBtn.textContent = `Find Traps (${skills.find_remove_traps}%)`;
  trapBtn.title = "Search adjacent tiles for traps.";
  trapBtn.disabled = combatState && combatState.phase !== "player";
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
  combatState.acted = true;
  updateCombatUI();
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
  combatState.acted = true;
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
  // Healing spells target the caster automatically.
  if (spell.heal) {
    await playerCastSpell(spell, null);
    combatState.acted = true;
    combatState.attacked = true;
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

function rollInitiative() {
  const active = activeCharacter();
  const playerMod = dexInitiativeMod();
  combatState.playerInitiative = rollDie(6) + playerMod;
  combatState.enemyInitiative = rollDie(6);
  const wentFirst = combatState.playerInitiative >= combatState.enemyInitiative ? "You" : "Enemies";
  log(`${wentFirst} win initiative (player ${combatState.playerInitiative}, enemy ${combatState.enemyInitiative}).`);
  combatState.phase = combatState.playerInitiative >= combatState.enemyInitiative ? "player" : "enemy";
  combatState.movementRemaining = tilesPerRound(active.sheet.movement);
  combatState.acted = false;
  combatState.attacked = false;
  combatState.playerActedThisRound = false;
  combatState.enemyActedThisRound = false;
  pendingSpell = null;
  pendingTrapSearch = false;
}

function rollSurprise() {
  const cfg = osricRules?.combat?.surprise || { chance_in_6: 2 };
  const threshold = cfg.chance_in_6 || 2;
  const playerSurprised = rollDie(6) <= threshold;
  const enemySurprised = rollDie(6) <= threshold;
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
  // Wait for the player to act and end turn, then begin round 1.
}

async function enemySurpriseRound() {
  // Enemies get a free round; mark them so they don't get another when normal combat starts.
  await enemyTurn();
  combatState.enemyActedThisRound = true;
}

async function startRound() {
  combatState.partyActed = new Set();
  if (!playerConscious()) {
    ensureConsciousActive();
  }
  rollInitiative();
  updateCombatUI();
  if (combatState.phase === "player" && !playerConscious()) {
    await doDeathSave();
    return;
  }
  if (combatState.phase === "player") {
    highlightReachable(playerPos, combatState.movementRemaining);
    highlightRangedTargets();
  } else {
    setTimeout(enemyTurn, 600);
  }
}

function updateCombatUI() {
  const name = playerCharacter ? playerCharacter.name : "Party";
  const turnText = combatState.phase === "player"
    ? `Round ${combatState.round} — ${name}'s turn · Move ${combatState.movementRemaining} tiles`
    : `Round ${combatState.round} — Enemy turn`;
  document.getElementById("turn-badge").textContent = turnText;
  document.getElementById("end-turn-btn").disabled = combatState.phase !== "player" || !playerConscious();

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
  for (const entry of inv) {
    if (!entry.equipped) continue;
    const item = osricOptions.equipment.find(i => i.id === entry.item_id);
    if (item && item.category === "weapons" && item.missile) return item;
  }
  return null;
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
  if (!playerConscious()) {
    log("You are unconscious and cannot act.");
    return;
  }

  // Open adjacent closed doors.
  if (mapData[gy] && mapData[gy][gx] === TILE.DOOR && !doorsOpened.has(`${gx},${gy}`)) {
    if (distance(playerPos, { x: gx, y: gy }) === 1) {
      doorsOpened.add(`${gx},${gy}`);
      log(`${playerCharacter.name} opens a door.`);
      drawMap();
      renderFog();
      highlightReachable(playerPos, combatState.movementRemaining);
      saveGame();
    }
    return;
  }

  const targetMonster = monsterAt(gx, gy);

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
    await playerCastSpell(pendingSpell, targetMonster);
    pendingSpell = null;
    combatState.acted = true;
    combatState.attacked = true; // spells count as the round's attack action
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
    await playerAttackMonster(targetMonster, false, 0, backstab);
    combatState.acted = true;
    combatState.attacked = true;
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
      if (!consumeAmmo()) {
        log("<span class='damage'>No ammo left for this weapon.</span>");
        return;
      }
      await playerAttackMonster(targetMonster, true, d * 10);
      combatState.acted = true;
      combatState.attacked = true;
      clearStealth();
      renderCharacterPanel();
      updateCombatUI();
      checkEnd();
      return;
    }
  }

  if (combatState.movementRemaining <= 0) return;
  const reachable = computeReachable(playerPos, combatState.movementRemaining);
  if (reachable.some(p => p.x === gx && p.y === gy)) {
    const dist = distance(playerPos, { x: gx, y: gy });
    movePlayer(gx, gy);
    combatState.movementRemaining -= dist;
    log(`${playerCharacter.name} moves ${dist * 10} ft.`);
    // Moving silently is hard; stealth breaks on movement unless thief.
    if (!isThief()) clearStealth();
    updateCombatUI();
    highlightReachable(playerPos, combatState.movementRemaining);
    highlightRangedTargets();
    await checkTileInteraction(gx, gy);
    saveGame();
  }
}

async function checkTileInteraction(x, y) {
  const t = mapData[y][x];
  if (t === TILE.CHEST && !chestsOpened.has(`${x},${y}`)) {
    openChest(x, y);
    const chestCfg = combatConfig().chest || {};
    const rolls = rollDamageExpression(chestCfg.gold_die || "1d6");
    const cp = rolls * (chestCfg.gold_cp_per_roll || 100);
    playerCharacter.remaining_gold += cp / 100;
    playerCharacter.sheet.xp += cp;
    log(`The chest holds <b>${formatCoins(cp)}</b> (${cp} XP).`, "hit");
    if (playerCharacter.sheet.xp >= playerCharacter.sheet.next_level_xp) {
      await levelUpCharacter();
    }
    renderCharacterPanel();
    saveGame();
  } else if (t === TILE.EXIT) {
    if (monsters.every(m => !m.alive || m.fled)) {
      showDescendChoice();
    } else {
      log("The exit is warded until the enemies fall.");
    }
  } else if (t === TILE.TRAP && !trapsTriggered.has(`${x},${y}`)) {
    triggerTrap(x, y);
  }
}

function trapDamage() {
  const die = combatConfig().trap?.damage_die || "1d6";
  return rollDamageExpression(die);
}

function trapSaveTarget() {
  const cfg = combatConfig().trap || {};
  const key = cfg.save_target;
  if (key && playerCharacter?.sheet?.saving_throws && playerCharacter.sheet.saving_throws[key] !== undefined) {
    return playerCharacter.sheet.saving_throws[key];
  }
  return cfg.save_fallback || 15;
}

function triggerTrap(x, y) {
  trapsTriggered.add(`${x},${y}`);
  drawMap();
  const cfg = combatConfig().trap || {};
  const damage = trapDamage();
  const saveTarget = trapSaveTarget();
  const saveRoll = rollDie(20);
  const saved = saveRoll >= saveTarget;
  const finalDamage = saved
    ? Math.max(cfg.min_damage_on_save ?? 1, Math.floor(damage / 2))
    : damage;
  playerCharacter.sheet.hit_points -= finalDamage;
  renderCharacterPanel();
  showFloatingText(x, y, `-${finalDamage}`, 0xff6b6b);
  log(`A trap springs! Save roll <span class="roll">${saveRoll}</span> vs ${saveTarget}: ${saved ? '<span class="hit">saved</span>' : '<span class="miss">failed</span>'}. Take <span class="damage">${finalDamage}</span> damage.`);
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

async function playerAttackMonster(monster, ranged = false, rangeFt = 0, backstab = false) {
  try {
    const slashColor = backstab ? 0xffd700 : (ranged ? 0xff6b6b : 0xd4a03d);
    showAttackSlash(playerPos.x, playerPos.y, monster.x, monster.y, slashColor);
    const res = await api("/api/osric/attack", {
      method: "POST",
      body: JSON.stringify({
        attacker: playerCharacter,
        defender: monsterToCombatant(monster),
        ranged,
        range_ft: rangeFt,
        backstab,
      }),
    });
    let action = ranged ? "shoots" : "attacks";
    if (backstab) action = "backstabs";
    const rangeNote = ranged && res.range_penalty ? ` (${res.range_penalty} range)` : "";
    const backstabNote = backstab ? ` <span class="hit">backstab x${res.backstab_multiplier}</span>` : "";
    log(`${res.attacker} ${action} ${res.defender}${rangeNote}: rolled <span class="roll">${res.raw_roll}</span> vs AC ${res.needed}. ${res.hit ? `<span class="hit">Hit</span>${backstabNote} for <span class="damage">${res.damage}</span> damage` : '<span class="miss">Miss</span>'}.`);
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

async function levelUpCharacter() {
  try {
    playerCharacter = await api("/api/osric/level-up", {
      method: "POST",
      body: JSON.stringify({ character: playerCharacter }),
    });
    if (party.length && activePartyIndex >= 0 && activePartyIndex < party.length) {
      party[activePartyIndex] = playerCharacter;
    }
    log(`<b>${playerCharacter.name} reaches level ${playerCharacter.sheet.level}!</b> HP ${playerCharacter.sheet.hit_points}, THAC0 ${playerCharacter.sheet.thac0}.`, "hit");
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
    const res = await api("/api/osric/spell", { method: "POST", body: JSON.stringify(body) });
    playerCharacter = res.character;
    const result = res.result;
    if (result.heal) {
      const oldHp = playerCharacter.sheet.hit_points;
      playerCharacter.sheet.hit_points = Math.min(
        playerCharacter.sheet.max_hit_points,
        playerCharacter.sheet.hit_points + result.heal
      );
      const healed = playerCharacter.sheet.hit_points - oldHp;
      showFloatingText(playerPos.x, playerPos.y, `+${healed}`, 0x5ac989);
      log(`${result.caster} casts <b>${result.spell}</b> and heals <span class="hit">${result.heal}</span> HP.`);
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

async function monsterAttackPlayer(monster) {
  try {
    if (!playerConscious()) ensureConsciousActive();
    if (!playerCharacter) return;
    showAttackSlash(monster.x, monster.y, playerPos.x, playerPos.y, 0xc94a4a);
    const res = await api("/api/osric/attack", {
      method: "POST",
      body: JSON.stringify({ attacker: monsterToCombatant(monster), defender: playerCharacter }),
    });
    log(`${res.attacker} attacks ${res.defender}: rolled <span class="roll">${res.raw_roll}</span> vs AC ${res.needed}. ${res.hit ? `<span class="hit">Hit</span> for <span class="damage">${res.damage}</span> damage` : '<span class="miss">Miss</span>'}.`);
    if (res.hit) {
      playerCharacter.sheet.hit_points -= res.damage;
      showFloatingText(playerPos.x, playerPos.y, `-${res.damage}`, 0xff6b6b);
      renderCharacterPanel();
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

function monsterToCombatant(m) {
  return {
    name: m.name,
    abilities: { strength: 10, dexterity: 10, constitution: 10, intelligence: 10, wisdom: 10, charisma: 10 },
    inventory: [{ item_id: "club", quantity: 1, equipped: true }],
    sheet: {
      thac0: m.thac0,
      armour_class_descending: m.acDesc,
      armour_class: 20 - m.acDesc,
    },
  };
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
  return m.ranged && distance(m, playerPos) > 0 && distance(m, playerPos) <= Math.floor(m.ranged.range / 10);
}

async function monsterRangedAttack(m) {
  try {
    if (!playerConscious()) ensureConsciousActive();
    if (!playerCharacter) return;
    showAttackSlash(m.x, m.y, playerPos.x, playerPos.y, 0xff6b6b);
    const rawRoll = rollDie(20);
    const needed = m.thac0 - playerCharacter.sheet.armour_class_descending;
    const autoHitVal = combatConfig().auto_hit ?? 20;
    const autoMissVal = combatConfig().auto_miss ?? 1;
    const autoHit = rawRoll === autoHitVal;
    const autoMiss = rawRoll === autoMissVal;
    const hit = autoHit || (!autoMiss && rawRoll >= needed);
    let damage = 0;
    if (hit) {
      damage = rollDamageExpression(m.ranged.damage);
      playerCharacter.sheet.hit_points -= damage;
      showFloatingText(playerPos.x, playerPos.y, `-${damage}`, 0xff6b6b);
      renderCharacterPanel();
    }
    log(`${m.name} shoots ${playerCharacter.name}: rolled <span class="roll">${rawRoll}</span> vs AC ${needed}. ${hit ? `<span class="hit">Hit</span> for <span class="damage">${damage}</span> damage` : '<span class="miss">Miss</span>'}.`);
    if (hit) {
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
  if (!combatState || combatState.phase !== "player") return;
  if (!playerConscious()) {
    log("You are unconscious and cannot act.");
    return;
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
    return;
  }
  combatState.playerActedThisRound = true;
  combatState.phase = "enemy";
  pendingSpell = null;
  clearHighlights();
  updateCombatUI();
  setTimeout(enemyTurn, 400);
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

    checkMonsterRally(m);

    // Intelligent monsters bash open adjacent doors to reach the player.
    if (!m.fled && m.morale > 4) {
      for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
        const nx = m.x + dx, ny = m.y + dy;
        if (mapData[ny] && mapData[ny][nx] === TILE.DOOR && !doorsOpened.has(`${nx},${ny}`)) {
          doorsOpened.add(`${nx},${ny}`);
          log(`A ${m.name} bursts through a door!`);
          drawMap();
          renderFog();
          break;
        }
      }
    }

    const speed = combatConfig().monster_speed_tiles || 6;
    let moves = speed;

    // Ranged monsters prefer to shoot when in range and not adjacent.
    if (!m.fled && m.ranged) {
      const inRange = monsterRangedInRange(m);
      const adjacent = distance(m, playerPos) === 1;
      if (inRange && !adjacent) {
        await monsterRangedAttack(m);
        if (!anyPartyAlive() || !anyPartyConscious()) break;
        continue;
      }
      // Move to get in range if too far; back up if adjacent.
      while (moves > 0 && !monsterRangedInRange(m)) {
        const step = adjacent ? nextStepAway(m, playerPos) : nextStepToward(m, playerPos);
        if (!step) break;
        m.x = step.x;
        m.y = step.y;
        moves--;
      }
      if (monsterRangedInRange(m) && distance(m, playerPos) > 1) {
        await monsterRangedAttack(m);
        if (!anyPartyAlive() || !anyPartyConscious()) break;
        continue;
      }
    }

    const target = m.fled ? farthestFromPlayer(m) : playerPos;
    while (moves > 0 && distance(m, target) > (m.fled ? 0 : 1)) {
      const step = m.fled ? nextStepAway(m, playerPos) : nextStepToward(m, playerPos);
      if (!step) break;
      m.x = step.x;
      m.y = step.y;
      moves--;
    }
    drawTokens();

    if (!m.fled && distance(m, playerPos) === 1) {
      await monsterAttackPlayer(m);
      if (!anyPartyAlive() || !anyPartyConscious()) break;
    }
  }

  combatState.enemyActedThisRound = true;

  if (!anyPartyAlive()) {
    showEnd(false, "Your party has fallen.");
    return;
  }

  if (!playerConscious()) {
    await doDeathSave();
    return;
  }

  const wanderCfg = combatConfig().wandering_monsters;
  if (wanderCfg?.enabled && wanderCfg?.check_every_round && !isCombatSafe()) {
    const chance = wanderCfg.chance_in_6 ?? 1;
    if (rollDie(6) <= chance) {
      const spawned = spawnWanderingMonster(wanderCfg.count_per_encounter);
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
  if (monsters.every(m => !m.alive || m.fled)) {
    log("All enemies are dead or fled. The exit is open.", "hit");
  }
}

function checkMorale(monster) {
  if (monster.moraleChecked || monster.fled || !monster.alive) return;
  if (monster.hp > monster.maxHp / 2) return;
  monster.moraleChecked = true;
  const roll = rollDie(6) + rollDie(6);
  if (roll > monster.morale) {
    monster.fled = true;
    log(`<b>${monster.name}</b> loses morale and flees!`, "miss");
    showFloatingText(monster.x, monster.y, "FLEE", 0x888888);
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
  if (!combatState || combatState.phase !== "player") return;
  if (!playerConscious()) {
    log("You are unconscious and cannot act.");
    return;
  }
  e.preventDefault();

  const [dx, dy] = dir;
  const tx = playerPos.x + dx;
  const ty = playerPos.y + dy;

  if (tx < 0 || tx >= MAP_W || ty < 0 || ty >= MAP_H) return;

  // Open adjacent closed door.
  if (mapData[ty] && mapData[ty][tx] === TILE.DOOR && !doorsOpened.has(`${tx},${ty}`)) {
    doorsOpened.add(`${tx},${ty}`);
    log(`${playerCharacter.name} opens a door.`);
    drawMap();
    renderFog();
    highlightReachable(playerPos, combatState.movementRemaining);
    saveGame();
    return;
  }

  // Attack adjacent monster.
  const target = monsterAt(tx, ty);
  if (target && distance(playerPos, { x: tx, y: ty }) === 1) {
    if (combatState.attacked) {
      log("You have already attacked this round.");
      return;
    }
    if (!findEquippedMeleeWeapon() && !findEquippedRangedWeapon()) {
      log("You have no weapon equipped.");
      return;
    }
    const backstab = isThief() && playerStealthed;
    await playerAttackMonster(target, false, 0, backstab);
    combatState.acted = true;
    combatState.attacked = true;
    clearStealth();
    updateCombatUI();
    checkEnd();
    saveGame();
    return;
  }

  // Move one tile if reachable.
  if (combatState.movementRemaining <= 0) return;
  const reachable = computeReachable(playerPos, combatState.movementRemaining);
  if (reachable.some(p => p.x === tx && p.y === ty)) {
    movePlayer(tx, ty);
    combatState.movementRemaining -= 1;
    log(`${playerCharacter.name} moves 10 ft.`);
    if (!isThief()) clearStealth();
    updateCombatUI();
    highlightReachable(playerPos, combatState.movementRemaining);
    highlightRangedTargets();
    await checkTileInteraction(tx, ty);
    saveGame();
  }
}

window.addEventListener("keydown", handleKeyDown);

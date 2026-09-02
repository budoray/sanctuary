/** Mercenary AI: auto-pilot hirelings during combat and exploration. */

const AUTO_MERC_KEY = "sanctuary_auto_mercs";
const MERC_AI_DELAY = 600;
const MERC_STEP_DELAY = 350;

let autoMercs = loadAutoMercSetting();

function loadAutoMercSetting() {
  try {
    const raw = localStorage.getItem(AUTO_MERC_KEY);
    return raw ? raw === "true" : true;
  } catch (e) {
    return true;
  }
}

function saveAutoMercSetting() {
  try {
    localStorage.setItem(AUTO_MERC_KEY, String(autoMercs));
  } catch (e) {
    console.warn("Failed to save auto-merc setting:", e);
  }
}

function setAutoMercs(value) {
  autoMercs = !!value;
  saveAutoMercSetting();
  syncAutoMercToggles();
}

function mercLog(character, msg) {
  log(`<span class="merc-action">${character.name}</span> ${msg}`, "merc-action");
}

function mercPotionEntry(character) {
  return character.sheet.inventory.items.find(i => i.item_id === "potion_of_healing" && (i.quantity || 1) > 0);
}

function mercHasPotion(character) {
  return !!mercPotionEntry(character);
}

async function useMercPotion(character) {
  const prevCharacter = playerCharacter;
  playerCharacter = character;
  try {
    const healed = await usePotion();
    return healed;
  } finally {
    playerCharacter = prevCharacter;
  }
}

function mercFindEquippedMeleeWeapon(character) {
  const inv = character.sheet.inventory.items;
  for (const entry of inv) {
    if (!entry.equipped) continue;
    const item = osricOptions.equipment.find(i => i.id === entry.item_id);
    if (item && item.category === "weapons" && !item.missile) return item;
  }
  return null;
}

function mercFindEquippedRangedWeapon(character) {
  const inv = character.sheet.inventory.items;
  for (const entry of inv) {
    if (!entry.equipped) continue;
    const item = osricOptions.equipment.find(i => i.id === entry.item_id);
    if (item && item.category === "weapons" && item.missile) return item;
  }
  return null;
}

function mercAmmoForWeapon(weapon) {
  if (!weapon) return null;
  if (weapon.id.includes("bow") || weapon.id === "arrows") return "arrows";
  if (weapon.id.includes("crossbow")) return "bolts";
  if (weapon.id === "sling") return "sling_bullet";
  return null;
}

function mercCountAmmo(character, ammoId) {
  const inv = character.sheet.inventory.items;
  const entry = inv.find(i => i.item_id === ammoId);
  return entry ? (entry.quantity || 1) : 0;
}

function mercCanUseRanged(character) {
  const weapon = mercFindEquippedRangedWeapon(character);
  if (!weapon) return false;
  const ammoId = mercAmmoForWeapon(weapon);
  if (!ammoId) return true;
  return mercCountAmmo(character, ammoId) > 0;
}

function mercAdjacentMonsters() {
  return monsters.filter(m => m.alive && distance(playerPos, { x: m.x, y: m.y }) === 1);
}

function mercNearestVisibleMonster() {
  const visible = computeVisibility();
  let best = null;
  let bestDist = Infinity;
  for (const m of monsters) {
    if (!m.alive) continue;
    if (!visible.has(`${m.x},${m.y}`)) continue;
    const d = distance(playerPos, { x: m.x, y: m.y });
    if (d < bestDist) {
      bestDist = d;
      best = m;
    }
  }
  return best;
}

function mercBestAttackSpell(character) {
  const spells = (osricOptions.spells && osricOptions.spells[character.class]) || [];
  const slots = character.sheet.spell_slots || {};
  for (const spell of spells) {
    const remaining = slots[spell.level] || slots[String(spell.level)] || 0;
    if (remaining <= 0) continue;
    if (spell.heal || spell.buff) continue;
    return spell;
  }
  return null;
}

function mercHasHealingSpell(character) {
  const spells = (osricOptions.spells && osricOptions.spells[character.class]) || [];
  const slots = character.sheet.spell_slots || {};
  return spells.some(spell => {
    if (!spell.heal) return false;
    const remaining = slots[spell.level] || slots[String(spell.level)] || 0;
    return remaining > 0;
  });
}

function mercBestMeleeTarget(adjacent) {
  return adjacent.slice().sort((a, b) => a.hp - b.hp)[0];
}

function mercConsciousThreshold() {
  return osricRules?.combat?.unconscious_threshold ?? 0;
}

function mercWoundedAllyForHealing(character) {
  const threshold = mercConsciousThreshold();
  let best = null;
  let bestPct = 0.5;
  for (const c of party) {
    if (!c.sheet || c.sheet.hit_points <= threshold) continue;
    if (c === character) continue;
    const pct = c.sheet.hit_points / c.sheet.max_hit_points;
    if (pct < bestPct) {
      bestPct = pct;
      best = c;
    }
  }
  if (!best && character.sheet.hit_points / character.sheet.max_hit_points < 0.5) {
    best = character;
  }
  return best;
}

async function mercCastHealingSpell(character, ally) {
  const spells = (osricOptions.spells && osricOptions.spells[character.class]) || [];
  const slots = character.sheet.spell_slots || {};
  const spell = spells.find(s => {
    if (!s.heal) return false;
    return (slots[s.level] || slots[String(s.level)] || 0) > 0;
  });
  if (!spell) return 0;

  const prevCharacter = playerCharacter;
  playerCharacter = character;
  try {
    const res = await api("/api/osric/spell", {
      method: "POST",
      body: JSON.stringify({ caster: character, spell_id: spell.id, target: null }),
    });
    const healed = res.result.heal || 0;
    const s = ally.sheet;
    const before = s.hit_points;
    s.hit_points = Math.min(s.max_hit_points, s.hit_points + healed);
    const actual = s.hit_points - before;

    // Sync the caster's spell slots back from the API response.
    character.sheet.spell_slots = res.character.sheet.spell_slots;
    if (typeof activePartyIndex === "number" && party[activePartyIndex] === character) {
      party[activePartyIndex] = character;
    }

    if (actual > 0) {
      showFloatingText(playerPos.x, playerPos.y, `+${actual}`, 0x5ac989);
      log(`${character.name} casts <b>${spell.name}</b> on <b>${ally.name}</b>, healing <span class="hit">${actual}</span> HP.`);
    }
    renderCharacterPanel();
    saveGame();
    return actual;
  } catch (err) {
    log(`<span class="damage">${err.message}</span>`);
    return 0;
  } finally {
    playerCharacter = prevCharacter;
  }
}

function mercAdjacentUnexploredDoor() {
  for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
    const nx = playerPos.x + dx, ny = playerPos.y + dy;
    if (nx < 0 || nx >= MAP_W || ny < 0 || ny >= MAP_H) continue;
    const t = mapData[ny][nx];
    if (t === TILE.DOOR && !doorsOpened.has(`${nx},${ny}`)) return { x: nx, y: ny };
    if (t === TILE.SECRET_DOOR && !secretDoorsDiscovered.has(`${nx},${ny}`)) return { x: nx, y: ny };
  }
  return null;
}

function mercFindSafeExploredTile(threatPos) {
  let best = null;
  let bestDist = distance(playerPos, threatPos);
  for (const key of explored) {
    const [x, y] = key.split(",").map(Number);
    if (!isWalkable(x, y)) continue;
    if (mapData[y][x] === TILE.TRAP) continue;
    if (monsterAt(x, y)) continue;
    const d = distance({ x, y }, threatPos);
    if (d > bestDist) {
      bestDist = d;
      best = { x, y };
    }
  }
  return best;
}

async function mercRetreatFrom(character, threatPos) {
  if (!combatState || combatState.movementRemaining <= 0) return false;
  const safeTile = mercFindSafeExploredTile(threatPos);
  const target = safeTile || playerPos;
  let moved = false;
  while (combatState.movementRemaining > 0) {
    const step = nextStepToward(playerPos, target);
    if (!step) break;
    if (!mercCanStepOn(step.x, step.y)) break;
    const dNow = distance(playerPos, threatPos);
    const dNext = distance(step, threatPos);
    if (dNext <= dNow && safeTile) break;
    movePlayer(step.x, step.y);
    combatState.movementRemaining -= 1;
    moved = true;
    await checkTileInteraction(step.x, step.y);
    saveGame();
    await new Promise(r => setTimeout(r, MERC_STEP_DELAY));
  }
  return moved;
}

async function mercAttackTarget(character, monster, ranged, backstab = false) {
  const prevCharacter = playerCharacter;
  playerCharacter = character;
  try {
    const d = distance(playerPos, { x: monster.x, y: monster.y });
    await playerAttackMonster(monster, ranged, ranged ? d * 10 : 0, backstab);
  } finally {
    playerCharacter = prevCharacter;
  }
}

async function mercCastSpell(character, spell, targetMonster) {
  const prevCharacter = playerCharacter;
  playerCharacter = character;
  try {
    await playerCastSpell(spell, targetMonster);
    if (typeof activePartyIndex === "number" && party[activePartyIndex]) {
      party[activePartyIndex] = playerCharacter;
    }
  } finally {
    playerCharacter = prevCharacter;
  }
}

function mercCanStepOn(x, y) {
  if (!isWalkable(x, y)) return false;
  if (monsterAt(x, y)) return false;
  if (mapData[y][x] === TILE.TRAP) return false;
  return true;
}

async function mercMoveTowards(character, targetPos) {
  if (!combatState || combatState.movementRemaining <= 0) return false;
  const step = nextStepToward(playerPos, targetPos);
  if (!step) return false;
  if (!mercCanStepOn(step.x, step.y)) return false;
  const reachable = computeReachable(playerPos, 1);
  if (!reachable.some(p => p.x === step.x && p.y === step.y)) return false;
  movePlayer(step.x, step.y);
  combatState.movementRemaining -= 1;
  mercLog(character, "moves toward the enemy.");
  updateCombatUI();
  highlightReachable(playerPos, combatState.movementRemaining);
  highlightRangedTargets();
  await checkTileInteraction(step.x, step.y);
  saveGame();
  return true;
}

function mercFindExploreTarget() {
  // Head for the exit if it has been seen.
  for (let y = 0; y < MAP_H; y++) {
    for (let x = 0; x < MAP_W; x++) {
      if (mapData[y][x] === TILE.EXIT && explored.has(`${x},${y}`)) {
        return { x, y };
      }
    }
  }
  // Otherwise pick the nearest walkable, unexplored tile adjacent to explored space.
  let best = null;
  let bestDist = Infinity;
  for (const key of explored) {
    const [x, y] = key.split(",").map(Number);
    for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
      const nx = x + dx, ny = y + dy;
      if (nx < 0 || nx >= MAP_W || ny < 0 || ny >= MAP_H) continue;
      if (explored.has(`${nx},${ny}`)) continue;
      if (!isWalkable(nx, ny)) continue;
      if (mapData[ny][nx] === TILE.TRAP) continue;
      const d = distance(playerPos, { x: nx, y: ny });
      if (d < bestDist) {
        bestDist = d;
        best = { x: nx, y: ny };
      }
    }
  }
  return best;
}

async function runMercenaryTurn(character, index) {
  if (!combatState || combatState.phase !== "player") return;
  if (combatState.partyActed?.has(index)) return;

  activePartyIndex = index;
  playerCharacter = character;
  renderCharacterPanel();
  updateCombatUI();

  if (isStuck(character)) {
    mercLog(character, "is stuck and ends their turn.");
    endTurn();
    return;
  }

  const hpPct = character.sheet.max_hit_points > 0 ? character.sheet.hit_points / character.sheet.max_hit_points : 1;
  const adjacent = mercAdjacentMonsters();
  const nearest = mercNearestVisibleMonster();
  const bossAdjacent = nearest?.boss && distance(playerPos, { x: nearest.x, y: nearest.y }) === 1;

  // 1. Drink a potion when badly wounded.
  if (hpPct <= 0.25 && mercHasPotion(character)) {
    mercLog(character, "is badly wounded and drinks a potion.");
    await useMercPotion(character);
    endTurn();
    return;
  }

  // 2. Retreat if badly wounded, out of potions, and overwhelmed.
  if (hpPct <= 0.25 && !mercHasPotion(character) && (adjacent.length >= 2 || bossAdjacent)) {
    const threat = nearest || (adjacent.length ? adjacent[0] : null);
    if (threat) {
      const retreated = await mercRetreatFrom(character, { x: threat.x, y: threat.y });
      if (retreated) {
        log(`<span class="merc-action">${character.name}</span> <span class="retreat">retreats</span> from the enemy.`, "merc-action retreat");
        endTurn();
        return;
      }
    }
  }

  // 3. Class-specific behaviour.
  if (character.class === "cleric") {
    if (adjacent.some(m => isUndead(m))) {
      await playerTurnUndead();
      endTurn();
      return;
    }
    const woundedAlly = mercWoundedAllyForHealing(character);
    if (woundedAlly && mercHasHealingSpell(character)) {
      const healed = await mercCastHealingSpell(character, woundedAlly);
      if (healed > 0) {
        mercLog(character, `heals <b>${woundedAlly.name}</b>.`);
        endTurn();
        return;
      }
    }
  }

  if (character.class === "thief") {
    if (nearest) {
      if (!playerStealthed && !combatState.attacked) {
        await playerSneak();
      }
      if (adjacent.length) {
        const target = mercBestMeleeTarget(adjacent);
        const backstab = playerStealthed;
        mercLog(character, backstab ? `backstabs <b>${target.name}</b>!` : `strikes at <b>${target.name}</b>.`);
        await mercAttackTarget(character, target, false, backstab);
        endTurn();
        return;
      }
    } else {
      const door = mercAdjacentUnexploredDoor();
      if (door && !combatState.acted) {
        pendingTrapSearch = true;
        searchTrapsAt(door.x, door.y);
        endTurn();
        return;
      }
    }
  }

  if (character.class === "magic_user") {
    // Keep distance from adjacent enemies.
    if (adjacent.length) {
      const retreated = await mercRetreatFrom(character, { x: adjacent[0].x, y: adjacent[0].y });
      if (retreated) {
        log(`<span class="merc-action">${character.name}</span> <span class="retreat">steps back</span> to cast.`, "merc-action retreat");
        endTurn();
        return;
      }
    }

    const spell = mercBestAttackSpell(character);
    if (spell && nearest) {
      mercLog(character, `casts <b>${spell.name}</b> at <b>${nearest.name}</b>.`);
      await mercCastSpell(character, spell, nearest);
      endTurn();
      return;
    }

    if (nearest && mercCanUseRanged(character)) {
      const weapon = mercFindEquippedRangedWeapon(character);
      const maxTiles = Math.floor((weapon?.range || 0) / 10);
      const d = distance(playerPos, { x: nearest.x, y: nearest.y });
      if (d <= maxTiles && d > 0) {
        mercLog(character, `shoots at <b>${nearest.name}</b>.`);
        await mercAttackTarget(character, nearest, true);
        endTurn();
        return;
      }
    }

    if (nearest && combatState.movementRemaining > 0) {
      const step = nextStepAway(playerPos, { x: nearest.x, y: nearest.y });
      if (step && mercCanStepOn(step.x, step.y)) {
        const reachable = computeReachable(playerPos, 1);
        if (reachable.some(p => p.x === step.x && p.y === step.y)) {
          movePlayer(step.x, step.y);
          combatState.movementRemaining -= 1;
          mercLog(character, "keeps distance from the enemy.");
          await checkTileInteraction(step.x, step.y);
          saveGame();
          endTurn();
          return;
        }
      }
    }

    // Last resort: close to melee only if there is no other option.
    if (nearest && adjacent.length) {
      const target = mercBestMeleeTarget(adjacent);
      mercLog(character, `swings at <b>${target.name}</b> as a last resort.`);
      await mercAttackTarget(character, target, false);
      endTurn();
      return;
    }
  }

  // 4. Default fighter-style behaviour: charge and melee.
  if (adjacent.length) {
    const target = mercBestMeleeTarget(adjacent);
    mercLog(character, `strikes at <b>${target.name}</b>.`);
    await mercAttackTarget(character, target, false);
    endTurn();
    return;
  }

  if (nearest && combatState.movementRemaining > 0) {
    let moved = false;
    while (combatState.movementRemaining > 0 && distance(playerPos, { x: nearest.x, y: nearest.y }) > 1) {
      const stepped = await mercMoveTowards(character, { x: nearest.x, y: nearest.y });
      if (!stepped) break;
      moved = true;
      await new Promise(r => setTimeout(r, MERC_STEP_DELAY));
    }
    if (moved) {
      const adjacentNow = mercAdjacentMonsters();
      if (adjacentNow.length && !combatState.attacked) {
        const target = mercBestMeleeTarget(adjacentNow);
        mercLog(character, `strikes at <b>${target.name}</b>.`);
        await mercAttackTarget(character, target, false);
      }
      endTurn();
      return;
    }
  }

  // 5. No monsters in sight: explore toward the exit or unexplored tiles.
  if (combatState.movementRemaining > 0) {
    const exploreTarget = mercFindExploreTarget();
    if (exploreTarget) {
      let moved = false;
      while (combatState.movementRemaining > 0) {
        const stepped = await mercMoveTowards(character, exploreTarget);
        if (!stepped) break;
        moved = true;
        await new Promise(r => setTimeout(r, MERC_STEP_DELAY));
      }
      if (moved) {
        endTurn();
        return;
      }
    }
  }

  mercLog(character, "holds position and ends their turn.");
  endTurn();
}

function createAutoMercToggle(id) {
  const label = document.createElement("label");
  label.id = id;
  label.className = "auto-merc-toggle";
  label.title = "Let mercenaries act automatically during combat.";
  label.innerHTML = `<input type="checkbox" ${autoMercs ? "checked" : ""}> <span>Auto Mercenaries</span>`;
  label.querySelector("input").addEventListener("change", (e) => {
    setAutoMercs(e.target.checked);
  });
  return label;
}

function syncAutoMercToggles() {
  document.querySelectorAll(".auto-merc-toggle input").forEach(input => {
    input.checked = autoMercs;
  });
}

function renderTownAutoMercToggle() {
  const townActions = document.querySelector(".town-actions");
  if (!townActions) return;
  if (!document.getElementById("town-auto-merc-toggle")) {
    townActions.insertBefore(createAutoMercToggle("town-auto-merc-toggle"), townActions.firstChild);
  }
}

function renderCombatAutoMercToggle() {
  const actionBar = document.getElementById("action-bar");
  if (!actionBar) return;
  if (!document.getElementById("combat-auto-merc-toggle")) {
    const spacer = actionBar.querySelector(".spacer");
    if (spacer && spacer.nextSibling) {
      actionBar.insertBefore(createAutoMercToggle("combat-auto-merc-toggle"), spacer.nextSibling);
    } else {
      actionBar.appendChild(createAutoMercToggle("combat-auto-merc-toggle"));
    }
  }
}

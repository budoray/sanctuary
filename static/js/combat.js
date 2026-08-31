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
  return playerCharacter && playerCharacter.sheet && playerCharacter.sheet.hit_points > -10;
}

function playerConscious() {
  return playerCharacter && playerCharacter.sheet && playerCharacter.sheet.hit_points > 0;
}

function formatCoins(cp) {
  if (cp >= 100) return `${Math.floor(cp / 100)} gp`;
  if (cp >= 10) return `${Math.floor(cp / 10)} sp`;
  return `${cp} cp`;
}



function initCombat() {
  initDungeon();
  document.getElementById("end-turn-btn").addEventListener("click", endTurn);
  renderSpellBar();
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
  };
  startRound();
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

function selectSpell(spell) {
  if (!combatState || combatState.phase !== "player") return;
  if (combatState.attacked) {
    log("You have already acted this round.");
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

function rollInitiative() {
  combatState.playerInitiative = rollDie(6);
  combatState.enemyInitiative = rollDie(6);
  const wentFirst = combatState.playerInitiative >= combatState.enemyInitiative ? "You" : "Enemies";
  log(`${wentFirst} win initiative (player ${combatState.playerInitiative}, enemy ${combatState.enemyInitiative}).`);
  combatState.phase = combatState.playerInitiative >= combatState.enemyInitiative ? "player" : "enemy";
  combatState.movementRemaining = tilesPerRound(playerCharacter.sheet.movement);
  combatState.acted = false;
  combatState.attacked = false;
  combatState.playerActedThisRound = false;
  combatState.enemyActedThisRound = false;
  pendingSpell = null;
}

function startRound() {
  rollInitiative();
  updateCombatUI();
  if (combatState.phase === "player") {
    highlightReachable(playerPos, combatState.movementRemaining);
    highlightRangedTargets();
  } else {
    setTimeout(enemyTurn, 600);
  }
}

function updateCombatUI() {
  const turnText = combatState.phase === "player"
    ? `Round ${combatState.round} — Your turn · Move ${combatState.movementRemaining} tiles`
    : `Round ${combatState.round} — Enemy turn`;
  document.getElementById("turn-badge").textContent = turnText;
  document.getElementById("end-turn-btn").disabled = combatState.phase !== "player";

  let hint;
  if (combatState.phase !== "player") {
    hint = "The dungeon stirs…";
  } else if (pendingSpell) {
    hint = `Click a monster to cast ${pendingSpell.name}.`;
  } else if (combatState.attacked) {
    hint = "You have attacked. Move or end your turn.";
  } else {
    const ranged = findEquippedRangedWeapon();
    hint = ranged
      ? "Click a highlighted tile to move, an adjacent monster to melee, or a circled monster to shoot."
      : "Click a highlighted tile to move, or click an adjacent monster to attack (once per round).";
  }
  document.getElementById("action-hint").textContent = hint;
  renderSpellBar();
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
  if (pendingSpell || findEquippedRangedWeapon()) {
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
    }
    return;
  }

  const targetMonster = monsterAt(gx, gy);

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
    await playerAttackMonster(targetMonster, false);
    combatState.acted = true;
    combatState.attacked = true;
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
    const d = distance(playerPos, { x: gx, y: gy });
    const maxTiles = Math.floor(findEquippedRangedWeapon().range / 10);
    if (d <= maxTiles) {
      await playerAttackMonster(targetMonster, true, d * 10);
      combatState.acted = true;
      combatState.attacked = true;
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
    updateCombatUI();
    highlightReachable(playerPos, combatState.movementRemaining);
    highlightRangedTargets();
    await checkTileInteraction(gx, gy);
  }
}

async function checkTileInteraction(x, y) {
  const t = mapData[y][x];
  if (t === TILE.CHEST && !chestsOpened.has(`${x},${y}`)) {
    openChest(x, y);
    const cp = rollDie(6) * 100;
    playerCharacter.remaining_gold += cp / 100;
    playerCharacter.sheet.xp += cp;
    log(`The chest holds <b>${formatCoins(cp)}</b> (${cp} XP).`, "hit");
    if (playerCharacter.sheet.xp >= playerCharacter.sheet.next_level_xp) {
      await levelUpCharacter();
    }
    renderCharacterPanel();
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

function triggerTrap(x, y) {
  trapsTriggered.add(`${x},${y}`);
  drawMap();
  const damage = rollDie(6);
  const saveTarget = playerCharacter.sheet.saving_throws.petrification_polymorph || 15;
  const saveRoll = rollDie(20);
  const saved = saveRoll >= saveTarget;
  const finalDamage = saved ? Math.max(1, Math.floor(damage / 2)) : damage;
  playerCharacter.sheet.hit_points = Math.max(0, playerCharacter.sheet.hit_points - finalDamage);
  renderCharacterPanel();
  showFloatingText(x, y, `-${finalDamage}`, 0xff6b6b);
  log(`A trap springs! Save roll <span class="roll">${saveRoll}</span> vs ${saveTarget}: ${saved ? '<span class="hit">saved</span>' : '<span class="miss">failed</span>'}. Take <span class="damage">${finalDamage}</span> damage.`);
  if (!playerAlive()) {
    showEnd(false, "Your hero has fallen to a hidden trap.");
  } else if (!playerConscious()) {
    showEnd(false, "Your hero has been knocked unconscious and is slain.");
  }
}

async function playerAttackMonster(monster, ranged = false, rangeFt = 0) {
  try {
    if (!ranged) {
      showAttackSlash(playerPos.x, playerPos.y, monster.x, monster.y, 0xd4a03d);
    } else {
      showAttackSlash(playerPos.x, playerPos.y, monster.x, monster.y, 0xff6b6b);
    }
    const res = await api("/api/osric/attack", {
      method: "POST",
      body: JSON.stringify({
        attacker: playerCharacter,
        defender: monsterToCombatant(monster),
        ranged,
        range_ft: rangeFt,
      }),
    });
    const action = ranged ? "shoots" : "attacks";
    const rangeNote = ranged && res.range_penalty ? ` (${res.range_penalty} range)` : "";
    log(`${res.attacker} ${action} ${res.defender}${rangeNote}: rolled <span class="roll">${res.raw_roll}</span> vs AC ${res.needed}. ${res.hit ? `<span class="hit">Hit</span> for <span class="damage">${res.damage}</span> damage` : '<span class="miss">Miss</span>'}.`);
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
    log(`<b>${playerCharacter.name} reaches level ${playerCharacter.sheet.level}!</b> HP ${playerCharacter.sheet.hit_points}, THAC0 ${playerCharacter.sheet.thac0}.`, "hit");
    renderCharacterPanel();
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
        showEnd(false, "Your hero has fallen.");
        return;
      }
      if (!playerConscious()) {
        showEnd(false, "Your hero is unconscious and overcome.");
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

function endTurn() {
  if (!combatState || combatState.phase !== "player") return;
  if (!playerConscious()) {
    log("You are unconscious and cannot act.");
    return;
  }
  combatState.playerActedThisRound = true;
  combatState.phase = "enemy";
  pendingSpell = null;
  clearHighlights();
  updateCombatUI();
  setTimeout(enemyTurn, 400);
}

async function enemyTurn() {
  const activeMonsters = monsters.filter(m => m.alive);
  for (const m of activeMonsters) {
    if (!playerAlive()) break;

    // Monsters can bash open adjacent doors.
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

    const speed = 6; // generic monster speed in tiles
    let moves = speed;
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
      if (!playerAlive()) break;
    }
  }

  combatState.enemyActedThisRound = true;

  if (!playerAlive()) {
    showEnd(false, "Your hero has fallen.");
    return;
  }

  if (!combatState.playerActedThisRound) {
    // Player lost initiative; now it's their turn in the same round.
    combatState.phase = "player";
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
    await playerAttackMonster(target, false);
    combatState.acted = true;
    combatState.attacked = true;
    updateCombatUI();
    checkEnd();
    return;
  }

  // Move one tile if reachable.
  if (combatState.movementRemaining <= 0) return;
  const reachable = computeReachable(playerPos, combatState.movementRemaining);
  if (reachable.some(p => p.x === tx && p.y === ty)) {
    movePlayer(tx, ty);
    combatState.movementRemaining -= 1;
    log(`${playerCharacter.name} moves 10 ft.`);
    updateCombatUI();
    highlightReachable(playerPos, combatState.movementRemaining);
    highlightRangedTargets();
    await checkTileInteraction(tx, ty);
  }
}

window.addEventListener("keydown", handleKeyDown);

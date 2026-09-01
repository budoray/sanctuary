/** Dungeon map generation and rendering. */

const TILE = {
  WALL: "#",
  FLOOR: ".",
  DOOR: "D",
  CHEST: "C",
  EXIT: "E",
  TRAP: "T",
};

let MAP_W = 22;
let MAP_H = 16;
let mapData = [];
let playerPos = { x: 1, y: 1 };
let monsters = [];
let chestsOpened = new Set();
let doorsOpened = new Set();
let trapsTriggered = new Set();
let trapsDiscovered = new Set();

let app = null;
let boardContainer = null;
let tileGraphics = null;
let tokenGraphics = null;
let highlightGraphics = null;
let fogGraphics = null;
let TILE_SIZE = 32;

const VISION_RADIUS = 6;
let explored = new Set();

function rollDie(sides) {
  return Math.floor(Math.random() * sides) + 1;
}

function makeEmptyMap() {
  return Array.from({ length: MAP_H }, () => Array(MAP_W).fill(TILE.WALL));
}

function carveRoom(grid, room) {
  for (let y = room.y; y < room.y + room.h; y++) {
    for (let x = room.x; x < room.x + room.w; x++) {
      if (y > 0 && y < MAP_H - 1 && x > 0 && x < MAP_W - 1) {
        grid[y][x] = TILE.FLOOR;
      }
    }
  }
}

function carveCorridor(grid, x1, y1, x2, y2) {
  let x = x1, y = y1;
  while (x !== x2) {
    grid[y][x] = TILE.FLOOR;
    x += x < x2 ? 1 : -1;
  }
  while (y !== y2) {
    grid[y][x] = TILE.FLOOR;
    y += y < y2 ? 1 : -1;
  }
  grid[y][x] = TILE.FLOOR;
}

function roomCenter(room) {
  return { x: Math.floor(room.x + room.w / 2), y: Math.floor(room.y + room.h / 2) };
}

function roomsOverlap(a, b) {
  return a.x - 1 <= b.x + b.w && a.x + a.w + 1 >= b.x &&
         a.y - 1 <= b.y + b.h && a.y + a.h + 1 >= b.y;
}

function generateDungeon() {
  const grid = makeEmptyMap();
  const roomGrid = makeEmptyMap();
  const rooms = [];
  const maxRooms = 12;
  const attempts = 80;

  for (let i = 0; i < attempts && rooms.length < maxRooms; i++) {
    const w = rollDie(4) + 2; // 3..6
    const h = rollDie(3) + 2; // 3..5
    const x = rollDie(MAP_W - w - 2);
    const y = rollDie(MAP_H - h - 2);
    const room = { x, y, w, h };
    if (rooms.some(r => roomsOverlap(r, room))) continue;
    carveRoom(grid, room);
    carveRoom(roomGrid, room);
    rooms.push(room);
  }

  // Connect each room to the previous with L-shaped corridors.
  for (let i = 1; i < rooms.length; i++) {
    const a = roomCenter(rooms[i - 1]);
    const b = roomCenter(rooms[i]);
    carveCorridor(grid, a.x, a.y, b.x, b.y);
  }

  // Place doors where corridors meet rooms.
  for (let y = 1; y < MAP_H - 1; y++) {
    for (let x = 1; x < MAP_W - 1; x++) {
      if (grid[y][x] !== TILE.FLOOR) continue;
      const isRoom = roomGrid[y][x] === TILE.FLOOR;
      const isCorridor = !isRoom;
      if (!isCorridor) continue;
      // Check if this corridor tile is adjacent to a room tile.
      let nextToRoom = false;
      for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
        if (roomGrid[y + dy][x + dx] === TILE.FLOOR) {
          nextToRoom = true;
          break;
        }
      }
      if (nextToRoom && Math.random() < 0.7) {
        grid[y][x] = TILE.DOOR;
      }
    }
  }

  // Scatter a few traps on corridor tiles (not in the start room).
  const trapCount = rollDie(2); // 1-2 traps
  let trapsPlaced = 0;
  const shuffled = [...rooms].sort(() => Math.random() - 0.5);
  const startRoom = shuffled[0];
  const startCenter = roomCenter(startRoom);
  for (let y = 1; y < MAP_H - 1 && trapsPlaced < trapCount; y++) {
    for (let x = 1; x < MAP_W - 1 && trapsPlaced < trapCount; x++) {
      if (grid[y][x] !== TILE.FLOOR) continue;
      if (roomGrid[y][x] === TILE.FLOOR) continue; // only corridors
      if (Math.abs(x - startCenter.x) + Math.abs(y - startCenter.y) <= 3) continue;
      if (Math.random() < 0.03) {
        grid[y][x] = TILE.TRAP;
        trapsPlaced++;
      }
    }
  }

  // Place player, exit, chest, and monsters.

  const exitRoom = shuffled[shuffled.length - 1];
  const chestRoom = shuffled[1];
  const used = new Set([startRoom, exitRoom, chestRoom]);
  const monsterRooms = shuffled.filter(r => !used.has(r));

  playerPos = roomCenter(startRoom);
  const exit = roomCenter(exitRoom);
  grid[exit.y][exit.x] = TILE.EXIT;
  const chest = roomCenter(chestRoom);
  grid[chest.y][chest.x] = TILE.CHEST;

  monsters = [];
  const monsterCount = Math.min(monsterRooms.length, 3 + rollDie(2)); // 4..5
  for (let i = 0; i < monsterCount; i++) {
    const r = monsterRooms[i % monsterRooms.length];
    const pos = roomCenter(r);
    if (distance(pos, playerPos) <= 2) continue;
    const roll = Math.random();
    const type = roll < 0.25 ? "Kobold" : roll < 0.55 ? "Goblin" : roll < 0.8 ? "Skeleton" : "Orc";
    const base = {
      Kobold:   { hp: 4,  maxHp: 4,  acDesc: 7, thac0: 20, damage: "1d4", xp: 7,  morale: 6 },
      Goblin:   { hp: 8,  maxHp: 8,  acDesc: 7, thac0: 20, damage: "1d6", xp: 15, morale: 7 },
      Skeleton: { hp: 12, maxHp: 12, acDesc: 7, thac0: 20, damage: "1d6", xp: 25, morale: 12 },
      Orc:      { hp: 16, maxHp: 16, acDesc: 6, thac0: 19, damage: "1d8", xp: 40, morale: 8 },
    }[type];
    const levelMult = 1 + (dungeonLevel - 1) * 0.35;
    const stats = {
      ...base,
      hp: Math.floor(base.hp * levelMult),
      maxHp: Math.floor(base.maxHp * levelMult),
      thac0: Math.max(1, base.thac0 - (dungeonLevel - 1)),
      xp: Math.floor(base.xp * levelMult),
    };
    monsters.push({
      id: `${type.toLowerCase()}-${pos.x}-${pos.y}-${dungeonLevel}`,
      name: type,
      x: pos.x,
      y: pos.y,
      ...stats,
      alive: true,
      fled: false,
      moraleChecked: false,
    });
  }

  mapData = grid;
  chestsOpened.clear();
  doorsOpened.clear();
  trapsTriggered.clear();
  trapsDiscovered.clear();
  explored.clear();
  computeVisibility();
}

function parseMap() {
  if (typeof loadDungeonModule === "function") {
    loadDungeonModule(dungeonModuleName || "crooked_tower");
  } else {
    generateDungeon();
  }
}

function initDungeon() {
  parseMap();
  const container = document.getElementById("board-canvas");
  if (app) app.destroy(true, { children: true });

  app = new PIXI.Application({
    width: container.clientWidth,
    height: container.clientHeight,
    background: "#1a1a1a",
    resolution: window.devicePixelRatio || 1,
    autoDensity: true,
  });
  container.appendChild(app.view);

  boardContainer = new PIXI.Container();
  app.stage.addChild(boardContainer);

  tileGraphics = new PIXI.Graphics();
  boardContainer.addChild(tileGraphics);

  highlightGraphics = new PIXI.Graphics();
  boardContainer.addChild(highlightGraphics);

  tokenGraphics = new PIXI.Container();
  boardContainer.addChild(tokenGraphics);

  fogGraphics = new PIXI.Graphics();
  boardContainer.addChild(fogGraphics);

  app.view.addEventListener("pointerdown", onBoardClick);
  window.addEventListener("resize", resizeDungeon);

  resizeDungeon();
}

function resizeDungeon() {
  if (!app) return;
  const container = document.getElementById("board-canvas");
  const w = container.clientWidth;
  const h = container.clientHeight;
  app.renderer.resize(w, h);

  TILE_SIZE = Math.floor(Math.min(w / MAP_W, h / MAP_H));
  const offsetX = (w - TILE_SIZE * MAP_W) / 2;
  const offsetY = (h - TILE_SIZE * MAP_H) / 2;
  boardContainer.position.set(offsetX, offsetY);

  drawMap();
  drawTokens();
  renderFog();
}

function drawMap() {
  if (!tileGraphics) return;
  tileGraphics.removeChildren();
  tileGraphics.clear();

  const wallColor = 0x2b2520;
  const wallEdge = 0x463a2d;
  const floorA = 0x1e1a16;
  const floorB = 0x242019;
  const hasTileArt = textureExists("/art/tile_floor.png");

  for (let y = 0; y < MAP_H; y++) {
    for (let x = 0; x < MAP_W; x++) {
      const t = mapData[y][x];
      const px = x * TILE_SIZE;
      const py = y * TILE_SIZE;

      if (t === TILE.WALL) {
        if (hasTileArt) {
          drawTileSprite("/art/tile_wall.png", x, y);
        } else {
          tileGraphics.beginFill(wallColor);
          tileGraphics.lineStyle(1, wallEdge, 1);
          tileGraphics.drawRect(px, py, TILE_SIZE, TILE_SIZE);
          tileGraphics.endFill();
          tileGraphics.beginFill(0x3d352c, 0.5);
          tileGraphics.drawRect(px + 2, py + 2, TILE_SIZE * 0.4, TILE_SIZE * 0.25);
          tileGraphics.endFill();
        }
      } else {
        if (hasTileArt) {
          const path = (x + y) % 2 === 0 ? "/art/tile_floor.png" : "/art/tile_floor_alt.png";
          drawTileSprite(path, x, y);
        } else {
          tileGraphics.beginFill((x + y) % 2 === 0 ? floorA : floorB);
          tileGraphics.lineStyle(1, 0x322a22, 0.6);
          tileGraphics.drawRect(px, py, TILE_SIZE, TILE_SIZE);
          tileGraphics.endFill();
        }

        if (t === TILE.DOOR && !doorsOpened.has(`${x},${y}`)) {
          drawTileSprite("/art/tile_door.png", x, y);
        } else if (t === TILE.CHEST && !chestsOpened.has(`${x},${y}`)) {
          drawFeatureSprite("/art/icon_chest.png", x, y);
        } else if (t === TILE.EXIT) {
          drawExitBeacon(x, y);
        } else if (t === TILE.TRAP && trapsTriggered.has(`${x},${y}`)) {
          drawFeatureIcon("trap", x, y, 0xc94a4a);
        } else if (t === TILE.TRAP && trapsDiscovered.has(`${x},${y}`)) {
          drawFeatureIcon("trap", x, y, 0xd4a03d);
        }
      }
    }
  }
}

function textureExists(path) {
  if (textureCache[path]) return true;
  // PIXI.Texture.from creates the texture immediately; we assume assets exist if generated.
  try {
    const t = PIXI.Texture.from(path);
    return t && t.baseTexture && !t.baseTexture._invalid;
  } catch (e) {
    return false;
  }
}

function drawTileSprite(path, x, y) {
  const sprite = new PIXI.Sprite(getTexture(path));
  sprite.position.set(x * TILE_SIZE, y * TILE_SIZE);
  sprite.width = TILE_SIZE;
  sprite.height = TILE_SIZE;
  tileGraphics.addChild(sprite);
}

function drawFeatureSprite(path, x, y) {
  const cx = x * TILE_SIZE + TILE_SIZE / 2;
  const cy = y * TILE_SIZE + TILE_SIZE / 2;
  const sprite = new PIXI.Sprite(getTexture(path));
  sprite.anchor.set(0.5);
  const scale = (TILE_SIZE * 0.75) / 32;
  sprite.scale.set(scale);
  sprite.position.set(cx, cy);
  tileGraphics.addChild(sprite);
}

function drawFeatureIcon(name, x, y, color) {
  const cx = x * TILE_SIZE + TILE_SIZE / 2;
  const cy = y * TILE_SIZE + TILE_SIZE / 2;
  const g = new PIXI.Graphics();
  g.beginFill(color, 0.2);
  g.lineStyle(2, color, 0.8);
  g.drawCircle(0, 0, TILE_SIZE * 0.35);
  g.endFill();
  g.position.set(cx, cy);
  tileGraphics.addChild(g);

  const text = new PIXI.Text(name === "chest" ? "C" : "?", {
    fontSize: TILE_SIZE * 0.45,
    fill: color,
    fontWeight: "bold",
  });
  text.anchor.set(0.5);
  text.position.set(cx, cy);
  tileGraphics.addChild(text);
}

function drawExitBeacon(x, y) {
  const cx = x * TILE_SIZE + TILE_SIZE / 2;
  const cy = y * TILE_SIZE + TILE_SIZE / 2;

  const sprite = new PIXI.Sprite(getTexture("/art/icon_beacon.png"));
  sprite.anchor.set(0.5);
  const scale = (TILE_SIZE * 0.8) / 32;
  sprite.scale.set(scale);
  sprite.position.set(cx, cy);
  tileGraphics.addChild(sprite);

  // Pulsing glow ring.
  const glow = new PIXI.Graphics();
  glow.beginFill(0xd4a03d, 0.15);
  glow.drawCircle(0, 0, TILE_SIZE * 0.45);
  glow.endFill();
  glow.position.set(cx, cy);
  tileGraphics.addChild(glow);
}

function drawEmoji(emoji, x, y) {
  const text = new PIXI.Text(emoji, { fontSize: TILE_SIZE * 0.6 });
  text.anchor.set(0.5);
  text.position.set(x * TILE_SIZE + TILE_SIZE / 2, y * TILE_SIZE + TILE_SIZE / 2);
  tileGraphics.addChild(text);
}

const textureCache = {};
function getTexture(path) {
  if (!textureCache[path]) {
    textureCache[path] = PIXI.Texture.from(path);
  }
  return textureCache[path];
}

function drawTokens() {
  if (!tokenGraphics) return;
  tokenGraphics.removeChildren();

  const visible = computeVisibility();

  // Player token.
  drawSpriteToken(playerPos.x, playerPos.y, "/art/player_token.png", true);

  // Monsters.
  for (const m of monsters) {
    if (!m.alive) continue;
    if (!visible.has(`${m.x},${m.y}`)) continue;
    const path = monsterTexturePath(m.name);
    drawSpriteToken(m.x, m.y, path, false, m.name);
  }
}

function monsterTexturePath(name) {
  if (!name) return null;
  const lower = name.toLowerCase();
  if (lower.includes("grik")) return "/art/monster_goblin_boss.png";
  if (lower.includes("drowned king")) return "/art/monster_drowned_king.png";
  const map = {
    Kobold: "/art/monster_kobold.png",
    "Giant Rat": "/art/monster_rat.png",
    Goblin: "/art/monster_goblin.png",
    Skeleton: "/art/monster_skeleton.png",
    Zombie: "/art/monster_zombie.png",
    Ghoul: "/art/monster_ghoul.png",
    Orc: "/art/monster_orc.png",
    Hobgoblin: "/art/monster_hobgoblin.png",
    Wight: "/art/monster_wight.png",
    "Giant Spider": "/art/monster_spider.png",
    Bandit: "/art/monster_bandit.png",
  };
  return map[name] || null;
}

function drawSpriteToken(x, y, path, isPlayer, name = "") {
  const cx = x * TILE_SIZE + TILE_SIZE / 2;
  const cy = y * TILE_SIZE + TILE_SIZE / 2;

  if (path) {
    const sprite = new PIXI.Sprite(getTexture(path));
    sprite.anchor.set(0.5);
    const scale = (TILE_SIZE * (isPlayer ? 0.9 : 0.82)) / 32;
    sprite.scale.set(scale);
    sprite.position.set(cx, cy);
    tokenGraphics.addChild(sprite);
    return;
  }

  // Fallback circle + letter.
  const label = isPlayer ? (playerCharacter ? classTokenLabel(playerCharacter.class) : "H") : (name ? name[0] : "?");
  const color = isPlayer ? 0xd4a03d : 0xc94a4a;
  drawFallbackToken(x, y, color, label, isPlayer);
}

function drawFallbackToken(x, y, color, label, isPlayer) {
  const cx = x * TILE_SIZE + TILE_SIZE / 2;
  const cy = y * TILE_SIZE + TILE_SIZE / 2;
  const radius = TILE_SIZE * (isPlayer ? 0.38 : 0.34);
  const g = new PIXI.Graphics();
  g.lineStyle(3, 0x0f0d0b, 1);
  g.drawCircle(0, 0, radius + 2);
  g.beginFill(color);
  g.drawCircle(0, 0, radius);
  g.endFill();
  g.beginFill(0xffffff, 0.15);
  g.drawCircle(-radius * 0.25, -radius * 0.25, radius * 0.35);
  g.endFill();
  g.position.set(cx, cy);
  tokenGraphics.addChild(g);

  const text = new PIXI.Text(label, {
    fontSize: TILE_SIZE * (isPlayer ? 0.5 : 0.45),
    fill: 0x1a1308,
    fontWeight: "bold",
  });
  text.anchor.set(0.5);
  text.position.set(cx, cy);
  tokenGraphics.addChild(text);
}

function classTokenLabel(classId) {
  return {
    fighter: "F",
    cleric: "C",
    magic_user: "M",
    thief: "T",
    druid: "D",
    paladin: "P",
    ranger: "R",
    illusionist: "I",
    assassin: "A",
  }[classId] || "H";
}

function isWalkable(x, y) {
  if (x < 0 || x >= MAP_W || y < 0 || y >= MAP_H) return false;
  const t = mapData[y][x];
  if (t === TILE.WALL) return false;
  if (t === TILE.DOOR && !doorsOpened.has(`${x},${y}`)) return false;
  return true;
}

function monsterAt(x, y) {
  return monsters.find(m => m.alive && m.x === x && m.y === y);
}

function distance(a, b) {
  return Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
}

function onBoardClick(e) {
  if (!combatState || combatState.phase !== "player") return;
  const rect = app.view.getBoundingClientRect();
  const scaleX = app.view.width / rect.width;
  const scaleY = app.view.height / rect.height;
  const px = (e.clientX - rect.left) * scaleX - boardContainer.x;
  const py = (e.clientY - rect.top) * scaleY - boardContainer.y;
  const gx = Math.floor(px / TILE_SIZE);
  const gy = Math.floor(py / TILE_SIZE);
  handleGridClick(gx, gy);
}

function highlightReachable(origin, range) {
  if (!highlightGraphics) return;
  highlightGraphics.clear();
  const reachable = computeReachable(origin, range);
  for (const p of reachable) {
    if (p.x === origin.x && p.y === origin.y) continue;
    highlightGraphics.beginFill(0xd4a03d, 0.18);
    highlightGraphics.lineStyle(1, 0xd4a03d, 0.55);
    highlightGraphics.drawRect(p.x * TILE_SIZE + 2, p.y * TILE_SIZE + 2, TILE_SIZE - 4, TILE_SIZE - 4);
    highlightGraphics.endFill();
  }
  return reachable;
}

function computeReachable(origin, range) {
  const queue = [{ ...origin, d: 0 }];
  const seen = new Set([`${origin.x},${origin.y}`]);
  const reachable = [];
  let head = 0;
  while (head < queue.length) {
    const cur = queue[head++];
    if (cur.d > 0) reachable.push({ x: cur.x, y: cur.y });
    if (cur.d >= range) continue;
    for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
      const nx = cur.x + dx, ny = cur.y + dy;
      const key = `${nx},${ny}`;
      if (seen.has(key)) continue;
      if (!isWalkable(nx, ny)) continue;
      if (monsterAt(nx, ny)) continue; // can't move through enemies
      seen.add(key);
      queue.push({ x: nx, y: ny, d: cur.d + 1 });
    }
  }
  return reachable;
}

function clearHighlights() {
  if (highlightGraphics) highlightGraphics.clear();
}

function movePlayer(x, y) {
  playerPos.x = x;
  playerPos.y = y;
  if (typeof checkRoomEntry === "function") checkRoomEntry(x, y);
  computeVisibility();
  drawTokens();
  renderFog();
}

function showFloatingText(x, y, text, color = 0xffffff) {
  if (!app || !boardContainer) return;
  const cx = x * TILE_SIZE + TILE_SIZE / 2;
  const cy = y * TILE_SIZE + TILE_SIZE / 2;
  const style = new PIXI.TextStyle({
    fontSize: TILE_SIZE * 0.55,
    fontWeight: "bold",
    fill: color,
    dropShadow: true,
    dropShadowColor: 0x000000,
    dropShadowDistance: 2,
    dropShadowBlur: 2,
  });
  const t = new PIXI.Text(text, style);
  t.anchor.set(0.5);
  t.position.set(cx, cy);
  boardContainer.addChild(t);

  let elapsed = 0;
  const duration = 900;
  const startY = cy;
  const tick = (delta) => {
    elapsed += app.ticker.elapsedMS;
    const p = Math.min(elapsed / duration, 1);
    t.position.y = startY - p * TILE_SIZE * 0.8;
    t.alpha = 1 - p;
    if (p >= 1) {
      app.ticker.remove(tick);
      t.destroy();
    }
  };
  app.ticker.add(tick);
}

function showAttackSlash(fromX, fromY, toX, toY, color = 0xffffff) {
  if (!app || !boardContainer) return;
  const fx = fromX * TILE_SIZE + TILE_SIZE / 2;
  const fy = fromY * TILE_SIZE + TILE_SIZE / 2;
  const tx = toX * TILE_SIZE + TILE_SIZE / 2;
  const ty = toY * TILE_SIZE + TILE_SIZE / 2;

  const g = new PIXI.Graphics();
  g.lineStyle(3, color, 0.9);
  g.moveTo(fx, fy);
  // A slight arc for slash effect.
  const mx = (fx + tx) / 2 + (ty - fy) * 0.15;
  const my = (fy + ty) / 2 - (tx - fx) * 0.15;
  g.quadraticCurveTo(mx, my, tx, ty);
  boardContainer.addChild(g);

  let elapsed = 0;
  const duration = 350;
  const tick = (delta) => {
    elapsed += app.ticker.elapsedMS;
    const p = Math.min(elapsed / duration, 1);
    g.alpha = 1 - p;
    if (p >= 1) {
      app.ticker.remove(tick);
      g.destroy();
    }
  };
  app.ticker.add(tick);
}

function computeVisibility() {
  const visible = new Set();
  const cx = playerPos.x;
  const cy = playerPos.y;

  // BFS out to VISION_RADIUS, stopping at walls.
  const queue = [{ x: cx, y: cy, d: 0 }];
  const seen = new Set([`${cx},${cy}`]);
  visible.add(`${cx},${cy}`);
  explored.add(`${cx},${cy}`);
  let head = 0;

  while (head < queue.length) {
    const cur = queue[head++];
    if (cur.d >= VISION_RADIUS) continue;
    for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
      const nx = cur.x + dx, ny = cur.y + dy;
      const key = `${nx},${ny}`;
      if (seen.has(key)) continue;
      if (nx < 0 || nx >= MAP_W || ny < 0 || ny >= MAP_H) continue;
      seen.add(key);
      explored.add(key);
      visible.add(key);
      // Light passes through floor/door/chest/exit but stops after walls.
      if (mapData[ny][nx] !== TILE.WALL) {
        queue.push({ x: nx, y: ny, d: cur.d + 1 });
      }
    }
  }
  return visible;
}

function renderFog() {
  if (!fogGraphics) return;
  fogGraphics.clear();
  const visible = computeVisibility();

  for (let y = 0; y < MAP_H; y++) {
    for (let x = 0; x < MAP_W; x++) {
      const key = `${x},${y}`;
      const px = x * TILE_SIZE;
      const py = y * TILE_SIZE;
      if (!visible.has(key)) {
        // Explored but not currently visible = dim memory.
        const alpha = explored.has(key) ? 0.55 : 0.92;
        fogGraphics.beginFill(0x050403, alpha);
        fogGraphics.drawRect(px, py, TILE_SIZE, TILE_SIZE);
        fogGraphics.endFill();
      }
    }
  }
}

async function killMonster(m) {
  m.alive = false;
  drawTokens();
  if (m.xp && playerCharacter && playerCharacter.sheet) {
    const gained = m.xp;
    playerCharacter.sheet.xp += gained;
    log(`${playerCharacter.name} gains <b>${gained} XP</b>.`, "hit");

    // Gold drop: 1d20 cp per HD, scaled by monster type.
    const goldRoll = Math.max(1, rollDie(20) * Math.max(1, Math.floor(m.maxHp / 4)));
    const goldGp = goldRoll / 100;
    playerCharacter.remaining_gold += goldGp;
    // OSRIC: 1 GP = 1 XP.
    playerCharacter.sheet.xp += Math.floor(goldGp * 100);
    showFloatingText(m.x, m.y, `+${goldGp.toFixed(1)}gp`, 0xd4a03d);
    log(`${m.name} drops <b>${formatCoins(goldRoll)}</b> (${Math.floor(goldGp * 100)} XP).`, "hit");

    if (playerCharacter.sheet.xp >= playerCharacter.sheet.next_level_xp) {
      await levelUpCharacter();
    }
    renderCharacterPanel();
    saveGame();
  }
}

function openChest(x, y) {
  chestsOpened.add(`${x},${y}`);
  drawMap();
}

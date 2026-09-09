/** Dungeon map generation and rendering. */

const TILE = {
  WALL: "#",
  FLOOR: ".",
  DOOR: "D",
  LOCKED_DOOR: "L",
  SECRET_DOOR: "S",
  CHEST: "C",
  EXIT: "E",
  TRAP: "T",
  BARREL: "B",
  WATER: "W",
};

let MAP_W = 22;
let MAP_H = 16;
let mapData = [];
let playerPos = { x: 1, y: 1 };
let monsters = [];
let chestsOpened = new Set();
let doorsOpened = new Set();
let doorsLocked = new Set();
let chestsWithKey = new Set();
let chestGoldGp = new Map();
let trapsTriggered = new Set();
let trapsDiscovered = new Set();
let trapData = new Map();
let secretDoorsDiscovered = new Set();
let barrelData = new Map(); // key "x,y" -> { hp, maxHp }

let app = null; // { view: canvas } — Canvas 2D, no Pixi
let canvas = null;
let ctx = null;
let boardContainer = { x: 0, y: 0 };
let highlightCells = [];
let pathCells = [];
let reachPrev = new Map();
let fxList = [];
let imageCache = {};
let fxRaf = 0;
let TILE_SIZE = 32;
const highlightGraphics = { clear() { highlightCells = []; requestDraw(); } };

const VISION_RADIUS = 6;
let explored = new Set();

function trapTypes() {
  // Prefer server-loaded OSRIC trap definitions; fall back to inline defaults.
  return osricRules?.traps?.traps || {
    pit: { name: "Pit", damage: "1d6", save: "petrification_polymorph", effect: "stuck" },
    poison_needle: { name: "Poison Needle", damage: "1d4", save: "death_paralysis_poison" },
    spike: { name: "Spike Trap", damage: "2d4", save: "breath_weapons" },
  };
}

function randomTrapType() {
  const keys = Object.keys(trapTypes());
  return keys[Math.floor(Math.random() * keys.length)];
}


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

function findDoorTileAdjacentToRoom(grid, roomGrid, roomId) {
  // Return a DOOR tile that sits on the boundary of the given room.
  for (let y = 1; y < MAP_H - 1; y++) {
    for (let x = 1; x < MAP_W - 1; x++) {
      if (grid[y][x] !== TILE.DOOR) continue;
      for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
        if (roomGrid[y + dy] && roomGrid[y + dy][x + dx] === roomId) {
          return { x, y };
        }
      }
    }
  }
  return null;
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
    const monsterId = pickEncounterMonster(dungeonLevel);
    if (!monsterId) continue;
    const template = getMonsterTemplate(monsterId);
    if (!template) continue;
    const stats = scaleMonsterStats(template, dungeonLevel);
    monsters.push({
      id: `${monsterId}-${pos.x}-${pos.y}-${dungeonLevel}`,
      name: template.name,
      hd: template.hd || 1,
      x: pos.x,
      y: pos.y,
      acDesc: stats.acDesc,
      ...stats,
      morale: template.morale,
      aiRole: template.ai_role || "brute",
      alive: true,
      fled: false,
      asleep: dungeonLevel > 1,
      moraleChecked: false,
      turned: 0,
    });
    if (typeof recordMonsterSeen === "function") recordMonsterSeen(template.name);
  }

  // Place environmental features (level 1 keeps them sparse and off critical paths).
  const maxBarrels = dungeonLevel === 1 ? 1 : 2 + rollDie(2);
  const maxWaterPools = dungeonLevel === 1 ? 1 : 2;
  placeBarrels(grid, rooms, startRoom, exitRoom, chestRoom, maxBarrels);
  placeWaterPools(grid, rooms, startRoom, exitRoom, chestRoom, maxWaterPools);

  mapData = grid;
  chestsOpened.clear();
  doorsOpened.clear();
  trapsTriggered.clear();
  trapsDiscovered.clear();
  secretDoorsDiscovered.clear();
  barrelData.clear();
  for (let y = 0; y < MAP_H; y++) {
    for (let x = 0; x < MAP_W; x++) {
      if (mapData[y][x] === TILE.TRAP) {
        trapData.set(`${x},${y}`, randomTrapType());
      } else if (mapData[y][x] === TILE.BARREL) {
        barrelData.set(`${x},${y}`, { hp: 1, maxHp: 1 });
      }
    }
  }
  computeVisibility();
}

function placeBarrels(grid, rooms, startRoom, exitRoom, chestRoom, count) {
  // Barrels go in non-essential rooms so they add cover/tactics without hard-locking progress.
  const candidates = rooms.filter(r => r !== startRoom && r !== exitRoom && r !== chestRoom);
  let placed = 0;
  for (let attempt = 0; attempt < 40 && placed < count; attempt++) {
    const room = candidates[Math.floor(Math.random() * candidates.length)];
    const x = room.x + rollDie(Math.max(1, room.w - 2));
    const y = room.y + rollDie(Math.max(1, room.h - 2));
    if (grid[y][x] !== TILE.FLOOR) continue;
    if (distance({ x, y }, roomCenter(room)) <= 1) continue; // keep center clear for combat
    // Don't block a corridor/door tile.
    let blocksCorridor = false;
    for (const [dx, dy] of [[0,1],[0,-1],[1,0],[-1,0],[1,1],[-1,-1],[1,-1],[-1,1]]) {
      const nx = x + dx, ny = y + dy;
      if (nx < 0 || nx >= MAP_W || ny < 0 || ny >= MAP_H) continue;
      if (grid[ny][nx] === TILE.DOOR || grid[ny][nx] === TILE.LOCKED_DOOR) {
        blocksCorridor = true;
        break;
      }
    }
    if (blocksCorridor) continue;
    grid[y][x] = TILE.BARREL;
    placed++;
  }
}

function placeWaterPools(grid, rooms, startRoom, exitRoom, chestRoom, count) {
  // Small water pools in non-essential rooms; each pool is 1-3 contiguous tiles.
  const candidates = rooms.filter(r => r !== startRoom && r !== exitRoom && r !== chestRoom);
  let placed = 0;
  for (let attempt = 0; attempt < 40 && placed < count; attempt++) {
    const room = candidates[Math.floor(Math.random() * candidates.length)];
    const centerX = room.x + Math.floor(room.w / 2);
    const centerY = room.y + Math.floor(room.h / 2);
    if (grid[centerY][centerX] !== TILE.FLOOR) continue;
    const pool = [{ x: centerX, y: centerY }];
    const size = dungeonLevel === 1 ? 1 : 1 + rollDie(2);
    let failures = 0;
    while (pool.length < size && failures < 20) {
      const base = pool[Math.floor(Math.random() * pool.length)];
      const dir = [[0,1],[0,-1],[1,0],[-1,0]][Math.floor(Math.random() * 4)];
      const nx = base.x + dir[0], ny = base.y + dir[1];
      if (nx < room.x || nx >= room.x + room.w || ny < room.y || ny >= room.y + room.h) { failures++; continue; }
      if (grid[ny][nx] !== TILE.FLOOR) { failures++; continue; }
      if (pool.some(p => p.x === nx && p.y === ny)) { failures++; continue; }
      pool.push({ x: nx, y: ny });
    }
    for (const p of pool) grid[p.y][p.x] = TILE.WATER;
    placed++;
  }
}

function parseMap() {
  if (typeof loadDungeonModule === "function") {
    loadDungeonModule(dungeonModuleName || "crooked_tower");
  } else {
    generateDungeon();
  }
}

function cssColor(n, a) {
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  return a == null ? `rgb(${r},${g},${b})` : `rgba(${r},${g},${b},${a})`;
}

function getImage(path) {
  if (!path) return null;
  if (imageCache[path]) return imageCache[path].complete && imageCache[path].naturalWidth ? imageCache[path] : null;
  const img = new Image();
  img.onload = () => requestDraw();
  img.src = path;
  imageCache[path] = img;
  return null;
}

function requestDraw() {
  if (!ctx || !canvas) return;
  paintBoard();
}

function initDungeon() {
  parseMap();
  const container = document.getElementById("board-canvas");
  container.innerHTML = "";
  canvas = document.createElement("canvas");
  canvas.setAttribute("aria-label", "Dungeon map");
  container.appendChild(canvas);
  ctx = canvas.getContext("2d");
  app = {
    view: canvas,
    ticker: { add() {}, remove() {}, elapsedMS: 16, speed: 1 },
    destroy() {},
  };
  canvas.addEventListener("pointerdown", onBoardClick);
  canvas.addEventListener("pointermove", onBoardHover);
  canvas.addEventListener("pointerleave", () => { pathCells = []; requestDraw(); });
  window.addEventListener("resize", resizeDungeon);
  [
    "/art/tile_floor.png", "/art/tile_floor_alt.png", "/art/tile_wall.png", "/art/tile_door.png",
    "/art/player_token.png", "/art/monster_kobold.png", "/art/monster_rat.png",
    "/art/monster_goblin.png", "/art/monster_goblin_boss.png",
    "/art/monster_skeleton.png", "/art/monster_zombie.png", "/art/monster_ghoul.png",
    "/art/monster_drowned_king.png",
    "/art/icon_chest.png", "/art/icon_beacon.png",
  ].forEach(getImage);
  if (!fxRaf) fxLoop();
  resizeDungeon();
}

function resizeDungeon() {
  if (!canvas || !ctx) return;
  const container = document.getElementById("board-canvas");
  const w = Math.max(1, container.clientWidth);
  const h = Math.max(1, container.clientHeight);
  canvas.width = w;
  canvas.height = h;
  ctx.imageSmoothingEnabled = false;
  TILE_SIZE = Math.max(16, Math.floor(Math.min(w / MAP_W, h / MAP_H)));
  boardContainer.x = Math.floor((w - TILE_SIZE * MAP_W) / 2);
  boardContainer.y = Math.floor((h - TILE_SIZE * MAP_H) / 2);
  requestDraw();
}

function fxLoop(ts) {
  fxRaf = requestAnimationFrame(fxLoop);
  if (!fxList.length) return;
  const now = ts || performance.now();
  fxList = fxList.filter((f) => now - f.t0 < f.dur);
  requestDraw();
}

function paintBoard() {
  const w = canvas.width, h = canvas.height;
  ctx.imageSmoothingEnabled = false;
  ctx.fillStyle = "#cbb896";
  ctx.fillRect(0, 0, w, h);
  ctx.save();
  ctx.translate(boardContainer.x, boardContainer.y);
  paintTiles();
  paintGrid();
  paintHighlights();
  paintPath();
  paintTokens();
  paintFog();
  paintFx();
  ctx.restore();
}

function paintGrid() {
  ctx.strokeStyle = "rgba(90, 60, 30, 0.22)";
  ctx.lineWidth = 1;
  for (let y = 0; y < MAP_H; y++) {
    for (let x = 0; x < MAP_W; x++) {
      ctx.strokeRect(x * TILE_SIZE + 0.5, y * TILE_SIZE + 0.5, TILE_SIZE - 1, TILE_SIZE - 1);
    }
  }
}

function drawMap() { requestDraw(); }

function fillTile(x, y, color) {
  ctx.fillStyle = color;
  ctx.fillRect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE);
}
function blit(path, x, y, scale = 1) {
  const img = getImage(path);
  const px = x * TILE_SIZE, py = y * TILE_SIZE;
  const s = TILE_SIZE * scale;
  if (img) {
    ctx.drawImage(img, px + (TILE_SIZE - s) / 2, py + (TILE_SIZE - s) / 2, s, s);
    return true;
  }
  return false;
}

function paintTiles() {
  if (!mapData.length) return;
  const visible = computeVisibility();
  for (let y = 0; y < MAP_H; y++) {
    for (let x = 0; x < MAP_W; x++) {
      const key = `${x},${y}`;
      if (!visible.has(key) && !explored.has(key)) continue;
      const t = mapData[y][x];
      if (t === TILE.WALL || t === TILE.SECRET_DOOR) {
        if (!blit("/art/tile_wall.png", x, y)) fillTile(x, y, "#2b2520");
      } else {
        const floor = (x + y) % 2 === 0 ? "/art/tile_floor.png" : "/art/tile_floor_alt.png";
        if (!blit(floor, x, y)) fillTile(x, y, (x + y) % 2 === 0 ? "#1e1a16" : "#242019");
        if ((t === TILE.DOOR || t === TILE.LOCKED_DOOR) && !doorsOpened.has(`${x},${y}`)) {
          blit("/art/tile_door.png", x, y);
          if (t === TILE.LOCKED_DOOR) {
            ctx.fillStyle = "#c94a4a";
            ctx.fillRect(x * TILE_SIZE + TILE_SIZE * 0.35, y * TILE_SIZE + TILE_SIZE * 0.4, TILE_SIZE * 0.3, TILE_SIZE * 0.25);
          }
        } else if (t === TILE.CHEST && !chestsOpened.has(`${x},${y}`)) {
          blit("/art/icon_chest.png", x, y, 0.8);
        } else if (t === TILE.EXIT) {
          ctx.fillStyle = "rgba(212,160,61,0.18)";
          ctx.beginPath();
          ctx.arc(x * TILE_SIZE + TILE_SIZE / 2, y * TILE_SIZE + TILE_SIZE / 2, TILE_SIZE * 0.45, 0, Math.PI * 2);
          ctx.fill();
          blit("/art/icon_beacon.png", x, y, 0.85);
        } else if (t === TILE.TRAP && (trapsTriggered.has(`${x},${y}`) || trapsDiscovered.has(`${x},${y}`))) {
          ctx.fillStyle = trapsTriggered.has(`${x},${y}`) ? "rgba(201,74,74,0.45)" : "rgba(212,160,61,0.45)";
          ctx.beginPath();
          ctx.arc(x * TILE_SIZE + TILE_SIZE / 2, y * TILE_SIZE + TILE_SIZE / 2, TILE_SIZE * 0.28, 0, Math.PI * 2);
          ctx.fill();
        } else if (t === TILE.WATER) {
          ctx.fillStyle = "rgba(42,77,102,0.75)";
          ctx.fillRect(x * TILE_SIZE + 2, y * TILE_SIZE + 2, TILE_SIZE - 4, TILE_SIZE - 4);
        } else if (t === TILE.BARREL && barrelData.has(`${x},${y}`)) {
          ctx.fillStyle = "#6b4423";
          ctx.fillRect(x * TILE_SIZE + TILE_SIZE * 0.22, y * TILE_SIZE + TILE_SIZE * 0.18, TILE_SIZE * 0.56, TILE_SIZE * 0.64);
        }
      }
    }
  }
}

function drawTokens() { requestDraw(); }

function paintTokens() {
  const visible = computeVisibility();
  paintSpriteToken(playerPos.x, playerPos.y, "/art/player_token.png", true, "H", 0xd4a03d);
  for (const m of monsters) {
    if (!m.alive) continue;
    if (!visible.has(`${m.x},${m.y}`)) continue;
    const path = monsterTexturePath(m.name);
    const fallback = m.aiRole === "healer" ? 0x5ac989 : (m.aiRole === "archer" ? 0x9b59b6 : 0xc94a4a);
    paintSpriteToken(m.x, m.y, path, false, m.name, fallback);
    if (typeof attackFocus !== "undefined" && attackFocus && monsterInAttackReach(m)) {
      paintAttackRing(m.x, m.y);
    }
    paintHealthBar(m.x, m.y, m.hp, m.maxHp);
    if (m.asleep) paintBadge(m.x, m.y, "z", "#888");
    else if (m.turned > 0) paintBadge(m.x, m.y, "T", "#d4a03d");
    else if (m.aiRole === "healer") paintBadge(m.x, m.y, "+", "#5ac989");
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

function paintSpriteToken(x, y, path, isPlayer, name, fallbackColor) {
  const scale = isPlayer ? 0.95 : 0.88;
  if (path && blit(path, x, y, scale)) return;
  const label = isPlayer ? (playerCharacter ? classTokenLabel(playerCharacter.class) : "H") : (name ? name[0] : "?");
  const cx = x * TILE_SIZE + TILE_SIZE / 2;
  const cy = y * TILE_SIZE + TILE_SIZE / 2;
  const radius = TILE_SIZE * (isPlayer ? 0.38 : 0.34);
  ctx.beginPath();
  ctx.arc(cx, cy, radius, 0, Math.PI * 2);
  ctx.fillStyle = cssColor(isPlayer ? 0xd4a03d : (fallbackColor || 0xc94a4a));
  ctx.fill();
  ctx.strokeStyle = "#0f0d0b";
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.fillStyle = "#1a1308";
  ctx.font = `bold ${Math.floor(TILE_SIZE * 0.45)}px Georgia, serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(label, cx, cy);
}

function paintBadge(x, y, label, color) {
  ctx.fillStyle = color;
  ctx.font = `bold ${Math.floor(TILE_SIZE * 0.32)}px Georgia, serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(label, x * TILE_SIZE + TILE_SIZE / 2, y * TILE_SIZE + TILE_SIZE * 0.14);
}

function paintAttackRing(x, y) {
  const cx = x * TILE_SIZE + TILE_SIZE / 2;
  const cy = y * TILE_SIZE + TILE_SIZE / 2;
  ctx.strokeStyle = "#c94a4a";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(cx, cy, TILE_SIZE * 0.46, 0, Math.PI * 2);
  ctx.stroke();
}

function paintHealthBar(x, y, hp, maxHp) {
  if (maxHp <= 0) return;
  const pct = Math.max(0, Math.min(1, hp / maxHp));
  const barW = TILE_SIZE * 0.7, barH = Math.max(3, TILE_SIZE * 0.1);
  const px = x * TILE_SIZE + (TILE_SIZE - barW) / 2;
  const py = y * TILE_SIZE + TILE_SIZE * 0.86;
  ctx.fillStyle = "#3a2a2a";
  ctx.fillRect(px, py, barW, barH);
  ctx.fillStyle = pct > 0.6 ? "#5ac989" : (pct > 0.3 ? "#d4a03d" : "#c94a4a");
  ctx.fillRect(px, py, barW * pct, barH);
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

function getMonsterTemplate(monsterId) {
  return osricMonsters?.monsters?.[monsterId] || null;
}

function pickEncounterMonster(level) {
  const table = osricMonsters?.encounter_tables?.[String(level)] || osricMonsters?.encounter_tables?.["1"] || [];
  if (!table.length) return null;
  const totalWeight = table.reduce((sum, e) => sum + (e.weight || 1), 0);
  let roll = Math.random() * totalWeight;
  for (const entry of table) {
    roll -= entry.weight || 1;
    if (roll <= 0) return entry.id;
  }
  return table[table.length - 1].id;
}

function weakenDamageExpression(damageExpr, level) {
  // On level 1, young or malnourished monsters deal slightly less damage.
  if (level !== 1 || !damageExpr) return damageExpr;
  const match = String(damageExpr).match(/^(\d+)d(\d+)(.*)$/);
  if (!match) return damageExpr;
  const count = parseInt(match[1], 10);
  let sides = parseInt(match[2], 10);
  const rest = match[3] || "";
  sides = Math.max(2, sides - 1);
  return `${count}d${sides}${rest}`;
}

function scaleMonsterStats(base, level) {
  // Level 1 is the tutorial band: give the player a slight edge by reducing
  // monster HP, damage, and AC. Deeper levels scale up normally.
  const levelMult = level === 1 ? 0.6 : 1 + (level - 1) * 0.35;
  const acDesc = Math.min(10, (base.ac_descending || 10) + (level === 1 ? 1 : -(level - 1)));
  return {
    hp: Math.max(1, Math.floor((base.hp || 1) * levelMult)),
    maxHp: Math.max(1, Math.floor((base.max_hp || base.hp || 1) * levelMult)),
    thac0: Math.max(1, (base.thac0 || 20) - (level - 1)),
    xp: Math.floor((base.xp || 1) * levelMult),
    damage: weakenDamageExpression(base.damage, level),
    acDesc: acDesc,
  };
}

function findMonsterIdByName(name) {
  const monsters = osricMonsters?.monsters || {};
  const direct = name.toLowerCase().replace(/\s+/g, "_");
  if (monsters[direct]) return direct;
  for (const [id, tpl] of Object.entries(monsters)) {
    if (tpl.name && tpl.name.toLowerCase() === name.toLowerCase()) return id;
  }
  return null;
}

function isWalkable(x, y) {
  if (x < 0 || x >= MAP_W || y < 0 || y >= MAP_H) return false;
  const t = mapData[y][x];
  if (t === TILE.WALL) return false;
  if (t === TILE.SECRET_DOOR) return false;
  if (t === TILE.DOOR && !doorsOpened.has(`${x},${y}`)) return false;
  if (t === TILE.LOCKED_DOOR && !doorsOpened.has(`${x},${y}`)) return false;
  if (t === TILE.BARREL && !barrelData.has(`${x},${y}`)) return false; // destroyed barrels removed separately
  if (t === TILE.BARREL) return false;
  return true;
}

function isObstacle(x, y) {
  // Obstacles block movement and ranged line of sight.
  if (x < 0 || x >= MAP_W || y < 0 || y >= MAP_H) return true;
  const t = mapData[y][x];
  return t === TILE.WALL || t === TILE.SECRET_DOOR || t === TILE.BARREL ||
         (t === TILE.DOOR && !doorsOpened.has(`${x},${y}`)) ||
         (t === TILE.LOCKED_DOOR && !doorsOpened.has(`${x},${y}`));
}

function isDifficultTerrain(x, y) {
  if (x < 0 || x >= MAP_W || y < 0 || y >= MAP_H) return false;
  return mapData[y][x] === TILE.WATER;
}

function movementCost(x, y) {
  return isDifficultTerrain(x, y) ? 2 : 1;
}

function monsterAt(x, y) {
  return monsters.find(m => m.alive && m.x === x && m.y === y);
}

function distance(a, b) {
  return Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
}

function hasRangedLineOfSight(from, to) {
  // Simple grid line traversal (Bresenham-style). Barrels and walls block.
  if (!from || !to) return false;
  if (from.x === to.x && from.y === to.y) return true;
  let x = from.x, y = from.y;
  const dx = Math.abs(to.x - from.x), dy = Math.abs(to.y - from.y);
  const sx = from.x < to.x ? 1 : -1;
  const sy = from.y < to.y ? 1 : -1;
  let err = dx - dy;
  while (true) {
    if (x === to.x && y === to.y) return true;
    const e2 = 2 * err;
    if (e2 > -dy) { err -= dy; x += sx; }
    else if (e2 < dx) { err += dx; y += sy; }
    else { err += dx - dy; x += sx; y += sy; }
    // Skip the starting tile; check every tile up to and including target.
    if (x === to.x && y === to.y) return true;
    if (isObstacle(x, y)) return false;
  }
}

function destroyBarrel(x, y) {
  const key = `${x},${y}`;
  if (!barrelData.has(key)) return false;
  barrelData.delete(key);
  mapData[y][x] = TILE.FLOOR;
  log(`<span class="damage">The barrel smashes apart!</span>`, "damage");
  drawMap();
  renderFog();
  return true;
}

function pushBarrel(x, y, dx, dy) {
  // Push a barrel from (x,y) one tile in direction (dx,dy) if the destination is free.
  // The pusher steps into the barrel's old tile.
  const key = `${x},${y}`;
  if (mapData[y][x] !== TILE.BARREL || !barrelData.has(key)) return false;
  const nx = x + dx, ny = y + dy;
  if (nx < 0 || nx >= MAP_W || ny < 0 || ny >= MAP_H) return false;
  if (!isWalkable(nx, ny)) return false;
  if (monsterAt(nx, ny)) return false;
  const data = barrelData.get(key);
  barrelData.delete(key);
  mapData[y][x] = TILE.FLOOR;
  mapData[ny][nx] = TILE.BARREL;
  barrelData.set(`${nx},${ny}`, data);
  log(`${playerCharacter.name} pushes a barrel.`);
  movePlayer(x, y);
  drawMap();
  renderFog();
  return true;
}

function gridFromEvent(e) {
  const rect = canvas.getBoundingClientRect();
  const px = e.clientX - rect.left - boardContainer.x;
  const py = e.clientY - rect.top - boardContainer.y;
  return { gx: Math.floor(px / TILE_SIZE), gy: Math.floor(py / TILE_SIZE) };
}

function onBoardClick(e) {
  if (!combatState || combatState.phase !== "player") return;
  stopAutoExplore();
  const { gx, gy } = gridFromEvent(e);
  handleGridClick(gx, gy);
}

function onBoardHover(e) {
  if (!combatState || combatState.phase !== "player") return;
  if (typeof isActing === "function" && isActing()) return;
  if (document.getElementById("dice-tray")?.classList.contains("open")) return;
  const { gx, gy } = gridFromEvent(e);
  if (!highlightCells.some((p) => p.x === gx && p.y === gy)) {
    if (pathCells.length) { pathCells = []; requestDraw(); }
    return;
  }
  const next = pathTo(gx, gy);
  if (next.length === pathCells.length && next.every((p, i) => p.x === pathCells[i].x && p.y === pathCells[i].y)) return;
  pathCells = next;
  requestDraw();
}

function highlightReachable(origin, range) {
  const reachable = computeReachable(origin, range);
  highlightCells = reachable.filter((p) => p.x !== origin.x || p.y !== origin.y);
  requestDraw();
  return reachable;
}

function paintHighlights() {
  ctx.fillStyle = "rgba(212,160,61,0.38)";
  ctx.strokeStyle = "rgba(255, 210, 90, 0.95)";
  ctx.lineWidth = 2;
  for (const p of highlightCells) {
    ctx.fillRect(p.x * TILE_SIZE + 3, p.y * TILE_SIZE + 3, TILE_SIZE - 6, TILE_SIZE - 6);
    ctx.strokeRect(p.x * TILE_SIZE + 3, p.y * TILE_SIZE + 3, TILE_SIZE - 6, TILE_SIZE - 6);
  }
}

function paintPath() {
  if (!pathCells.length) return;
  ctx.fillStyle = "#5aa8d4";
  ctx.strokeStyle = "rgba(90, 168, 212, 0.9)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  const sx = playerPos.x * TILE_SIZE + TILE_SIZE / 2;
  const sy = playerPos.y * TILE_SIZE + TILE_SIZE / 2;
  ctx.moveTo(sx, sy);
  for (const p of pathCells) {
    ctx.lineTo(p.x * TILE_SIZE + TILE_SIZE / 2, p.y * TILE_SIZE + TILE_SIZE / 2);
  }
  ctx.stroke();
  const end = pathCells[pathCells.length - 1];
  ctx.beginPath();
  ctx.arc(end.x * TILE_SIZE + TILE_SIZE / 2, end.y * TILE_SIZE + TILE_SIZE / 2, Math.max(3, TILE_SIZE * 0.14), 0, Math.PI * 2);
  ctx.fill();
}

function computeReachable(origin, range) {
  // Weighted Dijkstra over the grid. Difficult terrain (water) costs 2.
  const startKey = `${origin.x},${origin.y}`;
  const dist = new Map([[startKey, 0]]);
  const prev = new Map();
  const queue = [{ x: origin.x, y: origin.y, d: 0 }];
  const reachable = [];
  let head = 0;
  while (head < queue.length) {
    const cur = queue[head++];
    if (cur.d > 0) reachable.push({ x: cur.x, y: cur.y, cost: cur.d });
    for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
      const nx = cur.x + dx, ny = cur.y + dy;
      const key = `${nx},${ny}`;
      if (!isWalkable(nx, ny)) continue;
      if (monsterAt(nx, ny)) continue; // can't move through enemies
      const nd = cur.d + movementCost(nx, ny);
      if (nd > range) continue;
      if (dist.has(key) && dist.get(key) <= nd) continue;
      dist.set(key, nd);
      prev.set(key, `${cur.x},${cur.y}`);
      queue.push({ x: nx, y: ny, d: nd });
    }
  }
  reachPrev = prev;
  return reachable;
}

function pathTo(tx, ty) {
  const cells = [];
  let key = `${tx},${ty}`;
  const seen = new Set();
  while (reachPrev.has(key) && !seen.has(key)) {
    seen.add(key);
    const [x, y] = key.split(",").map(Number);
    cells.push({ x, y });
    key = reachPrev.get(key);
  }
  return cells.reverse();
}

function clearHighlights() {
  highlightCells = [];
  pathCells = [];
  requestDraw();
}

function movePlayer(x, y) {
  playerPos.x = x;
  playerPos.y = y;
  if (window.SanctuaryAudio) window.SanctuaryAudio.play("step");
  if (typeof checkRoomEntry === "function") checkRoomEntry(x, y);
  computeVisibility();
  drawTokens();
  renderFog();
  if (typeof tutorialManager !== "undefined" && tutorialManager) {
    tutorialManager.onPlayerMoved();
  }
}

function showFloatingText(x, y, text, color = 0xffffff) {
  fxList.push({ kind: "text", x, y, text, color, t0: performance.now(), dur: 500 });
}

function showAttackSlash(fromX, fromY, toX, toY, color = 0xffffff) {
  fxList.push({ kind: "slash", fromX, fromY, toX, toY, color, t0: performance.now(), dur: 220 });
}

function paintFx() {
  const now = performance.now();
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  for (const f of fxList) {
    const p = Math.min(1, (now - f.t0) / f.dur);
    if (f.kind === "text") {
      ctx.globalAlpha = 1 - p;
      ctx.fillStyle = cssColor(f.color);
      ctx.font = `bold ${Math.floor(TILE_SIZE * 0.5)}px Georgia, serif`;
      ctx.fillText(f.text, f.x * TILE_SIZE + TILE_SIZE / 2, f.y * TILE_SIZE + TILE_SIZE / 2 - p * TILE_SIZE * 0.8);
    } else if (f.kind === "slash") {
      ctx.globalAlpha = 1 - p;
      ctx.strokeStyle = cssColor(f.color);
      ctx.lineWidth = 3;
      const fx = f.fromX * TILE_SIZE + TILE_SIZE / 2;
      const fy = f.fromY * TILE_SIZE + TILE_SIZE / 2;
      const tx = f.toX * TILE_SIZE + TILE_SIZE / 2;
      const ty = f.toY * TILE_SIZE + TILE_SIZE / 2;
      ctx.beginPath();
      ctx.moveTo(fx, fy);
      ctx.quadraticCurveTo((fx + tx) / 2 + (ty - fy) * 0.15, (fy + ty) / 2 - (tx - fx) * 0.15, tx, ty);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }
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
      // Light passes through floor/door/chest/exit but stops after walls/barrels.
      const t = mapData[ny][nx];
      if (t !== TILE.WALL && t !== TILE.BARREL && t !== TILE.SECRET_DOOR) {
        queue.push({ x: nx, y: ny, d: cur.d + 1 });
      }
    }
  }
  return visible;
}

function isVisibleToPlayer(x, y) {
  return computeVisibility().has(`${x},${y}`);
}

function renderFog() { requestDraw(); }

function paintFog() {
  const visible = computeVisibility();
  for (let y = 0; y < MAP_H; y++) {
    for (let x = 0; x < MAP_W; x++) {
      const key = `${x},${y}`;
      if (visible.has(key)) continue;
      if (explored.has(key)) {
        ctx.fillStyle = "rgba(80, 52, 28, 0.42)";
        ctx.fillRect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE);
      }
    }
  }
}

async function killMonster(m) {
  m.alive = false;
  if (typeof recordMonsterKilled === "function") recordMonsterKilled(m.name);
  if (typeof tutorialManager !== "undefined" && tutorialManager && tutorialManager.onMonsterKilled) {
    tutorialManager.onMonsterKilled();
  }
  if (window.SanctuaryAudio) window.SanctuaryAudio.play("monster_death");
  drawTokens();
  if (typeof checkGroupMorale === "function") checkGroupMorale();
  if (m.xp && playerCharacter && playerCharacter.sheet) {
    const gained = m.xp;
    playerCharacter.sheet.xp += gained;
    log(`${playerCharacter.name} gains <b>${gained} XP</b>.`, "hit");

    if (m.gold_gp) {
      playerCharacter.remaining_gold += m.gold_gp;
      playerCharacter.sheet.xp += Math.floor(m.gold_gp);
      showFloatingText(m.x, m.y, `+${m.gold_gp}gp`, 0xd4a03d);
      log(`${m.name} drops <b>${m.gold_gp} gp</b> (${Math.floor(m.gold_gp)} XP).`, "hit");
    } else {
      const goldRoll = Math.max(1, rollDie(20) * (m.hd || 1));
      const goldGp = goldRoll / 100;
      playerCharacter.remaining_gold += goldGp;
      playerCharacter.sheet.xp += Math.floor(goldGp * 100);
      showFloatingText(m.x, m.y, `+${goldGp.toFixed(1)}gp`, 0xd4a03d);
      log(`${m.name} drops <b>${formatCoins(goldRoll)}</b> (${Math.floor(goldGp * 100)} XP).`, "hit");
    }

    if (typeof maybeLevelUp === "function") await maybeLevelUp();
    else if (playerCharacter.sheet.xp >= playerCharacter.sheet.next_level_xp) {
      await levelUpCharacter();
    }
    renderCharacterPanel();
    saveGame();
  }
}

function openChest(x, y) {
  chestsOpened.add(`${x},${y}`);
  if (window.SanctuaryAudio) window.SanctuaryAudio.play("chest_open");
  drawMap();
}

function findSpawnTiles(minDistance) {
  const tiles = [];
  for (let y = 1; y < MAP_H - 1; y++) {
    for (let x = 1; x < MAP_W - 1; x++) {
      if (!isWalkable(x, y)) continue;
      if (monsterAt(x, y)) continue;
      if (x === playerPos.x && y === playerPos.y) continue;
      if (distance({ x, y }, playerPos) >= minDistance) {
        tiles.push({ x, y });
      }
    }
  }
  return tiles;
}

function wanderingMonsterCheck(cfg) {
  // Level 1 is the tutorial band: fewer wanderers, so first-time players can
  // clear the map. Deeper levels use the configured chance.
  const baseChance = cfg.chance_in_6 ?? 1;
  const die = dungeonLevel === 1 ? 12 : 6;
  return rollDie(die) <= baseChance;
}

function wanderingMonsterCount(cfg) {
  // Tutorial level spawns single wanderers; deeper levels use the config.
  return dungeonLevel === 1 ? "1" : (cfg.count_per_encounter ?? "1");
}

function maybeSpawnWanderingMonster() {
  // Level 1 is the tutorial band: no wandering monsters so the run is
  // deterministic and first-time players aren't punished by chase loops.
  if (dungeonLevel === 1) return 0;
  const cfg = combatConfig().wandering_monsters || {};
  if (!cfg.enabled) return 0;
  if (!isCombatSafe()) return 0;
  if (!wanderingMonsterCheck(cfg)) return 0;
  const spawned = spawnWanderingMonster(wanderingMonsterCount(cfg));
  if (spawned) {
    log(`<span class="damage">Wandering monsters appear!</span>`, "damage");
  }
  return spawned;
}

/** Tutorial system for the Crooked Tower starter dungeon. */
let tutorialManager = null;
let tutorialHintsShown = new Set();

class TutorialManager {
  constructor() {
    this.toastEl = null;
    this.dismissTimer = null;
    this.actedTimer = null;
    this.hasAttacked = false;
    this.hasActedThisTurn = false;
    this.createToast();
  }

  static isActive() {
    return currentModule && currentModule.tutorial === true;
  }

  createToast() {
    let el = document.getElementById("tutorial-toast");
    if (!el) {
      el = document.createElement("div");
      el.id = "tutorial-toast";
      el.className = "tutorial-toast";
      el.innerHTML = `<div class="tutorial-title">Hint</div><div class="tutorial-text"></div><span class="tutorial-dismiss">Click to dismiss</span>`;
      document.body.appendChild(el);
      el.addEventListener("click", () => this.hideToast());
    }
    this.toastEl = el;
  }

  showToast(text, title = "Hint") {
    if (!this.toastEl) return;
    this.toastEl.querySelector(".tutorial-title").textContent = title;
    this.toastEl.querySelector(".tutorial-text").textContent = text;
    this.toastEl.classList.add("visible");
    if (this.dismissTimer) clearTimeout(this.dismissTimer);
    this.dismissTimer = setTimeout(() => this.hideToast(), 6000);
  }

  hideToast() {
    if (!this.toastEl) return;
    this.toastEl.classList.remove("visible");
    if (this.dismissTimer) {
      clearTimeout(this.dismissTimer);
      this.dismissTimer = null;
    }
  }

  showOnce(id, text, title = "Hint") {
    if (tutorialHintsShown.has(id)) return false;
    tutorialHintsShown.add(id);
    log(`<span class="hit">${title}:</span> ${text}`, "hit");
    this.showToast(text, title);
    return true;
  }

  onDungeonStart() {
    if (!TutorialManager.isActive()) return;
    const steps = currentModule.tutorial_steps || [];
    const welcome = steps.find(s => s.id === "welcome");
    if (welcome) this.showOnce("welcome", welcome.text);
    this.checkConditions();
  }

  onRoomEntered(roomId) {
    if (!TutorialManager.isActive()) return;
    const steps = currentModule.tutorial_steps || [];
    const step = steps.find(s => s.id === "room");
    if (step) this.showOnce("room", step.text);
    if (roomId === currentModule.exitRoom) {
      const exitStep = steps.find(s => s.id === "exit");
      if (exitStep) this.showOnce("exit", exitStep.text);
    }
    this.checkConditions();
  }

  onPlayerMoved() {
    if (!TutorialManager.isActive()) return;
    this.checkConditions();
  }

  onPlayerAttacked() {
    if (!TutorialManager.isActive()) return;
    if (!this.hasAttacked) {
      this.hasAttacked = true;
      const steps = currentModule.tutorial_steps || [];
      const step = steps.find(s => s.id === "attack");
      if (step) this.showOnce("attack", step.text);
    }
  }

  onTrapTriggered() {
    if (!TutorialManager.isActive()) return;
    const steps = currentModule.tutorial_steps || [];
    const step = steps.find(s => s.id === "trap");
    if (step) this.showOnce("trap", step.text);
  }

  onChestOpened() {
    if (!TutorialManager.isActive()) return;
    const steps = currentModule.tutorial_steps || [];
    const step = steps.find(s => s.id === "chest");
    if (step) this.showOnce("chest", step.text);
  }

  onMonsterKilled() {
    if (!TutorialManager.isActive()) return;
  }

  onWounded() {
    if (!TutorialManager.isActive()) return;
    const steps = currentModule.tutorial_steps || [];
    const step = steps.find((s) => s.id === "rest");
    if (step) this.showOnce("rest", step.text);
  }

  checkConditions() {
    if (!TutorialManager.isActive()) return;
    const px = playerPos.x, py = playerPos.y;
    const visible = computeVisibility();

    // Door proximity.
    for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
      const nx = px + dx, ny = py + dy;
      if (nx < 0 || nx >= MAP_W || ny < 0 || ny >= MAP_H) continue;
      if (mapData[ny][nx] === TILE.DOOR && !doorsOpened.has(`${nx},${ny}`)) {
        const steps = currentModule.tutorial_steps || [];
        const step = steps.find(s => s.id === "door");
        if (step) this.showOnce("door", step.text);
        break;
      }
    }

    // Monster visibility.
    const visibleMonster = monsters.find(m => m.alive && visible.has(`${m.x},${m.y}`));
    if (visibleMonster) {
      const steps = currentModule.tutorial_steps || [];
      const step = steps.find(s => s.id === "monster");
      if (step) this.showOnce("monster", step.text);
    }

    // Boss proximity.
    const boss = monsters.find(m => m.alive && m.name && (m.name.includes("Grik") || m.name.includes("Drowned King")));
    if (boss && visible.has(`${boss.x},${boss.y}`) && distance(playerPos, boss) <= 4) {
      const steps = currentModule.tutorial_steps || [];
      const step = steps.find(s => s.id === "boss");
      if (step) this.showOnce("boss", step.text);
    }

    // Chest visibility.
    for (let y = 0; y < MAP_H; y++) {
      for (let x = 0; x < MAP_W; x++) {
        if (mapData[y][x] === TILE.CHEST && !chestsOpened.has(`${x},${y}`) && visible.has(`${x},${y}`)) {
          const steps = currentModule.tutorial_steps || [];
          const step = steps.find(s => s.id === "chest");
          if (step) this.showOnce("chest", step.text);
        }
      }
    }

    // Trap proximity (discovered or triggered).
    for (let y = 0; y < MAP_H; y++) {
      for (let x = 0; x < MAP_W; x++) {
        if (mapData[y][x] !== TILE.TRAP) continue;
        const key = `${x},${y}`;
        const discovered = trapsDiscovered.has(key) || trapsTriggered.has(key);
        if (discovered && visible.has(key) && distance(playerPos, { x, y }) <= 2) {
          const steps = currentModule.tutorial_steps || [];
          const step = steps.find(s => s.id === "trap");
          if (step) this.showOnce("trap", step.text);
        }
      }
    }

    // Low HP reminder.
    if (playerCharacter && playerCharacter.sheet) {
      const hpPct = playerCharacter.sheet.max_hit_points > 0
        ? playerCharacter.sheet.hit_points / playerCharacter.sheet.max_hit_points
        : 1;
      if (hpPct <= 0.35 && playerCharacter.sheet.hit_points > 0) {
        const steps = currentModule.tutorial_steps || [];
        const step = steps.find(s => s.id === "rest");
        if (step) this.showOnce("rest", step.text);
      }
    }
  }

  markActed() {
    if (!TutorialManager.isActive()) return;
    this.hasActedThisTurn = true;
    if (this.actedTimer) clearTimeout(this.actedTimer);
    this.actedTimer = setTimeout(() => {
      if (combatState && combatState.phase === "player" && this.hasActedThisTurn) {
        this.showToast("Press End Turn when you are finished acting.", "Reminder");
        const endBtn = document.getElementById("end-turn-btn");
        if (endBtn) endBtn.classList.add("end-turn-reminder");
      }
    }, 10000);
  }

  resetTurn() {
    this.hasActedThisTurn = false;
    if (this.actedTimer) {
      clearTimeout(this.actedTimer);
      this.actedTimer = null;
    }
    const endBtn = document.getElementById("end-turn-btn");
    if (endBtn) endBtn.classList.remove("end-turn-reminder");
  }
}

function initTutorial() {
  tutorialManager = new TutorialManager();
  if (TutorialManager.isActive()) {
    tutorialManager.onDungeonStart();
  }
}

function resetTutorial() {
  tutorialHintsShown = new Set();
  tutorialManager = null;
}

function spawnWanderingMonster(countExpr = "1") {
  const count = Math.max(1, rollDamageExpression(countExpr));
  const cfg = combatConfig().wandering_monsters || {};
  const minDistance = cfg.min_distance_tiles || 5;
  const tiles = findSpawnTiles(minDistance);
  if (!tiles.length) return 0;

  let spawned = 0;
  for (let i = 0; i < count; i++) {
    const monsterId = pickEncounterMonster(dungeonLevel);
    if (!monsterId) continue;
    const template = getMonsterTemplate(monsterId);
    if (!template) continue;
    const pos = tiles[Math.floor(Math.random() * tiles.length)];
    const stats = scaleMonsterStats(template, dungeonLevel);
    monsters.push({
      id: `${monsterId}-wander-${pos.x}-${pos.y}-${dungeonLevel}-${Date.now()}-${i}`,
      name: template.name,
      hd: template.hd || 1,
      x: pos.x,
      y: pos.y,
      acDesc: stats.acDesc,
      ...stats,
      morale: template.morale,
      alive: true,
      fled: false,
      asleep: dungeonLevel > 1,
      moraleChecked: false,
      turned: 0,
    });
    if (typeof recordMonsterSeen === "function") recordMonsterSeen(template.name);
    spawned++;
  }
  if (spawned) {
    drawTokens();
    renderFog();
  }
  return spawned;
}

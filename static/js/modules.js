/** Hand-crafted dungeon modules. */

const DUNGEON_MODULES = {
  crooked_tower: {
    name: "The Crooked Tower",
    blurb: "Lord Huet's fallen keep. Something gnaws in the cellars beneath.",
    story: "Lord Huet was a feared warrior who drove the valley's goblin tribes into the hills. After his death the keep was abandoned, and now travelers report torchlight in the tower windows and missing livestock. The local reeve offers a modest purse for anyone who clears out whatever has taken root below.",
    objective: "Explore the cellars beneath the Crooked Tower, defeat the creatures lairing there, and reach the beacon that marks the old escape tunnel.",
    intro: "You descend a crumbling stair into damp torchlight. Somewhere ahead, something scrapes stone against stone.",
    width: 22,
    height: 16,
    rooms: [
      { id: "entrance",   x: 1, y: 12, w: 6, h: 4, label: "Entrance Hall" },
      { id: "antechamber",x: 8, y: 10, w: 5, h: 5, label: "Antechamber" },
      { id: "storage",    x: 16, y: 10, w: 5, h: 4, label: "Storage Room" },
      { id: "crossing",   x: 8, y: 6,  w: 6, h: 3, label: "Crossing" },
      { id: "westhall",   x: 2, y: 5,  w: 5, h: 3, label: "West Hall" },
      { id: "shrine",     x: 16, y: 5,  w: 5, h: 5, label: "Shrine" },
      { id: "throne",     x: 2, y: 1,  w: 7, h: 4, label: "Throne Room" },
      { id: "exit",       x: 16, y: 1,  w: 5, h: 4, label: "Exit Chamber" },
    ],
    room_descriptions: {
      entrance: "The entrance hall stinks of mildew and old blood. Rusted sconces still hold guttering torches.",
      antechamber: "A cramped antechamber where sentries once warmed themselves. Now kobold paw-prints streak the dust.",
      storage: "Cracked casks and rotted sacks line the walls. Something has gnawed through the grain barrels.",
      crossing: "A low crossing where three passages meet. The floor is unnaturally smooth, worn by recent traffic.",
      westhall: "A narrow hall leading toward the old throne room. Trip-wires glint in the torchlight.",
      shrine: "A forgotten shrine to a nameless god. Its altar has been desecrated and used as a larder.",
      throne: "Lord Huet's throne room. A hunched figure in rusted mail sits on the dais, gnawing a bone.",
      exit: "The old escape tunnel ends at a brass beacon, cold and dim. Beyond it lies the surface."
    },
    corridors: [
      ["entrance", "antechamber"],
      ["antechamber", "storage"],
      ["antechamber", "crossing"],
      ["crossing", "shrine"],
      ["crossing", "westhall"],
      ["westhall", "throne"],
      ["shrine", "exit"],
    ],
    playerStart: "entrance",
    exitRoom: "exit",
    monsters: [
      { room: "antechamber", type: "Kobold" },
      { room: "storage",     type: "Giant Rat" },
      { room: "shrine",      type: "Skeleton" },
      { room: "exit",        type: "Orc" },
      { room: "throne",      type: "Goblin", boss: true, name: "Grik the Goblin Chieftain" },
    ],
    chests: ["storage", "shrine"],
    traps: ["westhall"],
  },
};

let currentModule = null;
let roomIdGrid = [];
let roomsVisited = new Set();

function loadDungeonModule(name) {
  const mod = DUNGEON_MODULES[name];
  if (!mod) {
    console.warn("Unknown module", name);
    return false;
  }
  currentModule = mod;
  roomsVisited = new Set();

  MAP_W = mod.width;
  MAP_H = mod.height;
  const grid = makeEmptyMap();
  const roomGrid = makeEmptyMap();
  roomIdGrid = makeEmptyMap();
  const roomById = {};

  for (const room of mod.rooms) {
    carveRoom(grid, room);
    carveRoom(roomGrid, room);
    for (let y = room.y; y < room.y + room.h; y++) {
      for (let x = room.x; x < room.x + room.w; x++) {
        if (y > 0 && y < MAP_H - 1 && x > 0 && x < MAP_W - 1) {
          roomIdGrid[y][x] = room.id;
        }
      }
    }
    roomById[room.id] = room;
  }

  // Carve corridors.
  for (const [aId, bId] of mod.corridors) {
    const a = roomCenter(roomById[aId]);
    const b = roomCenter(roomById[bId]);
    carveCorridor(grid, a.x, a.y, b.x, b.y);
  }

  // Place doors where corridors meet rooms.
  for (let y = 1; y < MAP_H - 1; y++) {
    for (let x = 1; x < MAP_W - 1; x++) {
      if (grid[y][x] !== TILE.FLOOR) continue;
      const isRoom = roomGrid[y][x] === TILE.FLOOR;
      if (isRoom) continue;
      for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
        if (roomGrid[y + dy][x + dx] === TILE.FLOOR) {
          grid[y][x] = TILE.DOOR;
          break;
        }
      }
    }
  }

  // Reset state.
  chestsOpened.clear();
  doorsOpened.clear();
  trapsTriggered.clear();
  explored.clear();

  // Player and exit.
  playerPos = roomCenter(roomById[mod.playerStart]);
  const exitPos = roomCenter(roomById[mod.exitRoom]);
  grid[exitPos.y][exitPos.x] = TILE.EXIT;

  // Chests.
  for (const roomId of mod.chests) {
    const pos = roomCenter(roomById[roomId]);
    grid[pos.y][pos.x] = TILE.CHEST;
  }

  // Traps.
  for (const roomId of mod.traps) {
    const pos = roomCenter(roomById[roomId]);
    grid[pos.y][pos.x] = TILE.TRAP;
  }

  // Monsters.
  monsters = [];
  for (const entry of mod.monsters) {
    const pos = roomCenter(roomById[entry.room]);
    const type = entry.type;
    const base = MONSTER_BASE_STATS[type];
    if (!base) continue;
    const levelMult = 1 + (dungeonLevel - 1) * 0.35;
    const isBoss = entry.boss;
    const hp = Math.floor(base.hp * levelMult * (isBoss ? 1.5 : 1));
    monsters.push({
      id: `${type.toLowerCase().replace(/\s+/g, "_")}-${pos.x}-${pos.y}-${dungeonLevel}`,
      name: entry.name || type,
      x: pos.x,
      y: pos.y,
      ...base,
      hp: hp,
      maxHp: hp,
      thac0: Math.max(1, base.thac0 - (dungeonLevel - 1) - (isBoss ? 1 : 0)),
      damage: isBoss ? `1d${parseInt(base.damage.slice(2)) + 2}` : base.damage,
      xp: Math.floor(base.xp * levelMult * (isBoss ? 2 : 1)),
      alive: true,
      fled: false,
      moraleChecked: false,
    });
  }

  mapData = grid;
  computeVisibility();
  return true;
}

function checkRoomEntry(x, y) {
  if (!currentModule || !roomIdGrid.length) return;
  const roomId = roomIdGrid[y] && roomIdGrid[y][x];
  if (!roomId || roomsVisited.has(roomId)) return;
  roomsVisited.add(roomId);
  const desc = currentModule.room_descriptions && currentModule.room_descriptions[roomId];
  if (desc && typeof log === "function") {
    log(desc);
  }
}

const MONSTER_BASE_STATS = {
  Kobold:     { hp: 4,  maxHp: 4,  acDesc: 7, thac0: 20, damage: "1d4", xp: 7,  morale: 6 },
  "Giant Rat":{ hp: 6,  maxHp: 6,  acDesc: 7, thac0: 20, damage: "1d3", xp: 10, morale: 8 },
  Goblin:     { hp: 8,  maxHp: 8,  acDesc: 7, thac0: 20, damage: "1d6", xp: 15, morale: 7 },
  Skeleton:   { hp: 12, maxHp: 12, acDesc: 7, thac0: 20, damage: "1d6", xp: 25, morale: 12 },
  Orc:        { hp: 16, maxHp: 16, acDesc: 6, thac0: 19, damage: "1d8", xp: 40, morale: 8 },
};

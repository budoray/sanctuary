/** Hand-crafted dungeon modules. */

const DUNGEON_MODULES = {
  crooked_tower: {
    name: "The Crooked Tower",
    level: 1,
    unlocks: "sunken_crypt",
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
  sunken_crypt: {
    name: "The Sunken Crypt",
    level: 1,
    unlocks: "goblin_warren",
    blurb: "A flooded river-tomb where the drowned dead walk again.",
    story: "The old kings of the River Mere were buried in tombs cut into the chalk beneath the watermeadows. After the spring floods a faint green light has been seen down there, and villagers speak of figures dragging themselves through the marsh at night. The churchwarden offers coin for anyone who seals the lower vault.",
    objective: "Descend into the flooded crypts, destroy the walking dead, and reach the seal-stone that bars the lowest vault.",
    intro: "You wade down a slime-slick stair. The air smells of river mud and old bone. Somewhere ahead, water drips into still water.",
    width: 22,
    height: 16,
    rooms: [
      { id: "entrance",   x: 1, y: 12, w: 6, h: 4, label: "Flooded Entry" },
      { id: "catacombs",  x: 8, y: 10, w: 5, h: 5, label: "Catacombs" },
      { id: "cistern",    x: 16, y: 10, w: 5, h: 4, label: "Cistern" },
      { id: "crossing",   x: 8, y: 6,  w: 6, h: 3, label: "Sunken Crossing" },
      { id: "ossuary",    x: 2, y: 5,  w: 5, h: 3, label: "Ossuary" },
      { id: "shrine",     x: 16, y: 5,  w: 5, h: 5, label: "Shrine of Weeds" },
      { id: "tomb",       x: 2, y: 1,  w: 7, h: 4, label: "King's Tomb" },
      { id: "exit",       x: 16, y: 1,  w: 5, h: 4, label: "Seal Chamber" },
    ],
    room_descriptions: {
      entrance: "The entry stair is half-flooded. Rusted lanterns still hang from the ceiling, swaying in a draught from below.",
      catacombs: "Narrow alcoves hold stacked bones. Something has pulled many of them loose and scattered them across the floor.",
      cistern: "A cistern of black water fills the southern end of the room. Shapes move beneath the surface.",
      crossing: "Three passages meet in a low vault where the water is ankle-deep and unnaturally cold.",
      ossuary: "A chamber of heaped bones. Fresh mud and water stain the walls, as if something climbed up from below.",
      shrine: "A river-shrine to a forgotten god. Its altar is overgrown with weeds and circled by standing water.",
      tomb: "The royal tomb. A crowned figure in rotted silk stands knee-deep in water, its head lolling to one side.",
      exit: "The seal-stone stands in the centre of the chamber, carved with warnings against disturbing the dead."
    },
    corridors: [
      ["entrance", "catacombs"],
      ["catacombs", "cistern"],
      ["catacombs", "crossing"],
      ["crossing", "shrine"],
      ["crossing", "ossuary"],
      ["ossuary", "tomb"],
      ["shrine", "exit"],
    ],
    playerStart: "entrance",
    exitRoom: "exit",
    monsters: [
      { room: "catacombs", type: "Giant Rat" },
      { room: "cistern",   type: "Zombie" },
      { room: "ossuary",   type: "Skeleton" },
      { room: "shrine",    type: "Zombie" },
      { room: "tomb",      type: "Ghoul", boss: true, name: "The Drowned King" },
    ],
    chests: ["cistern", "shrine"],
    traps: ["crossing"],
  },
  goblin_warren: {
    name: "The Goblin Warren",
    level: 2,
    unlocks: "forgotten_shrine",
    blurb: "A reeking cave-complex where goblins breed spiders and raid the valley.",
    story: "Shepherds have vanished near the Broken Ridge, and scouts report torchlight in the old warren. The reeve offers a bounty for clearing the tunnels and breaking the goblin chieftain's grip.",
    objective: "Rout the goblin tribe, slay their hobgoblin champion, and seal the warren's back exit.",
    intro: "The tunnel reeks of smoke and wet fur. Ahead, crude drums echo and something skitters in the dark.",
    width: 22,
    height: 16,
    rooms: [
      { id: "entrance",   x: 1, y: 12, w: 6, h: 4, label: "Warren Mouth" },
      { id: "guardpost",  x: 8, y: 10, w: 5, h: 5, label: "Guard Post" },
      { id: "commonroom", x: 16, y: 10, w: 5, h: 4, label: "Common Cave" },
      { id: "pit",        x: 8, y: 6,  w: 6, h: 3, label: "Spider Pit" },
      { id: "storeroom",  x: 2, y: 5,  w: 5, h: 3, label: "Storeroom" },
      { id: "breeding",   x: 16, y: 5,  w: 5, h: 5, label: "Breeding Chamber" },
      { id: "chieftain",  x: 2, y: 1,  w: 7, h: 4, label: "Chieftain's Hall" },
      { id: "exit",       x: 16, y: 1,  w: 5, h: 4, label: "Back Tunnel" },
    ],
    room_descriptions: {
      entrance: "The warren mouth is littered with bones and cracked shields. Goblin grafitti covers the walls.",
      guardpost: "A crude guard post where sentries squat among piles of stolen gear.",
      commonroom: "Goblin beds of filthy straw and a smouldering cook-fire. The floor is slick with grease.",
      pit: "A natural pit bridged by rotten planks. Pale shapes crawl along the ceiling.",
      storeroom: "Crates and barrels looted from caravans. Most have been emptied.",
      breeding: "Giant spider egg-sacs hang from the ceiling, gently pulsing.",
      chieftain: "A raised dais of skulls and rusted shields. A hulking hobgoblin waits on a throne of bones.",
      exit: "A narrow back tunnel leads toward the ridge. A heavy stone could seal it forever."
    },
    corridors: [
      ["entrance", "guardpost"],
      ["guardpost", "commonroom"],
      ["guardpost", "pit"],
      ["pit", "breeding"],
      ["pit", "storeroom"],
      ["storeroom", "chieftain"],
      ["breeding", "exit"],
    ],
    playerStart: "entrance",
    exitRoom: "exit",
    monsters: [
      { room: "guardpost", type: "Kobold" },
      { room: "commonroom", type: "Goblin" },
      { room: "pit", type: "Giant Spider" },
      { room: "breeding", type: "Giant Spider" },
      { room: "chieftain", type: "Hobgoblin", boss: true, name: "Krag the Hobgoblin" },
    ],
    chests: ["storeroom", "breeding"],
    traps: ["pit"],
  },
  forgotten_shrine: {
    name: "The Forgotten Shrine",
    level: 3,
    blurb: "A desecrated temple where dead zealots and tomb-robbers clash in the dark.",
    story: "Pilgrims once left offerings at the Shrine of the Quiet Veil. Now bandits camp in its outer halls and the dead walk the inner sanctum. The church offers indulgences to anyone who reconsecrates the altar.",
    objective: "Drive out the looters, destroy the shrine wight, and relight the altar beacon.",
    intro: "Dust and incense hang thick in the air. Somewhere ahead, a dead voice intones prayers in a forgotten tongue.",
    width: 22,
    height: 16,
    rooms: [
      { id: "entrance",   x: 1, y: 12, w: 6, h: 4, label: "Porch" },
      { id: "vestibule",  x: 8, y: 10, w: 5, h: 5, label: "Vestibule" },
      { id: "camp",       x: 16, y: 10, w: 5, h: 4, label: "Bandit Camp" },
      { id: "crossing",   x: 8, y: 6,  w: 6, h: 3, label: "Crossing" },
      { id: "crypt",      x: 2, y: 5,  w: 5, h: 3, label: "Crypt" },
      { id: "reliquary",  x: 16, y: 5,  w: 5, h: 5, label: "Reliquary" },
      { id: "sanctuary",  x: 2, y: 1,  w: 7, h: 4, label: "Inner Sanctuary" },
      { id: "exit",       x: 16, y: 1,  w: 5, h: 4, label: "Altar Chamber" },
    ],
    room_descriptions: {
      entrance: "The porch is choked with dead leaves and broken offerings.",
      vestibule: "A marble vestibule defaced with bandit graffiti and crude camp-fires.",
      camp: "Bedrolls and looted relics show where the tomb-robbers have made camp.",
      crossing: "Three passages meet beneath a cracked dome. Water drips steadily from above.",
      crypt: "Rows of niches hold mouldering bones. Several have been pried open.",
      reliquary: "Golden vessels and torn tapestries. The most sacred items are already gone.",
      sanctuary: "The inner sanctuary. A withered figure in priestly robes kneels before a cold altar.",
      exit: "The altar chamber. A single brazier stands ready to be relit."
    },
    corridors: [
      ["entrance", "vestibule"],
      ["vestibule", "camp"],
      ["vestibule", "crossing"],
      ["crossing", "reliquary"],
      ["crossing", "crypt"],
      ["crypt", "sanctuary"],
      ["reliquary", "exit"],
    ],
    playerStart: "entrance",
    exitRoom: "exit",
    monsters: [
      { room: "camp", type: "Bandit" },
      { room: "vestibule", type: "Skeleton" },
      { room: "crypt", type: "Zombie" },
      { room: "reliquary", type: "Bandit" },
      { room: "sanctuary", type: "Wight", boss: true, name: "The Shrine Wight" },
    ],
    chests: ["camp", "reliquary"],
    traps: ["crossing"],
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
  Kobold:     { hp: 4,  maxHp: 4,  acDesc: 7, thac0: 20, damage: "1d4", xp: 7,  morale: 6,  ranged: { damage: "1d4", range: 40 } },
  "Giant Rat":{ hp: 6,  maxHp: 6,  acDesc: 7, thac0: 20, damage: "1d3", xp: 10, morale: 8 },
  Goblin:     { hp: 8,  maxHp: 8,  acDesc: 7, thac0: 20, damage: "1d6", xp: 15, morale: 7,  ranged: { damage: "1d4", range: 30 } },
  Skeleton:   { hp: 12, maxHp: 12, acDesc: 7, thac0: 20, damage: "1d6", xp: 25, morale: 12, ranged: { damage: "1d6", range: 50 } },
  Zombie:     { hp: 14, maxHp: 14, acDesc: 8, thac0: 20, damage: "1d8", xp: 20, morale: 12 },
  Ghoul:      { hp: 16, maxHp: 16, acDesc: 6, thac0: 19, damage: "1d6", xp: 35, morale: 10 },
  Orc:        { hp: 16, maxHp: 16, acDesc: 6, thac0: 19, damage: "1d8", xp: 40, morale: 8,  ranged: { damage: "1d6", range: 20 } },
  Hobgoblin:  { hp: 18, maxHp: 18, acDesc: 5, thac0: 18, damage: "1d8", xp: 45, morale: 10, ranged: { damage: "1d6", range: 30 } },
  Wight:      { hp: 20, maxHp: 20, acDesc: 5, thac0: 17, damage: "1d6", xp: 60, morale: 12 },
  "Giant Spider": { hp: 10, maxHp: 10, acDesc: 7, thac0: 20, damage: "1d6", xp: 25, morale: 7 },
  Bandit:     { hp: 10, maxHp: 10, acDesc: 7, thac0: 20, damage: "1d6", xp: 15, morale: 7, ranged: { damage: "1d4", range: 30 } },
};

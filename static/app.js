"use strict";

const ANCESTRIES = ["dwarf", "elf", "gnome", "half-elf", "halfling", "half-orc", "human"];
const CLASSES = ["assassin", "cleric", "druid", "fighter", "illusionist",
                 "magic-user", "monk", "paladin", "ranger", "thief"];

function fill(id, values) {
  const el = document.getElementById(id);
  el.innerHTML = "";
  for (const v of values) {
    const o = document.createElement("option");
    o.value = v; o.textContent = v;
    el.appendChild(o);
  }
}
fill("ancestry", ANCESTRIES);
document.getElementById("ancestry").value = "human";

// The class picker is a real radio group, server-rendered in index.html
// (one portrait tile per class, in CLASSES order) so it is focusable and
// keyboard-navigable with no JS at all - this just reads/writes it.
function classRadios() {
  return Array.from(document.querySelectorAll('input[name="klass"]'));
}
function selectedClass() {
  const checked = classRadios().find((r) => r.checked);
  return checked ? checked.value : CLASSES[0];
}

// ── Fix 1: an illegal ancestry/class pairing is known before any dice roll,
// from data/ancestries.yaml's own allowed_classes - so it is prevented, not
// reported back after a wasted /api/character round trip. The map comes
// from the server (never hand-copied here, or it drifts from the book).
let ancestryClasses = null; // {ancestry: [allowed class, ...]} once fetched

function applyClassAvailability() {
  if (!ancestryClasses) return;
  const ancestry = document.getElementById("ancestry").value;
  const allowed = new Set(ancestryClasses[ancestry] || CLASSES);
  const radios = classRadios();
  for (const input of radios) {
    const ok = allowed.has(input.value);
    input.disabled = !ok;
    const reason = ok ? "" : `${ancestry} may not be ${input.value}`;
    const label = document.getElementById(`klass-${input.value}-label`);
    if (label) label.title = reason;
    const reasonEl = document.getElementById(`klass-${input.value}-reason`);
    if (reasonEl) reasonEl.textContent = reason;
  }
  const current = radios.find((r) => r.checked);
  if (!current || current.disabled) {
    const firstLegal = radios.find((r) => allowed.has(r.value));
    if (firstLegal) firstLegal.checked = true;
  }
}

fetch("/api/ancestry-classes")
  .then((r) => r.json())
  .then((map) => { ancestryClasses = map; applyClassAvailability(); });

document.getElementById("ancestry").addEventListener("change", applyClassAvailability);

// The seed is the character. A new one per roll, shown in the log so any
// character can be reproduced exactly.
function newSeed() {
  return Date.now() % 2147483647;
}

function clearForgeError() {
  const err = document.getElementById("forge-error");
  err.hidden = true;
  err.textContent = "";
}

function showForgeError(message) {
  document.getElementById("sheet").hidden = true;
  document.getElementById("begin-delve").disabled = true;
  lastCharacter = null;
  const err = document.getElementById("forge-error");
  err.textContent = message;
  err.hidden = false;
}

function renderSheet(c) {
  clearForgeError();
  document.getElementById("sheet").hidden = false;
  // A fresh sheet means no delve underfoot: the button invites a run.
  const begin = document.getElementById("begin-delve");
  begin.disabled = false;
  begin.textContent = "Begin a delve";
  document.getElementById("who").textContent =
    `${c.name || "Unnamed"} — ${c.ancestry} ${c.classes.join("/")}`;

  const portrait = document.getElementById("portrait");
  portrait.src = c.portrait;
  portrait.alt = `${c.ancestry} ${c.classes.join("/")}`;

  const scores = document.getElementById("scores");
  scores.innerHTML = "";
  for (const [k, v] of Object.entries(c.scores)) {
    scores.insertAdjacentHTML("beforeend", `<dt>${k}</dt><dd>${v}</dd>`);
  }

  document.getElementById("vitals").textContent =
    `${c.hit_points} hp · AC ${c.armour_class} · to hit ${c.modifiers.hit >= 0 ? "+" : ""}${c.modifiers.hit}` +
    ` · damage ${c.modifiers.damage >= 0 ? "+" : ""}${c.modifiers.damage} · seed ${c.seed}`;

  const saves = document.getElementById("saves");
  saves.innerHTML = "";
  for (const [k, v] of Object.entries(c.saves)) {
    saves.insertAdjacentHTML("beforeend", `<dt>${k.replace(/_/g, " ")}</dt><dd>${v}</dd>`);
  }
}

// The die FACE comes from the server. This animation only reveals a number
// that was already rolled - it never generates one.
function animate(el, finalFaces) {
  const frames = 8;
  let i = 0;
  const tick = () => {
    // Cycle through the real faces rather than inventing values.
    el.textContent = finalFaces[i % finalFaces.length];
    if (++i < frames) {
      setTimeout(tick, 40);
    } else {
      el.textContent = finalFaces.join(" ");
    }
  };
  tick();
}

// Only the new roll dances: lines that already told their faces stay
// put, so a fresh render doesn't re-shimmer the whole ledger.
let prevRollsLen = 0;

function renderLog(rolls) {
  const log = document.getElementById("log");
  log.innerHTML = "";
  const freshFrom = rolls.length > prevRollsLen ? prevRollsLen : rolls.length;
  rolls.forEach((r, i) => {
    const li = document.createElement("li");
    const fresh = i >= freshFrom;
    if (fresh) li.className = "enter";
    const faces = document.createElement("b");
    li.appendChild(faces);
    const modText = r.mods ? ` ${r.mods > 0 ? "+" : ""}${r.mods}` : "";
    li.insertAdjacentHTML("beforeend",
      ` <code>${r.expr}</code>${modText} = <strong>${r.total}</strong>` +
      (r.reason ? ` <em>${r.reason}</em>` : ""));
    log.appendChild(li);
    if (fresh) animate(faces, r.faces);
    else faces.textContent = r.faces.join(" ");
  });
  prevRollsLen = rolls.length;
  // The newest roll is the one that matters - keep it in view.
  log.scrollTop = log.scrollHeight;
}

async function finalizeCharacter(seed, arrangement) {
  const payload = {
    seed,
    mode: document.getElementById("mode").value,
    ancestry: document.getElementById("ancestry").value,
    classes: [selectedClass()],
    // An untouched name field still SHOWS a name (the placeholder) - the
    // character should carry it, or the sheet contradicts what the player
    // saw when they pressed Roll.
    name: document.getElementById("name").value || document.getElementById("name").placeholder,
  };
  if (arrangement) payload.arrangement = arrangement;
  const res = await fetch("/api/character", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json();
    showForgeError(`Cannot roll that: ${err.detail}`);
    return;
  }
  const c = await res.json();
  renderSheet(c);
  // A fresh character is a fresh throw of the dice: the ledger's memory
  // resets so the creation rolls dance - even on a re-roll, when the new
  // log happens to be exactly as long as the last.
  prevRollsLen = 0;
  renderLog(c.log);
  lastCharacter = c;
}

// For an arrangeable mode, show the six rolled scores and let the player
// assign each to an ability before the sheet is finalised - six <select>
// elements (keyboard-accessible; no drag-and-drop-only path) is the whole UI.
function renderArrangement(seed, scores) {
  const abilities = Object.keys(scores);
  const values = Object.values(scores);
  const section = document.getElementById("arrange");
  const fields = document.getElementById("arrange-fields");
  fields.innerHTML = "";
  for (const ability of abilities) {
    const select = document.createElement("select");
    select.id = `arrange-${ability}`;
    select.dataset.ability = ability;
    values.forEach((v, i) => {
      const o = document.createElement("option");
      o.value = i;
      o.textContent = v;
      select.appendChild(o);
    });
    select.value = abilities.indexOf(ability); // sensible default: roll order
    fields.insertAdjacentHTML("beforeend", `<dt><label for="${select.id}">${ability}</label></dt>`);
    const dd = document.createElement("dd");
    dd.appendChild(select);
    fields.appendChild(dd);
  }
  section.hidden = false;
  section.dataset.seed = seed;
}

document.getElementById("roll").addEventListener("click", async () => {
  const mode = document.getElementById("mode").value;
  const seed = newSeed();
  const rolled = await fetch("/api/roll-abilities", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ seed, mode }),
  }).then((r) => r.json());

  if (rolled.arrangeable) {
    document.getElementById("sheet").hidden = true;
    renderArrangement(seed, rolled.scores);
    return;
  }
  document.getElementById("arrange").hidden = true;
  await finalizeCharacter(seed, null);
});

document.getElementById("confirm-arrangement").addEventListener("click", async () => {
  const section = document.getElementById("arrange");
  const seed = Number(section.dataset.seed);
  const selects = section.querySelectorAll("select[data-ability]");
  const arrangement = {};
  const rolledValues = Array.from(selects[0].options).map((o) => o.textContent);
  for (const select of selects) {
    arrangement[select.dataset.ability] = Number(rolledValues[select.value]);
  }
  section.hidden = true;
  await finalizeCharacter(seed, arrangement);
});

// --------------------------------------------------------------------
// Delve: solo play over sanctuary/runtime.py via sanctuary/session.py.
// The dice tray keeps rendering every roll exactly as it does for
// character generation - `renderLog` is reused unchanged.
//
// The map is built entirely from what `/api/delve/*` already returns:
// each `view` names the current area (`area_id`, `name`, `exits`). There
// is no "give me the whole dungeon" endpoint, so the client accumulates
// what it has actually seen into `exploredAreas` as the party moves -
// a fog-of-war map is the honest shape for a map built this way.
// --------------------------------------------------------------------

let delveSessionId = null;
let lastCharacter = null;
let exploredAreas = {};
let mapRootId = null;

// The way out looks like what it is: stairs, a door, a corridor mouth.
const EXIT_TILES = [["stairs", "stairs_down"], ["door", "door_open"], ["corridor", "floor_worn_stone"]];
function exitTile(kind) {
  const hit = EXIT_TILES.find(([k]) => (kind || "").includes(k));
  return `/static/art/tiles/${hit ? hit[1] : "floor_worn_stone"}.png`;
}

function recordArea(view) {
  if (mapRootId === null) mapRootId = view.area_id;
  exploredAreas[view.area_id] = { name: view.name, exits: view.exits, visited: true };
  for (const e of view.exits) {
    if (!(e.to in exploredAreas)) {
      exploredAreas[e.to] = { name: null, exits: [], visited: false };
    }
  }
}

// BFS layering from the root area: column = steps from the start, row =
// position within that column. Good enough for the mostly-linear graphs
// procgen produces; not a general graph-layout engine.
function layoutMap(rootId) {
  const adjacency = {};
  for (const id in exploredAreas) adjacency[id] = new Set();
  for (const id in exploredAreas) {
    for (const e of exploredAreas[id].exits) {
      const to = String(e.to);
      adjacency[id].add(to);
      if (!adjacency[to]) adjacency[to] = new Set();
      adjacency[to].add(id);
    }
  }
  const depth = {};
  const queue = [String(rootId)];
  depth[String(rootId)] = 0;
  const order = [];
  while (queue.length) {
    const cur = queue.shift();
    order.push(cur);
    for (const n of adjacency[cur] || []) {
      if (!(n in depth)) {
        depth[n] = depth[cur] + 1;
        queue.push(n);
      }
    }
  }
  const columns = {};
  for (const id of order) {
    const d = depth[id];
    (columns[d] = columns[d] || []).push(id);
  }
  const positions = {};
  for (const d in columns) {
    columns[d].forEach((id, i) => {
      positions[id] = { col: Number(d), row: i, rowCount: columns[d].length };
    });
  }
  return positions;
}

// ── The lantern map ────────────────────────────────────────────────────
// The dungeon as the party sees it: top-down tiles, a torch's worth of
// light around the character, visited rooms kept as dim memory, darkness
// everywhere else. Drawn on a canvas from the same fog-of-war graph
// (exploredAreas) the old node diagram used - the engine's geometry is
// untouched.

const TILE_PX = 64;
// Corridor cells leading out of the current room -> {to, label}; rebuilt by
// renderMap, consulted by the canvas click/hover handlers. mapMovesEnabled
// mirrors the exit buttons' disabled state (combat, ruling due, delve over).
const mapClickTargets = new Map();
let mapMovesEnabled = false;
// The exit whose corridor the pointer is over, or null - renderMap paints
// that corridor in lamplight so the walkable ways announce themselves.
let mapHoverTo = null;
// The torch's breath: a slow multiplier on the party's light radius,
// nudged by an interval so the carried light feels alive, not rendered.
let mapFlicker = 1;
// Living monsters in the current room - renderMap rings the party's
// light with them, so a fight is visible ON the map, not just in the rail.
let mapMenace = 0;
// Treasure piles in the current room - renderMap scatters a gold glint per
// haul across the floor, so loot catches the eye before the rail is read.
let mapTreasure = 0;
// The delve's end dims the world: when the run is over the carried light
// contracts to a guttering ember, and if the party fell their token greys.
let mapFinished = false;
let mapPartyDown = false;
// Arrow-key movement: the layout puts deeper areas to the RIGHT and the
// way back to the LEFT, so ←/→ are the dungeon's natural verbs. Rebuilt
// by renderMap from the same positions the corridors are drawn from.
const mapArrowExits = { left: null, right: null };
const TILE_NAMES = [
  "floor_cobblestone", "floor_flagstone", "floor_packed_dirt", "floor_worn_stone",
  "wall_dressed_stone", "wall_rough_hewn_rock",
  "door_closed", "door_open", "stairs_down", "stairs_up", "rubble", "water",
];
const FLOOR_TILES = TILE_NAMES.slice(0, 4);
const tileImages = {};      // url -> HTMLImageElement, once loaded
let tileLoadsPending = 0;

// Every tile draw goes through here: the first call starts the load and
// returns null; when the last pending image settles the map redraws once.
function tileImage(url) {
  if (tileImages[url]) return tileImages[url];
  tileLoadsPending++;
  const img = new Image();
  const done = () => { if (--tileLoadsPending === 0 && mapRootId !== null) renderMap(); };
  img.onload = () => { tileImages[url] = img; done(); };
  img.onerror = done;
  img.src = url;
  return null;
}
for (const n of TILE_NAMES) tileImage(`/static/art/tiles/${n}.png`);

function hashOf(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0;
  return h;
}

function renderMap() {
  const container = document.getElementById("map");
  if (mapRootId === null) { container.innerHTML = ""; return; }

  const ROOM_W = 6, ROOM_H = 5, CORR = 4;
  const COL_PITCH = ROOM_W + CORR;   // tiles per depth column
  const ROW_PITCH = ROOM_H + 3;      // tiles per row band
  const positions = layoutMap(mapRootId);
  const maxRows = Math.max(...Object.values(positions).map((p) => p.rowCount));

  // Every explored area gets a room rect in tile space - unexplored ones
  // too, so their corridors have somewhere to point; only visited rooms
  // are drawn. Size and floor come from a hash of the area id, so a room
  // keeps its shape for the whole delve.
  const rooms = {};
  for (const id in positions) {
    const p = positions[id];
    const h = hashOf(id);
    const w = 4 + h % 3;             // 4..6 tiles
    const hh = 3 + (h >> 3) % 3;     // 3..5 tiles
    const bandH = p.rowCount * ROW_PITCH;
    const ox = 1 + p.col * COL_PITCH + Math.floor((ROOM_W - w) / 2);
    const oy = 2 + Math.floor((maxRows * ROW_PITCH - bandH) / 2)
             + p.row * ROW_PITCH + Math.floor((ROOM_H - hh) / 2);
    rooms[id] = { ox, oy, w, h: hh, midY: oy + Math.floor(hh / 2), hash: h,
                  floor: FLOOR_TILES[h % FLOOR_TILES.length] };
  }

  const key = (x, y) => `${x},${y}`;
  const floorCells = new Map();      // "x,y" -> floor tile name
  const featCells = new Map();       // "x,y" -> door / stairs / rubble / water
  const putFloor = (x, y) => { if (!floorCells.has(key(x, y))) floorCells.set(key(x, y), "floor_worn_stone"); };

  for (const id in rooms) {
    if (!exploredAreas[id].visited) continue;
    const r = rooms[id];
    for (let dx = 0; dx < r.w; dx++)
      for (let dy = 0; dy < r.h; dy++)
        floorCells.set(key(r.ox + dx, r.oy + dy), r.floor);
  }

  // Corridors: one per explored edge, drawn from the shallower column,
  // L-shaped when the two rooms sit at different depths of row. Corridors
  // to unexplored areas are drawn too - they are the ways on, vanishing
  // into the dark. Passages between visited rooms are remembered as well
  // (corrCells): the light punches through them softly, so explored
  // dungeon reads as connected space, not islands.
  // Corridors OUT of the current room are also the move controls: their
  // cells are recorded in mapClickTargets so a click (or tap) on the map
  // walks that way - actions on the map, not just beside it.
  mapClickTargets.clear();
  // Arrow keys: an exit is "right" if it leads deeper (its column is
  // further from the entrance than ours), "left" if it leads back.
  // Same-column exits get no arrow - they have no corridor either.
  mapArrowExits.left = null;
  mapArrowExits.right = null;
  const curAreas = exploredAreas[String(mapCurrentId)];
  if (curAreas) {
    for (const e of curAreas.exits) {
      const from = positions[String(mapCurrentId)];
      const dest = positions[String(e.to)];
      if (!from || !dest) continue;
      if (dest.col > from.col && mapArrowExits.right === null) mapArrowExits.right = Number(e.to);
      if (dest.col < from.col && mapArrowExits.left === null) mapArrowExits.left = Number(e.to);
    }
  }
  const corrCells = [];
  const edgesSeen = new Set();
  for (const id in exploredAreas) {
    for (const e of exploredAreas[id].exits) {
      const to = String(e.to);
      if (!(to in rooms)) continue;
      const ekey = [id, to].sort().join("-");
      if (edgesSeen.has(ekey)) continue;
      edgesSeen.add(ekey);
      if (positions[id].col === positions[to].col) continue;
      const [aId, bId] = positions[id].col < positions[to].col ? [id, to] : [to, id];
      const a = rooms[aId], b = rooms[bId];
      const kind = e.kind || "";
      const bSeen = exploredAreas[bId].visited;
      const x0 = a.ox + a.w;         // first cell right of room A
      const x1 = b.ox - 1;           // last cell left of room B
      // A way into the unknown is a mouth, not a tunnel: cap the stub so
      // it vanishes into the dark a few tiles on.
      const xEnd = bSeen ? x1 : Math.min(x1, x0 + 2);
      for (let x = x0; x <= xEnd; x++) {
        putFloor(x, a.midY);
        if (bSeen) corrCells.push([x, a.midY]);
      }
      if (bSeen && a.midY !== b.midY) {
        const step = b.midY > a.midY ? 1 : -1;
        for (let y = a.midY; y !== b.midY + step; y += step) {
          putFloor(x1, y);
          corrCells.push([x1, y]);
        }
      }
      // A corridor touching the current room is a move control: every cell
      // of it (and of the stub into the dark) walks that way on click.
      // But only if the way is LEGAL from here: the engine's one-way
      // passages (a chute you dropped down, stairs that only descend) are
      // drawn as memory of how you got in, never as a door back - a click
      // the engine must refuse would be a lie under the pointer.
      const curIsA = String(mapCurrentId) === aId;
      const curIsB = String(mapCurrentId) === bId;
      if (curIsA || curIsB) {
        const otherId = curIsA ? bId : aId;
        const legal = (exploredAreas[String(mapCurrentId)].exits || [])
          .some((x) => String(x.to) === otherId);
        if (legal) {
          const seen = exploredAreas[otherId];
          const label = seen && seen.visited && seen.name
            ? `${kind || "way"} to ${seen.name}`
            : `${kind || "way"} into the dark`;
          const target = { to: Number(otherId), label };
          for (let x = x0; x <= xEnd; x++) mapClickTargets.set(key(x, a.midY), target);
          if (bSeen && a.midY !== b.midY) {
            const step = b.midY > a.midY ? 1 : -1;
            for (let y = a.midY; y !== b.midY + step; y += step) mapClickTargets.set(key(x1, y), target);
          }
        } else if (exploredAreas[otherId].visited) {
          // ...and the way is sealed from this side: a fall of rubble at
          // the mouth on the current room's edge, so the memory reads as
          // collapsed behind the party, not as an open door that ignores
          // the pointer.
          featCells.set(key(curIsA ? x0 : x1, a.midY), "rubble");
        }
      }
      if (kind.includes("door")) {
        featCells.set(key(x0, a.midY), bSeen ? "door_open" : "door_closed");
      }
      if (kind.includes("stairs")) {
        featCells.set(key(a.ox + a.w - 1, a.midY), "stairs_down");
      }
    }
  }

  // The way in: the entrance room carries the stairs back to the surface.
  const root = rooms[String(mapRootId)];
  if (root) featCells.set(key(root.ox, root.midY), "stairs_up");

  // Debris: a deterministic scatter of rubble and standing water, never
  // under a feature, never under the party's footing.
  for (const id in rooms) {
    if (!exploredAreas[id].visited) continue;
    const r = rooms[id];
    for (let dx = 0; dx < r.w; dx++) for (let dy = 0; dy < r.h; dy++) {
      const x = r.ox + dx, y = r.oy + dy, k = key(x, y);
      if (featCells.has(k)) continue;
      if (dx === Math.floor(r.w / 2) && dy === Math.floor(r.h / 2)) continue;
      const m = (x * 7 + y * 13 + r.hash) % 23;
      if (m === 0) featCells.set(k, "rubble");
      else if (m === 7) featCells.set(k, "water");
    }
  }

  // Walls ring every floor cell - rooms and corridors read as carved space.
  const wallCells = new Map();
  for (const k of floorCells.keys()) {
    const [x, y] = k.split(",").map(Number);
    for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) {
      const nx = x + dx, ny = y + dy, nk = key(nx, ny);
      if (!floorCells.has(nk) && !featCells.has(nk)) {
        wallCells.set(nk, (nx * 5 + ny * 11) % 2 ? "wall_dressed_stone" : "wall_rough_hewn_rock");
      }
    }
  }

  // The canvas wraps what has actually been explored, plus a tile of
  // margin - the unknown is not rendered space, it is simply elsewhere.
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const grow = (k) => {
    const [x, y] = k.split(",").map(Number);
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  };
  floorCells.forEach((_, k) => grow(k));
  wallCells.forEach((_, k) => grow(k));
  minX -= 1; minY -= 1; maxX += 1; maxY += 1;
  const TX = (v) => (v - minX) * TILE_PX;
  const TY = (v) => (v - minY) * TILE_PX;

  const canvas = document.createElement("canvas");
  canvas.width = (maxX - minX + 1) * TILE_PX;
  canvas.height = (maxY - minY + 1) * TILE_PX;
  canvas.className = "delve-map";
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", "Dungeon floor plan of areas explored so far");
  canvas.dataset.minX = minX;   // tile-space origin, for click handlers and
  canvas.dataset.minY = minY;   // for anything else that maps pixels to tiles
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;

  const drawCells = (cells) => {
    for (const [k, name] of cells) {
      const [x, y] = k.split(",").map(Number);
      const img = tileImage(`/static/art/tiles/${name}.png`);
      if (img) ctx.drawImage(img, TX(x), TY(y), TILE_PX, TILE_PX);
    }
  };
  drawCells(wallCells);
  drawCells(floorCells);
  drawCells(featCells);

  // The dark. One near-black overlay, punched through where the party has
  // been - softly for rooms they remember, wide and warm where they stand.
  const dark = document.createElement("canvas");
  dark.width = canvas.width;
  dark.height = canvas.height;
  const dctx = dark.getContext("2d");
  dctx.fillStyle = "rgba(4, 3, 2, 0.93)";
  dctx.fillRect(0, 0, dark.width, dark.height);
  dctx.globalCompositeOperation = "destination-out";
  for (const id in rooms) {
    if (!exploredAreas[id].visited) continue;
    const r = rooms[id];
    const isCurrent = Number(id) === Number(mapCurrentId);
    const cx = TX(r.ox + r.w / 2), cy = TY(r.oy + r.h / 2);
    // The carried light breathes: mapFlicker nudges only the CURRENT room's
    // halo - remembered rooms keep a steady memory-light. When the delve is
    // over the torch gutters: the reach shrinks to an ember of itself.
    const reach = isCurrent ? (mapFinished ? 1.1 : 2.5) * mapFlicker : 0.75;
    const rad = (Math.max(r.w, r.h) / 2 + reach) * TILE_PX;
    const grad = dctx.createRadialGradient(cx, cy, rad * 0.55, cx, cy, rad);
    grad.addColorStop(0, `rgba(0, 0, 0, ${isCurrent ? 1 : 0.6})`);
    grad.addColorStop(1, "rgba(0, 0, 0, 0)");
    dctx.fillStyle = grad;
    dctx.beginPath();
    dctx.arc(cx, cy, rad, 0, Math.PI * 2);
    dctx.fill();
  }
  // Remembered passages: a soft pulse of light every couple of tiles along
  // corridors the party has actually walked.
  for (let i = 0; i < corrCells.length; i += 2) {
    const [x, y] = corrCells[i];
    const cx = TX(x + 0.5), cy = TY(y + 0.5);
    const rad = 2.2 * TILE_PX;
    const grad = dctx.createRadialGradient(cx, cy, rad * 0.3, cx, cy, rad);
    grad.addColorStop(0, "rgba(0, 0, 0, 0.5)");
    grad.addColorStop(1, "rgba(0, 0, 0, 0)");
    dctx.fillStyle = grad;
    dctx.beginPath();
    dctx.arc(cx, cy, rad, 0, Math.PI * 2);
    dctx.fill();
  }
  ctx.drawImage(dark, 0, 0);

  // Hover glow: the corridor under the pointer catches the lamplight. Only
  // its own cells - the glow says "THIS way", not "somewhere over there".
  // Touch has no hover: on coarse pointers every walkable corridor keeps a
  // faint ember instead, so the tap targets are never invisible.
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  if (mapHoverTo !== null || (coarse && mapMovesEnabled && mapClickTargets.size)) {
    const accent = getComputedStyle(document.documentElement).getPropertyValue("--color-accent").trim() || "#e8a33d";
    ctx.save();
    ctx.shadowColor = accent;
    ctx.shadowBlur = TILE_PX * 0.6;
    ctx.fillStyle = accent;
    const ember = mapHoverTo === null;
    if (ember) {
      // A coal at the heart of each walkable cell: small, warm, unmissable
      // against the dark, but nothing like the full hover glow.
      for (const [k] of mapClickTargets) {
        const [x, y] = k.split(",").map(Number);
        const cx = TX(x) + TILE_PX / 2, cy = TY(y) + TILE_PX / 2;
        ctx.globalAlpha = 0.55;
        ctx.beginPath();
        ctx.arc(cx, cy, TILE_PX * 0.07, 0, Math.PI * 2);
        ctx.fill();
      }
    } else {
      ctx.globalAlpha = 0.32;
      for (const [k, t] of mapClickTargets) {
        if (t.to !== mapHoverTo) continue;
        const [x, y] = k.split(",").map(Number);
        const inset = TILE_PX * 0.1;
        ctx.fillRect(TX(x) + inset, TY(y) + inset, TILE_PX - inset * 2, TILE_PX - inset * 2);
      }
    }
    ctx.restore();
  }

  // The party stands at the centre of the light: their portrait is the
  // token. The fallback marker uses the theme's accent, read live.
  const cur = rooms[String(mapCurrentId)];
  if (cur) {
    const px = TX(cur.ox + Math.floor(cur.w / 2));
    const py = TY(cur.oy + Math.floor(cur.h / 2));
    const portrait = lastCharacter && lastCharacter.portrait ? tileImage(lastCharacter.portrait) : null;
    if (portrait) {
      // The fallen stand grey in the guttering light.
      if (mapPartyDown) ctx.filter = "grayscale(1) brightness(0.7)";
      ctx.drawImage(portrait, px, py, TILE_PX, TILE_PX);
      if (mapPartyDown) ctx.filter = "none";
    } else {
      ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--color-accent") || "#e8a33d";
      ctx.beginPath();
      ctx.arc(px + TILE_PX / 2, py + TILE_PX / 2, TILE_PX / 3, 0, Math.PI * 2);
      ctx.fill();
    }
    // What shares the room shares the light: a blood-red eye per living
    // monster, ringing the party just inside the halo's edge.
    if (mapMenace > 0) {
      const danger = getComputedStyle(document.documentElement).getPropertyValue("--color-danger").trim() || "#c0392b";
      ctx.save();
      ctx.shadowColor = danger;
      ctx.shadowBlur = TILE_PX * 0.35;
      ctx.fillStyle = danger;
      const ringR = TILE_PX * 1.05;
      for (let i = 0; i < mapMenace; i++) {
        const a = -Math.PI / 2 + (i * 2 * Math.PI) / mapMenace;
        const mx = px + TILE_PX / 2 + ringR * Math.cos(a);
        const my = py + TILE_PX / 2 + ringR * Math.sin(a);
        ctx.beginPath();
        ctx.arc(mx, my, TILE_PX * 0.09, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }
    // Loot winks out of the dark: one gold spark per treasure haul, seeded
    // by the room so a redraw never moves it, brightening with the torch's
    // breath. The party cell stays clear - the spark must not read as a foe.
    if (mapTreasure > 0) {
      const accent = getComputedStyle(document.documentElement).getPropertyValue("--color-accent").trim() || "#e8a33d";
      const partyX = cur.ox + Math.floor(cur.w / 2), partyY = cur.oy + Math.floor(cur.h / 2);
      const phase = Math.max(0, Math.min(1, (mapFlicker - 0.93) / 0.07));
      ctx.save();
      ctx.shadowColor = accent;
      ctx.shadowBlur = TILE_PX * 0.4;
      ctx.fillStyle = accent;
      for (let i = 0; i < mapTreasure; i++) {
        const h2 = (mapCurrentId * 2654435761 + i * 974711) >>> 0;
        let gx = cur.ox + (h2 % cur.w);
        let gy = cur.oy + ((h2 >> 8) % cur.h);
        if (gx === partyX && gy === partyY) gx = cur.ox + ((gx + 1 - cur.ox) % cur.w);
        const cx = TX(gx) + TILE_PX / 2, cy = TY(gx) + TILE_PX / 2;
        ctx.globalAlpha = 0.5 + 0.45 * phase;
        const r = TILE_PX * 0.09, arm = TILE_PX * 0.2;
        ctx.beginPath();   // a four-point spark: core dot plus short rays
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillRect(cx - arm, cy - r * 0.28, arm * 2, r * 0.56);
        ctx.fillRect(cx - r * 0.28, cy - arm, r * 0.56, arm * 2);
      }
      ctx.restore();
    }
  }

  container.innerHTML = "";
  // The map names itself: a screen reader gets the same truth the torch
  // gives the eyes - where the party stands, and how much is known.
  const knownRooms = Object.values(exploredAreas).filter((a) => a.visited).length;
  const curName = exploredAreas[String(mapCurrentId)] && exploredAreas[String(mapCurrentId)].name;
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label",
    `Map of the delve: the party stands in ${curName || "an unnamed area"}; ${knownRooms} area${knownRooms === 1 ? "" : "s"} explored.`);
  container.appendChild(canvas);

  // Re-centre the light only when the party changes room - hover redraws
  // must not yank the view away from wherever the user has scrolled to.
  const scrollState = { left: container.scrollLeft, top: container.scrollTop };
  const areaChanged = mapScrollAreaId !== mapCurrentId;

  // Click / hover: a corridor out of the current room is a door you can
  // walk through. Hover names the way (and shows the pointer); click moves.
  const tileXY = (ev) => {
    const r = canvas.getBoundingClientRect();
    return [
      Math.floor((ev.clientX - r.left) / TILE_PX) + minX,
      Math.floor((ev.clientY - r.top) / TILE_PX) + minY,
    ];
  };
  const tileAt = (ev) => {
    const [x, y] = tileXY(ev);
    return mapClickTargets.get(key(x, y));
  };
  // Memory has names: hovering a room the party has actually stood in
  // answers with what the delve called it. Unvisited shells stay mute.
  const roomNameAt = (ev) => {
    const [x, y] = tileXY(ev);
    for (const id in rooms) {
      const rm = rooms[id];
      if (!exploredAreas[id].visited) continue;
      if (x >= rm.ox && x < rm.ox + rm.w && y >= rm.oy && y < rm.oy + rm.h) {
        return exploredAreas[id].name;
      }
    }
    return null;
  };
  canvas.addEventListener("mousemove", (ev) => {
    const t = mapMovesEnabled ? tileAt(ev) : null;
    canvas.style.cursor = t ? "pointer" : "";
    canvas.title = t ? t.label : (roomNameAt(ev) || "");
    const hoverTo = t ? t.to : null;
    if (hoverTo !== mapHoverTo) {
      mapHoverTo = hoverTo;
      syncRailHover();
      renderMap();
    }
  });
  canvas.addEventListener("mouseleave", () => {
    if (mapHoverTo !== null) {
      mapHoverTo = null;
      syncRailHover();
      renderMap();
    }
  });
  canvas.addEventListener("click", (ev) => {
    if (!mapMovesEnabled) return;
    const t = tileAt(ev);
    if (t) act("move", { to: t.to });
  });

  // Keep the light in view when the dungeon outgrows the frame - but only
  // on a real move; hover redraws restore the user's own scroll position.
  if (cur && container.clientWidth > 0) {
    if (areaChanged) {
      container.scrollLeft = Math.max(0, TX(cur.ox + cur.w / 2) - container.clientWidth / 2);
      container.scrollTop = Math.max(0, TY(cur.oy + cur.h / 2) - container.clientHeight / 2);
      mapScrollAreaId = mapCurrentId;
    } else {
      container.scrollLeft = scrollState.left;
      container.scrollTop = scrollState.top;
    }
  }
}

let mapCurrentId = null;
// The area the map last centred itself on - so hover redraws don't fight
// the user's own scrolling.
let mapScrollAreaId = null;

// Torch flicker: a slow breath on the party's light radius. One interval
// for the app's lifetime; it cheaply re-renders the map (tile images are
// cached) only while a delve map is actually on screen, and stays still
// for users who prefer reduced motion.
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
setInterval(() => {
  if (mapRootId === null || document.getElementById("map-stage").hidden) return;
  if (reduceMotion.matches) { if (mapFlicker !== 1) { mapFlicker = 1; renderMap(); } return; }
  // Slow triangle wave 0.93..1.0 - the light leans out and settles back.
  const t = Date.now() / 2600;
  mapFlicker = 0.93 + 0.07 * (1 - Math.abs(1 - (t % 2)));
  renderMap();
}, 450);

// Mirror the map's hover state onto the rail: the exit button for the
// hovered corridor gets .map-hover, every other button loses it.
function syncRailHover() {
  document.querySelectorAll("#exits button").forEach((b) => {
    b.classList.toggle("map-hover", mapHoverTo !== null && Number(b.dataset.to) === mapHoverTo);
  });
}

// The rail remembers the last view's wounds and winnings, so a fresh
// render can feel the difference: a chip pulses red when its bearer took
// a hit, and the XP figure flashes gold when the haul grows.
let prevHpByName = {};
let prevXp = 0;
// Arrivals: whether blades were out last render (combat's first round
// jolts), and which ways were known in this room (a searched-out door
// enters with a fade, not a pop).
let prevInCombat = false;
let prevAreaId = null;
let prevExitTos = new Set();
let prevTurns = 0;
// What's happened, line by line: only entries beyond this count are new.
let prevDelveLogLen = 0;

// One beat of an animation class, restartable: remove, reflow, re-add.
// Consecutive beats on the same element must not be swallowed.
function beat(el, cls) {
  el.classList.remove(cls);
  void el.offsetWidth;
  el.classList.add(cls);
}

function renderDelve(view) {
  document.getElementById("forge").hidden = true;
  document.getElementById("arrange").hidden = true;
  document.getElementById("map-stage").hidden = false;
  document.getElementById("party-status").hidden = false;

  const nameEl = document.getElementById("area-name");
  nameEl.textContent = view.name;
  document.getElementById("area-description").textContent = view.description;
  const turnsEl = document.getElementById("area-turns");
  turnsEl.textContent =
    `Turn ${view.turns}` + (view.finished ? " — the delve is over." : "");
  // Passage has a pulse: the room's name fades in on arrival, the turn
  // count each time it climbs. First render beats for nothing.
  if (prevAreaId !== null && view.area_id !== prevAreaId) beat(nameEl, "enter");
  if (view.turns > prevTurns) beat(turnsEl, "enter");
  prevTurns = view.turns;

  // One delve at a time: while the party is below ground the begin button
  // says so and stays shut; when the run ends it opens again, renamed so
  // the next click plainly starts a NEW delve rather than resuming this one.
  const begin = document.getElementById("begin-delve");
  begin.disabled = !view.finished;
  begin.textContent = view.finished ? "Begin a new delve" : "Delve in progress";

  // The end of a delve is a moment, not a shrug: a tally over the map
  // tells the table how the run went and where the next one starts.
  const over = document.getElementById("delve-over");
  over.hidden = !view.finished;
  if (view.finished) {
    document.getElementById("delve-over-tally").textContent =
      `${view.turns} turn${view.turns === 1 ? "" : "s"} below ground, ${view.xp} xp earned.`;
  }

  mapCurrentId = view.area_id;
  mapHoverTo = null;   // a new view rebuilds every corridor - stale glow helps no one
  mapMenace = view.in_combat && view.combat
    ? view.combat.monsters.filter((m) => m.alive).length
    : view.monsters.length;
  mapTreasure = view.treasure.length;
  mapFinished = view.finished;
  mapPartyDown = view.party.length > 0 && view.party[0].hp <= 0;
  recordArea(view);
  renderMap();

  // Vitals as chips, not a sentence: each party member gets a thin hp bar
  // under their name, so a beating reads at a glance, not after a parse.
  const vitals = document.getElementById("party-vitals");
  vitals.innerHTML = "";
  view.party.forEach((p) => {
    const chip = document.createElement("span");
    chip.className = "hp-chip";
    const label = document.createElement("span");
    label.textContent = `${p.name} ${p.hp}/${p.max_hp} hp`;
    const bar = document.createElement("span");
    bar.className = "hp-bar";
    // The bar is a meter to the eyes; make it one to the ears as well.
    bar.setAttribute("role", "progressbar");
    bar.setAttribute("aria-valuemin", "0");
    bar.setAttribute("aria-valuemax", String(p.max_hp));
    bar.setAttribute("aria-valuenow", String(p.hp));
    bar.setAttribute("aria-label", `${p.name} hit points`);
    const fill = document.createElement("span");
    fill.className = "hp-fill" + (p.hp <= 0 ? " hp-dead" : p.hp * 3 <= p.max_hp ? " hp-low" : "");
    fill.style.width = `${Math.max(0, Math.min(100, (100 * p.hp) / p.max_hp))}%`;
    bar.appendChild(fill);
    chip.appendChild(label);
    chip.appendChild(bar);
    // A wound announces itself: the chip of anyone who lost hp since the
    // last view pulses blood-red once, then settles back to its bar.
    if (p.name in prevHpByName && p.hp < prevHpByName[p.name]) chip.classList.add("hp-hit");
    // A mend answers in lamp-gold: rest or a kind ruling lifts the bar,
    // and the chip glows warm for a beat to say so.
    if (p.name in prevHpByName && p.hp > prevHpByName[p.name]) chip.classList.add("hp-mend");
    // The fallen read as a memorial, not a meter: name struck, chip dimmed.
    if (p.hp <= 0) chip.classList.add("dead");
    vitals.appendChild(chip);
  });
  prevHpByName = Object.fromEntries(view.party.map((p) => [p.name, p.hp]));
  // One truth: the sheet's vitals line tracks the delve's hp, not the
  // morning the character rolled out of bed. (The sheet shows the
  // party's first - and, at this table, only - member.)
  if (view.party.length) {
    const vit = document.getElementById("vitals");
    vit.textContent = vit.textContent.replace(/^\d+ hp/, `${view.party[0].hp} hp`);
  }
  const xpEl = document.getElementById("xp");
  xpEl.textContent = view.xp;
  // A boon announces itself too: the XP figure flashes lamp-gold on every
  // gain, the beat restarted so back-to-back boons are not swallowed.
  if (view.xp > prevXp) beat(xpEl, "xp-flash");
  prevXp = view.xp;

  const decisionPending = view.pending_decisions.length > 0;

  const decisions = document.getElementById("pending-decisions");
  decisions.innerHTML = "";
  view.pending_decisions.forEach((d, i) => {
    const p = document.createElement("p");
    p.className = "enter";
    // A stacked docket reads as one repeated card; number it so the DM can
    // tell the second giant frog from the first.
    const label = view.pending_decisions.length > 1
      ? `Decision ${i + 1} of ${view.pending_decisions.length}:` : "Decision needed:";
    p.innerHTML = `<strong>${label}</strong> ${d.detail} `;
    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Your ruling";
    input.id = `ruling-${i}`;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "Rule on it";
    btn.addEventListener("click", () => act("decide", { index: i, ruling: input.value || "no effect" }, btn));
    // The DM's hands are already on the keyboard - Enter rules, same as
    // reaching for the mouse. The input is no form, so the key must call it.
    input.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") { ev.preventDefault(); btn.click(); }
    });
    p.appendChild(input);
    p.appendChild(btn);
    decisions.appendChild(p);
  });

  // The ruling is the only door forward - put the caret in it. Guarded so a
  // re-render never yanks focus away from a DM already typing in the block.
  if (decisionPending && !decisions.contains(document.activeElement)) {
    const first = decisions.querySelector("input");
    if (first) first.focus();
  }

  document.getElementById("movement-hint").hidden = !decisionPending;

  const combatSection = document.getElementById("combat");
  combatSection.hidden = !view.in_combat;
  // Combat enters with a jolt: the first render with blades out rings the
  // card in blood for a beat. Later rounds render quiet - the fight is
  // already joined, no need to keep shouting it.
  combatSection.classList.toggle("combat-start", view.in_combat && !prevInCombat);
  prevInCombat = view.in_combat;
  // Reset every turn: the loading state a click sets on `act()`'s way out
  // only ever gets cleared by a fresh render replacing the element (true for
  // #exits, rebuilt below) or, for these two static buttons, by this line -
  // without it a successful attack leaves `attack`/`flee` disabled forever.
  document.getElementById("attack").disabled = !view.in_combat || decisionPending;
  document.getElementById("flee").disabled = !view.in_combat;
  const combatList = document.getElementById("combat-monsters");
  combatList.innerHTML = "";
  if (view.combat) {
    view.combat.monsters.forEach((m, i) => {
      const li = document.createElement("li");
      const label = document.createElement("span");
      label.textContent = `${m.name}: ${m.hp}/${m.max_hp} hp ${m.alive ? "" : "(defeated)"}`;
      // The defeated read as the fallen do at the party rail: struck,
      // dimmed, done - not a meter still standing at zero.
      if (!m.alive) li.classList.add("defeated");
      const bar = document.createElement("span");
      bar.className = "hp-bar";
      bar.setAttribute("role", "progressbar");
      bar.setAttribute("aria-valuemin", "0");
      bar.setAttribute("aria-valuemax", String(m.max_hp));
      bar.setAttribute("aria-valuenow", String(m.hp));
      bar.setAttribute("aria-label", `${m.name} hit points`);
      const fill = document.createElement("span");
      fill.className = "hp-fill" + (m.hp * 3 <= m.max_hp ? " hp-low" : "") + (m.alive ? "" : " hp-dead");
      fill.style.width = `${Math.max(0, Math.min(100, (100 * m.hp) / m.max_hp))}%`;
      bar.appendChild(fill);
      li.appendChild(label);
      li.appendChild(bar);
      li.dataset.target = i;
      if (m.alive) {
        li.classList.add("selectable");
        // Attack falls back to target 0 - show that default honestly.
        if (![...combatList.children].some((el) => el.classList.contains("targeted"))) {
          li.classList.add("targeted");
        }
        li.addEventListener("click", () => {
          combatList.dataset.target = i;
          // The target is the one marked - a click with no visible answer
          // reads as a miss.
          combatList.querySelectorAll("li").forEach((el) => el.classList.remove("targeted"));
          li.classList.add("targeted");
        });
      }
      combatList.appendChild(li);
    });
  }

  const exitsList = document.getElementById("exits");
  exitsList.innerHTML = "";
  mapMovesEnabled = !(view.in_combat || view.finished || decisionPending);
  const mapHint = document.getElementById("map-hint");
  mapHint.hidden = !mapMovesEnabled;
  // The hint teaches the controls the device actually has: arrows need a
  // keyboard, taps need nothing.
  mapHint.textContent = window.matchMedia("(hover: hover) and (pointer: fine)").matches
    ? "Click a passage to walk it — ← heads back, → presses deeper, 1–9 picks a way."
    : "Tap a passage on the map to walk it.";
  view.exits.forEach((e) => {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    // Where the way leads decides how it is named: a visited room by its
    // name, the unknown as the unknown.
    const seen = exploredAreas[String(e.to)];
    const kind = e.kind || "way";
    btn.textContent = seen && seen.visited && seen.name
      ? `${kind} to ${seen.name}`
      : `${kind} into the dark`;
    btn.dataset.to = e.to;
    // A way that appears where none was - a searched-out secret door -
    // enters with a fade so the reveal is seen. Moving rooms rebuilds the
    // whole list; only arrivals in the SAME room count as reveals.
    if (view.area_id === prevAreaId && !prevExitTos.has(e.to)) btn.classList.add("enter");
    const icon = document.createElement("img");
    icon.src = exitTile(e.kind);
    icon.alt = "";
    icon.className = "exit-icon";
    btn.prepend(icon);
    btn.disabled = view.in_combat || view.finished || decisionPending;
    btn.title = decisionPending ? "Resolve the pending decision first."
      : view.in_combat ? "Cannot leave while monsters are still standing."
      : view.finished ? "The delve is over."
      : "";
    btn.addEventListener("click", () => act("move", { to: e.to }, btn));
    // Two-way sync: hovering the rail button lights its corridor on the
    // map, the same glow hovering the corridor itself would paint.
    btn.addEventListener("mouseenter", () => {
      if (btn.disabled) return;
      mapHoverTo = Number(e.to);
      renderMap();
    });
    btn.addEventListener("mouseleave", () => {
      if (mapHoverTo !== Number(e.to)) return;
      // Moving straight from the button onto its corridor must not kill
      // the glow the canvas just set - defer to whatever the pointer is
      // actually over now.
      if (document.querySelector("#map canvas:hover")) return;
      mapHoverTo = null;
      renderMap();
    });
    li.appendChild(btn);
    exitsList.appendChild(li);
  });
  prevAreaId = view.area_id;
  prevExitTos = new Set(view.exits.map((e) => e.to));

  // A heading over an empty <ul> reads as broken, not as "nothing here" -
  // "Here" and "Inventory" both rendered as a label above void.
  const emptyNote = (list, text) => {
    if (list.children.length) return;
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = text;
    list.appendChild(li);
  };

  const areaMonsters = document.getElementById("area-monsters");
  areaMonsters.innerHTML = "";
  (view.in_combat ? [] : view.monsters).forEach((m) => {
    const li = document.createElement("li");
    li.textContent = m;
    areaMonsters.appendChild(li);
  });

  const areaTreasure = document.getElementById("area-treasure");
  areaTreasure.innerHTML = "";
  view.treasure.forEach((t) => {
    const li = document.createElement("li");
    li.textContent = t;
    areaTreasure.appendChild(li);
  });

  if (!view.in_combat) emptyNote(areaMonsters, "Nothing stirring.");
  emptyNote(areaTreasure, "No treasure in sight.");
  // A sealed room must not read as a broken list: when the delve is live
  // and no exit is known, name the ways that remain - Search may reveal a
  // hidden door; Leave ends the run on the party's own terms.
  emptyNote(exitsList, view.finished
    ? "No way on from here."
    : "No way on from here - the dark gives nothing back. Search for a hidden way, or leave the delve.");

  const inventory = document.getElementById("inventory");
  inventory.innerHTML = "";
  view.inventory.forEach((t) => {
    const li = document.createElement("li");
    li.textContent = t;
    inventory.appendChild(li);
  });
  emptyNote(inventory, "Nothing carried yet.");

  const log = document.getElementById("delve-log");
  log.innerHTML = "";
  view.log.forEach((line, i) => {
    const li = document.createElement("li");
    // What's happened arrives line by line: only the new entries fade in.
    if (i >= prevDelveLogLen) li.classList.add("enter");
    li.textContent = line;
    log.appendChild(li);
  });
  prevDelveLogLen = view.log.length;
  log.scrollTop = log.scrollHeight;
  // A young delve has no history: the heading stays out of the way until
  // there is something to remember.
  document.getElementById("delve-log-heading").hidden = view.log.length === 0;
  log.hidden = view.log.length === 0;

  const exploring = !view.in_combat && !view.finished && !decisionPending;
  document.getElementById("search").disabled = !exploring;
  document.getElementById("rest").disabled = !exploring;
  document.getElementById("take-treasure").disabled = !exploring;
  document.getElementById("leave-delve").disabled = !exploring;

  renderLog(view.rolls);
}

// `btn`, when given, gets the loading/error states while the request is in
// flight - the click that started it is disabled and marked "loading",
// flips to "error" (and re-enables) on failure, or is simply replaced by
// `renderDelve`'s fresh markup on success.
// Only ONE action may be in flight: a second click mid-request used to fire
// a concurrent POST against state the first call was already mutating, and
// the loser came back as a confusing 400.
let actBusy = false;

// Failure (and the occasional success) speaks in the house's voice: a
// toast, never a native dialog. Blood-edged by default, lamp-gold when
// the news is good, dismissed by time rather than by demand.
let toastTimer = null;
function toast(message, ok = false) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.classList.toggle("ok", ok);
  el.hidden = false;
  beat(el, "enter");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 4200);
}

async function act(action, payload, btn) {
  if (actBusy) return false;
  actBusy = true;
  document.getElementById("party-status").classList.add("busy");
  let restingText;
  if (btn) {
    btn.disabled = true;
    btn.classList.add("loading");
    restingText = btn.textContent;
  }
  let res, view;
  try {
    res = await fetch("/api/delve/act", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ session_id: delveSessionId, action, ...(payload || {}) }),
    });
    view = await res.json();
  } catch (err) {
    if (btn) flagError(btn, restingText);
    toast("Cannot reach the server.");
    return false;
  } finally {
    actBusy = false;
    document.getElementById("party-status").classList.remove("busy");
  }
  if (!res.ok) {
    if (btn) flagError(btn, restingText);
    toast(`Cannot do that: ${view.detail}`);
    return false;
  }
  renderDelve(view);
  return true;
}

function flagError(btn, restingText) {
  btn.classList.remove("loading");
  btn.classList.add("error");
  btn.disabled = false;
  btn.textContent = restingText;
  setTimeout(() => btn.classList.remove("error"), 1200);
}

// ← walks back toward the entrance, → walks deeper - the same moves the
// map corridors and the rail buttons make, from the keyboard. Never while
// a ruling input has focus, and never when movement is locked (combat,
// a ruling due, the delve over) - the same rule the exit buttons obey.
document.addEventListener("keydown", (ev) => {
  if (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight") return;
  if (ev.target.matches("input, textarea, select")) return;
  if (!mapMovesEnabled) return;
  const to = ev.key === "ArrowRight" ? mapArrowExits.right : mapArrowExits.left;
  if (to === null) return;
  ev.preventDefault();
  act("move", { to });
});

// 1-9 picks among the ways out, top to bottom as the rail lists them -
// the same enabled buttons the pointer gets, under the same locks as the
// arrow keys. Never inside an input.
document.addEventListener("keydown", (ev) => {
  if (!/^[1-9]$/.test(ev.key)) return;
  if (ev.target.matches("input, textarea, select")) return;
  if (!mapMovesEnabled) return;
  const exits = Array.from(document.querySelectorAll("#exits button"))
    .filter((b) => !b.disabled);
  const btn = exits[Number(ev.key) - 1];
  if (!btn) return;
  ev.preventDefault();
  btn.click();
});

// The keyboard fights too: A attacks the marked monster, F flees - the
// same buttons, under the same locks (a ruling due disables Attack just
// as it does for the mouse). Never inside an input, never outside combat.
document.addEventListener("keydown", (ev) => {
  const k = ev.key.toLowerCase();
  if (k !== "a" && k !== "f") return;
  if (ev.target.matches("input, textarea, select")) return;
  if (document.getElementById("combat").hidden) return;
  const btn = document.getElementById(k === "a" ? "attack" : "flee");
  if (btn.disabled) return;
  ev.preventDefault();
  btn.click();
});

document.getElementById("begin-delve").addEventListener("click", async () => {
  if (!lastCharacter) return;
  const res = await fetch("/api/delve/start", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      module: "generate",
      seed: lastCharacter.seed,
      target_areas: 6,
      dungeon_level: 1,
      party: [{
        seed: lastCharacter.seed, mode: "normal",
        ancestry: lastCharacter.ancestry, classes: lastCharacter.classes,
        name: lastCharacter.name,
      }],
    }),
  });
  const view = await res.json();
  if (!res.ok) {
    toast(`Cannot begin a delve: ${view.detail}`);
    return;
  }
  delveSessionId = view.session_id;
  exploredAreas = {};
  mapRootId = null;
  // A fresh delve starts the rail's memory fresh too - no mend pulse for
  // hp the new party never gained, no gold flash for xp it never earned.
  prevHpByName = {};
  prevXp = 0;
  prevInCombat = false;
  prevAreaId = null;
  prevExitTos = new Set();
  prevTurns = 0;
  prevRollsLen = 0;
  prevDelveLogLen = 0;
  renderDelve(view);
});

document.getElementById("attack").addEventListener("click", (ev) => {
  const target = Number(document.getElementById("combat-monsters").dataset.target || 0);
  act("attack", { target }, ev.currentTarget);
});
document.getElementById("flee").addEventListener("click", (ev) => act("flee", null, ev.currentTarget));
document.getElementById("search").addEventListener("click", (ev) => act("search", null, ev.currentTarget));
document.getElementById("rest").addEventListener("click", (ev) => act("rest", { turns: 1 }, ev.currentTarget));
document.getElementById("take-treasure").addEventListener("click", (ev) => act("take_treasure", null, ev.currentTarget));
document.getElementById("leave-delve").addEventListener("click", (ev) => act("leave", null, ev.currentTarget));

document.getElementById("report").addEventListener("click", async () => {
  const title = prompt("What went wrong?");
  if (!title) return;
  const res = await fetch("/api/report", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ kind: "bug", title, body: location.href }),
  });
  const out = await res.json();
  toast(out.ok ? "Report sent." : "Could not send the report.", out.ok);
});

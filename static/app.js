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
  document.getElementById("begin-delve").disabled = false;
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

function renderLog(rolls) {
  const log = document.getElementById("log");
  log.innerHTML = "";
  for (const r of rolls) {
    const li = document.createElement("li");
    li.className = "enter";
    const faces = document.createElement("b");
    li.appendChild(faces);
    const modText = r.mods ? ` ${r.mods > 0 ? "+" : ""}${r.mods}` : "";
    li.insertAdjacentHTML("beforeend",
      ` <code>${r.expr}</code>${modText} = <strong>${r.total}</strong>` +
      (r.reason ? ` <em>${r.reason}</em>` : ""));
    log.appendChild(li);
    animate(faces, r.faces);
  }
  // The newest roll is the one that matters - keep it in view.
  log.scrollTop = log.scrollHeight;
}

async function finalizeCharacter(seed, arrangement) {
  const payload = {
    seed,
    mode: document.getElementById("mode").value,
    ancestry: document.getElementById("ancestry").value,
    classes: [selectedClass()],
    name: document.getElementById("name").value,
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
      const curIsA = String(mapCurrentId) === aId;
      const curIsB = String(mapCurrentId) === bId;
      if (curIsA || curIsB) {
        const seen = exploredAreas[curIsA ? bId : aId];
        const label = seen && seen.visited && seen.name
          ? `${kind || "way"} to ${seen.name}`
          : `${kind || "way"} into the dark`;
        const target = { to: Number(curIsA ? bId : aId), label };
        for (let x = x0; x <= xEnd; x++) mapClickTargets.set(key(x, a.midY), target);
        if (bSeen && a.midY !== b.midY) {
          const step = b.midY > a.midY ? 1 : -1;
          for (let y = a.midY; y !== b.midY + step; y += step) mapClickTargets.set(key(x1, y), target);
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
    const rad = (Math.max(r.w, r.h) / 2 + (isCurrent ? 2.5 : 0.75)) * TILE_PX;
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

  // The party stands at the centre of the light: their portrait is the
  // token. The fallback marker uses the theme's accent, read live.
  const cur = rooms[String(mapCurrentId)];
  if (cur) {
    const px = TX(cur.ox + Math.floor(cur.w / 2));
    const py = TY(cur.oy + Math.floor(cur.h / 2));
    const portrait = lastCharacter && lastCharacter.portrait ? tileImage(lastCharacter.portrait) : null;
    if (portrait) {
      ctx.drawImage(portrait, px, py, TILE_PX, TILE_PX);
    } else {
      ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--color-accent") || "#e8a33d";
      ctx.beginPath();
      ctx.arc(px + TILE_PX / 2, py + TILE_PX / 2, TILE_PX / 3, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  container.innerHTML = "";
  container.appendChild(canvas);

  // Click / hover: a corridor out of the current room is a door you can
  // walk through. Hover names the way (and shows the pointer); click moves.
  const tileAt = (ev) => {
    const r = canvas.getBoundingClientRect();
    const x = Math.floor((ev.clientX - r.left) / TILE_PX) + minX;
    const y = Math.floor((ev.clientY - r.top) / TILE_PX) + minY;
    return mapClickTargets.get(key(x, y));
  };
  canvas.addEventListener("mousemove", (ev) => {
    const t = mapMovesEnabled ? tileAt(ev) : null;
    canvas.style.cursor = t ? "pointer" : "";
    canvas.title = t ? t.label : "";
  });
  canvas.addEventListener("click", (ev) => {
    if (!mapMovesEnabled) return;
    const t = tileAt(ev);
    if (t) act("move", { to: t.to });
  });

  // Keep the light in view when the dungeon outgrows the frame.
  if (cur && container.clientWidth > 0) {
    container.scrollLeft = Math.max(0, TX(cur.ox + cur.w / 2) - container.clientWidth / 2);
    container.scrollTop = Math.max(0, TY(cur.oy + cur.h / 2) - container.clientHeight / 2);
  }
}

let mapCurrentId = null;

function renderDelve(view) {
  document.getElementById("forge").hidden = true;
  document.getElementById("arrange").hidden = true;
  document.getElementById("map-stage").hidden = false;
  document.getElementById("party-status").hidden = false;

  document.getElementById("area-name").textContent = view.name;
  document.getElementById("area-description").textContent = view.description;
  document.getElementById("area-turns").textContent =
    `Turn ${view.turns}` + (view.finished ? " — the delve is over." : "");

  mapCurrentId = view.area_id;
  recordArea(view);
  renderMap();

  document.getElementById("party-vitals").textContent = view.party
    .map((p) => `${p.name} ${p.hp}/${p.max_hp} hp`).join(", ");
  document.getElementById("xp").textContent = view.xp;

  const decisionPending = view.pending_decisions.length > 0;

  const decisions = document.getElementById("pending-decisions");
  decisions.innerHTML = "";
  view.pending_decisions.forEach((d, i) => {
    const p = document.createElement("p");
    p.className = "enter";
    p.innerHTML = `<strong>Decision needed:</strong> ${d.detail} `;
    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Your ruling";
    input.id = `ruling-${i}`;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "Rule on it";
    btn.addEventListener("click", () => act("decide", { index: i, ruling: input.value || "no effect" }, btn));
    p.appendChild(input);
    p.appendChild(btn);
    decisions.appendChild(p);
  });

  document.getElementById("movement-hint").hidden = !decisionPending;

  const combatSection = document.getElementById("combat");
  combatSection.hidden = !view.in_combat;
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
      li.textContent = `${m.name}: ${m.hp}/${m.max_hp} hp ${m.alive ? "" : "(defeated)"}`;
      li.dataset.target = i;
      if (m.alive) {
        li.classList.add("selectable");
        li.addEventListener("click", () => { combatList.dataset.target = i; });
      }
      combatList.appendChild(li);
    });
  }

  const exitsList = document.getElementById("exits");
  exitsList.innerHTML = "";
  mapMovesEnabled = !(view.in_combat || view.finished || decisionPending);
  document.getElementById("map-hint").hidden = !mapMovesEnabled;
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
    li.appendChild(btn);
    exitsList.appendChild(li);
  });

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
  emptyNote(exitsList, "No way on from here.");

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
  view.log.forEach((line) => {
    const li = document.createElement("li");
    li.textContent = line;
    log.appendChild(li);
  });
  log.scrollTop = log.scrollHeight;

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
    alert("Cannot reach the server.");
    return false;
  } finally {
    actBusy = false;
    document.getElementById("party-status").classList.remove("busy");
  }
  if (!res.ok) {
    if (btn) flagError(btn, restingText);
    alert(`Cannot do that: ${view.detail}`);
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
    alert(`Cannot begin a delve: ${view.detail}`);
    return;
  }
  delveSessionId = view.session_id;
  exploredAreas = {};
  mapRootId = null;
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
  alert(out.ok ? "Report sent." : "Could not send the report.");
});

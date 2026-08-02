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
fill("klass", CLASSES);
document.getElementById("ancestry").value = "human";
document.getElementById("klass").value = "fighter";

// The seed is the character. A new one per roll, shown in the log so any
// character can be reproduced exactly.
function newSeed() {
  return Date.now() % 2147483647;
}

function renderSheet(c) {
  document.getElementById("sheet").hidden = false;
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
}

async function finalizeCharacter(seed, arrangement) {
  const payload = {
    seed,
    mode: document.getElementById("mode").value,
    ancestry: document.getElementById("ancestry").value,
    classes: [document.getElementById("klass").value],
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
    document.getElementById("who").textContent = `Cannot roll that: ${err.detail}`;
    document.getElementById("sheet").hidden = false;
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

const NS = "http://www.w3.org/2000/svg";
function svgEl(tag, attrs) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
  return el;
}

function renderMap() {
  const container = document.getElementById("map");
  if (mapRootId === null) { container.innerHTML = ""; return; }

  const NODE_W = 128, NODE_H = 72, GAP_X = 96, GAP_Y = 32;
  const positions = layoutMap(mapRootId);
  const maxCol = Math.max(...Object.values(positions).map((p) => p.col));
  const maxRows = Math.max(...Object.values(positions).map((p) => p.rowCount));
  const width = (maxCol + 1) * (NODE_W + GAP_X) - GAP_X + GAP_X;
  const height = maxRows * (NODE_H + GAP_Y) + GAP_Y;

  const centerOf = (id) => {
    const p = positions[id];
    const colX = GAP_X / 2 + p.col * (NODE_W + GAP_X) + NODE_W / 2;
    const bandH = p.rowCount * (NODE_H + GAP_Y);
    const rowY = (height - bandH) / 2 + p.row * (NODE_H + GAP_Y) + GAP_Y / 2 + NODE_H / 2;
    return { x: colX, y: rowY };
  };

  const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}`, class: "delve-map", role: "img",
                              "aria-label": "Dungeon floor plan of areas explored so far" });

  const edgesSeen = new Set();
  for (const id in exploredAreas) {
    for (const e of exploredAreas[id].exits) {
      const to = String(e.to);
      const key = [id, to].sort().join("-");
      if (edgesSeen.has(key)) continue;
      edgesSeen.add(key);
      const a = centerOf(id), b = centerOf(to);
      const line = svgEl("line", {
        x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: "map-edge",
      });
      svg.appendChild(line);
      const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      const label = svgEl("text", { x: mx, y: my, class: "map-edge-label" });
      label.textContent = e.kind || "";
      svg.appendChild(label);
    }
  }

  for (const id in exploredAreas) {
    const area = exploredAreas[id];
    const { x, y } = centerOf(id);
    const isCurrent = Number(id) === Number(mapCurrentId);
    const g = svgEl("g", {
      class: `map-node enter ${area.visited ? "visited" : "ghost"} ${isCurrent ? "current" : ""}`,
      transform: `translate(${x - NODE_W / 2}, ${y - NODE_H / 2})`,
    });
    g.appendChild(svgEl("rect", { width: NODE_W, height: NODE_H, rx: 10, class: "map-node-rect" }));
    const label = svgEl("text", { x: NODE_W / 2, y: NODE_H / 2, class: "map-node-label" });
    label.textContent = area.visited ? area.name : "unexplored";
    g.appendChild(label);
    svg.appendChild(g);
  }

  container.innerHTML = "";
  container.appendChild(svg);
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
  view.exits.forEach((e) => {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = `${e.kind} to area ${e.to}`;
    btn.dataset.to = e.to;
    btn.disabled = view.in_combat || view.finished || decisionPending;
    btn.title = decisionPending ? "Resolve the pending decision first."
      : view.in_combat ? "Cannot leave while monsters are still standing."
      : view.finished ? "The delve is over."
      : "";
    btn.addEventListener("click", () => act("move", { to: e.to }, btn));
    li.appendChild(btn);
    exitsList.appendChild(li);
  });

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

  const inventory = document.getElementById("inventory");
  inventory.innerHTML = "";
  view.inventory.forEach((t) => {
    const li = document.createElement("li");
    li.textContent = t;
    inventory.appendChild(li);
  });

  const log = document.getElementById("delve-log");
  log.innerHTML = "";
  view.log.forEach((line) => {
    const li = document.createElement("li");
    li.textContent = line;
    log.appendChild(li);
  });

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
async function act(action, payload, btn) {
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

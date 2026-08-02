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
// --------------------------------------------------------------------

let delveSessionId = null;
let lastCharacter = null;

function renderDelve(view) {
  document.getElementById("delve").hidden = false;
  document.getElementById("area-name").textContent = view.name;
  document.getElementById("area-description").textContent = view.description;
  document.getElementById("area-turns").textContent =
    `Turn ${view.turns}` + (view.finished ? " — the delve is over." : "");

  document.getElementById("party-vitals").textContent = view.party
    .map((p) => `${p.name} ${p.hp}/${p.max_hp} hp`).join(", ");
  document.getElementById("xp").textContent = view.xp;

  const decisions = document.getElementById("pending-decisions");
  decisions.innerHTML = "";
  view.pending_decisions.forEach((d, i) => {
    const p = document.createElement("p");
    p.innerHTML = `<strong>Decision needed:</strong> ${d.detail} `;
    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Your ruling";
    input.id = `ruling-${i}`;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "Rule on it";
    btn.addEventListener("click", () => act("decide", { index: i, ruling: input.value || "no effect" }));
    p.appendChild(input);
    p.appendChild(btn);
    decisions.appendChild(p);
  });

  const combatSection = document.getElementById("combat");
  combatSection.hidden = !view.in_combat;
  const combatList = document.getElementById("combat-monsters");
  combatList.innerHTML = "";
  if (view.combat) {
    view.combat.monsters.forEach((m, i) => {
      const li = document.createElement("li");
      li.textContent = `${m.name}: ${m.hp}/${m.max_hp} hp ${m.alive ? "" : "(defeated)"}`;
      li.dataset.target = i;
      if (m.alive) {
        li.style.cursor = "pointer";
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
    btn.disabled = view.in_combat || view.finished;
    btn.addEventListener("click", () => act("move", { to: e.to }));
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

  const exploring = !view.in_combat && !view.finished;
  document.getElementById("search").disabled = !exploring;
  document.getElementById("rest").disabled = !exploring;
  document.getElementById("take-treasure").disabled = !exploring;
  document.getElementById("leave-delve").disabled = !exploring;

  renderLog(view.rolls);
}

async function act(action, payload) {
  const res = await fetch("/api/delve/act", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ session_id: delveSessionId, action, ...(payload || {}) }),
  });
  const view = await res.json();
  if (!res.ok) {
    alert(`Cannot do that: ${view.detail}`);
    return;
  }
  renderDelve(view);
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
  renderDelve(view);
});

document.getElementById("attack").addEventListener("click", () => {
  const target = Number(document.getElementById("combat-monsters").dataset.target || 0);
  act("attack", { target });
});
document.getElementById("flee").addEventListener("click", () => act("flee"));
document.getElementById("search").addEventListener("click", () => act("search"));
document.getElementById("rest").addEventListener("click", () => act("rest", { turns: 1 }));
document.getElementById("take-treasure").addEventListener("click", () => act("take_treasure"));
document.getElementById("leave-delve").addEventListener("click", () => act("leave"));

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

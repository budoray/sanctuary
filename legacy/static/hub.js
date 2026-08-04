"use strict";

// The hub: pick the table (ruleset, module, depth), then step into the
// forge. Delves already under way are listed for rejoining - the session
// id rides in the URL, never in localStorage, so a link can be shared.

const MODULE_NAMES = {
  generate: "A generated dungeon",
  weeping_cistern: "The Weeping Cistern",
};

async function bootRulesets() {
  const sel = document.getElementById("hub-ruleset");
  try {
    const res = await fetch("/api/rulesets");
    if (!res.ok) throw new Error(String(res.status));
    const packs = await res.json();
    sel.innerHTML = "";
    for (const p of packs) {
      const o = document.createElement("option");
      o.value = p.id;
      o.textContent = `${p.name} (v${p.version})`;
      sel.appendChild(o);
    }
  } catch {
    sel.innerHTML = "";
    const o = document.createElement("option");
    o.value = "osric";
    o.textContent = "OSRIC 3.0";
    sel.appendChild(o);
  }
}

function describeGame(g) {
  const module = MODULE_NAMES[g.module] || g.module;
  const state = g.finished ? "delve over" : `area ${g.area} · ${g.turns} turns · ${g.xp} xp`;
  return `${module} — ${g.ruleset} · ${state}`;
}

async function bootGames() {
  const list = document.getElementById("games");
  const empty = document.getElementById("games-empty");
  try {
    const res = await fetch("/api/games");
    if (!res.ok) throw new Error(String(res.status));
    const games = await res.json();
    list.innerHTML = "";
    empty.hidden = games.length > 0;
    for (const g of games) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = `/play?session=${g.session_id}`;
      a.textContent = describeGame(g);
      li.appendChild(a);
      list.appendChild(li);
    }
  } catch {
    empty.hidden = false;
  }
}

document.getElementById("hub-module").addEventListener("change", (e) => {
  // Depth only means something to a generated dungeon.
  document.getElementById("hub-level-row").hidden = e.target.value !== "generate";
});

document.getElementById("hub-begin").addEventListener("click", () => {
  const module = document.getElementById("hub-module").value;
  const level = document.getElementById("hub-level").value;
  const params = new URLSearchParams({ module, level });
  window.location.href = `/play?${params}`;
});

bootRulesets();
bootGames();

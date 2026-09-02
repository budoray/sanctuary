/** Public /live: an in-page agent plays so visitors can watch a delve. */
(function () {
  if (!location.pathname.startsWith("/live")) return;

  function sleep(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }

  function click(id) {
    var el = document.getElementById(id);
    if (el && !el.disabled) el.click();
    return el;
  }

  async function setup() {
    document.body.classList.add("watch-live");
    var play = document.getElementById("play-now-btn");
    if (play) play.textContent = "Watching a delve";
    await sleep(400);
    click("play-now-btn");
    await sleep(400);
    var klass = document.getElementById("char-class");
    if (klass) klass.value = "fighter";
    klass && klass.dispatchEvent(new Event("change"));
    for (var i = 0; i < 8; i++) {
      if (typeof rollCharacter === "function") await rollCharacter();
      else click("roll-character-btn");
      await sleep(200);
      if (playerCharacter && playerCharacter.sheet.max_hit_points >= 6) break;
    }
    var kit = document.getElementById("buy-starter-kit");
    if (typeof buyStarterKit === "function") await buyStarterKit();
    else if (kit) kit.click();
    await sleep(400);
    if (typeof enterDungeon === "function") await enterDungeon();
    else click("enter-dungeon-btn");
    await sleep(400);
    var card = document.querySelector(".module-card[data-id='crooked_tower']");
    if (card) card.click();
    await sleep(800);
    loop();
  }

  function dist(ax, ay, bx, by) {
    return Math.abs(ax - bx) + Math.abs(ay - by);
  }

  function walkable(x, y, state) {
    if (x < 0 || y < 0 || x >= state.mapW || y >= state.mapH) return false;
    var t = state.map[y][x];
    if (t === "." || t === "E" || t === "C") return true;
    if (t === "D" && state.doorsOpened.has(x + "," + y)) return true;
    return false;
  }

  function takeAction() {
    if (typeof combatState === "undefined" || !combatState || combatState.phase !== "player") return false;
    if (typeof handleGridClick !== "function") return false;
    var px = playerPos.x, py = playerPos.y;
    var alive = (monsters || []).filter(function (m) { return m.alive; });
    var adj = alive.filter(function (m) { return dist(px, py, m.x, m.y) === 1; });
    if (adj.length && !combatState.attacked) {
      handleGridClick(adj[0].x, adj[0].y);
      return true;
    }
    var dirs = [[0, 1], [0, -1], [1, 0], [-1, 0]];
    for (var i = 0; i < dirs.length; i++) {
      var dx = dirs[i][0], dy = dirs[i][1];
      var x = px + dx, y = py + dy;
      if (y < 0 || y >= MAP_H || x < 0 || x >= MAP_W) continue;
      if (mapData[y][x] === "D" && !doorsOpened.has(x + "," + y)) {
        handleGridClick(x, y);
        return true;
      }
    }
    if (combatState.movementRemaining > 0) {
      var best = null, bestScore = -1;
      dirs.forEach(function (d) {
        var x = px + d[0], y = py + d[1];
        if (!walkable(x, y, { map: mapData, mapW: MAP_W, mapH: MAP_H, doorsOpened: doorsOpened })) return;
        var score = explored.has(x + "," + y) ? 1 : 10;
        if (alive.length) {
          var near = Math.min.apply(null, alive.map(function (m) { return dist(x, y, m.x, m.y); }));
          score += near <= 1 ? 5 : 0;
        }
        if (score > bestScore) { bestScore = score; best = { x: x, y: y }; }
      });
      if (best) {
        handleGridClick(best.x, best.y);
        return true;
      }
    }
    return false;
  }

  async function loop() {
    for (var n = 0; n < 200; n++) {
      var end = document.getElementById("end-modal");
      if (end && !end.classList.contains("hidden")) return;
      if (typeof combatState !== "undefined" && combatState && combatState.phase === "player") {
        var acted = false;
        for (var a = 0; a < 5; a++) {
          if (!takeAction()) break;
          acted = true;
          await sleep(450);
        }
        if (typeof endTurn === "function") endTurn();
        await sleep(acted ? 900 : 600);
      } else {
        await sleep(400);
      }
    }
  }

  window.addEventListener("DOMContentLoaded", function () {
    setTimeout(setup, 600);
  });
})();

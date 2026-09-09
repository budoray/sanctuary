/** Shared dice tray. Player clicks Roll; AI auto-throws. No SFX. */
(function (global) {
  function $(id) { return document.getElementById(id); }

  function parseSides(expr) {
    const m = String(expr || "1d8").match(/d(\d+)/i);
    return m ? parseInt(m[1], 10) : 8;
  }

  function anatomyAttack(res) {
    const mod = Number(res.to_hit_mod) || 0;
    const modTxt = mod ? (mod > 0 ? ` +${mod}` : ` ${mod}`) : " +0";
    const nat = res.raw_roll === 20 ? " (nat 20)" : res.raw_roll === 1 ? " (nat 1)" : "";
    let hitTxt = "miss";
    if (res.hit) {
      const dmgMod = Number(res.damage_mod) || 0;
      const dmgBit = dmgMod ? `${res.damage_die || "dmg"}${dmgMod > 0 ? "+" : ""}${dmgMod}` : (res.damage_die || "dmg");
      hitTxt = `hit · ${dmgBit} -> ${res.damage}`;
    }
    return `${res.weapon || "Attack"}: d20 ${res.raw_roll}${modTxt} = ${res.roll} vs ${res.needed}${nat} · ${hitTxt}`;
  }

  function anatomySave(res, label) {
    const roll = res.roll ?? res.raw_roll;
    const target = res.effective_target ?? res.target;
    const ok = res.success === true || res.hit === true;
    return `${label || "Save"}: d20 ${roll} vs ${target} · ${ok ? "saved" : "failed"}`;
  }

  function dieNode(sides, value, tumbling) {
    const el = document.createElement("div");
    el.className = `die die-d${sides}${tumbling ? " tumbling" : ""}`;
    if (sides === 20 && value === 20) el.classList.add("nat20");
    if (sides === 20 && value === 1) el.classList.add("nat1");
    el.innerHTML = `<span class="die-sides">d${sides}</span><span class="die-face">${value == null ? "?" : value}</span>`;
    return el;
  }

  const Dice = {
    parseSides,
    anatomyAttack,
    anatomySave,

    async present(opts) {
      const tray = $("dice-tray");
      const diceEl = $("dice-tray-dice");
      const metaEl = $("dice-tray-meta");
      const whoEl = $("dice-tray-who");
      const rollBtn = $("dice-roll-btn");
      if (!tray || !diceEl) {
        return opts.resolve();
      }

      const name = opts.name || "Someone";
      const roller = opts.roller || "player";
      const auto = opts.auto != null
        ? opts.auto
        : roller === "ai" || location.pathname.startsWith("/live") || document.body.classList.contains("watch-live");
      const preview = opts.dice && opts.dice.length ? opts.dice : [{ sides: 20 }];

      if (typeof tutorialManager !== "undefined" && tutorialManager && tutorialManager.hideToast) {
        tutorialManager.hideToast();
      }
      tray.classList.remove("hidden", "hit", "miss");
      tray.classList.add("open", roller === "ai" ? "ai" : "player");
      if (whoEl) whoEl.textContent = roller === "ai" ? `${name} throws` : `${name} — your throw`;
      if (metaEl) metaEl.textContent = opts.label || "Attack roll";
      diceEl.innerHTML = "";
      preview.forEach((d) => diceEl.appendChild(dieNode(d.sides, "?", true)));
      if (rollBtn) {
        rollBtn.classList.toggle("hidden", !!auto);
        rollBtn.disabled = false;
      }

      const data = await new Promise((done) => {
        const fire = async () => {
          if (rollBtn) {
            rollBtn.disabled = true;
            rollBtn.classList.add("hidden");
          }
          const result = await opts.resolve();
          const faces = result.dice || preview.map((d, i) => ({ ...d, value: "?" }));
          diceEl.innerHTML = "";
          faces.forEach((d) => diceEl.appendChild(dieNode(d.sides, d.value, false)));
          if (metaEl) metaEl.textContent = result.anatomy || "";
          tray.classList.toggle("hit", result.hit === true);
          tray.classList.toggle("miss", result.hit === false);
          done(result);
        };
        Dice._pending = fire;
        if (auto) setTimeout(fire, 650);
      });
      Dice._pending = null;
      return data;
    },

    rollNow() {
      if (typeof Dice._pending === "function") Dice._pending();
    },

    hideSoon(ms = 2800) {
      const tray = $("dice-tray");
      if (!tray) return;
      setTimeout(() => tray.classList.remove("open"), ms);
    },
  };

  document.addEventListener("DOMContentLoaded", () => {
    const btn = $("dice-roll-btn");
    if (btn) btn.addEventListener("click", () => Dice.rollNow());
  });

  global.SanctuaryDice = Dice;
})(window);

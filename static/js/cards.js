/** Card definitions and effects for the prototype. */

const CARDS = {
  strike: {
    id: "strike",
    name: "Strike",
    cost: 1,
    type: "attack",
    text: "Deal 6 damage.",
    art: "attack",
    effect: (player, enemy) => {
      dealDamage(enemy, 6);
    },
  },
  slash: {
    id: "slash",
    name: "Slash",
    cost: 2,
    type: "attack",
    text: "Deal 10 damage.",
    art: "attack",
    effect: (player, enemy) => {
      dealDamage(enemy, 10);
    },
  },
  defend: {
    id: "defend",
    name: "Defend",
    cost: 1,
    type: "skill",
    text: "Gain 5 Block.",
    art: "defend",
    effect: (player, enemy) => {
      player.block += 5;
    },
  },
  fortify: {
    id: "fortify",
    name: "Fortify",
    cost: 2,
    type: "skill",
    text: "Gain 10 Block.",
    art: "defend",
    effect: (player, enemy) => {
      player.block += 10;
    },
  },
  poison_sting: {
    id: "poison_sting",
    name: "Poison Sting",
    cost: 1,
    type: "attack",
    text: "Deal 2 damage. Apply 3 Poison.",
    art: "poison",
    effect: (player, enemy) => {
      dealDamage(enemy, 2);
      applyStatus(enemy, "poison", 3);
    },
  },
  ember: {
    id: "ember",
    name: "Ember",
    cost: 1,
    type: "attack",
    text: "Deal 4 damage. Apply 2 Burn.",
    art: "fire",
    effect: (player, enemy) => {
      dealDamage(enemy, 4);
      applyStatus(enemy, "burn", 2);
    },
  },
  bash: {
    id: "bash",
    name: "Bash",
    cost: 1,
    type: "attack",
    text: "Deal 4 damage. Gain 2 Block.",
    art: "attack",
    effect: (player, enemy) => {
      dealDamage(enemy, 4);
      player.block += 2;
    },
  },
};

/** Apply damage to an actor, reducing block first. */
function dealDamage(actor, amount) {
  if (actor.block > 0) {
    const absorbed = Math.min(actor.block, amount);
    actor.block -= absorbed;
    amount -= absorbed;
  }
  actor.hp = Math.max(0, actor.hp - amount);
}

/** Apply or stack a status effect. */
function applyStatus(actor, key, amount) {
  if (!actor.statuses[key]) actor.statuses[key] = 0;
  actor.statuses[key] += amount;
}

/** Tick statuses at the start of the actor's turn. */
function tickStatuses(actor) {
  // Poison deals damage and decreases by 1.
  if (actor.statuses.poison > 0) {
    actor.hp = Math.max(0, actor.hp - actor.statuses.poison);
    actor.statuses.poison -= 1;
  }
  // Burn deals damage and decreases by 1.
  if (actor.statuses.burn > 0) {
    actor.hp = Math.max(0, actor.hp - actor.statuses.burn);
    actor.statuses.burn -= 1;
  }
}

/** Build a starter deck. */
function starterDeck() {
  return [
    "strike", "strike", "strike", "strike",
    "defend", "defend", "defend", "defend",
    "bash", "ember",
  ];
}

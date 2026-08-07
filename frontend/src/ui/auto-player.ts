import type { Game } from './game';
import { actInSession } from '../net/api';

const RANGED_RANGE = 4;

interface Pos { x: number; y: number }

export class AutoPlayer {
  private game: Game;
  private running = false;
  private pending = false;

  constructor(game: Game) {
    this.game = game;
  }

  start() {
    this.running = true;
    this.tick();
  }

  stop() {
    this.running = false;
  }

  isRunning() {
    return this.running;
  }

  onUpdate() {
    if (!this.running || this.pending) return;
    window.setTimeout(() => this.tick(), 350);
  }

  private async tick() {
    if (!this.running || this.pending) return;
    const session = this.game.getSession();
    const mod = this.game.getModule();
    if (!session || !mod || session.status !== 'active' || session.phase !== 'player') return;

    const player = session.player;
    if (!player || player.down || player.alive === false) {
      this.stop();
      return;
    }

    const aliveMonsters = session.monsters.filter((m) => m.alive !== false);
    if (aliveMonsters.length === 0) {
      this.stop();
      return;
    }

    this.pending = true;
    try {
      await this.takeTurn(session, mod, player, aliveMonsters);
    } finally {
      this.pending = false;
    }
  }

  private async takeTurn(
    session: any,
    mod: any,
    player: any,
    monsters: any[]
  ) {
    const occupied = new Set<string>();
    for (const t of [...session.players, ...session.monsters]) {
      if (t.alive !== false && t.id !== player.id) {
        occupied.add(`${t.x},${t.y}`);
      }
    }

    const isWalkable = (x: number, y: number) => {
      if (x < 0 || y < 0 || x >= mod.width || y >= mod.height) return false;
      const row = mod.tiles[y] || '';
      return row[x] !== '1' && !occupied.has(`${x},${y}`);
    };

    // Adjacent target -> melee.
    const adjacentMonster = this.findNearestAdjacent(player, monsters);
    if (adjacentMonster) {
      const { session: next } = await actInSession(session.id, 'attack', { target_id: adjacentMonster.id });
      this.game.update(next);
      return;
    }

    // Ranged target in LoS -> shoot.
    const rangedTarget = this.findRangedTarget(player, monsters, mod);
    if (rangedTarget) {
      const { session: next } = await actInSession(session.id, 'ranged', { target_id: rangedTarget.id });
      this.game.update(next);
      return;
    }

    // Move one step toward the nearest monster.
    const step = this.findStepTowards(player, monsters, isWalkable);
    if (step) {
      const { session: next } = await actInSession(session.id, 'move', { x: step.x, y: step.y });
      this.game.update(next);
      return;
    }

    // Nothing useful to do; end turn.
    const { session: next } = await actInSession(session.id, 'end_turn');
    this.game.update(next);
  }

  private findNearestAdjacent(player: Pos, monsters: any[]): any | null {
    let best: any | null = null;
    let bestDist = Infinity;
    for (const m of monsters) {
      const dist = Math.abs(player.x - m.x) + Math.abs(player.y - m.y);
      if (dist === 1 && dist < bestDist) {
        best = m;
        bestDist = dist;
      }
    }
    return best;
  }

  private findRangedTarget(player: Pos, monsters: any[], mod: any): any | null {
    let best: any | null = null;
    let bestDist = Infinity;
    for (const m of monsters) {
      const dist = Math.abs(player.x - m.x) + Math.abs(player.y - m.y);
      if (dist > 1 && dist <= RANGED_RANGE && dist < bestDist && this.hasLineOfSight(player, m, mod)) {
        best = m;
        bestDist = dist;
      }
    }
    return best;
  }

  private findStepTowards(
    player: Pos,
    monsters: any[],
    isWalkable: (x: number, y: number) => boolean
  ): Pos | null {
    // BFS from player over walkable, unoccupied tiles.
    const start = `${player.x},${player.y}`;
    const visited = new Set<string>([start]);
    const parent = new Map<string, string | null>();
    parent.set(start, null);
    const queue: Pos[] = [{ x: player.x, y: player.y }];

    let bestTarget: Pos | null = null;
    let bestScore = Infinity;

    while (queue.length > 0) {
      const cur = queue.shift()!;
      for (const m of monsters) {
        const d = Math.abs(cur.x - m.x) + Math.abs(cur.y - m.y);
        if (d < bestScore) {
          bestScore = d;
          bestTarget = cur;
        }
      }
      for (const [dx, dy] of [[0, -1], [0, 1], [-1, 0], [1, 0]]) {
        const nx = cur.x + dx;
        const ny = cur.y + dy;
        const key = `${nx},${ny}`;
        if (visited.has(key) || !isWalkable(nx, ny)) continue;
        visited.add(key);
        parent.set(key, `${cur.x},${cur.y}`);
        queue.push({ x: nx, y: ny });
      }
    }

    if (!bestTarget) return null;

    // Walk back from bestTarget to player; the first step after start is the move.
    let cur = `${bestTarget.x},${bestTarget.y}`;
    while (parent.get(cur)) {
      const prev = parent.get(cur)!;
      if (prev === start) {
        const [x, y] = cur.split(',').map(Number);
        return { x, y };
      }
      cur = prev;
    }
    return null;
  }

  private hasLineOfSight(a: Pos, b: Pos, mod: any): boolean {
    let dx = Math.abs(b.x - a.x);
    let dy = Math.abs(b.y - a.y);
    const sx = a.x < b.x ? 1 : -1;
    const sy = a.y < b.y ? 1 : -1;
    let err = dx - dy;
    let x = a.x;
    let y = a.y;
    while (x !== b.x || y !== b.y) {
      const e2 = 2 * err;
      if (e2 > -dy) {
        err -= dy;
        x += sx;
      }
      if (e2 < dx) {
        err += dx;
        y += sy;
      }
      if ((x !== a.x || y !== a.y) && mod.tiles[y]?.[x] === '1') {
        return false;
      }
    }
    return true;
  }
}

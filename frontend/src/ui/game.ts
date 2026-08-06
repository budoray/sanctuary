import { Application, Container, Graphics } from 'pixi.js';
import { actInSession, GameSession, Token } from '../net/api';
import { DiceTray } from './dice-tray';
import { TokenSprite } from './token-sprite';
import { el, clear } from './utils';

const TILE_SIZE = 40;
const WALL_BASE = 0x23262d;
const WALL_TOP = 0x3a3f4a;
const WALL_SHADOW = 0x15171c;
const FLOOR_COLOR = 0x121418;
const FLOOR_BORDER = 0x2c2f38;
const FLOOR_HIGHLIGHT = 0x1c1f25;
const VISION_RADIUS = 6;

interface ModuleData {
  width: number;
  height: number;
  tile_size: number;
  tiles: string[];
}

interface Particle {
  gfx: Graphics;
  vx: number;
  vy: number;
  life: number;
  maxLife: number;
}

export class Game {
  private root: HTMLElement;
  private sessionId: string;
  private module: ModuleData;
  private app: Application | null = null;
  private mapContainer: Container = new Container();
  private tokenContainer: Container = new Container();
  private fxContainer: Container = new Container();
  private ui: HTMLElement;
  private logEl: HTMLElement = document.createElement('div');
  private statusEl: HTMLElement = document.createElement('div');
  private timerEl: HTMLElement = document.createElement('div');
  private action: 'move' | 'attack' | null = null;
  private session: GameSession | null = null;
  private onExit: () => void;
  private canvasContainer: HTMLElement;
  private timerInterval: number | null = null;
  private timeoutFired = false;
  private tokenSprites: Map<string, TokenSprite> = new Map();
  private tileSprites: Graphics[][] = [];
  private shakeFrames = 0;
  private lastLogLength = 0;
  private particles: Particle[] = [];
  private ambientTime = 0;

  constructor(
    container: HTMLElement,
    sessionId: string,
    module: ModuleData,
    initialSession: GameSession,
    onExit: () => void
  ) {
    this.root = container;
    this.sessionId = sessionId;
    this.module = module;
    this.onExit = onExit;

    this.root.className = 'game-shell';
    this.canvasContainer = el('div', { className: 'game-canvas-container' });
    this.ui = this.buildUI();
    this.root.appendChild(this.canvasContainer);
    this.root.appendChild(this.ui);

    const trayAnchor = el('div', { className: 'tray-anchor' });
    this.root.appendChild(trayAnchor);
    new DiceTray(trayAnchor);

    this.update(initialSession);

    window.addEventListener('resize', () => this.centerMap());
  }

  async init() {
    this.app = new Application();
    await this.app.init({
      resizeTo: this.canvasContainer,
      backgroundColor: 0x050607,
      antialias: true,
    });
    this.canvasContainer.appendChild(this.app.canvas as HTMLCanvasElement);

    this.mapContainer = new Container();
    this.tokenContainer = new Container();
    this.fxContainer = new Container();
    this.app.stage.addChild(this.mapContainer);
    this.app.stage.addChild(this.tokenContainer);
    this.app.stage.addChild(this.fxContainer);

    this.renderMap();
    this.renderTokens(true);
    this.centerMap();

    this.app.ticker.add((ticker) => this.onTick(ticker));
  }

  private buildUI() {
    const hud = el('div', { className: 'game-hud' });
    hud.appendChild(el('h1', {}, 'Sanctuary'));
    this.statusEl = el('div', { className: 'game-status' }, 'Turn 1 · Your Move');
    hud.appendChild(this.statusEl);
    this.timerEl = el('div', { className: 'game-timer' });
    hud.appendChild(this.timerEl);

    const actions = el('div', { className: 'game-actions' });
    const moveBtn = el('button', { onclick: () => this.setAction('move') }, 'Move');
    const attackBtn = el('button', { onclick: () => this.setAction('attack') }, 'Attack');
    const endBtn = el('button', { onclick: () => this.endTurn() }, 'End Turn');
    actions.appendChild(moveBtn);
    actions.appendChild(attackBtn);
    actions.appendChild(endBtn);
    hud.appendChild(actions);

    this.logEl = el('div', { className: 'game-log' });
    hud.appendChild(el('h2', {}, 'Chronicle'));
    hud.appendChild(this.logEl);

    const exitBtn = el('button', { className: 'danger', onclick: () => this.onExit() }, 'Leave');
    hud.appendChild(exitBtn);

    return hud;
  }

  private setAction(action: 'move' | 'attack') {
    this.action = this.action === action ? null : action;
    this.updateStatus();
    this.highlightActionTiles();
  }

  private async endTurn() {
    if (!this.session || this.session.phase !== 'player') return;
    try {
      const { session } = await actInSession(this.sessionId, 'end_turn');
      this.action = null;
      this.update(session);
      if (session.phase === 'dm') {
        setTimeout(() => this.runDmTurn(), 600);
      }
    } catch (err: any) {
      this.log(err.message || 'End turn failed.');
    }
  }

  private async runDmTurn() {
    try {
      const { session } = await actInSession(this.sessionId, 'dm_turn');
      this.update(session);
    } catch (err: any) {
      this.log(err.message || 'DM turn failed.');
    }
  }

  private renderMap() {
    if (!this.app) return;
    this.mapContainer.removeChildren();
    this.tileSprites = [];
    for (let y = 0; y < this.module.height; y++) {
      const row = this.module.tiles[y] || '';
      const tileRow: Graphics[] = [];
      for (let x = 0; x < this.module.width; x++) {
        const tile = row[x] || '0';
        const g = new Graphics();
        this.drawTile(g, tile, x, y);
        g.x = x * TILE_SIZE;
        g.y = y * TILE_SIZE;
        g.eventMode = 'static';
        g.on('pointerdown', () => this.onTileClick(x, y));
        this.mapContainer.addChild(g);
        tileRow.push(g);
      }
      this.tileSprites.push(tileRow);
    }
    this.centerMap();
  }

  private drawTile(g: Graphics, tile: string, x: number, y: number) {
    if (tile === '1') {
      // Wall with depth
      g.rect(0, 0, TILE_SIZE, TILE_SIZE);
      g.fill({ color: WALL_SHADOW });
      g.rect(2, 2, TILE_SIZE - 4, TILE_SIZE - 4);
      g.fill({ color: WALL_BASE });
      g.rect(4, 4, TILE_SIZE - 8, TILE_SIZE - 8);
      g.fill({ color: WALL_TOP });
      // Cracks / stone detail
      g.rect(8, 10, 4, 12);
      g.fill({ color: WALL_BASE, alpha: 0.5 });
      g.rect(24, 20, 3, 8);
      g.fill({ color: WALL_BASE, alpha: 0.4 });
    } else {
      // Floor
      g.rect(0, 0, TILE_SIZE, TILE_SIZE);
      g.fill({ color: FLOOR_COLOR });
      g.rect(0, 0, TILE_SIZE, TILE_SIZE);
      g.stroke({ width: 1, color: FLOOR_BORDER });
      // Subtle stone speckle
      if ((x + y * 7) % 5 === 0) {
        g.rect(TILE_SIZE * 0.3, TILE_SIZE * 0.4, 2, 2);
        g.fill({ color: 0x2a2d35, alpha: 0.4 });
      }
      if ((x * 3 + y) % 7 === 0) {
        g.rect(TILE_SIZE * 0.7, TILE_SIZE * 0.2, 2, 2);
        g.fill({ color: 0x2a2d35, alpha: 0.3 });
      }
    }
  }

  private highlightActionTiles() {
    if (!this.session) return;
    const player = this.session.player;
    for (let y = 0; y < this.module.height; y++) {
      const row = this.module.tiles[y] || '';
      for (let x = 0; x < this.module.width; x++) {
        const g = this.tileSprites[y]?.[x];
        if (!g) continue;
        const tile = row[x] || '0';
        let highlight = false;
        if (this.action === 'move' && tile !== '1') {
          const dist = Math.abs(x - player.x) + Math.abs(y - player.y);
          highlight = dist === 1;
        }
        if (highlight) {
          g.tint = FLOOR_HIGHLIGHT;
        } else {
          g.tint = 0xffffff;
        }
      }
    }
  }

  private updateLighting() {
    if (!this.session) return;
    const px = this.session.player.x;
    const py = this.session.player.y;
    for (let y = 0; y < this.module.height; y++) {
      const row = this.module.tiles[y] || '';
      for (let x = 0; x < this.module.width; x++) {
        const tile = row[x] || '0';
        const dist = Math.sqrt((x - px) ** 2 + (y - py) ** 2);
        const isWall = tile === '1';
        let alpha: number;
        if (dist <= VISION_RADIUS - 1) {
          alpha = 1;
        } else if (dist <= VISION_RADIUS + 1) {
          const t = (dist - (VISION_RADIUS - 1)) / 2;
          alpha = 1 - t * (1 - (isWall ? 0.22 : 0.1));
        } else {
          alpha = isWall ? 0.22 : 0.1;
        }
        this.tileSprites[y][x].alpha = alpha;
      }
    }
  }

  private centerMap() {
    if (!this.app) return;
    const mw = this.module.width * TILE_SIZE;
    const mh = this.module.height * TILE_SIZE;
    const cx = (this.app.screen.width - mw) / 2;
    const cy = (this.app.screen.height - mh) / 2;
    const baseX = Math.max(0, cx);
    const baseY = Math.max(0, cy);
    this.applyMapPosition(baseX, baseY);
  }

  private applyMapPosition(x: number, y: number) {
    let ox = 0;
    let oy = 0;
    if (this.shakeFrames > 0) {
      const intensity = Math.min(this.shakeFrames, 8);
      ox = (Math.random() - 0.5) * intensity;
      oy = (Math.random() - 0.5) * intensity;
    }
    this.mapContainer.x = x + ox;
    this.mapContainer.y = y + oy;
    this.tokenContainer.x = x + ox;
    this.tokenContainer.y = y + oy;
    this.fxContainer.x = x + ox;
    this.fxContainer.y = y + oy;
  }

  private renderTokens(snap = false) {
    if (!this.session) return;
    const tokens: Token[] = [this.session.player, ...this.session.monsters];
    const aliveIds = new Set<string>();
    const playerPhase = this.session.phase === 'player';

    tokens.forEach((t) => {
      if (t.alive === false) {
        const existing = this.tokenSprites.get(t.id);
        if (existing) {
          this.spawnDeathParticles(existing.container.x + TILE_SIZE / 2, existing.container.y + TILE_SIZE / 2, t.type === 'player' ? 0x3498db : 0x2ecc71);
          existing.destroy();
          this.tokenSprites.delete(t.id);
        }
        return;
      }
      aliveIds.add(t.id);
      let sprite = this.tokenSprites.get(t.id);
      if (!sprite) {
        sprite = new TokenSprite(t, TILE_SIZE);
        sprite.container.eventMode = 'static';
        sprite.container.cursor = 'pointer';
        sprite.container.on('pointerdown', () => this.onTokenClick(t));
        this.tokenContainer.addChild(sprite.container);
        this.tokenSprites.set(t.id, sprite);
        if (snap) sprite.snapToTarget();
      }
      sprite.setTarget(t.x, t.y);
      sprite.updateHP(t.hp, t.max_hp);
      sprite.setActive(playerPhase && t.type === 'player');
    });

    for (const [id, sprite] of this.tokenSprites) {
      if (!aliveIds.has(id)) {
        sprite.destroy();
        this.tokenSprites.delete(id);
      }
    }
  }

  private spawnDeathParticles(x: number, y: number, color: number) {
    for (let i = 0; i < 12; i++) {
      const angle = (Math.PI * 2 * i) / 12 + Math.random() * 0.5;
      const speed = 1 + Math.random() * 2;
      this.spawnParticle(x, y, Math.cos(angle) * speed, Math.sin(angle) * speed, color, 30 + Math.random() * 20);
    }
  }

  private spawnSlashEffect(fromX: number, fromY: number, toX: number, toY: number) {
    const g = new Graphics();
    const cx = (fromX + toX) / 2 * TILE_SIZE + TILE_SIZE / 2;
    const cy = (fromY + toY) / 2 * TILE_SIZE + TILE_SIZE / 2;
    g.moveTo(cx - 12, cy - 12);
    g.lineTo(cx + 12, cy + 12);
    g.stroke({ width: 3, color: 0xffffff, alpha: 0.9 });
    g.moveTo(cx + 12, cy - 12);
    g.lineTo(cx - 12, cy + 12);
    g.stroke({ width: 3, color: 0xffffff, alpha: 0.9 });
    this.fxContainer.addChild(g);
    let life = 12;
    const tick = () => {
      life--;
      g.alpha = life / 12;
      if (life <= 0) {
        g.destroy();
        return;
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  private spawnParticle(x: number, y: number, vx: number, vy: number, color: number, life: number) {
    const g = new Graphics();
    g.circle(0, 0, 2 + Math.random() * 2);
    g.fill({ color });
    g.x = x;
    g.y = y;
    this.fxContainer.addChild(g);
    this.particles.push({ gfx: g, vx, vy, life, maxLife: life });
  }

  private onTick(ticker: import('pixi.js').Ticker) {
    const dt = ticker.deltaTime;
    const dtSec = dt / 60;
    const speed = 12;
    for (const sprite of this.tokenSprites.values()) {
      const dx = sprite.targetX - sprite.container.x;
      const dy = sprite.targetY - sprite.container.y;
      if (Math.abs(dx) > 0.1 || Math.abs(dy) > 0.1) {
        sprite.container.x += dx * (1 - Math.exp(-speed * dtSec));
        sprite.container.y += dy * (1 - Math.exp(-speed * dtSec));
      } else {
        sprite.container.x = sprite.targetX;
        sprite.container.y = sprite.targetY;
      }
      sprite.tick(dt);
    }

    if (this.shakeFrames > 0) {
      this.shakeFrames -= dt;
      this.centerMap();
    }

    // Particles
    for (let i = this.particles.length - 1; i >= 0; i--) {
      const p = this.particles[i];
      p.life -= dt;
      p.gfx.x += p.vx;
      p.gfx.y += p.vy;
      p.gfx.alpha = Math.max(0, p.life / p.maxLife);
      p.vx *= 0.95;
      p.vy *= 0.95;
      if (p.life <= 0) {
        p.gfx.destroy();
        this.particles.splice(i, 1);
      }
    }

    // Ambient torch flicker on tiles near player
    this.ambientTime += dtSec;
    if (this.session && this.app && this.ambientTime > 0.15) {
      this.ambientTime = 0;
      const px = this.session.player.x;
      const py = this.session.player.y;
      for (let y = Math.max(0, py - VISION_RADIUS); y <= Math.min(this.module.height - 1, py + VISION_RADIUS); y++) {
        for (let x = Math.max(0, px - VISION_RADIUS); x <= Math.min(this.module.width - 1, px + VISION_RADIUS); x++) {
          const g = this.tileSprites[y]?.[x];
          if (!g) continue;
          const dist = Math.sqrt((x - px) ** 2 + (y - py) ** 2);
          if (dist <= VISION_RADIUS && g.alpha > 0.3) {
            const flicker = 0.97 + Math.random() * 0.06;
            g.alpha = Math.min(1, g.alpha * flicker);
          }
        }
      }
    }
  }

  private async onTileClick(x: number, y: number) {
    if (!this.session || this.session.phase !== 'player' || this.action !== 'move') return;
    try {
      const { session } = await actInSession(this.sessionId, 'move', { x, y });
      this.action = null;
      this.update(session);
    } catch (err: any) {
      this.log(err.message || 'Move failed.');
    }
  }

  private async onTokenClick(token: Token) {
    if (!this.session || this.session.phase !== 'player' || this.action !== 'attack') return;
    if (token.type !== 'monster') return;
    const player = this.session.player;
    const isAdjacent = Math.abs(player.x - token.x) + Math.abs(player.y - token.y) === 1;
    try {
      const { session } = await actInSession(this.sessionId, 'attack', { target_id: token.id });
      this.action = null;
      if (isAdjacent) {
        this.spawnSlashEffect(player.x, player.y, token.x, token.y);
      }
      this.update(session);
      if (session.phase === 'dm') {
        setTimeout(() => this.runDmTurn(), 600);
      }
    } catch (err: any) {
      this.log(err.message || 'Attack failed.');
    }
  }

  private update(session: GameSession) {
    this.session = session;
    this.renderTokens();
    this.updateLighting();
    this.highlightActionTiles();
    this.updateStatus();
    this.updateTimer();
    this.renderLog();
  }

  private updateStatus() {
    if (!this.session) return;
    const phaseText = this.session.phase === 'player' ? 'Your Move' : "DM's Move";
    const actionText = this.action ? ` · ${this.action} mode` : '';
    this.statusEl.textContent = `Turn ${this.session.turn} · ${phaseText}${actionText}`;
    if (this.session.status !== 'active') {
      this.statusEl.textContent = `Game ${this.session.status.toUpperCase()}`;
    }
  }

  private updateTimer() {
    if (this.timerInterval) {
      window.clearInterval(this.timerInterval);
      this.timerInterval = null;
    }
    if (
      !this.session ||
      this.session.status !== 'active' ||
      this.session.phase !== 'player' ||
      this.session.turn_timer_seconds <= 0 ||
      !this.session.turn_deadline
    ) {
      this.timerEl.textContent = '';
      return;
    }

    const tick = () => {
      const deadline = new Date(this.session!.turn_deadline!).getTime();
      const remaining = Math.ceil((deadline - Date.now()) / 1000);
      if (remaining <= 0) {
        this.timerEl.textContent = 'Time up!';
        if (!this.timeoutFired) {
          this.timeoutFired = true;
          this.endTurn();
        }
      } else {
        this.timeoutFired = false;
        const mins = Math.floor(remaining / 60);
        const secs = remaining % 60;
        this.timerEl.textContent = `${mins}:${secs.toString().padStart(2, '0')} remaining`;
      }
    };

    tick();
    this.timerInterval = window.setInterval(tick, 250);
  }

  private renderLog() {
    clear(this.logEl);
    if (!this.session) return;
    const log = this.session.log;
    log.slice(-20).forEach((entry) => {
      this.logEl.appendChild(el('div', { className: 'log-entry' }, entry));
    });
    this.logEl.scrollTop = this.logEl.scrollHeight;

    if (log.length > this.lastLogLength) {
      const newEntries = log.slice(this.lastLogLength);
      const combatKeywords = ['strike', 'blow', 'hit', 'miss', 'pain', 'weapon', 'crumple', 'fall', 'dies', 'bites', 'stinging'];
      if (newEntries.some((e) => combatKeywords.some((k) => e.toLowerCase().includes(k)))) {
        this.shakeFrames = 12;
      }
      this.lastLogLength = log.length;
    }
  }

  private log(message: string) {
    this.logEl.appendChild(el('div', { className: 'log-entry error' }, message));
    this.logEl.scrollTop = this.logEl.scrollHeight;
  }

  destroy() {
    if (this.timerInterval) {
      window.clearInterval(this.timerInterval);
      this.timerInterval = null;
    }
    this.app?.destroy(true, { children: true });
    clear(this.root);
  }
}

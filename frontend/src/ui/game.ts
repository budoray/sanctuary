import { Application, Container, Graphics } from 'pixi.js';
import type { Socket } from 'socket.io-client';
import { actInSession, GameSession, Token } from '../net/api';
import { connectSocket } from '../net/socket';
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
  private statEl: HTMLElement = document.createElement('div');
  private partyEl: HTMLElement = document.createElement('div');
  private rosterEl: HTMLElement = document.createElement('div');
  private dmOverlay: HTMLElement = document.createElement('div');
  private damageFlash: HTMLElement = document.createElement('div');
  private action: 'move' | 'attack' | null = null;
  private session: GameSession | null = null;
  private userId: number | null = null;
  private onExit: () => void;
  private onReplay?: (characterId: string) => void;
  private canvasContainer: HTMLElement;
  private timerInterval: number | null = null;
  private timeoutFired = false;
  private tokenSprites: Map<string, TokenSprite> = new Map();
  private tileSprites: Graphics[][] = [];
  private lastTokenHp: Map<string, number> = new Map();
  private shakeFrames = 0;
  private lastLogLength = 0;
  private lastBannerTurn = 0;
  private particles: Particle[] = [];
  private ambientTime = 0;
  private cameraX = 0;
  private cameraY = 0;
  private tooltip: HTMLElement;
  private moveBtn!: HTMLButtonElement;
  private attackBtn!: HTMLButtonElement;
  private endBtn!: HTMLButtonElement;
  private dmTurnBtn!: HTMLButtonElement;
  private socket: Socket | null = null;

  constructor(
    container: HTMLElement,
    sessionId: string,
    module: ModuleData,
    initialSession: GameSession,
    onExit: () => void,
    onReplay?: (characterId: string) => void,
    userId?: number
  ) {
    this.root = container;
    this.sessionId = sessionId;
    this.module = module;
    this.userId = userId ?? null;
    this.onExit = onExit;
    this.onReplay = onReplay;

    this.root.className = 'game-shell';
    this.canvasContainer = el('div', { className: 'game-canvas-container' });
    this.ui = this.buildUI();
    this.root.appendChild(this.canvasContainer);
    this.root.appendChild(this.ui);

    this.tooltip = el('div', { className: 'token-tooltip' });
    this.tooltip.style.display = 'none';
    this.root.appendChild(this.tooltip);

    this.dmOverlay = el('div', { className: 'dm-overlay' });
    this.dmOverlay.innerHTML = '<div class="dm-spinner"></div><span>The DM ponders...</span>';
    this.dmOverlay.style.display = 'none';
    this.root.appendChild(this.dmOverlay);

    this.damageFlash = el('div', { className: 'damage-flash' });
    this.root.appendChild(this.damageFlash);

    const scanlines = el('div', { className: 'scanlines' });
    this.root.appendChild(scanlines);

    const trayAnchor = el('div', { className: 'tray-anchor' });
    this.root.appendChild(trayAnchor);
    new DiceTray(trayAnchor);

    this.update(initialSession);

    window.addEventListener('resize', () => this.centerMap());
    this.keydownHandler = (e: KeyboardEvent) => this.onKeyDown(e);
    window.addEventListener('keydown', this.keydownHandler);
  }

  private keydownHandler: ((e: KeyboardEvent) => void) | null = null;

  private isCampaignSession() {
    return !!this.session?.campaign_id;
  }

  private isDm() {
    return this.isCampaignSession() && this.session?.dm_account_id === this.userId;
  }

  private isPlayer() {
    if (!this.session) return false;
    const active = this.session.player;
    if (active && 'account_id' in active && active.account_id != null) {
      return active.account_id === this.userId;
    }
    // Fallback for older solo sessions.
    return !this.session.campaign_id || this.session.account_id === this.userId;
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

    this.socket = connectSocket();
    this.socket.emit('join_session', { session_id: this.sessionId });
    this.socket.on('session_update', (payload: { session?: GameSession }) => {
      if (payload.session && payload.session.id === this.sessionId) {
        this.update(payload.session);
      }
    });
  }

  private buildUI() {
    const hud = el('div', { className: 'game-hud' });
    hud.appendChild(el('h1', {}, 'Sanctuary'));
    this.statusEl = el('div', { className: 'game-status' }, 'Turn 1 · Your Move');
    hud.appendChild(this.statusEl);
    this.timerEl = el('div', { className: 'game-timer' });
    hud.appendChild(this.timerEl);

    const actions = el('div', { className: 'game-actions' });
    this.moveBtn = el('button', { onclick: () => this.setAction('move') }, 'Move [M]') as HTMLButtonElement;
    this.attackBtn = el('button', { onclick: () => this.setAction('attack') }, 'Attack [F]') as HTMLButtonElement;
    this.endBtn = el('button', { onclick: () => this.endTurn() }, 'End [E]') as HTMLButtonElement;
    actions.appendChild(this.moveBtn);
    actions.appendChild(this.attackBtn);
    actions.appendChild(this.endBtn);
    hud.appendChild(actions);

    this.dmTurnBtn = el('button', {
      className: 'dm-turn-btn',
      onclick: () => this.runDmTurn(),
    }, 'Run DM Turn') as HTMLButtonElement;
    this.dmTurnBtn.style.display = 'none';
    hud.appendChild(this.dmTurnBtn);

    this.statEl = el('div', { className: 'player-stats' });
    hud.appendChild(this.statEl);

    this.partyEl = el('div', { className: 'party-roster' });
    hud.appendChild(el('h2', {}, 'Party'));
    hud.appendChild(this.partyEl);

    this.rosterEl = el('div', { className: 'monster-roster' });
    hud.appendChild(el('h2', {}, 'Foes'));
    hud.appendChild(this.rosterEl);

    this.logEl = el('div', { className: 'game-log' });
    hud.appendChild(el('h2', {}, 'Chronicle'));
    hud.appendChild(this.logEl);

    const exitBtn = el('button', { className: 'danger', onclick: () => this.onExit() }, 'Leave');
    hud.appendChild(exitBtn);

    return hud;
  }

  private showTooltip(token: Token, clientX: number, clientY: number) {
    const subtitle = token.type === 'player'
      ? (token.classes || ['Adventurer']).join(' / ')
      : token.name;
    this.tooltip.innerHTML = `
      <strong>${token.name}</strong>
      <div class="token-tooltip-sub">${subtitle}</div>
      <div>HP ${token.hp}/${token.max_hp}</div>
      <div>AC ${token.ac}</div>
    `;
    this.tooltip.style.display = 'block';
    this.positionTooltip(clientX, clientY);
  }

  private moveTooltip(clientX: number, clientY: number) {
    if (this.tooltip.style.display === 'none') return;
    this.positionTooltip(clientX, clientY);
  }

  private positionTooltip(clientX: number, clientY: number) {
    const rect = this.root.getBoundingClientRect();
    const x = clientX - rect.left + 14;
    const y = clientY - rect.top + 14;
    const maxX = rect.width - 180;
    const maxY = rect.height - 90;
    this.tooltip.style.left = `${Math.min(x, maxX)}px`;
    this.tooltip.style.top = `${Math.min(y, maxY)}px`;
  }

  private hideTooltip() {
    this.tooltip.style.display = 'none';
  }

  private showGameOver() {
    if (!this.session || this.session.status === 'active') return;
    const existing = this.root.querySelector('.game-over-overlay');
    if (existing) return;
    const overlay = el('div', { className: 'game-over-overlay' });
    const panel = el('div', { className: 'game-over-panel' });
    const won = this.session.status === 'won';
    panel.appendChild(el('h1', {}, won ? 'Victory' : 'Defeat'));
    panel.appendChild(el('p', { className: 'message' }, won
      ? 'The lair is quiet. You survive to adventure again.'
      : 'Your light fades in the dark. The dungeon claims another.'));
    const canReplay = this.onReplay && this.session.character_id;
    if (canReplay) {
      const replay = el('button', { className: 'enter', onclick: () => this.onReplay!(this.session!.character_id!) }, 'Play Again');
      panel.appendChild(replay);
    }
    const leave = el('button', { onclick: () => this.onExit() }, 'Return to Sanctuary');
    panel.appendChild(leave);
    overlay.appendChild(panel);
    this.root.appendChild(overlay);
  }

  private setAction(action: 'move' | 'attack') {
    this.action = this.action === action ? null : action;
    this.updateStatus();
    this.highlightActionTiles();
  }

  private onKeyDown(e: KeyboardEvent) {
    if (!this.session || this.session.status !== 'active' || this.session.phase !== 'player') return;

    switch (e.key.toLowerCase()) {
      case 'escape':
        if (this.action) {
          this.action = null;
          this.updateStatus();
          this.highlightActionTiles();
        }
        break;
      case 'm':
        this.setAction('move');
        break;
      case 'f':
        this.setAction('attack');
        break;
      case 'e':
      case ' ':
        e.preventDefault();
        this.endTurn();
        break;
      case 'arrowup':
      case 'w':
        e.preventDefault();
        this.tryMove(0, -1);
        break;
      case 'arrowdown':
      case 's':
        e.preventDefault();
        this.tryMove(0, 1);
        break;
      case 'arrowleft':
      case 'a':
        e.preventDefault();
        this.tryMove(-1, 0);
        break;
      case 'arrowright':
      case 'd':
        e.preventDefault();
        this.tryMove(1, 0);
        break;
    }
  }

  private async tryMove(dx: number, dy: number) {
    if (!this.session || this.session.phase !== 'player' || this.session.status !== 'active') return;
    if (this.action && this.action !== 'move') return;
    const player = this.session.player;
    const x = player.x + dx;
    const y = player.y + dy;
    try {
      const { session } = await actInSession(this.sessionId, 'move', { x, y });
      this.action = null;
      this.update(session);
    } catch (err: any) {
      this.log(err.message || 'Move failed.');
    }
  }

  private async endTurn() {
    if (!this.session || this.session.phase !== 'player') return;
    try {
      const { session } = await actInSession(this.sessionId, 'end_turn');
      this.action = null;
      this.update(session);
      if (session.phase === 'dm' && !this.isCampaignSession()) {
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
    const target = this.playerPixelCenter();
    const mw = this.module.width * TILE_SIZE;
    const mh = this.module.height * TILE_SIZE;

    let baseX: number;
    let baseY: number;
    if (mw <= this.app.screen.width && mh <= this.app.screen.height) {
      baseX = (this.app.screen.width - mw) / 2;
      baseY = (this.app.screen.height - mh) / 2;
    } else {
      const px = target ? target.x : mw / 2;
      const py = target ? target.y : mh / 2;
      baseX = this.app.screen.width / 2 - px;
      baseY = this.app.screen.height / 2 - py;
      baseX = Math.min(0, Math.max(this.app.screen.width - mw, baseX));
      baseY = Math.min(0, Math.max(this.app.screen.height - mh, baseY));
    }

    this.cameraX = baseX;
    this.cameraY = baseY;
    this.applyMapPosition();
  }

  private updateCamera(dt: number) {
    if (!this.app) return;
    const target = this.playerPixelCenter();
    const mw = this.module.width * TILE_SIZE;
    const mh = this.module.height * TILE_SIZE;

    let desiredX: number;
    let desiredY: number;
    if (mw <= this.app.screen.width && mh <= this.app.screen.height) {
      desiredX = (this.app.screen.width - mw) / 2;
      desiredY = (this.app.screen.height - mh) / 2;
    } else {
      const px = target ? target.x : mw / 2;
      const py = target ? target.y : mh / 2;
      desiredX = this.app.screen.width / 2 - px;
      desiredY = this.app.screen.height / 2 - py;
      desiredX = Math.min(0, Math.max(this.app.screen.width - mw, desiredX));
      desiredY = Math.min(0, Math.max(this.app.screen.height - mh, desiredY));
    }

    const speed = 8;
    const dtSec = dt / 60;
    this.cameraX += (desiredX - this.cameraX) * (1 - Math.exp(-speed * dtSec));
    this.cameraY += (desiredY - this.cameraY) * (1 - Math.exp(-speed * dtSec));
    if (Math.abs(this.cameraX - desiredX) < 0.2) this.cameraX = desiredX;
    if (Math.abs(this.cameraY - desiredY) < 0.2) this.cameraY = desiredY;
    this.applyMapPosition();
  }

  private playerPixelCenter(): { x: number; y: number } | null {
    if (!this.session) return null;
    const sprite = this.tokenSprites.get(this.session.player.id);
    if (sprite) {
      return {
        x: sprite.targetX + TILE_SIZE / 2,
        y: sprite.targetY + TILE_SIZE / 2,
      };
    }
    return {
      x: this.session.player.x * TILE_SIZE + TILE_SIZE / 2,
      y: this.session.player.y * TILE_SIZE + TILE_SIZE / 2,
    };
  }

  private applyMapPosition() {
    let ox = 0;
    let oy = 0;
    if (this.shakeFrames > 0) {
      const intensity = Math.min(this.shakeFrames, 8);
      ox = (Math.random() - 0.5) * intensity;
      oy = (Math.random() - 0.5) * intensity;
    }
    this.mapContainer.x = this.cameraX + ox;
    this.mapContainer.y = this.cameraY + oy;
    this.tokenContainer.x = this.cameraX + ox;
    this.tokenContainer.y = this.cameraY + oy;
    this.fxContainer.x = this.cameraX + ox;
    this.fxContainer.y = this.cameraY + oy;
  }

  private renderTokens(snap = false) {
    if (!this.session) return;
    const session = this.session;
    const tokens: Token[] = [...session.players, ...session.monsters];
    const aliveIds = new Set<string>();

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
        sprite.container.on('pointerover', (e: any) => {
          const rect = this.canvasContainer.getBoundingClientRect();
          this.showTooltip(t, rect.left + e.global.x, rect.top + e.global.y);
        });
        sprite.container.on('pointermove', (e: any) => {
          const rect = this.canvasContainer.getBoundingClientRect();
          this.moveTooltip(rect.left + e.global.x, rect.top + e.global.y);
        });
        sprite.container.on('pointerout', () => this.hideTooltip());
        this.tokenContainer.addChild(sprite.container);
        this.tokenSprites.set(t.id, sprite);
        if (snap) sprite.snapToTarget();
      }
      sprite.setTarget(t.x, t.y);
      const prevHp = this.lastTokenHp.get(t.id);
      sprite.updateHP(t.hp, t.max_hp);
      if (prevHp !== undefined && t.hp !== prevHp) {
        const delta = t.hp - prevHp;
        sprite.showFloat(`${delta > 0 ? '+' : ''}${delta}`, delta < 0 ? 0xc0392b : 0x2ecc71);
        if (delta < 0) {
          this.spawnBloodSplatter(sprite.container.x + TILE_SIZE / 2, sprite.container.y + TILE_SIZE / 2, Math.abs(delta));
        }
      }
      const isActivePlayer = t.type === 'player' && t.id === session.player.id && session.phase === 'player';
      sprite.setActive(isActivePlayer);
    });

    this.lastTokenHp.clear();
    for (const t of tokens) {
      if (t.alive !== false) this.lastTokenHp.set(t.id, t.hp);
    }

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

  private spawnBloodSplatter(x: number, y: number, damage: number) {
    const count = Math.min(20, 6 + damage * 2);
    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = 0.8 + Math.random() * 2.5;
      this.spawnParticle(x, y, Math.cos(angle) * speed, Math.sin(angle) * speed, 0xc0392b, 25 + Math.random() * 20);
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
    }
    this.updateCamera(dt);

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
    const wasDm = this.session?.phase === 'dm';
    const playerHurt = this.session ? session.player.hp < this.session.player.hp : false;
    this.session = session;
    this.renderTokens();
    this.updateLighting();
    this.highlightActionTiles();
    this.updateStatus();
    this.updateActions();
    this.updateStats();
    this.updatePartyRoster();
    this.updateRoster();
    this.updateTimer();
    this.renderLog();

    if (session.status === 'active' && session.phase === 'player' && session.turn !== this.lastBannerTurn) {
      this.showTurnBanner(session.turn);
      this.lastBannerTurn = session.turn;
    }

    if (wasDm && session.phase === 'player' && playerHurt) {
      this.spawnMonsterAttackSlash();
      this.triggerDamageFlash();
    }
  }

  private triggerDamageFlash() {
    this.damageFlash.classList.remove('active');
    void this.damageFlash.offsetWidth; // reflow
    this.damageFlash.classList.add('active');
    window.setTimeout(() => this.damageFlash.classList.remove('active'), 350);
  }

  private showTurnBanner(turn: number) {
    const existing = this.root.querySelector('.turn-banner');
    if (existing) existing.remove();
    const banner = el('div', { className: 'turn-banner' });
    banner.innerHTML = `<span>Turn ${turn}</span>`;
    this.root.appendChild(banner);
    window.setTimeout(() => banner.classList.add('visible'), 10);
    window.setTimeout(() => {
      banner.classList.remove('visible');
      window.setTimeout(() => banner.remove(), 600);
    }, 1400);
  }

  private updateStats() {
    if (!this.session) return;
    const p = this.session.player;
    const ratio = Math.max(0, Math.min(1, p.hp / p.max_hp));
    const hpColor = ratio > 0.5 ? '#2ecc71' : ratio > 0.25 ? '#f1c40f' : '#c0392b';
    this.statEl.innerHTML = `
      <div class="player-name">${p.name}</div>
      <div class="player-class">${(p.classes || ['Adventurer']).join(' / ')}</div>
      <div class="hp-bar"><span style="width:${Math.round(ratio * 100)}%; background:${hpColor};"></span></div>
      <div class="hp-text">HP ${p.hp}/${p.max_hp}</div>
      <div class="ac-text">AC ${p.ac}</div>
    `;
  }

  private updatePartyRoster() {
    if (!this.session) return;
    clear(this.partyEl);
    const activeId = this.session.phase === 'player' ? this.session.player?.id : null;
    this.session.players.forEach((p) => {
      const isActive = p.id === activeId;
      const ratio = Math.max(0, Math.min(1, p.hp / p.max_hp));
      const hpColor = ratio > 0.5 ? '#2ecc71' : ratio > 0.25 ? '#f1c40f' : '#c0392b';
      const row = el('div', { className: `party-row${isActive ? ' active' : ''}` });
      row.appendChild(el('span', { className: 'party-name' }, p.name));
      const barWrap = el('div', { className: 'party-hp-bar' });
      barWrap.innerHTML = `<span style="width:${Math.round(ratio * 100)}%; background:${hpColor};"></span>`;
      row.appendChild(barWrap);
      row.appendChild(el('span', { className: 'party-hp-text' }, `${p.hp}/${p.max_hp}`));
      this.partyEl.appendChild(row);
    });
  }

  private updateRoster() {
    if (!this.session) return;
    clear(this.rosterEl);
    const alive = this.session.monsters.filter((m) => m.alive !== false);
    if (alive.length === 0) {
      this.rosterEl.appendChild(el('div', { className: 'empty-roster' }, 'None remain.'));
      return;
    }
    alive.forEach((m) => {
      const ratio = Math.max(0, Math.min(1, m.hp / m.max_hp));
      const hpColor = ratio > 0.5 ? '#2ecc71' : ratio > 0.25 ? '#f1c40f' : '#c0392b';
      const row = el('div', { className: 'monster-row' });
      row.appendChild(el('span', { className: 'monster-name' }, m.name));
      const barWrap = el('div', { className: 'monster-hp-bar' });
      barWrap.innerHTML = `<span style="width:${Math.round(ratio * 100)}%; background:${hpColor};"></span>`;
      row.appendChild(barWrap);
      this.rosterEl.appendChild(row);
    });
  }

  private spawnMonsterAttackSlash() {
    if (!this.session) return;
    const player = this.session.player;
    let attacker: Token | null = null;
    let bestDist = Infinity;
    for (const m of this.session.monsters) {
      if (m.alive === false) continue;
      const dist = Math.abs(m.x - player.x) + Math.abs(m.y - player.y);
      if (dist <= 1 && dist < bestDist) {
        attacker = m;
        bestDist = dist;
      }
    }
    if (attacker) {
      this.spawnSlashEffect(attacker.x, attacker.y, player.x, player.y);
      this.shakeFrames = 12;
    }
  }

  private updateActions() {
    const canAct =
      !!this.session &&
      this.session.status === 'active' &&
      this.session.phase === 'player' &&
      this.isPlayer();
    this.moveBtn.disabled = !canAct;
    this.attackBtn.disabled = !canAct;
    this.endBtn.disabled = !canAct;
  }

  private updateStatus() {
    if (!this.session) return;
    const isDmPhase = this.session.phase === 'dm';
    const isCampaign = this.isCampaignSession();
    let phaseText = this.session.phase === 'player' ? 'Your Move' : "DM's Move";
    if (isCampaign && isDmPhase && this.isDm()) {
      phaseText = "DM's Move · Run Turn";
    } else if (isCampaign && isDmPhase) {
      phaseText = "Waiting for DM";
    }
    const actionText = this.action ? ` · ${this.action} mode` : '';
    this.statusEl.textContent = `Turn ${this.session.turn} · ${phaseText}${actionText}`;

    const showDmBtn =
      this.session.status === 'active' && isDmPhase && isCampaign && this.isDm();
    this.dmTurnBtn.style.display = showDmBtn ? 'block' : 'none';

    this.dmOverlay.style.display =
      this.session.status === 'active' && isDmPhase ? 'flex' : 'none';
    if (this.session.status !== 'active') {
      this.statusEl.textContent = `Game ${this.session.status.toUpperCase()}`;
      this.dmOverlay.style.display = 'none';
      this.dmTurnBtn.style.display = 'none';
      this.showGameOver();
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
    if (!this.session) return;
    const log = this.session.log;

    if (log.length > this.lastLogLength) {
      const newCount = log.length - this.lastLogLength;
      for (let i = log.length - newCount; i < log.length; i++) {
        const entry = log[i];
        const isTurn = entry.startsWith('— Turn');
        const className = isTurn ? 'log-entry turn-marker' : 'log-entry fresh';
        const row = el('div', { className }, entry);
        this.logEl.appendChild(row);
        if (!isTurn) {
          window.setTimeout(() => row.classList.remove('fresh'), 600);
        }
      }
      // Trim old entries to keep the log from growing forever.
      while (this.logEl.childElementCount > 20) {
        this.logEl.firstElementChild?.remove();
      }
      const newEntries = log.slice(this.lastLogLength);
      const combatKeywords = ['strike', 'blow', 'hit', 'miss', 'pain', 'weapon', 'crumple', 'fall', 'dies', 'bites', 'stinging'];
      if (newEntries.some((e) => combatKeywords.some((k) => e.toLowerCase().includes(k)))) {
        this.shakeFrames = 12;
      }
      this.lastLogLength = log.length;
    } else if (this.logEl.childElementCount === 0) {
      log.slice(-20).forEach((entry) => {
        const isTurn = entry.startsWith('— Turn');
        const className = isTurn ? 'log-entry turn-marker' : 'log-entry';
        this.logEl.appendChild(el('div', { className }, entry));
      });
      this.lastLogLength = log.length;
    }

    this.logEl.scrollTop = this.logEl.scrollHeight;
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
    if (this.keydownHandler) {
      window.removeEventListener('keydown', this.keydownHandler);
      this.keydownHandler = null;
    }
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    this.app?.destroy(true, { children: true });
    clear(this.root);
  }
}

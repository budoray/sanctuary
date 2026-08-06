import { Application, Container, Graphics, Text } from 'pixi.js';
import { actInSession, GameSession, Token } from '../net/api';
import { DiceTray } from './dice-tray';
import { el, clear } from './utils';

const TILE_SIZE = 40;
const WALL_COLOR = 0x2a2d35;
const FLOOR_COLOR = 0x121418;
const FLOOR_BORDER = 0x2c2f38;

interface ModuleData {
  width: number;
  height: number;
  tile_size: number;
  tiles: string[];
}

export class Game {
  private root: HTMLElement;
  private sessionId: string;
  private module: ModuleData;
  private app: Application;
  private mapContainer: Container;
  private tokenContainer: Container;
  private ui: HTMLElement;
  private logEl: HTMLElement = document.createElement('div');
  private statusEl: HTMLElement = document.createElement('div');
  private action: 'move' | 'attack' | null = null;
  private session: GameSession | null = null;
  private onExit: () => void;

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
    const canvasContainer = el('div', { className: 'game-canvas-container' });
    this.ui = this.buildUI();
    this.root.appendChild(canvasContainer);
    this.root.appendChild(this.ui);

    const trayAnchor = el('div', { className: 'tray-anchor' });
    this.root.appendChild(trayAnchor);
    new DiceTray(trayAnchor);

    this.app = new Application({
      resizeTo: canvasContainer,
      backgroundColor: 0x050607,
      antialias: true,
    });
    canvasContainer.appendChild(this.app.view as HTMLCanvasElement);

    this.mapContainer = new Container();
    this.tokenContainer = new Container();
    this.app.stage.addChild(this.mapContainer);
    this.app.stage.addChild(this.tokenContainer);

    this.renderMap();
    this.update(initialSession);

    window.addEventListener('resize', () => this.centerMap());
  }

  private buildUI() {
    const hud = el('div', { className: 'game-hud' });
    hud.appendChild(el('h1', {}, 'SANCTUARY'));
    this.statusEl = el('div', { className: 'game-status' }, 'Turn 1 · Your Move');
    hud.appendChild(this.statusEl);

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
  }

  private async endTurn() {
    if (!this.session || this.session.phase !== 'player') return;
    try {
      const { session } = await actInSession(this.sessionId, 'end_turn');
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
    this.mapContainer.removeChildren();
    for (let y = 0; y < this.module.height; y++) {
      const row = this.module.tiles[y] || '';
      for (let x = 0; x < this.module.width; x++) {
        const tile = row[x] || '0';
        const g = new Graphics();
        const color = tile === '1' ? WALL_COLOR : FLOOR_COLOR;
        g.rect(0, 0, TILE_SIZE, TILE_SIZE);
        g.fill({ color });
        if (tile !== '1') {
          g.rect(0, 0, TILE_SIZE, TILE_SIZE);
          g.stroke({ width: 1, color: FLOOR_BORDER });
        }
        g.x = x * TILE_SIZE;
        g.y = y * TILE_SIZE;
        g.eventMode = 'static';
        g.on('pointerdown', () => this.onTileClick(x, y));
        this.mapContainer.addChild(g);
      }
    }
    this.centerMap();
  }

  private centerMap() {
    const mw = this.module.width * TILE_SIZE;
    const mh = this.module.height * TILE_SIZE;
    const cx = (this.app.screen.width - mw) / 2;
    const cy = (this.app.screen.height - mh) / 2;
    this.mapContainer.x = Math.max(0, cx);
    this.mapContainer.y = Math.max(0, cy);
    this.tokenContainer.x = this.mapContainer.x;
    this.tokenContainer.y = this.mapContainer.y;
  }

  private renderTokens() {
    this.tokenContainer.removeChildren();
    if (!this.session) return;
    const tokens = [this.session.player, ...this.session.monsters];
    tokens.forEach((t) => {
      if (t.alive === false) return;
      const g = new Graphics();
      g.rect(4, 4, TILE_SIZE - 8, TILE_SIZE - 8);
      g.fill({ color: parseInt(t.color.replace('#', ''), 16) });
      g.x = t.x * TILE_SIZE;
      g.y = t.y * TILE_SIZE;
      g.eventMode = 'static';
      g.on('pointerdown', () => this.onTokenClick(t));
      this.tokenContainer.addChild(g);

      const label = new Text({
        text: t.name,
        style: {
          fontSize: 10,
          fill: 0xffffff,
          align: 'center',
        },
      });
      label.anchor.set(0.5, 1);
      label.x = g.x + TILE_SIZE / 2;
      label.y = g.y - 2;
      this.tokenContainer.addChild(label);
    });
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
    try {
      const { session } = await actInSession(this.sessionId, 'attack', { target_id: token.id });
      this.action = null;
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
    this.updateStatus();
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

  private renderLog() {
    clear(this.logEl);
    if (!this.session) return;
    this.session.log.slice(-20).forEach((entry) => {
      this.logEl.appendChild(el('div', { className: 'log-entry' }, entry));
    });
    this.logEl.scrollTop = this.logEl.scrollHeight;
  }

  private log(message: string) {
    this.logEl.appendChild(el('div', { className: 'log-entry error' }, message));
    this.logEl.scrollTop = this.logEl.scrollHeight;
  }

  destroy() {
    this.app.destroy(true, { children: true });
    clear(this.root);
  }
}

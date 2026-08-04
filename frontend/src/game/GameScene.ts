import * as PIXI from 'pixi.js';
import { GameMap } from './Map';
import { Token } from './Token';
import { createSession, getSession, moveToken, whoami } from '../net/api';
import { connectSocket } from '../net/socket';
import { HUD } from '../ui/HUD';
import { Socket } from 'socket.io-client';

interface TokenData {
  id: string;
  name: string;
  x: number;
  y: number;
  color: string;
  owner?: string | null;
}

interface SessionState {
  id: string;
  turn: number;
  phase: string;
  log: Array<{ turn: number; text: string }>;
  map: {
    width: number;
    height: number;
    tile_size: number;
    tokens: TokenData[];
  };
}

export class GameScene {
  private app!: PIXI.Application;
  private map: GameMap | null = null;
  private tokens: Map<string, Token> = new Map();
  private selectedTokenId: string | null = null;
  private sessionId: string | null = null;
  private socket: Socket;
  private hud: HUD;
  private phase: string = 'player';

  constructor(private container: HTMLElement = document.body) {
    this.hud = new HUD(container);
    this.socket = connectSocket();
    this.setupSocket();
    this.createControls();
    this.loadUser();
  }

  private async loadUser() {
    try {
      const data = await whoami();
      this.hud.setUser(data.user.name, data.user.id);
    } catch (e) {
      // 401 will redirect; other errors are silent for now.
    }
  }

  private setupSocket() {
    this.socket.on('message', (msg: any) => {
      if (msg.type === 'move' && msg.token_id) {
        this.updateTokenPosition(msg.token_id, msg.x, msg.y);
      }
      if (msg.type === 'system') {
        this.hud.setStatus(msg.text);
      }
      if (msg.type === 'dm_turn' && msg.entry) {
        this.hud.addLog(msg.entry.text);
        this.hud.setStatus("DM's turn complete. Your move.");
        this.phase = 'player';
        this.hud.setTurn(msg.entry.turn, 'player');
      }
    });
  }

  private createControls() {
    const controls = document.createElement('div');
    controls.id = 'controls';

    const newBtn = document.createElement('button');
    newBtn.textContent = 'New Session';
    newBtn.onclick = () => this.newSession();
    controls.appendChild(newBtn);

    this.container.appendChild(controls);
  }

  async newSession() {
    this.hud.setStatus('Creating session...');
    try {
      const data = await createSession();
      await this.loadSession(data.session_id, data.state);
    } catch (e) {
      this.hud.setStatus(`Error: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  async loadSession(id: string, state?: SessionState) {
    if (!state) {
      const data = await getSession(id);
      state = data.state as SessionState;
    }
    if (!state) {
      throw new Error('Session state not found');
    }
    this.sessionId = id;
    this.phase = state.phase || 'player';
    this.hud.setSession(id);
    this.hud.setTurn(state.turn, this.phase);
    this.hud.setStatus(this.phase === 'player' ? 'Click a tile to move the Hero.' : "DM is thinking...");
    this.hud.clearLog();
    for (const entry of state.log || []) {
      this.hud.addLog(entry.text);
    }
    await this.renderState(state);
    this.socket.emit('join_session', { session_id: id });
  }

  private async renderState(state: SessionState) {
    if (this.app) {
      this.app.destroy(true);
      this.tokens.clear();
    }

    const tileSize = state.map.tile_size || 32;
    const canvasWidth = state.map.width * tileSize;
    const canvasHeight = state.map.height * tileSize;

    this.app = new PIXI.Application();
    await this.app.init({
      width: canvasWidth,
      height: canvasHeight,
      background: 0x0d0e10,
      antialias: true,
      resolution: window.devicePixelRatio || 1,
      autoDensity: true,
    });
    this.app.canvas.id = 'game-canvas';
    this.container.appendChild(this.app.canvas as HTMLCanvasElement);

    this.map = new GameMap(state.map.width, state.map.height, tileSize);
    this.app.stage.addChild(this.map.view);

    for (const t of state.map.tokens) {
      this.addToken(t);
    }

    this.setupInput();
  }

  private addToken(data: TokenData) {
    const tileSize = this.map!.tileSize;
    const token = new Token(this.app, data, tileSize);
    token.view.eventMode = 'static';
    token.view.cursor = 'pointer';
    token.view.on('pointerdown', (e: Event) => {
      e.stopPropagation();
      this.selectToken(data.id);
    });
    this.tokens.set(data.id, token);
    this.app.stage.addChild(token.view);
  }

  private selectToken(id: string) {
    this.selectedTokenId = id;
    for (const [tid, t] of this.tokens) {
      t.highlight(tid === id);
    }
    this.hud.setStatus(`Selected ${this.tokens.get(id)?.name}. Click a tile to move.`);
  }

  private setupInput() {
    this.app.stage.eventMode = 'static';
    this.app.stage.hitArea = this.app.screen;
    this.app.stage.on('pointerdown', async (e: any) => {
      if (!this.selectedTokenId || !this.sessionId || !this.map) return;
      if (this.phase !== 'player') {
        this.hud.setStatus("Wait for the DM's turn to finish.");
        return;
      }
      const pos = e.global;
      const tx = Math.floor(pos.x / this.map.tileSize);
      const ty = Math.floor(pos.y / this.map.tileSize);

      if (tx < 0 || tx >= this.map.width || ty < 0 || ty >= this.map.height) return;

      this.map.highlightTile(tx, ty);
      this.phase = 'dm';
      this.hud.setStatus("DM is thinking...");
      try {
        await moveToken(this.sessionId, this.selectedTokenId, tx, ty);
      } catch (err) {
        this.phase = 'player';
        this.hud.setStatus(`Move failed: ${err instanceof Error ? err.message : String(err)}`);
      }
    });
  }

  private updateTokenPosition(id: string, x: number, y: number) {
    const token = this.tokens.get(id);
    if (!token) return;
    token.setGridPosition(x, y);
    if (this.map) this.map.highlightTile(x, y);
  }
}

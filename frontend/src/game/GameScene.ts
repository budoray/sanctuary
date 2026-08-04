import * as PIXI from 'pixi.js';
import { GameMap, MapData, TokenData } from './Map';
import { Token } from './Token';
import { createSession, getSession, moveToken, attackToken, whoami } from '../net/api';
import { connectSocket } from '../net/socket';
import { HUD, CharacterInfo } from '../ui/HUD';
import { Socket } from 'socket.io-client';

interface SessionState {
  id: string;
  turn: number;
  phase: string;
  log: Array<{ turn: number; text: string }>;
  map: MapData;
}

export class GameScene {
  private app!: PIXI.Application;
  private map: GameMap | null = null;
  private tokens: Map<string, Token> = new Map();
  private selectedTokenId: string | null = null;
  private targetTokenId: string | null = null;
  private sessionId: string | null = null;
  private socket: Socket;
  private hud: HUD;
  private phase: string = 'player';
  private actionMode: 'move' | 'attack' | null = 'move';
  private character: CharacterInfo | null = null;

  constructor(private container: HTMLElement = document.body) {
    this.hud = new HUD(container);
    this.socket = connectSocket();
    this.setupSocket();
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
      if (msg.type === 'attack') {
        this.showAttack(msg);
      }
      if (msg.type === 'system') {
        this.hud.setStatus(msg.text);
      }
      if (msg.type === 'dm_turn' && msg.entry) {
        this.hud.addLog(msg.entry.text);
        this.hud.setStatus("DM's turn complete. Your move.");
        this.phase = 'player';
        this.actionMode = 'move';
        this.hud.setTurn(msg.entry.turn, 'player');
        this.updateActions();
        this.updateFog();
      }
    });
  }

  async newSession() {
    this.hud.setStatus('Creating session...');
    try {
      const data = await createSession();
      if (data.character) {
        this.character = data.character as CharacterInfo;
        this.hud.setCharacter(this.character);
      }
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
    this.actionMode = this.phase === 'player' ? 'move' : null;
    this.hud.setSession(id);
    this.hud.setTurn(state.turn, this.phase);
    this.hud.setStatus(this.phase === 'player' ? 'Select a token, then click a tile to move.' : "DM is thinking...");
    this.hud.clearLog();
    for (const entry of state.log || []) {
      this.hud.addLog(entry.text);
    }
    await this.renderState(state);
    this.socket.emit('join_session', { session_id: id });
    this.updateActions();
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
      background: 0x050607,
      antialias: true,
      resolution: window.devicePixelRatio || 1,
      autoDensity: true,
    });
    this.app.canvas.id = 'game-canvas';
    this.container.appendChild(this.app.canvas as HTMLCanvasElement);

    this.map = GameMap.fromData(state.map);
    this.app.stage.addChild(this.map.view);

    for (const t of state.map.tokens) {
      this.addToken(t);
    }

    this.updateFog();
    this.setupInput();
  }

  private addToken(data: TokenData) {
    const tileSize = this.map!.tileSize;
    const token = new Token(this.app, data, tileSize);
    token.view.eventMode = 'static';
    token.view.cursor = 'pointer';
    token.view.on('pointerdown', (e: Event) => {
      e.stopPropagation();
      this.onTokenClick(data);
    });
    this.tokens.set(data.id, token);
    this.app.stage.addChild(token.view);
  }

  private onTokenClick(data: TokenData) {
    if (!this.sessionId || this.phase !== 'player') return;

    const token = this.tokens.get(data.id);
    if (!token) return;

    if (data.owner === 'player') {
      this.selectToken(data.id);
      return;
    }

    // Enemy token clicked
    if (this.actionMode === 'attack' && this.selectedTokenId) {
      this.targetTokenId = data.id;
      this.performAttack();
    } else {
      this.hud.setStatus('Select an action or a player token first.');
    }
  }

  private selectToken(id: string) {
    this.selectedTokenId = id;
    this.targetTokenId = null;
    for (const [tid, t] of this.tokens) {
      t.highlight(tid === id);
      t.markTarget(false);
    }
    const token = this.tokens.get(id);
    this.hud.setStatus(`Selected ${token?.name}. Choose an action or click a destination.`);
    this.updateActions();
  }

  private setActionMode(mode: 'move' | 'attack') {
    this.actionMode = mode;
    const token = this.selectedTokenId ? this.tokens.get(this.selectedTokenId) : null;
    if (mode === 'attack' && token) {
      this.hud.setStatus(`Attack mode: click an enemy adjacent to ${token.name}.`);
    } else if (token) {
      this.hud.setStatus(`Move mode: click a floor tile to move ${token.name}.`);
    }
    this.updateActions();
  }

  private updateActions() {
    const canAct = this.phase === 'player';
    this.hud.setActions([
      {
        id: 'move',
        label: 'Move',
        disabled: !canAct,
        onClick: () => this.setActionMode('move'),
      },
      {
        id: 'attack',
        label: 'Attack',
        disabled: !canAct || !this.selectedTokenId,
        onClick: () => this.setActionMode('attack'),
      },
      {
        id: 'new',
        label: 'New Session',
        onClick: () => this.newSession(),
      },
    ]);
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

      const token = this.tokens.get(this.selectedTokenId);
      if (!token) return;

      if (this.actionMode === 'attack') {
        const target = this.tokensAt(tx, ty).find((t) => t.owner !== 'player');
        if (target) {
          this.targetTokenId = target.id;
          await this.performAttack();
        } else {
          this.hud.setStatus('Select an enemy to attack.');
        }
        return;
      }

      // Move mode
      if (!this.map.isWalkable(tx, ty)) {
        this.hud.setStatus('That space is blocked.');
        return;
      }

      const dist = Math.abs(tx - token.gridX) + Math.abs(ty - token.gridY);
      if (dist !== 1) {
        this.hud.setStatus('You can move one tile per turn.');
        return;
      }

      this.map.highlightTile(tx, ty, 0x3498db);
      this.phase = 'dm';
      this.hud.setStatus("DM is thinking...");
      this.hud.setTurn(0, 'dm');
      this.updateActions();
      try {
        await moveToken(this.sessionId, this.selectedTokenId, tx, ty);
      } catch (err) {
        this.phase = 'player';
        this.hud.setStatus(`Move failed: ${err instanceof Error ? err.message : String(err)}`);
        this.updateActions();
      }
    });
  }

  private tokensAt(x: number, y: number): TokenData[] {
    return Array.from(this.tokens.values())
      .filter((t) => t.gridX === x && t.gridY === y)
      .map((t) => ({
        id: t.id,
        name: t.name,
        x: t.gridX,
        y: t.gridY,
        color: t.color,
        owner: t.owner,
      }));
  }

  private async performAttack() {
    if (!this.sessionId || !this.selectedTokenId || !this.targetTokenId) return;

    const attacker = this.tokens.get(this.selectedTokenId);
    const target = this.tokens.get(this.targetTokenId);
    if (!attacker || !target) return;

    const dist = Math.abs(attacker.gridX - target.gridX) + Math.abs(attacker.gridY - target.gridY);
    if (dist !== 1) {
      this.hud.setStatus('Target must be adjacent.');
      return;
    }

    this.phase = 'dm';
    this.hud.setStatus("DM is thinking...");
    this.hud.setTurn(0, 'dm');
    this.updateActions();

    try {
      await attackToken(this.sessionId, this.selectedTokenId, this.targetTokenId);
    } catch (err) {
      this.phase = 'player';
      this.hud.setStatus(`Attack failed: ${err instanceof Error ? err.message : String(err)}`);
      this.updateActions();
    }
  }

  private updateTokenPosition(id: string, x: number, y: number) {
    const token = this.tokens.get(id);
    if (!token) return;
    token.setGridPosition(x, y);
    if (this.map) this.map.highlightTile(x, y, 0x3498db);
    this.updateFog();
  }

  private showAttack(msg: any) {
    const target = this.tokens.get(msg.target_id);
    if (target) {
      target.playHitEffect();
      if (msg.damage) {
        this.showFloatingText(`${msg.damage}`, target.view.x, target.view.y - 20, 0xc0392b);
      }
    }
  }

  private showFloatingText(text: string, x: number, y: number, color: number) {
    const t = new PIXI.Text({
      text,
      style: {
        fontFamily: 'ui-monospace, monospace',
        fontSize: 14,
        fill: color,
        fontWeight: 'bold',
        dropShadow: {
          color: 0x000000,
          alpha: 0.8,
          angle: 45,
          distance: 1,
          blur: 2,
        },
      },
    });
    t.anchor.set(0.5);
    t.x = x;
    t.y = y;
    this.app.stage.addChild(t);

    const startTime = performance.now();
    const duration = 900;
    const startY = y;
    const tick = (now: number) => {
      const elapsed = now - startTime;
      const p = Math.min(1, elapsed / duration);
      t.y = startY - p * 30;
      t.alpha = 1 - p;
      if (p < 1) {
        requestAnimationFrame(tick);
      } else {
        t.destroy();
      }
    };
    requestAnimationFrame(tick);
  }

  private updateFog() {
    const player = Array.from(this.tokens.values()).find((t) => t.owner === 'player');
    if (player && this.map) {
      this.map.updateFog(player.gridX, player.gridY, 7);
    }
  }
}

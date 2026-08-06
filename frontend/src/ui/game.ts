import { Application, Container, Graphics, Sprite } from 'pixi.js';
import type { Socket } from 'socket.io-client';
import {
  actInSession, advanceSession, dmMove, dmReveal, dmSpawn, GameSession,
  getModule, getSessionPresence, Presence, restInSession, saveProgress, Token,
} from '../net/api';
import { connectSocket } from '../net/socket';
import { DiceTray } from './dice-tray';
import { TokenSprite } from './token-sprite';
import { el, clear } from './utils';
import { AudioController } from './audio';
import { getTheme, loadAtlas, tileFrame } from '../lib/tile-atlas';

const TILE_SIZE = 40;

function withTimeout<T>(promise: Promise<T>, ms: number, reason = 'Operation timed out'): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error(reason)), ms);
    promise
      .then((value) => { window.clearTimeout(timer); resolve(value); })
      .catch((err) => { window.clearTimeout(timer); reject(err); });
  });
}

const WALL_BASE = 0x23262d;
const WALL_TOP = 0x3a3f4a;
const WALL_SHADOW = 0x15171c;
const FLOOR_COLOR = 0x121418;
const FLOOR_BORDER = 0x2c2f38;
const FLOOR_HIGHLIGHT = 0x1c1f25;
const FLOOR_RANGE_HIGHLIGHT = 0x2a3a1a;
const VISION_RADIUS = 6;
const RANGED_RANGE = 4;
const TRAP_COLOR = 0x8b0000;
const TRAP_HIGHLIGHT = 0xff4444;

interface ModuleData {
  width: number;
  height: number;
  tile_size: number;
  tiles: string[];
  theme?: string;
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
  private action: 'move' | 'attack' | 'ranged' | 'ability' | null = null;
  private session: GameSession | null = null;
  private userId: number | null = null;
  private onExit: () => void;
  private onReplay?: (characterId: string) => void;
  private canvasContainer: HTMLElement;
  private timerInterval: number | null = null;
  private timeoutFired = false;
  private tokenSprites: Map<string, TokenSprite> = new Map();
  private tileSprites: Container[][] = [];
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
  private rangedBtn!: HTMLButtonElement;
  private potionBtn!: HTMLButtonElement;
  private abilityBtn!: HTMLButtonElement;
  private stabilizeBtn!: HTMLButtonElement;
  private restBtn!: HTMLButtonElement;
  private endBtn!: HTMLButtonElement;
  private saveBtn!: HTMLButtonElement;
  private dmTurnBtn!: HTMLButtonElement;
  private dmToolsEl: HTMLElement = document.createElement('div');
  private dmMonsterSelect: HTMLSelectElement = document.createElement('select');
  private dmTokenSelect: HTMLSelectElement = document.createElement('select');
  private dmAction: 'spawn' | 'move' | 'reveal' | null = null;
  private socket: Socket | null = null;
  private visited: Set<string> = new Set();
  private audio = new AudioController();
  private chatPanel: HTMLElement | null = null;
  private chatMessages: HTMLElement = document.createElement('div');
  private chatInput: HTMLInputElement = document.createElement('input');
  private chatCollapsed = false;
  private presencePanel: HTMLElement | null = null;
  private presenceList: HTMLElement = document.createElement('div');
  private journalPanel: HTMLElement | null = null;
  private journalOpen = false;
  private heartbeatInterval: number | null = null;
  private moduleId: string;
  private loadingOverlay: HTMLElement;

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
    this.moduleId = initialSession.module_id;
    this.userId = userId ?? null;
    this.onExit = onExit;
    this.onReplay = onReplay;

    this.root.className = 'game-shell';
    this.canvasContainer = el('div', { className: 'game-canvas-container' });
    this.ui = this.buildUI();
    this.chatPanel = this.buildChatPanel();
    this.presencePanel = this.buildPresencePanel();
    this.root.appendChild(this.canvasContainer);
    this.root.appendChild(this.ui);
    if (this.presencePanel) this.root.appendChild(this.presencePanel);
    if (this.chatPanel) this.root.appendChild(this.chatPanel);

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

    this.loadingOverlay = el('div', { className: 'game-loading' });
    this.loadingOverlay.innerHTML = '<div class="game-loading-spinner"></div><span>Entering the realm...</span>';
    this.root.appendChild(this.loadingOverlay);

    this.update(initialSession);

    window.addEventListener('resize', () => this.centerMap());
    this.keydownHandler = (e: KeyboardEvent) => this.onKeyDown(e);
    window.addEventListener('keydown', this.keydownHandler);

    this.beforeUnloadHandler = () => {
      if (this.session && this.session.status !== 'won') {
        this.saveProgression().catch(() => {});
      }
    };
    window.addEventListener('beforeunload', this.beforeUnloadHandler);
  }

  private keydownHandler: ((e: KeyboardEvent) => void) | null = null;
  private beforeUnloadHandler: ((e: BeforeUnloadEvent) => void) | null = null;

  private isCampaignSession() {
    return !!this.session?.campaign_id;
  }

  private isDm() {
    return this.isCampaignSession() && this.session?.dm_account_id === this.userId;
  }

  private isPlayer() {
    if (!this.session) return false;
    const active = this.session.player;
    if (active?.down) return false;
    if (active && 'account_id' in active && active.account_id != null) {
      return active.account_id === this.userId;
    }
    // Fallback for older solo sessions.
    return !this.session.campaign_id || this.session.account_id === this.userId;
  }

  private setLoadingStatus(text: string) {
    const span = this.loadingOverlay.querySelector('span');
    if (span) span.textContent = text;
  }

  async init() {
    // Safety net: never let the loading overlay block the player forever.
    const safetyTimeout = window.setTimeout(() => {
      // eslint-disable-next-line no-console
      console.error('Game init safety timeout fired; forcing overlay removal.');
      this.loadingOverlay?.remove();
    }, 15000);

    const releaseSafety = () => window.clearTimeout(safetyTimeout);

    try {
      this.app = new Application();
      this.setLoadingStatus('Opening the gate...');
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

      this.setLoadingStatus('Loading realm tiles...');
      try {
        await withTimeout(loadAtlas(), 5000, 'Tile atlas load timed out');
      } catch (err: any) {
        // eslint-disable-next-line no-console
        console.warn('Proceeding without tile atlas:', err);
      }

      this.setLoadingStatus('Carving the dungeon...');
      this.renderMap();
      this.renderTokens(true);
      this.centerMap();

      this.app.ticker.add((ticker) => this.onTick(ticker));

      this.setLoadingStatus('Joining the session...');
      this.socket = connectSocket();
      this.socket.emit('join_session', { session_id: this.sessionId });
      this.socket.on('session_update', (payload: { session?: GameSession }) => {
        if (payload.session && payload.session.id === this.sessionId) {
          this.update(payload.session);
        }
      });
      this.socket.on('chat_broadcast', (payload: { account_id?: number; name?: string; text?: string; timestamp?: string }) => {
        this.appendChatMessage(payload);
      });
      this.socket.on('presence_update', (payload: { session_id?: string; present?: Presence[] }) => {
        if (payload.session_id === this.sessionId && payload.present) {
          this.updatePresence(payload.present);
        }
      });

      try {
        const { present } = await withTimeout(getSessionPresence(this.sessionId), 5000, 'Presence fetch timed out');
        this.updatePresence(present);
      } catch {
        // Presence is best-effort; the socket will keep it updated.
      }

      this.heartbeatInterval = window.setInterval(() => {
        this.socket?.emit('heartbeat', { session_id: this.sessionId });
      }, 30000);
    } catch (err: any) {
      releaseSafety();
      // eslint-disable-next-line no-console
      console.error('Failed to initialize game:', err);
      this.loadingOverlay.innerHTML = '<span>Failed to enter the realm.</span><button>Return</button>';
      const btn = this.loadingOverlay.querySelector('button');
      if (btn) btn.onclick = () => this.onExit();
      throw err;
    }
    releaseSafety();
    this.loadingOverlay.remove();
  }

  private buildUI() {
    const hud = el('div', { className: 'game-hud' });
    hud.appendChild(el('h1', {}, 'Sanctuary'));
    this.statusEl = el('div', { className: 'game-status' }, 'Turn 1 · Your Move');
    hud.appendChild(this.statusEl);
    this.timerEl = el('div', { className: 'game-timer' });
    hud.appendChild(this.timerEl);

    const actions = el('div', { className: 'game-actions' });
    this.moveBtn = el('button', { onclick: () => { this.ensureAudioStarted(); this.setAction('move'); } }, 'Move [M]') as HTMLButtonElement;
    this.attackBtn = el('button', { onclick: () => { this.ensureAudioStarted(); this.setAction('attack'); } }, 'Attack [F]') as HTMLButtonElement;
    this.rangedBtn = el('button', { onclick: () => { this.ensureAudioStarted(); this.setAction('ranged'); } }, 'Ranged [R]') as HTMLButtonElement;
    this.potionBtn = el('button', { onclick: () => { this.ensureAudioStarted(); this.usePotion(); } }, 'Potion [P]') as HTMLButtonElement;
    this.abilityBtn = el('button', { onclick: () => { this.ensureAudioStarted(); this.setAction('ability'); } }, 'Ability [Q]') as HTMLButtonElement;
    this.stabilizeBtn = el('button', { onclick: () => { this.ensureAudioStarted(); this.stabilize(); } }, 'Stabilize [S]') as HTMLButtonElement;
    this.restBtn = el('button', { onclick: () => { this.ensureAudioStarted(); this.rest(); } }, 'Rest') as HTMLButtonElement;
    this.endBtn = el('button', { onclick: () => { this.ensureAudioStarted(); this.endTurn(); } }, 'End [E]') as HTMLButtonElement;
    actions.appendChild(this.moveBtn);
    actions.appendChild(this.attackBtn);
    actions.appendChild(this.rangedBtn);
    actions.appendChild(this.potionBtn);
    actions.appendChild(this.abilityBtn);
    actions.appendChild(this.stabilizeBtn);
    actions.appendChild(this.restBtn);
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

    const muteBtn = el('button', {
      className: 'mute-btn',
      onclick: () => {
        this.ensureAudioStarted();
        const muted = this.audio.toggleMute();
        muteBtn.textContent = muted ? 'Unmute' : 'Mute';
        muteBtn.classList.toggle('muted', muted);
      },
    }, 'Mute') as HTMLButtonElement;
    hud.appendChild(muteBtn);

    const ambientBtn = el('button', {
      className: 'ambient-btn',
      onclick: () => {
        this.ensureAudioStarted();
        if (this.audio.isAmbientActive()) {
          this.audio.stopAmbient();
          ambientBtn.textContent = 'Ambient: Off';
        } else {
          this.audio.playAmbient(this.moduleId === 'sunken_crypt' ? 'cave' : 'dungeon');
          ambientBtn.textContent = 'Ambient: On';
        }
      },
    }, 'Ambient: Off') as HTMLButtonElement;
    hud.appendChild(ambientBtn);

    const volumeWrap = el('div', { className: 'volume-control' });
    volumeWrap.appendChild(el('label', { htmlFor: 'music-volume' }, 'Music'));
    const volumeSlider = el('input', {
      id: 'music-volume',
      type: 'range',
      min: '0',
      max: '1',
      step: '0.05',
      value: String(this.audio.getMusicVolume()),
      oninput: (e: Event) => {
        const val = parseFloat((e.target as HTMLInputElement).value);
        this.audio.setMusicVolume(val);
      },
    }) as HTMLInputElement;
    volumeWrap.appendChild(volumeSlider);
    hud.appendChild(volumeWrap);

    const saveBtn = el('button', {
      className: 'save-btn',
      onclick: () => this.saveProgression(),
    }, 'Save Progress') as HTMLButtonElement;
    this.saveBtn = saveBtn;
    hud.appendChild(saveBtn);

    const journalBtn = el('button', {
      className: 'journal-btn',
      onclick: () => this.toggleJournal(),
    }, 'Journal') as HTMLButtonElement;
    hud.appendChild(journalBtn);

    this.dmToolsEl = this.buildDmTools();
    this.dmToolsEl.style.display = 'none';
    hud.appendChild(this.dmToolsEl);

    const exitBtn = el('button', { className: 'danger', onclick: () => this.leaveSession() }, 'Leave');
    hud.appendChild(exitBtn);

    return hud;
  }

  private ensureAudioStarted() {
    this.audio.ensureStartedFromGesture().catch(() => {});
  }

  private buildChatPanel(): HTMLElement {
    const panel = el('div', { className: 'chat-panel' });
    const header = el('div', {
      className: 'chat-header',
      onclick: () => this.toggleChat(),
    }, 'Party Chat');
    panel.appendChild(header);

    this.chatMessages = el('div', { className: 'chat-messages' });
    panel.appendChild(this.chatMessages);

    const controls = el('div', { className: 'chat-controls' });
    this.chatInput = el('input', {
      type: 'text',
      placeholder: 'Say something...',
      maxlength: 500,
      onkeydown: (e: KeyboardEvent) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          this.sendChat();
        }
      },
    }) as HTMLInputElement;
    const sendBtn = el('button', {
      onclick: () => this.sendChat(),
    }, 'Send') as HTMLButtonElement;
    controls.appendChild(this.chatInput);
    controls.appendChild(sendBtn);
    panel.appendChild(controls);

    panel.style.display = 'none';
    return panel;
  }

  private buildPresencePanel(): HTMLElement {
    const panel = el('div', { className: 'presence-panel' });
    panel.appendChild(el('h3', {}, 'Online'));
    this.presenceList = el('div', { className: 'presence-list' });
    panel.appendChild(this.presenceList);
    panel.style.display = 'none';
    return panel;
  }

  private buildJournalPanel(): HTMLElement {
    const panel = el('div', { className: 'journal-overlay' });
    const card = el('div', { className: 'journal-card' });
    const header = el('div', { className: 'journal-header' });
    header.appendChild(el('h2', {}, 'Adventure Journal'));
    const close = el('button', { className: 'journal-close', onclick: () => this.toggleJournal() }, '×');
    header.appendChild(close);
    card.appendChild(header);

    const body = el('div', { className: 'journal-body' });
    const moduleName = el('h3', { className: 'journal-module' }, this.moduleId);
    body.appendChild(moduleName);

    const bestiary = el('div', { className: 'journal-bestiary' });
    bestiary.appendChild(el('h4', {}, 'Bestiary'));
    const bestiaryList = el('div', { className: 'journal-bestiary-list' });
    bestiary.appendChild(bestiaryList);
    body.appendChild(bestiary);

    const chronicle = el('div', { className: 'journal-chronicle' });
    chronicle.appendChild(el('h4', {}, 'Chronicle'));
    const chronicleList = el('div', { className: 'journal-chronicle-list' });
    chronicle.appendChild(chronicleList);
    body.appendChild(chronicle);

    card.appendChild(body);
    panel.appendChild(card);
    panel.style.display = 'none';
    return panel;
  }

  private toggleJournal() {
    if (!this.journalPanel) {
      this.journalPanel = this.buildJournalPanel();
      this.root.appendChild(this.journalPanel);
    }
    this.journalOpen = !this.journalOpen;
    this.journalPanel.style.display = this.journalOpen ? 'flex' : 'none';
    if (this.journalOpen) this.updateJournal();
  }

  private updateJournal() {
    if (!this.journalPanel || !this.session) return;
    const moduleName = this.journalPanel.querySelector('.journal-module') as HTMLElement | null;
    if (moduleName) moduleName.textContent = this.moduleId;

    const bestiaryList = this.journalPanel.querySelector('.journal-bestiary-list') as HTMLElement | null;
    if (bestiaryList) {
      clear(bestiaryList);
      const seen = new Set<string>();
      [...this.session.monsters, ...(this.session.players || [])].forEach((t) => {
        const key = t.type === 'monster' ? t.monster || t.name : t.name;
        if (!key || seen.has(key)) return;
        seen.add(key);
        const row = el('div', { className: 'journal-bestiary-row' });
        row.appendChild(el('span', { className: 'journal-bestiary-name' }, key));
        row.appendChild(el('span', { className: 'journal-bestiary-hp' }, `HP ${t.hp}/${t.max_hp}`));
        row.appendChild(el('span', { className: 'journal-bestiary-ac' }, `AC ${t.ac}`));
        bestiaryList.appendChild(row);
      });
      if (bestiaryList.childElementCount === 0) {
        bestiaryList.appendChild(el('div', { className: 'journal-empty' }, 'No creatures encountered yet.'));
      }
    }

    const chronicleList = this.journalPanel.querySelector('.journal-chronicle-list') as HTMLElement | null;
    if (chronicleList) {
      clear(chronicleList);
      const log = this.session.log.slice(-30);
      if (log.length === 0) {
        chronicleList.appendChild(el('div', { className: 'journal-empty' }, 'No events recorded yet.'));
      } else {
        log.forEach((entry) => {
          const row = el('div', { className: 'journal-chronicle-row' }, entry);
          chronicleList.appendChild(row);
        });
      }
    }
  }

  private updatePresence(present: Presence[]) {
    if (!this.presencePanel) return;
    clear(this.presenceList);
    if (present.length === 0) {
      this.presencePanel.style.display = 'none';
      return;
    }
    this.presencePanel.style.display = 'block';
    present.forEach((p) => {
      const name = p.name || `Account ${p.account_id ?? '?'}`;
      this.presenceList.appendChild(el('div', { className: 'presence-row' }, name));
    });
  }

  private toggleChat() {
    this.chatCollapsed = !this.chatCollapsed;
    this.chatPanel?.classList.toggle('collapsed', this.chatCollapsed);
  }

  private sendChat() {
    if (!this.socket) return;
    const text = this.chatInput.value.trim();
    if (!text) return;
    this.socket.emit('chat_message', {
      session_id: this.sessionId,
      text,
      name: document.body.dataset.user || 'Player',
    });
    this.chatInput.value = '';
  }

  private appendChatMessage(payload: { account_id?: number; name?: string; text?: string; timestamp?: string }) {
    if (!payload.text) return;
    const name = payload.name || 'Player';
    const time = payload.timestamp
      ? new Date(payload.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      : '';
    const row = el('div', { className: 'chat-message' });
    const timeSpan = el('span', { className: 'chat-time' }, time);
    const nameSpan = el('span', { className: 'chat-name' }, name);
    const textSpan = el('span', { className: 'chat-text' }, payload.text);
    row.appendChild(timeSpan);
    row.appendChild(nameSpan);
    row.appendChild(textSpan);
    this.chatMessages.appendChild(row);
    this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
  }

  private showTooltip(token: Token, clientX: number, clientY: number) {
    const subtitle = token.type === 'player'
      ? (token.classes || ['Adventurer']).join(' / ')
      : token.name;
    const statusText = (token.statuses || [])
      .map((s) => `${s.type}${s.duration ? ` (${s.duration})` : ''}`)
      .join(', ');
    const downText = token.down ? '<div class="token-tooltip-down">DOWNED</div>' : '';
    this.tooltip.innerHTML = `
      <strong>${token.name}</strong>
      <div class="token-tooltip-sub">${subtitle}</div>
      <div>HP ${token.hp}/${token.max_hp}</div>
      <div>AC ${token.ac}</div>
      ${downText}
      ${statusText ? `<div>Status: ${statusText}</div>` : ''}
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
    if (won) {
      const living = this.session.players.filter((p) => p.alive !== false);
      const totalXp = living.reduce((sum, p) => sum + (p.xp ?? 0), 0);
      const totalGold = living.reduce((sum, p) => sum + (p.gold ?? 0), 0);
      panel.appendChild(el('p', { className: 'message' }, `The lair is quiet. Party gains ${totalXp} XP and ${totalGold} gold.`));
    } else {
      panel.appendChild(el('p', { className: 'message' }, 'Your light fades in the dark. The dungeon claims another.'));
    }
    const isCampaign = this.isCampaignSession();
    if (isCampaign && won) {
      const journey = el('button', { className: 'enter', onclick: () => this.journeyOn() }, 'Journey On');
      panel.appendChild(journey);
    } else if (this.onReplay && this.session.character_id) {
      const replay = el('button', { className: 'enter', onclick: () => this.onReplay!(this.session!.character_id!) }, 'Play Again');
      panel.appendChild(replay);
    }
    const leave = el('button', { onclick: () => this.onExit() }, 'Return to Sanctuary');
    panel.appendChild(leave);
    overlay.appendChild(panel);
    this.root.appendChild(overlay);
  }

  private setAction(action: 'move' | 'attack' | 'ranged' | 'ability') {
    this.action = this.action === action ? null : action;
    this.updateStatus();
    this.highlightActionTiles();
  }

  private setDmAction(action: 'spawn' | 'move' | 'reveal' | null) {
    this.dmAction = this.dmAction === action ? null : action;
    this.updateStatus();
  }

  private buildDmTools(): HTMLElement {
    const panel = el('div', { className: 'dm-tools' });
    panel.appendChild(el('h3', {}, 'DM Tools'));

    const spawnWrap = el('div', { className: 'dm-tool-row' });
    this.dmMonsterSelect = el('select', {}) as HTMLSelectElement;
    ['goblin', 'orc', 'skeleton', 'zombie', 'ghoul', 'shadow_imp', 'librarian', 'animated_book'].forEach((m) => {
      const opt = document.createElement('option');
      opt.value = m;
      opt.textContent = m;
      this.dmMonsterSelect.appendChild(opt);
    });
    spawnWrap.appendChild(this.dmMonsterSelect);
    spawnWrap.appendChild(el('button', { onclick: () => this.setDmAction('spawn') }, 'Spawn'));
    panel.appendChild(spawnWrap);

    const moveWrap = el('div', { className: 'dm-tool-row' });
    this.dmTokenSelect = el('select', {}) as HTMLSelectElement;
    moveWrap.appendChild(this.dmTokenSelect);
    moveWrap.appendChild(el('button', { onclick: () => this.setDmAction('move') }, 'Move'));
    panel.appendChild(moveWrap);

    panel.appendChild(
      el('button', { onclick: () => this.setDmAction('reveal') }, 'Reveal Fog')
    );

    return panel;
  }

  private updateDmTools() {
    const isDm = this.isDm();
    this.dmToolsEl.style.display = isDm && this.session?.status === 'active' ? 'block' : 'none';
    if (!isDm || !this.session) return;

    const currentToken = this.dmTokenSelect.value;
    clear(this.dmTokenSelect);
    this.session.monsters.filter((m) => m.alive !== false).forEach((m) => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = `${m.name} (${m.id})`;
      this.dmTokenSelect.appendChild(opt);
    });
    if (currentToken) this.dmTokenSelect.value = currentToken;
  }

  private onKeyDown(e: KeyboardEvent) {
    this.ensureAudioStarted();
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
      case 'r':
        this.setAction('ranged');
        break;
      case 'p':
        e.preventDefault();
        this.usePotion();
        break;
      case 'q':
        this.setAction('ability');
        break;
      case 's':
        e.preventDefault();
        this.stabilize();
        break;
      case 'e':
      case ' ':
        e.preventDefault();
        this.endTurn();
        break;
      case 'arrowup':
        e.preventDefault();
        this.tryMove(0, -1);
        break;
      case 'arrowdown':
        e.preventDefault();
        this.tryMove(0, 1);
        break;
      case 'arrowleft':
        e.preventDefault();
        this.tryMove(-1, 0);
        break;
      case 'arrowright':
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

  private async usePotion() {
    if (!this.session || this.session.phase !== 'player' || !this.isPlayer()) return;
    try {
      const { session } = await actInSession(this.sessionId, 'use_potion');
      this.update(session);
      if (session.phase === 'dm' && !this.isCampaignSession()) {
        setTimeout(() => this.runDmTurn(), 600);
      }
    } catch (err: any) {
      this.log(err.message || 'Potion failed.');
    }
  }

  private async stabilize() {
    if (!this.session || this.session.phase !== 'player' || !this.isPlayer()) return;
    const target = this.findAdjacentDownedAlly();
    if (!target) return;
    try {
      const { session } = await actInSession(this.sessionId, 'stabilize', { target_id: target.id });
      this.update(session);
      if (session.phase === 'dm' && !this.isCampaignSession()) {
        setTimeout(() => this.runDmTurn(), 600);
      }
    } catch (err: any) {
      this.log(err.message || 'Stabilize failed.');
    }
  }

  private async rest() {
    if (!this.session || this.session.status !== 'active') return;
    try {
      const { session } = await restInSession(this.sessionId);
      this.update(session);
    } catch (err: any) {
      this.log(err.message || 'Rest failed.');
    }
  }

  private async saveProgression(): Promise<void> {
    if (!this.session) return;
    try {
      this.saveBtn.disabled = true;
      this.saveBtn.textContent = 'Saving...';
      await saveProgress(this.sessionId);
      this.saveBtn.textContent = 'Saved';
      window.setTimeout(() => {
        this.saveBtn.textContent = 'Save Progress';
        this.saveBtn.disabled = false;
      }, 1500);
    } catch (err: any) {
      this.saveBtn.textContent = 'Save Failed';
      this.log(err.message || 'Save progress failed.');
      window.setTimeout(() => {
        this.saveBtn.textContent = 'Save Progress';
        this.saveBtn.disabled = false;
      }, 1500);
    }
  }

  private async leaveSession() {
    if (this.session && this.session.status !== 'won') {
      await this.saveProgression();
    }
    this.onExit();
  }

  private async journeyOn() {
    if (!this.session || this.session.status !== 'won' || !this.isCampaignSession()) return;
    try {
      const { session } = await advanceSession(this.sessionId);
      const { module } = await getModule(session.module_id);
      this.module = module.map;
      this.visited.clear();
      this.renderMap();
      this.update(session);
      const overlay = this.root.querySelector('.game-over-overlay');
      overlay?.remove();
    } catch (err: any) {
      this.log(err.message || 'Journey on failed.');
    }
  }

  private findAdjacentDownedAlly(): Token | null {
    if (!this.session) return null;
    const player = this.session.player;
    for (const p of this.session.players) {
      if (p.id === player.id || !p.down) continue;
      const dist = Math.abs(player.x - p.x) + Math.abs(player.y - p.y);
      if (dist === 1) return p;
    }
    return null;
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
    const theme = getTheme(this.module.theme);
    for (let y = 0; y < this.module.height; y++) {
      const row = this.module.tiles[y] || '';
      const tileRow: Container[] = [];
      for (let x = 0; x < this.module.width; x++) {
        const tile = row[x] || '0';
        const c = new Container();
        this.drawTile(c, tile, x, y, theme);
        c.x = x * TILE_SIZE;
        c.y = y * TILE_SIZE;
        c.eventMode = 'static';
        c.on('pointerdown', () => this.onTileClick(x, y));
        this.mapContainer.addChild(c);
        tileRow.push(c);
      }
      this.tileSprites.push(tileRow);
    }
    this.centerMap();
  }

  private drawTile(c: Container, tile: string, x: number, y: number, theme: import('../lib/tile-atlas').TileTheme | null) {
    const tex = theme ? tileFrame(theme, tile) : null;
    if (tex) {
      const s = new Sprite(tex);
      s.width = TILE_SIZE;
      s.height = TILE_SIZE;
      c.addChild(s);
      // Slight shading to keep lighting effects readable
      const overlay = new Graphics();
      overlay.rect(0, 0, TILE_SIZE, TILE_SIZE);
      overlay.fill({ color: 0x000000, alpha: 0.12 });
      c.addChild(overlay);
    } else if (tile === '1') {
      const g = new Graphics();
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
      c.addChild(g);
    } else {
      const g = new Graphics();
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
      if (tile === '2') {
        // Trap tile: faint red speckle / spike hint
        g.rect(TILE_SIZE * 0.25, TILE_SIZE * 0.25, 3, 3);
        g.fill({ color: TRAP_HIGHLIGHT, alpha: 0.35 });
        g.rect(TILE_SIZE * 0.65, TILE_SIZE * 0.55, 3, 3);
        g.fill({ color: TRAP_HIGHLIGHT, alpha: 0.3 });
        g.rect(TILE_SIZE * 0.45, TILE_SIZE * 0.65, 2, 2);
        g.fill({ color: TRAP_COLOR, alpha: 0.4 });
      }
      c.addChild(g);
    }
  }

  private hasLineOfSight(x0: number, y0: number, x1: number, y1: number): boolean {
    let dx = Math.abs(x1 - x0);
    let dy = Math.abs(y1 - y0);
    const sx = x0 < x1 ? 1 : -1;
    const sy = y0 < y1 ? 1 : -1;
    let err = dx - dy;
    let x = x0;
    let y = y0;
    while (x !== x1 || y !== y1) {
      const e2 = 2 * err;
      if (e2 > -dy) {
        err -= dy;
        x += sx;
      }
      if (e2 < dx) {
        err += dx;
        y += sy;
      }
      if (x !== x0 || y !== y0) {
        const row = this.module.tiles[y] || '';
        if (row[x] === '1') return false;
      }
    }
    return true;
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
        let highlight: number | null = null;
        if (this.action === 'move' && tile !== '1') {
          const dist = Math.abs(x - player.x) + Math.abs(y - player.y);
          if (dist === 1) highlight = FLOOR_HIGHLIGHT;
        }
        if (this.action === 'ranged' && tile !== '1') {
          const dist = Math.abs(x - player.x) + Math.abs(y - player.y);
          if (dist > 0 && dist <= RANGED_RANGE && this.hasLineOfSight(player.x, player.y, x, y)) {
            highlight = FLOOR_RANGE_HIGHLIGHT;
          }
        }
        if (this.action === 'ability' && tile !== '1') {
          const dist = Math.abs(x - player.x) + Math.abs(y - player.y);
          const cls = (player.classes?.[0] ?? '').toLowerCase();
          const abilityRange = cls === 'magic-user' || cls === 'illusionist' ? 6 : cls === 'cleric' ? 4 : 1;
          if (dist > 0 && dist <= abilityRange && this.hasLineOfSight(player.x, player.y, x, y)) {
            highlight = FLOOR_RANGE_HIGHLIGHT;
          }
        }
        g.tint = highlight ?? 0xffffff;
      }
    }
  }

  private updateLighting() {
    if (!this.session || !this.app || this.tileSprites.length === 0) return;
    const px = this.session.player.x;
    const py = this.session.player.y;
    for (let y = 0; y < this.module.height; y++) {
      const row = this.module.tiles[y] || '';
      for (let x = 0; x < this.module.width; x++) {
        const tile = row[x] || '0';
        const dist = Math.sqrt((x - px) ** 2 + (y - py) ** 2);
        const inRadius = dist <= VISION_RADIUS + 1;
        const hasLos = inRadius && this.hasLineOfSight(px, py, x, y);
        const key = `${x},${y}`;
        let alpha: number;
        if (hasLos) {
          this.visited.add(key);
          if (dist <= VISION_RADIUS - 1) {
            alpha = 1;
          } else {
            const t = (dist - (VISION_RADIUS - 1)) / 2;
            const isWall = tile === '1';
            alpha = 1 - t * (1 - (isWall ? 0.22 : 0.1));
          }
        } else if (this.visited.has(key)) {
          alpha = 0.35;
        } else {
          alpha = 0;
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
      sprite.setDown(t.down ?? false);
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

  private ambientEffectConfig() {
    const theme = this.module.theme || 'dungeon';
    switch (theme) {
      case 'ice':
        return {
          count: 4,
          color: 0xd6eaf8,
          size: 1.1,
          alpha: 0.7,
          vx: () => (Math.random() - 0.5) * 0.2,
          vy: () => 0.4 + Math.random() * 0.4,
          life: 100 + Math.random() * 80,
        };
      case 'lava':
        return {
          count: 4,
          color: Math.random() < 0.5 ? 0xff5500 : 0xffaa00,
          size: 1.3,
          alpha: 0.85,
          vx: () => (Math.random() - 0.5) * 0.4,
          vy: () => -0.5 - Math.random() * 0.5,
          life: 70 + Math.random() * 60,
        };
      case 'forest':
        return {
          count: 2,
          color: 0xa9dfbf,
          size: 0.9,
          alpha: 0.4,
          vx: () => 0.2 + Math.random() * 0.3,
          vy: () => 0.6 + Math.random() * 0.4,
          life: 90 + Math.random() * 70,
        };
      case 'library':
        return {
          count: 2,
          color: 0xf7dc6f,
          size: 0.8,
          alpha: 0.5,
          vx: () => (Math.random() - 0.5) * 0.15,
          vy: () => -0.2 - Math.random() * 0.2,
          life: 140 + Math.random() * 100,
        };
      default:
        return {
          count: 3,
          color: Math.random() < 0.25 ? 0xffaa44 : 0x9a9590,
          size: Math.random() < 0.25 ? 1.2 : 0.8,
          alpha: Math.random() < 0.25 ? 0.9 : 0.45,
          vx: () => (Math.random() - 0.5) * 0.3,
          vy: () => (Math.random() < 0.25 ? -0.3 - Math.random() * 0.4 : (Math.random() - 0.5) * 0.2),
          life: 120 + Math.random() * 120,
        };
    }
  }

  private spawnAmbientParticles() {
    if (!this.session || !this.app) return;
    const px = this.session.player.x * TILE_SIZE + TILE_SIZE / 2;
    const py = this.session.player.y * TILE_SIZE + TILE_SIZE / 2;
    const radius = VISION_RADIUS * TILE_SIZE;
    const cfg = this.ambientEffectConfig();
    for (let i = 0; i < cfg.count; i++) {
      const angle = Math.random() * Math.PI * 2;
      const dist = Math.random() * radius;
      const x = px + Math.cos(angle) * dist;
      const y = py + Math.sin(angle) * dist;
      const g = new Graphics();
      g.circle(0, 0, cfg.size);
      g.fill({ color: cfg.color, alpha: cfg.alpha });
      g.x = x;
      g.y = y;
      this.fxContainer.addChild(g);
      this.particles.push({
        gfx: g,
        vx: cfg.vx(),
        vy: cfg.vy(),
        life: cfg.life,
        maxLife: cfg.life,
      });
    }
  }

  private onTick(ticker: import('pixi.js').Ticker) {
    const dt = ticker.deltaTime;
    const dtSec = dt / 60;
    const speed = 12;

    // Ambient dust / torch sparks
    if (this.session && this.session.status === 'active' && Math.random() < 0.08) {
      this.spawnAmbientParticles();
    }
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
      // Ambient motes keep drifting; combat particles decay quickly.
      if (Math.abs(p.vx) > 1 || Math.abs(p.vy) > 1) {
        p.vx *= 0.95;
        p.vy *= 0.95;
      }
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
    if (!this.session || this.session.status !== 'active') return;

    if (this.dmAction && this.isDm()) {
      try {
        let response: { session: GameSession } | undefined;
        if (this.dmAction === 'spawn') {
          const name = this.dmMonsterSelect.value || 'goblin';
          response = await dmSpawn(this.sessionId, { name, x, y });
        } else if (this.dmAction === 'move') {
          const tokenId = this.dmTokenSelect.value;
          if (!tokenId) return;
          response = await dmMove(this.sessionId, { token_id: tokenId, x, y });
        } else if (this.dmAction === 'reveal') {
          response = await dmReveal(this.sessionId, { x, y, radius: 4 });
        }
        if (response) {
          this.dmAction = null;
          this.update(response.session);
        }
      } catch (err: any) {
        this.log(err.message || 'DM action failed.');
      }
      return;
    }

    if (this.session.phase !== 'player' || this.action !== 'move') return;
    try {
      const { session } = await actInSession(this.sessionId, 'move', { x, y });
      this.action = null;
      this.update(session);
    } catch (err: any) {
      this.log(err.message || 'Move failed.');
    }
  }

  private async onTokenClick(token: Token) {
    if (!this.session || this.session.phase !== 'player') return;
    if (this.action === 'attack') {
      if (token.type !== 'monster') return;
      const player = this.session.player;
      const isAdjacent = Math.abs(player.x - token.x) + Math.abs(player.y - token.y) === 1;
      this.audio.swordHit();
      this.audio.combatSting();
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
    } else if (this.action === 'ranged') {
      if (token.type !== 'monster') return;
      const player = this.session.player;
      this.audio.rangedShot();
      this.audio.combatSting();
      try {
        const { session } = await actInSession(this.sessionId, 'ranged', { target_id: token.id });
        this.action = null;
        this.spawnSlashEffect(player.x, player.y, token.x, token.y);
        this.update(session);
        if (session.phase === 'dm') {
          setTimeout(() => this.runDmTurn(), 600);
        }
      } catch (err: any) {
        this.log(err.message || 'Ranged attack failed.');
      }
    } else if (this.action === 'ability') {
      if (token.type !== 'monster') return;
      const player = this.session.player;
      const cls = (player.classes?.[0] ?? '').toLowerCase();
      const rangedAbility = cls === 'magic-user' || cls === 'illusionist' || cls === 'cleric';
      if (rangedAbility) {
        this.audio.rangedShot();
      } else {
        this.audio.swordHit();
      }
      this.audio.combatSting();
      try {
        const { session } = await actInSession(this.sessionId, 'ability', { target_id: token.id });
        this.action = null;
        this.spawnSlashEffect(player.x, player.y, token.x, token.y);
        this.update(session);
        if (session.phase === 'dm') {
          setTimeout(() => this.runDmTurn(), 600);
        }
      } catch (err: any) {
        this.log(err.message || 'Ability failed.');
      }
    }
  }

  private update(session: GameSession) {
    const prevSession = this.session;
    const wasDm = prevSession?.phase === 'dm';
    const playerHurt = prevSession ? session.player.hp < prevSession.player.hp : false;
    const prevStatus = prevSession?.status;
    const prevPlayerPos = prevSession ? `${prevSession.player.x},${prevSession.player.y}` : '';

    this.session = session;

    // Merge DM-revealed fog into the local visited set.
    session.dm_revealed?.forEach((key) => this.visited.add(key));

    // Music state transitions.
    if (!prevSession) {
      if (session.mode === 'arena') {
        this.audio.combatSting();
      } else {
        this.audio.exploration();
      }
    }
    if (this.chatPanel) {
      this.chatPanel.style.display = this.isCampaignSession() ? 'flex' : 'none';
    }
    this.updateDmTools();
    this.updateJournal();
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

    if (prevStatus === 'active' && session.status === 'won') {
      this.audio.victory();
    } else if (prevStatus === 'active' && session.status === 'lost') {
      this.audio.defeat();
    }
    if (prevPlayerPos && prevPlayerPos !== `${session.player.x},${session.player.y}`) {
      this.audio.footstep();
    }

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
      <div class="progression-text">Level ${p.level ?? 1} · XP ${p.xp ?? 0} · Gold ${p.gold ?? 0}</div>
    `;
    this.root.classList.toggle('low-hp', ratio <= 0.25 && p.hp > 0);
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
      const portraitUrl = this.fallbackPortraitUrl((p.classes?.[0] ?? ''));
      const portrait = el('img', {
        className: 'party-portrait',
        src: portraitUrl,
        alt: p.name,
        onerror: () => { portrait.src = this.fallbackPortraitUrl(); },
      }) as HTMLImageElement;
      row.appendChild(portrait);
      row.appendChild(el('span', { className: 'party-name' }, p.name));
      const barWrap = el('div', { className: 'party-hp-bar' });
      barWrap.innerHTML = `<span style="width:${Math.round(ratio * 100)}%; background:${hpColor};"></span>`;
      row.appendChild(barWrap);
      row.appendChild(el('span', { className: 'party-hp-text' }, `${p.hp}/${p.max_hp}`));
      const statusText = (p.statuses || [])
        .map((s) => `${s.type}${s.duration ? ` ${s.duration}t` : ''}`)
        .join(', ');
      if (statusText || p.down) {
        const statusEl = el('span', { className: 'party-status' });
        statusEl.textContent = [p.down ? 'DOWN' : '', statusText].filter(Boolean).join(' · ');
        row.appendChild(statusEl);
      }
      row.appendChild(el('span', { className: 'party-progression' }, `Lv${p.level ?? 1} · XP ${p.xp ?? 0} · G ${p.gold ?? 0}`));
      this.partyEl.appendChild(row);
    });
  }

  private fallbackPortraitUrl(className?: string): string {
    const key = (className || 'generic').toLowerCase().replace(/\s+/g, '-');
    return `/portraits/${key}.png`;
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
    const player = this.session?.player;
    const isActiveUser =
      !!this.session &&
      this.session.status === 'active' &&
      this.session.phase === 'player' &&
      ((player && 'account_id' in player && player.account_id != null && player.account_id === this.userId) ||
        (!this.session.campaign_id || this.session.account_id === this.userId));
    const canAct = isActiveUser && !player?.down;
    const hasPotion = !!player && (player.inventory || []).some((i) => i.slot === 'consumable' || i.type === 'potion');
    const isSessionPlayer =
      !!this.session &&
      this.session.status === 'active' &&
      (this.session.players.some((p) => p.account_id === this.userId) ||
        (!this.session.campaign_id && this.session.account_id === this.userId));
    this.moveBtn.disabled = !canAct;
    this.attackBtn.disabled = !canAct;
    this.rangedBtn.disabled = !canAct;
    this.potionBtn.disabled = !canAct || !hasPotion;
    this.abilityBtn.disabled = !canAct;
    this.endBtn.disabled = !isActiveUser;
    const canStabilize = canAct && !!this.findAdjacentDownedAlly();
    this.stabilizeBtn.style.display = canStabilize ? 'inline-block' : 'none';
    this.restBtn.disabled = !isSessionPlayer;
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
    const dmActionText = this.dmAction ? ` · DM: ${this.dmAction}` : '';
    this.statusEl.textContent = `Turn ${this.session.turn} · ${phaseText}${actionText}${dmActionText}`;

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
      if (newEntries.some((e) => e.toLowerCase().includes('trap') || e.toLowerCase().includes('spike'))) {
        this.audio.trapTrigger();
        this.shakeFrames = 20;
        this.triggerDamageFlash();
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
    if (this.heartbeatInterval) {
      window.clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
    if (this.keydownHandler) {
      window.removeEventListener('keydown', this.keydownHandler);
      this.keydownHandler = null;
    }
    if (this.beforeUnloadHandler) {
      window.removeEventListener('beforeunload', this.beforeUnloadHandler);
      this.beforeUnloadHandler = null;
    }
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    this.app?.destroy(true, { children: true });
    clear(this.root);
  }
}

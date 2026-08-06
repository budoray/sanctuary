import { getAccountProgress, listCampaigns, listModules, listSessions, ModuleInfo } from '../net/api';
import { el, clear } from './utils';

const THEME_LABELS: Record<string, string> = {
  dungeon: 'Dungeon',
  cave: 'Cave',
  library: 'Library',
  ice: 'Frozen',
  lava: 'Volcanic',
  forest: 'Forest',
  tomb: 'Tomb',
  sewer: 'Sewer',
};

export class Hub {
  private root: HTMLElement;
  private onSolo: () => void;
  private onJoin: () => void;
  private onCampaigns: () => void;
  private onResume: () => void;
  private container: HTMLElement;
  private modules: ModuleInfo[] = [];
  private progressEl: HTMLElement;

  constructor(
    container: HTMLElement,
    onSolo: () => void,
    onJoin: () => void,
    onCampaigns: () => void,
    onResume: () => void
  ) {
    this.root = el('div', { className: 'sanctuary-hub' });
    this.onSolo = onSolo;
    this.onJoin = onJoin;
    this.onCampaigns = onCampaigns;
    this.onResume = onResume;

    const background = el('div', { className: 'hub-background' });
    const vignette = el('div', { className: 'hub-vignette' });
    const particles = el('div', { className: 'hub-particles' });
    for (let i = 0; i < 32; i++) {
      const p = el('span', { className: 'hub-particle' });
      p.style.left = `${Math.random() * 100}%`;
      p.style.top = `${Math.random() * 100}%`;
      p.style.animationDelay = `${Math.random() * 6}s`;
      p.style.animationDuration = `${4 + Math.random() * 4}s`;
      particles.appendChild(p);
    }

    this.container = el('div', { className: 'hub-container' });
    this.progressEl = el('div', { className: 'hub-progress' });
    this.container.appendChild(this.progressEl);
    this.renderHeader();
    this.renderActions();
    this.renderRealm();

    this.root.appendChild(background);
    this.root.appendChild(vignette);
    this.root.appendChild(particles);
    this.root.appendChild(this.container);
    container.appendChild(this.root);

    this.loadData();
  }

  private renderHeader() {
    const header = el('header', { className: 'hub-header' });
    const badge = el('span', { className: 'hub-badge' }, 'Tenshin Arts');
    const title = el('h1', {}, 'Sanctuary');
    const subtitle = el('p', {}, 'Choose your path into the dark.');
    header.appendChild(badge);
    header.appendChild(title);
    header.appendChild(subtitle);
    this.container.appendChild(header);
  }

  private renderActions() {
    const grid = el('div', { className: 'hub-actions' });

    const solo = this.buildCard(
      'solo',
      'Solo Adventure',
      'Forge a hero and delve into any realm alone. Your torch, your choices, your fate.',
      'Begin Solo',
      () => this.onSolo()
    );

    const join = this.buildCard(
      'join',
      'Join Adventure',
      'Resume a saved session or join an active campaign already in progress with friends.',
      'Join / Resume',
      () => this.onJoin()
    );

    const group = this.buildCard(
      'group',
      'Create Group Adventure',
      'Start a campaign, invite friends, and lead or follow as DM with AI assistance.',
      'Create Campaign',
      () => this.onCampaigns()
    );

    grid.appendChild(solo);
    grid.appendChild(join);
    grid.appendChild(group);
    this.container.appendChild(grid);

    this.loadResumeHint();
  }

  private buildCard(kind: string, title: string, desc: string, action: string, onClick: () => void): HTMLElement {
    const card = el('div', { className: `hub-card hub-card-${kind}` });
    const icon = el('div', { className: 'hub-card-icon' });
    const body = el('div', { className: 'hub-card-body' });
    const h2 = el('h2', {}, title);
    const p = el('p', {}, desc);
    const btn = el('button', { onclick: onClick }, action);
    body.appendChild(h2);
    body.appendChild(p);
    body.appendChild(btn);
    card.appendChild(icon);
    card.appendChild(body);
    return card;
  }

  private async loadResumeHint() {
    try {
      const [{ sessions }, { campaigns }] = await Promise.all([listSessions(), listCampaigns()]);
      const activeSessions = sessions.filter((s) => s.status === 'active');
      if (activeSessions.length === 0 && campaigns.length === 0) return;

      const hint = el('div', { className: 'hub-resume-hint' });
      const parts: string[] = [];
      if (activeSessions.length > 0) parts.push(`${activeSessions.length} active adventure${activeSessions.length > 1 ? 's' : ''}`);
      if (campaigns.length > 0) parts.push(`${campaigns.length} campaign${campaigns.length > 1 ? 's' : ''}`);
      hint.textContent = `You have ${parts.join(' and ')} waiting. `;
      const link = el('button', { className: 'hub-resume-link', onclick: () => this.onResume() }, 'Resume now');
      hint.appendChild(link);
      this.container.appendChild(hint);
    } catch {
      // Best-effort hint.
    }
  }

  private async loadData() {
    try {
      const [{ modules }, progress] = await Promise.all([
        listModules(),
        getAccountProgress().catch(() => null),
      ]);
      this.modules = modules;
      this.renderProgress(progress);
      this.renderRealm();
    } catch {
      // Realm preview is best-effort.
    }
  }

  private renderProgress(progress: { wins?: number; losses?: number; boss_kills?: number; modules_cleared?: number; deaths?: number; level_ups?: number; sessions?: number } | null) {
    clear(this.progressEl);
    if (!progress) {
      this.progressEl.style.display = 'none';
      return;
    }
    this.progressEl.style.display = 'flex';
    const stats = [
      ['Wins', progress.wins ?? 0],
      ['Losses', progress.losses ?? 0],
      ['Boss Kills', progress.boss_kills ?? 0],
      ['Cleared', progress.modules_cleared ?? 0],
      ['Deaths', progress.deaths ?? 0],
      ['Level Ups', progress.level_ups ?? 0],
    ];
    stats.forEach(([label, value]) => {
      this.progressEl.appendChild(el('span', {}, `${label} ${value}`));
    });
  }

  private renderRealm() {
    const existing = this.container.querySelector('.hub-realm');
    if (existing) existing.remove();

    const realm = el('div', { className: 'hub-realm' });
    const header = el('div', { className: 'hub-realm-header' });
    header.appendChild(el('h3', {}, 'Realms'));
    header.appendChild(el('span', { className: 'hub-realm-count' }, `${this.modules.length} available`));
    realm.appendChild(header);

    if (this.modules.length === 0) {
      realm.appendChild(el('p', { className: 'hub-realm-empty' }, 'Loading realms...'));
    } else {
      const scroll = el('div', { className: 'hub-realm-scroll' });
      this.modules.forEach((m) => {
        const chip = el('div', { className: 'hub-realm-chip' });
        const preview = this.buildMiniMap(m);
        if (preview) chip.appendChild(preview);
        const meta = el('div', { className: 'hub-realm-meta' });
        const theme = m.theme || 'dungeon';
        meta.appendChild(el('span', { className: `hub-realm-theme theme-${theme}` }, THEME_LABELS[theme] || theme));
        meta.appendChild(el('strong', {}, m.name));
        meta.appendChild(el('span', { className: 'hub-realm-size' }, `${m.width}×${m.height}`));
        chip.appendChild(meta);
        scroll.appendChild(chip);
      });
      realm.appendChild(scroll);
    }

    this.container.appendChild(realm);
  }

  private buildMiniMap(m: ModuleInfo): HTMLElement | null {
    if (!m.tiles || m.tiles.length === 0) return null;
    const wrap = el('div', { className: 'hub-realm-map' });
    const maxRows = Math.min(m.height, 12);
    const maxCols = Math.min(m.width, 18);
    wrap.style.gridTemplateRows = `repeat(${maxRows}, 1fr)`;
    wrap.style.gridTemplateColumns = `repeat(${maxCols}, 1fr)`;
    for (let y = 0; y < maxRows; y++) {
      const row = m.tiles[y] || '';
      for (let x = 0; x < maxCols; x++) {
        const tile = row[x] || '0';
        const cell = el('span', { className: `mini-tile mini-tile-${tile === '1' ? 'wall' : tile === '2' ? 'trap' : 'floor'}` });
        wrap.appendChild(cell);
      }
    }
    return wrap;
  }

  destroy() {
    this.root.remove();
  }
}

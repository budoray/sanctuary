import { listCampaigns, listModules, listSessions, ModuleInfo } from '../net/api';
import { el } from './utils';

export class Hub {
  private root: HTMLElement;
  private onSolo: () => void;
  private onJoin: () => void;
  private onCampaigns: () => void;
  private onResume: () => void;
  private container: HTMLElement;
  private modules: ModuleInfo[] = [];

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
    for (let i = 0; i < 24; i++) {
      const p = el('span', { className: 'hub-particle' });
      p.style.left = `${Math.random() * 100}%`;
      p.style.top = `${Math.random() * 100}%`;
      p.style.animationDelay = `${Math.random() * 6}s`;
      p.style.animationDuration = `${4 + Math.random() * 4}s`;
      particles.appendChild(p);
    }

    this.container = el('div', { className: 'hub-container' });
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
      'Create a hero and delve into a module alone. Your torch, your choices, your fate.',
      'Begin Solo',
      () => this.onSolo()
    );

    const join = this.buildCard(
      'join',
      'Join Adventure',
      'Resume a saved session or join an active campaign already in progress.',
      'Join / Resume',
      () => this.onJoin()
    );

    const group = this.buildCard(
      'group',
      'Create Group Adventure',
      'Start a campaign, invite friends, and lead (or follow) as DM.',
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
      const { modules } = await listModules();
      this.modules = modules;
      this.renderRealm();
    } catch {
      // Realm preview is best-effort.
    }
  }

  private renderRealm() {
    const existing = this.container.querySelector('.hub-realm');
    if (existing) existing.remove();

    const realm = el('div', { className: 'hub-realm' });
    realm.appendChild(el('h3', {}, 'Realms'));

    if (this.modules.length === 0) {
      realm.appendChild(el('p', { className: 'hub-realm-empty' }, 'Loading realms...'));
    } else {
      const scroll = el('div', { className: 'hub-realm-scroll' });
      this.modules.forEach((m) => {
        const chip = el('div', { className: 'hub-realm-chip' });
        const theme = m.theme || 'dungeon';
        chip.appendChild(el('span', { className: `hub-realm-theme theme-${theme}` }, theme));
        chip.appendChild(el('strong', {}, m.name));
        chip.appendChild(el('span', { className: 'hub-realm-size' }, `${m.width}×${m.height}`));
        scroll.appendChild(chip);
      });
      realm.appendChild(scroll);
    }

    this.container.appendChild(realm);
  }

  destroy() {
    this.root.remove();
  }
}

import { Campaign, User, createCampaign, getCampaign, joinCampaign, listCampaigns, whoami } from '../net/api';
import { AdminPanel } from './admin-panel';
import { el, clear } from './utils';

export class CampaignLobby {
  private root: HTMLElement;
  private container: HTMLElement;
  private onSelect: (campaign: Campaign) => void;
  private onBack: () => void;
  private listEl: HTMLElement;
  private user: User | null = null;
  private adminBar: HTMLElement | null = null;

  constructor(
    container: HTMLElement,
    onSelect: (campaign: Campaign) => void,
    onBack: () => void
  ) {
    this.root = el('div', { className: 'adventure-manager' });
    this.container = container;
    this.onSelect = onSelect;
    this.onBack = onBack;

    const background = el('div', { className: 'adventure-manager-background' });
    const vignette = el('div', { className: 'adventure-manager-vignette' });

    const shell = el('div', { className: 'adventure-manager-shell' });
    shell.appendChild(this.buildHeader());
    shell.appendChild(this.buildForms());

    const listHeader = el('div', { className: 'campaign-list-header' });
    listHeader.appendChild(el('h2', {}, 'Your Campaigns'));
    this.adminBar = el('div', { className: 'admin-bar' });
    this.adminBar.style.display = 'none';
    listHeader.appendChild(this.adminBar);
    shell.appendChild(listHeader);

    this.listEl = el('div', { className: 'campaigns-grid' });
    shell.appendChild(this.listEl);

    shell.appendChild(this.buildFooter());

    this.root.appendChild(background);
    this.root.appendChild(vignette);
    this.root.appendChild(shell);
    container.appendChild(this.root);
    this.load();
  }

  private buildHeader(): HTMLElement {
    const header = el('header', { className: 'adventure-manager-header' });
    const title = el('div', { className: 'adventure-manager-title' });
    title.appendChild(el('h1', {}, 'Campaigns'));
    title.appendChild(el('p', {}, 'Create a private campaign, join one by ID and password, or manage your existing campaigns.'));
    header.appendChild(title);
    header.appendChild(el('button', { className: 'adventure-manager-back', onclick: () => this.onBack() }, '← Back to Sanctuary'));
    return header;
  }

  private buildForms(): HTMLElement {
    const forms = el('div', { className: 'campaign-forms' });

    const createCard = el('div', { className: 'campaign-form-card' });
    createCard.appendChild(el('h3', {}, 'Create Campaign'));
    createCard.appendChild(el('p', {}, 'Start a new campaign for your friends. Set a password to keep it private.'));
    const nameInput = el('input', { type: 'text', placeholder: 'Campaign name' }) as HTMLInputElement;
    const passInput = el('input', { type: 'text', placeholder: 'Share password' }) as HTMLInputElement;
    const createBtn = el('button', {
      className: 'enter',
      onclick: async () => {
        const name = nameInput.value.trim();
        const password = passInput.value.trim();
        if (!name || !password) return;
        try {
          const { campaign } = await createCampaign({ name, password });
          this.onSelect(campaign);
        } catch (err: any) {
          alert(err.message || 'Create failed');
        }
      },
    }, 'Create Campaign');
    createCard.appendChild(nameInput);
    createCard.appendChild(passInput);
    createCard.appendChild(createBtn);
    forms.appendChild(createCard);

    const joinCard = el('div', { className: 'campaign-form-card' });
    joinCard.appendChild(el('h3', {}, 'Join Campaign'));
    joinCard.appendChild(el('p', {}, 'Enter the campaign ID and password shared by the DM.'));
    const idInput = el('input', { type: 'text', placeholder: 'Campaign ID' }) as HTMLInputElement;
    const joinPassInput = el('input', { type: 'text', placeholder: 'Password' }) as HTMLInputElement;
    const joinBtn = el('button', {
      className: 'enter',
      onclick: async () => {
        const id = idInput.value.trim();
        const password = joinPassInput.value.trim();
        if (!id || !password) return;
        try {
          await joinCampaign(id, password);
          const { campaign } = await getCampaign(id);
          this.onSelect(campaign);
        } catch (err: any) {
          alert(err.message || 'Join failed');
        }
      },
    }, 'Join Campaign');
    joinCard.appendChild(idInput);
    joinCard.appendChild(joinPassInput);
    joinCard.appendChild(joinBtn);
    forms.appendChild(joinCard);

    return forms;
  }

  private buildFooter(): HTMLElement {
    const footer = el('footer', { className: 'adventure-manager-footer' });
    footer.appendChild(el('button', { className: 'adventure-manager-back', onclick: () => this.onBack() }, '← Back to Sanctuary'));
    return footer;
  }

  async load() {
    try {
      const [{ campaigns }, userData] = await Promise.all([
        listCampaigns(),
        whoami().catch(() => ({ user: { id: 0, name: '', is_admin: false } })),
      ]);
      this.user = userData.user as User;
      this.render(campaigns);
      this.renderAdminBar();
    } catch (err: any) {
      clear(this.listEl);
      this.listEl.appendChild(el('div', { className: 'campaigns-empty error' }, err.message || 'Failed to load campaigns.'));
    }
  }

  private renderAdminBar() {
    if (!this.adminBar || !this.user?.is_admin) return;
    clear(this.adminBar);
    this.adminBar.style.display = 'flex';
    this.adminBar.appendChild(el('span', { className: 'admin-badge' }, 'Admin'));
    this.adminBar.appendChild(el('button', {
      onclick: () => this.showAdminPanel(),
    }, 'Open Admin Panel'));
  }

  private showAdminPanel() {
    this.destroy();
    new AdminPanel(this.container, () => {
      new CampaignLobby(this.container, this.onSelect, this.onBack);
    });
  }

  private render(campaigns: Campaign[]) {
    clear(this.listEl);
    if (campaigns.length === 0) {
      const empty = el('div', { className: 'campaigns-empty' });
      empty.appendChild(el('h3', {}, 'No campaigns yet'));
      empty.appendChild(el('p', {}, 'Create a campaign above or join an existing one to get started.'));
      this.listEl.appendChild(empty);
      return;
    }
    campaigns.forEach((c) => {
      const total = c.module_ids.length;
      const cleared = (c.cleared_module_ids || []).length;
      const progressText = total > 0 ? `Progress ${cleared}/${total}` : 'No modules';

      const card = el('div', { className: 'campaign-card', onclick: () => this.onSelect(c) });
      const header = el('div', { className: 'campaign-card-header' });
      header.appendChild(el('span', { className: 'campaign-ruleset' }, c.ruleset_id));
      header.appendChild(el('span', { className: c.is_dm ? 'campaign-role dm' : 'campaign-role' }, c.is_dm ? 'DM' : 'Player'));
      card.appendChild(header);

      const body = el('div', { className: 'campaign-card-body' });
      body.appendChild(el('h3', {}, c.name));
      body.appendChild(el('p', {}, progressText));
      if (c.completed) {
        body.appendChild(el('span', { className: 'campaign-completed' }, 'Completed'));
      }
      card.appendChild(body);

      const footer = el('div', { className: 'campaign-card-footer' });
      footer.appendChild(el('span', { className: 'campaign-id' }, c.id));
      footer.appendChild(el('span', {}, 'Open →'));
      card.appendChild(footer);
      this.listEl.appendChild(card);
    });
  }

  destroy() {
    this.root.remove();
  }
}

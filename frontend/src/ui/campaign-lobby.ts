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
    this.root = el('div', { className: 'session-select' });
    this.container = container;
    this.onSelect = onSelect;
    this.onBack = onBack;

    const panel = el('div', { className: 'session-panel' });
    panel.appendChild(el('h1', {}, 'Campaigns'));
    panel.appendChild(el('p', { className: 'subtitle' }, 'Create a private campaign or join one by link and password.'));

    this.adminBar = el('div', { className: 'admin-bar' });
    this.adminBar.style.display = 'none';
    panel.appendChild(this.adminBar);

    const createForm = this.buildCreateForm();
    panel.appendChild(createForm);

    const joinForm = this.buildJoinForm();
    panel.appendChild(joinForm);

    this.listEl = el('ul', { className: 'session-list' });
    panel.appendChild(el('h2', {}, 'Your Campaigns'));
    panel.appendChild(this.listEl);

    const backBtn = el('button', { className: 'enter', onclick: () => this.onBack() }, 'Back');
    panel.appendChild(backBtn);

    this.root.appendChild(panel);
    container.appendChild(this.root);
    this.load();
  }

  private buildCreateForm() {
    const wrapper = el('div', { className: 'form-group' });
    const nameInput = el('input', { type: 'text', placeholder: 'Campaign name' }) as HTMLInputElement;
    const passInput = el('input', { type: 'text', placeholder: 'Share password' }) as HTMLInputElement;
    const btn = el('button', {
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
    wrapper.appendChild(nameInput);
    wrapper.appendChild(passInput);
    wrapper.appendChild(btn);
    return wrapper;
  }

  private buildJoinForm() {
    const wrapper = el('div', { className: 'form-group' });
    const idInput = el('input', { type: 'text', placeholder: 'Campaign ID' }) as HTMLInputElement;
    const passInput = el('input', { type: 'text', placeholder: 'Password' }) as HTMLInputElement;
    const btn = el('button', {
      onclick: async () => {
        const id = idInput.value.trim();
        const password = passInput.value.trim();
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
    wrapper.appendChild(idInput);
    wrapper.appendChild(passInput);
    wrapper.appendChild(btn);
    return wrapper;
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
      this.listEl.appendChild(el('li', { className: 'empty' }, err.message || 'Failed to load campaigns.'));
    }
  }

  private renderAdminBar() {
    if (!this.adminBar || !this.user?.is_admin) return;
    clear(this.adminBar);
    this.adminBar.style.display = 'block';
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
      this.listEl.appendChild(el('li', { className: 'empty' }, 'No campaigns yet.'));
      return;
    }
    campaigns.forEach((c) => {
      const info = el('div', { className: 'session-info' });
      info.appendChild(el('strong', {}, c.name));
      info.appendChild(el('span', {}, `${c.ruleset_id} · ${c.is_dm ? 'DM' : 'Player'}`));
      const idSpan = el('span', { className: 'session-id' }, c.id);
      const item = el('li', { onclick: () => this.onSelect(c) });
      item.appendChild(info);
      item.appendChild(idSpan);
      this.listEl.appendChild(item);
    });
  }

  destroy() {
    this.root.remove();
  }
}

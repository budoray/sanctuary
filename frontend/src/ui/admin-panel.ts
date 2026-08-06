import { adminListCampaigns, adminListSessions, adminDeleteCampaign, adminDeleteSession, adminCreateCampaign } from '../net/api';
import { el, clear } from './utils';

const ALL_MODULE_IDS = [
  { id: 'sample_lair', name: 'The Goblin Lair' },
  { id: 'sunken_crypt', name: 'The Sunken Crypt' },
  { id: 'shadow_keep', name: 'The Shadow Keep' },
  { id: 'forsaken_library', name: 'The Forsaken Library' },
  { id: 'arena_pit', name: 'The Arena Pit' },
];

type Tab = 'campaigns' | 'sessions' | 'editor';

export class AdminPanel {
  private root: HTMLElement;
  private onBack: () => void;
  private campaignsEl: HTMLElement;
  private sessionsEl: HTMLElement;
  private editorEl: HTMLElement;
  private tabContent: HTMLElement;
  private selectedModules: string[] = [];

  constructor(container: HTMLElement, onBack: () => void) {
    this.root = el('div', { className: 'session-select' });
    this.onBack = onBack;

    const panel = el('div', { className: 'session-panel' });
    panel.appendChild(el('h1', {}, 'Admin Panel'));
    panel.appendChild(el('p', { className: 'subtitle' }, 'Manage campaigns and active sessions.'));

    const tabs = el('div', { className: 'admin-tabs' });
    tabs.appendChild(this.tabButton('Campaigns', 'campaigns'));
    tabs.appendChild(this.tabButton('Active Sessions', 'sessions'));
    tabs.appendChild(this.tabButton('Campaign Editor', 'editor'));
    panel.appendChild(tabs);

    this.tabContent = el('div', { className: 'admin-tab-content' });

    this.campaignsEl = el('div', {});
    this.sessionsEl = el('div', {});
    this.editorEl = el('div', {});

    this.tabContent.appendChild(this.campaignsEl);
    this.tabContent.appendChild(this.sessionsEl);
    this.tabContent.appendChild(this.editorEl);
    panel.appendChild(this.tabContent);

    const backBtn = el('button', { className: 'enter', onclick: () => this.onBack() }, 'Back');
    panel.appendChild(backBtn);

    this.root.appendChild(panel);
    container.appendChild(this.root);

    this.buildEditor();
    this.switchTab('campaigns');
    this.load();
  }

  private tabButton(label: string, tab: Tab): HTMLButtonElement {
    const btn = el('button', {
      className: 'admin-tab',
      'data-tab': tab,
      onclick: () => this.switchTab(tab),
    }, label) as HTMLButtonElement;
    return btn;
  }

  private switchTab(tab: Tab) {
    this.campaignsEl.style.display = tab === 'campaigns' ? 'block' : 'none';
    this.sessionsEl.style.display = tab === 'sessions' ? 'block' : 'none';
    this.editorEl.style.display = tab === 'editor' ? 'block' : 'none';
    this.root.querySelectorAll('.admin-tab').forEach((b) => {
      b.classList.toggle('active', b.getAttribute('data-tab') === tab);
    });
  }

  async load() {
    try {
      const [{ campaigns }, { sessions }] = await Promise.all([
        adminListCampaigns(),
        adminListSessions(),
      ]);
      this.renderCampaigns(campaigns);
      this.renderSessions(sessions);
    } catch (err: any) {
      clear(this.campaignsEl);
      this.campaignsEl.appendChild(el('div', { className: 'empty error' }, err.message || 'Failed to load admin data.'));
    }
  }

  private buildEditor() {
    clear(this.editorEl);
    this.editorEl.appendChild(el('h2', {}, 'Campaign Editor'));
    this.editorEl.appendChild(el('p', { className: 'subtitle' }, 'Create a campaign with a custom module order.'));

    const form = el('div', { className: 'admin-form' });

    const nameInput = el('input', { type: 'text', placeholder: 'Campaign name' }) as HTMLInputElement;
    const passInput = el('input', { type: 'text', placeholder: 'Share password' }) as HTMLInputElement;

    form.appendChild(el('label', {}, 'Name'));
    form.appendChild(nameInput);
    form.appendChild(el('label', {}, 'Password'));
    form.appendChild(passInput);

    form.appendChild(el('label', {}, 'Modules (check in desired order)'));
    const checklist = el('div', { className: 'module-checklist' });
    const orderDisplay = el('div', { className: 'module-order' }, 'Selected order: (none)');

    const updateOrder = () => {
      this.selectedModules = [];
      checklist.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
        const box = cb as HTMLInputElement;
        if (box.checked) this.selectedModules.push(box.value);
      });
      orderDisplay.textContent =
        this.selectedModules.length > 0
          ? `Selected order: ${this.selectedModules.map((id) => ALL_MODULE_IDS.find((m) => m.id === id)?.name || id).join(' → ')}`
          : 'Selected order: (none)';
    };

    ALL_MODULE_IDS.forEach((mod) => {
      const row = el('label', { className: 'module-check-row' });
      const cb = el('input', {
        type: 'checkbox',
        value: mod.id,
        onchange: () => updateOrder(),
      }) as HTMLInputElement;
      row.appendChild(cb);
      row.appendChild(document.createTextNode(mod.name));
      checklist.appendChild(row);
    });

    form.appendChild(checklist);
    form.appendChild(orderDisplay);

    const statusEl = el('div', { className: 'editor-status' });

    const createBtn = el('button', {
      className: 'enter',
      onclick: async () => {
        const name = nameInput.value.trim();
        const password = passInput.value.trim();
        if (!name || !password) {
          statusEl.textContent = 'Name and password are required.';
          return;
        }
        if (this.selectedModules.length === 0) {
          statusEl.textContent = 'Select at least one module.';
          return;
        }
        try {
          createBtn.disabled = true;
          createBtn.textContent = 'Creating...';
          await adminCreateCampaign({ name, password, module_ids: this.selectedModules });
          nameInput.value = '';
          passInput.value = '';
          checklist.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
            (cb as HTMLInputElement).checked = false;
          });
          this.selectedModules = [];
          updateOrder();
          statusEl.textContent = 'Campaign created.';
          createBtn.textContent = 'Create Campaign';
          createBtn.disabled = false;
          this.switchTab('campaigns');
          this.load();
        } catch (err: any) {
          statusEl.textContent = err.message || 'Create failed';
          createBtn.textContent = 'Create Campaign';
          createBtn.disabled = false;
        }
      },
    }, 'Create Campaign') as HTMLButtonElement;

    form.appendChild(createBtn);
    form.appendChild(statusEl);
    this.editorEl.appendChild(form);
  }

  private renderCampaigns(campaigns: { id: string; name: string; ruleset_id: string; module_ids: string[]; dm_account_id: number; member_count: number; created_at: string | null }[]) {
    clear(this.campaignsEl);
    this.campaignsEl.appendChild(el('h2', {}, 'Campaigns'));

    if (campaigns.length === 0) {
      this.campaignsEl.appendChild(el('div', { className: 'empty' }, 'No campaigns.'));
      return;
    }

    const list = el('ul', { className: 'session-list' });
    campaigns.forEach((c) => {
      const info = el('div', { className: 'session-info' });
      info.appendChild(el('strong', {}, c.name));
      const moduleNames = c.module_ids.map((id) => ALL_MODULE_IDS.find((m) => m.id === id)?.name || id).join(' → ');
      info.appendChild(el('span', {}, `${c.ruleset_id} · DM ${c.dm_account_id} · ${c.member_count} members`));
      info.appendChild(el('span', { className: 'module-order' }, `Order: ${moduleNames}`));

      const delBtn = el('button', {
        className: 'danger',
        onclick: async () => {
          if (!confirm(`Delete campaign "${c.name}"?`)) return;
          try {
            await adminDeleteCampaign(c.id);
            this.load();
          } catch (err: any) {
            alert(err.message || 'Delete failed');
          }
        },
      }, 'Delete') as HTMLButtonElement;

      const row = el('li', {});
      row.appendChild(info);
      row.appendChild(delBtn);
      list.appendChild(row);
    });
    this.campaignsEl.appendChild(list);
  }

  private renderSessions(sessions: { id: string; name: string; module_id: string; campaign_id: string | null; status: string; turn: number; phase: string; player_count: number }[]) {
    clear(this.sessionsEl);
    this.sessionsEl.appendChild(el('h2', {}, 'Active Sessions'));

    if (sessions.length === 0) {
      this.sessionsEl.appendChild(el('div', { className: 'empty' }, 'No active sessions.'));
      return;
    }

    const list = el('ul', { className: 'session-list' });
    sessions.forEach((s) => {
      const info = el('div', { className: 'session-info' });
      info.appendChild(el('strong', {}, s.name));
      info.appendChild(el('span', {}, `${s.module_id} · Turn ${s.turn} · ${s.phase} · ${s.player_count} players`));

      const delBtn = el('button', {
        className: 'danger',
        onclick: async () => {
          if (!confirm(`Delete session "${s.name}"?`)) return;
          try {
            await adminDeleteSession(s.id);
            this.load();
          } catch (err: any) {
            alert(err.message || 'Delete failed');
          }
        },
      }, 'Delete') as HTMLButtonElement;

      const row = el('li', {});
      row.appendChild(info);
      row.appendChild(delBtn);
      list.appendChild(row);
    });
    this.sessionsEl.appendChild(list);
  }

  destroy() {
    this.root.remove();
  }
}

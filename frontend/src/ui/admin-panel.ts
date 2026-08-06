import { adminListCampaigns, adminListSessions, adminDeleteCampaign, adminDeleteSession } from '../net/api';
import { el, clear } from './utils';

export class AdminPanel {
  private root: HTMLElement;
  private onBack: () => void;
  private campaignsEl: HTMLElement;
  private sessionsEl: HTMLElement;

  constructor(container: HTMLElement, onBack: () => void) {
    this.root = el('div', { className: 'session-select' });
    this.onBack = onBack;

    const panel = el('div', { className: 'session-panel' });
    panel.appendChild(el('h1', {}, 'Admin Panel'));
    panel.appendChild(el('p', { className: 'subtitle' }, 'Manage campaigns and active sessions.'));

    panel.appendChild(el('h2', {}, 'Campaigns'));
    this.campaignsEl = el('ul', { className: 'session-list' });
    panel.appendChild(this.campaignsEl);

    panel.appendChild(el('h2', {}, 'Active Sessions'));
    this.sessionsEl = el('ul', { className: 'session-list' });
    panel.appendChild(this.sessionsEl);

    const backBtn = el('button', { className: 'enter', onclick: () => this.onBack() }, 'Back');
    panel.appendChild(backBtn);

    this.root.appendChild(panel);
    container.appendChild(this.root);
    this.load();
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
      this.campaignsEl.appendChild(el('li', { className: 'empty error' }, err.message || 'Failed to load admin data.'));
    }
  }

  private renderCampaigns(campaigns: { id: string; name: string; ruleset_id: string; dm_account_id: number; member_count: number; created_at: string | null }[]) {
    clear(this.campaignsEl);
    if (campaigns.length === 0) {
      this.campaignsEl.appendChild(el('li', { className: 'empty' }, 'No campaigns.'));
      return;
    }
    campaigns.forEach((c) => {
      const info = el('div', { className: 'session-info' });
      info.appendChild(el('strong', {}, c.name));
      info.appendChild(el('span', {}, `${c.ruleset_id} · DM ${c.dm_account_id} · ${c.member_count} members`));

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
      this.campaignsEl.appendChild(row);
    });
  }

  private renderSessions(sessions: { id: string; name: string; module_id: string; campaign_id: string | null; status: string; turn: number; phase: string; player_count: number }[]) {
    clear(this.sessionsEl);
    if (sessions.length === 0) {
      this.sessionsEl.appendChild(el('li', { className: 'empty' }, 'No active sessions.'));
      return;
    }
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
      this.sessionsEl.appendChild(row);
    });
  }

  destroy() {
    this.root.remove();
  }
}

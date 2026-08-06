import {
  Campaign,
  CampaignMember,
  CharacterState,
  getCampaignMembers,
  joinSession,
  listCampaignSessions,
  listCharacters,
  setMemberRole,
  transferDm,
} from '../net/api';
import { el, clear } from './utils';

interface CampaignSession {
  id: string;
  name: string;
  module_id: string;
  status: string;
  turn: number;
  phase: string;
  player_count: number;
}

export class CampaignDetail {
  private root: HTMLElement;
  private campaign: Campaign;
  private onStartNew: (campaign: Campaign) => void;
  private onJoinSession: (session: CampaignSession) => void;
  private onBack: () => void;
  private sessionsEl: HTMLElement;
  private membersEl: HTMLElement;
  private characters: CharacterState[] = [];
  private members: CampaignMember[] = [];

  constructor(
    container: HTMLElement,
    campaign: Campaign,
    onStartNew: (campaign: Campaign) => void,
    onJoinSession: (session: CampaignSession) => void,
    onBack: () => void
  ) {
    this.root = el('div', { className: 'session-select' });
    this.campaign = campaign;
    this.onStartNew = onStartNew;
    this.onJoinSession = onJoinSession;
    this.onBack = onBack;

    const panel = el('div', { className: 'session-panel' });
    panel.appendChild(el('h1', {}, campaign.name));
    const roleText = campaign.is_dm ? 'You are a DM' : 'Campaign';
    panel.appendChild(el('p', { className: 'subtitle' }, `${campaign.ruleset_id} · ${roleText}`));

    const actions = el('div', { className: 'session-actions' });
    const newBtn = el('button', {
      className: 'enter',
      onclick: () => this.onStartNew(campaign),
    }, 'Start New Session');
    actions.appendChild(newBtn);
    panel.appendChild(actions);

    panel.appendChild(el('h2', {}, 'Active Sessions'));
    this.sessionsEl = el('ul', { className: 'session-list' });
    panel.appendChild(this.sessionsEl);

    this.membersEl = el('div', { className: 'members-panel' });
    panel.appendChild(el('h2', {}, 'Members'));
    panel.appendChild(this.membersEl);

    const backBtn = el('button', { className: 'enter', onclick: () => this.onBack() }, 'Back');
    panel.appendChild(backBtn);

    this.root.appendChild(panel);
    container.appendChild(this.root);
    this.load();
  }

  async load() {
    try {
      const [{ sessions }, { characters }, { members }] = await Promise.all([
        listCampaignSessions(this.campaign.id),
        listCharacters(),
        getCampaignMembers(this.campaign.id),
      ]);
      this.characters = characters;
      this.members = members;
      this.render(sessions);
      this.renderMembers();
    } catch (err: any) {
      clear(this.sessionsEl);
      this.sessionsEl.appendChild(el('li', { className: 'empty error' }, err.message || 'Failed to load sessions.'));
    }
  }

  private render(sessions: CampaignSession[]) {
    clear(this.sessionsEl);
    if (sessions.length === 0) {
      this.sessionsEl.appendChild(el('li', { className: 'empty' }, 'No active sessions. Start one above.'));
      return;
    }

    sessions.forEach((s) => {
      const info = el('div', { className: 'session-info' });
      info.appendChild(el('strong', {}, s.name));
      const phaseText = s.phase === 'player' ? 'Player Turn' : "DM's Turn";
      info.appendChild(el('span', {}, `Turn ${s.turn} · ${phaseText} · ${s.player_count} adventurer${s.player_count === 1 ? '' : 's'}`));

      const row = el('div', { className: 'session-actions' });
      const select = el('select', {}) as HTMLSelectElement;
      if (this.characters.length === 0) {
        const opt = document.createElement('option');
        opt.textContent = 'No characters';
        opt.value = '';
        select.appendChild(opt);
        select.disabled = true;
      } else {
        this.characters.forEach((c) => {
          const opt = document.createElement('option');
          opt.value = c.id ?? '';
          opt.textContent = c.name;
          select.appendChild(opt);
        });
      }
      row.appendChild(select);

      const joinBtn = el('button', {
        disabled: this.characters.length === 0,
        onclick: async () => {
          if (!select.value) return;
          try {
            await joinSession(s.id, select.value);
            this.onJoinSession(s);
          } catch (err: any) {
            alert(err.message || 'Join failed');
          }
        },
      }, 'Join') as HTMLButtonElement;
      row.appendChild(joinBtn);

      const item = el('li', {});
      item.appendChild(info);
      item.appendChild(row);
      this.sessionsEl.appendChild(item);
    });
  }

  private renderMembers() {
    clear(this.membersEl);
    if (this.members.length === 0) {
      this.membersEl.appendChild(el('p', { className: 'empty' }, 'No members.'));
      return;
    }

    const isDm = this.campaign.is_dm;
    this.members.forEach((m) => {
      const row = el('div', { className: 'member-row' });
      row.appendChild(el('span', {}, `Account ${m.account_id} · ${m.role}`));

      if (isDm) {
        const controls = el('span', { className: 'member-controls' });

        if (m.role !== 'dm') {
          controls.appendChild(el('button', {
            onclick: async () => {
              try {
                await transferDm(this.campaign.id, m.account_id);
                alert('DM role transferred.');
                this.campaign.dm_account_id = m.account_id;
                await this.load();
              } catch (err: any) {
                alert(err.message || 'Transfer failed');
              }
            },
          }, 'Make DM'));
        }

        if (m.role !== 'dm') {
          controls.appendChild(el('button', {
            onclick: async () => {
              try {
                await setMemberRole(this.campaign.id, m.account_id, 'dm');
                await this.load();
              } catch (err: any) {
                alert(err.message || 'Promote failed');
              }
            },
          }, 'Promote to DM'));
        } else if (this.campaign.dm_account_id !== m.account_id) {
          controls.appendChild(el('button', {
            onclick: async () => {
              try {
                await setMemberRole(this.campaign.id, m.account_id, 'player');
                await this.load();
              } catch (err: any) {
                alert(err.message || 'Demote failed');
              }
            },
          }, 'Demote to Player'));
        }

        controls.appendChild(el('button', {
          className: 'danger',
          onclick: async () => {
            if (!confirm(`Kick account ${m.account_id}?`)) return;
            try {
              await setMemberRole(this.campaign.id, m.account_id, 'none');
              await this.load();
            } catch (err: any) {
              alert(err.message || 'Kick failed');
            }
          },
        }, 'Kick'));

        row.appendChild(controls);
      }

      this.membersEl.appendChild(row);
    });
  }

  destroy() {
    this.root.remove();
  }
}

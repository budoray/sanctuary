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
    this.root = el('div', { className: 'adventure-manager' });
    this.campaign = campaign;
    this.onStartNew = onStartNew;
    this.onJoinSession = onJoinSession;
    this.onBack = onBack;

    const background = el('div', { className: 'adventure-manager-background' });
    const vignette = el('div', { className: 'adventure-manager-vignette' });

    const shell = el('div', { className: 'adventure-manager-shell' });
    shell.appendChild(this.buildHeader());

    const main = el('main', { className: 'campaign-detail-main' });

    const sessionsSection = el('section', { className: 'campaign-detail-section' });
    const sessionsHeader = el('div', { className: 'campaign-section-header' });
    sessionsHeader.appendChild(el('h2', {}, 'Active Sessions'));
    if (campaign.is_dm) {
      sessionsHeader.appendChild(el('button', {
        className: 'enter',
        onclick: () => this.onStartNew(campaign),
      }, '+ Start Session'));
    }
    sessionsSection.appendChild(sessionsHeader);
    this.sessionsEl = el('div', { className: 'campaign-sessions-grid' });
    sessionsSection.appendChild(this.sessionsEl);
    main.appendChild(sessionsSection);

    const membersSection = el('section', { className: 'campaign-detail-section' });
    membersSection.appendChild(el('h2', {}, 'Members'));
    this.membersEl = el('div', { className: 'members-list' });
    membersSection.appendChild(this.membersEl);
    main.appendChild(membersSection);

    shell.appendChild(main);
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
    title.appendChild(el('h1', {}, this.campaign.name));
    const roleText = this.campaign.is_dm ? 'You are the DM' : 'Player';
    const total = this.campaign.module_ids.length;
    const cleared = (this.campaign.cleared_module_ids || []).length;
    const progress = total > 0 ? `${cleared}/${total} modules cleared` : 'No modules assigned';
    title.appendChild(el('p', {}, `${this.campaign.ruleset_id} · ${roleText} · ${progress}`));
    header.appendChild(title);
    header.appendChild(el('button', { className: 'adventure-manager-back', onclick: () => this.onBack() }, '← Back to Campaigns'));
    return header;
  }

  private buildFooter(): HTMLElement {
    const footer = el('footer', { className: 'adventure-manager-footer' });
    footer.appendChild(el('button', { className: 'adventure-manager-back', onclick: () => this.onBack() }, '← Back to Campaigns'));
    return footer;
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
      this.sessionsEl.appendChild(el('div', { className: 'campaigns-empty error' }, err.message || 'Failed to load sessions.'));
    }
  }

  private render(sessions: CampaignSession[]) {
    clear(this.sessionsEl);
    if (sessions.length === 0) {
      const empty = el('div', { className: 'campaigns-empty' });
      empty.appendChild(el('p', {}, 'No active sessions. Start one to bring the party together.'));
      if (this.campaign.is_dm) {
        empty.appendChild(el('button', {
          className: 'enter',
          onclick: () => this.onStartNew(this.campaign),
        }, 'Start New Session'));
      }
      this.sessionsEl.appendChild(empty);
      return;
    }

    sessions.forEach((s) => {
      const phaseText = s.phase === 'player' ? 'Player Turn' : "DM's Turn";

      const card = el('div', { className: 'session-card' });
      const header = el('div', { className: 'session-card-header' });
      header.appendChild(el('span', { className: 'session-status active' }, 'Active'));
      header.appendChild(el('span', { className: 'session-turn' }, `Turn ${s.turn}`));
      card.appendChild(header);

      const body = el('div', { className: 'session-card-body' });
      body.appendChild(el('h3', {}, s.name));
      body.appendChild(el('p', {}, `${phaseText} · ${s.player_count} adventurer${s.player_count === 1 ? '' : 's'}`));
      card.appendChild(body);

      const actions = el('div', { className: 'session-card-actions' });
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
      actions.appendChild(select);
      actions.appendChild(el('button', {
        className: 'enter',
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
      }, 'Join'));
      card.appendChild(actions);
      this.sessionsEl.appendChild(card);
    });
  }

  private renderMembers() {
    clear(this.membersEl);
    if (this.members.length === 0) {
      this.membersEl.appendChild(el('div', { className: 'campaigns-empty' }, 'No members.'));
      return;
    }

    const isDm = this.campaign.is_dm;
    this.members.forEach((m) => {
      const row = el('div', { className: 'member-row' });
      const info = el('div', { className: 'member-info' });
      info.appendChild(el('strong', {}, `Account ${m.account_id}`));
      info.appendChild(el('span', { className: 'member-role' }, m.role));
      row.appendChild(info);

      if (isDm) {
        const controls = el('div', { className: 'member-controls' });

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
          }, 'Promote'));
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
          }, 'Demote'));
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

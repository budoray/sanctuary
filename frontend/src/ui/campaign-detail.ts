import {
  Campaign,
  CharacterState,
  joinSession,
  listCampaignSessions,
  listCharacters,
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
  private characters: CharacterState[] = [];

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
    panel.appendChild(el('p', { className: 'subtitle' }, `${campaign.ruleset_id} · ${campaign.is_dm ? 'You are the DM' : 'Campaign'}`));

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

    const backBtn = el('button', { className: 'enter', onclick: () => this.onBack() }, 'Back');
    panel.appendChild(backBtn);

    this.root.appendChild(panel);
    container.appendChild(this.root);
    this.load();
  }

  async load() {
    try {
      const [{ sessions }, { characters }] = await Promise.all([
        listCampaignSessions(this.campaign.id),
        listCharacters(),
      ]);
      this.characters = characters;
      this.render(sessions);
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

  destroy() {
    this.root.remove();
  }
}

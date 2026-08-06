import { GameSession, getSession, listSessions } from '../net/api';
import { el, clear } from './utils';

export class SessionSelect {
  private root: HTMLElement;
  private onResume: (session: GameSession) => void;
  private onNew: () => void;
  private listEl: HTMLElement;

  constructor(
    container: HTMLElement,
    onResume: (session: GameSession) => void,
    onNew: () => void
  ) {
    this.root = el('div', { className: 'session-select' });
    this.onResume = onResume;
    this.onNew = onNew;

    const panel = el('div', { className: 'session-panel' });
    panel.appendChild(el('h1', {}, 'Sanctuary'));
    panel.appendChild(el('p', { className: 'subtitle' }, 'Resume an adventure, or begin anew.'));

    this.listEl = el('ul', { className: 'session-list' });
    panel.appendChild(this.listEl);

    const actions = el('div', { className: 'session-actions' });
    const newBtn = el('button', { onclick: () => this.onNew() }, 'New Adventurer');
    actions.appendChild(newBtn);
    panel.appendChild(actions);

    this.root.appendChild(panel);
    container.appendChild(this.root);
    this.load();
  }

  async load() {
    try {
      const { sessions } = await listSessions();
      this.render(sessions);
    } catch (err: any) {
      this.listEl.appendChild(el('li', { className: 'empty' }, err.message || 'Failed to load sessions.'));
    }
  }

  private render(sessions: { id: string; name: string; module_id: string; character_id: string; status: string; turn: number; phase: string }[]) {
    clear(this.listEl);
    if (sessions.length === 0) {
      this.listEl.appendChild(el('li', { className: 'empty' }, 'No saved adventures.'));
      return;
    }
    sessions.forEach((s) => {
      const info = el('div', { className: 'session-info' });
      info.appendChild(el('strong', {}, s.name));
      const phaseText = s.phase === 'player' ? 'Your Move' : "DM's Move";
      const statusClass = s.status === 'active' ? '' : ` ${s.status}`;
      info.appendChild(el('span', {}, `Turn ${s.turn} · ${phaseText}`));

      const actions = el('div', { className: 'session-actions' });
      const resumeBtn = el(
        'button',
        {
          className: `enter${statusClass}`,
          onclick: () => this.resume(s.id),
        },
        s.status === 'active' ? 'Resume' : 'View'
      );
      actions.appendChild(resumeBtn);

      const item = el('li', {});
      item.appendChild(info);
      item.appendChild(actions);
      this.listEl.appendChild(item);
    });
  }

  private async resume(sessionId: string) {
    try {
      const { session } = await getSession(sessionId);
      this.onResume(session);
    } catch (err: any) {
      this.listEl.appendChild(el('li', { className: 'empty error' }, err.message || 'Failed to resume session.'));
    }
  }

  destroy() {
    this.root.remove();
  }
}

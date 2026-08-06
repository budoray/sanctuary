import { GameSession, getSession, listSessions } from '../net/api';
import { el, clear } from './utils';

export class SessionSelect {
  private root: HTMLElement;
  private onResume: (session: GameSession) => void;
  private onNew: () => void;
  private onBack?: () => void;
  private gridEl: HTMLElement;

  constructor(
    container: HTMLElement,
    onResume: (session: GameSession) => void,
    onNew: () => void,
    onBack?: () => void
  ) {
    this.root = el('div', { className: 'adventure-manager' });
    this.onResume = onResume;
    this.onNew = onNew;
    this.onBack = onBack;

    const background = el('div', { className: 'adventure-manager-background' });
    const vignette = el('div', { className: 'adventure-manager-vignette' });

    const shell = el('div', { className: 'adventure-manager-shell' });
    shell.appendChild(this.buildHeader());

    this.gridEl = el('div', { className: 'sessions-grid' });
    shell.appendChild(this.gridEl);

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
    title.appendChild(el('h1', {}, 'Join / Resume'));
    title.appendChild(el('p', {}, 'Pick up where you left off, or start a new adventurer.'));
    header.appendChild(title);

    const actions = el('div', { className: 'adventure-manager-actions' });
    actions.appendChild(el('button', { className: 'adventure-manager-btn', onclick: () => this.onNew() }, '+ New Adventurer'));
    if (this.onBack) {
      actions.appendChild(el('button', { onclick: () => this.onBack!() }, '← Back'));
    }
    header.appendChild(actions);
    return header;
  }

  private buildFooter(): HTMLElement {
    const footer = el('footer', { className: 'adventure-manager-footer' });
    if (this.onBack) {
      footer.appendChild(el('button', { className: 'adventure-manager-back', onclick: () => this.onBack!() }, '← Back to Sanctuary'));
    }
    return footer;
  }

  async load() {
    try {
      const { sessions } = await listSessions();
      this.render(sessions);
    } catch (err: any) {
      clear(this.gridEl);
      this.gridEl.appendChild(el('div', { className: 'sessions-empty error' }, err.message || 'Failed to load sessions.'));
    }
  }

  private render(sessions: { id: string; name: string; module_id: string; character_id: string; status: string; turn: number; phase: string }[]) {
    clear(this.gridEl);
    if (sessions.length === 0) {
      const empty = el('div', { className: 'sessions-empty' });
      empty.appendChild(el('h2', {}, 'No saved adventures'));
      empty.appendChild(el('p', {}, 'Your active sessions will appear here. Create a hero to begin.'));
      empty.appendChild(el('button', { className: 'enter', onclick: () => this.onNew() }, 'Create New Adventurer'));
      this.gridEl.appendChild(empty);
      return;
    }
    sessions.forEach((s) => {
      const phaseText = s.phase === 'player' ? 'Your Move' : "DM's Move";
      const statusLabel = s.status === 'active' ? 'Active' : 'Complete';
      const statusClass = s.status === 'active' ? 'active' : 'complete';

      const card = el('div', { className: 'session-card' });
      const header = el('div', { className: 'session-card-header' });
      header.appendChild(el('span', { className: `session-status ${statusClass}` }, statusLabel));
      header.appendChild(el('span', { className: 'session-turn' }, `Turn ${s.turn}`));
      card.appendChild(header);

      const body = el('div', { className: 'session-card-body' });
      body.appendChild(el('h3', {}, s.name));
      body.appendChild(el('p', {}, `${phaseText} · ${s.module_id}`));
      card.appendChild(body);

      const actions = el('div', { className: 'session-card-actions' });
      actions.appendChild(el('button', {
        className: 'enter',
        onclick: () => this.resume(s.id),
      }, s.status === 'active' ? 'Resume' : 'View'));
      card.appendChild(actions);
      this.gridEl.appendChild(card);
    });
  }

  private async resume(sessionId: string) {
    try {
      const { session } = await getSession(sessionId);
      this.onResume(session);
    } catch (err: any) {
      clear(this.gridEl);
      this.gridEl.appendChild(el('div', { className: 'sessions-empty error' }, err.message || 'Failed to resume session.'));
    }
  }

  destroy() {
    this.root.remove();
  }
}

import { GameSession } from '../net/api';
import { el } from './utils';

export class ResumeScreen {
  private root: HTMLElement;
  private onResume: () => void;
  private onNew: () => void;

  constructor(
    container: HTMLElement,
    session: GameSession,
    onResume: () => void,
    onNew: () => void
  ) {
    this.root = el('div', { className: 'session-select' });
    this.onResume = onResume;
    this.onNew = onNew;

    const panel = el('div', { className: 'session-panel' });
    panel.appendChild(el('h1', {}, 'Sanctuary'));
    panel.appendChild(el('p', { className: 'subtitle' }, 'An adventure awaits.'));

    const card = el('div', { className: 'session-list' });
    const item = el('li', {});
    const info = el('div', { className: 'session-info' });
    info.appendChild(el('strong', {}, session.player.name));
    info.appendChild(el('span', {}, `Turn ${session.turn} · ${session.phase === 'player' ? 'Your Move' : "DM's Move"}`));
    item.appendChild(info);
    card.appendChild(item);
    panel.appendChild(card);

    const resumeBtn = el('button', { className: 'enter', onclick: () => this.onResume() }, 'Resume Adventure');
    panel.appendChild(resumeBtn);

    const newBtn = el('button', { onclick: () => this.onNew() }, 'Start New');
    panel.appendChild(newBtn);

    this.root.appendChild(panel);
    container.appendChild(this.root);
  }

  destroy() {
    this.root.remove();
  }
}

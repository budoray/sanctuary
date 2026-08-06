import { CharacterState, deleteCharacter, listCharacters } from '../net/api';
import { el, clear } from './utils';

export class CharacterSelect {
  private root: HTMLElement;
  private onPlay: (character: CharacterState, turnTimerSeconds: number) => void;
  private onCreate: () => void;
  private onSessions?: () => void;
  private listEl: HTMLElement;
  private timerInput: HTMLSelectElement;

  constructor(
    container: HTMLElement,
    onPlay: (character: CharacterState, turnTimerSeconds: number) => void,
    onCreate: () => void,
    onCampaigns: () => void,
    onSessions?: () => void
  ) {
    this.root = el('div', { className: 'session-select' });
    this.onPlay = onPlay;
    this.onCreate = onCreate;
    this.onSessions = onSessions;

    const panel = el('div', { className: 'session-panel' });
    panel.appendChild(el('h1', {}, 'Sanctuary'));
    panel.appendChild(el('p', { className: 'subtitle' }, 'Choose an adventurer, or begin anew.'));

    const timerWrap = el('div', { className: 'timer-config' });
    timerWrap.appendChild(el('label', { htmlFor: 'turn-timer' }, 'Turn timer'));
    this.timerInput = el('select', { id: 'turn-timer' }) as HTMLSelectElement;
    [
      { value: '0', label: 'Off' },
      { value: '15', label: '15 seconds' },
      { value: '30', label: '30 seconds' },
      { value: '60', label: '1 minute' },
    ].forEach((opt) => {
      const option = document.createElement('option');
      option.value = opt.value;
      option.textContent = opt.label;
      this.timerInput.appendChild(option);
    });
    timerWrap.appendChild(this.timerInput);
    panel.appendChild(timerWrap);

    this.listEl = el('ul', { className: 'session-list' });
    panel.appendChild(this.listEl);

    const actions = el('div', { className: 'session-actions' });
    const newBtn = el('button', { onclick: () => this.onCreate() }, 'New Adventurer');
    const campaignBtn = el('button', { onclick: () => onCampaigns() }, 'Campaigns');
    actions.appendChild(newBtn);
    actions.appendChild(campaignBtn);
    if (this.onSessions) {
      const sessionsBtn = el('button', { onclick: () => this.onSessions!() }, 'Saved Adventures');
      actions.appendChild(sessionsBtn);
    }
    panel.appendChild(actions);

    this.root.appendChild(panel);
    container.appendChild(this.root);
    this.load();
  }

  async load() {
    try {
      const { characters } = await listCharacters();
      this.render(characters);
    } catch (err: any) {
      this.listEl.appendChild(el('li', { className: 'empty' }, err.message || 'Failed to load characters.'));
    }
  }

  private render(characters: CharacterState[]) {
    clear(this.listEl);
    if (characters.length === 0) {
      this.listEl.appendChild(el('li', { className: 'empty' }, 'No adventurers yet.'));
      return;
    }
    characters.forEach((c) => {
      const info = el('div', { className: 'session-info' });
      info.appendChild(el('strong', {}, c.name));
      info.appendChild(
        el(
          'span',
          {},
          `${this.titleCase(c.ancestry)} ${c.classes.map((x) => this.titleCase(x)).join('/')} · HP ${c.hit_points}/${c.max_hp} · AC ${c.armour_class}`
        )
      );
      const idSpan = el('span', { className: 'session-id' }, c.id || '');
      const actions = el('div', { className: 'session-actions' });
      const playBtn = el('button', { onclick: () => this.onPlay(c, parseInt(this.timerInput.value, 10) || 0) }, 'Play');
      const delBtn = el('button', {
        className: 'danger',
        onclick: async () => {
          if (!c.id) return;
          if (!confirm(`Delete ${c.name}?`)) return;
          await deleteCharacter(c.id);
          this.load();
        },
      }, 'Delete');
      actions.appendChild(playBtn);
      actions.appendChild(delBtn);

      const item = el('li', {});
      item.appendChild(info);
      item.appendChild(idSpan);
      item.appendChild(actions);
      this.listEl.appendChild(item);
    });
  }

  private titleCase(str: string) {
    return str.replace(/\b\w/g, (c) => c.toUpperCase());
  }

  destroy() {
    this.root.remove();
  }
}

import { CharacterState, deleteCharacter, listCharacters } from '../net/api';
import { el, clear } from './utils';

export class CharacterSelect {
  private root: HTMLElement;
  private onPlay: (character: CharacterState) => void;
  private onCreate: () => void;
  private listEl: HTMLElement;

  constructor(
    container: HTMLElement,
    onPlay: (character: CharacterState) => void,
    onCreate: () => void
  ) {
    this.root = el('div', { className: 'session-select' });
    this.onPlay = onPlay;
    this.onCreate = onCreate;

    const panel = el('div', { className: 'session-panel' });
    panel.appendChild(el('h1', {}, 'Sanctuary'));
    panel.appendChild(el('p', { className: 'subtitle' }, 'Choose an adventurer, or begin anew.'));

    this.listEl = el('ul', { className: 'session-list' });
    panel.appendChild(this.listEl);

    const newBtn = el('button', { className: 'enter', onclick: () => this.onCreate() }, 'New Adventurer');
    panel.appendChild(newBtn);

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
      const playBtn = el('button', { onclick: () => this.onPlay(c) }, 'Play');
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

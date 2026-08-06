import { CharacterState, deleteCharacter, getAccountProgress, listCharacters, listModules, ModuleInfo } from '../net/api';
import { CharacterSheet } from './character-sheet';
import { el, clear } from './utils';

const THEME_LABELS: Record<string, string> = {
  dungeon: 'Dungeon',
  cave: 'Cave',
  library: 'Library',
  ice: 'Frozen',
  lava: 'Volcanic',
  forest: 'Forest',
  tomb: 'Tomb',
  sewer: 'Sewer',
};

export class CharacterSelect {
  private root: HTMLElement;
  private onPlay: (character: CharacterState, turnTimerSeconds: number, moduleId: string) => void;
  private onCreate: () => void;
  private onSessions?: () => void;
  private listEl: HTMLElement;
  private timerInput: HTMLSelectElement;
  private moduleCardsEl: HTMLElement;
  private moduleErrorEl: HTMLElement;
  private modules: ModuleInfo[] = [];
  private selectedModuleId = 'sample_lair';
  private progressEl: HTMLElement;

  constructor(
    container: HTMLElement,
    onPlay: (character: CharacterState, turnTimerSeconds: number, moduleId: string) => void,
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

    this.progressEl = el('div', { className: 'account-progress' });
    panel.appendChild(this.progressEl);

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

    const moduleLabel = el('div', { className: 'module-select-label' }, 'Adventure');
    panel.appendChild(moduleLabel);
    this.moduleCardsEl = el('div', { className: 'module-cards' });
    this.moduleErrorEl = el('div', { className: 'module-select-error' });
    panel.appendChild(this.moduleCardsEl);
    panel.appendChild(this.moduleErrorEl);

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
      const [{ characters }, { modules }, progress] = await Promise.all([
        listCharacters(),
        listModules(),
        getAccountProgress().catch(() => null),
      ]);
      this.modules = modules;
      this.renderModules();
      this.render(characters);
      this.renderProgress(progress);
    } catch (err: any) {
      this.listEl.appendChild(el('li', { className: 'empty' }, err.message || 'Failed to load characters.'));
      this.moduleErrorEl.textContent = err.message || 'Failed to load adventures.';
    }
  }

  private renderProgress(progress: { wins?: number; losses?: number; boss_kills?: number; modules_cleared?: number; deaths?: number; level_ups?: number; sessions?: number } | null) {
    clear(this.progressEl);
    if (!progress) {
      this.progressEl.style.display = 'none';
      return;
    }
    this.progressEl.style.display = 'block';
    this.progressEl.appendChild(el('span', {}, `Wins ${progress.wins ?? 0}`));
    this.progressEl.appendChild(el('span', {}, `Losses ${progress.losses ?? 0}`));
    this.progressEl.appendChild(el('span', {}, `Boss Kills ${progress.boss_kills ?? 0}`));
    this.progressEl.appendChild(el('span', {}, `Modules Cleared ${progress.modules_cleared ?? 0}`));
    this.progressEl.appendChild(el('span', {}, `Deaths ${progress.deaths ?? 0}`));
    this.progressEl.appendChild(el('span', {}, `Level Ups ${progress.level_ups ?? 0}`));
  }

  private renderModules() {
    clear(this.moduleCardsEl);
    clear(this.moduleErrorEl);
    if (this.modules.length === 0) {
      this.moduleErrorEl.textContent = 'No adventures available.';
      return;
    }
    this.modules.forEach((m) => {
      const card = el('div', {
        className: `module-card${m.id === this.selectedModuleId ? ' selected' : ''}`,
        onclick: () => this.selectModule(m.id),
      });
      const header = el('div', { className: 'module-card-header' });
      const theme = THEME_LABELS[m.theme || 'dungeon'] || m.theme || 'Dungeon';
      const badge = el('span', { className: `module-theme theme-${m.theme || 'dungeon'}` }, theme);
      header.appendChild(badge);
      header.appendChild(el('span', { className: 'module-size' }, `${m.width}×${m.height}`));
      card.appendChild(header);
      card.appendChild(el('h3', {}, m.name));
      card.appendChild(el('p', { className: 'module-desc' }, m.description || ''));
      const preview = this.buildMiniMap(m);
      if (preview) card.appendChild(preview);
      this.moduleCardsEl.appendChild(card);
    });
  }

  private buildMiniMap(m: ModuleInfo): HTMLElement | null {
    if (!m.tiles || m.tiles.length === 0) return null;
    const wrap = el('div', { className: 'module-mini-map' });
    const maxRows = Math.min(m.height, 16);
    const maxCols = Math.min(m.width, 22);
    wrap.style.gridTemplateRows = `repeat(${maxRows}, 1fr)`;
    wrap.style.gridTemplateColumns = `repeat(${maxCols}, 1fr)`;
    for (let y = 0; y < maxRows; y++) {
      const row = m.tiles[y] || '';
      for (let x = 0; x < maxCols; x++) {
        const tile = row[x] || '0';
        const cell = el('span', { className: `mini-tile mini-tile-${tile === '1' ? 'wall' : tile === '2' ? 'trap' : 'floor'}` });
        wrap.appendChild(cell);
      }
    }
    return wrap;
  }

  private selectModule(id: string) {
    this.selectedModuleId = id;
    this.renderModules();
  }

  private render(characters: CharacterState[]) {
    clear(this.listEl);
    if (characters.length === 0) {
      this.listEl.appendChild(el('li', { className: 'empty' }, 'No adventurers yet.'));
      return;
    }
    characters.forEach((c) => {
      const portraitUrl = c.portrait_url || this.fallbackPortraitUrl(c.classes[0]);
      const portrait = el('img', {
        className: 'session-portrait',
        src: portraitUrl,
        alt: c.name,
        onerror: () => { portrait.src = this.fallbackPortraitUrl(); },
      }) as HTMLImageElement;

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
      const playBtn = el('button', { onclick: () => this.onPlay(c, parseInt(this.timerInput.value, 10) || 0, this.selectedModuleId) }, 'Play');
      const sheetBtn = el('button', { onclick: () => this.openSheet(c) }, 'Sheet');
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
      actions.appendChild(sheetBtn);
      actions.appendChild(delBtn);

      const item = el('li', {});
      item.appendChild(portrait);
      item.appendChild(info);
      item.appendChild(idSpan);
      item.appendChild(actions);
      this.listEl.appendChild(item);
    });
  }

  private fallbackPortraitUrl(className?: string): string {
    const key = (className || 'generic').toLowerCase().replace(/\s+/g, '-');
    return `/portraits/${key}.png`;
  }

  private openSheet(character: CharacterState) {
    new CharacterSheet(this.root, character, () => this.load());
  }

  private titleCase(str: string) {
    return str.replace(/\b\w/g, (c) => c.toUpperCase());
  }

  destroy() {
    this.root.remove();
  }
}

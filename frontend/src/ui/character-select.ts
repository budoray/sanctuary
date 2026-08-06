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
  private onCampaigns: () => void;
  private onSessions?: () => void;
  private onBack?: () => void;
  private charactersEl!: HTMLElement;
  private timerInput!: HTMLSelectElement;
  private moduleCardsEl!: HTMLElement;
  private moduleErrorEl!: HTMLElement;
  private progressEl!: HTMLElement;
  private modules: ModuleInfo[] = [];
  private selectedModuleId = 'sample_lair';
  private characters: CharacterState[] = [];

  constructor(
    container: HTMLElement,
    onPlay: (character: CharacterState, turnTimerSeconds: number, moduleId: string) => void,
    onCreate: () => void,
    onCampaigns: () => void,
    onSessions?: () => void,
    onBack?: () => void
  ) {
    this.root = el('div', { className: 'solo-hub' });
    this.onPlay = onPlay;
    this.onCreate = onCreate;
    this.onCampaigns = onCampaigns;
    this.onSessions = onSessions;
    this.onBack = onBack;

    const background = el('div', { className: 'solo-hub-background' });
    const vignette = el('div', { className: 'solo-hub-vignette' });

    const shell = el('div', { className: 'solo-hub-shell' });
    shell.appendChild(this.buildHeader());
    shell.appendChild(this.buildMain());
    shell.appendChild(this.buildFooter());

    this.root.appendChild(background);
    this.root.appendChild(vignette);
    this.root.appendChild(shell);
    container.appendChild(this.root);

    this.load();
  }

  private buildHeader(): HTMLElement {
    const header = el('header', { className: 'solo-hub-header' });

    const titleBlock = el('div', { className: 'solo-hub-title' });
    titleBlock.appendChild(el('h1', {}, 'Solo Adventure'));
    titleBlock.appendChild(el('p', {}, 'Choose a hero and a realm to begin your delve.'));
    header.appendChild(titleBlock);

    this.progressEl = el('div', { className: 'account-progress' });
    header.appendChild(this.progressEl);

    const controls = el('div', { className: 'solo-hub-controls' });

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
    controls.appendChild(timerWrap);

    const actionGroup = el('div', { className: 'solo-hub-actions' });
    actionGroup.appendChild(el('button', { className: 'solo-hub-btn', onclick: () => this.onCreate() }, '+ New Hero'));
    actionGroup.appendChild(el('button', { className: 'solo-hub-btn', onclick: () => this.onCampaigns() }, 'Campaigns'));
    if (this.onSessions) {
      actionGroup.appendChild(el('button', { className: 'solo-hub-btn', onclick: () => this.onSessions!() }, 'Saved'));
    }
    controls.appendChild(actionGroup);

    header.appendChild(controls);
    return header;
  }

  private buildMain(): HTMLElement {
    const main = el('main', { className: 'solo-hub-main' });

    const charactersSection = el('section', { className: 'solo-hub-section characters-section' });
    charactersSection.appendChild(el('h2', {}, 'Your Heroes'));
    this.charactersEl = el('div', { className: 'characters-grid' });
    charactersSection.appendChild(this.charactersEl);
    main.appendChild(charactersSection);

    const realmsSection = el('section', { className: 'solo-hub-section realms-section' });
    const realmsHeader = el('div', { className: 'realms-header' });
    realmsHeader.appendChild(el('h2', {}, 'Realms'));
    this.moduleErrorEl = el('div', { className: 'module-select-error' });
    realmsHeader.appendChild(this.moduleErrorEl);
    realmsSection.appendChild(realmsHeader);
    this.moduleCardsEl = el('div', { className: 'module-cards' });
    realmsSection.appendChild(this.moduleCardsEl);
    main.appendChild(realmsSection);

    return main;
  }

  private buildFooter(): HTMLElement {
    const footer = el('footer', { className: 'solo-hub-footer' });
    if (this.onBack) {
      footer.appendChild(el('button', { className: 'solo-hub-back', onclick: () => this.onBack!() }, '← Back to Sanctuary'));
    }
    footer.appendChild(el('span', { className: 'solo-hub-hint' }, 'Tip: click a realm to select it, then Play a hero.'));
    return footer;
  }

  async load() {
    try {
      const [{ characters }, { modules }, progress] = await Promise.all([
        listCharacters(),
        listModules(),
        getAccountProgress().catch(() => null),
      ]);
      this.modules = modules;
      this.characters = characters;
      this.renderProgress(progress);
      this.renderModules();
      this.renderCharacters(characters);
    } catch (err: any) {
      this.charactersEl.appendChild(el('div', { className: 'characters-empty' }, err.message || 'Failed to load heroes.'));
      this.moduleErrorEl.textContent = err.message || 'Failed to load realms.';
    }
  }

  private renderProgress(progress: { wins?: number; losses?: number; boss_kills?: number; modules_cleared?: number; deaths?: number; level_ups?: number; sessions?: number } | null) {
    clear(this.progressEl);
    if (!progress) {
      this.progressEl.style.display = 'none';
      return;
    }
    this.progressEl.style.display = 'flex';
    const stats = [
      ['Wins', progress.wins ?? 0],
      ['Losses', progress.losses ?? 0],
      ['Boss Kills', progress.boss_kills ?? 0],
      ['Cleared', progress.modules_cleared ?? 0],
      ['Deaths', progress.deaths ?? 0],
      ['Level Ups', progress.level_ups ?? 0],
    ];
    stats.forEach(([label, value]) => {
      this.progressEl.appendChild(el('span', {}, `${label} ${value}`));
    });
  }

  private renderModules() {
    clear(this.moduleCardsEl);
    clear(this.moduleErrorEl);
    if (this.modules.length === 0) {
      this.moduleErrorEl.textContent = 'No realms available.';
      return;
    }
    this.modules.forEach((m) => {
      const card = el('div', {
        className: `module-card${m.id === this.selectedModuleId ? ' selected' : ''}`,
        onclick: () => this.selectModule(m.id),
      });
      const preview = this.buildMiniMap(m);
      if (preview) card.appendChild(preview);
      const body = el('div', { className: 'module-card-body' });
      const header = el('div', { className: 'module-card-header' });
      const theme = THEME_LABELS[m.theme || 'dungeon'] || m.theme || 'Dungeon';
      header.appendChild(el('span', { className: `module-theme theme-${m.theme || 'dungeon'}` }, theme));
      header.appendChild(el('span', { className: 'module-size' }, `${m.width}×${m.height}`));
      body.appendChild(header);
      body.appendChild(el('h3', {}, m.name));
      body.appendChild(el('p', { className: 'module-desc' }, m.description || ''));
      card.appendChild(body);
      this.moduleCardsEl.appendChild(card);
    });
  }

  private buildMiniMap(m: ModuleInfo): HTMLElement | null {
    if (!m.tiles || m.tiles.length === 0) return null;
    const wrap = el('div', { className: 'module-mini-map' });
    const maxRows = Math.min(m.height, 20);
    const maxCols = Math.min(m.width, 28);
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
    this.renderCharacters(this.characters);
  }

  private renderCharacters(characters: CharacterState[]) {
    clear(this.charactersEl);
    if (characters.length === 0) {
      const empty = el('div', { className: 'characters-empty' });
      empty.appendChild(el('p', {}, 'No adventurers yet.'));
      empty.appendChild(el('button', { onclick: () => this.onCreate() }, 'Create your first hero'));
      this.charactersEl.appendChild(empty);
      return;
    }
    characters.forEach((c) => {
      const card = el('div', { className: 'character-card' });

      const portraitUrl = c.portrait_url || this.fallbackPortraitUrl(c.classes[0]);
      const portrait = el('img', {
        className: 'character-portrait',
        src: portraitUrl,
        alt: c.name,
        onerror: () => { portrait.src = this.fallbackPortraitUrl(); },
      }) as HTMLImageElement;

      const info = el('div', { className: 'character-info' });
      info.appendChild(el('strong', {}, c.name));
      info.appendChild(el('span', { className: 'character-meta' }, `${this.titleCase(c.ancestry)} · ${c.classes.map((x) => this.titleCase(x)).join('/')}`));

      const hpPercent = Math.max(0, Math.min(100, Math.round((c.hit_points / Math.max(1, c.max_hp)) * 100)));
      const hpBar = el('div', { className: 'character-hp-bar' });
      hpBar.appendChild(el('span', { style: `width:${hpPercent}%` }));
      info.appendChild(hpBar);

      const stats = el('div', { className: 'character-stats' });
      stats.appendChild(el('span', {}, `HP ${c.hit_points}/${c.max_hp}`));
      stats.appendChild(el('span', {}, `AC ${c.armour_class}`));
      stats.appendChild(el('span', {}, `LVL ${c.level ?? 1}`));
      info.appendChild(stats);

      const abilities = el('div', { className: 'character-abilities' });
      const abilityEntries = [
        ['STR', c.scores?.strength],
        ['DEX', c.scores?.dexterity],
        ['CON', c.scores?.constitution],
        ['INT', c.scores?.intelligence],
        ['WIS', c.scores?.wisdom],
        ['CHA', c.scores?.charisma],
      ];
      abilityEntries.forEach(([label, value]) => {
        abilities.appendChild(el('span', {}, `${label} ${value ?? '-'}`));
      });
      info.appendChild(abilities);

      const actions = el('div', { className: 'character-actions' });
      actions.appendChild(el('button', { className: 'play-btn', onclick: () => this.onPlay(c, parseInt(this.timerInput.value, 10) || 0, this.selectedModuleId) }, 'Play'));
      actions.appendChild(el('button', { onclick: () => this.openSheet(c) }, 'Sheet'));
      actions.appendChild(el('button', {
        className: 'danger',
        onclick: async () => {
          if (!c.id) return;
          if (!confirm(`Delete ${c.name}?`)) return;
          await deleteCharacter(c.id);
          this.load();
        },
      }, 'Delete'));

      card.appendChild(portrait);
      card.appendChild(info);
      card.appendChild(actions);
      this.charactersEl.appendChild(card);
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

import {
  CharacterState,
  createCharacter,
  getRulesetOptions,
  previewCharacter,
  PreviewRequest,
} from '../net/api';
import { DiceTray } from './dice-tray';
import { el, clear, formatModifier, seededRandomSeed } from './utils';

type ModeInfo = { id: string; roll: string; arrange: boolean };

export class CharacterCreator {
  private root: HTMLElement;
  private onSaved: (character: CharacterState) => void;
  private options: { abilities: string[]; ancestries: string[]; classes: string[]; modes: ModeInfo[] } | null = null;
  private preview: CharacterState | null = null;
  private arrangement: Record<string, number> | undefined;
  private seed: number | undefined;

  private nameInput: HTMLInputElement;
  private ancestrySelect: HTMLSelectElement;
  private modeSelect: HTMLSelectElement;
  private classContainer: HTMLElement;
  private previewPanel: HTMLElement;
  private messageEl: HTMLElement;
  private arrangeContainer: HTMLElement;
  private rollButton: HTMLButtonElement;
  private saveButton: HTMLButtonElement;

  constructor(container: HTMLElement, onSaved: (character: CharacterState) => void) {
    this.root = el('div', { className: 'creator-shell' });
    this.onSaved = onSaved;

    const panel = el('div', { className: 'creator-panel' });
    panel.appendChild(el('h1', {}, 'Sanctuary'));
    panel.appendChild(el('p', { className: 'subtitle' }, 'Forge your adventurer'));

    this.messageEl = el('div', { className: 'creator-message' });
    panel.appendChild(this.messageEl);

    this.nameInput = el('input', { type: 'text', value: 'Hero', maxlength: '24' }) as HTMLInputElement;
    panel.appendChild(this.formGroup('Name', this.nameInput));

    this.ancestrySelect = el('select', { onchange: () => this.updateClassChoices() }) as HTMLSelectElement;
    panel.appendChild(this.formGroup('Ancestry', this.ancestrySelect));

    this.modeSelect = el('select', {}) as HTMLSelectElement;
    panel.appendChild(this.formGroup('Generation', this.modeSelect));

    this.classContainer = el('div', { className: 'creator-classes' });
    panel.appendChild(this.formGroup('Class', this.classContainer));

    this.rollButton = el('button', { className: 'reroll', onclick: () => this.rollPreview() }, 'Roll Abilities') as HTMLButtonElement;
    panel.appendChild(this.rollButton);

    this.arrangeContainer = el('div', { className: 'arrange-container' });
    panel.appendChild(this.arrangeContainer);

    this.previewPanel = el('div', { className: 'preview-panel' });
    panel.appendChild(this.previewPanel);

    this.saveButton = el('button', { className: 'enter', onclick: () => this.save() }, 'Enter Sanctuary') as HTMLButtonElement;
    this.saveButton.disabled = true;
    panel.appendChild(this.saveButton);

    this.root.appendChild(panel);

    const trayAnchor = el('div', { className: 'tray-anchor' });
    this.root.appendChild(trayAnchor);
    new DiceTray(trayAnchor);

    container.appendChild(this.root);
    this.loadOptions();
  }

  private formGroup(label: string, control: HTMLElement) {
    const group = el('div', { className: 'form-group' });
    group.appendChild(el('label', {}, label));
    group.appendChild(control);
    return group;
  }

  private async loadOptions() {
    try {
      this.options = await getRulesetOptions();
      this.populateControls();
    } catch (err) {
      this.showMessage('Could not load ruleset options.', true);
    }
  }

  private populateControls() {
    if (!this.options) return;
    clear(this.ancestrySelect);
    this.options.ancestries.forEach((a) => {
      this.ancestrySelect.appendChild(el('option', { value: a }, this.titleCase(a)));
    });

    clear(this.modeSelect);
    this.options.modes.forEach((m) => {
      const label = `${this.titleCase(m.id)} · ${m.roll}${m.arrange ? ' · arrange' : ''}`;
      this.modeSelect.appendChild(el('option', { value: m.id }, label));
    });

    this.updateClassChoices();
  }

  private updateClassChoices() {
    if (!this.options) return;
    clear(this.classContainer);
    this.options.classes.forEach((c) => {
      const label = el('label', { className: 'class-chip' });
      const checkbox = el('input', { type: 'checkbox', value: c, onchange: () => this.validateClassSelection() }) as HTMLInputElement;
      label.appendChild(checkbox);
      label.appendChild(document.createTextNode(this.titleCase(c)));
      this.classContainer.appendChild(label);
    });
    this.validateClassSelection();
  }

  private validateClassSelection() {
    const selected = Array.from(this.classContainer.querySelectorAll('input:checked')).map(
      (i) => (i as HTMLInputElement).value
    );
    if (selected.length === 0) {
      this.showMessage('Choose at least one class.', true);
      this.saveButton.disabled = true;
      return;
    }
    this.clearMessage();
  }

  private selectedClasses(): string[] {
    return Array.from(this.classContainer.querySelectorAll('input:checked')).map(
      (i) => (i as HTMLInputElement).value
    );
  }

  private async rollPreview() {
    this.rollButton.disabled = true;
    this.saveButton.disabled = true;
    this.clearMessage();
    this.arrangement = undefined;
    try {
      const req = this.buildRequest();
      const { character } = await previewCharacter(req);
      this.preview = character;
      this.seed = character.seed;
      this.renderPreview();
      this.saveButton.disabled = false;
      if (this.currentMode()?.arrange) {
        this.renderArrange();
      }
    } catch (err: any) {
      this.showMessage(this.formatError(err) || 'Roll failed.', true);
    } finally {
      this.rollButton.disabled = false;
    }
  }

  private currentMode(): ModeInfo | undefined {
    return this.options?.modes.find((m) => m.id === this.modeSelect.value);
  }

  private buildRequest(): PreviewRequest {
    return {
      mode: this.modeSelect.value,
      ancestry: this.ancestrySelect.value,
      classes: this.selectedClasses(),
      name: this.nameInput.value.trim() || 'Hero',
      seed: this.seed ?? seededRandomSeed(),
      arrangement: this.arrangement,
    };
  }

  private renderPreview() {
    clear(this.previewPanel);
    if (!this.preview) return;
    const char = this.preview;

    const grid = el('div', { className: 'abilities-grid' });
    this.options?.abilities.forEach((ability) => {
      const score = char.scores[ability];
      const mod = char.modifiers[ability];
      const cell = el('div');
      cell.appendChild(el('span', {}, this.abbreviate(ability)));
      cell.appendChild(el('strong', {}, String(score)));
      if (mod !== undefined) {
        cell.appendChild(el('small', {}, formatModifier(mod)));
      }
      grid.appendChild(cell);
    });

    const derived = el('div', { className: 'derived' });
    derived.appendChild(el('span', {}, `HP ${char.hit_points}`));
    derived.appendChild(el('span', {}, `AC ${char.armour_class}`));

    this.previewPanel.appendChild(grid);
    this.previewPanel.appendChild(derived);
  }

  private renderArrange() {
    clear(this.arrangeContainer);
    if (!this.preview || !this.options) return;
    const values = Object.values(this.preview.scores);
    const slots: Record<string, HTMLElement> = {};

    const wrapper = el('div', { className: 'arrange-panel' });
    wrapper.appendChild(el('p', {}, 'Drag values to assign abilities'));

    const pool = el('div', { className: 'arrange-pool' });
    values.forEach((v) => {
      const chip = el('div', { className: 'arrange-chip', draggable: 'true' }, String(v));
      chip.dataset.value = String(v);
      chip.addEventListener('dragstart', (e) => {
        (e as DragEvent).dataTransfer?.setData('text/plain', String(v));
      });
      pool.appendChild(chip);
    });

    const abilitySlots = el('div', { className: 'arrange-slots' });
    this.options.abilities.forEach((ability) => {
      const slot = el('div', { className: 'arrange-slot' });
      slot.dataset.ability = ability;
      slot.appendChild(el('span', {}, this.abbreviate(ability)));
      const valueEl = el('strong', {}, '-');
      slot.appendChild(valueEl);
      slots[ability] = valueEl;
      slot.addEventListener('dragover', (e) => e.preventDefault());
      slot.addEventListener('drop', (e) => {
        e.preventDefault();
        const value = parseInt((e as DragEvent).dataTransfer?.getData('text/plain') || '0', 10);
        if (!value) return;
        slots[ability].textContent = String(value);
        this.updateArrangement();
      });
      abilitySlots.appendChild(slot);
    });

    wrapper.appendChild(pool);
    wrapper.appendChild(abilitySlots);
    this.arrangeContainer.appendChild(wrapper);
  }

  private updateArrangement() {
    const slots = this.arrangeContainer.querySelectorAll('.arrange-slot');
    const arrangement: Record<string, number> = {};
    let complete = true;
    slots.forEach((s) => {
      const ability = (s as HTMLElement).dataset.ability!;
      const text = s.querySelector('strong')?.textContent || '';
      const value = parseInt(text, 10);
      if (Number.isNaN(value)) {
        complete = false;
      } else {
        arrangement[ability] = value;
      }
    });
    this.arrangement = complete ? arrangement : undefined;
    if (complete) {
      this.rollPreview();
    }
  }

  private async save() {
    if (!this.preview) return;
    this.saveButton.disabled = true;
    this.clearMessage();
    try {
      const req = this.buildRequest();
      const { character } = await createCharacter(req);
      this.onSaved(character);
    } catch (err: any) {
      this.showMessage(this.formatError(err) || 'Save failed.', true);
      this.saveButton.disabled = false;
    }
  }

  private formatError(err: any): string {
    const raw = err?.message || String(err);
    const detailMatch = raw.match(/\{[^}]*"detail"\s*:\s*"([^"]+)"/);
    const detail = detailMatch ? detailMatch[1] : raw;

    const minimumsMatch = detail.match(/does not meet ([^']+)'s ability minimums/);
    if (minimumsMatch) {
      const className = this.titleCase(minimumsMatch[1].replace(/-/g, ' '));
      return `${className} requires higher ability scores than your current rolls provide. Try a different class or rearrange your scores.`;
    }

    if (detail.toLowerCase().includes('may not be')) {
      return 'That ancestry cannot take that combination of classes.';
    }

    if (detail.toLowerCase().includes('ability scores do not meet')) {
      return 'Your rolled scores do not meet the minimum requirements for that ancestry.';
    }

    return detail;
  }

  private showMessage(text: string, error = false) {
    this.messageEl.textContent = text;
    this.messageEl.className = `creator-message ${error ? 'error' : ''}`;
  }

  private clearMessage() {
    this.messageEl.textContent = '';
    this.messageEl.className = 'creator-message';
  }

  private titleCase(str: string) {
    return str.replace(/\b\w/g, (c) => c.toUpperCase());
  }

  private abbreviate(ability: string) {
    return ability.slice(0, 3).toUpperCase();
  }

  destroy() {
    this.root.remove();
  }
}

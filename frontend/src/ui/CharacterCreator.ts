import { CharacterInfo } from './HUD';

const RACES = ['Human', 'Elf', 'Dwarf', 'Halfling'];
const CLASSES = ['Fighter', 'Cleric', 'Magic-User', 'Thief'];

export class CharacterCreator {
  public onCreate: ((char: CharacterInfo) => void) | null = null;
  private root: HTMLElement;
  private preview: HTMLElement;
  private abilityRolls: Record<string, number> = {};

  constructor(container: HTMLElement = document.body) {
    this.root = document.createElement('div');
    this.root.id = 'char-creator';

    const panel = document.createElement('div');
    panel.className = 'creator-panel';

    const title = document.createElement('h1');
    title.textContent = 'Forge Your Hero';
    panel.appendChild(title);

    const subtitle = document.createElement('p');
    subtitle.className = 'subtitle';
    subtitle.textContent = 'Create an OSRIC character to enter the Sanctuary.';
    panel.appendChild(subtitle);

    const form = document.createElement('form');
    form.onsubmit = (e) => {
      e.preventDefault();
      this.submit();
    };

    const nameGroup = this.createInputGroup('Name', 'name', 'text', 'Hero');
    form.appendChild(nameGroup);

    const raceGroup = this.createSelectGroup('Race', 'race', RACES);
    form.appendChild(raceGroup);

    const classGroup = this.createSelectGroup('Class', 'class', CLASSES);
    form.appendChild(classGroup);

    this.preview = document.createElement('div');
    this.preview.className = 'ability-preview';
    panel.appendChild(this.preview);

    const rerollBtn = document.createElement('button');
    rerollBtn.type = 'button';
    rerollBtn.className = 'reroll';
    rerollBtn.textContent = 'Re-roll Abilities';
    rerollBtn.onclick = () => this.rollAbilities();
    panel.appendChild(rerollBtn);

    const submitBtn = document.createElement('button');
    submitBtn.type = 'submit';
    submitBtn.className = 'enter';
    submitBtn.textContent = 'Enter Sanctuary';
    form.appendChild(submitBtn);

    panel.appendChild(form);
    this.root.appendChild(panel);
    container.appendChild(this.root);

    this.rollAbilities();

    const raceSelect = form.querySelector('#race') as HTMLSelectElement;
    const classSelect = form.querySelector('#class') as HTMLSelectElement;
    raceSelect.addEventListener('change', () => this.updatePreview());
    classSelect.addEventListener('change', () => this.updatePreview());
  }

  private createInputGroup(label: string, id: string, type: string, placeholder: string): HTMLElement {
    const group = document.createElement('div');
    group.className = 'form-group';
    const lbl = document.createElement('label');
    lbl.htmlFor = id;
    lbl.textContent = label;
    const input = document.createElement('input');
    input.id = id;
    input.type = type;
    input.placeholder = placeholder;
    input.required = true;
    input.maxLength = 24;
    group.appendChild(lbl);
    group.appendChild(input);
    return group;
  }

  private createSelectGroup(label: string, id: string, options: string[]): HTMLElement {
    const group = document.createElement('div');
    group.className = 'form-group';
    const lbl = document.createElement('label');
    lbl.htmlFor = id;
    lbl.textContent = label;
    const select = document.createElement('select');
    select.id = id;
    for (const opt of options) {
      const option = document.createElement('option');
      option.value = opt;
      option.textContent = opt;
      select.appendChild(option);
    }
    group.appendChild(lbl);
    group.appendChild(select);
    return group;
  }

  private rollAbilities() {
    const roll = () => Math.floor(Math.random() * 16) + 3; // 3-18
    this.abilityRolls = {
      str: roll(),
      dex: roll(),
      con: roll(),
      int: roll(),
      wis: roll(),
      cha: roll(),
    };
    this.updatePreview();
  }

  private racialMod(race: string, ability: string): number {
    const mods: Record<string, Record<string, number>> = {
      Elf: { dex: 1, con: -1 },
      Dwarf: { con: 1, cha: -1 },
      Halfling: { dex: 1, str: -1 },
      Human: {},
    };
    return mods[race]?.[ability] || 0;
  }

  private updatePreview() {
    const race = (this.root.querySelector('#race') as HTMLSelectElement).value;
    const cls = (this.root.querySelector('#class') as HTMLSelectElement).value;

    const abilities: Record<string, number> = {};
    for (const [k, v] of Object.entries(this.abilityRolls)) {
      abilities[k] = Math.max(3, Math.min(18, v + this.racialMod(race, k)));
    }

    const con = abilities.con;
    const dex = abilities.dex;
    const conMod = Math.floor((con - 10) / 2);
    const dexMod = Math.floor((dex - 10) / 2);
    const hitDice: Record<string, number> = { Fighter: 8, Cleric: 6, 'Magic-User': 4, Thief: 6 };
    const hd = hitDice[cls] || 6;
    const maxHp = Math.max(1, Math.floor(Math.random() * hd) + 1 + conMod);
    const ac = 10 + dexMod;

    this.preview.innerHTML = `
      <div class="abilities-grid">
        ${Object.entries(abilities)
          .map(([k, v]) => {
            const mod = Math.floor((v - 10) / 2);
            const sign = mod >= 0 ? '+' : '';
            return `<div><span>${k.toUpperCase()}</span><strong>${v}</strong><small>${sign}${mod}</small></div>`;
          })
          .join('')}
      </div>
      <div class="derived">
        <span>HP ${maxHp}</span>
        <span>AC ${ac}</span>
      </div>
    `;
  }

  private submit() {
    const name = (this.root.querySelector('#name') as HTMLInputElement).value.trim() || 'Hero';
    const race = (this.root.querySelector('#race') as HTMLSelectElement).value;
    const cls = (this.root.querySelector('#class') as HTMLSelectElement).value;

    const abilities: Record<string, number> = {};
    for (const [k, v] of Object.entries(this.abilityRolls)) {
      abilities[k] = Math.max(3, Math.min(18, v + this.racialMod(race, k)));
    }

    const con = abilities.con;
    const dex = abilities.dex;
    const conMod = Math.floor((con - 10) / 2);
    const dexMod = Math.floor((dex - 10) / 2);
    const hitDice: Record<string, number> = { Fighter: 8, Cleric: 6, 'Magic-User': 4, Thief: 6 };
    const hd = hitDice[cls] || 6;
    const maxHp = Math.max(1, Math.floor(Math.random() * hd) + 1 + conMod);

    const char: CharacterInfo = {
      name,
      race,
      class: cls,
      level: 1,
      hp: maxHp,
      max_hp: maxHp,
      ac: 10 + dexMod,
      abilities,
    };

    if (this.onCreate) {
      this.onCreate(char);
    }
  }

  destroy() {
    this.root.remove();
  }
}

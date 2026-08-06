import { buyItem, CharacterState, equipItem, Item, useItem } from '../net/api';
import { el, clear } from './utils';

export class CharacterSheet {
  private root: HTMLElement;
  private character: CharacterState;
  private onClose: () => void;
  private overlay: HTMLElement;

  constructor(container: HTMLElement, character: CharacterState, onClose: () => void) {
    this.root = container;
    this.character = character;
    this.onClose = onClose;

    this.overlay = el('div', { className: 'character-sheet-overlay' });
    const panel = el('div', { className: 'character-sheet-panel' });
    panel.appendChild(this.buildHeader());
    panel.appendChild(this.buildStats());
    panel.appendChild(this.buildEquipment());
    panel.appendChild(this.buildInventory());
    panel.appendChild(this.buildShop());

    const closeBtn = el('button', { className: 'enter', onclick: () => this.close() }, 'Close');
    panel.appendChild(closeBtn);

    this.overlay.appendChild(panel);
    this.overlay.addEventListener('click', (e) => {
      if (e.target === this.overlay) this.close();
    });
    this.root.appendChild(this.overlay);
  }

  private buildHeader() {
    const c = this.character;
    const header = el('div', { className: 'sheet-header' });
    header.appendChild(el('h1', {}, c.name));
    header.appendChild(
      el('p', { className: 'subtitle' }, `${this.titleCase(c.ancestry)} ${c.classes.map((x) => this.titleCase(x)).join('/')}`)
    );
    return header;
  }

  private buildStats() {
    const c = this.character;
    const grid = el('div', { className: 'sheet-stats' });
    grid.appendChild(this.statBox('Level', String(c.level ?? 1)));
    grid.appendChild(this.statBox('XP', String(c.xp ?? 0)));
    grid.appendChild(this.statBox('Gold', String(c.gold ?? 0)));
    grid.appendChild(this.statBox('HP', `${c.hit_points}/${c.max_hp}`));
    grid.appendChild(this.statBox('AC', String(c.armour_class)));
    return grid;
  }

  private statBox(label: string, value: string) {
    const box = el('div', { className: 'sheet-stat-box' });
    box.appendChild(el('span', {}, label));
    box.appendChild(el('strong', {}, value));
    return box;
  }

  private buildEquipment() {
    const equipment = this.character.equipment || {};
    const section = el('div', { className: 'sheet-section' });
    section.appendChild(el('h2', {}, 'Equipped'));
    const list = el('ul', { className: 'sheet-list' });
    const slots = Object.keys(equipment);
    if (slots.length === 0) {
      list.appendChild(el('li', { className: 'empty' }, 'Nothing equipped.'));
    } else {
      slots.forEach((slot) => {
        const item = equipment[slot];
        list.appendChild(el('li', {}, `${this.titleCase(slot)}: ${item.name}`));
      });
    }
    section.appendChild(list);
    return section;
  }

  private buildInventory() {
    const inventory = this.character.inventory || [];
    const section = el('div', { className: 'sheet-section' });
    section.appendChild(el('h2', {}, 'Inventory'));
    const list = el('ul', { className: 'sheet-list' });
    if (inventory.length === 0) {
      list.appendChild(el('li', { className: 'empty' }, 'No items.'));
    } else {
      inventory.forEach((item) => {
        const li = el('li', { className: 'sheet-item' });
        li.appendChild(el('span', {}, item.name));
        const actions = el('div', { className: 'sheet-item-actions' });
        if (item.slot && item.slot !== 'consumable') {
          actions.appendChild(
            el('button', { onclick: () => this.doEquip(item) }, 'Equip')
          );
        }
        if (item.slot === 'consumable') {
          actions.appendChild(
            el('button', { onclick: () => this.doUse(item) }, 'Use')
          );
        }
        li.appendChild(actions);
        list.appendChild(li);
      });
    }
    section.appendChild(list);
    return section;
  }

  private async doEquip(item: Item) {
    if (!this.character.id) return;
    try {
      const { character } = await equipItem(this.character.id, item.instance_id);
      this.character = character;
      this.refresh();
    } catch (err: any) {
      alert(err.message || 'Equip failed');
    }
  }

  private async doUse(item: Item) {
    if (!this.character.id) return;
    try {
      const { character, restored } = await useItem(this.character.id, item.instance_id);
      this.character = character;
      this.refresh();
      if (restored) {
        alert(`Restored ${restored} HP.`);
      }
    } catch (err: any) {
      alert(err.message || 'Use failed');
    }
  }

  private buildShop() {
    const section = el('div', { className: 'sheet-section' });
    section.appendChild(el('h2', {}, 'Shop'));
    const row = el('div', { className: 'sheet-shop-row' });
    const gold = this.character.gold ?? 0;
    const canAfford = gold >= 15;
    const buyBtn = el(
      'button',
      {
        disabled: !canAfford,
        onclick: () => this.doBuy(),
      },
      'Buy Potion (15g)'
    );
    row.appendChild(buyBtn);
    row.appendChild(el('span', { className: 'sheet-shop-gold' }, `${gold}g`));
    section.appendChild(row);
    return section;
  }

  private async doBuy() {
    if (!this.character.id) return;
    try {
      const { character } = await buyItem(this.character.id, 'healing_potion', 15);
      this.character = character;
      this.refresh();
    } catch (err: any) {
      alert(err.message || 'Buy failed');
    }
  }

  private refresh() {
    clear(this.overlay);
    const panel = el('div', { className: 'character-sheet-panel' });
    panel.appendChild(this.buildHeader());
    panel.appendChild(this.buildStats());
    panel.appendChild(this.buildEquipment());
    panel.appendChild(this.buildInventory());
    panel.appendChild(this.buildShop());
    const closeBtn = el('button', { className: 'enter', onclick: () => this.close() }, 'Close');
    panel.appendChild(closeBtn);
    this.overlay.appendChild(panel);
  }

  private close() {
    this.overlay.remove();
    this.onClose();
  }

  private titleCase(str: string) {
    return str.replace(/\b\w/g, (c) => c.toUpperCase());
  }
}

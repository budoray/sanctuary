import { el, clear } from './utils';

const COMMON_ROLLS = [
  { label: 'd4', expr: '1d4' },
  { label: 'd6', expr: '1d6' },
  { label: 'd8', expr: '1d8' },
  { label: 'd10', expr: '1d10' },
  { label: 'd12', expr: '1d12' },
  { label: 'd20', expr: '1d20' },
  { label: 'd100', expr: '1d100' },
];

interface TrayRoll {
  expr: string;
  total: number;
  timestamp: Date;
}

export class DiceTray {
  private root: HTMLElement;
  private history: HTMLElement;
  private rolls: TrayRoll[] = [];
  private onRoll?: (expr: string) => Promise<number>;

  constructor(container: HTMLElement, onRoll?: (expr: string) => Promise<number>) {
    this.onRoll = onRoll;
    this.root = el('div', { className: 'dice-tray' });
    const header = el('div', { className: 'tray-header' }, 'Dice Tray');
    const controls = this.buildControls();
    this.history = el('div', { className: 'tray-history' });
    this.root.appendChild(header);
    this.root.appendChild(controls);
    this.root.appendChild(this.history);
    container.appendChild(this.root);
    this.renderHistory();
  }

  private buildControls() {
    const controls = el('div', { className: 'tray-controls' });

    const quickButtons = el('div', { className: 'tray-quick' });
    COMMON_ROLLS.forEach(({ label, expr }) => {
      const btn = el('button', { className: 'tray-die', onclick: () => this.roll(expr) }, label);
      quickButtons.appendChild(btn);
    });

    const custom = el('div', { className: 'tray-custom' });
    const input = el('input', {
      type: 'text',
      placeholder: 'e.g. 3d6, 2d8+3',
      onkeydown: (e: KeyboardEvent) => {
        if (e.key === 'Enter') {
          const value = (input as HTMLInputElement).value.trim();
          if (value) {
            this.roll(value);
            (input as HTMLInputElement).value = '';
          }
        }
      },
    }) as HTMLInputElement;
    const rollBtn = el('button', { onclick: () => {
      const value = input.value.trim();
      if (value) {
        this.roll(value);
        input.value = '';
      }
    } }, 'Roll');
    custom.appendChild(input);
    custom.appendChild(rollBtn);

    controls.appendChild(quickButtons);
    controls.appendChild(custom);
    return controls;
  }

  async roll(expr: string) {
    let total: number;
    try {
      if (this.onRoll) {
        total = await this.onRoll(expr);
      } else {
        total = this.evaluateLocal(expr);
      }
    } catch (err) {
      this.addHistory({ expr, total: NaN, timestamp: new Date() });
      return;
    }
    this.addHistory({ expr, total, timestamp: new Date() });
  }

  private evaluateLocal(expr: string): number {
    const normalized = expr.replace(/\s/g, '').toLowerCase();
    const parts = normalized.split(/(?=[+-])/);
    let total = 0;
    for (const part of parts) {
      if (part.includes('d')) {
        const [countStr, facesStr] = part.split('d');
        const count = countStr === '' ? 1 : parseInt(countStr, 10);
        const faces = parseInt(facesStr, 10);
        if (Number.isNaN(count) || Number.isNaN(faces)) throw new Error('bad dice');
        for (let i = 0; i < count; i++) {
          total += Math.floor(Math.random() * faces) + 1;
        }
      } else {
        total += parseInt(part, 10) || 0;
      }
    }
    return total;
  }

  private addHistory(roll: TrayRoll) {
    this.rolls.unshift(roll);
    if (this.rolls.length > 50) this.rolls.pop();
    this.renderHistory();
  }

  private renderHistory() {
    clear(this.history);
    if (this.rolls.length === 0) {
      this.history.appendChild(el('div', { className: 'tray-empty' }, 'Rolls appear here'));
      return;
    }
    this.rolls.forEach((r) => {
      const value = Number.isNaN(r.total) ? '?' : String(r.total);
      const item = el('div', { className: 'tray-roll' });
      item.appendChild(el('span', { className: 'tray-expr' }, r.expr));
      item.appendChild(el('span', { className: 'tray-total' }, value));
      this.history.appendChild(item);
    });
  }

  destroy() {
    this.root.remove();
  }
}

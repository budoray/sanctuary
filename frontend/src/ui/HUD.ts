export class HUD {
  private root: HTMLElement;
  private titleEl: HTMLHeadingElement;
  private userEl: HTMLParagraphElement;
  private sessionEl: HTMLParagraphElement;
  private turnEl: HTMLParagraphElement;
  private statusEl: HTMLParagraphElement;
  private logEl: HTMLDivElement;

  constructor(container: HTMLElement = document.body) {
    this.root = document.createElement('div');
    this.root.id = 'hud';

    this.titleEl = document.createElement('h1');
    this.titleEl.textContent = 'Sanctuary';
    this.root.appendChild(this.titleEl);

    this.userEl = document.createElement('p');
    this.userEl.textContent = 'User: —';
    this.root.appendChild(this.userEl);

    this.sessionEl = document.createElement('p');
    this.sessionEl.textContent = 'Session: —';
    this.root.appendChild(this.sessionEl);

    this.turnEl = document.createElement('p');
    this.turnEl.textContent = 'Turn: —';
    this.root.appendChild(this.turnEl);

    this.statusEl = document.createElement('p');
    this.statusEl.className = 'status';
    this.statusEl.textContent = 'Click a tile to move the Hero.';
    this.root.appendChild(this.statusEl);

    this.logEl = document.createElement('div');
    this.logEl.id = 'combat-log';
    this.root.appendChild(this.logEl);

    container.appendChild(this.root);
  }

  setUser(name: string, id: number | null) {
    this.userEl.textContent = `User: ${name}${id ? ` (#${id})` : ''}`;
  }

  setSession(id: string) {
    this.sessionEl.textContent = `Session: ${id}`;
  }

  setTurn(turn: number, phase: string) {
    this.turnEl.textContent = `Turn ${turn} — ${phase === 'player' ? 'Your move' : "DM's move"}`;
  }

  setStatus(text: string) {
    this.statusEl.textContent = text;
  }

  addLog(entry: string) {
    const p = document.createElement('p');
    p.className = 'log-entry';
    p.textContent = entry;
    this.logEl.appendChild(p);
    this.logEl.scrollTop = this.logEl.scrollHeight;
  }

  clearLog() {
    this.logEl.innerHTML = '';
  }
}

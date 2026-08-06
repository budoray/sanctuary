export interface CharacterInfo {
  id?: string;
  name: string;
  race: string;
  class: string;
  level: number;
  hp: number;
  max_hp: number;
  ac: number;
  abilities: Record<string, number>;
}

export class HUD {
  private root: HTMLElement;
  private header: HTMLElement;
  private userEl: HTMLElement;
  private sessionEl: HTMLElement;
  private turnEl: HTMLElement;
  private statusEl: HTMLElement;
  private charSheet: HTMLElement;
  private logEl: HTMLElement;
  private actionBar: HTMLElement;

  constructor(container: HTMLElement = document.body) {
    this.root = document.createElement('div');
    this.root.id = 'hud';

    this.header = document.createElement('header');
    const title = document.createElement('h1');
    title.textContent = 'Sanctuary';
    this.userEl = document.createElement('p');
    this.userEl.className = 'user';
    this.userEl.textContent = 'User: —';
    this.sessionEl = document.createElement('p');
    this.sessionEl.className = 'session';
    this.sessionEl.textContent = 'Session: —';
    this.header.appendChild(title);
    this.header.appendChild(this.userEl);
    this.header.appendChild(this.sessionEl);
    this.root.appendChild(this.header);

    this.turnEl = document.createElement('p');
    this.turnEl.className = 'turn';
    this.turnEl.textContent = 'Turn: —';
    this.root.appendChild(this.turnEl);

    this.statusEl = document.createElement('p');
    this.statusEl.className = 'status';
    this.statusEl.textContent = 'Initializing...';
    this.root.appendChild(this.statusEl);

    this.charSheet = document.createElement('div');
    this.charSheet.className = 'char-sheet';
    this.root.appendChild(this.charSheet);

    const logHeader = document.createElement('h2');
    logHeader.textContent = 'Chronicle';
    this.root.appendChild(logHeader);

    this.logEl = document.createElement('div');
    this.logEl.id = 'combat-log';
    this.root.appendChild(this.logEl);

    container.appendChild(this.root);

    this.actionBar = document.createElement('div');
    this.actionBar.id = 'action-bar';
    container.appendChild(this.actionBar);
  }

  setUser(name: string, id: number | null) {
    this.userEl.textContent = `User: ${name}${id ? ` #${id}` : ''}`;
  }

  setSession(id: string) {
    this.sessionEl.textContent = `Session: ${id}`;
  }

  setTurn(turn: number, phase: string) {
    this.turnEl.textContent = `Turn ${turn} — ${phase === 'player' ? 'Your Move' : "DM's Move"}`;
    this.turnEl.className = `turn ${phase}`;
  }

  setStatus(text: string) {
    this.statusEl.textContent = text;
  }

  setCharacter(info: CharacterInfo | null) {
    this.charSheet.innerHTML = '';
    if (!info) {
      this.charSheet.textContent = 'No character';
      return;
    }

    const header = document.createElement('div');
    header.className = 'char-header';
    header.innerHTML = `<strong>${info.name}</strong> <span>${info.race} ${info.class} ${info.level}</span>`;
    this.charSheet.appendChild(header);

    const stats = document.createElement('div');
    stats.className = 'stats';
    const hpPct = info.max_hp > 0 ? (info.hp / info.max_hp) * 100 : 0;
    stats.innerHTML = `
      <div class="stat"><span>HP</span><div class="hp-bar"><div style="width:${hpPct}%"></div></div><span>${info.hp}/${info.max_hp}</span></div>
      <div class="stat"><span>AC</span><strong>${info.ac}</strong></div>
      <div class="stat abilities">
        ${Object.entries(info.abilities)
          .map(([k, v]) => `<span title="${k.toUpperCase()}">${k.slice(0, 3).toUpperCase()} ${v}</span>`)
          .join('')}
      </div>
    `;
    this.charSheet.appendChild(stats);
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

  setActions(actions: { id: string; label: string; disabled?: boolean; onClick: () => void }[]) {
    this.actionBar.innerHTML = '';
    for (const action of actions) {
      const btn = document.createElement('button');
      btn.textContent = action.label;
      btn.disabled = !!action.disabled;
      btn.onclick = action.onClick;
      this.actionBar.appendChild(btn);
    }
  }
}

export interface SessionSummary {
  session_id: string;
  turn: number;
  phase: string;
  module_id: string;
  hero_name: string;
}

export class SessionSelect {
  public onResume: ((sessionId: string) => void) | null = null;
  public onNew: (() => void) | null = null;
  private root: HTMLElement;

  constructor(sessions: SessionSummary[], container: HTMLElement = document.body) {
    this.root = document.createElement('div');
    this.root.id = 'session-select';

    const panel = document.createElement('div');
    panel.className = 'session-panel';

    const title = document.createElement('h1');
    title.textContent = 'Sanctuary';
    panel.appendChild(title);

    const subtitle = document.createElement('p');
    subtitle.className = 'subtitle';
    subtitle.textContent = 'Choose an adventure to resume, or begin anew.';
    panel.appendChild(subtitle);

    const list = document.createElement('ul');
    list.className = 'session-list';
    for (const s of sessions) {
      const li = document.createElement('li');
      li.innerHTML = `
        <div class="session-info">
          <strong>${s.hero_name}</strong>
          <span>Turn ${s.turn} — ${s.phase === 'player' ? 'Your Move' : "DM's Move"}</span>
        </div>
        <span class="session-id">${s.session_id}</span>
      `;
      li.onclick = () => {
        if (this.onResume) this.onResume(s.session_id);
      };
      list.appendChild(li);
    }
    panel.appendChild(list);

    const newBtn = document.createElement('button');
    newBtn.className = 'enter';
    newBtn.textContent = 'New Adventure';
    newBtn.onclick = () => {
      if (this.onNew) this.onNew();
    };
    panel.appendChild(newBtn);

    this.root.appendChild(panel);
    container.appendChild(this.root);
  }

  destroy() {
    this.root.remove();
  }
}

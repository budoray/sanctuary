export class HUD {
  private root: HTMLElement;
  private titleEl: HTMLHeadingElement;
  private sessionEl: HTMLParagraphElement;
  private statusEl: HTMLParagraphElement;

  constructor(container: HTMLElement = document.body) {
    this.root = document.createElement('div');
    this.root.id = 'hud';

    this.titleEl = document.createElement('h1');
    this.titleEl.textContent = 'Sanctuary';
    this.root.appendChild(this.titleEl);

    this.sessionEl = document.createElement('p');
    this.sessionEl.textContent = 'Session: —';
    this.root.appendChild(this.sessionEl);

    this.statusEl = document.createElement('p');
    this.statusEl.className = 'status';
    this.statusEl.textContent = 'Click a tile to move the Hero.';
    this.root.appendChild(this.statusEl);

    container.appendChild(this.root);
  }

  setSession(id: string) {
    this.sessionEl.textContent = `Session: ${id}`;
  }

  setStatus(text: string) {
    this.statusEl.textContent = text;
  }
}

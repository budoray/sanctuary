export class GameOver {
  public onRestart: (() => void) | null = null;
  private root: HTMLElement;

  constructor(message: string, container: HTMLElement = document.body) {
    this.root = document.createElement('div');
    this.root.id = 'game-over';

    const panel = document.createElement('div');
    panel.className = 'game-over-panel';

    const title = document.createElement('h1');
    title.textContent = 'You Have Fallen';
    panel.appendChild(title);

    const msg = document.createElement('p');
    msg.className = 'message';
    msg.textContent = message;
    panel.appendChild(msg);

    const btn = document.createElement('button');
    btn.className = 'enter';
    btn.textContent = 'Begin Anew';
    btn.onclick = () => {
      if (this.onRestart) this.onRestart();
    };
    panel.appendChild(btn);

    this.root.appendChild(panel);
    container.appendChild(this.root);
  }

  destroy() {
    this.root.remove();
  }
}

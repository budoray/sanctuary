import { CharacterState, whoami } from '../net/api';
import { CharacterCreator } from './character-creator';
import { CharacterSelect } from './character-select';
import { clear } from './utils';

type Screen = 'loading' | 'select' | 'create' | 'game';

export class SanctuaryApp {
  private app: HTMLElement;
  private current: CharacterCreator | CharacterSelect | null = null;

  constructor(app: HTMLElement) {
    this.app = app;
  }

  async start() {
    try {
      const user = await whoami();
      document.body.dataset.user = user.user.name || 'player';
    } catch {
      // whoami will redirect to login if not authenticated
      return;
    }
    this.showSelect();
  }

  private setScreen(name: Screen) {
    document.body.dataset.screen = name;
  }

  private showSelect() {
    this.setScreen('select');
    clear(this.app);
    this.current?.destroy();
    this.current = new CharacterSelect(
      this.app,
      (character) => this.enterGame(character),
      () => this.showCreate()
    );
  }

  private showCreate() {
    this.setScreen('create');
    clear(this.app);
    this.current?.destroy();
    this.current = new CharacterCreator(this.app, (character) => {
      this.enterGame(character);
    });
  }

  private enterGame(character: CharacterState) {
    this.setScreen('game');
    clear(this.app);
    this.current?.destroy();
    this.current = null;

    const placeholder = document.createElement('div');
    placeholder.className = 'placeholder-panel';
    placeholder.innerHTML = `
      <h1>Sanctuary</h1>
      <p>${character.name} enters the realm.</p>
      <p class="muted">The dungeon engine is being rebuilt. Your character is saved and will be here when the adventure opens.</p>
      <footer class="licence">
        Sanctuary is an independent product published under the OSRIC 3.0 Third-Party License
        and is not affiliated with Mythmere Games LLC.
      </footer>
    `;
    this.app.appendChild(placeholder);

    const back = document.createElement('button');
    back.textContent = 'Back to Characters';
    back.style.position = 'absolute';
    back.style.bottom = '24px';
    back.style.left = '50%';
    back.style.transform = 'translateX(-50%)';
    back.style.zIndex = '100';
    back.onclick = () => this.showSelect();
    this.app.appendChild(back);
  }
}

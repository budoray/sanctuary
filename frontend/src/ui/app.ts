import { CharacterState, createSession, getModule, whoami } from '../net/api';
import { CharacterCreator } from './character-creator';
import { CharacterSelect } from './character-select';
import { Game } from './game';
import { clear } from './utils';

type Screen = 'loading' | 'select' | 'create' | 'game';

export class SanctuaryApp {
  private app: HTMLElement;
  private current: CharacterCreator | CharacterSelect | Game | null = null;

  constructor(app: HTMLElement) {
    this.app = app;
  }

  async start() {
    try {
      const user = await whoami();
      document.body.dataset.user = user.user.name || 'player';
    } catch {
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

  private async enterGame(character: CharacterState) {
    if (!character.id) return;
    this.setScreen('loading');
    clear(this.app);
    this.current?.destroy();

    try {
      const { session } = await createSession(character.id);
      const { module } = await getModule(session.module_id);
      this.setScreen('game');
      this.current = new Game(
        this.app,
        session.id,
        module.map,
        session,
        () => this.showSelect()
      );
    } catch (err: any) {
      this.setScreen('select');
      this.showSelect();
      // eslint-disable-next-line no-console
      console.error('Failed to enter game:', err);
    }
  }
}

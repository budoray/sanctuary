import { CampaignLobby } from './campaign-lobby';
import { Campaign, CharacterState, createSession, getModule, listSessions, whoami } from '../net/api';
import { CharacterCreator } from './character-creator';
import { CharacterSelect } from './character-select';
import { Game } from './game';
import { SessionSelect } from './session-select';
import { clear } from './utils';

type Screen = 'loading' | 'select' | 'create' | 'campaigns' | 'sessions' | 'game';

export class SanctuaryApp {
  private app: HTMLElement;
  private current: CharacterCreator | CharacterSelect | CampaignLobby | SessionSelect | Game | null = null;

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

    try {
      const { sessions } = await listSessions();
      const active = sessions.filter((s) => s.status === 'active');
      if (active.length > 0) {
        this.showSessions();
      } else {
        this.showSelect();
      }
    } catch {
      this.showSelect();
    }
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
      (character, timerSeconds) => this.enterGame(character, undefined, timerSeconds),
      () => this.showCreate(),
      () => this.showCampaigns(),
      () => this.showSessions()
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

  private showCampaigns() {
    this.setScreen('campaigns');
    clear(this.app);
    this.current?.destroy();
    this.current = new CampaignLobby(
      this.app,
      (campaign) => {
        this.showSelectForCampaign(campaign);
      },
      () => this.showSelect()
    );
  }

  private showSelectForCampaign(campaign: Campaign) {
    this.setScreen('select');
    clear(this.app);
    this.current?.destroy();
    this.current = new CharacterSelect(
      this.app,
      (character, timerSeconds) => this.enterGame(character, campaign.id, timerSeconds),
      () => this.showCreate(),
      () => this.showCampaigns(),
      () => this.showSessions()
    );
  }

  private showSessions() {
    this.setScreen('sessions');
    clear(this.app);
    this.current?.destroy();
    this.current = new SessionSelect(
      this.app,
      (session) => this.resumeGame(session),
      () => this.showSelect()
    );
  }

  private async resumeGame(session: import('../net/api').GameSession) {
    this.setScreen('loading');
    clear(this.app);
    this.current?.destroy();

    try {
      const { module } = await getModule(session.module_id);
      this.setScreen('game');
      const game = new Game(
        this.app,
        session.id,
        module.map,
        session,
        () => this.showSelect()
      );
      this.current = game;
      await game.init();
    } catch (err: any) {
      this.setScreen('select');
      this.showSelect();
      // eslint-disable-next-line no-console
      console.error('Failed to resume game:', err);
    }
  }

  private async enterGame(character: CharacterState, campaignId?: string, turnTimerSeconds = 0) {
    if (!character.id) return;
    this.setScreen('loading');
    clear(this.app);
    this.current?.destroy();

    try {
      const { session } = await createSession(character.id, 'sample_lair', campaignId, turnTimerSeconds);
      const { module } = await getModule(session.module_id);
      this.setScreen('game');
      const game = new Game(
        this.app,
        session.id,
        module.map,
        session,
        () => this.showSelect()
      );
      this.current = game;
      await game.init();
    } catch (err: any) {
      this.setScreen('select');
      this.showSelect();
      // eslint-disable-next-line no-console
      console.error('Failed to enter game:', err);
    }
  }
}

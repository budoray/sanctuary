import { CampaignLobby } from './campaign-lobby';
import { CampaignDetail } from './campaign-detail';
import { Campaign, CharacterState, createSession, getModule, getSession, listSessions, whoami } from '../net/api';
import { CharacterCreator } from './character-creator';
import { CharacterSelect } from './character-select';
import { Game } from './game';
import { SessionSelect } from './session-select';
import { clear } from './utils';

type Screen = 'loading' | 'select' | 'create' | 'campaigns' | 'sessions' | 'game';

export class SanctuaryApp {
  private app: HTMLElement;
  private userId: number | null = null;
  private current: CharacterCreator | CharacterSelect | CampaignLobby | CampaignDetail | SessionSelect | Game | null = null;

  constructor(app: HTMLElement) {
    this.app = app;
  }

  async start() {
    try {
      const user = await whoami();
      this.userId = user.user.id ?? null;
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
      (character, timerSeconds, moduleId) => this.enterGame(character, undefined, timerSeconds, moduleId),
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
        this.showCampaignDetail(campaign);
      },
      () => this.showSelect()
    );
  }

  private showCampaignDetail(campaign: Campaign) {
    this.setScreen('campaigns');
    clear(this.app);
    this.current?.destroy();
    this.current = new CampaignDetail(
      this.app,
      campaign,
      (c) => this.showSelectForCampaign(c),
      async (s) => {
        try {
          const { session } = await getSession(s.id);
          this.resumeGame(session);
        } catch (err: any) {
          // eslint-disable-next-line no-console
          console.error('Failed to load joined session:', err);
          this.showCampaigns();
        }
      },
      () => this.showCampaigns()
    );
  }

  private showSelectForCampaign(campaign: Campaign) {
    this.setScreen('select');
    clear(this.app);
    this.current?.destroy();
    this.current = new CharacterSelect(
      this.app,
      (character, timerSeconds, _moduleId) => this.enterGame(character, campaign.id, timerSeconds),
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
        () => this.showSessions(),
        (characterId) => this.replayGame(characterId),
        this.userId ?? undefined
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

  private async replayGame(characterId: string) {
    this.setScreen('loading');
    clear(this.app);
    this.current?.destroy();

    try {
      const { session } = await createSession(characterId, 'sample_lair');
      const { module } = await getModule(session.module_id);
      this.setScreen('game');
      const game = new Game(
        this.app,
        session.id,
        module.map,
        session,
        () => this.showSessions(),
        (cid) => this.replayGame(cid),
        this.userId ?? undefined
      );
      this.current = game;
      await game.init();
    } catch (err: any) {
      this.setScreen('select');
      this.showSelect();
      // eslint-disable-next-line no-console
      console.error('Failed to replay game:', err);
    }
  }

  private async enterGame(character: CharacterState, campaignId?: string, turnTimerSeconds = 0, moduleId = 'sample_lair') {
    if (!character.id) return;
    this.setScreen('loading');
    clear(this.app);
    this.current?.destroy();

    try {
      const { session } = await createSession(character.id, moduleId, campaignId, turnTimerSeconds);
      const { module } = await getModule(session.module_id);
      this.setScreen('game');
      const game = new Game(
        this.app,
        session.id,
        module.map,
        session,
        () => this.showSessions(),
        (characterId) => this.replayGame(characterId),
        this.userId ?? undefined
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

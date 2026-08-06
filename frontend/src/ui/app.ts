import { CampaignLobby } from './campaign-lobby';
import { Campaign, CharacterState, createSession, getModule, whoami } from '../net/api';
import { CharacterCreator } from './character-creator';
import { CharacterSelect } from './character-select';
import { Game } from './game';
import { clear } from './utils';

type Screen = 'loading' | 'select' | 'create' | 'campaigns' | 'game';

export class SanctuaryApp {
  private app: HTMLElement;
  private current: CharacterCreator | CharacterSelect | CampaignLobby | Game | null = null;

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
      () => this.showCreate(),
      () => this.showCampaigns()
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
      (character) => this.enterGame(character, campaign.id),
      () => this.showCreate(),
      () => this.showCampaigns()
    );
  }

  private async enterGame(character: CharacterState, campaignId?: string) {
    if (!character.id) return;
    this.setScreen('loading');
    clear(this.app);
    this.current?.destroy();

    try {
      const { session } = await createSession(character.id, 'sample_lair', campaignId);
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

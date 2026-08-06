import { Container, Graphics, Text } from 'pixi.js';
import { Token } from '../net/api';

export class TokenSprite {
  readonly container: Container;
  private body: Graphics;
  private label: Text;
  private hpBar: Graphics;
  private hpFill: Graphics;
  private tileSize: number;
  targetX = 0;
  targetY = 0;

  constructor(token: Token, tileSize: number) {
    this.tileSize = tileSize;
    this.container = new Container();
    this.container.x = token.x * tileSize;
    this.container.y = token.y * tileSize;
    this.targetX = this.container.x;
    this.targetY = this.container.y;

    this.body = new Graphics();
    this.body.rect(4, 4, tileSize - 8, tileSize - 8);
    this.body.fill({ color: parseInt(token.color.replace('#', ''), 16) });
    this.container.addChild(this.body);

    this.label = new Text({
      text: token.name,
      style: { fontSize: 10, fill: 0xffffff, align: 'center' },
    });
    this.label.anchor.set(0.5, 1);
    this.label.x = tileSize / 2;
    this.label.y = 2;
    this.container.addChild(this.label);

    const barW = tileSize - 8;
    this.hpBar = new Graphics();
    this.hpBar.rect(4, -6, barW, 4);
    this.hpBar.fill({ color: 0x000000 });
    this.container.addChild(this.hpBar);

    this.hpFill = new Graphics();
    this.updateHP(token.hp, token.max_hp);
    this.container.addChild(this.hpFill);
  }

  updateHP(hp: number, maxHp: number) {
    const ratio = Math.max(0, Math.min(1, hp / maxHp));
    const barW = this.tileSize - 8;
    this.hpFill.clear();
    this.hpFill.rect(4, -6, barW * ratio, 4);
    this.hpFill.fill({
      color: ratio > 0.5 ? 0x2ecc71 : ratio > 0.25 ? 0xf1c40f : 0xc0392b,
    });
  }

  setTarget(x: number, y: number) {
    this.targetX = x * this.tileSize;
    this.targetY = y * this.tileSize;
  }

  snapToTarget() {
    this.container.x = this.targetX;
    this.container.y = this.targetY;
  }

  destroy() {
    this.container.destroy({ children: true });
  }
}

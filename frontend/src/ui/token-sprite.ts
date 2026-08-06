import { Container, Graphics, Sprite, Text } from 'pixi.js';
import { Token } from '../net/api';
import { tokenFrame } from '../lib/tile-atlas';

interface Floater {
  text: Text;
  life: number;
  maxLife: number;
  vy: number;
}

const TOKEN_COLORS: Record<string, number> = {
  player: 0x3498db,
  fighter: 0x3498db,
  cleric: 0xf1c40f,
  thief: 0x9b59b6,
  magicuser: 0xe74c3c,
  monster: 0x2ecc71,
  goblin: 0x2ecc71,
};

export class TokenSprite {
  readonly container: Container;
  private body: Graphics;
  private shadow: Graphics;
  private detail: Graphics;
  private label: Text;
  private hpBar: Graphics;
  private hpFill: Graphics;
  private tileSize: number;
  private pulse = 0;
  private ring: Graphics;
  private downCross: Graphics;
  private floaters: Floater[] = [];
  targetX = 0;
  targetY = 0;

  constructor(token: Token, tileSize: number) {
    this.tileSize = tileSize;
    this.container = new Container();
    this.container.x = token.x * tileSize;
    this.container.y = token.y * tileSize;
    this.targetX = this.container.x;
    this.targetY = this.container.y;

    const cx = tileSize / 2;
    const cy = tileSize / 2;

    // Active turn ring
    this.ring = new Graphics();
    this.ring.circle(cx, cy, tileSize * 0.46);
    this.ring.stroke({ width: 3, color: 0xf1c40f, alpha: 0.95 });
    this.ring.circle(cx, cy, tileSize * 0.40);
    this.ring.stroke({ width: 1, color: 0xffffff, alpha: 0.6 });
    this.ring.visible = false;
    this.container.addChild(this.ring);

    const pad = 3;
    const size = tileSize - pad * 2;
    const baseColor = this.resolveColor(token);
    const atlasKey = this.resolveAtlasKey(token);
    const atlasTex = atlasKey ? tokenFrame(atlasKey) : null;

    // Drop shadow
    this.shadow = new Graphics();
    this.shadow.ellipse(cx + 2, cy + 4, size * 0.42, size * 0.18);
    this.shadow.fill({ color: 0x000000, alpha: 0.45 });
    this.container.addChild(this.shadow);

    // Body backing: a solid coloured disc so the token is always visible
    const backing = new Graphics();
    backing.circle(cx, cy, size * 0.42);
    backing.fill({ color: baseColor });
    backing.circle(cx, cy, size * 0.42);
    backing.stroke({ width: 2, color: 0xffffff, alpha: 0.35 });
    this.container.addChild(backing);

    // Body
    this.body = new Graphics();
    if (atlasTex) {
      const atlas = new Sprite(atlasTex);
      atlas.width = size * 0.85;
      atlas.height = size * 0.85;
      atlas.anchor.set(0.5);
      atlas.x = cx;
      atlas.y = cy;
      this.body.addChild(atlas);
      // Tint faint class colour around the edges for readability
      this.body.circle(cx, cy, size * 0.44);
      this.body.stroke({ width: 2, color: 0xffffff, alpha: 0.5 });
    } else if (token.type === 'player') {
      // Hero: shield-shaped body
      this.body.roundRect(cx - size * 0.38, cy - size * 0.38, size * 0.76, size * 0.76, 8);
      this.body.fill({ color: baseColor });
      this.body.roundRect(cx - size * 0.38, cy - size * 0.38, size * 0.76, size * 0.76, 8);
      this.body.stroke({ width: 2, color: 0xffffff, alpha: 0.35 });
    } else {
      // Monster: jagged/circle hybrid
      this.body.circle(cx, cy, size * 0.38);
      this.body.fill({ color: baseColor });
      this.body.circle(cx, cy, size * 0.38);
      this.body.stroke({ width: 2, color: 0x000000, alpha: 0.35 });
    }
    this.container.addChild(this.body);

    // Detail icon
    this.detail = new Graphics();
    if (atlasTex) {
      // No extra vector detail when using atlas sprite
    } else if (token.type === 'player') {
      // Sword cross
      const bladeW = size * 0.12;
      const bladeH = size * 0.5;
      const guardW = size * 0.4;
      const guardH = size * 0.08;
      this.detail.roundRect(cx - bladeW / 2, cy - bladeH / 2, bladeW, bladeH, 2);
      this.detail.fill({ color: 0xffffff, alpha: 0.9 });
      this.detail.roundRect(cx - guardW / 2, cy + bladeH * 0.1 - guardH / 2, guardW, guardH, 2);
      this.detail.fill({ color: 0xd4af37, alpha: 0.95 });
    } else {
      // Monster eyes
      const eyeR = size * 0.07;
      this.detail.ellipse(cx - size * 0.12, cy - size * 0.05, eyeR, eyeR * 1.2);
      this.detail.ellipse(cx + size * 0.12, cy - size * 0.05, eyeR, eyeR * 1.2);
      this.detail.fill({ color: 0xffeb3b, alpha: 0.9 });
      // Mouth
      this.detail.ellipse(cx, cy + size * 0.15, size * 0.14, size * 0.06);
      this.detail.fill({ color: 0x000000, alpha: 0.45 });
    }
    this.container.addChild(this.detail);

    // Name label
    this.label = new Text({
      text: token.name,
      style: {
        fontSize: 10,
        fill: 0xffffff,
        align: 'center',
        dropShadow: {
          color: '#000000',
          distance: 1,
          blur: 2,
          alpha: 0.8,
        },
      },
    });
    this.label.anchor.set(0.5, 1);
    this.label.x = cx;
    this.label.y = pad + 1;
    this.container.addChild(this.label);

    // HP bar
    const barW = tileSize - 8;
    this.hpBar = new Graphics();
    this.hpBar.roundRect(4, -7, barW, 5, 2);
    this.hpBar.fill({ color: 0x1a1a1a, alpha: 0.9 });
    this.container.addChild(this.hpBar);

    this.hpFill = new Graphics();
    this.updateHP(token.hp, token.max_hp);
    this.container.addChild(this.hpFill);

    // Downed indicator (red cross)
    this.downCross = new Graphics();
    const crossSize = size * 0.35;
    this.downCross.moveTo(cx - crossSize, cy - crossSize);
    this.downCross.lineTo(cx + crossSize, cy + crossSize);
    this.downCross.moveTo(cx + crossSize, cy - crossSize);
    this.downCross.lineTo(cx - crossSize, cy + crossSize);
    this.downCross.stroke({ width: 3, color: 0xc0392b, alpha: 0.95 });
    this.downCross.visible = false;
    this.container.addChild(this.downCross);

    this.setDown(token.down ?? false);
  }

  setDown(down: boolean) {
    this.downCross.visible = down;
    this.container.alpha = down ? 0.55 : 1;
  }

  private resolveColor(token: Token): number {
    if (token.type === 'player') {
      const cls = token.classes?.[0]?.toLowerCase().replace(/[-\s]/g, '') || 'player';
      return TOKEN_COLORS[cls] || TOKEN_COLORS.player;
    }
    const key = token.name?.toLowerCase().replace(/[\s-]/g, '') || 'monster';
    return TOKEN_COLORS[key] || parseInt((token.color || '#2ecc71').replace('#', ''), 16) || TOKEN_COLORS.monster;
  }

  private resolveAtlasKey(token: Token): string | undefined {
    if (token.type === 'player') {
      const cls = token.classes?.[0]?.toLowerCase().replace(/[-\s]/g, '') || 'player';
      return cls;
    }
    return token.monster || token.name?.toLowerCase().replace(/[\s-]/g, '') || '';
  }

  updateHP(hp: number, maxHp: number) {
    const ratio = Math.max(0, Math.min(1, hp / maxHp));
    const barW = this.tileSize - 8;
    this.hpFill.clear();
    if (ratio > 0) {
      this.hpFill.roundRect(4, -7, barW * ratio, 5, 2);
      this.hpFill.fill({
        color: ratio > 0.5 ? 0x2ecc71 : ratio > 0.25 ? 0xf1c40f : 0xc0392b,
      });
    }
  }

  setTarget(x: number, y: number) {
    this.targetX = x * this.tileSize;
    this.targetY = y * this.tileSize;
  }

  snapToTarget() {
    this.container.x = this.targetX;
    this.container.y = this.targetY;
  }

  setActive(active: boolean) {
    this.container.alpha = active ? 1 : 0.65;
    this.pulse = active ? 1 : 0;
    this.ring.visible = active;
  }

  showFloat(text: string, color: number) {
    const cx = this.tileSize / 2;
    const floater = new Text({
      text,
      style: {
        fontSize: 12,
        fill: color,
        fontWeight: 'bold',
        align: 'center',
        dropShadow: { color: '#000000', distance: 1, blur: 2, alpha: 0.8 },
      },
    });
    floater.anchor.set(0.5, 1);
    floater.x = cx;
    floater.y = -4;
    this.container.addChild(floater);
    this.floaters.push({ text: floater, life: 40, maxLife: 40, vy: -0.6 });
  }

  tick(delta: number) {
    if (this.pulse > 0) {
      this.pulse -= delta * 0.05;
      const s = 1 + Math.sin(this.pulse * 8) * 0.04;
      this.body.scale.set(s);
      this.detail.scale.set(s);
      if (this.ring.visible) {
        const rs = 1 + Math.sin(this.pulse * 8) * 0.08;
        this.ring.scale.set(rs);
        this.ring.alpha = 0.5 + Math.sin(this.pulse * 8) * 0.35;
      }
    }

    for (let i = this.floaters.length - 1; i >= 0; i--) {
      const f = this.floaters[i];
      f.life -= delta;
      f.text.y += f.vy * delta;
      f.text.alpha = Math.max(0, f.life / f.maxLife);
      if (f.life <= 0) {
        f.text.destroy();
        this.floaters.splice(i, 1);
      }
    }
  }

  destroy() {
    this.container.destroy({ children: true });
  }
}

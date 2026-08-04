import * as PIXI from 'pixi.js';

export class Token {
  public id: string;
  public name: string;
  public color: string;
  public owner: string | null;
  public hp: number;
  public maxHp: number;
  public ac: number;
  public gridX: number;
  public gridY: number;
  public view: PIXI.Container;
  private body: PIXI.Graphics;
  private hpBar: PIXI.Graphics;
  private label: PIXI.Text;
  private selection: PIXI.Graphics;
  private targetMarker: PIXI.Graphics;

  constructor(
    public app: PIXI.Application,
    data: {
      id: string;
      name: string;
      x: number;
      y: number;
      color: string;
      owner?: string | null;
      hp?: number;
      max_hp?: number;
      ac?: number;
    },
    private tileSize: number
  ) {
    this.id = data.id;
    this.name = data.name;
    this.color = data.color;
    this.owner = data.owner ?? null;
    this.hp = data.hp ?? 0;
    this.maxHp = data.max_hp ?? 0;
    this.ac = data.ac ?? 10;
    this.gridX = data.x;
    this.gridY = data.y;

    this.view = new PIXI.Container();
    this.body = new PIXI.Graphics();
    this.hpBar = new PIXI.Graphics();
    this.selection = new PIXI.Graphics();
    this.targetMarker = new PIXI.Graphics();

    this.drawBody();
    this.drawHpBar();
    this.drawSelection(false);
    this.drawTarget(false);

    this.label = new PIXI.Text({
      text: this.name,
      style: {
        fontFamily: 'ui-monospace, monospace',
        fontSize: 10,
        fill: 0xffffff,
        align: 'center',
        dropShadow: {
          color: 0x000000,
          alpha: 0.7,
          angle: 45,
          distance: 1,
          blur: 2,
        },
      },
    });
    this.label.anchor.set(0.5);
    this.label.y = -this.tileSize * 0.25;

    this.view.addChild(this.body);
    this.view.addChild(this.hpBar);
    this.view.addChild(this.label);
    this.view.addChild(this.selection);
    this.view.addChild(this.targetMarker);

    this.view.x = data.x * this.tileSize + this.tileSize / 2;
    this.view.y = data.y * this.tileSize + this.tileSize / 2;
  }

  private drawBody() {
    this.body.clear();
    const r = this.tileSize * 0.32;
    // Shadow
    this.body.beginFill(0x000000, 0.4);
    this.body.drawCircle(3, 3, r);
    this.body.endFill();
    // Body
    this.body.beginFill(this.color);
    this.body.drawCircle(0, 0, r);
    this.body.endFill();
    // Rim
    this.body.lineStyle(2, 0xffffff, 0.85);
    this.body.drawCircle(0, 0, r);
  }

  private drawHpBar() {
    this.hpBar.clear();
    if (this.maxHp <= 0) return;
    const w = this.tileSize * 0.6;
    const h = 4;
    const pct = Math.max(0, this.hp / this.maxHp);
    const color = pct > 0.5 ? 0x2ecc71 : pct > 0.25 ? 0xf1c40f : 0xc0392b;
    this.hpBar.beginFill(0x000000, 0.7);
    this.hpBar.drawRect(-w / 2, this.tileSize * 0.18, w, h);
    this.hpBar.endFill();
    this.hpBar.beginFill(color);
    this.hpBar.drawRect(-w / 2, this.tileSize * 0.18, w * pct, h);
    this.hpBar.endFill();
  }

  private drawSelection(active: boolean) {
    this.selection.clear();
    if (!active) return;
    const r = this.tileSize * 0.38;
    this.selection.lineStyle(2, 0xf1c40f, 0.9);
    this.selection.drawCircle(0, 0, r);
  }

  private drawTarget(active: boolean) {
    this.targetMarker.clear();
    if (!active) return;
    const r = this.tileSize * 0.42;
    this.targetMarker.lineStyle(2, 0xc0392b, 0.9);
    this.targetMarker.drawCircle(0, 0, r);
  }

  setGridPosition(x: number, y: number, animate = true) {
    this.gridX = x;
    this.gridY = y;
    const tx = x * this.tileSize + this.tileSize / 2;
    const ty = y * this.tileSize + this.tileSize / 2;

    if (!animate) {
      this.view.x = tx;
      this.view.y = ty;
      return;
    }

    const startX = this.view.x;
    const startY = this.view.y;
    const duration = 180;
    const startTime = performance.now();

    const tick = (now: number) => {
      const elapsed = now - startTime;
      const t = Math.min(1, elapsed / duration);
      const ease = t * (2 - t);
      this.view.x = startX + (tx - startX) * ease;
      this.view.y = startY + (ty - startY) * ease;
      if (t < 1) {
        requestAnimationFrame(tick);
      }
    };
    requestAnimationFrame(tick);
  }

  setStats(hp: number, maxHp: number, ac: number) {
    this.hp = hp;
    this.maxHp = maxHp;
    this.ac = ac;
    this.drawHpBar();
  }

  highlight(active: boolean) {
    this.drawSelection(active);
  }

  markTarget(active: boolean) {
    this.drawTarget(active);
  }

  flashDamage() {
    const original = this.body.tint;
    this.body.tint = 0xffffff;
    setTimeout(() => {
      this.body.tint = original;
    }, 120);
  }

  playHitEffect() {
    this.flashDamage();
  }
}

import * as PIXI from 'pixi.js';

export class Token {
  public id: string;
  public name: string;
  public color: string;
  public owner: string | null;
  public view: PIXI.Container;
  private circle: PIXI.Graphics;
  private label: PIXI.Text;

  constructor(
    public app: PIXI.Application,
    data: { id: string; name: string; x: number; y: number; color: string; owner?: string | null },
    private tileSize: number
  ) {
    this.id = data.id;
    this.name = data.name;
    this.color = data.color;
    this.owner = data.owner ?? null;

    this.view = new PIXI.Container();
    this.circle = new PIXI.Graphics();
    this.draw();

    this.label = new PIXI.Text({
      text: this.name,
      style: {
        fontFamily: 'ui-monospace, monospace',
        fontSize: 10,
        fill: 0xffffff,
        align: 'center',
      },
    });
    this.label.anchor.set(0.5);
    this.label.y = this.tileSize / 2;
    this.view.addChild(this.circle);
    this.view.addChild(this.label);

    this.setGridPosition(data.x, data.y);
  }

  private draw() {
    this.circle.clear();
    this.circle.beginFill(this.color);
    this.circle.drawCircle(this.tileSize / 2, this.tileSize / 2, this.tileSize * 0.35);
    this.circle.endFill();
    this.circle.lineStyle(2, 0xffffff, 0.8);
    this.circle.drawCircle(this.tileSize / 2, this.tileSize / 2, this.tileSize * 0.35);
  }

  setGridPosition(x: number, y: number) {
    this.view.x = x * this.tileSize;
    this.view.y = y * this.tileSize;
  }

  highlight(active: boolean) {
    this.view.alpha = active ? 1 : 0.6;
  }
}

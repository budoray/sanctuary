import * as PIXI from 'pixi.js';

export class GameMap {
  public view: PIXI.Container;
  private grid: PIXI.Graphics;
  private highlight: PIXI.Graphics;

  constructor(
    public width: number,
    public height: number,
    public tileSize: number
  ) {
    this.view = new PIXI.Container();
    this.grid = new PIXI.Graphics();
    this.highlight = new PIXI.Graphics();
    this.view.addChild(this.grid);
    this.view.addChild(this.highlight);
    this.drawGrid();
  }

  private drawGrid() {
    this.grid.clear();
    this.grid.lineStyle(1, 0x2c2f38, 0.7);

    for (let x = 0; x <= this.width; x++) {
      this.grid.moveTo(x * this.tileSize, 0);
      this.grid.lineTo(x * this.tileSize, this.height * this.tileSize);
    }
    for (let y = 0; y <= this.height; y++) {
      this.grid.moveTo(0, y * this.tileSize);
      this.grid.lineTo(this.width * this.tileSize, y * this.tileSize);
    }

    const floor = new PIXI.Graphics();
    floor.beginFill(0x111216);
    floor.drawRect(0, 0, this.width * this.tileSize, this.height * this.tileSize);
    floor.endFill();
    this.view.addChildAt(floor, 0);
  }

  highlightTile(x: number, y: number) {
    this.highlight.clear();
    this.highlight.beginFill(0xc0392b, 0.25);
    this.highlight.drawRect(x * this.tileSize, y * this.tileSize, this.tileSize, this.tileSize);
    this.highlight.endFill();
    this.highlight.lineStyle(1, 0xc0392b, 0.8);
    this.highlight.drawRect(x * this.tileSize, y * this.tileSize, this.tileSize, this.tileSize);
  }

  clearHighlight() {
    this.highlight.clear();
  }
}

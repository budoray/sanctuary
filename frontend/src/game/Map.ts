import * as PIXI from 'pixi.js';

export type TileType = 'floor' | 'wall' | 'door';

export interface TokenData {
  id: string;
  name: string;
  x: number;
  y: number;
  color: string;
  owner?: string | null;
  hp?: number;
  max_hp?: number;
  ac?: number;
}

export interface MapData {
  width: number;
  height: number;
  tile_size: number;
  tiles: string[][];
  tokens: TokenData[];
}

const FLOOR_COLOR = 0x1a1c21;
const FLOOR_ALT = 0x1e2026;
const WALL_COLOR = 0x0b0c0e;
const WALL_TOP = 0x2c2f38;
const DOOR_COLOR = 0x5d4037;
const DOOR_GLOW = 0x8d6e63;
const FOG_COLOR = 0x050607;

export class GameMap {
  public view: PIXI.Container;
  private tilesLayer: PIXI.Container;
  private gridLayer: PIXI.Graphics;
  private highlightLayer: PIXI.Graphics;
  private fogLayer: PIXI.Graphics;
  private seen: boolean[][];

  constructor(
    public width: number,
    public height: number,
    public tileSize: number,
    public tiles: TileType[][]
  ) {
    this.view = new PIXI.Container();
    this.tilesLayer = new PIXI.Container();
    this.gridLayer = new PIXI.Graphics();
    this.highlightLayer = new PIXI.Graphics();
    this.fogLayer = new PIXI.Graphics();

    this.view.addChild(this.tilesLayer);
    this.view.addChild(this.gridLayer);
    this.view.addChild(this.highlightLayer);
    this.view.addChild(this.fogLayer);

    this.seen = Array.from({ length: height }, () => Array(width).fill(false));
    this.drawTiles();
    this.drawGrid();
  }

  static fromData(data: MapData): GameMap {
    const tiles = (data.tiles || []).map((row) =>
      row.map((t) => (t as TileType) || 'floor')
    );
    return new GameMap(data.width, data.height, data.tile_size || 32, tiles);
  }

  private drawTiles() {
    this.tilesLayer.removeChildren();
    for (let y = 0; y < this.height; y++) {
      for (let x = 0; x < this.width; x++) {
        const tile = this.tiles[y]?.[x] || 'floor';
        const g = new PIXI.Graphics();
        const px = x * this.tileSize;
        const py = y * this.tileSize;

        if (tile === 'wall') {
          g.beginFill(WALL_COLOR);
          g.drawRect(px, py, this.tileSize, this.tileSize);
          g.endFill();
          g.beginFill(WALL_TOP);
          g.drawRect(px + 2, py + 2, this.tileSize - 4, this.tileSize - 6);
          g.endFill();
        } else if (tile === 'door') {
          const alt = (x + y) % 2 === 0;
          g.beginFill(alt ? FLOOR_COLOR : FLOOR_ALT);
          g.drawRect(px, py, this.tileSize, this.tileSize);
          g.endFill();
          g.beginFill(DOOR_COLOR);
          g.drawRect(px + 6, py + 4, this.tileSize - 12, this.tileSize - 8);
          g.endFill();
          g.lineStyle(2, DOOR_GLOW, 0.6);
          g.drawRect(px + 6, py + 4, this.tileSize - 12, this.tileSize - 8);
        } else {
          const alt = (x + y) % 2 === 0;
          g.beginFill(alt ? FLOOR_COLOR : FLOOR_ALT);
          g.drawRect(px, py, this.tileSize, this.tileSize);
          g.endFill();
          // Subtle stone detail
          g.lineStyle(1, 0x25282e, 0.3);
          g.drawRect(px + 4, py + 4, this.tileSize - 8, this.tileSize - 8);
        }
        this.tilesLayer.addChild(g);
      }
    }
  }

  private drawGrid() {
    this.gridLayer.clear();
    this.gridLayer.lineStyle(1, 0x2c2f38, 0.35);
    for (let x = 0; x <= this.width; x++) {
      this.gridLayer.moveTo(x * this.tileSize, 0);
      this.gridLayer.lineTo(x * this.tileSize, this.height * this.tileSize);
    }
    for (let y = 0; y <= this.height; y++) {
      this.gridLayer.moveTo(0, y * this.tileSize);
      this.gridLayer.lineTo(this.width * this.tileSize, y * this.tileSize);
    }
  }

  highlightTile(x: number, y: number, color = 0xc0392b) {
    this.highlightLayer.clear();
    this.highlightLayer.beginFill(color, 0.2);
    this.highlightLayer.drawRect(x * this.tileSize, y * this.tileSize, this.tileSize, this.tileSize);
    this.highlightLayer.endFill();
    this.highlightLayer.lineStyle(1, color, 0.7);
    this.highlightLayer.drawRect(x * this.tileSize, y * this.tileSize, this.tileSize, this.tileSize);
  }

  clearHighlight() {
    this.highlightLayer.clear();
  }

  updateFog(playerX: number, playerY: number, sightRadius = 6) {
    // Mark seen tiles
    for (let y = 0; y < this.height; y++) {
      for (let x = 0; x < this.width; x++) {
        const dx = x - playerX;
        const dy = y - playerY;
        if (dx * dx + dy * dy <= sightRadius * sightRadius) {
          this.seen[y][x] = true;
        }
      }
    }

    this.fogLayer.clear();
    for (let y = 0; y < this.height; y++) {
      for (let x = 0; x < this.width; x++) {
        const dx = x - playerX;
        const dy = y - playerY;
        const dist2 = dx * dx + dy * dy;
        const visible = dist2 <= sightRadius * sightRadius;
        const explored = this.seen[y][x];

        if (!visible) {
          const alpha = explored ? 0.6 : 1.0;
          this.fogLayer.beginFill(FOG_COLOR, alpha);
          this.fogLayer.drawRect(x * this.tileSize, y * this.tileSize, this.tileSize, this.tileSize);
          this.fogLayer.endFill();
        }
      }
    }
  }

  isWalkable(x: number, y: number): boolean {
    if (x < 0 || x >= this.width || y < 0 || y >= this.height) return false;
    const t = this.tiles[y][x];
    return t === 'floor' || t === 'door';
  }
}

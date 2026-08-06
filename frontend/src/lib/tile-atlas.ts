import { Assets, Rectangle, Sprite, Texture } from 'pixi.js';

const SHEET_PATH = '/assets/kenney/roguelikeSheet_transparent.png';
const TILE_WIDTH = 16;
const TILE_HEIGHT = 16;
const SPACING = 1;
const COLUMNS = 57;
const ROWS = 31;

let baseTexture: Texture | null = null;
let frameCache: Map<string, Texture> = new Map();

export interface TileTheme {
  name: string;
  floor: [number, number];
  wall: [number, number];
  trap?: [number, number];
  door?: [number, number];
  water?: [number, number];
  lava?: [number, number];
  pit?: [number, number];
  // Per-tile char overrides
  tiles?: Record<string, [number, number]>;
}

export const THEMES: Record<string, TileTheme> = {
  dungeon: {
    name: 'Dungeon',
    floor: [20, 0],
    wall: [21, 1],
    trap: [8, 6],
  },
  cave: {
    name: 'Cave',
    floor: [6, 0],
    wall: [6, 5],
    trap: [8, 6],
  },
  library: {
    name: 'Library',
    floor: [15, 0],
    wall: [10, 2],
    trap: [8, 6],
  },
  ice: {
    name: 'Frozen',
    floor: [17, 13],
    wall: [19, 12],
    trap: [8, 6],
    water: [17, 12],
  },
  lava: {
    name: 'Volcanic',
    floor: [28, 14],
    wall: [29, 12],
    trap: [8, 6],
    lava: [29, 14],
  },
  forest: {
    name: 'Forest',
    floor: [0, 0],
    wall: [3, 6],
    trap: [8, 6],
    water: [1, 0],
  },
};

export function getTheme(id?: string): TileTheme | null {
  if (!id) return null;
  return THEMES[id] ?? null;
}

export async function loadAtlas(): Promise<Texture | null> {
  if (baseTexture) return baseTexture;
  try {
    baseTexture = await Assets.load(SHEET_PATH);
    return baseTexture;
  } catch (err) {
    console.warn('Failed to load tile atlas', err);
    return null;
  }
}

export function frameAt(col: number, row: number): Texture | null {
  if (!baseTexture) return null;
  if (col < 0 || col >= COLUMNS || row < 0 || row >= ROWS) return null;
  const key = `${col},${row}`;
  if (frameCache.has(key)) return frameCache.get(key)!;

  const x = col * (TILE_WIDTH + SPACING);
  const y = row * (TILE_HEIGHT + SPACING);
  const frame = new Texture({
    source: baseTexture.source,
    frame: new Rectangle(x, y, TILE_WIDTH, TILE_HEIGHT),
  });
  frameCache.set(key, frame);
  return frame;
}

export function spriteFor(col: number, row: number, size = 40): Sprite | null {
  const tex = frameAt(col, row);
  if (!tex) return null;
  const s = new Sprite(tex);
  s.width = size;
  s.height = size;
  return s;
}

export function tileFrame(theme: TileTheme, tile: string): Texture | null {
  const override = theme.tiles?.[tile];
  if (override) return frameAt(override[0], override[1]);
  switch (tile) {
    case '0':
    case '3':
    case '4':
    case '5':
      return frameAt(theme.floor[0], theme.floor[1]);
    case '1':
      return frameAt(theme.wall[0], theme.wall[1]);
    case '2':
      return frameAt(theme.trap?.[0] ?? theme.floor[0], theme.trap?.[1] ?? theme.floor[1]);
    default:
      return frameAt(theme.floor[0], theme.floor[1]);
  }
}

export interface TokenAtlas {
  col: number;
  row: number;
}

export const TOKEN_SPRITES: Record<string, TokenAtlas> = {
  hero: { col: 26, row: 7 },
  fighter: { col: 26, row: 7 },
  cleric: { col: 24, row: 7 },
  magicuser: { col: 25, row: 7 },
  illusionist: { col: 25, row: 7 },
  thief: { col: 27, row: 7 },
  ranger: { col: 28, row: 7 },
  paladin: { col: 29, row: 7 },
  druid: { col: 23, row: 7 },
  assassin: { col: 27, row: 8 },
  monk: { col: 28, row: 8 },
  goblin: { col: 23, row: 8 },
  orc: { col: 24, row: 8 },
  skeleton: { col: 25, row: 8 },
  zombie: { col: 26, row: 8 },
  ghoul: { col: 22, row: 8 },
  shadow_imp: { col: 21, row: 8 },
  librarian: { col: 22, row: 7 },
  animated_book: { col: 20, row: 7 },
  shadow_warden: { col: 29, row: 8 },
  wolf: { col: 24, row: 9 },
  bear: { col: 25, row: 9 },
  spider: { col: 26, row: 9 },
  snake: { col: 27, row: 9 },
  bat: { col: 28, row: 9 },
  rat: { col: 29, row: 9 },
  slime: { col: 23, row: 9 },
  demon: { col: 22, row: 9 },
  dragon: { col: 21, row: 9 },
};

export function tokenFrame(key?: string): Texture | null {
  const entry = key ? TOKEN_SPRITES[key.toLowerCase().replace(/[-\s]/g, '')] : undefined;
  if (!entry) return null;
  return frameAt(entry.col, entry.row);
}

export function resetAtlas() {
  baseTexture = null;
  frameCache.clear();
}

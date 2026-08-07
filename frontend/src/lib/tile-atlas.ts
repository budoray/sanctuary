import { Assets, Rectangle, Sprite, Texture } from 'pixi.js';

const SHEET_PATH = '/assets/kenney/roguelikeSheet_transparent.png';
const TILE_WIDTH = 16;
const TILE_HEIGHT = 16;
const SPACING = 1;
const COLUMNS = 57;
const ROWS = 31;

let baseTexture: Texture | null = null;
let frameCache: Map<string, Texture> = new Map();
const themeTextures: Map<string, Texture> = new Map();
const tokenTextures: Map<string, Texture> = new Map();

export interface TileTheme {
  name: string;
  floor: [number, number];
  wall: [number, number];
  trap?: [number, number];
  door?: [number, number];
  water?: [number, number];
  lava?: [number, number];
  pit?: [number, number];
  // Optional 32x32 custom art paths (falls back to Kenney sheet)
  images?: {
    floor?: string;
    wall?: string;
    trap?: string;
  };
  // Per-tile char overrides
  tiles?: Record<string, [number, number]>;
}

export const THEMES: Record<string, TileTheme> = {
  dungeon: {
    name: 'Dungeon',
    floor: [20, 0],
    wall: [21, 1],
    trap: [8, 6],
    images: { floor: '/assets/tiles/dungeon_floor.png', wall: '/assets/tiles/dungeon_wall.png', trap: '/assets/tiles/dungeon_trap.png' },
  },
  cave: {
    name: 'Cave',
    floor: [6, 0],
    wall: [6, 5],
    trap: [8, 6],
    images: { floor: '/assets/tiles/cave_floor.png', wall: '/assets/tiles/cave_wall.png', trap: '/assets/tiles/cave_trap.png' },
  },
  library: {
    name: 'Library',
    floor: [15, 0],
    wall: [10, 2],
    trap: [8, 6],
    images: { floor: '/assets/tiles/library_floor.png', wall: '/assets/tiles/library_wall.png', trap: '/assets/tiles/library_trap.png' },
  },
  ice: {
    name: 'Frozen',
    floor: [17, 13],
    wall: [19, 12],
    trap: [8, 6],
    water: [17, 12],
    images: { floor: '/assets/tiles/ice_floor.png', wall: '/assets/tiles/ice_wall.png', trap: '/assets/tiles/ice_trap.png' },
  },
  lava: {
    name: 'Volcanic',
    floor: [28, 14],
    wall: [29, 12],
    trap: [8, 6],
    lava: [29, 14],
    images: { floor: '/assets/tiles/lava_floor.png', wall: '/assets/tiles/lava_wall.png', trap: '/assets/tiles/lava_trap.png' },
  },
  forest: {
    name: 'Forest',
    floor: [0, 0],
    wall: [3, 6],
    trap: [8, 6],
    water: [1, 0],
    images: { floor: '/assets/tiles/forest_floor.png', wall: '/assets/tiles/forest_wall.png', trap: '/assets/tiles/forest_trap.png' },
  },
  tomb: {
    name: 'Tomb',
    floor: [20, 13],
    wall: [21, 13],
    trap: [8, 6],
    images: { floor: '/assets/tiles/tomb_floor.png', wall: '/assets/tiles/tomb_wall.png', trap: '/assets/tiles/tomb_trap.png' },
  },
  sewer: {
    name: 'Sewer',
    floor: [10, 13],
    wall: [12, 13],
    trap: [8, 6],
    water: [1, 0],
    images: { floor: '/assets/tiles/sewer_floor.png', wall: '/assets/tiles/sewer_wall.png', trap: '/assets/tiles/sewer_trap.png' },
  },
};

export const TOKEN_IMAGES: Record<string, string> = {
  hero: '/assets/tokens/hero.png',
  fighter: '/assets/tokens/hero.png',
  cleric: '/assets/tokens/hero.png',
  magicuser: '/assets/tokens/hero.png',
  illusionist: '/assets/tokens/hero.png',
  thief: '/assets/tokens/hero.png',
  ranger: '/assets/tokens/hero.png',
  paladin: '/assets/tokens/hero.png',
  druid: '/assets/tokens/hero.png',
  assassin: '/assets/tokens/hero.png',
  monk: '/assets/tokens/hero.png',
  goblin: '/assets/tokens/goblin.png',
  orc: '/assets/tokens/orc.png',
  skeleton: '/assets/tokens/skeleton.png',
  zombie: '/assets/tokens/zombie.png',
  ghoul: '/assets/tokens/ghoul.png',
  shadow_imp: '/assets/tokens/shadow_imp.png',
  librarian: '/assets/tokens/librarian.png',
  animated_book: '/assets/tokens/animated_book.png',
  shadow_warden: '/assets/tokens/shadow_warden.png',
  wolf: '/assets/tokens/wolf.png',
  bear: '/assets/tokens/bear.png',
  spider: '/assets/tokens/spider.png',
  snake: '/assets/tokens/snake.png',
  bat: '/assets/tokens/bat.png',
  rat: '/assets/tokens/rat.png',
  slime: '/assets/tokens/slime.png',
  demon: '/assets/tokens/demon.png',
  dragon: '/assets/tokens/dragon.png',
};

export function getTheme(id?: string): TileTheme | null {
  if (!id) return null;
  return THEMES[id] ?? null;
}

export async function loadAtlas(): Promise<Texture | null> {
  if (baseTexture) return baseTexture;
  try {
    baseTexture = await Assets.load(SHEET_PATH);
  } catch (err) {
    console.warn('Failed to load tile atlas', err);
  }

  // Preload custom 32x32 theme tiles.
  for (const [id, theme] of Object.entries(THEMES)) {
    if (theme.images?.floor) {
      try {
        const tex = await Assets.load(theme.images.floor);
        themeTextures.set(`${id}:floor`, tex);
      } catch (err) {
        console.warn(`Failed to load ${id} floor tile`, err);
      }
    }
    if (theme.images?.wall) {
      try {
        const tex = await Assets.load(theme.images.wall);
        themeTextures.set(`${id}:wall`, tex);
      } catch (err) {
        console.warn(`Failed to load ${id} wall tile`, err);
      }
    }
    if (theme.images?.trap) {
      try {
        const tex = await Assets.load(theme.images.trap);
        themeTextures.set(`${id}:trap`, tex);
      } catch (err) {
        console.warn(`Failed to load ${id} trap tile`, err);
      }
    }
  }

  // Preload custom token sprites.
  for (const [key, path] of Object.entries(TOKEN_IMAGES)) {
    if (tokenTextures.has(key)) continue;
    try {
      const tex = await Assets.load(path);
      tokenTextures.set(key, tex);
    } catch (err) {
      console.warn(`Failed to load token sprite ${key}`, err);
    }
  }

  return baseTexture;
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

export function tileFrame(themeId: string, theme: TileTheme, tile: string): Texture | null {
  const override = theme.tiles?.[tile];
  if (override) return frameAt(override[0], override[1]);
  switch (tile) {
    case '0':
    case '3':
    case '4':
    case '5': {
      const custom = theme.images?.floor ? themeTextures.get(`${themeId}:floor`) : null;
      return custom ?? frameAt(theme.floor[0], theme.floor[1]);
    }
    case '1': {
      const custom = theme.images?.wall ? themeTextures.get(`${themeId}:wall`) : null;
      return custom ?? frameAt(theme.wall[0], theme.wall[1]);
    }
    case '2': {
      const custom = theme.images?.trap ? themeTextures.get(`${themeId}:trap`) : null;
      return custom ?? frameAt(theme.trap?.[0] ?? theme.floor[0], theme.trap?.[1] ?? theme.floor[1]);
    }
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
  if (!key) return null;
  const normalized = key.toLowerCase().replace(/[-\s]/g, '');
  const imagePath = TOKEN_IMAGES[normalized];
  if (imagePath) {
    const tex = tokenTextures.get(normalized);
    if (tex) return tex;
  }
  const entry = TOKEN_SPRITES[normalized];
  if (!entry) return null;
  return frameAt(entry.col, entry.row);
}

export function resetAtlas() {
  baseTexture = null;
  frameCache.clear();
}

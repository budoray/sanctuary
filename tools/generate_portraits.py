"""Generate class portrait PNGs from the Kenney roguelike atlas."""
from pathlib import Path
from PIL import Image

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "frontend" / "public" / "assets" / "kenney" / "roguelikeSheet_transparent.png"
OUT = BASE / "frontend" / "public" / "portraits"

TILE = 16
SPACING = 1
SCALE = 4

CLASSES = {
    "generic": (26, 7),
    "fighter": (26, 7),
    "cleric": (24, 7),
    "magic-user": (25, 7),
    "illusionist": (25, 7),
    "thief": (27, 7),
    "ranger": (28, 7),
    "paladin": (29, 7),
    "druid": (23, 7),
    "assassin": (27, 8),
    "monk": (28, 8),
}


def main():
    if not SRC.exists():
        raise FileNotFoundError(SRC)
    OUT.mkdir(parents=True, exist_ok=True)
    sheet = Image.open(SRC).convert("RGBA")
    for name, (col, row) in CLASSES.items():
        x = col * (TILE + SPACING)
        y = row * (TILE + SPACING)
        tile = sheet.crop((x, y, x + TILE, y + TILE))
        scaled = tile.resize((TILE * SCALE, TILE * SCALE), Image.NEAREST)
        # Center on a dark circular background for portrait feel
        bg = Image.new("RGBA", (TILE * SCALE, TILE * SCALE), (18, 20, 24, 255))
        bg.paste(scaled, (0, 0), scaled)
        path = OUT / f"{name}.png"
        bg.save(path)
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()

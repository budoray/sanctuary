"""Chroma-key magenta and write engine-ready PNGs into static/art."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

SRC = Path(r"C:\Users\budor\.grok\sessions\d%3A%5CTenshin%20Arts\01a08647-6481-77c3-9545-0ff0789909ae\images")
DST = Path(__file__).resolve().parent.parent / "static" / "art"

# session image -> dest name, keyed?, size
JOBS = [
    ("2.jpg", "tile_floor.png", False, 64),
    ("7.jpg", "tile_floor_alt.png", False, 64),
    ("6.jpg", "tile_wall.png", False, 64),
    ("10.jpg", "tile_door.png", False, 64),
    ("5.jpg", "player_token.png", True, 128),
    ("1.jpg", "monster_kobold.png", True, 128),
    ("3.jpg", "monster_rat.png", True, 128),
    ("4.jpg", "monster_goblin.png", True, 128),
    ("12.jpg", "monster_goblin_boss.png", True, 128),
    ("8.jpg", "icon_chest.png", True, 96),
    ("9.jpg", "icon_beacon.png", True, 96),
    ("16.jpg", "monster_skeleton.png", True, 128),
    ("15.jpg", "monster_zombie.png", True, 128),
    ("14.jpg", "monster_ghoul.png", True, 128),
    ("13.jpg", "monster_drowned_king.png", True, 128),
]


def key_magenta(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r > 170 and b > 170 and g < 170 and r + b > g * 2.1:
                px[x, y] = (0, 0, 0, 0)
    return im


def crop_alpha(im: Image.Image, pad: int = 4) -> Image.Image:
    bbox = im.getbbox()
    if not bbox:
        return im
    l, t, r, b = bbox
    l = max(0, l - pad)
    t = max(0, t - pad)
    r = min(im.width, r + pad)
    b = min(im.height, b + pad)
    return im.crop((l, t, r, b))


def main() -> None:
    DST.mkdir(parents=True, exist_ok=True)
    for src_name, dest_name, keyed, size in JOBS:
        src = SRC / src_name
        if not src.exists():
            print(f"missing {src}")
            continue
        im = Image.open(src)
        if keyed:
            im = key_magenta(im)
            im = crop_alpha(im)
            im.thumbnail((size, size), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            ox = (size - im.width) // 2
            oy = (size - im.height) // 2
            canvas.paste(im, (ox, oy), im)
            im = canvas
        else:
            im = im.convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
        out = DST / dest_name
        im.save(out, "PNG")
        print(f"wrote {out.name} {im.size}")


if __name__ == "__main__":
    main()

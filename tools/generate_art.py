#!/usr/bin/env python3
"""Generate simple pixel-art tokens and icons for the OSRIC prototype."""
from PIL import Image, ImageDraw
import os

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "art")
os.makedirs(OUT_DIR, exist_ok=True)
SIZE = 32


def new_image():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def draw_base(img, draw, color, outline=(0, 0, 0, 255)):
    r = SIZE // 2 - 1
    cx, cy = SIZE // 2, SIZE // 2
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color, outline=outline, width=2)
    # highlight
    draw.ellipse([cx - r // 2, cy - r // 2, cx + r // 4, cy + r // 4], fill=(255, 255, 255, 40))


def save(name, img):
    img.save(os.path.join(OUT_DIR, name), "PNG")
    print(f"Generated {name}")


def make_player():
    img, draw = new_image()
    draw_base(img, draw, (90, 100, 120, 255))
    # head
    draw.ellipse([12, 6, 20, 14], fill=(230, 200, 160, 255), outline=(0, 0, 0, 255), width=1)
    # sword blade
    draw.rectangle([22, 8, 24, 24], fill=(210, 210, 220, 255), outline=(0, 0, 0, 255))
    draw.rectangle([21, 22, 25, 25], fill=(140, 90, 50, 255), outline=(0, 0, 0, 255))
    # shield
    draw.ellipse([6, 16, 16, 28], fill=(160, 50, 50, 255), outline=(0, 0, 0, 255), width=1)
    save("player_token.png", img)


def make_kobold():
    img, draw = new_image()
    draw_base(img, draw, (160, 120, 70, 255))
    draw.ellipse([12, 6, 20, 14], fill=(180, 140, 90, 255), outline=(0, 0, 0, 255), width=1)
    # spear
    draw.rectangle([23, 6, 25, 26], fill=(120, 90, 60, 255), outline=(0, 0, 0, 255))
    save("monster_kobold.png", img)


def make_goblin():
    img, draw = new_image()
    draw_base(img, draw, (90, 150, 70, 255))
    draw.ellipse([12, 5, 20, 13], fill=(110, 180, 90, 255), outline=(0, 0, 0, 255), width=1)
    # big ears
    draw.polygon([(10, 9), (5, 5), (10, 12)], fill=(110, 180, 90, 255), outline=(0, 0, 0, 255))
    draw.polygon([(22, 9), (27, 5), (22, 12)], fill=(110, 180, 90, 255), outline=(0, 0, 0, 255))
    # club
    draw.rectangle([22, 10, 26, 26], fill=(120, 90, 60, 255), outline=(0, 0, 0, 255))
    save("monster_goblin.png", img)


def make_skeleton():
    img, draw = new_image()
    draw_base(img, draw, (220, 220, 210, 255))
    # skull
    draw.ellipse([12, 6, 20, 14], fill=(240, 240, 230, 255), outline=(0, 0, 0, 255), width=1)
    # eye sockets
    draw.ellipse([14, 9, 15, 11], fill=(0, 0, 0, 255))
    draw.ellipse([17, 9, 18, 11], fill=(0, 0, 0, 255))
    # sword
    draw.rectangle([22, 8, 24, 24], fill=(180, 180, 180, 255), outline=(0, 0, 0, 255))
    save("monster_skeleton.png", img)


def make_orc():
    img, draw = new_image()
    draw_base(img, draw, (90, 130, 90, 255))
    draw.ellipse([12, 5, 20, 13], fill=(110, 160, 110, 255), outline=(0, 0, 0, 255), width=1)
    # axe
    draw.rectangle([22, 8, 25, 24], fill=(120, 90, 60, 255), outline=(0, 0, 0, 255))
    draw.polygon([(23, 6), (29, 10), (23, 14)], fill=(180, 180, 180, 255), outline=(0, 0, 0, 255))
    save("monster_orc.png", img)


def make_rat():
    img, draw = new_image()
    draw_base(img, draw, (130, 100, 80, 255))
    # snout
    draw.ellipse([13, 7, 19, 13], fill=(150, 120, 100, 255), outline=(0, 0, 0, 255), width=1)
    draw.ellipse([16, 10, 21, 13], fill=(150, 120, 100, 255), outline=(0, 0, 0, 255), width=1)
    # tail
    draw.line([(8, 24), (4, 28)], fill=(100, 70, 60, 255), width=2)
    save("monster_rat.png", img)


def make_door():
    img, draw = new_image()
    draw.rectangle([2, 2, 29, 29], fill=(110, 80, 50, 255), outline=(60, 40, 25, 255), width=2)
    draw.line([(16, 2), (16, 29)], fill=(60, 40, 25, 255), width=1)
    draw.rectangle([18, 14, 21, 17], fill=(180, 160, 60, 255), outline=(0, 0, 0, 255))
    save("icon_door.png", img)


def make_chest():
    img, draw = new_image()
    draw.rounded_rectangle([4, 10, 28, 26], radius=3, fill=(140, 90, 50, 255), outline=(60, 40, 25, 255), width=2)
    draw.rectangle([4, 15, 28, 17], fill=(100, 60, 30, 255))
    draw.ellipse([14, 14, 18, 18], fill=(210, 180, 60, 255), outline=(0, 0, 0, 255))
    save("icon_chest.png", img)


def make_beacon():
    img, draw = new_image()
    # glowing circle
    draw.ellipse([4, 4, 28, 28], fill=(255, 200, 80, 60), outline=(255, 180, 50, 180), width=2)
    draw.ellipse([10, 10, 22, 22], fill=(255, 220, 100, 200), outline=(255, 200, 60, 255), width=2)
    # rune cross
    draw.line([(16, 12), (16, 20)], fill=(80, 50, 10, 255), width=2)
    draw.line([(12, 16), (20, 16)], fill=(80, 50, 10, 255), width=2)
    save("icon_beacon.png", img)


def _noise_block(draw, rect, base, var):
    import random
    x0, y0, x1, y1 = rect
    for y in range(y0, y1):
        for x in range(x0, x1):
            v = max(0, min(255, base + random.randint(-var, var)))
            draw.point((x, y), fill=(v, v, v, 255))


def make_floor():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    _noise_block(draw, (0, 0, SIZE, SIZE), 48, 14)
    # mortar lines
    draw.line([(0, 0), (SIZE - 1, 0)], fill=(30, 26, 22, 255), width=1)
    draw.line([(0, 0), (0, SIZE - 1)], fill=(30, 26, 22, 255), width=1)
    save("tile_floor.png", img)


def make_floor_alt():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    _noise_block(draw, (0, 0, SIZE, SIZE), 56, 14)
    draw.line([(0, 0), (SIZE - 1, 0)], fill=(35, 30, 25, 255), width=1)
    draw.line([(0, 0), (0, SIZE - 1)], fill=(35, 30, 25, 255), width=1)
    save("tile_floor_alt.png", img)


def make_wall():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # stone block body
    _noise_block(draw, (0, 0, SIZE, SIZE), 35, 12)
    # top edge highlight
    draw.rectangle([0, 0, SIZE - 1, 5], fill=(60, 52, 44, 255))
    # cracks
    import random
    for _ in range(3):
        x = random.randint(4, SIZE - 4)
        y = random.randint(8, SIZE - 4)
        draw.line([(x, y), (x + random.randint(-4, 4), y + random.randint(2, 6))],
                  fill=(20, 17, 14, 255), width=1)
    save("tile_wall.png", img)


def make_door_tile():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # frame
    draw.rectangle([2, 2, SIZE - 2, SIZE - 2], fill=(80, 55, 35, 255), outline=(40, 28, 18, 255), width=2)
    # planks
    for x in range(7, SIZE - 2, 6):
        draw.line([(x, 4), (x, SIZE - 4)], fill=(55, 38, 25, 255), width=1)
    # handle
    draw.ellipse([SIZE - 9, SIZE // 2 - 3, SIZE - 5, SIZE // 2 + 3], fill=(180, 160, 60, 255), outline=(0, 0, 0, 255), width=1)
    save("tile_door.png", img)


def make_hobgoblin():
    img, draw = new_image()
    draw_base(img, draw, (150, 60, 60, 255))
    draw.ellipse([12, 5, 20, 13], fill=(180, 90, 90, 255), outline=(0, 0, 0, 255), width=1)
    # small ears
    draw.polygon([(10, 9), (5, 5), (10, 12)], fill=(180, 90, 90, 255), outline=(0, 0, 0, 255))
    draw.polygon([(22, 9), (27, 5), (22, 12)], fill=(180, 90, 90, 255), outline=(0, 0, 0, 255))
    # sword
    draw.rectangle([22, 8, 24, 24], fill=(190, 190, 200, 255), outline=(0, 0, 0, 255), width=1)
    draw.rectangle([21, 22, 25, 25], fill=(120, 80, 40, 255), outline=(0, 0, 0, 255), width=1)
    save("monster_hobgoblin.png", img)


def make_wight():
    img, draw = new_image()
    draw_base(img, draw, (60, 70, 90, 255))
    # pale ghoul-like face
    draw.ellipse([12, 6, 20, 14], fill=(200, 210, 220, 255), outline=(0, 0, 0, 255), width=1)
    draw.ellipse([14, 9, 15, 11], fill=(0, 0, 0, 255))
    draw.ellipse([17, 9, 18, 11], fill=(0, 0, 0, 255))
    # spectral claws
    draw.polygon([(24, 16), (29, 20), (24, 24)], fill=(160, 180, 200, 255), outline=(0, 0, 0, 255))
    save("monster_wight.png", img)


def make_spider():
    img, draw = new_image()
    draw_base(img, draw, (60, 50, 65, 255))
    # body segments
    draw.ellipse([12, 10, 20, 18], fill=(80, 70, 85, 255), outline=(0, 0, 0, 255), width=1)
    draw.ellipse([14, 5, 18, 11], fill=(70, 60, 75, 255), outline=(0, 0, 0, 255), width=1)
    # legs
    for angle in [(4, 4), (8, 2), (24, 2), (28, 4), (4, 24), (8, 28), (24, 28), (28, 24)]:
        draw.line([(16, 13), angle], fill=(80, 70, 85, 255), width=2)
    save("monster_spider.png", img)


def make_bandit():
    img, draw = new_image()
    draw_base(img, draw, (110, 90, 70, 255))
    draw.ellipse([12, 6, 20, 14], fill=(190, 160, 130, 255), outline=(0, 0, 0, 255), width=1)
    # hood mask
    draw.polygon([(12, 6), (20, 6), (16, 12)], fill=(60, 55, 50, 255), outline=(0, 0, 0, 255))
    # dagger
    draw.rectangle([23, 10, 25, 22], fill=(180, 180, 190, 255), outline=(0, 0, 0, 255), width=1)
    save("monster_bandit.png", img)


if __name__ == "__main__":
    make_player()
    make_kobold()
    make_goblin()
    make_skeleton()
    make_orc()
    make_rat()
    make_door()
    make_chest()
    make_beacon()
    make_floor()
    make_floor_alt()
    make_wall()
    make_door_tile()
    make_hobgoblin()
    make_wight()
    make_spider()
    make_bandit()

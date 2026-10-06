"""تيفو v5 app icons and iPhone splash screens (site/redesign/v5/ROLLOUT.md, PWA).
   python site/redesign/v5/icons.py   -> site/icons/*.png (committed; build.cjs copies site/icons/ into out/icons/)
   The mark is v5's 3x3 «tifo» of rounded cards (src/v5/app.css .mark): pitch green ground, white cards, two quiet cards, and the
   three accent cards in a light pitch green. Maskable icons keep the mark inside the 80 % safe circle; the badge is a white mark
   on transparent (Android draws notification badges from the alpha only). Splash screens: the icon on the system ground of each
   scheme (#F2F2F7 light, #000000 dark) at the sizes current iPhones ask for."""
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "icons"))
GREEN, LIGHT, WHITE = (11, 130, 70), (124, 240, 180), (255, 255, 255)
# v5 .mark: cells 2, 6, 7 accent; 3, 5 quiet; the rest full
KIND = ["full", "accent", "quiet", "full", "quiet", "accent", "accent", "full", "full"]


def mark(draw, cx, cy, size, on_green=True, mono=False):
    """the 3x3 mark centred at (cx, cy), `size` px across"""
    gap = size * 0.07
    cell = (size - 2 * gap) / 3
    rad = cell * 0.24
    for i, k in enumerate(KIND):
        r, c = divmod(i, 3)
        x0 = cx - size / 2 + c * (cell + gap)
        y0 = cy - size / 2 + r * (cell + gap)
        if mono:
            col = (255, 255, 255, 255 if k != "quiet" else 140)
        elif on_green:
            col = WHITE + (255,) if k == "full" else LIGHT + (255,) if k == "accent" else WHITE + (110,)
        else:
            col = (20, 20, 20, 255) if k == "full" else GREEN + (255,) if k == "accent" else (20, 20, 20, 90)
        draw.rounded_rectangle([x0, y0, x0 + cell, y0 + cell], radius=rad, fill=col)


def icon(px, scale=0.5, bg=GREEN, rounded=False):
    im = Image.new("RGBA", (px, px), bg + (255,))
    layer = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    mark(ImageDraw.Draw(layer), px / 2, px / 2, px * scale)
    im = Image.alpha_composite(im, layer)
    if rounded:   # an iOS-like squircle for places that show the PNG as is (the in-page install sheet)
        m = Image.new("L", (px, px), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, px - 1, px - 1], radius=px * 0.225, fill=255)
        im.putalpha(m)
    return im


def save(im, name):
    p = os.path.join(OUT, name)
    im.save(p, optimize=True)
    print(name, im.size, os.path.getsize(p), "bytes")


def main():
    os.makedirs(OUT, exist_ok=True)
    save(icon(512), "icon-512.png")
    save(icon(192), "icon-192.png")
    save(icon(512, scale=0.42), "maskable-512.png")       # the mark inside the 80 % safe zone
    save(icon(192, scale=0.42), "maskable-192.png")
    save(icon(180, scale=0.52).convert("RGB"), "apple-touch-icon.png")   # iOS rounds the corners itself; no alpha
    save(icon(256, rounded=True), "app-256.png")
    b = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    mark(ImageDraw.Draw(b), 48, 48, 64, mono=True)
    save(b, "badge-96.png")
    # iPhone launch screens (portrait): width x height in device pixels
    for w, h in [(1290, 2796), (1206, 2622), (1179, 2556), (1170, 2532), (1125, 2436), (828, 1792), (750, 1334)]:
        for scheme, bg in (("light", (242, 242, 247)), ("dark", (0, 0, 0))):
            im = Image.new("RGB", (w, h), bg)
            ic = icon(int(w * 0.22), rounded=True)
            im.paste(ic, ((w - ic.width) // 2, int(h * 0.42) - ic.height // 2), ic)
            save(im, f"splash-{w}x{h}-{scheme}.png")


if __name__ == "__main__":
    main()

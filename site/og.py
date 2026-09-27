"""Share-preview images (feature 169): 1200x630 PNGs in the Tifo identity for WhatsApp/X/Telegram link previews.
Reads out/og/jobs.json (written by build.cjs: [{key, kind, home, away, score, time, comp, colors...}]) and renders each
into cache/og/<key>.png, skipping keys whose content hash hasn't changed; copies them to out/og/. Pillow + raqm (Arabic
shaping), fonts in site/fonts (OFL: Noto Kufi Arabic, Barlow Condensed, Readex Pro). Club crests from cache/logo."""
import hashlib, json, os, random, shutil, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT, CACHE = os.path.join(HERE, "out"), os.path.join(HERE, "cache")
NIGHT, NIGHT2, CHALK, DUNE, PULSE = (10, 38, 32), (18, 58, 49), (246, 247, 242), (176, 122, 59), (16, 160, 75)
W, H = 1200, 630

def font(name, size, var=None):
    f = ImageFont.truetype(os.path.join(HERE, "fonts", name), size, layout_engine=ImageFont.Layout.RAQM)
    if var:
        try: f.set_variation_by_name(var)
        except Exception: pass
    return f

KUFI = lambda s: font("kufi.ttf", s, b"ExtraBold")
DIG = lambda s: font("barlow.ttf", s)
TXT = lambda s: font("readex.ttf", s, b"Regular")

def hexrgb(h):
    h = (h or "#5C6660").lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def stand(d, x0, y0, w, h, cs, home, away, seed):
    rnd = random.Random(seed); cols, rows = w // cs + 1, h // cs + 1
    for r in range(rows):
        for c in range(cols):
            right = c >= cols / 2; pal = home if right or away is None else away
            stripe = ((cols - c if right else c) + r) % 7 < 2
            base = pal[1] if stripe and len(pal) > 1 else pal[0]; k = 0.86 + rnd.random() * 0.22
            col = tuple(max(0, min(255, int(v * k))) for v in base)
            d.rectangle([x0 + c * cs, y0 + r * cs, x0 + c * cs + cs - 3, y0 + r * cs + cs - 3], fill=col)

def fit(d, text, mk, size, maxw):
    while size > 18:
        f = mk(size)
        if d.textlength(text, font=f, direction="rtl", language="ar") <= maxw: return f
        size -= 2
    return mk(size)

def logo(path, size):
    try:
        im = Image.open(path).convert("RGBA"); im.thumbnail((size, size)); return im
    except Exception: return None

def mark(d, x, y, s):
    cl = [[CHALK, PULSE, DUNE], [CHALK, DUNE, PULSE], [PULSE, DUNE, CHALK]]
    for r in range(3):
        for c in range(3): d.rectangle([x + c * s * 1.25, y + r * s * 1.25, x + c * s * 1.25 + s, y + r * s * 1.25 + s], fill=cl[r][c])

def render(j):
    im = Image.new("RGB", (W, H), NIGHT); d = ImageDraw.Draw(im)
    hc = [hexrgb(c) for c in (j.get("hc") or ["#5C6660"])]; ac = [hexrgb(c) for c in (j.get("ac") or ["#3D4A44"])] if j.get("away") else None
    stand(d, 0, 0, W, 190, 30, hc, ac, j["key"])
    d.rectangle([0, 190, W, H], fill=NIGHT)
    if j.get("comp"): d.text((W / 2, 235), j["comp"], font=TXT(30), fill=(185, 199, 192), anchor="mm", direction="rtl", language="ar")
    if j.get("away"):
        for side, x in (("home", W - 210), ("away", 210)):
            lg = logo(os.path.join(CACHE, "logo", f"{j[side + '_id']}.png"), 150)
            if lg: im.paste(lg, (int(x - lg.width / 2), 270), lg)
            d.text((x, 470), j[side], font=fit(d, j[side], KUFI, 44, 360), fill=CHALK, anchor="mm", direction="rtl", language="ar")
        big = j.get("score") or j.get("time") or ""
        d.text((W / 2, 360), big, font=DIG(150 if j.get("score") else 120), fill=CHALK, anchor="mm")
        if j.get("sub"): d.text((W / 2, 470), j["sub"], font=KUFI(30), fill=DUNE, anchor="mm", direction="rtl", language="ar")
    else:
        lg = logo(os.path.join(CACHE, "logo", f"{j.get('home_id')}.png"), 170) if j.get("home_id") else None
        if lg: im.paste(lg, (int(W / 2 - lg.width / 2), 250), lg)
        d.text((W / 2, 480), j["home"], font=fit(d, j["home"], KUFI, 64, W - 200), fill=CHALK, anchor="mm", direction="rtl", language="ar")
        if j.get("sub"): d.text((W / 2, 545), j["sub"], font=TXT(30), fill=(185, 199, 192), anchor="mm", direction="rtl", language="ar")
    mark(d, W - 150, H - 88, 16); d.text((W - 190, H - 62), "تيفو", font=KUFI(40), fill=CHALK, anchor="rm", direction="rtl", language="ar")
    d.text((60, H - 62), "tifo.elyoxe.com", font=DIG(34), fill=(185, 199, 192), anchor="lm")
    return im

def main():
    jobs = json.load(open(os.path.join(OUT, "og", "jobs.json"))); os.makedirs(os.path.join(CACHE, "og"), exist_ok=True); new = 0
    for j in jobs:
        h = hashlib.sha1(json.dumps(j, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:10]
        cf = os.path.join(CACHE, "og", f"{j['key']}-{h}.png")
        if not os.path.exists(cf):
            render(j).save(cf, optimize=True); new += 1
        shutil.copyfile(cf, os.path.join(OUT, "og", f"{j['key']}.png"))
    os.remove(os.path.join(OUT, "og", "jobs.json"))
    print(f"og: {len(jobs)} images ({new} new)")

if __name__ == "__main__":
    main()

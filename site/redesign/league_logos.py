"""Competition logos for the v3 preview: FotMob league crests (index.json ids are FotMob league ids), the dark variant
preferred when FotMob serves one that differs, cached in redesign/cache/leaguelogo/<id>.png (never the shared site cache).
Dominant colours with site/logo_colors.py's method (buckets ranked by count x saturation, white/black rims discounted)
-> redesign/cache/league_colors.json {id: [c1, c2]}. Usage: python3 league_logos.py <id> [<id> ...]"""
import json, os, sys, colorsys, hashlib, urllib.request
from PIL import Image
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
L = os.path.join(D, "leaguelogo"); os.makedirs(L, exist_ok=True)
def fetch(u):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=20) as r: return r.read() if r.status == 200 else None
    except Exception: return None
for cid in sys.argv[1:]:
    f = os.path.join(L, cid + ".png")
    if os.path.exists(f): continue
    light = fetch(f"https://images.fotmob.com/image_resources/logo/leaguelogo/{cid}.png")
    dark = fetch(f"https://images.fotmob.com/image_resources/logo/leaguelogo/dark/{cid}.png")
    b = dark if dark and (not light or hashlib.sha1(dark).digest() != hashlib.sha1(light).digest()) else light
    if b: open(f, "wb").write(b)
out = {}
for n in sorted(os.listdir(L)):
    try: im = Image.open(os.path.join(L, n)).convert("RGBA").resize((64, 64))
    except Exception: continue
    buckets = {}
    for r, g, b, a in im.getdata():
        if a < 200: continue
        k = (r // 24 * 24 + 12, g // 24 * 24 + 12, b // 24 * 24 + 12); buckets[k] = buckets.get(k, 0) + 1
    if not buckets: continue
    def score(kv):
        (r, g, b), c = kv; h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        return c * (0.35 + s) * (0.15 if l > 0.9 or l < 0.08 else 1.0)
    ranked = sorted(buckets.items(), key=score, reverse=True)
    far = lambda a, b: sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5 > 90
    c1 = ranked[0][0]; c2 = next((k for k, _ in ranked[1:] if far(k, c1)), None)
    hx = lambda c: "#%02x%02x%02x" % tuple(min(255, v) for v in c)
    out[n.split(".")[0]] = [hx(c1)] + ([hx(c2)] if c2 else [])
json.dump(out, open(os.path.join(D, "league_colors.json"), "w"), separators=(",", ":"))
print(len(os.listdir(L)), "logos,", len(out), "coloured")

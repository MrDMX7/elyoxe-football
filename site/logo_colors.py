"""Club colours from the cached crests (cache/logo/<id>.png) -> cache/colors.json {id: ["#rrggbb", "#rrggbb"]}.
Ignores transparent pixels; ranks colour buckets by count x saturation so white rims and black outlines lose to the real
club colour. A crest with nothing usable gets no entry (the site falls back to neutral chalk/ink)."""
import json, os, colorsys
from PIL import Image
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
out, old = {}, {}
f = os.path.join(D, "colors.json")
if os.path.exists(f): old = json.load(open(f))
for n in sorted(os.listdir(os.path.join(D, "logo"))):
    tid = n.split(".")[0]
    if tid in old: out[tid] = old[tid]; continue
    try: im = Image.open(os.path.join(D, "logo", n)).convert("RGBA").resize((64, 64))
    except Exception: continue
    buckets = {}
    px = im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata()
    for r, g, b, a in px:
        if a < 200: continue
        k = (r // 24 * 24 + 12, g // 24 * 24 + 12, b // 24 * 24 + 12)
        buckets[k] = buckets.get(k, 0) + 1
    if not buckets: continue
    def score(kv):
        (r, g, b), c = kv; h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        w = 0.15 if l > 0.9 or l < 0.08 else 1.0
        return c * (0.35 + s) * w
    ranked = sorted(buckets.items(), key=score, reverse=True)
    def far(a, b): return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5 > 90
    c1 = ranked[0][0]; c2 = next((k for k, _ in ranked[1:] if far(k, c1)), None)
    hexs = lambda c: "#%02x%02x%02x" % tuple(min(255, v) for v in c)
    out[tid] = [hexs(c1)] + ([hexs(c2)] if c2 else [])
json.dump(out, open(f, "w"), separators=(",", ":"))
print(len(out), "crests coloured")

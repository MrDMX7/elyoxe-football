"""Row-size crests (audit W2.11): cache/logo/<id>.png -> cache/logo96/<id>.webp (96 px, quality 82), made once and reused.
The build copies them to out/logo/96/. Heroes keep the full png."""
import os, sys
from PIL import Image
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
src, dst = os.path.join(D, "logo"), os.path.join(D, "logo96")
os.makedirs(dst, exist_ok=True); n = 0
for f in os.listdir(src):
    if not f.endswith(".png"): continue
    o = os.path.join(dst, f[:-4] + ".webp"); s = os.path.join(src, f)
    if os.path.exists(o) and os.path.getmtime(o) >= os.path.getmtime(s): continue
    try:
        im = Image.open(s).convert("RGBA"); im.thumbnail((96, 96)); im.save(o, "WEBP", quality=82, method=4); n += 1
    except Exception: pass
print(n, "new row crests")

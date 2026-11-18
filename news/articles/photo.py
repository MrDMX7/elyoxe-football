"""The article's photo (spec, «Every article has a real photo of its subject»). A match report takes a frame of the match: the
official highlights video's YouTube thumbnail (maxresdefault, 1280x720), else a goal clip's, from v1/media/<id>.json; else
Tifo's match card (/og/m-<id>.png, 1200x630). A frame is cropped to 16:9 and resized to 1200x675, stored at
v1/news/img/<id>.jpg (an outlet's link can break), and captioned. Under 1200 px wide it is skipped."""
import io
from PIL import Image

SITE = "https://tifo.elyoxe.com"


def _yt(v):
    return f"https://i.ytimg.com/vi/{v['id']}/maxresdefault.jpg" if v.get("source") == "youtube" and v.get("id") else v.get("image")


def candidates(md, media):
    out = []
    for v in (media or {}).get("highlights") or []:
        if _yt(v):
            out.append({"url": _yt(v), "caption": f"لقطة من ملخص المباراة على قناة {v.get('channel') or 'رسمية'}", "source": v.get("source")})
    for clips in ((media or {}).get("goals") or {}).values():
        for v in clips:
            if _yt(v):
                out.append({"url": _yt(v), "caption": f"لقطة من هدف في المباراة على قناة {v.get('channel') or 'رسمية'}", "source": v.get("source")})
    out.append({"url": f"{SITE}/og/m-{md['id']}.png", "caption": f"بطاقة مباراة {md['home']['name_ar']} و{md['away']['name_ar']} من تيفو", "source": "card"})
    return out


def pick(aid, md, media, fetch, store):
    for c in candidates(md, media):
        if c["source"] == "card":
            return dict(c, w=1200, h=630, card=True)
        raw = fetch(c["url"])
        if not raw:
            continue
        try:
            im = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception:
            continue
        if im.width < 1200:
            continue
        w, h = im.size
        ch = round(w * 9 / 16)
        if ch <= h:
            top = (h - ch) // 2; im = im.crop((0, top, w, top + ch))
        else:
            cw = round(h * 16 / 9); left = (w - cw) // 2; im = im.crop((left, 0, left + cw, h))
        im = im.resize((1200, 675), Image.LANCZOS)
        b = io.BytesIO(); im.save(b, "JPEG", quality=85, optimize=True)
        store.put_bytes(f"news/img/{aid}.jpg", b.getvalue(), "image/jpeg", cache="static")
        return {"url": f"{SITE}/v1/news/img/{aid}.jpg", "w": 1200, "h": 675, "caption": c["caption"], "source": c["source"], "card": False}

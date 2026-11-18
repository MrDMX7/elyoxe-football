"""The article's photo (spec, «Every article has a real photo of its subject»). A match report takes a frame of the match: the
official highlights video's YouTube thumbnail (maxresdefault, 1280x720), else a goal clip's, from v1/media/<id>.json; else
Tifo's own card with the two logos and the score. A frame is cropped to 16:9 and resized to 1200x675, stored at
v1/news/img/<id>.jpg (an outlet's link can break), and captioned. Under 1200 px wide it is skipped. With no frame, Tifo draws
its own card (card() below) and stores it the same way."""
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
    out.append({"url": None, "caption": f"بطاقة مباراة {md['home'].get('name_ar')} و{md['away'].get('name_ar')} من تيفو", "source": "card"})
    return out


def card(md, fetch):
    """Tifo's own 1200x675 card when the match has no frame: the two club logos and the score on Tifo's dark ground. Drawn here
    because /og/m-<id>.png exists only for a few competitions (final review, finding 2: most reports pointed at a 404).
    Home on the right (Arabic reading order); digits only, so no Arabic shaping is needed."""
    from PIL import ImageDraw, ImageFont
    im = Image.new("RGB", (1200, 675), (20, 26, 23))
    d = ImageDraw.Draw(im)
    for side, cx in (("home", 960), ("away", 240)):
        raw = fetch((md.get(side) or {}).get("logo") or "") if (md.get(side) or {}).get("logo") else None
        try:
            lg = Image.open(io.BytesIO(raw)).convert("RGBA"); lg.thumbnail((300, 300))
            im.paste(lg, (cx - lg.width // 2, 337 - lg.height // 2), lg)
        except Exception:
            d.ellipse((cx - 120, 217, cx + 120, 457), outline=(92, 102, 96), width=6)
    sc = md.get("score") or {}
    txt = f"{sc.get('away', '')}  -  {sc.get('home', '')}"
    try:
        font = ImageFont.load_default(size=150)
    except TypeError:
        font = ImageFont.load_default()
    d.text((600, 337), txt, fill=(242, 242, 247), font=font, anchor="mm")
    return im


def pick(aid, md, media, fetch, store):
    for c in candidates(md, media):
        if c["source"] == "card":
            b = io.BytesIO(); card(md, fetch).save(b, "JPEG", quality=88, optimize=True)
            store.put_bytes(f"news/img/{aid}.jpg", b.getvalue(), "image/jpeg", cache="static")
            return {"url": f"{SITE}/v1/news/img/{aid}.jpg", "w": 1200, "h": 675, "caption": c["caption"], "source": "card", "card": True}
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

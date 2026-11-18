"""The article's photo (spec, «Every article has a real photo of its subject»). A match report takes a frame of the match: the
official highlights video's YouTube thumbnail (maxresdefault, 1280x720), else a goal clip's, from v1/media/<id>.json; else
Tifo's own card with the two logos and the score. A frame is cropped to 16:9 and resized to 1200x675, stored at
v1/news/img/<id>.jpg (an outlet's link can break), and captioned. Under 1200 px wide it is skipped. With no frame, Tifo draws
its own card (card() below) and stores it the same way."""
import io, json, urllib.parse, urllib.request
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


LOGO = "https://images.fotmob.com/image_resources/logo/teamlogo/{}.png"
COMMONS = "ويكيميديا كومنز"
UA = {"User-Agent": "tifo-articles/1.0 (https://tifo.elyoxe.com)"}       # Wikimedia asks every client to name itself


def _get_json(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
            return json.loads(r.read())
    except Exception:
        return None


def commons(query, get_json=None, n=4):
    """Photos of a player or club on Wikimedia Commons, best match first, as 1600 px thumbnails."""
    q = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": n,
                                "gsrsearch": f"{query} filetype:bitmap", "prop": "imageinfo", "iiprop": "url|size", "iiurlwidth": 1600})
    pages = ((get_json or _get_json)(f"https://commons.wikimedia.org/w/api.php?{q}") or {}).get("query", {}).get("pages", {})
    out = sorted(pages.values(), key=lambda p: p.get("index", 99))
    return [{"url": p["imageinfo"][0].get("thumburl") or p["imageinfo"][0]["url"], "source": COMMONS} for p in out if p.get("imageinfo")]


def news_candidates(texts, story, items, extra):
    """Every photo the story offers: the outlets' own (og:image), the journal's item images, then `extra` (Commons)."""
    raw = [(t.get("image"), t.get("source")) for t in texts]
    raw += [((items.get(i) or {}).get("image"), (items.get(i) or {}).get("source")) for i in story.get("items") or []]
    raw += [(c["url"], c["source"]) for c in extra]
    seen, out = set(), []
    for url, src in raw:
        if url and url not in seen:
            seen.add(url); out.append({"url": url, "source": src})
    return out[:10]


def clubs_card(team_ids, fetch):
    """Tifo's card for a news article with no fitting photo: the clubs' logos on Tifo's dark ground."""
    im = Image.new("RGB", (1200, 675), (20, 26, 23))
    ids = list(team_ids)[:2]
    for tid, cx in zip(ids, [600] if len(ids) == 1 else [800, 400]):
        try:
            lg = Image.open(io.BytesIO(fetch(LOGO.format(tid)))).convert("RGBA"); lg.thumbnail((320, 320))
            im.paste(lg, (cx - lg.width // 2, 337 - lg.height // 2), lg)
        except Exception:
            pass
    return im


def _crop169(im):
    w, h = im.size
    if w * 9 > h * 16:
        nw = round(h * 16 / 9); return im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    nh = round(w * 9 / 16); return im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))


def _thumb(im):
    t = im.copy(); t.thumbnail((512, 512))
    b = io.BytesIO(); t.save(b, "JPEG", quality=80); return b.getvalue()


def news_pick(aid, cands, team_ids, fetch, store, subject=None, headline="", judge=None):
    """The candidate that fits the news best (the owner's plan review): the 1200 px and wider ones go to `judge` with the
    headline, which answers an index or -1 (none fits: Tifo's card). Without a judge, or if it fails, the widest."""
    ok = []
    for c in cands:
        try:
            im = Image.open(io.BytesIO(fetch(c["url"]))).convert("RGB")
        except Exception:
            continue
        if im.width >= 1200:
            ok.append((im, c))
    best = max(ok, key=lambda x: x[0].width) if ok else None
    if ok and judge:
        try:
            import inspect
            thumbs = [_thumb(im) for im, _ in ok]
            if len(inspect.signature(judge).parameters) >= 3:          # the judge is told where each photo came from
                i = judge(headline, thumbs, [c["source"] for _, c in ok])
            else:
                i = judge(headline, thumbs)
            best = ok[i] if 0 <= i < len(ok) else None
        except Exception as e:
            print(json.dumps({"photo_judge_error": aid, "error": str(e)[:200]}))
    who = f"{subject} — " if subject else ""
    if best:
        im, caption, card = _crop169(best[0]).resize((1200, 675), Image.LANCZOS), f"{who}الصورة من {best[1]['source']}", False
    else:
        im, caption, card = clubs_card(team_ids, fetch), f"{who}بطاقة تيفو", True
    b = io.BytesIO(); im.save(b, "JPEG", quality=86, optimize=True)
    store.put_bytes(f"news/img/{aid}.jpg", b.getvalue(), "image/jpeg", cache="static")
    return {"url": f"{SITE}/v1/news/img/{aid}.jpg", "w": 1200, "h": 675, "caption": caption, "source": "news", "card": card}

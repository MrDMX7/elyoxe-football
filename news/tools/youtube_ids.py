"""Resolve official YouTube handles to channel ids and check each channel's public feed (free, no API key).
   python news/tools/youtube_ids.py                          # the HANDLES below -> yaml lines for sources.yaml
   python news/tools/youtube_ids.py --check @beINSPORTS UCvuPuKPukGd8S2qr4msLAuQ …
The id is read from the channel page itself (never guessed); a handle that doesn't resolve is reported and left out.

--check prints what decides whether a channel is the official one (news/sources.yaml `media:` keeps only those): the canonical
id, the name, the @handle, the subscriber count, whether YouTube shows its verified badge, the first line of its description,
and the newest titles of its feed (do they match what the organisation publishes?). A verified badge alone proves nothing: a
re-upload channel can carry one («Youssef Sobhi», 2026-09-30); the name, the scale and the uploads have to agree."""
import json, re, sys, time, urllib.parse, urllib.request
sys.path.insert(0, __file__.rsplit("news", 1)[0])
from news.readers import parse_feed, fetch, UA

HANDLES = {  # handle: (Arabic name for the site, entity hint)
    "RealMadrid": "ريال مدريد", "fcbarcelona": "برشلونة", "mancity": "مانشستر سيتي", "LiverpoolFC": "ليفربول",
    "manutd": "مانشستر يونايتد", "arsenal": "أرسنال", "chelseafc": "تشيلسي", "FCBayern": "بايرن ميونخ",
    "PSG": "باريس سان جيرمان", "juventus": "يوفنتوس", "inter": "إنتر ميلان", "acmilan": "ميلان",
    "AlNassr": "النصر", "Alhilal": "الهلال", "AlAhlySC": "الأهلي", "premierleague": "الدوري الإنجليزي",
    "LaLiga": "الليغا", "SerieA": "الدوري الإيطالي", "Bundesliga": "البوندسليغا", "championsleague": "دوري أبطال أوروبا",
    "FIFA": "فيفا", "InterMiamiCF": "إنتر ميامي", "UAEProLeague": "دوري أدنوك", "ESPNFC": "ESPN FC",
}


def page(handle_or_id):
    h = handle_or_id.lstrip("@")
    url = f"https://www.youtube.com/channel/{h}" if re.fullmatch(r"UC[0-9A-Za-z_-]{22}", h) else f"https://www.youtube.com/@{urllib.parse.quote(h)}"
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"}), timeout=25).read().decode("utf-8", "replace")


def channel_id(handle):
    html = page(handle)
    # the page's own channel only: the canonical link, else "externalId". A bare "channelId" can be a related channel
    # (@premierleague gave Arsenal's id that way on 2026-09-30).
    m = re.search(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[0-9A-Za-z_-]{22})"', html) or re.search(r'"externalId":"(UC[0-9A-Za-z_-]{22})"', html)
    return m.group(1) if m else None


def facts(handle_or_id):
    """What the channel page says about itself."""
    html = page(handle_or_id)
    g = lambda p: (re.search(p, html) or [None, None])[1]
    cid = g(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[0-9A-Za-z_-]{22})"') or g(r'"externalId":"(UC[0-9A-Za-z_-]{22})"')
    handle = g(r'"vanityChannelUrl":"https?://www\.youtube\.com/(@[^"]+)"')
    desc = g(r'"description":"((?:[^"\\]|\\.){0,300})')
    try:
        desc = json.loads('"' + (desc or "") + '"')
    except ValueError:
        pass
    # YouTube puts its check mark («CHECK_CIRCLE_FILLED», label "Verified") next to the channel's name on its own uploads
    ver = '"name":"CHECK_CIRCLE_FILLED"' in html and '"accessibilityLabel":"Verified"' in html
    return {"id": cid, "title": g(r'<meta property="og:title" content="([^"]*)"'), "handle": handle,
            "subscribers": g(r'"content":"([\d.,]+[KMB]?) subscribers"') or g(r"([\d.,]+[KMB]?) subscribers"),
            "verified": ver, "desc": re.sub(r"\s+", " ", desc or "")[:160]}


def check(args):
    for a in args:
        try:
            f = facts(a)
        except Exception as e:
            print(f"# {a}: {type(e).__name__} {str(e)[:80]}\n"); continue
        items = []
        if f["id"]:
            try:
                items = parse_feed(fetch(f"https://www.youtube.com/feeds/videos.xml?channel_id={f['id']}"), {"key": "yt", "kind": "youtube", "lang": "", "tier": "official", "name": ""})
            except Exception as e:
                print(f"   feed: {type(e).__name__} {str(e)[:60]}")
        print(f"{a}\n   id {f['id']}  {f['handle']}  «{f['title']}»  {f['subscribers']} subscribers  verified={f['verified']}\n   {f['desc']}")
        print(f"   feed: {len(items)} videos, newest {items[0]['at'] if items else '-'}")
        for it in items[:6]:
            print(f"     {it['at'][:16]}  {it['title'][:100]}")
        print()
        time.sleep(1.0)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--check"]:
        sys.stdout.reconfigure(encoding="utf-8")
        check(sys.argv[2:]); sys.exit(0)
    for h, ar in HANDLES.items():
        try:
            cid = channel_id(h)
            if not cid:
                print(f"# {h}: no channel id on the page"); continue
            items = parse_feed(fetch(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"), {"key": "yt", "kind": "youtube", "lang": "", "tier": "official", "name": ar})
            print(f'  - {{key: yt_{h.lower()}, kind: rss, lang: xx, tier: official, name: "{ar}", url: "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"}}   # @{h}, {len(items)} videos, newest {items[0]["at"] if items else "-"}: {items[0]["title"][:50] if items else ""}')
        except Exception as e:
            print(f"# {h}: {type(e).__name__} {str(e)[:60]}")

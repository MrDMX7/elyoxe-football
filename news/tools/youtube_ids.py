"""Resolve official YouTube handles to channel ids and check each channel's public feed (free, no API key).
   python news/tools/youtube_ids.py            # prints yaml lines for sources.yaml
The id is read from the channel page itself (never guessed); a handle that doesn't resolve is reported and left out."""
import re, sys, urllib.request
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


def channel_id(handle):
    html = urllib.request.urlopen(urllib.request.Request(f"https://www.youtube.com/@{handle}", headers={"User-Agent": UA, "Accept-Language": "en"}), timeout=20).read().decode("utf-8", "replace")
    # the page's own channel only: the canonical link, else "externalId". A bare "channelId" can be a related channel
    # (@premierleague gave Arsenal's id that way on 2026-09-30).
    m = re.search(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[0-9A-Za-z_-]{22})"', html) or re.search(r'"externalId":"(UC[0-9A-Za-z_-]{22})"', html)
    return m.group(1) if m else None


if __name__ == "__main__":
    for h, ar in HANDLES.items():
        try:
            cid = channel_id(h)
            if not cid:
                print(f"# {h}: no channel id on the page"); continue
            items = parse_feed(fetch(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"), {"key": "yt", "kind": "youtube", "lang": "", "tier": "official", "name": ar})
            print(f'  - {{key: yt_{h.lower()}, kind: rss, lang: xx, tier: official, name: "{ar}", url: "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"}}   # @{h}, {len(items)} videos, newest {items[0]["at"] if items else "-"}: {items[0]["title"][:50] if items else ""}')
        except Exception as e:
            print(f"# {h}: {type(e).__name__} {str(e)[:60]}")

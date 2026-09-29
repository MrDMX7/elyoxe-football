"""Probe candidate news feeds: does it answer, how many items, how fresh, with images? Prints one line per feed.
   python news/tools/probe_feeds.py            # every candidate below
   python news/tools/probe_feeds.py marca bbc  # just these keys
Stdlib only (RSS 2.0, Atom, Media RSS), so it runs the same on the laptop, the Fold and Lambda."""
import sys, time, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

UA = "Mozilla/5.0 (compatible; TifoNews/0.1; +https://tifo.elyoxe.com)"
GN = lambda q: "https://news.google.com/rss/search?" + urllib.parse.urlencode(q)
CANDIDATES = {
    # Spain
    "marca": "https://e00-marca.uecdn.es/rss/futbol/portada.xml",
    "as": "https://feeds.as.com/mrss-s/pages/as/site/as.com/section/futbol/portada/",
    "mundodeportivo": "https://www.mundodeportivo.com/rss/futbol.xml",
    "sport": "https://www.sport.es/es/rss/futbol/rss.xml",
    # England
    "bbc": "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "sky": "https://www.skysports.com/rss/12040",
    "guardian": "https://www.theguardian.com/football/rss",
    "espn": "https://www.espn.com/espn/rss/soccer/news",
    # France, Italy, Germany
    "lequipe": "https://dwh.lequipe.fr/api/edito/rss?path=/Football/",
    "gazzetta": "https://www.gazzetta.it/rss/calcio.xml",
    "kicker": "https://newsfeed.kicker.de/news/fussball",
    # Arabic
    "alarabiya": "https://www.alarabiya.net/feed/rss2/ar/sport.xml",
    "skynewsarabia": "https://www.skynewsarabia.com/rss/sport.xml",
    "aawsat": "https://aawsat.com/feed/sport",
    "btolat": "https://www.btolat.com/rss",
    "filgoal": "https://www.filgoal.com/rss",
    "emaratalyoum": "https://www.emaratalyoum.com/sports/rss",
    "alittihad": "https://www.alittihad.ae/rss/sports",
    "alkhaleej": "https://www.alkhaleej.ae/rss/sport",
    # Google News, Arabic, per entity (the safety net: any outlet it indexes)
    "gn_uae_league": GN({"q": "دوري أدنوك للمحترفين", "hl": "ar", "gl": "AE", "ceid": "AE:ar"}),
    "gn_messi_ar": GN({"q": "ميسي", "hl": "ar", "gl": "AE", "ceid": "AE:ar"}),
    "gn_transfers_en": GN({"q": "\"here we go\" Fabrizio Romano", "hl": "en-GB", "gl": "GB", "ceid": "GB:en"}),
}
NS = {"atom": "http://www.w3.org/2005/Atom", "media": "http://search.yahoo.com/mrss/"}


def parse(raw):
    root = ET.fromstring(raw)
    items = root.findall(".//item") or root.findall(".//atom:entry", NS)
    out = []
    for it in items:
        t = (it.findtext("title") or it.findtext("atom:title", default="", namespaces=NS) or "").strip()
        d = it.findtext("pubDate") or it.findtext("atom:updated", default="", namespaces=NS) or it.findtext("atom:published", default="", namespaces=NS)
        img = it.find("enclosure") is not None or it.find("media:content", NS) is not None or it.find("media:thumbnail", NS) is not None
        out.append((t, d, img))
    return out


def when(d):
    try:
        return parsedate_to_datetime(d)
    except Exception:
        try:
            return datetime.fromisoformat(d.replace("Z", "+00:00"))
        except Exception:
            return None


def probe(key, url):
    t0 = time.time()
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=20).read()
        items = parse(raw)
        ds = [w for w in (when(d) for _, d, _ in items) if w]
        newest = max(ds) if ds else None
        age = f"{(datetime.now(timezone.utc) - newest).total_seconds() / 3600:.1f}h" if newest else "?"
        print(f"OK   {key:16} {len(items):3} items  newest {age:>7}  images {sum(1 for *_, i in items if i):3}  {time.time() - t0:.1f}s  | {items[0][0][:70] if items else ''}")
    except Exception as e:
        print(f"FAIL {key:16} {type(e).__name__}: {str(e)[:80]}")


if __name__ == "__main__":
    keys = sys.argv[1:] or list(CANDIDATES)
    for k in keys:
        probe(k, CANDIDATES[k])

"""Readers: every source kind returns the same item shape.

  {id, src, kind, lang, tier, source, title, desc, url, at, image, query}

`id` is a hash of the canonical URL, so the same article from two queries or two runs is one item.
Stdlib only (RSS 2.0, Atom, Media RSS); a failing source is reported and skipped, never fatal."""
import hashlib, html, os, re, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

UA = "Mozilla/5.0 (compatible; TifoNews/1.0; +https://tifo.elyoxe.com)"
NS = {"atom": "http://www.w3.org/2005/Atom", "media": "http://search.yahoo.com/mrss/"}
TAG = re.compile(r"<[^>]+>")


def _when(d):
    if not d:
        return None
    try:
        w = parsedate_to_datetime(d)
    except Exception:
        try:
            w = datetime.fromisoformat(d.strip().replace("Z", "+00:00"))
        except Exception:
            return None
    return (w if w.tzinfo else w.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def _clean(s, n=None):
    s = re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", html.unescape(s or "")))).strip()
    return s[:n] if n else s


def canonical(url):
    p = urllib.parse.urlsplit((url or "").strip())
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query) if not k.lower().startswith(("utm_", "fbclid", "gclid", "ns_", "at_"))]
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), urllib.parse.urlencode(q), ""))


def item_id(url):
    return hashlib.sha1(canonical(url).encode()).hexdigest()[:16]


def parse_feed(raw, src):
    """Feed bytes -> items for the source dict `src` (key, kind, lang, tier, name)."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        raw = re.sub(rb"&(?!(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)", b"&amp;", raw)   # a stray & breaks the whole feed
        root = ET.fromstring(raw)
    entries = root.findall(".//item") or root.findall(".//atom:entry", NS)
    out = []
    for it in entries:
        title = _clean(it.findtext("title") or it.findtext("atom:title", default="", namespaces=NS))
        link = (it.findtext("link") or "").strip()
        if not link:
            a = it.find("atom:link", NS)
            link = a.get("href") if a is not None else ""
        if not title or not link:
            continue
        desc = _clean(it.findtext("description") or it.findtext("atom:summary", default="", namespaces=NS), 400)
        at = _when(it.findtext("pubDate") or it.findtext("atom:published", default="", namespaces=NS) or it.findtext("atom:updated", default="", namespaces=NS))
        img = None
        for el in (it.find("media:content", NS), it.find("media:thumbnail", NS), it.find("enclosure")):
            if el is not None and el.get("url") and (el.get("type") or "image").startswith("image"):
                img = el.get("url"); break
        if src["kind"] == "youtube":         # the Atom thumbnail sits inside media:group; the video id gives the same picture
            m = re.search(r"(?:v=|/shorts/)([\w-]{11})", link)
            img = f"https://i.ytimg.com/vi/{m.group(1)}/hqdefault.jpg" if m else img
            desc = _clean(it.findtext("media:group/media:description", default="", namespaces=NS), 400)
        source = src["name"]
        if src["kind"] == "gnews":           # «العنوان - البيان»: the outlet is the last « - » part
            m = re.match(r"^(.*\S)\s+-\s+([^-]{2,60})$", title)
            if m:
                title, source = m.group(1), m.group(2).strip()
            desc = ""                        # Google's description repeats the title plus other outlets
        out.append({"id": item_id(link), "src": src["key"], "kind": src["kind"], "lang": src["lang"], "tier": src["tier"],
                    "source": source, "title": title[:300], "desc": desc, "url": link, "image": img,
                    "at": at.isoformat().replace("+00:00", "Z") if at else None, "query": src.get("query"), "owner": src.get("owner")})
    return out


def fetch(url, timeout=20):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout).read()


def read_source(src):
    """One source (rss or a gnews query) -> (items, error or None)."""
    try:
        return parse_feed(fetch(src["url"]), src), None
    except Exception as e:
        return [], f"{type(e).__name__}: {str(e)[:120]}"


def youtube_source(y):
    """A `youtube:` entry of sources.yaml -> a source; `owner` is the club or league the channel belongs to."""
    owner = ["team", int(y["team"])] if y.get("team") else (["comp", int(y["comp"])] if y.get("comp") else None)
    return {"key": y["key"], "kind": "youtube", "lang": y.get("lang", "en"), "tier": "official", "name": y["name"], "owner": owner,
            "url": "https://www.youtube.com/feeds/videos.xml?channel_id=" + y["channel"]}


def x_posts(box):
    """The posts news/xreader.js collected ({"items": [...]}, from S3 or a local file) -> items. Nothing is emptied: the
    reader keeps its last 800 posts and run.py skips the ids it already holds. A club's or league's account carries its
    owner like a YouTube channel."""
    out = []
    for p in (box or {}).get("items") or []:
        txt = _clean(p.get("text") or "")
        if not txt:
            continue
        first = re.split(r"(?<=[.!?؟])\s", txt)[0]
        owner = ["team", int(p["team"])] if p.get("team") else (["comp", int(p["comp"])] if p.get("comp") else None)
        out.append({"id": item_id(p["url"]), "src": "x_" + p["handle"].lower(), "kind": "x", "lang": p.get("lang", "en"),
                    "tier": p.get("tier", "journalist"), "source": p.get("source") or p.get("name") or p["handle"],
                    "title": (first if 25 <= len(first) <= 300 else txt)[:300], "desc": txt[:400], "url": p["url"],
                    "image": p.get("image"), "at": p.get("at"), "query": None, "owner": owner})
    return out


def gnews_source(query, cfg):
    params = dict(cfg.get("params") or {}, q=query)
    return {"key": "gnews", "kind": "gnews", "lang": cfg.get("lang", "ar"), "tier": "aggregator", "name": "Google News",
            "query": query, "url": "https://news.google.com/rss/search?" + urllib.parse.urlencode(params)}

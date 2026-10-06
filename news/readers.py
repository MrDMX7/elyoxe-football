"""Readers: every source kind returns the same item shape.

  {id, src, kind, lang, tier, source, title, desc, url, at, image, query}

`id` is a hash of the canonical URL, so the same article from two queries or two runs is one item.
Stdlib only (RSS 2.0, Atom, Media RSS); a failing source is reported and skipped, never fatal."""
import gzip, hashlib, html, json, os, re, threading, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
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
    """One source (rss or a gnews query) -> (items, error or None). A YouTube channel whose feed fails is read from its own
    pages (youtube_page)."""
    try:
        return parse_feed(fetch(src["url"]), src), None
    except Exception as e:
        err = f"{type(e).__name__}: {str(e)[:120]}"
    if src.get("kind") == "youtube":
        try:
            return youtube_page(src), None
        except Exception as e:
            return [], f"{err}; page: {type(e).__name__}: {str(e)[:80]}"
    return [], err


# ------------------------------------------------------------------ YouTube without its feed
# YouTube's /feeds/videos.xml answered 404 for every channel from 2026-10-06 ~03:00 UTC (a platform-wide outage, on and off
# since 10-04; YouTube's own channel too, from two networks), which emptied the goal videos and the clubs' video news.
# The channel's Videos tab gives each video's age («4 days ago»), its Shorts tab none; both are public pages, read like a
# visitor would (no key, no sign-in). A video keeps the time of its first sighting, so an age rounded to the hour or the
# day does not drift between runs; a short counts from the run that first saw it (the journal reads every 15 min), and the
# shorts already up when a channel is first read this way are recorded without a time and never listed.
YT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
YT_SEEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "yt-seen.json")
AGO = re.compile(r"(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago", re.I)
UNIT = {"second": 1, "minute": 60, "hour": 3600, "day": 86400, "week": 7 * 86400, "month": 30 * 86400, "year": 365 * 86400}
_SEEN, _LOCK = {}, threading.Lock()     # vid -> first-seen ISO time ("?<time>": up before our first read); "ch:<id>:shorts" -> read


def _iso(t):
    return t.astimezone(timezone.utc).isoformat()[:19] + "Z"


def _seen():
    if not _SEEN:
        try:
            _SEEN.update(json.load(open(YT_SEEN, encoding="utf-8")))
        except (OSError, ValueError):
            _SEEN["_"] = "loaded"
    return _SEEN


def _save_seen(now):
    cut = _iso(now - timedelta(days=45))
    for k in [k for k, v in _SEEN.items() if k != "_" and isinstance(v, str) and v.lstrip("?") < cut]:
        del _SEEN[k]
    os.makedirs(os.path.dirname(YT_SEEN), exist_ok=True)
    tmp = YT_SEEN + f".{threading.get_ident()}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(_SEEN, f)
    os.replace(tmp, YT_SEEN)


def _yt_html(cid, tab, timeout=20):
    req = urllib.request.Request(f"https://www.youtube.com/channel/{cid}/{tab}?hl=en&gl=US",
                                 headers={"User-Agent": YT_UA, "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "gzip"})
    r = urllib.request.urlopen(req, timeout=timeout)
    b = r.read()
    return (gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b).decode("utf-8", "replace")


def _yt_data(page):
    m = re.search(r"var ytInitialData\s*=\s*(\{.*?\});\s*</script>", page, re.S)
    if not m:
        raise ValueError("no ytInitialData (a consent or check page)")
    return json.loads(m.group(1))


def _all(o, key, out):
    if isinstance(o, dict):
        if key in o:
            out.append(o[key])
            return out
        for v in o.values():
            _all(v, key, out)
    elif isinstance(o, list):
        for v in o:
            _all(v, key, out)
    return out


def youtube_page(src, now=None):
    """A channel's Videos and Shorts tabs -> items in parse_feed's shape (same URLs as the feed's, so the same ids)."""
    cid = urllib.parse.parse_qs(urllib.parse.urlsplit(src["url"]).query).get("channel_id", [""])[0]
    if not cid:
        raise ValueError("no channel id")
    now = now or datetime.now(timezone.utc)
    vids = _all(_yt_data(_yt_html(cid, "videos")), "lockupViewModel", [])
    try:
        shorts = _all(_yt_data(_yt_html(cid, "shorts")), "shortsLockupViewModel", [])
    except Exception:
        shorts = None                    # the videos are worth listing alone
    out = []

    def add(vid, title, at, link):
        out.append({"id": item_id(link), "src": src["key"], "kind": "youtube", "lang": src["lang"], "tier": src["tier"],
                    "source": src["name"], "title": title[:300], "desc": "", "url": link,
                    "image": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg", "at": at, "query": src.get("query"), "owner": src.get("owner")})
    with _LOCK:
        seen = _seen()
        for lv in vids:
            md = (lv.get("metadata") or {}).get("lockupMetadataViewModel") or {}
            vid, title = lv.get("contentId"), ((md.get("title") or {}).get("content") or "").strip()
            if not vid or not title or lv.get("contentType") not in (None, "LOCKUP_CONTENT_TYPE_VIDEO"):
                continue
            ago = None
            for row in ((md.get("metadata") or {}).get("contentMetadataViewModel") or {}).get("metadataRows") or []:
                for part in row.get("metadataParts") or []:
                    m = AGO.search(part.get("accessibilityLabel") or (part.get("text") or {}).get("content") or "")
                    if m:
                        ago = int(m.group(1)) * UNIT[m.group(2).lower()]
            if ago is None:              # live now, or a premiere still ahead
                continue
            seen.setdefault(vid, _iso(now - timedelta(seconds=ago)))
            if not seen[vid].startswith("?"):
                add(vid, title, seen[vid], "https://www.youtube.com/watch?v=" + vid)
        if shorts is not None:
            first = f"ch:{cid}:shorts" not in seen
            for sh in shorts:
                vid = ((((sh.get("onTap") or {}).get("innertubeCommand") or {}).get("reelWatchEndpoint")) or {}).get("videoId")
                title = (((sh.get("overlayMetadata") or {}).get("primaryText") or {}).get("content") or "").strip()
                if not vid or not title:
                    continue
                seen.setdefault(vid, ("?" if first else "") + _iso(now))
                if not seen[vid].startswith("?"):
                    add(vid, title, seen[vid], "https://www.youtube.com/shorts/" + vid)
            seen[f"ch:{cid}:shorts"] = _iso(now)
        _save_seen(now)
    return out


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

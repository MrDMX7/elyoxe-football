"""Stage `awards` (weekly, before `graph`; spec §7.4): every article under English Wikipedia's football award categories and
the article of each of our competitions, kept as HTML, and the Wikidata facts of every person, club and award its award
tables link (human?, birth date, Arabic and English labels, Transfermarkt player and club ids). The graph's `awards` loader
reads only these files.

    python -m graph.awards_fetch [--upload] [--limit N]

Files (graph/.cache/awards/, and S3 state/graph/awards/cache.tar.gz between runs):
  pages/<sha1>.html.gz   an article's Parsoid HTML (refetched after 30 days; a failed fetch keeps the last copy)
  pages.json             {title: {"fetched": "YYYY-MM-DD", "sha": ...}}
  items.json             {link title: {"qid", "human", "born", "ar", "en", "tm_player", "tm_club"}}
  comps.json             {FotMob competition id: article title} (db/champions.py's competition items -> enwiki)
  articles.json          {"awards": [titles], "comps": {fid: title}} the last crawl
At most one request a second to each of Wikipedia and Wikidata.
"""
import argparse, gzip, hashlib, io, json, os, sys, tarfile, time, urllib.parse, urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
CACHE = os.path.join(HERE, ".cache", "awards")
REST = "https://en.wikipedia.org/api/rest_v1/page/html/"
API = "https://en.wikipedia.org/w/api.php"
WD = "https://www.wikidata.org/w/api.php"
UA = {"User-Agent": "elyoxe-tifo/0.1 (hello@elyoxe.com)"}
ROOTS = ["Category:Association football player of the year awards", "Category:Association football top scorer awards",
         "Category:Association football goalkeeper awards", "Category:Association football young player of the year awards",
         "Category:Association football manager of the year awards", "Category:Association football player awards",
         "Category:Association football trophies and awards"]
STATE_KEY = "state/graph/awards/cache.tar.gz"
SEASON_BUDGET = 1500            # new season articles a run (a first run would otherwise take hours): the rest come the next weeks


class HTTP:
    def __init__(self, gap=1.0):
        self.gap, self.last = gap, {}

    def get(self, url):
        host = urllib.parse.urlparse(url).netloc
        wait = self.gap - (time.time() - self.last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        err = None
        for attempt in range(3):
            try:
                self.last[host] = time.time()
                return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    raise
                err = e
            except OSError as e:
                err = e
            time.sleep(3 * (attempt + 1))
        raise err


def _key(title):
    return hashlib.sha1(title.replace(" ", "_").encode("utf-8")).hexdigest()


def _jload(p, default):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _jsave(p, obj):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, p)


def read_page(d, title):
    p = os.path.join(d, "pages", _key(title) + ".html.gz")
    try:
        return gzip.decompress(open(p, "rb").read())
    except OSError:
        return None


def fetch_pages(http, d, titles, max_age_days=30):
    os.makedirs(os.path.join(d, "pages"), exist_ok=True)
    idx = _jload(os.path.join(d, "pages.json"), {})
    today = date.today()
    n = {"fetched": 0, "kept": 0, "failed": 0}
    for t in titles:
        rec = idx.get(t) or {}
        if rec.get("fetched") and max_age_days and (today - date.fromisoformat(rec["fetched"])).days < max_age_days and read_page(d, t) is not None:
            n["kept"] += 1
            continue
        try:
            body = http.get(REST + urllib.parse.quote(t.replace(" ", "_"), safe="'(),!"))
        except Exception as e:
            n["failed"] += 1
            continue
        p = os.path.join(d, "pages", _key(t) + ".html.gz")
        with open(p + ".tmp", "wb") as f:
            f.write(gzip.compress(body, mtime=0))
        os.replace(p + ".tmp", p)
        idx[t] = {"fetched": str(today), "sha": hashlib.sha1(body).hexdigest()[:12]}
        n["fetched"] += 1
        if n["fetched"] % 50 == 0:
            _jsave(os.path.join(d, "pages.json"), idx)
            print(f"awards pages: {n}", flush=True)
    _jsave(os.path.join(d, "pages.json"), idx)
    return n


def crawl(http, roots=ROOTS, depth=2):
    seen, pages = set(), set()

    def walk(cat, dep):
        if cat in seen or dep < 0:
            return
        seen.add(cat)
        cont = {}
        while True:
            q = {"action": "query", "list": "categorymembers", "cmtitle": cat, "cmlimit": "500", "format": "json", **cont}
            d = json.loads(http.get(API + "?" + urllib.parse.urlencode(q)))
            for m in d.get("query", {}).get("categorymembers", []):
                if m["ns"] == 14:
                    walk(m["title"], dep - 1)
                elif m["ns"] == 0:
                    pages.add(m["title"])
            if "continue" not in d:
                break
            cont = d["continue"]

    for r in roots:
        walk(r, depth)
    return sorted(pages)


def _claim(c, prop):
    for st in (c.get(prop) or []):
        v = ((st.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if v is not None:
            return v
    return None


def resolve(http, d, titles):
    """{title: facts} for every title, asking only the ones items.json lacks."""
    p = os.path.join(d, "items.json")
    items = _jload(p, {})
    new = sorted({t for t in titles if t and t not in items})
    for i in range(0, len(new), 50):
        batch = new[i:i + 50]
        q = {"action": "query", "prop": "pageprops", "ppprop": "wikibase_item", "redirects": "1", "format": "json", "formatversion": "2",
             "titles": "|".join(t.replace("_", " ") for t in batch)}
        try:
            r = json.loads(http.get(API + "?" + urllib.parse.urlencode(q)))
        except Exception as e:
            print(f"pageprops: {e}", flush=True)
            continue
        qr = r.get("query") or {}
        alias = {}
        for k in ("normalized", "redirects"):
            for x in qr.get(k) or []:
                alias[x["from"]] = x["to"]
        qid_of = {pg["title"]: (pg.get("pageprops") or {}).get("wikibase_item") for pg in qr.get("pages") or []}
        got = {}
        for t in batch:
            name = t.replace("_", " ")
            for _ in range(3):
                name = alias.get(name, name)
            got[t] = qid_of.get(name)
        ids = sorted({q for q in got.values() if q})
        facts = {}
        for j in range(0, len(ids), 50):
            q2 = {"action": "wbgetentities", "ids": "|".join(ids[j:j + 50]), "props": "labels|claims", "languages": "ar|en", "format": "json"}
            try:
                ents = json.loads(http.get(WD + "?" + urllib.parse.urlencode(q2))).get("entities") or {}
            except Exception as e:
                print(f"wbgetentities: {e}", flush=True)
                continue
            for qid, e in ents.items():
                c, lab = e.get("claims") or {}, e.get("labels") or {}
                born = _claim(c, "P569")
                facts[qid] = {"qid": qid, "human": (_claim(c, "P31") or {}).get("id") == "Q5" or any(
                    ((s.get("mainsnak") or {}).get("datavalue") or {}).get("value", {}).get("id") == "Q5" for s in c.get("P31") or []),
                              "born": born["time"][1:11] if isinstance(born, dict) and born.get("time") else None,
                              "ar": (lab.get("ar") or {}).get("value"), "en": (lab.get("en") or {}).get("value"),
                              "tm_player": _claim(c, "P2446"), "tm_club": _claim(c, "P7223")}
        for t, qid in got.items():
            items[t] = facts.get(qid) or {"qid": qid, "human": False, "born": None, "ar": None, "en": None, "tm_player": None, "tm_club": None}
        if (i // 50) % 20 == 0:
            _jsave(p, items)
            print(f"awards items: {len(items)}", flush=True)
    _jsave(p, items)
    return items


def comp_articles(S, http):
    """{FotMob competition id: enwiki title} from db/champions.py's competition items."""
    st = S.store()
    keys = [o["Key"] for page in st.b.s3.get_paginator("list_objects_v2").paginate(Bucket=st.b.bucket, Prefix="v1/history/champions/")
            for o in page.get("Contents", [])]
    qids = {}
    for k in keys:
        fid = k.rsplit("/", 1)[1].split(".")[0]
        if fid.isdigit():
            d = S.published(f"history/champions/{fid}.json") or {}
            if d.get("qid"):
                qids[d["qid"]] = fid
    out, ids = {}, sorted(qids)
    for j in range(0, len(ids), 50):
        q = {"action": "wbgetentities", "ids": "|".join(ids[j:j + 50]), "props": "sitelinks", "sitefilter": "enwiki", "format": "json"}
        for qid, e in (json.loads(http.get(WD + "?" + urllib.parse.urlencode(q))).get("entities") or {}).items():
            t = ((e.get("sitelinks") or {}).get("enwiki") or {}).get("title")
            if t:
                out[qids[qid]] = t
    return out


def pick_seasons(links, have, budget=SEASON_BUDGET):
    """{season article: FotMob competition id}: every article already kept, plus up to `budget` new ones, the competitions
    taking turns (each competition's links newest first, as its article lists them), so every league moves forward."""
    out, queues, new = {}, {fid: list(v) for fid, v in sorted(links.items())}, 0
    while any(queues.values()):
        for fid in sorted(queues):
            if not queues[fid]:
                continue
            t = queues[fid].pop(0)
            if t in have:
                out[t] = fid
            elif new < budget:
                out[t] = fid
                new += 1
    return out


def run(S, http, d, limit=None):
    from graph.awards_wiki import extract
    os.makedirs(d, exist_ok=True)
    prev = _jload(os.path.join(d, "articles.json"), {})
    try:
        awards = crawl(http)
    except Exception as e:
        print(f"crawl failed ({e}); the last crawl's articles", flush=True)
        awards = prev.get("awards") or []
    try:
        comps = comp_articles(S, http)
    except Exception as e:
        print(f"competition articles failed ({e}); the last ones", flush=True)
        comps = prev.get("comps") or {}
    if not awards and prev.get("awards"):
        awards = prev["awards"]
    from graph.awards_wiki import national_articles, intl_records
    try:                                      # every men's national team: its caps and goals records (graph/load/intl_records.py)
        national = national_articles(http.get(REST + urllib.parse.quote("List_of_men's_national_association_football_teams")))
    except Exception as e:
        print(f"national teams list failed ({e}); the last one", flush=True)
        national = prev.get("national") or []
    titles = sorted(set(awards) | set(comps.values()) | set(national))
    if limit:
        titles = titles[:limit]
    _jsave(os.path.join(d, "articles.json"), {"awards": awards, "comps": comps, "national": national})
    n = fetch_pages(http, d, titles)
    from graph.awards_wiki import season_links, extract_season
    have = set(_jload(os.path.join(d, "pages.json"), {}))
    seasons = pick_seasons({fid: season_links(read_page(d, t) or b"") for fid, t in comps.items()}, have)
    seasons = {**(prev.get("seasons") or {}), **seasons}
    n["seasons"] = fetch_pages(http, d, sorted(seasons))
    _jsave(os.path.join(d, "articles.json"), {"awards": awards, "comps": comps, "seasons": seasons, "national": national})
    links = set(titles)
    for t in seasons:
        h = read_page(d, t)
        if h:
            links.update(x for r in extract_season(h, t)["rows"] for x in (r.get("person"), r.get("team")) if x)
    for t in titles:
        h = read_page(d, t)
        if not h:
            continue
        for tb in extract(h, t):
            for r in tb["rows"]:
                links.update(x for x in (r.get("person"), r.get("team"), r.get("runner_up")) if x)
    for t in national:
        h = read_page(d, t)
        if h:
            links.update(r["person"] for r in intl_records(h))
    items = resolve(http, d, sorted(links))
    return {"articles": len(titles), **n, "items": len(items), "humans": sum(1 for v in items.values() if v.get("human"))}


def _tar(d):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        tf.add(d, arcname="awards")
    return buf.getvalue()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args(argv)
    from graph.src import Sources
    S = Sources()
    st = S.store() if a.upload else None
    if st and not os.path.exists(os.path.join(CACHE, "items.json")):
        try:
            raw = st.b.s3.get_object(Bucket=st.b.bucket, Key=STATE_KEY)["Body"].read()
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
                tf.extractall(os.path.dirname(CACHE), filter="data")
            print("awards cache restored from S3", flush=True)
        except Exception as e:
            print(f"no awards cache in S3 ({type(e).__name__})", flush=True)
    out = run(S, HTTP(), CACHE, limit=a.limit)
    print(json.dumps(out), flush=True)
    if st:
        st.b.s3.put_object(Bucket=st.b.bucket, Key=STATE_KEY, Body=_tar(CACHE), ContentType="application/gzip")
    return 0


if __name__ == "__main__":
    sys.exit(main())


def restore(S, d=CACHE):
    """The last stage run's cache from S3 (the graph build runs on days the weekly stage does not)."""
    try:
        st = S.store()
        raw = st.b.s3.get_object(Bucket=st.b.bucket, Key=STATE_KEY)["Body"].read()
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
            tf.extractall(os.path.dirname(d), filter="data")
        return True
    except Exception as e:
        print(f"no awards cache in S3 ({type(e).__name__})", flush=True)
        return False

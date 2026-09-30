"""Arabic Wikipedia's lead for every club and player we can tie to a Wikidata item (owner 2026-09-30: «كل الخانات تكون
كاملة»): players from the photo pipeline's identity check (state/photos.json: the Wikidata footballer whose birth date is
FotMob's), clubs from db/clubs.py's cards.

    python -m db.wiki_ar [--upload]

Wikidata gives the Arabic article (schema:about), Wikipedia's REST summary its lead; disambiguation pages are skipped.
Out (public): v1/history/wiki_ar.json {"players": {fotmob id: [title, lead]}, "clubs": {fotmob id: [title, lead]}}
Cache: db/.cache/wiki_ar.json (each lead kept 30 days).
"""
import argparse, gzip, json, os, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from store import Store, S3Backend  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
CACHE = os.path.join(HERE, ".cache", "wiki_ar.json")
UA = "TifoBot/1.0 (https://tifo.elyoxe.com; hello@elyoxe.com)"
BAD = ("unverified", "birth date differs")


def http_json(url, data=None, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Accept": "application/json", "Accept-Encoding": "gzip"})
            r = urllib.request.urlopen(req, timeout=60)
            b = r.read()
            return json.loads(gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 + 4 * i)
        except Exception:
            time.sleep(2 + 4 * i)
    return None


def articles(qids):
    """qid -> Arabic Wikipedia title."""
    out, qs = {}, sorted(set(qids))
    for i in range(0, len(qs), 300):
        vals = " ".join("wd:" + q for q in qs[i:i + 300])
        q = "SELECT ?item ?t WHERE { VALUES ?item { %s } ?a schema:about ?item; schema:isPartOf <https://ar.wikipedia.org/>; schema:name ?t }" % vals
        d = http_json("https://query.wikidata.org/sparql", data=urllib.parse.urlencode({"query": q, "format": "json"}).encode())
        for b in ((d or {}).get("results") or {}).get("bindings") or []:
            out[b["item"]["value"].rsplit("/", 1)[1]] = b["t"]["value"]
        time.sleep(1)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); a = ap.parse_args(argv)
    store = Store(S3Backend(BUCKET))
    ph = store.get_state("photos.json") or {}
    pq = {k: v["qid"] for k, v in ph.items() if isinstance(v, dict) and v.get("qid") and not str(v.get("status") or "").startswith(BAD)}
    try:
        r = urllib.request.urlopen(urllib.request.Request("https://tifo.elyoxe.com/v1/history/clubs.json", headers={"User-Agent": UA, "Accept-Encoding": "gzip"}), timeout=120)
        b = r.read(); cl = json.loads(gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b).get("clubs") or {}
    except Exception as e:
        print("no club cards", e); cl = {}
    cq = {k: v["qid"] for k, v in cl.items() if v.get("qid")}
    print(len(pq), "players and", len(cq), "clubs with a Wikidata item")
    titles = articles(list(pq.values()) + list(cq.values()))
    print(len(titles), "with an Arabic article")
    cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    now = time.time()
    todo = [t for t in set(titles.values()) if not (t in cache and now - cache[t][1] < 30 * 86400)]

    def lead(t):
        d = http_json("https://ar.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(t.replace(" ", "_"), safe=""))
        if not d or d.get("type") == "disambiguation":
            return t, ""
        return t, (d.get("extract") or "").strip()
    t0 = time.time()
    with ThreadPoolExecutor(6) as ex:
        for t, x in ex.map(lead, todo):
            cache[t] = [x, now]
    print(f"{len(todo)} leads fetched ({round(time.time() - t0)}s)")
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(cache, open(CACHE, "w", encoding="utf-8", newline="\n"), ensure_ascii=False)
    pick = lambda m: {k: [titles[q], cache[titles[q]][0]] for k, q in m.items() if q in titles and cache.get(titles[q], [""])[0]}
    out = {"generated": date.today().isoformat(), "players": pick(pq), "clubs": pick(cq)}
    print(len(out["players"]), "players and", len(out["clubs"]), "clubs with a lead")
    if a.upload:
        store.put_json("history/wiki_ar.json", out, cache="warm")
        print("uploaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())

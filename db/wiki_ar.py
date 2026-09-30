"""Arabic Wikipedia's lead for every club and player we can tie to a Wikidata item (owner 2026-09-30: «كل الخانات تكون
كاملة»): players from the photo pipeline's identity check (state/photos.json: the Wikidata footballer whose birth date is
FotMob's), clubs from db/clubs.py's cards.
A player gets a lead only when that check passed (identity «ok»; before photos/build.py wrote it, the statuses «ok» and
«no clear face»: an item with no picture was never checked), never when two FotMob players point at one item, and never
when the lead's own birth year («ولد في … 1953») is another than FotMob's.

    python -m db.wiki_ar [--upload]

Wikidata gives the Arabic article (schema:about), Wikipedia's REST summary its lead; disambiguation pages are skipped.
Out (public): v1/history/wiki_ar.json {"players": {fotmob id: [title, lead]}, "clubs": {fotmob id: [title, lead]}}
Cache: db/.cache/wiki_ar.json (each lead kept 30 days).
"""
import argparse, gzip, json, os, re, sys, time, urllib.parse, urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from store import Store, S3Backend  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
CACHE = os.path.join(HERE, ".cache", "wiki_ar.json")
UA = "TifoBot/1.0 (https://tifo.elyoxe.com; hello@elyoxe.com)"
PASSED = ("ok", "no clear face")        # photo statuses reached only after the identity check passed
BORN = re.compile(r"(?:ولد|وُلد|مواليد|مولود|ولدت)[^0-9٠-٩]{0,40}?([0-9٠-٩]{4})")


def verified(v):
    return v.get("identity") == "ok" if "identity" in v else str(v.get("status") or "") in PASSED


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
    pq = {k: v["qid"] for k, v in ph.items() if isinstance(v, dict) and v.get("qid") and verified(v)}
    shared = {q for q, n in Counter(pq.values()).items() if n > 1}      # two FotMob players on one item: at most one is it
    pq = {k: q for k, q in pq.items() if q not in shared}
    print(len(shared), "items shared by two FotMob players left out")
    cl = (store.get_json("history/clubs.json") or {}).get("clubs") or {}
    cq = {k: v["qid"] for k, v in cl.items() if v.get("qid")}
    born = {k: (v.get("born") or "")[:4] for k, v in ((store.get_json("history/fm/players.json") or {}).get("players") or {}).items()}
    for k, v in ((store.get_json("world/bios.json") or {}).get("players") or {}).items():
        born.setdefault(k, (v[1] or "")[:4])
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

    def lead_year(t):
        m = BORN.search((t or "").translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
        return m.group(1) if m else None
    players = pick(pq)
    other = [k for k, (t, x) in players.items() if lead_year(x) and born.get(k, "") >= "1900" and abs(int(lead_year(x)) - int(born[k])) > 1]
    for k in other:
        del players[k]
    print(len(other), "player leads left out: the lead's birth year is another than FotMob's")
    out = {"generated": date.today().isoformat(), "players": players, "clubs": pick(cq)}
    print(len(out["players"]), "players and", len(out["clubs"]), "clubs with a lead")
    if a.upload:
        store.put_json("history/wiki_ar.json", out, cache="warm")
        print("uploaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())

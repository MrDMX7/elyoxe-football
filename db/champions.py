"""Every competition's champions through history, stage 4 of the owner's database (2026-09-30 «كلها»).

    python -m db.champions [--upload] [--report]

1. Wikidata (CC0): each of our competitions is matched to its Wikidata item (English name, then the item's country);
   every season/edition whose «season of» (P3450) is that item and that has a winner (P1346) gives [season, winner].
2. The winner is linked back to a FotMob club through db/clubs.py's cards (same Wikidata item) when it is one of ours.
Coverage is reported per competition (--report) so the gaps can be filled from RSSSF / Wikipedia tables next.
Out: v1/history/champions/<comp id>.json {champions: [[year, winner qid, name_ar|en, fotmob id|null]], counts}.
"""
import argparse, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request
from collections import Counter
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from store import Store, S3Backend  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
UA = {"User-Agent": "elyoxe-tifo/0.1 (https://tifo.elyoxe.com; hello@elyoxe.com)", "Accept": "application/json"}
# our competitions whose English name differs from their Wikidata label, or that need the item fixed by hand (verified ids)
FIXED = {}
SEARCH = {268: "Campeonato Brasileiro Série A", 50: "UEFA European Championship", 329: "Arabian Gulf Cup", 10242: "FIFA Arab Cup",
          10474: "Arab Club Champions Cup", 516: "Algerian Ligue Professionnelle 1", 544: "Tunisian Ligue Professionnelle 1",
          529: "Kuwaiti Premier League", 11840: "Moroccan Throne Cup", 11018: "Emir of Qatar Cup", 10074: "Saudi Super Cup",
          11026: "UAE Super Cup", 10314: "Egyptian Super Cup", 11027: "UAE League Cup", 10043: "Leagues Cup", 10703: "FIFA Intercontinental Cup",
          9806: "UEFA Nations League", 112: "Argentine Primera División", 538: "UAE Pro League", 519: "Egyptian Premier League"}
# leagues decided by one points table (no play-offs, no split): recent champions can be computed from our own archive
TABLE_LEAGUES = {47, 87, 55, 54, 53, 536, 538, 535, 530, 268, 516}


def table_champions(store, cid):
    """{season end year: FotMob club id} for a league from v1/archive/all/<season>.json: 3 points a win, then goal
    difference, then goals. Only complete seasons (the season's last match is in the past)."""
    out = {}
    for y in range(2010, date.today().year + 1):
        d = store.get_json(f"archive/all/{y}-{y + 1}.json") or {}
        ms = [m for m in d.get("matches") or [] if m[2] == cid and m[5] is not None]
        if len(ms) < 50 or max(m[1] for m in ms) > date.today().isoformat() or (date.today().isoformat() < f"{y + 1}-07-01"):
            continue
        pts = {}
        for m in ms:
            for t, gf, ga in ((m[3], m[5], m[6]), (m[4], m[6], m[5])):
                r = pts.setdefault(t, [0, 0, 0]); r[0] += 3 if gf > ga else 1 if gf == ga else 0; r[1] += gf - ga; r[2] += gf
        out[str(y + 1)] = max(pts, key=lambda t: pts[t])
    return out


def sparql(q):
    for i in range(4):
        try:
            data = urllib.parse.urlencode({"query": q, "format": "json"}).encode()
            return json.loads(urllib.request.urlopen(urllib.request.Request("https://query.wikidata.org/sparql", data=data, headers=UA), timeout=180).read())["results"]["bindings"]
        except Exception:
            if i == 3:
                raise
            time.sleep(15 * (i + 1))


def search(name):
    u = "https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({"action": "wbsearchentities", "search": name, "language": "en", "type": "item", "limit": 7, "format": "json"})
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read()).get("search", [])


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); ap.add_argument("--report", action="store_true"); a = ap.parse_args(argv)
    store = Store(S3Backend(BUCKET))
    comps = (store.get_json("index.json") or {}).get("competitions") or []
    cards = ((store.get_json("history/clubs.json") or {}).get("clubs")) or {}
    by_qid = {c["qid"]: int(k) for k, c in cards.items() if c.get("qid")}
    teams = (store.get_json("teams.json") or {}).get("teams") or {}
    report, out = [], {}
    for c in comps:
        cid, en = c["id"], c.get("name_en") or ""
        qid = FIXED.get(cid)
        if not qid:
            # the first search hit that has seasons with winners
            cc = (c.get("country") or {}).get("iso2")
            for h in search(SEARCH.get(cid, en))[:5]:
                # a national league must be in its country (Brazil's «Série A» is not Italy's); GB-ENG -> GB
                if cc and not sparql("SELECT ?x WHERE { wd:%s wdt:P17 ?x. ?x wdt:P297 \"%s\" } LIMIT 1" % (h["id"], cc.split("-")[0])):
                    continue
                n = sparql("SELECT (COUNT(?e) AS ?n) WHERE { ?e wdt:P3450 wd:%s; wdt:P1346 ?w }" % h["id"])
                if n and int(n[0]["n"]["value"]) >= 3:
                    qid = h["id"]; break
                time.sleep(0.3)
        if not qid:
            report.append((cid, en, None, 0)); continue
        rows = sparql("""SELECT ?e ?eL ?w ?wAr ?wEn ?when WHERE { ?e wdt:P3450 wd:%s; wdt:P1346 ?w. OPTIONAL { ?e wdt:P582 ?end } OPTIONAL { ?e wdt:P585 ?pt }
            OPTIONAL { ?e wdt:P580 ?st } BIND(COALESCE(?end, ?pt, ?st) AS ?when) ?e rdfs:label ?eL FILTER(LANG(?eL)='en')
            OPTIONAL { ?w rdfs:label ?wAr FILTER(LANG(?wAr)='ar') } OPTIONAL { ?w rdfs:label ?wEn FILTER(LANG(?wEn)='en') } }""" % qid)
        seen, champs = set(), []
        for b in rows:
            w = b["w"]["value"].rsplit("/", 1)[1]
            y = ((b.get("when") or {}).get("value") or "")[:4] or (re.findall(r"\d{4}", b["eL"]["value"]) or [""])[-1]
            if not y or (y, w) in seen:
                continue
            seen.add((y, w))
            champs.append([y, w, (b.get("wAr") or {}).get("value") or (b.get("wEn") or {}).get("value"), by_qid.get(w)])
        # the seasons Wikidata has no winner for yet: from our own archive's points table (single-table leagues only)
        if cid in TABLE_LEAGUES:
            have = {x[0] for x in champs}
            fm2 = {v: k for k, v in by_qid.items()}
            for y, fid in table_champions(store, cid).items():
                if y not in have:
                    t = teams.get(str(fid)) or {}
                    champs.append([y, fm2.get(fid) or f"fm:{fid}", t.get("name_ar") or t.get("name"), fid, "table"])
        champs.sort(key=lambda x: x[0])
        cnt = Counter(x[1] for x in champs)
        out[cid] = {"comp": cid, "qid": qid, "champions": champs,
                    "counts": [[q, n, next(x[2] for x in champs if x[1] == q), by_qid.get(q)] for q, n in cnt.most_common()],
                    "source": "Wikidata (winner of each season); seasons marked «table» from Tifo's own FotMob archive (points table)"}
        report.append((cid, en, qid, len(champs), champs[0][0] if champs else "", champs[-1][0] if champs else ""))
        if a.upload:
            store.put_json(f"history/champions/{cid}.json", out[cid], cache="warm")
        time.sleep(0.5)
    for r in report:
        print(*r)
    print(sum(1 for r in report if r[3]), "of", len(report), "competitions have champions")
    return 0


if __name__ == "__main__":
    sys.exit(main())

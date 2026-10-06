"""Every competition's champions through history, stage 4 of the owner's database (2026-09-30 «كلها»).

    python -m db.champions [--upload] [--report] [--out DIR] [--only 538,9943]

1. Wikidata (CC0): each of our competitions is matched to its Wikidata item (English name, then the item's country);
   every season/edition whose «season of» (P3450) is that item and that has a winner (P1346) gives [season, winner].
2. The winner is linked back to a FotMob club through db/clubs.py's cards (same Wikidata item) when it is one of ours.
Coverage is reported per competition (--report) so the gaps can be filled from RSSSF / Wikipedia tables next.
Out: v1/history/champions/<comp id>.json {champions: [[year, winner qid, name_ar|en, fotmob id|null]], counts};
--out DIR writes the would-be files there instead (tests; db/champions_wiki.py --dir DIR reads them).

Audit 2026-09-30 (291 of 1,523 Wikidata rows one season early, runners-up and a city as champions):
  * the year is the season's END year read from the item's label («2010–11 UAE President's Cup» -> 2011; the old fallback
    took the label's last 4-digit number, 2010). The item's dates only stand in for a label without a year, and an item
    whose dates are more than a year from its own label is dropped (the «2016 Copa Libertadores» item dated 2018, Boca);
  * a winner is read through its statement: one whose «results» qualifier (P2501) says runner-up, second or third place is
    not a winner (EURO 2004 Portugal, Club World Cup 2008 LDU Quito and Pachuca, Europa League 2010 Fulham), and the winner
    must be a sports club/team or a national team, never a place (the city of Al Ain, Aba for Enyimba);
  * two seasons are never merged because they share a winner (LaLiga 2024–25 and 2025–26, both Barcelona, now 2025 and 2026);
    items of one title are (the Nations League season, its League A and its Finals), two tournaments of one year are not;
  * a season 365Scores lists with no winner (v1/s365/fm.json: UAE 2019–20, Serie A 1926–27 and 2004–05, Ligue 1 1992–93,
    Egypt 2011–12 and 2012–13) has no champion here either, and a «table» row 365 contradicts is dropped (the archive splits
    seasons on 1 July, so the COVID-stretched Botola 2019–20 and 2020–21 and Algeria 2020–21 computed the wrong leader);
  * a Wikidata club card sitting on a national team's FotMob id (history/clubs.json: Germany carries VfB Stuttgart's item,
    South Korea Jeonbuk's) never links a club's title to the national team.
Wikidata is asked at most once a second, and its answers are kept 6 days in db/.cache/wd/ (a second run asks nothing).
"""
import argparse, hashlib, json, os, re, sys, time, urllib.parse, urllib.request
from collections import Counter
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from store import Store, S3Backend  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
UA = {"User-Agent": "elyoxe-tifo/0.1 (https://tifo.elyoxe.com; hello@elyoxe.com)", "Accept": "application/json"}
CACHE, TTL = os.path.join(HERE, ".cache", "wd"), 6 * 86400
WIN = {"Q852061", "Q18560095"}          # P2501 «results» values that do mean the winner: champion, winner
# what a winner must be an instance of (or of a subclass): sports club, sports team, association football club, national
# association football team. Checked on the 362 winners of 2026-09-30: only the cities of Aba and Al Ain and a dam fail.
TEAM_CLASSES = "wd:Q847017 wd:Q12973014 wd:Q476028 wd:Q6979593"
STAGE = re.compile(r"apertura|clausura|metropolitano|nacional|inicial|transici", re.I)   # tournaments that share a year
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


_last = [0.0]


def wd(url, data=None):
    """One Wikidata answer (API or SPARQL) through a 6-day file cache; never more than one request a second."""
    p = os.path.join(CACHE, hashlib.sha1(url.encode() + b"\n" + (data or b"")).hexdigest()[:24] + ".json")
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < TTL:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    for i in range(4):
        time.sleep(max(0.0, 1.0 - (time.time() - _last[0])))
        try:
            j = json.loads(urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=180).read())
            break
        except Exception:
            if i == 3:
                raise
            time.sleep(15 * (i + 1))
        finally:
            _last[0] = time.time()
    os.makedirs(CACHE, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(j, f, ensure_ascii=False)
    return j


def sparql(q):
    return wd("https://query.wikidata.org/sparql", urllib.parse.urlencode({"query": q, "format": "json"}).encode())["results"]["bindings"]


def search(name):
    return wd("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({"action": "wbsearchentities", "search": name, "language": "en", "type": "item", "limit": 7, "format": "json"})).get("search", [])


def end_year(label):
    """A season's END year from its label or title: «2010–11 …» and «2010/2011» -> 2011, «1999–2000 …» -> 2000,
    «UEFA Euro 2004» -> 2004; None when it names no year («خليجي 26»)."""
    m = re.search(r"(?<!\d)(\d{4})\s*[–\-/]\s*(\d{4}|\d{2})(?!\d)", label or "")
    if m:
        a, b = m.group(1), m.group(2)
        if len(b) == 4:
            return b
        y = int(a[:2] + b)
        return str(y + 100 if y < int(a) else y)
    ys = re.findall(r"(?<!\d)\d{4}(?!\d)", label or "")
    return ys[-1] if ys else None


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); ap.add_argument("--report", action="store_true")
    ap.add_argument("--out", help="write the would-be files to this folder (<comp id>.json) instead of uploading")
    ap.add_argument("--only", default="", help="comma-separated competition ids"); a = ap.parse_args(argv)
    only = {int(x) for x in a.only.split(",") if x.strip()}
    store = Store(S3Backend(BUCKET))
    comps = (store.get_json("index.json") or {}).get("competitions") or []
    cards = ((store.get_json("history/clubs.json") or {}).get("clubs")) or {}
    teams = (store.get_json("teams.json") or {}).get("teams") or {}
    # national teams: flagged under «country», or playing a national-team competition (Germany's FotMob entry has no country)
    scope = {c["id"]: c.get("scope") for c in comps}
    nat = {k for k, t in teams.items() if (t.get("country") or {}).get("national") or any(scope.get(x) == "national" for x in t.get("comps") or [])}
    by_qid = {c["qid"]: int(k) for k, c in cards.items() if c.get("qid") and k not in nat}
    # 365Scores' champions of the site's competitions (db/scores365.py): the seasons it lists with no winner, and its winners
    s365 = (store.get_json("s365/fm.json") or {}).get("comps") or {}
    report, out = [], {}
    for c in comps:
        cid, en = c["id"], c.get("name_en") or ""
        if only and cid not in only:
            continue
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
        if not qid:
            report.append((cid, en, None, 0)); continue
        # every winner statement of every season (best rank, as wdt: gives), its «results» qualifier, and only winners that
        # are clubs/teams; the item's own dates for a label without a year
        rows = sparql("""SELECT ?e ?eL ?w ?wAr ?wEn ?end ?pt ?st ?res WHERE {
            ?e wdt:P3450 wd:%s; p:P1346 ?s. ?s ps:P1346 ?w; a wikibase:BestRank. OPTIONAL { ?s pq:P2501 ?res }
            FILTER EXISTS { ?w wdt:P31/wdt:P279* ?k. VALUES ?k { %s } }
            OPTIONAL { ?e wdt:P582 ?end } OPTIONAL { ?e wdt:P585 ?pt } OPTIONAL { ?e wdt:P580 ?st } ?e rdfs:label ?eL FILTER(LANG(?eL)='en')
            OPTIONAL { ?w rdfs:label ?wAr FILTER(LANG(?wAr)='ar') } OPTIONAL { ?w rdfs:label ?wEn FILTER(LANG(?wEn)='en') } }""" % (qid, TEAM_CLASSES))
        x365 = s365.get(str(cid)) or {}
        void = {end_year(r[0]) for r in x365.get("champions") or [] if not r[1]} - {None}
        won365 = {}
        for r in x365.get("champions") or []:
            if r[1] and r[2]:
                won365.setdefault(end_year(r[0]), set()).add(r[2])
        seen, champs, bad, stg = set(), [], set(), []
        for b in rows:
            v = lambda k: (b.get(k) or {}).get("value")
            if v("res") and v("res").rsplit("/", 1)[1] not in WIN:
                continue                                      # runner-up / second / third place written on «winner»
            e, w = v("e").rsplit("/", 1)[1], v("w").rsplit("/", 1)[1]
            ly, dy = end_year(v("eL")), next((v(k)[:4] for k in ("end", "pt", "st") if v(k)), None)
            if ly and dy and abs(int(dy) - int(ly)) > 1:
                bad.add(f"{v('eL')} ({dy})"); continue           # the item's dates contradict its label: a broken item
            y = ly or dy
            # one title per (year, winner, stage): «2018–19 UEFA Nations League» and «… League A» (or «2021 … Finals») are one
            # title, while two tournaments of one year stay two (Argentina's 1975 Metropolitano and Nacional, both River)
            k = (y, w, (STAGE.search(v("eL")) or [""])[0].lower())
            if not y or y in void or k in seen:
                continue
            seen.add(k)
            champs.append([y, w, v("wAr") or v("wEn"), by_qid.get(w)]); stg.append(k[2])
        # one champion a season (and stage): Wikidata can carry a second «winner» on a season item (LaLiga 2014–15 also names
        # Real Betis, that season's Segunda champion: audit duplicate_season 2026-10-05). 365Scores' winner decides, else our own
        # points table; a season neither settles keeps both, and the audit lists it
        tab = table_champions(store, cid) if cid in TABLE_LEAGUES else {}
        groups, drop = {}, set()
        for i, x in enumerate(champs):
            groups.setdefault((x[0], stg[i]), []).append(i)
        for (y, _), ix in groups.items():
            if len({champs[i][1] for i in ix}) < 2:
                continue
            ref = won365.get(y) or ({tab[y]} if y in tab else set())
            keep = [i for i in ix if champs[i][3] is not None and champs[i][3] in ref]
            if keep:
                drop.update(i for i in ix if i not in keep)
        champs = [x for i, x in enumerate(champs) if i not in drop]
        # the seasons Wikidata has no winner for yet: from our own archive's points table (single-table leagues only), never
        # for a season 365 marks void or names another winner for
        if cid in TABLE_LEAGUES:
            have = {x[0] for x in champs}
            fm2 = {f: q for q, f in by_qid.items()}
            for y, fid in tab.items():
                if y not in have and y not in void and (y not in won365 or fid in won365[y]):
                    t = teams.get(str(fid)) or {}
                    champs.append([y, fm2.get(fid) or f"fm:{fid}", t.get("name_ar") or t.get("name"), fid, "table"])
        champs.sort(key=lambda x: x[0])
        cnt = Counter(x[1] for x in champs)
        out[cid] = {"comp": cid, "qid": qid, "champions": champs,
                    "counts": [[q, n, next(x[2] for x in champs if x[1] == q), by_qid.get(q)] for q, n in cnt.most_common()],
                    "source": "Wikidata (winner of each season); seasons marked «table» from Tifo's own FotMob archive (points table)"}
        report.append((cid, en, qid, len(champs), champs[0][0] if champs else "", champs[-1][0] if champs else "", *(["dropped:"] + sorted(bad) if bad else [])))
        if a.out:
            os.makedirs(a.out, exist_ok=True)
            with open(os.path.join(a.out, f"{cid}.json"), "w", encoding="utf-8", newline="\n") as f:
                json.dump(out[cid], f, ensure_ascii=False)
        elif a.upload:
            store.put_json(f"history/champions/{cid}.json", out[cid], cache="warm")
    for r in report:
        print(*r)
    print(sum(1 for r in report if r[3]), "of", len(report), "competitions have champions")
    return 0


if __name__ == "__main__":
    sys.exit(main())

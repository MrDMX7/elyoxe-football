"""The Messi museum's other rooms, each from its own open source (the shots and play come from statsbomb_messi.py):

  career     FotMob playerData: club by club and Argentina (apps, goals, assists), the total the page leads with
  value      Transfermarkt player_valuations (CC0): his market value over time
  awards     Wikidata (CC0): every award on his item with its year; Ballon d'Or years picked out
  trophies   Wikidata: every season/edition whose winner (P1346) was his team while he was there
  intl       martj42 goalscorers + results (CC0): his international goals with venue city and country (the dataset
             covers the tournaments and qualifiers, not every friendly; the page says so)
  legends    Wikidata: national-team caps and goals for him, Pelé and Maradona (same property, same source)

    python -m history.messi_extra [--upload]          -> v1/legends/messi/extra.json
"""
import argparse, csv, gzip, io, json, os, sys, urllib.parse, urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
UA = {"User-Agent": "elyoxe-tifo/0.1 (https://tifo.elyoxe.com; hello@elyoxe.com)"}
Q = {"messi": "Q615", "pele": "Q12897", "maradona": "Q17515"}
CLUBS = {"Q7156": ("برشلونة", "2004-10-16", "2021-08-05"), "Q483020": ("باريس سان جيرمان", "2021-08-10", "2023-06-30"),
         "Q79800": ("الأرجنتين", "2005-08-17", None), "Q16844931": ("إنتر ميامي", "2023-07-15", None)}


def fetch(url, data=None):
    return urllib.request.urlopen(urllib.request.Request(url, data=data, headers=dict(UA, Accept="application/json")), timeout=120).read()


def sparql(q):
    return json.loads(fetch("https://query.wikidata.org/sparql", urllib.parse.urlencode({"query": q, "format": "json"}).encode()))["results"]["bindings"]


def career():
    from sources.fotmob import FotMob
    raw = FotMob().http.get_json("https://www.fotmob.com/api/data/playerData?id=30981", min_ttl=0)
    out = []
    for kind, v in ((raw.get("careerHistory") or {}).get("careerItems") or {}).items():
        for t in v.get("teamEntries") or []:
            if t.get("appearances") is None:
                continue
            out.append({"kind": kind, "team": t.get("team"), "team_id": t.get("teamId"), "from": (t.get("startDate") or "")[:10],
                        "to": (t.get("endDate") or "")[:10] or None, "apps": t.get("appearances"), "goals": t.get("goals"), "assists": t.get("assists")})
    senior = [c for c in out if c["kind"] in ("senior", "national team") and "U2" not in (c["team"] or "")]
    num = lambda v: int(v) if str(v or "").strip().isdigit() else 0
    return {"teams": out, "total": {k: sum(num(c[k]) for c in senior) for k in ("apps", "goals", "assists")}}


def value():
    raw = fetch("https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/player_valuations.csv.gz")
    rows = [r for r in csv.DictReader(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(raw)), encoding="utf-8")) if r["player_id"] == "28003"]
    return [[r["date"][:10], int(float(r["market_value_in_eur"])), r["current_club_name"]] for r in sorted(rows, key=lambda r: r["date"])]


def awards():
    rows = sparql("SELECT ?aw ?awL ?awAr ?t WHERE { wd:%s p:P166 ?s. ?s ps:P166 ?aw. OPTIONAL{?s pq:P585 ?t} "
                  "?aw rdfs:label ?awL FILTER(LANG(?awL)='en') OPTIONAL{?aw rdfs:label ?awAr FILTER(LANG(?awAr)='ar')} }" % Q["messi"])
    out = sorted({(b.get("t", {}).get("value", "")[:4], b["awL"]["value"], b.get("awAr", {}).get("value"), b["aw"]["value"].rsplit("/", 1)[1]) for b in rows})
    return [{"year": y or None, "name": n, "name_ar": a, "qid": q} for y, n, a, q in out]


import re
TITLE = re.compile(r"^(\d{4}(?:[–-]\d{2,4})? )(La Liga|Ligue 1|UEFA Champions League|Copa del Rey|Supercopa de España|UEFA Super Cup|FIFA Club World Cup|"
                   r"Trophée des Champions|FIFA World Cup|Copa América|Leagues Cup|FIFA U-20 World Cup|Supporters' Shield|CONMEBOL–UEFA Cup of Champions|Finalissima)$"
                   r"|^Football at the 2008 Summer Olympics – Men's tournament$|^MLS Cup \d{4}$")


def trophies():
    out = []
    for qid, (ar, start, end) in CLUBS.items():
        rows = sparql("SELECT ?e ?eL ?eAr ?d ?end WHERE { ?e wdt:P1346 wd:%s. OPTIONAL{?e wdt:P582 ?end} OPTIONAL{?e wdt:P585 ?d} "
                      "?e rdfs:label ?eL FILTER(LANG(?eL)='en') OPTIONAL{?e rdfs:label ?eAr FILTER(LANG(?eAr)='ar')} }" % qid)
        seen = set()
        for b in rows:
            if b["e"]["value"] in seen:
                continue
            seen.add(b["e"]["value"])
            # the edition's end date, else its date, else the last year in its name («2023 Leagues Cup», «2004–05 La Liga»)
            d = (b.get("end") or b.get("d") or {}).get("value", "")[:10]
            if not d:
                ys = re.findall(r"(\d{4})(?:[–-](\d{2,4}))?", b["eL"]["value"])
                if ys:
                    y0, y1 = ys[0]; d = (y0[:2] + y1 if len(y1) == 2 else y1 or y0) + "-06-30"
            if not d or d < start or (end and d > end[:4] + "-12-31"):
                continue
            if not TITLE.match(b["eL"]["value"]):       # a whole competition won, not one match, a youth cup, a friendly or another sport
                continue
            out.append({"team": ar, "name": b["eL"]["value"], "name_ar": (b.get("eAr") or {}).get("value"), "date": d, "qid": b["e"]["value"].rsplit("/", 1)[1]})
    return sorted(out, key=lambda x: x["date"])


def intl():
    gs = csv.DictReader(io.StringIO(fetch("https://raw.githubusercontent.com/martj42/international_results/master/goalscorers.csv").decode("utf-8")))
    res = {(r["date"], r["home_team"], r["away_team"]): r for r in csv.DictReader(io.StringIO(fetch("https://raw.githubusercontent.com/martj42/international_results/master/results.csv").decode("utf-8")))}
    out = []
    for g in gs:
        if g["scorer"] != "Lionel Messi":
            continue
        r = res.get((g["date"], g["home_team"], g["away_team"]), {})
        out.append({"date": g["date"], "opp": g["away_team"] if g["team"] == g["home_team"] else g["home_team"], "min": g["minute"],
                    "pen": g["penalty"] == "TRUE", "tournament": r.get("tournament"), "city": r.get("city"), "country": r.get("country"),
                    "score": [r.get("home_score"), r.get("away_score")], "home": g["team"] == g["home_team"]})
    return out


def legends():
    rows = sparql("SELECT ?p ?team ?teamL ?apps ?goals WHERE { VALUES ?p { %s } ?p p:P54 ?s. ?s ps:P54 ?team. "
                  "OPTIONAL{?s pq:P1350 ?apps} OPTIONAL{?s pq:P1351 ?goals} ?team rdfs:label ?teamL FILTER(LANG(?teamL)='en') }" % " ".join("wd:" + v for v in Q.values()))
    inv = {v: k for k, v in Q.items()}
    out = {}
    for b in rows:
        k = inv[b["p"]["value"].rsplit("/", 1)[1]]
        if "national" not in b["teamL"]["value"].lower() or "under" in b["teamL"]["value"].lower() or "olympic" in b["teamL"]["value"].lower():
            continue
        out[k] = {"team": b["teamL"]["value"], "apps": int(float(b["apps"]["value"])) if b.get("apps") else None, "goals": int(float(b["goals"]["value"])) if b.get("goals") else None}
    return out


def dob():
    b = sparql("SELECT ?d WHERE { wd:%s wdt:P569 ?d }" % Q["messi"])
    return b[0]["d"]["value"][:10] if b else None


def names_ar():
    """Arabic labels for the teammates, assist receivers and coaches StatsBomb names (English labels matched exactly,
    footballers and managers only: a namesake never gets in)."""
    base = os.path.join(HERE, ".cache", "messi")
    try:
        play = json.load(open(os.path.join(base, "play.json"), encoding="utf-8")); mm = json.load(open(os.path.join(base, "matches.json"), encoding="utf-8"))
    except OSError:
        return {}
    want = {x[0] for x in play.get("links", [])} | {x[0] for x in play.get("costarts", [])} | {a.get("to") for a in play.get("assists", []) if a.get("to")} | {m.get("coach") for m in mm["matches"] if m.get("coach")}
    out, want = {}, sorted(w for w in want if w)
    for i in range(0, len(want), 60):
        vals = " ".join('"%s"@en' % w.replace('"', "") for w in want[i:i + 60])
        for b in sparql("SELECT ?l ?ar WHERE { VALUES ?l { %s } ?p rdfs:label ?l; wdt:P106 ?o. VALUES ?o { wd:Q937857 wd:Q628099 } ?p rdfs:label ?ar FILTER(LANG(?ar)='ar') }" % vals):
            out.setdefault(b["l"]["value"], b["ar"]["value"])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); a = ap.parse_args(argv)
    doc = {"generated": date.today().isoformat(), "sources": {"career": "FotMob", "value": "Transfermarkt (transfermarkt-datasets, CC0)",
           "awards": "Wikidata", "trophies": "Wikidata (P1346 winner)", "intl": "martj42/international_results (CC0)", "legends": "Wikidata (P54 with P1350/P1351)"}}
    for name, fn in (("dob", dob), ("names_ar", names_ar), ("career", career), ("value", value), ("awards", awards), ("trophies", trophies), ("intl", intl), ("legends", legends)):
        try:
            doc[name] = fn()
        except Exception as e:
            print(name, "failed:", type(e).__name__, str(e)[:120]); doc[name] = None
        v = doc[name]
        print(name, (len(v) if isinstance(v, list) else json.dumps(v, ensure_ascii=False)[:200]) if v is not None else "-")
    p = os.path.join(HERE, ".cache", "messi", "extra.json"); os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(doc, open(p, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, separators=(",", ":"))
    if a.upload:
        from store import Store, S3Backend
        Store(S3Backend(os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1"))).put_json("legends/messi/extra.json", doc, cache="warm")
        print("uploaded v1/legends/messi/extra.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

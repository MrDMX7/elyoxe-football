"""Every club's identity card from Wikidata (CC0), stage 2 of the owner's database (2026-09-30 «كلها»).

    python -m db.clubs [--upload]

Linking a FotMob club to its Wikidata item, strongest first:
  1. Transfermarkt id: history/transfermarkt.py maps Transfermarkt clubs to FotMob; Wikidata holds the Transfermarkt id (P7223).
  2. Name + country: an exact (folded) English or Arabic label of a football club (Q476028 and subclasses) in the same
     country (P17 -> ISO 3166 P297). Only when exactly one item matches.
Fields: founded (P571), stadium (P115) + its capacity (P1083) and coordinates (P625), city (P159 / P131), nickname
(P1449), website (P856), official accounts (Instagram, X, Facebook, YouTube, TikTok), Arabic label, and every season/edition it won (items whose winner P1346 is the club), grouped
by competition (P3450 «season of»).
Out: v1/history/clubs.json {fotmob id: card} (one file: the build reads it once, the client never needs it separately).
"""
import argparse, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from store import Store, S3Backend  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
UA = {"User-Agent": "elyoxe-tifo/0.1 (https://tifo.elyoxe.com; hello@elyoxe.com)", "Accept": "application/json"}
ISO_FIX = {"GB-ENG": "GB", "GB-SCT": "GB", "GB-WLS": "GB", "GB-NIR": "GB"}


def sparql(q):
    for i in range(4):
        try:
            data = urllib.parse.urlencode({"query": q, "format": "json"}).encode()
            return json.loads(urllib.request.urlopen(urllib.request.Request("https://query.wikidata.org/sparql", data=data, headers=UA), timeout=180).read())["results"]["bindings"]
        except Exception as e:
            if i == 3:
                raise
            time.sleep(15 * (i + 1))


def fold(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(fc|cf|sc|ac|afc|club|football|futbol|clube|calcio|sk|fk|cd|sd|ud|ca|se|ec)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def ar_fold(s):
    s = re.sub(r"[ً-ْـ]", "", s or "")
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")
    return re.sub(r"^(نادي|النادي)\s+", "", re.sub(r"\s+(السعودي|الاماراتي|المصري|الرياضي|لكره القدم)$", "", s.strip()))


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); a = ap.parse_args(argv)
    store = Store(S3Backend(BUCKET))
    teams = (store.get_json("teams.json") or {}).get("teams") or {}
    # a club's country: its own, else its league's (FotMob leaves many foreign clubs without one: River Plate, Boca…)
    comp_cc = {c["id"]: (c.get("country") or {}).get("iso2") for c in ((store.get_json("index.json") or {}).get("competitions") or []) if c.get("kind") == "league"}
    clubs = {}
    for k, t in teams.items():
        if t.get("national"):
            continue
        cc = (t.get("country") or {}).get("iso2") or next((comp_cc[c] for c in t.get("comps") or [] if comp_cc.get(c)), None)
        if cc:
            clubs[k] = dict(t, country={"iso2": cc})
    # 1. Transfermarkt ids -> FotMob, from the transfer history's club map
    tm2fm = {}
    try:
        tm2fm = json.load(open(os.path.join(ROOT, "history", ".cache", "tm_clubmap.json"), encoding="utf-8"))
    except OSError:
        pass
    qid = {}
    if tm2fm:
        vals = " ".join(f'"{k}"' for k in tm2fm)
        for b in sparql("SELECT ?c ?tm WHERE { VALUES ?tm { %s } ?c wdt:P7223 ?tm }" % vals):
            fm = tm2fm.get(b["tm"]["value"])
            if fm:
                qid.setdefault(str(fm), b["c"]["value"].rsplit("/", 1)[1])
    print(len(qid), "clubs linked by Transfermarkt id")
    # 2. name + country, per country (one query each: every football club there with its labels)
    by_cc = defaultdict(list)
    for k, t in clubs.items():
        if k not in qid:
            by_cc[ISO_FIX.get(t["country"]["iso2"], t["country"]["iso2"])].append(k)
    for cc, ids in sorted(by_cc.items()):
        rows = sparql("""SELECT ?c ?en ?ar WHERE { ?co wdt:P297 "%s". ?c wdt:P17 ?co; wdt:P31/wdt:P279* wd:Q476028.
                         OPTIONAL { ?c rdfs:label ?en FILTER(LANG(?en)='en') } OPTIONAL { ?c rdfs:label ?ar FILTER(LANG(?ar)='ar') } }""" % cc)
        en, arl = defaultdict(set), defaultdict(set)
        for b in rows:
            q = b["c"]["value"].rsplit("/", 1)[1]
            if b.get("en"): en[fold(b["en"]["value"])].add(q)
            if b.get("ar"): arl[ar_fold(b["ar"]["value"])].add(q)
        got = 0
        for k in ids:
            t = clubs[k]; c = en.get(fold(t.get("name"))) or set()
            if len(c) != 1 and t.get("name_ar"):
                c = arl.get(ar_fold(t["name_ar"])) or set()
            if len(c) == 1:
                qid[k] = next(iter(c)); got += 1
        print(cc, f"{got}/{len(ids)}")
        time.sleep(1)
    print(len(qid), "clubs linked in all")
    # the cards
    cards, qs = {}, sorted(set(qid.values()))
    inv = defaultdict(list)
    for k, q in qid.items():
        inv[q].append(k)
    for i in range(0, len(qs), 150):
        vals = " ".join("wd:" + q for q in qs[i:i + 150])
        for b in sparql("""SELECT ?c ?ar ?founded ?st ?stAr ?stEn ?cap ?coord ?city ?cityAr ?nick ?web WHERE { VALUES ?c { %s }
            OPTIONAL { ?c rdfs:label ?ar FILTER(LANG(?ar)='ar') } OPTIONAL { ?c wdt:P571 ?founded }
            OPTIONAL { ?c wdt:P115 ?st. OPTIONAL { ?st rdfs:label ?stAr FILTER(LANG(?stAr)='ar') } OPTIONAL { ?st rdfs:label ?stEn FILTER(LANG(?stEn)='en') }
                       OPTIONAL { ?st wdt:P1083 ?cap } OPTIONAL { ?st wdt:P625 ?coord } }
            OPTIONAL { ?c wdt:P159 ?city. OPTIONAL { ?city rdfs:label ?cityAr FILTER(LANG(?cityAr)='ar') } }
            OPTIONAL { ?c wdt:P1449 ?nick FILTER(LANG(?nick)='ar' || LANG(?nick)='en') } OPTIONAL { ?c wdt:P856 ?web } }""" % vals):
            q = b["c"]["value"].rsplit("/", 1)[1]
            for k in inv[q]:
                c = cards.setdefault(k, {"qid": q})
                v = lambda n: (b.get(n) or {}).get("value")
                if v("ar"): c.setdefault("name_ar", v("ar"))
                if v("founded"): c.setdefault("founded", v("founded")[:4].lstrip("+"))
                if v("st"): c.setdefault("stadium", {"ar": v("stAr"), "en": v("stEn"), "qid": v("st").rsplit("/", 1)[1]})
                if v("cap") and "stadium" in c: c["stadium"].setdefault("capacity", int(float(v("cap"))))
                if v("coord") and "stadium" in c:
                    m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", v("coord"))
                    if m: c["stadium"].setdefault("lonlat", [round(float(m.group(1)), 5), round(float(m.group(2)), 5)])
                if v("cityAr"): c.setdefault("city", v("cityAr"))
                if v("nick"): c.setdefault("nick", [])
                if v("nick") and v("nick") not in c["nick"] and len(c["nick"]) < 3: c["nick"].append(v("nick"))
                if v("web"): c.setdefault("web", v("web"))
        time.sleep(1)
    # official accounts: Instagram (P2003), X (P2002), Facebook (P2013), YouTube channel (P2397), TikTok (P7085)
    SOC = {"P2003": "instagram", "P2002": "x", "P2013": "facebook", "P2397": "youtube", "P7085": "tiktok"}
    for i in range(0, len(qs), 150):
        vals = " ".join("wd:" + q for q in qs[i:i + 150])
        for b in sparql("""SELECT ?c ?p ?v WHERE { VALUES ?c { %s } VALUES ?p { wdt:P2003 wdt:P2002 wdt:P2013 wdt:P2397 wdt:P7085 } ?c ?p ?v }""" % vals):
            q, prop, val = b["c"]["value"].rsplit("/", 1)[1], b["p"]["value"].rsplit("/", 1)[1], b["v"]["value"]
            for k in inv[q]:
                cards.setdefault(k, {"qid": q}).setdefault("social", {}).setdefault(SOC.get(prop, prop), val)
        time.sleep(1)
    # honours: every season/edition won, grouped by the competition it belongs to
    for i in range(0, len(qs), 100):
        vals = " ".join("wd:" + q for q in qs[i:i + 100])
        for b in sparql("""SELECT ?c ?e ?eL ?comp ?compAr ?compEn ?when WHERE { VALUES ?c { %s } ?e wdt:P1346 ?c; wdt:P3450 ?comp.
            OPTIONAL { ?e wdt:P582 ?end } OPTIONAL { ?e wdt:P585 ?pt } OPTIONAL { ?e wdt:P580 ?st } BIND(COALESCE(?end, ?pt, ?st) AS ?when)
            OPTIONAL { ?comp rdfs:label ?compAr FILTER(LANG(?compAr)='ar') } OPTIONAL { ?comp rdfs:label ?compEn FILTER(LANG(?compEn)='en') }
            ?e rdfs:label ?eL FILTER(LANG(?eL)='en') }""" % vals):
            q = b["c"]["value"].rsplit("/", 1)[1]
            y = ((b.get("when") or {}).get("value") or "")[:4] or (re.findall(r"\d{4}", b["eL"]["value"]) or [""])[-1]
            for k in inv[q]:
                h = cards.setdefault(k, {"qid": q}).setdefault("honours", {})
                cq = b["comp"]["value"].rsplit("/", 1)[1]
                e = h.setdefault(cq, {"ar": (b.get("compAr") or {}).get("value"), "en": (b.get("compEn") or {}).get("value"), "years": []})
                if y and y not in e["years"]: e["years"].append(y)
        time.sleep(1)
    for c in cards.values():
        for e in (c.get("honours") or {}).values():
            e["years"].sort()
    doc = {"generated": date.today().isoformat(), "source": "Wikidata (CC0)", "clubs": cards}
    p = os.path.join(HERE, ".cache", "clubs.json"); json.dump(doc, open(p, "w", encoding="utf-8", newline="\n"), ensure_ascii=False)
    print(len(cards), "cards;", sum(1 for c in cards.values() if c.get("founded")), "with a founding year;", sum(1 for c in cards.values() if c.get("stadium")), "with a stadium;",
          sum(1 for c in cards.values() if c.get("honours")), "with honours")
    if a.upload:
        store.put_json("history/clubs.json", doc, cache="warm"); print("uploaded v1/history/clubs.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

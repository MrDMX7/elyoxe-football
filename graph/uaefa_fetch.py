"""The UAE FA's own record of every top-flight game from 2003/04 to 2013/14 (FotMob's UAE league starts in 2014/15):
uaefa.ae/api's match_report (line-ups and benches, substitutions and cards with minutes, the referee team, the ground, the
kick-off) and match_highlights2 in English and Arabic (goals with minute and side). research/uae-league-history-sources-
2026-11-22.md has the map; the owner, 22 Nov 2026: «الدوري الاماراتي… من بداية بداياته».

  python -m graph.uaefa_fetch --cache DIR ids        # FA ids: uaepl.ae's fixture lists (2008/09-) and a scan of 14000-23840
  python -m graph.uaefa_fetch --cache DIR matches    # each top-flight id's report and events (one file an id: resumable)
  python -m graph.uaefa_fetch --cache DIR pack OUT   # one gz file for the graph build (graph/load/uaefa.py)

A one-time fetch of finished seasons, run on the laptop (GitHub first, else the laptop): about a request a second, a missing
id is the API's HTTP 500."""
import argparse, glob, gzip, json, os, re, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://www.uaefa.ae/api/"
UAEPL = "https://www.uaepl.ae"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
      "Accept": "application/json, text/plain, */*"}
# the league's uaepl.ae season-competition ids (its fixtures page's `var season`), FotMob holds 2014/15 on
SEASONS = {"2008/2009": "98a49220-7f1e-11eb-81e1-cfe80e72eb76", "2009/2010": "98a49220-7f1e-11eb-81e1-cfe80e72eb66",
           "2010/2011": "0c8d9c50-6a3f-11eb-abea-f59ee726fay9", "2011/2012": "0c8d9c50-6a3f-11eb-abea-f59ee726fax9",
           "2012/2013": "0c8d9c50-6a3f-11eb-abea-f59ee726fab9", "2013/2014": "c08fa630-6a38-11eb-8498-4dd725155205",
           # FotMob's own seasons, for the links only: the same game in both ties the FA's players to FotMob's (shirt numbers)
           "2014/2015": "85706d40-6a34-11eb-a1bf-056e272802ea", "2015/2016": "14dac730-6964-11eb-950d-69b91f0a8daa",
           "2016/2017": "14dac730-6964-11eb-950d-69b91f0a8dca"}
SCAN = (14000, 23840, 10)
GAP = 0.8
WORKERS = 4                    # four requests at a time (the API answers in 1-3 s; ~1.5 a second in all)


def get(url, headers=None, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=40) as r:
                time.sleep(GAP)
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            time.sleep(GAP)
            if e.code in (404, 500):
                return None                       # a gap in the id range
            if i == tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError):
            if i == tries - 1:
                raise
        time.sleep(5 * (i + 1))


def season_of(att):
    """the API's «2006/2005» (end/start) as «2005/2006»"""
    m = re.fullmatch(r"(\d{4})/(\d{4})", str((att or {}).get("season") or ""))
    if not m:
        return None
    a, b = sorted(int(x) for x in m.groups())
    return f"{a}/{b}"


def top_flight(season, comp):
    """«First Division league» is the top tier up to 2007/08 (from 2008/09 the second); never a youth or reserve side's"""
    c = str(comp or "")
    if not season or re.search(r"under|\bu\s?\d\d|youth|reserve|olympic|junior|second division|\bcup\b|women|\d+ year", c, re.I):
        return False
    if season <= "2007/2008":
        return bool(re.search(r"first division", c, re.I))
    return bool(re.search(r"pro\s?league|arabian gulf league", c, re.I))


def path(cache, *p):
    f = os.path.join(cache, *p)
    os.makedirs(os.path.dirname(f), exist_ok=True)
    return f


def cached(f, fetch):
    if os.path.exists(f):
        return json.load(open(f, encoding="utf-8"))
    d = fetch()
    json.dump(d, open(f + ".tmp", "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(f + ".tmp", f)
    return d


def each(fn, items):
    with ThreadPoolExecutor(WORKERS) as ex:
        return list(ex.map(fn, items))


def highlights(cache, i, lang):
    return cached(path(cache, "h" + lang, f"{i}.json"), lambda: get(f"{API}match_highlights2?lang={lang}&match_id={i}"))


def uaepl_list(cache, season):
    """uaepl.ae's fixture list of a season (English and Arabic), with each game's FA id (its box's matchList_<id>)"""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from sources.uaepl import parse_fixtures
    xhr = {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"}

    def lists():
        q = f"fixtures/matches?seasonCompetitionId={SEASONS[season]}&weekNumber=&teamId="
        en = (get(f"{UAEPL}/en/{q}", xhr) or {}).get("html") or ""
        ar = (get(f"{UAEPL}/ar/{q}", xhr) or {}).get("html") or ""
        return [{**f, "fa": int(re.sub(r"\D", "", f["box_id"]))} for f in parse_fixtures(en, ar) if re.sub(r"\D", "", f["box_id"] or "")]
    return cached(path(cache, "uaepl", season.replace("/", "-") + ".json"), lists)


def ids(cache):
    for season in SEASONS:
        print(f"uaepl {season}: {len(uaepl_list(cache, season))}", flush=True)
    lo, hi, step = SCAN
    probes = list(range(lo, hi + 1, step))
    hits = []
    for i, d in zip(probes, each(lambda i: highlights(cache, i, "en"), probes)):
        att = ((d or {}).get("match_highlights2") or {}).get("attributes") or {}
        s = season_of(att)
        if s and s <= "2007/2008" and top_flight(s, att.get("competition")):
            hits.append(i)
    print(f"scan: {len(hits)} top-flight probes", flush=True)
    block = sorted({i for h in hits for i in range(h - step + 1, h + step)})      # the whole block around each hit
    each(lambda i: highlights(cache, i, "en"), block)
    found = {}
    for f in glob.glob(os.path.join(cache, "hen", "*.json")):
        d = json.load(open(f, encoding="utf-8"))
        att = ((d or {}).get("match_highlights2") or {}).get("attributes") or {}
        s = season_of(att)
        if s and s <= "2007/2008" and top_flight(s, att.get("competition")):
            found.setdefault(s, []).append(int(os.path.basename(f)[:-5]))
    json.dump({s: sorted(v) for s, v in sorted(found.items())}, open(path(cache, "scan_ids.json"), "w"))
    print({s: len(v) for s, v in sorted(found.items())}, flush=True)


def wanted(cache):
    out = {}
    for season in SEASONS:
        for f in uaepl_list(cache, season):
            out[f["fa"]] = (season, f)
    for season, v in json.load(open(path(cache, "scan_ids.json"))).items():
        for i in v:
            out.setdefault(i, (season, None))
    return out


def matches(cache):
    w = sorted(wanted(cache))

    def one(i):
        cached(path(cache, "report", f"{i}.json"), lambda: get(f"{API}match_report?match_id={i}"))
        highlights(cache, i, "en")
        highlights(cache, i, "ar")
    for k in range(0, len(w), 200):
        each(one, w[k:k + 200])
        print(f"matches {min(k + 200, len(w))}/{len(w)}", flush=True)


def pack(cache, out):
    rows = []
    for i, (season, fx) in sorted(wanted(cache).items()):
        rd = lambda d, f: json.load(open(f, encoding="utf-8")) if os.path.exists(f) else None
        rep = rd(0, path(cache, "report", f"{i}.json"))
        if not rep:
            continue
        rows.append({"fa": i, "season": season, "uaepl": fx, "report": (rep or {}).get("match_report"),
                     "en": ((rd(0, path(cache, "hen", f"{i}.json")) or {}).get("match_highlights2")),
                     "ar": ((rd(0, path(cache, "har", f"{i}.json")) or {}).get("match_highlights2"))})
    with gzip.open(out, "wt", encoding="utf-8") as z:
        json.dump({"source": "uaefa.ae/api + uaepl.ae", "matches": rows}, z, ensure_ascii=False)
    print(f"packed {len(rows)} -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("stage", choices=["ids", "matches", "pack"])
    ap.add_argument("out", nargs="?")
    a = ap.parse_args()
    {"ids": lambda: ids(a.cache), "matches": lambda: matches(a.cache), "pack": lambda: pack(a.cache, a.out)}[a.stage]()

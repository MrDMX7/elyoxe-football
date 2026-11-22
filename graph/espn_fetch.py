"""ESPN's match records (site.api.espn.com: scoreboard by month, then each game's summary) for the seasons before FotMob's
detail: the big five leagues 2001/02-2009/10, the Champions League 2001/02-2009/10, the AFC Champions League 2006-2009, the
Africa Cup of Nations 2004-2010 and the 2007 Asian Cup; 2010/11 of the five leagues too, so its men tie to FotMob's by the
shirt each wore in a game both hold (research/open-football-datasets-2026-11-22.md §2.1). Per game: both squads with the
starters, substitutions, goals with minute, cards, the referee, the ground, the attendance.

  python -m graph.espn_fetch --cache DIR fetch       # resumable: one compact file a game
  python -m graph.espn_fetch --cache DIR pack OUT    # one gz file for the graph build (graph/load/espn.py)

Run where ESPN answers (the laptop, 22 Nov 2026), four requests at a time."""
import argparse, glob, gzip, json, os, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

SITE = "https://site.api.espn.com/apis/site/v2/sports/soccer/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"}
SPLIT = lambda y: [(y, m) for m in range(7, 13)] + [(y + 1, m) for m in range(1, 7)]       # July-June
CAL = lambda y: [(y, m) for m in range(1, 13)]
# league code -> [(our label, months)]
WANT = {**{lg: [(f"{y}/{y + 1}", SPLIT(y)) for y in range(2001, 2011)] for lg in ("eng.1", "esp.1", "ita.1", "ger.1", "fra.1")},
        "uefa.champions": [(f"{y}/{y + 1}", SPLIT(y)) for y in range(2001, 2010)],
        "afc.champions": [(str(y), CAL(y)) for y in range(2006, 2010)],
        "caf.nations": [(str(y), [(y, 1), (y, 2)]) for y in (2004, 2006, 2008, 2010)],
        "afc.asian.cup": [("2007", [(2007, 7)])]}
WORKERS, GAP = 4, 0.25


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                time.sleep(GAP)
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None
            if i == tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError):
            if i == tries - 1:
                raise
        time.sleep(4 * (i + 1))


def cached(f, fetch):
    if os.path.exists(f):
        return json.load(open(f, encoding="utf-8"))
    d = fetch()
    os.makedirs(os.path.dirname(f), exist_ok=True)
    json.dump(d, open(f + ".tmp", "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(f + ".tmp", f)
    return d


def compact(s):
    """what the loader reads of a summary (225 KB of news, odds and commentary otherwise)"""
    if not s:
        return None
    comp = ((s.get("header") or {}).get("competitions") or [{}])[0]
    gi = s.get("gameInfo") or {}
    return {"date": comp.get("date"),
            "teams": [{"id": t.get("id"), "name": (t.get("team") or {}).get("displayName"), "side": t.get("homeAway"), "score": t.get("score")}
                      for t in comp.get("competitors") or []],
            "venue": ((gi.get("venue") or {}).get("fullName")), "attendance": gi.get("attendance"),
            "referee": next((o.get("fullName") for o in gi.get("officials") or [] if (o.get("position") or {}).get("name") == "Referee"), None),
            "rosters": [{"team": (r.get("team") or {}).get("id"), "side": r.get("homeAway"),
                         "men": [{"id": (p.get("athlete") or {}).get("id"), "name": (p.get("athlete") or {}).get("displayName"),
                                  "no": p.get("jersey"), "start": p.get("starter"), "in": p.get("subbedIn"), "out": p.get("subbedOut"),
                                  "pos": (p.get("position") or {}).get("abbreviation"),
                                  "plays": [{"t": (x.get("clock") or {}).get("displayValue"), **{k: True for k in ("scoringPlay", "yellowCard", "redCard",
                                             "substitution", "penaltyKick", "ownGoal") if x.get(k)}} for x in p.get("plays") or []]}
                                 for p in r.get("roster") or []]} for r in s.get("rosters") or []],
            "key": [{"t": (k.get("clock") or {}).get("displayValue"), "type": (k.get("type") or {}).get("text"), "team": (k.get("team") or {}).get("id"),
                     "who": [(a.get("athlete") or {}).get("id") for a in k.get("participants") or []]} for k in s.get("keyEvents") or []]}


def fetch(cache):
    for lg, seasons in WANT.items():
        events = {}
        for label, months in seasons:
            for y, m in months:
                d = cached(os.path.join(cache, "sb", lg, f"{y}{m:02d}.json"), lambda: get(f"{SITE}{lg}/scoreboard?dates={y}{m:02d}&limit=500"))
                for e in (d or {}).get("events") or []:
                    events[e["id"]] = label
        json.dump(events, open(os.path.join(cache, f"events-{lg}.json"), "w"))
        todo = [(i, s) for i, s in events.items() if not os.path.exists(os.path.join(cache, "ev", lg, f"{i}.json"))]
        print(f"{lg}: {len(events)} games, {len(todo)} to fetch", flush=True)

        def one(item):
            i, _ = item
            return cached(os.path.join(cache, "ev", lg, f"{i}.json"), lambda: compact(get(f"{SITE}{lg}/summary?event={i}")))
        for k in range(0, len(todo), 400):
            with ThreadPoolExecutor(WORKERS) as ex:
                list(ex.map(one, todo[k:k + 400]))
            print(f"{lg}: {min(k + 400, len(todo))}/{len(todo)}", flush=True)


def pack(cache, out):
    rows = []
    for lg in WANT:
        f = os.path.join(cache, f"events-{lg}.json")
        if not os.path.exists(f):
            continue
        for i, label in json.load(open(f)).items():
            p = os.path.join(cache, "ev", lg, f"{i}.json")
            d = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
            if d:
                rows.append({"league": lg, "id": i, "season": label, **d})
    with gzip.open(out, "wt", encoding="utf-8") as z:
        json.dump({"source": "site.api.espn.com", "matches": rows}, z, ensure_ascii=False)
    print(f"packed {len(rows)} -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("stage", choices=["fetch", "pack"])
    ap.add_argument("out", nargs="?")
    a = ap.parse_args()
    fetch(a.cache) if a.stage == "fetch" else pack(a.cache, a.out)

"""Every season's top scorers and assisters from FotMob, for every competition on the site (owner 2026-09-30: the Argentine
league showed two seasons only; Transfermarkt's dataset has twelve competitions and Argentina from 2024 only).

    python -m db.fm_scorers [--upload]

FotMob keeps full leader lists for the seasons it has deep stats for (leagues?id=<comp>&season=<name> -> stats.players
-> fetchAllUrl; around five or six seasons for most leagues, more for the big ones). Older seasons answer with no lists.
Merged into v1/history/scorers/<comp>.json with db/scorers.py's Transfermarkt seasons: FotMob wins a season both have
(it is the league's own count), Transfermarkt keeps the older ones.
"""
import argparse, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from store import Store, S3Backend  # noqa: E402
from sources.fotmob import FotMob  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")


def lists(h, cid, season):
    """(goals top 10, assists top 10) for one season, or None when FotMob has no lists for it."""
    try:
        raw = h.get_json(f"https://www.fotmob.com/api/data/leagues?id={cid}&season={season.replace('/', '%2F')}", min_ttl=3600)
    except Exception:
        return None
    by = {p.get("name"): p.get("fetchAllUrl") for p in ((raw.get("stats") or {}).get("players") or []) if p.get("fetchAllUrl")}
    if not by.get("goals"):
        return None
    out = []
    for k in ("goals", "goal_assist"):
        try:
            r = h.get_json(by[k], min_ttl=3600) if by.get(k) else {}
        except Exception:
            r = {}
        tl = (r.get("TopLists") or [{}])[0].get("StatList") or []
        out.append([[x.get("ParticiantId") or x.get("ParticipantId"), x.get("ParticipantName"), int(x.get("StatValue") or 0), x.get("TeamId"), x.get("MatchesPlayed")] for x in tl[:10]])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); a = ap.parse_args(argv)
    store = Store(S3Backend(BUCKET)); h = FotMob().http
    comps = [c for c in (store.get_json("index.json") or {}).get("competitions") or [] if c.get("id")]
    par = json.load(open(os.path.join(ROOT, "names", "players_ar.json"), encoding="utf-8"))
    fmn = h.get_json("https://www.fotmob.com/api/translationmapping?locale=ar", min_ttl=3600).get("Participants") or {}   # FotMob's own Arabic, every id
    ar = lambda pid, fb: (par.get(str(pid)) or {}).get("ar") or fmn.get(str(pid)) or fb

    def one(c):
        cid = c["id"]
        try:
            seasons = (h.get_json(f"https://www.fotmob.com/api/data/leagues?id={cid}", min_ttl=3600).get("allAvailableSeasons")) or []
        except Exception:
            return cid, {}
        got, misses = {}, 0
        for s in seasons:
            r = lists(h, cid, s)
            if not r:
                misses += 1
                if misses >= 2:
                    break
                continue
            misses = 0
            got[s] = {"goals": [[p[0], ar(p[0], p[1]), p[2], p[3], p[4]] for p in r[0]], "assists": [[p[0], ar(p[0], p[1]), p[2], p[3], p[4]] for p in r[1]]}
            time.sleep(0.2)
        return cid, got

    with ThreadPoolExecutor(4) as ex:
        res = dict(ex.map(one, comps))
    n = 0
    for cid, got in res.items():
        if not got:
            continue
        old = store.get_json(f"history/scorers/{cid}.json") or {"seasons": {}}
        seasons = dict(old.get("seasons") or {})
        for s, v in got.items():
            seasons[s] = {"goals": [[p[0], p[1], p[2]] for p in v["goals"]], "assists": [[p[0], p[1], p[2]] for p in v["assists"]], "src": "fotmob"}
        doc = {"comp": cid, "seasons": dict(sorted(seasons.items())), "source": "FotMob (recent seasons) + Transfermarkt (older)"}
        n += 1
        print(cid, len(got), "FotMob seasons;", len(seasons), "in all; newest:", sorted(got)[-1], got[sorted(got)[-1]]["goals"][:1])
        if a.upload:
            store.put_json(f"history/scorers/{cid}.json", doc, cache="warm")
    if a.upload:
        idx = store.get_json("history/scorers/index.json") or {"comps": []}
        store.put_json("history/scorers/index.json", {"generated": date.today().isoformat(), "comps": sorted(set(idx.get("comps") or []) | {c for c, g in res.items() if g})}, cache="warm")
    print(n, "competitions with season leaders")
    return 0


if __name__ == "__main__":
    sys.exit(main())

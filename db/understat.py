"""Expected goals season by season since 2014 for every club in the big five leagues, from Understat
(understat.com, the site's own JSON: getLeagueData/<league>/<year>). Stage of the owner's database (2026-09-30 «كلها»).

    python -m db.understat [--upload]

Per team and season: xG, xGA, non-penalty xG, goals, goals against, points, expected points (xPts), and pressing
(PPDA: opponent passes per defensive action, lower = more pressing). A team is linked to our FotMob id by name within
the same league (exact folded name, else every word of Understat's name in exactly one of the league's team names),
then within the league's country (relegated clubs).
Out: v1/history/xg/<fotmob id>.json {seasons: [[season, comp, xg, xga, goals, against, pts, xpts, ppda]]}.
"""
import argparse, json, os, re, sys, time, unicodedata, urllib.request
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from store import Store, S3Backend  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
LEAGUES = {"EPL": 47, "La_liga": 87, "Bundesliga": 54, "Serie_A": 55, "Ligue_1": 53}
ALIAS = {"Wolverhampton Wanderers": "Wolves", "Manchester United": "Manchester United", "Newcastle United": "Newcastle", "Paris Saint Germain": "Paris Saint-Germain",
         "Bayern Munich": "Bayern München", "Borussia M.Gladbach": "Borussia Mönchengladbach", "Atletico Madrid": "Atlético Madrid", "AC Milan": "Milan",
         "Parma Calcio 1913": "Parma", "RasenBallsport Leipzig": "RB Leipzig", "Athletic Club": "Athletic Club", "Real Betis": "Real Betis", "Nottingham Forest": "Nottingham Forest"}


def fold(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(fc|cf|sc|ac|afc|club|calcio|ssc|as|us|1\. ?)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def get(league, year):
    req = urllib.request.Request(f"https://understat.com/getLeagueData/{league}/{year}", headers={"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest", "Accept-Encoding": "gzip"})
    raw = urllib.request.urlopen(req, timeout=90).read()
    if raw[:2] == b"\x1f\x8b":
        import gzip
        raw = gzip.decompress(raw)
    return json.loads(raw)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); a = ap.parse_args(argv)
    store = Store(S3Backend(BUCKET))
    teams = (store.get_json("teams.json") or {}).get("teams") or {}
    comps = {c["id"]: c for c in (store.get_json("index.json") or {}).get("competitions") or []}

    def link(cid, name):
        f = fold(ALIAS.get(name, name)); ws = set(f.split())
        cc = ((comps.get(cid) or {}).get("country") or {}).get("iso2")
        pools = [[k for k, t in teams.items() if cid in (t.get("comps") or [])],
                 [k for k, t in teams.items() if (t.get("country") or {}).get("iso2") == cc]]
        for pool in pools:
            ex = [k for k in pool if fold(teams[k].get("name")) == f]
            if len(ex) == 1:
                return int(ex[0])
            sub = [k for k in pool if ws and ws <= set(fold(teams[k].get("name")).split())]
            if len(sub) == 1:
                return int(sub[0])
        return None

    out, missing = defaultdict(list), set()
    this = date.today().year if date.today().month >= 8 else date.today().year - 1
    for lg, cid in LEAGUES.items():
        for y in range(2014, this + 1):
            try:
                d = get(lg, y)
            except Exception as e:
                print(lg, y, "failed", e); continue
            for t in d.get("teams", {}).values():
                h = t.get("history") or []
                if not h:
                    continue
                s = lambda k: sum(float(m.get(k) or 0) for m in h)
                ppda = [m["ppda"] for m in h if isinstance(m.get("ppda"), dict) and m["ppda"].get("def")]
                pp = round(sum(p["att"] for p in ppda) / max(1, sum(p["def"] for p in ppda)), 2) if ppda else None
                fid = link(cid, t["title"])
                if not fid:
                    missing.add(f"{lg}:{t['title']}"); continue
                out[fid].append([f"{y}/{y + 1}", cid, round(s("xG"), 1), round(s("xGA"), 1), int(s("scored")), int(s("missed")), int(s("pts")), round(s("xpts"), 1), pp, len(h)])
            time.sleep(0.6)
        print(lg, "done")
    for v in out.values():
        v.sort()
    print(len(out), "clubs with xG seasons;", len(missing), "unlinked:", sorted(missing)[:25])
    if a.upload:
        for fid, seasons in out.items():
            store.put_json(f"history/xg/{fid}.json", {"club": fid, "fields": ["season", "comp", "xg", "xga", "goals", "against", "pts", "xpts", "ppda", "matches"],
                                                       "seasons": seasons, "source": "Understat"}, cache="warm")
        store.put_json("history/xg/index.json", {"generated": date.today().isoformat(), "clubs": sorted(out)}, cache="warm")
        print("uploaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())

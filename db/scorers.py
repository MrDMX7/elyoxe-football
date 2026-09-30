"""Every season's top scorers and top assisters since 2012 (Transfermarkt datasets, CC0: game_events + games), for our
competitions Transfermarkt covers. Owner's database, 2026-09-30 «كلها».

    python -m db.scorers [--upload]

Goals exclude own goals; a player links to our FotMob id through history/transfermarkt.py's name + birth date map, and
then shows his Arabic name. Out: v1/history/scorers/<comp id>.json {seasons: {"2024/2025": {goals: [[fotmob id|null,
name, n]], assists: [...]}}} (top 10 each).
"""
import argparse, json, os, sys
from collections import Counter, defaultdict
from datetime import date

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from store import Store, S3Backend  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
C = os.path.join(HERE, ".cache")
TM2FM = {"GB1": 47, "ES1": 87, "IT1": 55, "L1": 54, "FR1": 53, "CL": 42, "EL": 73, "UCOL": 10216, "SA1": 536, "MLS1": 130, "BRA1": 268, "ARG1": 112}


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); a = ap.parse_args(argv)
    con = duckdb.connect()
    ev, gm = os.path.join(C, "tm_game_events.csv.gz").replace("\\", "/"), os.path.join(C, "tm_games.csv.gz").replace("\\", "/")
    pl = os.path.join(ROOT, "history", ".cache", "tm_players.csv.gz")
    names = {}
    if os.path.exists(pl):
        for pid, nm in con.execute(f"select player_id, name from read_csv_auto('{pl.replace(chr(92), '/')}')").fetchall():
            names[pid] = nm
    tm2fm = {}
    try:
        tm2fm = {int(k): int(v) for k, v in json.load(open(os.path.join(ROOT, "history", ".cache", "tm_playermap.json"), encoding="utf-8")).items()}
    except OSError:
        pass
    par = json.load(open(os.path.join(ROOT, "names", "players_ar.json"), encoding="utf-8"))
    comps = "', '".join(TM2FM)
    rows = con.execute(f"""select g.competition_id, g.season, e.type, e.player_id, e.player_assist_id, coalesce(e.description, '')
        from read_csv_auto('{ev}') e join read_csv_auto('{gm}') g using (game_id)
        where e.type = 'Goals' and g.competition_id in ('{comps}')""").fetchall()
    goals, assists = defaultdict(Counter), defaultdict(Counter)
    for comp, season, _, pid, ast, desc in rows:
        if "own" in desc.lower():
            continue
        k = (comp, int(season))
        if pid: goals[k][pid] += 1
        if ast: assists[k][ast] += 1
    out = defaultdict(lambda: {"seasons": {}})
    for (comp, season), cnt in goals.items():
        cid = TM2FM[comp]
        top = lambda c: [[tm2fm.get(p), (par.get(str(tm2fm.get(p))) or {}).get("ar") or names.get(p) or str(p), n] for p, n in c.most_common(10)]
        out[cid]["seasons"][f"{season}/{season + 1}"] = {"goals": top(cnt), "assists": top(assists[(comp, season)])}
    for cid, d in out.items():
        d["seasons"] = dict(sorted(d["seasons"].items()))
        print(cid, len(d["seasons"]), "seasons; latest top scorer:", list(d["seasons"].values())[-1]["goals"][:1])
    if a.upload:
        store = Store(S3Backend(BUCKET))
        for cid, d in out.items():
            store.put_json(f"history/scorers/{cid}.json", dict(d, comp=cid, source="Transfermarkt (transfermarkt-datasets, CC0)"), cache="warm")
        store.put_json("history/scorers/index.json", {"generated": date.today().isoformat(), "comps": sorted(out)}, cache="warm"); print("uploaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())

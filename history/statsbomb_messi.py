"""Every shot Lionel Messi took in StatsBomb's open data (github.com/statsbomb/open-data; free with credit to StatsBomb, no
Share-Alike): La Liga 2004/05-2020/21 with Barcelona, Ligue 1 with PSG, World Cups 2018 and 2022, Copa América 2024,
Champions League finals, MLS 2023. For the Messi page and its 3D pitch (owner 2026-09-30: «صفحات… لميسي واي مكان لعب
فيه»; the climax rule: one moment that is impossible without 3D — all his goals on one pitch, from where he hit them).

    python -m history.statsbomb_messi [--upload]

Resumable: each match's extracted shots are cached in history/.cache/sb/<match>.json, so a cut run picks up where it
stopped (the raw event files are ~3 MB each and are not kept). Output: v1/legends/messi/shots.json.
"""
import argparse, json, os, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
CACHE = os.path.join(HERE, ".cache", "sb")
MESSI = 5503
TEAMS = {"Barcelona", "Paris Saint-Germain", "Argentina", "Inter Miami"}
COMPS = {11: "الدوري الإسباني", 7: "الدوري الفرنسي", 43: "كأس العالم", 223: "كوبا أمريكا", 16: "دوري أبطال أوروبا", 44: "الدوري الأمريكي"}
BODY = {"Left Foot": "L", "Right Foot": "R", "Head": "H"}


def get(path):
    return json.loads(urllib.request.urlopen(urllib.request.Request(ROOT + path, headers={"User-Agent": "elyoxe-tifo/0.1"}), timeout=120).read())


def shots(m):
    cf = os.path.join(CACHE, f"{m['match_id']}.json")
    if os.path.exists(cf):
        return json.load(open(cf, encoding="utf-8"))
    ev = get(f"/events/{m['match_id']}.json")
    home, away = m["home_team"]["home_team_name"], m["away_team"]["away_team_name"]
    mine = home if home in TEAMS else away
    out = []
    for e in ev:
        if e.get("type", {}).get("name") != "Shot" or (e.get("player") or {}).get("id") != MESSI:
            continue
        s = e["shot"]; end = s.get("end_location") or [None, None, None]
        out.append({"x": e["location"][0], "y": e["location"][1], "ex": end[0], "ey": end[1], "ez": end[2] if len(end) > 2 else None,
                    "xg": round(s.get("statsbomb_xg") or 0, 3), "goal": s["outcome"]["name"] == "Goal", "out": s["outcome"]["name"],
                    "body": BODY.get(s.get("body_part", {}).get("name"), "O"), "kind": s.get("type", {}).get("name"),
                    "min": e["minute"], "period": e["period"]})
    rec = {"match": m["match_id"], "date": m["match_date"], "comp": m["competition"]["competition_id"], "season": m["season"]["season_name"],
           "team": mine, "opp": away if mine == home else home, "score": [m["home_score"], m["away_score"]], "home": mine == home, "shots": out}
    os.makedirs(CACHE, exist_ok=True)
    json.dump(rec, open(cf + ".tmp", "w", encoding="utf-8", newline="\n")); os.replace(cf + ".tmp", cf)
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); a = ap.parse_args(argv)
    seasons = [(c["competition_id"], c["season_id"]) for c in get("/competitions.json")
               if c["competition_id"] in COMPS and c["competition_gender"] == "male" and c["season_name"] >= "2004"]
    matches = []
    for cid, sid in seasons:
        for m in get(f"/matches/{cid}/{sid}.json"):
            if m["home_team"]["home_team_name"] in TEAMS or m["away_team"]["away_team_name"] in TEAMS:
                matches.append(m)
    print(len(matches), "matches with his teams")
    with ThreadPoolExecutor(8) as ex:
        recs = list(ex.map(shots, matches))
    recs = [r for r in recs if r["shots"]]
    recs.sort(key=lambda r: r["date"])
    goals = sum(1 for r in recs for s in r["shots"] if s["goal"])
    n = sum(len(r["shots"]) for r in recs)
    print(f"{len(recs)} matches with a Messi shot, {n} shots, {goals} goals")
    out = {"source": "StatsBomb open data (github.com/statsbomb/open-data)", "comps": {str(k): v for k, v in COMPS.items()},
           "pitch": "StatsBomb 120x80, x toward the goal he attacks", "matches": recs,
           "totals": {"matches": len(recs), "shots": n, "goals": goals}}
    path = os.path.join(HERE, ".cache", "messi_shots.json")
    json.dump(out, open(path, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, separators=(",", ":"))
    print("wrote", path, os.path.getsize(path) // 1024, "KB")
    if a.upload:
        sys.path.insert(0, os.path.dirname(HERE))
        from store import Store, S3Backend
        Store(S3Backend(os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1"))).put_json("legends/messi/shots.json", out, cache="static")
        print("uploaded v1/legends/messi/shots.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Messi in StatsBomb's open data (github.com/statsbomb/open-data; free with credit to StatsBomb, no Share-Alike): every
match of his in La Liga 2004/05-2020/21, Ligue 1 with PSG, the World Cups 2018 and 2022, Copa América 2024, the
Champions League finals and MLS 2023. Feeds the Messi museum (/messi/, owner 2026-09-30: «حول صفحته لمتحف»).

    python -m history.statsbomb_messi [--upload]

One pass over each match's events + lineups, cached per match in history/.cache/sb2/<match>.json (resumable; the raw
~3 MB event files are not kept). Out, public under v1/legends/messi/:
  shots.json    every shot (strike point, crossing point with height, xG, body part, kind), per match   (the 3D pitch)
  play.json     assists and key passes (from -> to), completed dribbles, progressive carries, touches per season
                on a 12x8 grid (the layered-seasons climax), pass links with each teammate, co-starts, minutes
  matches.json  one line per match: date, competition, opponent, score, coach, goals, assists, key passes, dribbles
"""
import argparse, json, os, sys, urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
CACHE = os.path.join(HERE, ".cache", "sb2")
MESSI = 5503
TEAMS = {"Barcelona", "Paris Saint-Germain", "Argentina", "Inter Miami"}
COMPS = {11: "الدوري الإسباني", 7: "الدوري الفرنسي", 43: "كأس العالم", 223: "كوبا أمريكا", 16: "دوري أبطال أوروبا", 44: "الدوري الأمريكي"}
BODY = {"Left Foot": "L", "Right Foot": "R", "Head": "H"}
R1 = lambda v: None if v is None else round(v, 1)


def get(path):
    return json.loads(urllib.request.urlopen(urllib.request.Request(ROOT + path, headers={"User-Agent": "elyoxe-tifo/0.1"}), timeout=120).read())


def mins(t):   # "12:34" -> 12.6
    a, b = t.split(":")[:2]
    return int(a) + int(b) / 60


def one(m):
    cf = os.path.join(CACHE, f"{m['match_id']}.json")
    if os.path.exists(cf):
        return json.load(open(cf, encoding="utf-8"))
    ev, lu = get(f"/events/{m['match_id']}.json"), get(f"/lineups/{m['match_id']}.json")
    home, away = m["home_team"]["home_team_name"], m["away_team"]["away_team_name"]
    mine = home if home in TEAMS else away
    side = m["home_team"] if mine == home else m["away_team"]
    coach = ((side.get("managers") or [{}])[0]).get("nickname") or ((side.get("managers") or [{}])[0]).get("name")
    last = max((e["minute"] for e in ev), default=90)
    # lineups: nicknames, who started, Messi's minutes
    nick, started, messi_min = {}, [], 0
    for t in lu:
        if t["team_name"] != mine:
            continue
        for p in t["lineup"]:
            nick[p["player_id"]] = p.get("player_nickname") or p["player_name"]
            pos = p.get("positions") or []
            if pos and pos[0].get("start_reason") == "Starting XI":
                started.append(p["player_id"])
            if p["player_id"] == MESSI and pos:
                messi_min = round(sum(((mins(x["to"]) if x.get("to") else last) - mins(x["from"])) for x in pos))
    shots, assists, keyp, drib, carries, touches = [], [], [], [], [], Counter()
    to_mate, from_mate, drib_try = Counter(), Counter(), 0
    for e in ev:
        t = e.get("type", {}).get("name"); pl = (e.get("player") or {}).get("id")
        if t == "Pass" and (e.get("pass") or {}).get("recipient", {}).get("id") == MESSI and pl != MESSI and not (e["pass"].get("outcome")):
            from_mate[pl] += 1
        if pl != MESSI:
            continue
        loc = e.get("location")
        if loc:
            touches[(min(11, int(loc[0] // 10)), min(7, int(loc[1] // 10)))] += 1
        if t == "Shot":
            s = e["shot"]; end = s.get("end_location") or [None, None, None]
            shots.append({"x": R1(loc[0]), "y": R1(loc[1]), "ex": R1(end[0]), "ey": R1(end[1]), "ez": R1(end[2]) if len(end) > 2 else None,
                          "xg": round(s.get("statsbomb_xg") or 0, 3), "goal": s["outcome"]["name"] == "Goal", "out": s["outcome"]["name"],
                          "body": BODY.get(s.get("body_part", {}).get("name"), "O"), "kind": s.get("type", {}).get("name"),
                          "min": e["minute"], "period": e["period"], "first_time": bool(s.get("first_time"))})
        elif t == "Pass":
            p = e["pass"]; rec = (p.get("recipient") or {}).get("id")
            if not p.get("outcome") and rec:
                to_mate[rec] += 1
            if p.get("goal_assist") or p.get("shot_assist"):
                (assists if p.get("goal_assist") else keyp).append([R1(loc[0]), R1(loc[1]), R1(p["end_location"][0]), R1(p["end_location"][1]), nick.get(rec) or (p.get("recipient") or {}).get("name"), e["minute"]])
        elif t == "Dribble":
            drib_try += 1
            if (e.get("dribble") or {}).get("outcome", {}).get("name") == "Complete":
                drib.append([R1(loc[0]), R1(loc[1])])
        elif t == "Carry":
            end = e["carry"]["end_location"]
            if end[0] - loc[0] >= 10 or (end[0] >= 102 and 18 <= end[1] <= 62 and not (loc[0] >= 102 and 18 <= loc[1] <= 62)):
                carries.append([R1(loc[0]), R1(loc[1]), R1(end[0]), R1(end[1])])
    rec = {"match": m["match_id"], "date": m["match_date"], "comp": m["competition"]["competition_id"], "season": m["season"]["season_name"],
           "stage": (m.get("competition_stage") or {}).get("name"), "team": mine, "opp": away if mine == home else home,
           "score": [m["home_score"], m["away_score"]], "home": mine == home, "coach": coach, "min": messi_min,
           "started": MESSI in started, "played": MESSI in nick and (messi_min > 0 or any(True for _ in shots)),
           "xi": [nick.get(i) for i in started if i != MESSI], "shots": shots, "assists": assists, "keyp": keyp, "drib": drib,
           "drib_try": drib_try, "carries": carries, "touches": [[a, b, n] for (a, b), n in touches.items()],
           "to": {nick.get(k) or str(k): v for k, v in to_mate.items()}, "from": {nick.get(k) or str(k): v for k, v in from_mate.items()}}
    os.makedirs(CACHE, exist_ok=True)
    json.dump(rec, open(cf + ".tmp", "w", encoding="utf-8", newline="\n")); os.replace(cf + ".tmp", cf)
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); a = ap.parse_args(argv)
    seasons = [(c["competition_id"], c["season_id"]) for c in get("/competitions.json")
               if c["competition_id"] in COMPS and c["competition_gender"] == "male" and c["season_name"] >= "2004"]
    matches = [m for cid, sid in seasons for m in get(f"/matches/{cid}/{sid}.json")
               if m["home_team"]["home_team_name"] in TEAMS or m["away_team"]["away_team_name"] in TEAMS]
    print(len(matches), "matches with his teams")
    with ThreadPoolExecutor(8) as ex:
        recs = [r for r in ex.map(one, matches) if r["played"]]
    recs.sort(key=lambda r: r["date"])
    goals = sum(1 for r in recs for s in r["shots"] if s["goal"])
    n = sum(len(r["shots"]) for r in recs)
    print(f"{len(recs)} matches he played, {n} shots, {goals} goals, {sum(len(r['assists']) for r in recs)} assists")
    src = "StatsBomb open data (github.com/statsbomb/open-data)"
    shots = {"source": src, "comps": {str(k): v for k, v in COMPS.items()}, "pitch": "StatsBomb 120x80, x toward the goal he attacks",
             "matches": [{k: r[k] for k in ("match", "date", "comp", "season", "team", "opp", "score", "home", "shots")} for r in recs if r["shots"]],
             "totals": {"matches": len(recs), "shots": n, "goals": goals}}
    # touches per season (the layered climax), progressive carries capped per season so the file stays small
    by_season = defaultdict(Counter); car = defaultdict(list); links = defaultdict(lambda: [0, 0]); costarts = Counter()
    for r in recs:
        k = f"{r['season']}|{r['team']}"
        for a_, b_, c_ in r["touches"]:
            by_season[k][(a_, b_)] += c_
        car[k] += r["carries"]
        for nm, v in r["to"].items():
            links[nm][0] += v
        for nm, v in r["from"].items():
            links[nm][1] += v
        costarts.update(x for x in r["xi"] if x)
    play = {"source": src,
            "assists": [dict(zip(("x", "y", "ex", "ey", "to", "min"), x), date=r["date"], opp=r["opp"], season=r["season"]) for r in recs for x in r["assists"]],
            "keyp": [x[:4] for r in recs for x in r["keyp"]],
            "drib": [x + [r["season"]] for r in recs for x in r["drib"]],
            "carries": {k: v[::max(1, len(v) // 150)][:150] for k, v in car.items()},
            "touches": {k: [[a_, b_, c_] for (a_, b_), c_ in v.items()] for k, v in by_season.items()},
            "links": sorted(([k, v[0], v[1]] for k, v in links.items() if v[0] + v[1] >= 40), key=lambda x: -(x[1] + x[2]))[:40],
            "costarts": costarts.most_common(40),
            "drib_try": sum(r["drib_try"] for r in recs), "drib_ok": sum(len(r["drib"]) for r in recs)}
    matches_doc = {"source": src, "comps": shots["comps"], "matches": [
        {"match": r["match"], "date": r["date"], "comp": r["comp"], "season": r["season"], "stage": r["stage"], "team": r["team"], "opp": r["opp"],
         "score": r["score"], "home": r["home"], "coach": r["coach"], "min": r["min"], "started": r["started"],
         "g": sum(1 for s in r["shots"] if s["goal"]), "a": len(r["assists"]), "kp": len(r["keyp"]) + len(r["assists"]),
         "sh": len(r["shots"]), "xg": round(sum(s["xg"] for s in r["shots"]), 2), "dr": len(r["drib"])} for r in recs]}
    out_dir = os.path.join(HERE, ".cache", "messi"); os.makedirs(out_dir, exist_ok=True)
    for name, doc in (("shots", shots), ("play", play), ("matches", matches_doc)):
        p = os.path.join(out_dir, name + ".json")
        json.dump(doc, open(p, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, separators=(",", ":"))
        print(name, os.path.getsize(p) // 1024, "KB")
    if a.upload:
        sys.path.insert(0, os.path.dirname(HERE))
        from store import Store, S3Backend
        st = Store(S3Backend(os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")))
        for name, doc in (("shots", shots), ("play", play), ("matches", matches_doc)):
            st.put_json(f"legends/messi/{name}.json", doc, cache="static")
        print("uploaded v1/legends/messi/{shots,play,matches}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

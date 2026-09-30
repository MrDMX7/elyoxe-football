"""Every match of every competition on the site since 2010, in detail (owner 2026-09-30: «متى بيكتمل كل شي من نتايج
ومباريات وكروت ولمسات وصناعات»), then every player's match log and season totals built from them.

    python -m db.matches [--upload] [--season 2024-2025] [--limit N]

Source: FotMob matchDetails for each match id in our own archive (v1/archive/all/<season>.json). What FotMob has depends
on the season and the league: in the UAE league 2010/11 the result only; from about 2014-2017 lineups, goals with the
assist, cards and substitutions; in recent seasons every player's stats (touches, passes, shots, dribbles, tackles…).
A finished match never changes: its compact record is cached for good in db/.cache/fm/mx/<id>.json and never fetched
again, so the daily run only asks for new matches.
Out (public):
  v1/matchx/<id>.json          one match: teams, score, date, round, stadium, referee, lineups, events, player stats
  v1/player/<id>/log.json      every match of the player (club and country) and his totals per season and competition

Events are compact arrays: goal [minute, "g", side, player id, name, assist id, "pen"|"own"|null, how_ar, how_key] —
the last two (compute/goal_how.py: «رأسية من ركنية», "header+corner") only on goals fetched from 2026-09-30 on, and only
when FotMob's event, its shot or the live ticker the poller read (v1/match/<id>.json) says how; older cached records keep
7 fields (the raw details they came from were not kept, and refetching 66k matches is not worth it). Cards
[minute, "y"|"r"|"c", side, id, name, null, card], substitutions [minute, "s", side, in id, in name, out id, out name].
"""
import argparse, json, os, re, sys, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from store import Store, S3Backend  # noqa: E402
from sources.fotmob import FotMob  # noqa: E402
from compute import goal_how as GH  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
MX = os.path.join(HERE, ".cache", "fm", "mx")
STORE = None          # main() sets it: fetch() reads the poller's match file for goals FotMob's event does not describe
# player stats kept per match (FotMob keys); the rest of FotMob's thirty-odd lines stay out of the files
KEEP = {"rating_title": "r", "minutes_played": "min", "goals": "g", "assists": "a", "total_shots": "sh", "ShotsOnTarget": "sot", "touches": "tch",
        "accurate_passes": "pas", "chances_created": "kp", "expected_goals": "xg", "expected_assists": "xa", "dribbles_succeeded": "dr",
        "successful_dribbles": "dr", "tackles_won": "tk", "matchstats.headers.tackles": "tk", "interceptions": "int", "clearances": "clr", "recoveries": "rec",
        "duel_won": "dw", "ground_duels_won": "gdw", "aerials_won": "aw", "was_fouled": "fd", "fouls": "fc", "saves": "sv", "goals_conceded": "gc",
        "accurate_crosses": "cr", "accurate_long_balls": "lb", "dispossessed": "dsp", "blocked_shots": "blk"}
FM = None


def val(stat):
    s = stat.get("stat") or {}
    v, t = s.get("value"), s.get("total")
    return [v, t] if t is not None else v


def compact(raw, mid):
    c, g, hd = raw.get("content") or {}, raw.get("general") or {}, raw.get("header") or {}
    teams = hd.get("teams") or [{}, {}]
    info = (c.get("matchFacts") or {}).get("infoBox") or {}
    stad, ref = info.get("Stadium") or {}, info.get("Referee") or {}
    m = {"id": mid, "date": g.get("matchTimeUTCDate") or (info.get("Match Date") or {}).get("utcTime") or g.get("matchTimeUTC"), "comp": g.get("parentLeagueId") or g.get("leagueId"),
         "round": g.get("leagueRoundName") or (info.get("Tournament") or {}).get("roundName"),
         "home": [teams[0].get("id"), teams[0].get("name"), teams[0].get("score")], "away": [teams[1].get("id"), teams[1].get("name"), teams[1].get("score")],
         "stadium": [stad.get("name"), stad.get("city")] if stad else None, "referee": ref.get("text") if isinstance(ref, dict) else None,
         "attendance": info.get("Attendance"), "lineups": {}, "events": [], "ps": {}}
    lu = c.get("lineup") or {}
    for side in ("homeTeam", "awayTeam"):
        t = lu.get(side) or {}
        rows = []
        for starter, grp in ((1, t.get("starters") or []), (0, t.get("subs") or [])):
            for p in grp:
                rows.append([p.get("id"), p.get("name"), p.get("shirtNumber"), p.get("positionId"), starter, ((p.get("performance") or {}).get("rating"))])
        if rows:
            m["lineups"]["h" if side == "homeTeam" else "a"] = {"formation": t.get("formation"), "players": rows}
    for e in ((c.get("matchFacts") or {}).get("events") or {}).get("events") or []:
        tp, side = e.get("type"), "h" if e.get("isHome") else "a"
        if tp == "Goal" and not e.get("isPenaltyShootoutEvent"):
            ap = re.search(r"/players/(\d+)", e.get("assistProfileUrl") or "")
            row = [e.get("time"), "g", side, e.get("playerId"), e.get("nameStr") or e.get("fullName"), int(ap.group(1)) if ap else None,
                   "own" if e.get("ownGoal") else ("pen" if (e.get("goalDescriptionKey") or "").startswith("pen") or e.get("suffixKey") == "penalty" else None)]
            how = GH.describe(e)                                  # how it was scored: «رأسية من ركنية» (appended, optional)
            if how:
                row += [how["ar"], how["key"]]
            m["events"].append(row)
        elif tp == "Card":
            m["events"].append([e.get("time"), "y" if e.get("card") == "Yellow" else "r" if e.get("card") in ("Red", "YellowRed") else "c", side, e.get("playerId"),
                                (e.get("player") or {}).get("name"), None, e.get("card")])
        elif tp == "Substitution":
            sw = e.get("swap") or [{}, {}]
            m["events"].append([e.get("time"), "s", side, int(sw[0].get("id") or 0) or None, sw[0].get("name"), int(sw[1].get("id") or 0) or None, sw[1].get("name")])
    for pid, p in (c.get("playerStats") or {}).items():
        row = {}
        for grp in p.get("stats") or []:
            for st in (grp.get("stats") or {}).values():
                k = KEEP.get(st.get("key"))
                if k and k not in row and (st.get("stat") or {}).get("value") is not None:
                    row[k] = val(st)
        if row:
            row["t"] = p.get("teamId")
            m["ps"][str(pid)] = row
    return m


def fill_how(m, poller_doc):
    """Goals FotMob's event and shot leave undescribed (no shot map: the UAE leagues…) take the description the poller
    wrote from the live ticker into v1/match/<id>.json (compute/goal_how.py), matched on minute and scorer."""
    how = {}
    for e in (poller_doc or {}).get("events") or []:
        if e.get("how") and "goal" in (e.get("type") or ""):
            how[(e.get("minute"), (e.get("player") or {}).get("id"))] = e["how"]
    for e in m["events"]:
        if e[1] == "g" and len(e) < 8:
            h = how.get((e[0], e[3]))
            if h:
                e += [h["ar"], h["key"]]
    return m


def fetch(mid):
    global FM
    p = os.path.join(MX, f"{mid}.json")
    if os.path.exists(p):
        try:
            return json.load(open(p, encoding="utf-8"))
        except ValueError:
            pass
    FM = FM or FotMob()
    for i in range(3):
        try:
            raw = FM.http.get_json(f"https://www.fotmob.com/api/data/matchDetails?matchId={mid}", min_ttl=0)
            m = compact(raw, mid)
            if STORE is not None and any(e[1] == "g" and len(e) < 8 for e in m["events"]):
                try:
                    fill_how(m, STORE.get_json(f"match/{mid}.json"))
                except Exception:
                    pass                         # the poller never had this match (older than the poller): nothing to add
            if not ((raw.get("general") or {}).get("finished")):
                return m                     # not over yet: not cached, asked again next run
            os.makedirs(MX, exist_ok=True)
            json.dump(m, open(p + ".tmp", "w", encoding="utf-8", newline="\n"), ensure_ascii=False, separators=(",", ":")); os.replace(p + ".tmp", p)
            return m
        except Exception as e:
            if "404" in str(e):
                return None
            time.sleep(3 * (i + 1))
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); ap.add_argument("--season"); ap.add_argument("--limit", type=int, default=0); ap.add_argument("--comp", type=int)
    a = ap.parse_args(argv)
    global STORE
    store = STORE = Store(S3Backend(BUCKET))
    seasons = [s["season"] for s in ((store.get_json("archive/index-all.json") or {}).get("seasons") or []) if s["season"] != "unknown"]
    if a.season:
        seasons = [a.season]
    ids = []
    for s in seasons:
        for r in (store.get_json(f"archive/all/{s}.json") or {}).get("matches") or []:
            if r[5] is not None and (not a.comp or r[2] == a.comp):
                ids.append(r[0])
    ids = sorted(set(ids), reverse=True)
    if a.limit:
        ids = ids[:a.limit]
    todo = [i for i in ids if not os.path.exists(os.path.join(MX, f"{i}.json"))]
    print(f"{len(ids)} finished matches; {len(todo)} to fetch")
    t0 = time.time()
    with ThreadPoolExecutor(int(os.environ.get("FM_THREADS", "12"))) as ex:
        ms = [m for m in ex.map(fetch, ids) if m]
    print(f"{len(ms)} matches ({round(time.time() - t0)}s); with lineups {sum(1 for m in ms if m['lineups'])}, with player stats {sum(1 for m in ms if m['ps'])}")
    # every player's log and season totals
    logs = defaultdict(list)
    for m in ms:
        on = defaultdict(dict)
        for side in ("h", "a"):
            team = m["home"] if side == "h" else m["away"]; opp = m["away"] if side == "h" else m["home"]
            for p in ((m["lineups"].get(side) or {}).get("players") or []):
                if p[0]:
                    on[p[0]] = {"team": team[0], "opp": opp[0], "side": side, "start": p[4], "r": p[5]}
        for e in m["events"]:
            if e[1] == "s" and e[3] and e[3] not in on:            # a substitute the lineup left out
                on[e[3]] = {"team": (m["home"] if e[2] == "h" else m["away"])[0], "opp": (m["away"] if e[2] == "h" else m["home"])[0], "side": e[2], "start": 0}
        for pid, x in list(on.items()):
            st = m["ps"].get(str(pid)) or {}
            if not x["start"] and not st.get("min") and not any(e[1] == "s" and e[3] == pid for e in m["events"]):
                continue                                           # an unused substitute
            # goals and assists: the player's own stat line when the match has one (FotMob credits assists there even when the
            # goal event names none), else the events
            g = st.get("g") if st.get("g") is not None else sum(1 for e in m["events"] if e[1] == "g" and e[3] == pid and e[6] != "own")
            a_ = st.get("a") if st.get("a") is not None else sum(1 for e in m["events"] if e[1] == "g" and e[5] == pid)
            y = sum(1 for e in m["events"] if e[1] == "y" and e[3] == pid); rd = sum(1 for e in m["events"] if e[1] == "r" and e[3] == pid)
            gs = m["home"][2] if x["side"] == "h" else m["away"][2]; ga = m["away"][2] if x["side"] == "h" else m["home"][2]
            logs[pid].append([m["id"], (m["date"] or "")[:10], m["comp"], x["team"], x["opp"], gs, ga, x["start"], st.get("min"), g, a_, y, rd, st.get("r") or x.get("r"),
                              {k: v for k, v in st.items() if k not in ("r", "min", "g", "a", "t")}])
    print(len(logs), "players with a match log")
    tm = FotMob().http.get_json("https://www.fotmob.com/api/translationmapping?locale=ar", min_ttl=3600)
    TT, PP = tm.get("TournamentTemplates") or {}, tm.get("Participants") or {}
    if a.upload:
        with ThreadPoolExecutor(8) as ex:
            list(ex.map(lambda m: store.put_json(f"matchx/{m['id']}.json", dict(m, names={"comp": TT.get(str(m["comp"])),
                                                                                           "home": PP.get(str(m["home"][0])), "away": PP.get(str(m["away"][0]))}), cache="static"), ms))

        def season_of(d):
            y, mo = int(d[:4]), int(d[5:7])
            return f"{y}/{y + 1}" if mo >= 7 else f"{y - 1}/{y}"

        def one(item):
            pid, L = item
            L.sort(key=lambda r: r[1], reverse=True)
            tot = {}
            for r in L:
                k = f"{season_of(r[1])}|{r[2]}"
                t = tot.setdefault(k, {"season": season_of(r[1]), "comp": r[2], "apps": 0, "starts": 0, "min": 0, "g": 0, "a": 0, "y": 0, "r": 0, "rs": 0, "rn": 0})
                t["apps"] += 1; t["starts"] += 1 if r[7] else 0; t["min"] += r[8] or 0; t["g"] += r[9]; t["a"] += r[10]; t["y"] += r[11]; t["r"] += r[12]
                if r[13]:
                    t["rs"] += float(r[13]); t["rn"] += 1
                for sk, sv in (r[14] or {}).items():
                    t[sk] = round(t.get(sk, 0) + (sv[0] if isinstance(sv, list) else (sv or 0)), 2)
            store.put_json(f"player/{pid}/log.json", {"player": pid, "fields": ["match", "date", "comp", "team", "opp", "for", "against", "started", "minutes", "goals",
                                                                                "assists", "yellow", "red", "rating", "stats"],
                                                        "matches": L, "seasons": sorted(tot.values(), key=lambda t: t["season"], reverse=True), "source": "FotMob",
                                                        # Arabic names for what the log shows (FotMob's own mapping), so the page needs nothing else
                                                        "comps": {str(c): TT.get(str(c)) for c in {r[2] for r in L} if TT.get(str(c))},
                                                        "teams": {str(t): PP.get(str(t)) for t in {x for r in L for x in (r[3], r[4])} if PP.get(str(t))}}, cache="warm")
        with ThreadPoolExecutor(8) as ex:
            list(ex.map(one, logs.items()))
        print("uploaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())

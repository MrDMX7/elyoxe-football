"""Transfermarkt's lineups, appearances and events (dcaribou game_lineups / appearances / game_events, CC0, 2012+; spec §9)
for the Transfermarkt matches FotMob doesn't hold (the leagues it has no archive for): starters and substitutes, minutes,
goals, assists, cards, and the goal / card / substitution events. A substitute who never came on is listed, not played."""
import csv, gzip, os
from collections import defaultdict


def _rows(path):
    if not os.path.exists(path):
        return
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def _i(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def load(G, reg, S):
    targets = {}
    for k, mid in list(reg.map.items()):
        if k.startswith("match|tm|"):
            mid = reg.resolve("match", mid)
            row = G.c.execute("SELECT src, home, away FROM match WHERE mid=?", (mid,)).fetchone()
            if row and row[0] == "tm" and not G.c.execute("SELECT 1 FROM appearance WHERE mid=? LIMIT 1", (mid,)).fetchone():
                targets[k.split("|", 2)[2]] = (mid, row[1], row[2])
    if not targets:
        return {"skipped": "no Transfermarkt-only match"}
    written = set()

    def player(tm_id, name=None):
        pid = reg.get("player", "tm", str(tm_id)) or reg.mint("player", "tm", str(tm_id))
        if pid not in written or name:
            written.add(pid)
            G.put("player", {"pid": pid, "name": name}, "tm")
        return pid

    def club(tm_id):
        return reg.get("team", "tm", str(tm_id)) or reg.mint("team", "tm", str(tm_id))

    apps = defaultdict(dict)                                   # game -> Transfermarkt player -> what we know
    for r in _rows(os.path.join(S.db, "tm_game_lineups.csv.gz")):
        if r["game_id"] in targets:
            apps[r["game_id"]][r["player_id"]] = {"name": r["player_name"], "club": r["club_id"], "started": 1 if r["type"] == "starting_lineup" else 0,
                                                  "shirt": r.get("number") or None, "captain": 1 if r.get("team_captain") == "1" else 0}
    for r in _rows(os.path.join(S.db, "tm_appearances.csv.gz")):
        if r["game_id"] in targets:
            a = apps[r["game_id"]].setdefault(r["player_id"], {"name": r["player_name"], "club": r["player_club_id"], "started": None, "shirt": None, "captain": 0})
            a.update(minutes=_i(r["minutes_played"]), goals=_i(r["goals"]), assists=_i(r["assists"]), yellow=_i(r["yellow_cards"]), red=_i(r["red_cards"]), seen=1)
    n = {"matches": 0, "appearances": 0, "events": 0}
    for g, plist in sorted(apps.items()):
        mid = targets[g][0]
        rows = [{"mid": mid, "pid": player(tmp, a["name"]), "tid": club(a["club"]), "played": 1 if a.get("seen") else 0, "started": a["started"],
                 "minutes": a.get("minutes") if a.get("seen") else 0, "shirt": a["shirt"], "captain": a["captain"], "goals": a.get("goals") or 0,
                 "assists": a.get("assists") or 0, "yellow": a.get("yellow") or 0, "red": a.get("red") or 0} for tmp, a in plist.items()]
        G.many("appearance", rows, "tm")
        n["matches"] += 1
        n["appearances"] += len(rows)
    evs = defaultdict(list)
    for r in _rows(os.path.join(S.db, "tm_game_events.csv.gz")):
        if r["game_id"] in targets:
            evs[r["game_id"]].append(r)
    for g, lst in sorted(evs.items()):
        mid, home = targets[g][0], targets[g][1]
        out = []
        for r in lst:
            tid = club(r["club_id"])
            d = (r.get("description") or "").lower()
            if r["type"] == "Goals":
                tp = "own_goal" if "own" in d and "goal" in d else "penalty_goal" if "penalty" in d else "goal"
                pid, pid2 = player(r["player_id"]), (player(r["player_assist_id"]) if r.get("player_assist_id") else None)
            elif r["type"] == "Cards":
                tp = "second_yellow" if "second yellow" in d else "red" if "red card" in d else "yellow"
                pid, pid2 = player(r["player_id"]), None
            elif r["type"] == "Substitutions":
                tp, pid, pid2 = "sub", (player(r["player_in_id"]) if r.get("player_in_id") else None), player(r["player_id"])
            else:
                continue
            out.append((_i(r["minute"]), tp, "h" if tid == home else "a", tid, pid, pid2))
        out.sort(key=lambda e: e[0] if e[0] is not None else 999)
        G.many("event", [{"mid": mid, "seq": i, "minute": e[0], "added": 0, "type": e[1], "side": e[2], "tid": e[3], "pid": e[4], "pid2": e[5]}
                         for i, e in enumerate(out)], "tm")
        n["events"] += len(out)
    return n

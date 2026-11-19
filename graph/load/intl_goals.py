"""International scorers since 1916 (martj42 goalscorers.csv, CC0; spec §9): goal events (minute, penalty, own goal) and the
scorer's appearance on the internationals the graph holds without events. A scorer is a player of his national team by name
(`martj42-name`, «<team>|<name>»): the dataset gives no ids."""
import csv, os
from collections import defaultdict


def _i(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def load(G, reg, S):
    p = os.path.join(S.db, "martj42_goalscorers.csv")
    if not os.path.exists(p):
        return {"skipped": "no martj42_goalscorers.csv"}
    by = defaultdict(list)
    for r in csv.DictReader(open(p, encoding="utf-8", newline="")):
        by[f"{r['date']}|{r['home_team']}|{r['away_team']}"].append(r)
    n = {"matches": 0, "goals": 0}
    for key in sorted(by):
        mid = reg.get("match", "martj42", key)
        if mid is None or G.c.execute("SELECT 1 FROM event WHERE mid=? LIMIT 1", (mid,)).fetchone():
            continue
        m = G.c.execute("SELECT home, away FROM match WHERE mid=?", (mid,)).fetchone()
        if not m:
            continue
        home_name = key.split("|")[1]
        evs, apps = [], defaultdict(int)
        for r in by[key]:
            pk = f"{r['team']}|{r['scorer']}"
            pid = reg.get("player", "martj42-name", pk) or reg.mint("player", "martj42-name", pk)
            G.put("player", {"pid": pid, "name": r["scorer"]}, "martj42")
            own, side = r["own_goal"].upper() == "TRUE", "h" if r["team"] == home_name else "a"
            tp = "own_goal" if own else "penalty_goal" if r["penalty"].upper() == "TRUE" else "goal"
            evs.append((_i(r["minute"]), tp, side, pid))
            if not own:
                apps[(pid, side)] += 1
        evs.sort(key=lambda e: e[0] if e[0] is not None else 999)
        G.many("event", [{"mid": mid, "seq": i, "minute": e[0], "added": 0, "type": e[1], "side": e[2], "tid": m[0] if e[2] == "h" else m[1], "pid": e[3]}
                         for i, e in enumerate(evs)], "martj42")
        G.many("appearance", [{"mid": mid, "pid": pid, "tid": m[0] if side == "h" else m[1], "played": 1, "goals": g}
                              for (pid, side), g in apps.items()], "martj42")
        n["matches"] += 1
        n["goals"] += len(evs)
    return n

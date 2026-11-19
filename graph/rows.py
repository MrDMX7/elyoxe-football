"""One finished FotMob match (db/matches.py's compact record) as graph rows. The nightly build and, in phase 6, the
poller at the final whistle both call match_rows, so the two can never count differently."""
import json, re
from collections import Counter, defaultdict
from graph.fm import iso

GOAL = {None: "goal", "own": "own_goal", "pen": "penalty_goal"}


def _minute(v):
    m = re.match(r"(\d+)(?:\+(\d+))?", str(v if v is not None else ""))
    return (int(m.group(1)), int(m.group(2) or 0)) if m else (None, 0)


def _int(v):
    try:
        return int(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def match_rows(rec, eid, reg):
    from db.matches import est_minutes
    out, seen = defaultdict(list), set()

    def ent(t, src_id, row, method="fotmob-native", src="fotmob"):
        i = reg.mint(t, src, src_id)
        if (t, i) not in seen:
            seen.add((t, i))
            out["xref"].append((t, i, src, str(src_id), method, 1.0))
            row = dict(row)
            row[{"team": "tid", "player": "pid", "referee": "rid", "stadium": "sid", "match": "mid"}[t]] = i
            out[t].append(row)
        return i

    h, a = rec["home"], rec["away"]
    side_t = {"h": ent("team", h[0], {"name": h[1]}), "a": ent("team", a[0], {"name": a[1]})}
    st = rec.get("stadium") or [None, None]
    sid = ent("stadium", f"{st[0]}|{st[1] or ''}", {"name": st[0], "city": st[1]}, "fotmob-name", "fotmob-name") if st[0] else None
    rid = ent("referee", rec["referee"], {"name": rec["referee"]}, "fotmob-name", "fotmob-name") if rec.get("referee") else None
    mid = ent("match", rec["id"], {"eid": eid, "round": rec.get("round"), "date": iso(rec.get("date")), "home": side_t["h"], "away": side_t["a"],
                                   "hs": h[2], "as_": a[2], "status": "finished", "sid": sid, "rid": rid, "attendance": _int(rec.get("attendance"))})
    events = rec.get("events") or []
    ps = rec.get("ps") or {}
    goals, assists, yellow, red, came_on = Counter(), Counter(), Counter(), Counter(), set()
    for e in events:
        if e[1] == "g" and e[6] != "own":
            goals[e[3]] += 1
            if e[5]:
                assists[e[5]] += 1
        elif e[1] == "y":
            yellow[e[3]] += 1
        elif e[1] == "r":
            red[e[3]] += 1
        elif e[1] == "s" and e[3]:
            came_on.add(e[3])
    in_lineup = set()

    def appear(fid, name, side, shirt=None, position=None, started=None, rating=None):
        pid = ent("player", fid, {"name": name})
        s = ps.get(str(fid)) or {}
        minutes = s.get("min")
        if minutes is None and started is not None:
            minutes = est_minutes(rec, fid, started)
        if started:
            played = 1
        elif started == 0:
            played = 1 if (fid in came_on or (minutes or 0) > 0) else (0 if any(e[1] == "s" for e in events) or ps else None)
        else:
            played = 1
        stats = {k: v for k, v in s.items() if k != "t"}
        out["appearance"].append({"mid": mid, "pid": pid, "tid": side_t[side], "played": played, "started": started,
                                  "minutes": minutes if played else (0 if played == 0 else None), "position": position, "shirt": shirt,
                                  "rating": s.get("r") if s.get("r") is not None else rating,
                                  "goals": s["g"] if s.get("g") is not None else goals[fid], "assists": s["a"] if s.get("a") is not None else assists[fid],
                                  "yellow": yellow[fid], "red": red[fid], "stats": json.dumps(stats, sort_keys=True) if stats else None})

    for side in ("h", "a"):
        for p in ((rec.get("lineups") or {}).get(side) or {}).get("players") or []:
            if p[0] and p[0] not in in_lineup:
                in_lineup.add(p[0])
                appear(p[0], p[1], side, p[2], p[3], int(bool(p[4])), p[5])
    for e in events:                                   # a scorer or assister whose side has no lineup row for him
        if e[1] == "g":
            side = e[2] if e[6] != "own" else ("a" if e[2] == "h" else "h")
            for fid, nm in ((e[3], e[4]),) + (((e[5], None),) if e[6] != "own" and e[5] else ()):
                if fid and fid not in in_lineup:
                    in_lineup.add(fid)
                    appear(fid, nm, side)
    for seq, e in enumerate(events):
        mn, add = _minute(e[0])
        if e[1] == "g":
            tp, pid2, det = GOAL.get(e[6], "goal"), (ent("player", e[5], {"name": None}) if e[5] else None), (e[7] if len(e) > 7 else None)
        elif e[1] == "s":
            tp, pid2, det = "sub", (ent("player", e[5], {"name": e[6]}) if e[5] else None), None
        else:
            tp = {"y": "yellow", "r": "second_yellow" if e[6] == "YellowRed" else "red"}.get(e[1], "card")
            pid2, det = None, e[6]
        out["event"].append({"mid": mid, "seq": seq, "minute": mn, "added": add, "type": tp, "side": e[2], "tid": side_t.get(e[2]),
                             "pid": ent("player", e[3], {"name": e[4]}) if e[3] else None, "pid2": pid2, "detail": det})
    return out

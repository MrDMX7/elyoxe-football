"""ESPN's match records (graph/espn_fetch.py) for the seasons before FotMob's detail: the big five leagues 2001/02-2009/10,
the Champions League, the AFC Champions League 2006-2009, the Africa Cup of Nations 2004-2010, the 2007 Asian Cup. The graph's
copy of a game (schochastics', engsoccerdata's, martj42's) takes ESPN's squads, goals, cards, substitutions, referee, ground
and attendance; a game no source held is ESPN's own. FotMob's game keeps its own and takes only what it lacks.

  * a club or a national team: the one the competition's games of the same day and score vote for, 3 votes and three times
    the next; else ESPN's own;
  * a man: FotMob's man who wore his shirt in a game both hold (2010/11 is fetched for this), twice and three times any other,
    or once with a name that agrees; else ESPN's own (his Latin name; the people pass may join him later);
  * goals that do not add up to the score are left out, the rest kept.
research/open-football-datasets-2026-11-22.md §2.1."""
import gzip, json, os, re
from collections import Counter, defaultdict
from graph.link import MatchIndex, edition_for
from graph.load.uaefa import agree
from graph.load.teams import squash

FILE = "espn.json.gz"
LEAGUE = {"eng.1": 47, "esp.1": 87, "ita.1": 55, "ger.1": 54, "fra.1": 53, "uefa.champions": 42, "afc.champions": 525,
          "caf.nations": 289, "afc.asian.cup": 290}


def clock(t):
    """«34'» -> (34, 0), «90'+3'» -> (90, 3)"""
    m = re.match(r"\s*(\d+)'?\s*(?:\+\s*(\d+))?", str(t or ""))
    return (int(m.group(1)), int(m.group(2) or 0)) if m else (None, 0)


def _shift(d, days):
    from datetime import date, timedelta
    try:
        return (date.fromisoformat(d[:10]) + timedelta(days=days)).isoformat()
    except ValueError:
        return d


def load(G, reg, S):
    f = os.path.join(S.db, FILE)
    if not os.path.exists(f):
        return {"skipped": "no espn.json.gz"}
    # a game with its squads only: the scoreboards also list squad-less games with made-up scores (2009/10: «Wolves 7-1 West Ham»)
    rows = [r for r in json.load(gzip.open(f, "rt", encoding="utf-8"))["matches"] if r.get("teams") and len(r["teams"]) == 2
            and any(ro.get("men") for ro in r.get("rosters") or [])]
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    n = Counter()
    fm_team = {t for (t,) in q("SELECT tifo_id FROM xref WHERE type='team' AND source='fotmob'")}
    cid = {lg: reg.get("competition", "fotmob", fid) for lg, fid in LEAGUE.items()}
    eds = {c: {e for (e,) in q("SELECT eid FROM edition WHERE cid=?", (c,))} for c in set(cid.values()) if c}
    comp_of = {e: c for c, es in eds.items() for e in es}
    marks = ",".join("?" * len(comp_of)) or "NULL"
    held = q(f"SELECT mid, eid, substr(date,1,10), home, away, hs, as_ FROM match WHERE eid IN ({marks}) AND date IS NOT NULL", tuple(comp_of))
    eid_of = {m: e for m, e, *_ in held}
    side = lambda r, s: next((t for t in r["teams"] if t.get("side") == s), {})
    score = lambda t: int(t["score"]) if str(t.get("score", "")).isdigit() else None
    day = lambda r: str(r.get("date") or "")[:10]

    # 1. clubs and national teams: the competition's games of the same day and score vote
    by_comp_day = defaultdict(list)
    for m, e, d, h, a, hs, as_ in held:
        if hs is not None:
            by_comp_day[(comp_of[e], d)].append((h, a, hs, as_))
    votes = defaultdict(Counter)
    for r in rows:
        c = cid.get(r["league"])
        h, a = side(r, "home"), side(r, "away")
        for dd in (day(r), _shift(day(r), -1), _shift(day(r), 1)):
            for gh, ga, ghs, gas in by_comp_day.get((c, dd), ()):
                if (ghs, gas) == (score(h), score(a)):
                    votes[h.get("id")][gh] += 1 + (gh in fm_team)
                    votes[a.get("id")][ga] += 1 + (ga in fm_team)
    team, names = {}, {}
    for r in rows:
        for t in r["teams"]:
            names[t.get("id")] = t.get("name")
    for k, c in votes.items():
        top = c.most_common(2)
        # three times the next, or FotMob's club ahead of another source's record (one club held twice: Porto 2001-09)
        if top and top[0][1] >= 3 and (len(top) == 1 or top[0][1] >= 3 * top[1][1] or (top[0][0] in fm_team and top[1][0] not in fm_team)):
            team[k] = reg.link("team", "espn", str(k), top[0][0]) or top[0][0]
            G.xref("team", team[k], "espn", str(k), "date+score-votes")
            n["teams_voted"] += 1
    # no copy to vote by (the Champions League before 2010/11 is ESPN's alone): FotMob's club of exactly that name, if one
    fm_names = defaultdict(list)
    for t, nm in q("SELECT t.tid, t.name FROM team t JOIN xref x ON x.type='team' AND x.source='fotmob' AND x.tifo_id=t.tid"):
        fm_names[squash(nm)].append(t)
    for k, nm in names.items():
        hit = fm_names.get(squash(nm)) if k not in team and nm else None
        if hit and len(set(hit)) == 1:
            team[k] = reg.link("team", "espn", str(k), hit[0]) or hit[0]
            G.xref("team", team[k], "espn", str(k), "name")
            n["teams_named"] += 1
    for k, nm in names.items():
        if k not in team:
            team[k] = reg.get("team", "espn", str(k)) or reg.mint("team", "espn", str(k))
            G.put("team", {"tid": team[k], "name": nm}, "espn")
            G.xref("team", team[k], "espn", str(k), "espn-native")
            n["teams_own"] += 1
    # 2. the games: the competition's copy of each (once), else ESPN's own
    idx, claimed, game, theirs = MatchIndex(G), set(), {}, {}
    for r in rows:
        c = cid.get(r["league"])
        h, a = side(r, "home"), side(r, "away")
        th, ta, hit = team[h.get("id")], team[a.get("id")], None
        for mid, swapped in idx.candidates(day(r), th, ta):
            if swapped or mid in claimed or eid_of.get(mid) not in eds.get(c, ()):
                continue
            row = q("SELECT hs, as_, src FROM match WHERE mid=?", (mid,))[0]
            if (row[0], row[1]) == (score(h), score(a)):
                hit = (mid, row[2])
                break
        if hit:
            claimed.add(hit[0])
        game[r["id"]], theirs[r["id"]] = (hit or (None, None))
    # 3. men: FotMob's man who wore the same shirt in a game both hold
    pv = defaultdict(Counter)
    for r in rows:
        mid = game[r["id"]]
        if not mid or theirs[r["id"]] != "fotmob":
            continue
        fm = defaultdict(dict)
        for pid, tid, shirt, nm in q("SELECT a.pid, a.tid, a.shirt, p.name FROM appearance a JOIN player p ON p.pid=a.pid WHERE a.mid=?", (mid,)):
            fm[tid][str(shirt or "")] = (pid, nm)
        for ro in r.get("rosters") or []:
            tid = team.get(ro.get("team"))
            for p in ro.get("men") or []:
                got = fm[tid].get(str(p.get("no") or "")) if p.get("no") else None
                if got:
                    pv[p["id"]][got[0]] += 2 if agree(p.get("name"), got[1]) else 1
    linked = {}
    for k, c in pv.items():
        top = c.most_common(2)
        if top[0][1] >= 2 and (len(top) == 1 or top[0][1] >= 3 * top[1][1]):
            got = reg.link("player", "espn", str(k), top[0][0])
            if got is not None:
                linked[k] = got
                n["men_linked"] += 1

    def man(p):
        k = p.get("id")
        if not k:
            return None
        pid = linked.get(k) or reg.get("player", "espn", str(k)) or reg.mint("player", "espn", str(k))
        if not G.c.execute("SELECT 1 FROM player WHERE pid=?", (pid,)).fetchone():
            G.put("player", {"pid": pid, "name": p.get("name")}, "espn")
            G.xref("player", pid, "espn", str(k), "espn-native")
            n["men_own"] += 1
        return pid

    named = {}

    def named_row(kind, name):
        if not name:
            return None
        if (kind, name) not in named:
            t, k = ("referee", "rid") if kind == "referee" else ("stadium", "sid")
            hit = q(f"SELECT {k} FROM {t} WHERE lower(name)=lower(?)", (name,))
            i = hit[0][0] if len(hit) == 1 else (reg.get(kind, "espn", name) or reg.mint(kind, "espn", name))
            if not hit:
                G.put(t, {k: i, "name": name}, "espn")
            named[(kind, name)] = i
        return named[(kind, name)]

    # 4. each game's record
    for r in rows:
        c = cid.get(r["league"])
        h, a = side(r, "home"), side(r, "away")
        th, ta = team[h.get("id")], team[a.get("id")]
        mid, src = game[r["id"]], theirs[r["id"]]
        fill = {"sid": named_row("stadium", r.get("venue")), "rid": named_row("referee", r.get("referee")),
                "attendance": int(r["attendance"]) if str(r.get("attendance") or "").isdigit() and int(r["attendance"]) > 0 else None}
        if mid is None:
            mid = reg.get("match", "espn", str(r["id"])) or reg.mint("match", "espn", str(r["id"]))
            G.put("match", {"mid": mid, "eid": edition_for(G, reg, "espn", f"{LEAGUE[r['league']]}|{r['season']}", c, r["season"]),
                            "date": str(r.get("date") or "")[:16] + ":00Z" if "T" in str(r.get("date")) else day(r), "home": th, "away": ta,
                            "hs": score(h), "as_": score(a), "status": "finished", **fill}, "espn")
            G.xref("match", mid, "espn", str(r["id"]), "espn-native")
            idx.add(mid, day(r), th, ta)
            n["games_own"] += 1
        else:
            G.xref("match", mid, "espn", str(r["id"]), "date+teams")
            for k, v in fill.items():
                if v is not None:
                    G.c.execute(f"UPDATE match SET {k}=? WHERE mid=? AND {k} IS NULL", (v, mid))
            if src != "fotmob" and "T" in str(r.get("date")):
                G.c.execute("UPDATE match SET date=? WHERE mid=? AND length(date)=10", (str(r["date"])[:16] + ":00Z", mid))
            n["games_joined"] += 1
        _detail(G, r, mid, th, ta, man, team, n)
    return dict(n)


def _detail(G, r, mid, th, ta, man, team, n):
    """squads and events where the game holds none yet"""
    has_lu = G.c.execute("SELECT 1 FROM appearance WHERE mid=? LIMIT 1", (mid,)).fetchone()
    has_ev = G.c.execute("SELECT 1 FROM event WHERE mid=? LIMIT 1", (mid,)).fetchone()
    s_of = {"home": ("h", th), "away": ("a", ta)}
    apps, ev, subs = [], [], defaultdict(lambda: {"in": [], "out": []})
    any_start = any(p.get("start") for ro in r.get("rosters") or [] for p in ro.get("men") or [])
    for ro in r.get("rosters") or []:
        s, tid = s_of.get(ro.get("side"), (None, None))
        if not s:
            continue
        for p in ro.get("men") or []:
            pid = man(p)
            if pid is None:
                continue
            played = bool(p.get("start") or p.get("in") or p.get("plays"))
            apps.append({"mid": mid, "pid": pid, "tid": tid, "played": 1 if played or not any_start else 0,
                         "started": (1 if p.get("start") else 0) if any_start else None, "shirt": p.get("no"),
                         "goals": 0, "yellow": 0, "red": 0, "assists": 0})
            for x in p.get("plays") or []:
                mi, ad = clock(x.get("t"))
                if x.get("scoringPlay"):
                    if x.get("ownGoal"):
                        ev.append([mi, ad, "own_goal", "a" if s == "h" else "h", tid, pid, None])
                    else:
                        ev.append([mi, ad, "penalty_goal" if x.get("penaltyKick") else "goal", s, tid, pid, None])
                if x.get("yellowCard"):
                    ev.append([mi, ad, "yellow", s, tid, pid, None])
                if x.get("redCard"):
                    ev.append([mi, ad, "red", s, tid, pid, None])
                if x.get("substitution"):
                    subs[(s, mi, ad)]["in" if p.get("in") else "out"].append(pid)
    for (s, mi, ad), v in subs.items():
        for i in range(max(len(v["in"]), len(v["out"]))):
            ev.append([mi, ad, "sub", s, th if s == "h" else ta, v["in"][i] if i < len(v["in"]) else None, v["out"][i] if i < len(v["out"]) else None])
    hs, as_ = G.c.execute("SELECT hs, as_ FROM match WHERE mid=?", (mid,)).fetchone()
    goals = Counter(e[3] for e in ev if e[2] in ("goal", "penalty_goal", "own_goal"))
    if (goals["h"], goals["a"]) != (hs, as_):
        if goals:
            n["goals_not_adding_up"] += 1
        ev = [e for e in ev if e[2] not in ("goal", "penalty_goal", "own_goal")]
    booked = set()
    for e in sorted(ev, key=lambda e: (e[0] or 0, e[1])):
        if e[2] == "yellow":
            booked.add(e[5])
        elif e[2] == "red" and e[5] in booked:
            e[2] = "second_yellow"
    by = {a["pid"]: a for a in apps}
    for e in ev:
        a = by.get(e[5])
        if a and e[2] in ("goal", "penalty_goal"):
            a["goals"] += 1
        elif a and e[2] == "yellow":
            a["yellow"] += 1
        elif a and e[2] in ("red", "second_yellow"):
            a["red"] += 1
    if not has_lu and apps:
        G.many("appearance", apps, "espn")
        n["line_ups"] += 1
    if not has_ev and ev:
        ev.sort(key=lambda e: (e[0] if e[0] is not None else 999, e[1]))
        G.many("event", [{"mid": mid, "seq": i, "minute": e[0], "added": e[1], "type": e[2], "side": e[3], "tid": e[4], "pid": e[5], "pid2": e[6]}
                         for i, e in enumerate(ev)], "espn")
        n["events"] += len(ev)

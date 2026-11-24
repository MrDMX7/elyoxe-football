"""UEFA's own match records (graph/uefa_fetch.py) for the seasons before FotMob's detail: the European Cup and Champions
League from 1955, the UEFA Cup, the Cup Winners' Cup, the Intertoto Cup, the Super Cup, the Intercontinental Cup, the Fairs
Cup and the EURO with its qualifiers. The graph's copy of a game (schochastics', martj42's, ESPN's) takes UEFA's squads,
goals, cards, substitutions, coaches, referee, ground and attendance; a game no source held is UEFA's own. A game that has
squads or events keeps them.

  * a club or a national team: the one the competition's games of the same day and score vote for (3 votes and three times
    the next; fewer when the name agrees too); else FotMob's club of exactly that name; else UEFA's own;
  * a game: the same two teams on the day ±1 with the same score in that competition, home and away either way round; a
    game of ours goes to the edition the season's other games sit in, else to the season its dates span;
  * a man: the one who wore his shirt in a game both hold, twice and three times any other; else the one man born on his
    day whose name shares a word with his; else UEFA's own, with his birthday, country, line and height;
  * goals that do not add up to the score are left out, the rest kept; a shoot-out's kicks are no goals.
research/tifo-sources-2026-11-24.md."""
import gzip, json, os
from datetime import date
from collections import Counter, defaultdict
from graph.countries import canon
from graph.link import MatchIndex, edition_for, _days
from graph.load.uaefa import agree
from graph.load.teams import alike, squash
from graph.load.wikidata_facts import fold, house

FILE = "uefa.json.gz"
# our label -> the registry keys of the competitions its games may sit in, the first for a game of our own
COMP = {"champions": [("fotmob", "42")], "uefa-cup": [("fotmob", "73")], "super-cup": [("fotmob", "74")],
        "cup-winners": [("sch", "cup-winners-cup")], "intertoto": [("sch", "UEFA ITC")], "intercontinental": [("sch", "intercontinental-cup-old")],
        "euro": [("fotmob", "50"), ("martj42", "UEFA Euro qualification")], "fairs-cup": [("uefa", "fairs-cup")]}
FAIRS = {"name": "Inter-Cities Fairs Cup", "name_ar": "كأس المعارض الأوروبية", "kind": "cup", "scope": "europe"}
ROUND = {"FINAL": "final", "SEMIFINAL": "1/2", "QUARTER_FINALS": "1/4", "ROUND_OF_16": "1/8", "ROUND_OF_32": "1/16", "THIRD_PLACE_PLAY_OFF": "3rd place"}
LINE = {"GOALKEEPER": "Goalkeeper", "DEFENDER": "Defender", "MIDFIELDER": "Midfielder", "FORWARD": "Forward"}
PLAY = ("FIRST_HALF", "SECOND_HALF", "EXTRA_TIME_FIRST_HALF", "EXTRA_TIME_SECOND_HALF")
SCORED = ("goal", "penalty_goal", "own_goal")
THIN = ("martj42",)        # its squads are the scorers alone
GOAL = {None: "goal", "PENALTY": "penalty_goal", "OWN": "own_goal", "SCORED": "goal"}
CARD = {"YELLOW_CARD": "yellow", "RED_CARD": "red", "RED_YELLOW_CARD": "second_yellow"}


LOOSE = {"Friendlies", "Club Friendlies", "Other Matches"}       # where a source leaves a game it cannot place


def score(r, key="total"):
    s = (r.get("score") or {}).get(key) or {}
    return (s.get("home"), s.get("away")) if s.get("home") is not None and s.get("away") is not None else None


def real(r):
    """the scores a copy of the game may carry: after extra time, and after ninety minutes"""
    return {s for s in (score(r), score(r, "regular")) if s}


def scores(r):
    """real(r), and what a source that counted the shoot-out wrote: the kicks alone (Boca Juniors 3-1 Milan, 2003), or
    on top of the goals (Porto 8-7 Once Caldas, 2004). A game joined on one of those takes the organiser's score"""
    out, p = real(r), score(r, "penalty")
    return out | {p} | {(s[0] + p[0], s[1] + p[1]) for s in out} if p else out


def near(a, b, days=21):
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days) <= days


def season_of(dates, national=False):
    """the season a group of games (one seasonYear of one competition) spans: «1960/1961», the Fairs Cup's «1955/1958»; a
    cup played inside one year belongs to the season that year starts («2008/2009» for the summer of 2008) unless it was
    over by June (the Super Cup of January 1973 is 1972/1973's)"""
    ys = sorted(d[:4] for d in dates)
    y0, y1 = int(ys[0]), int(ys[-1])
    if national:
        return str(y1)
    if y0 != y1:
        return f"{y0}/{y1}"
    return f"{y0 - 1}/{y0}" if max(d[5:7] for d in dates) <= "06" else f"{y0}/{y0 + 1}"


def load(G, reg, S):
    f = os.path.join(S.db, FILE)
    if not os.path.exists(f):
        return {"skipped": "no uefa.json.gz"}
    ok = lambda t: t.get("id") and t.get("name") and "WOMEN" not in str(t.get("kind") or "") and "YOUTH" not in str(t.get("kind") or "")
    rows = [r for r in json.load(gzip.open(f, "rt", encoding="utf-8"))["matches"] if r.get("comp") in COMP and r.get("status") == "FINISHED"
            and r.get("date") and score(r) and ok(r.get("home") or {}) and ok(r.get("away") or {})]
    if reg.get("competition", "uefa", "fairs-cup") is None and any(r["comp"] == "fairs-cup" for r in rows):
        c = reg.mint("competition", "uefa", "fairs-cup")
        G.put("competition", {"cid": c, **FAIRS}, "uefa")
        G.xref("competition", c, "uefa", "fairs-cup", "uefa-native")
    return apply(G, reg, rows, "uefa", COMP, group, own)


def group(r):
    """the games of one season of one competition; the EURO's qualifiers apart from its finals"""
    return (r["comp"], r.get("year"), r.get("phase") == "QUALIFYING" if r["comp"] == "euro" else None)


def own(r, g, dates, cids):
    """(competition, edition key, season, whatever the season's other games sit in) for a game no source held"""
    if r["comp"] == "euro":
        y = r["date"][:4] if g[2] else str(r.get("year"))
        return cids["euro"][-1 if g[2] and len(cids["euro"]) > 1 else 0], f"euro|{'q' if g[2] else 't'}|{y}", y, True
    s = season_of(dates)
    return cids[r["comp"]][0], f"{r['comp']}|{s}", s, False


def apply(G, reg, rows, src, comp, group, own, thin=THIN):
    """An organiser's records (UEFA's, FIFA's) onto the graph. `comp`: label -> registry keys of the competitions its games may
    sit in; `group(r)`: the games of one season; `own(r, g, dates, cids)`: where a game no source held goes; `thin`: sources
    whose squads are only the scorers, which a full squad replaces."""
    rows = sorted(rows, key=lambda r: (r["date"], str(r["id"])))
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    n = Counter()
    cids = {lb: [c for c in (reg.get("competition", s, k) for s, k in keys) if c] for lb, keys in comp.items()}
    eds = {c: {e for (e,) in q("SELECT eid FROM edition WHERE cid=?", (c,))} for cs in cids.values() for c in cs}
    comp_of = {e: c for c, es in eds.items() for e in es}
    marks = ",".join("?" * len(comp_of)) or "NULL"
    held = q(f"SELECT mid, eid, substr(date,1,10), home, away, hs, as_, src FROM match WHERE eid IN ({marks}) AND date IS NOT NULL", tuple(comp_of))
    of_mid = {m: (e, h, a, hs, as_, by) for m, e, d, h, a, hs, as_, by in held}
    fm_team = {t for (t,) in q("SELECT tifo_id FROM xref WHERE type='team' AND source='fotmob'")}
    day = lambda r: r["date"][:10]

    # 1. clubs and national teams: the competition's games of the same day and score vote
    by_day = defaultdict(list)
    for m, e, d, h, a, hs, as_, by in held:
        if hs is not None:
            by_day[(comp_of[e], d)].append((h, a, hs, as_))
    votes, names = defaultdict(Counter), {}
    for r in rows:
        h, a, ss = r["home"], r["away"], scores(r)
        names[h["id"]], names[a["id"]] = h, a
        for c in cids[r["comp"]]:
            for dd in _days(day(r)):
                for gh, ga, ghs, gas in by_day.get((c, dd), ()):
                    if (ghs, gas) in ss:
                        votes[h["id"]][gh] += 1 + (gh in fm_team)
                        votes[a["id"]][ga] += 1 + (ga in fm_team)
                    elif h.get("national") and (gas, ghs) in ss:       # a neutral ground, filed the other way round
                        votes[h["id"]][ga] += 1 + (ga in fm_team)
                        votes[a["id"]][gh] += 1 + (gh in fm_team)
    name_of = dict(q("SELECT tid, name FROM team"))
    kind_of = dict(q("SELECT tid, kind FROM team"))
    team = {}
    for k, c in votes.items():
        top = c.most_common(2)
        first, second = top[0], (top[1][1] if len(top) > 1 else 0)
        same = alike(names[k]["name"], name_of.get(first[0])) or alike(names[k].get("official"), name_of.get(first[0]))
        if bool(names[k].get("national")) != (kind_of.get(first[0]) == "national") and kind_of.get(first[0]):
            continue
        if (first[1] >= 3 and (first[1] >= 3 * second or (first[0] in fm_team and top[1][0] not in fm_team))) or (same and first[1] > second):
            team[k] = reg.link("team", src, str(k), first[0]) or first[0]
            G.xref("team", team[k], src, str(k), "date+score-votes")
            n["teams_voted"] += 1
    # a team no day voted for (the sources' dates differ by more than a day): the opponent of a team already known, at home
    # or away as UEFA has it, with that score within three weeks
    at, pair = defaultdict(list), defaultdict(list)
    for m, e, d, h, a, hs, as_, by in held:
        if hs is not None:
            at[(comp_of[e], h, "h")].append((d, a, hs, as_))
            at[(comp_of[e], a, "a")].append((d, h, hs, as_))
            pair[(comp_of[e], h, a)].append((d, m, hs, as_))
    def opponents():
        late, sure = defaultdict(Counter), set()                    # sure: the known team's game of that very day
        for r in rows:
            h, a = r["home"]["id"], r["away"]["id"]
            if (h in team) == (a in team):
                continue
            known, k, sd = (team[h], a, "h") if h in team else (team[a], h, "a")
            ss = scores(r)
            for c in cids[r["comp"]]:
                for d, opp, hs, as_ in at.get((c, known, sd), ()):
                    same = near(d, day(r), 1) and ((hs, as_) in ss or bool(r.get("unsure")))
                    if same or ((hs, as_) in ss and near(d, day(r))):
                        late[k][opp] += 1
                    if same:
                        sure.add((k, opp))
                for d, opp, hs, as_ in at.get((c, known, "a" if sd == "h" else "h"), ()):      # a neutral ground, filed the other way round
                    if d == day(r) and ((as_, hs) in ss or r.get("unsure")):
                        late[k][opp] += 1
                        sure.add((k, opp))
        for k, c in late.items():
            top = c.most_common(2)
            first, second = top[0], (top[1][1] if len(top) > 1 else 0)
            same = alike(names[k]["name"], name_of.get(first[0])) or alike(names[k].get("official"), name_of.get(first[0]))
            if bool(names[k].get("national")) != (kind_of.get(first[0]) == "national") and kind_of.get(first[0]):
                continue
            lone = not second and (k, first[0]) in sure and first[0] not in set(team.values())
            if (first[1] >= 2 and first[1] >= 3 * second) or (same and first[1] > second) or lone:
                team[k] = reg.link("team", src, str(k), first[0]) or first[0]
                G.xref("team", team[k], src, str(k), "opponent+score-votes")
                n["teams_voted_late"] += 1

    opponents()
    fm_names = defaultdict(set)
    for (c, h, sd) in at:                                       # a club of the competition's own games comes before FotMob's of that name
        fm_names[("comp", squash(name_of.get(h)), kind_of.get(h) == "national")].add(h)
    for t, nm, kd in q("SELECT t.tid, t.name, t.kind FROM team t JOIN xref x ON x.type='team' AND x.source='fotmob' AND x.tifo_id=t.tid"):
        fm_names[(squash(nm), kd == "national")].add(t)
    lands = house(G, "team", "country")
    for k, t in names.items():
        if k in team:
            continue
        if reg.linked("team", src, str(k)):                      # tied by an earlier build, or by the caller
            team[k] = reg.get("team", src, str(k))
            G.xref("team", team[k], src, str(k), "registry")
            n["teams_known"] += 1
            continue
        hit = fm_names.get(("comp", squash(t["name"]), bool(t.get("national")))) or ()
        hit = hit if len(hit) == 1 else fm_names.get((squash(t["name"]), bool(t.get("national")))) or ()
        if len(hit) == 1:
            team[k] = reg.link("team", src, str(k), next(iter(hit))) or next(iter(hit))
            G.xref("team", team[k], src, str(k), "name")
            n["teams_named"] += 1
    opponents()                                                 # the opponent of a team its name has just found
    for k, t in names.items():
        if k not in team:
            team[k] = reg.get("team", src, str(k)) or reg.mint("team", src, str(k))
            G.xref("team", team[k], src, str(k), f"{src}-native")
            n["teams_own"] += 1
    for k, t in names.items():
        _fill(G, src, "team", "tid", team[k], {"name": t["name"], "name_ar": t.get("ar"), "kind": "national" if t.get("national") else "club",
                                          "country": lands.get(canon(t.get("country")))})

    # 2. the games: the competition's copy of each (once), else UEFA's own, in the edition its season's games sit in
    idx, claimed, game, flip = MatchIndex(G), set(), {}, {}
    redate, rescore = {}, set()
    for r in rows:
        th, ta, ss = team[r["home"]["id"]], team[r["away"]["id"]], scores(r)
        for mid, swapped in idx.candidates(day(r), th, ta):
            if mid in claimed or mid not in of_mid or comp_of[of_mid[mid][0]] not in cids[r["comp"]]:
                continue
            hs, as_ = of_mid[mid][3], of_mid[mid][4]
            if ((as_, hs) if swapped else (hs, as_)) in ss or hs is None:
                claimed.add(mid)
                game[r["id"]], flip[r["id"]] = mid, swapped
                if hs is not None and ((as_, hs) if swapped else (hs, as_)) not in real(r):
                    rescore.add(r["id"])
                break
    # the sources disagree: the two's one game of that day whatever its score (the organiser's score is the better one), then
    # their one game of that score within six weeks (the organiser's date)
    for loose in (lambda d, sc, r: abs((date.fromisoformat(d) - date.fromisoformat(day(r))).days) <= 1, lambda d, sc, r: sc in scores(r) and near(d, day(r), 45)):
        for r in rows:
            if r["id"] in game:
                continue
            th, ta = team[r["home"]["id"]], team[r["away"]["id"]]
            hit = [(m, d) for c in cids[r["comp"]] for d, m, hs, as_ in pair.get((c, th, ta), ()) if m not in claimed and loose(d, (hs, as_), r)]
            if len(hit) == 1:
                claimed.add(hit[0][0])
                game[r["id"]], flip[r["id"]] = hit[0][0], False
                if (of_mid[hit[0][0]][3], of_mid[hit[0][0]][4]) not in real(r) and not r.get("unsure"):
                    rescore.add(r["id"])
                if hit[0][1] != day(r):
                    redate[r["id"]] = day(r)
    # one side is another team in the graph's copy («Serbia and Montenegro» of 2006 where the organiser says Serbia): the
    # other side's one game of that day and score in the competition, which keeps its teams
    on_day, stand = defaultdict(list), {}
    for m, e, d, h, a, hs, as_, by in held:
        on_day[(comp_of[e], d)].append((m, h, a, hs, as_))
    for r in rows:
        if r["id"] in game:
            continue
        th, ta, ss, free = team[r["home"]["id"]], team[r["away"]["id"]], scores(r), bool(r.get("unsure"))
        hit = []
        for c in cids[r["comp"]]:
            for dd in _days(day(r)):
                for m, h, a, hs, as_ in on_day.get((c, dd), ()):
                    if m in claimed:
                        continue
                    if (h == th) != (a == ta) and ((hs, as_) in ss or free or hs is None):
                        hit.append((m, h, a, False))
                    elif (h == ta) != (a == th) and ((as_, hs) in ss or free or hs is None):
                        hit.append((m, a, h, True))
        if len(hit) == 1:
            m, h, a, swapped = hit[0]
            claimed.add(m)
            game[r["id"]], flip[r["id"]] = m, swapped
            stand[r["id"]] = {**team, r["home"]["id"]: h, r["away"]["id"]: a}
            n["games_joined_by_one_side"] += 1
    # the graph files the game under another competition (a continental championship that was the qualifier too, a final a
    # source left among its friendlies): the two's one game of that day and score, wherever it sits. One page a match
    moved = {}
    for r in rows:
        if r["id"] in game:
            continue
        th, ta, ss, hit = team[r["home"]["id"]], team[r["away"]["id"]], scores(r), []
        for mid, swapped in idx.candidates(day(r), th, ta):
            if mid in claimed:
                continue
            row = G.c.execute("SELECT m.eid, m.home, m.away, m.hs, m.as_, m.src, c.name FROM match m JOIN edition e ON e.eid=m.eid "
                              "JOIN competition c ON c.cid=e.cid WHERE m.mid=?", (mid,)).fetchone()
            if row and row[3] is not None and ((row[4], row[3]) if swapped else (row[3], row[4])) in ss and not r.get("unsure"):
                hit.append((mid, swapped, row))
        if len(hit) == 1:
            mid, swapped, row = hit[0]
            claimed.add(mid)
            game[r["id"]], flip[r["id"]], of_mid[mid] = mid, swapped, row[:6]
            if ((row[4], row[3]) if swapped else (row[3], row[4])) not in real(r):
                rescore.add(r["id"])
            moved[r["id"]] = row[6] in LOOSE
            n["games_joined_elsewhere"] += 1
    tm = lambda r: stand.get(r["id"]) or team
    sits, dates = defaultdict(Counter), defaultdict(list)
    for r in rows:
        dates[group(r)].append(day(r))
        if r["id"] in game and r["id"] not in moved:
            sits[group(r)][of_mid[game[r["id"]]][0]] += 1

    def edition(r):
        g = group(r)
        top = sits[g].most_common(1)
        c, key, season, fixed = own(r, g, dates[g], cids)
        if not fixed and top and top[0][1] * 2 > sum(sits[g].values()):
            return top[0][0]
        return edition_for(G, reg, src, key, c, season)

    # 3. men: the one who wore the same shirt in a game both hold, else the one man born that day whose name agrees
    pv, seen = defaultdict(Counter), {}
    for r in rows:
        for sq in r.get("lineups") or []:
            for p in sq.get("men") or []:
                if p.get("id") and p.get("sex") in (None, "MALE"):
                    seen.setdefault(p["id"], p)
        mid = game.get(r["id"])
        if not mid or not r.get("lineups"):
            continue
        ours, there = defaultdict(dict), defaultdict(list)
        for pid, tid, shirt, nm, born in q("SELECT a.pid, a.tid, a.shirt, p.name, p.born FROM appearance a JOIN player p ON p.pid=a.pid WHERE a.mid=?", (mid,)):
            if shirt:
                ours[tid][str(shirt)] = (pid, nm, born)
            there[tid].append((pid, nm, born))
        apart = lambda p, b: bool(b and p.get("born") and b[:10] != p["born"])
        for sq in r["lineups"]:
            tid = tm(r).get(sq.get("team"))
            for p in sq.get("men") or []:
                got = ours[tid].get(str(p.get("no") or "")) if p.get("no") else None
                if got and not apart(p, got[2]):
                    pv[p["id"]][got[0]] += 2 if agree(p.get("name"), got[1]) else 1
                    continue
                # no shirt on our copy (a scorer of martj42's): the side's one man of that name, who is that name's one man
                hit = [x for x in there[tid] if agree(p.get("name"), x[1]) and not apart(p, x[2])]
                if len(hit) == 1 and sum(1 for o in sq["men"] if agree(o.get("name"), hit[0][1])) == 1:
                    pv[p["id"]][hit[0][0]] += 2
    linked, taken = {}, {}

    def tie(k, pid, how):
        if taken.setdefault(pid, k) != k:
            return
        got = reg.link("player", src, str(k), pid)
        if got is not None:
            linked[k] = got
            G.xref("player", got, src, str(k), how)
            n["men_" + how] += 1

    for k in sorted(pv, key=str):
        top = pv[k].most_common(2)
        if top[0][1] >= 2 and (len(top) == 1 or top[0][1] >= 3 * top[1][1]):
            tie(k, top[0][0], "shirt")
    born = defaultdict(list)
    for pid, nm, b in q("SELECT pid, name, born FROM player WHERE length(born)>=10"):
        born[b[:10]].append((pid, nm))
    for k in sorted(seen, key=str):
        p = seen[k]
        if k in linked or reg.get("player", src, str(k)) or not p.get("born"):
            continue
        hit = [pid for pid, nm in born.get(p["born"], ()) if agree(p.get("name"), nm)]
        if len(hit) == 1:
            tie(k, hit[0], "born-name")
    codes = {v for (v,) in q("SELECT DISTINCT nationality FROM player WHERE nationality IS NOT NULL")}
    men = {}

    def man(p):
        k = p.get("id")
        if not k or p.get("sex") not in (None, "MALE"):
            return None
        if k not in men:
            pid = linked.get(k) or reg.get("player", src, str(k)) or reg.mint("player", src, str(k))
            p = {**p, **{f: v for f, v in (seen.get(k) or {}).items() if v}}
            if k not in linked:
                G.xref("player", pid, src, str(k), f"{src}-native")
                n["men_own"] += 1
            h = p.get("height")
            _fill(G, src, "player", "pid", pid, {"name": p.get("name"), "name_ar": p.get("ar"), "born": p.get("born"), "position": LINE.get(p.get("pos")),
                                            "nationality": p.get("country") if p.get("country") in codes else None,
                                            "height": int(h) if isinstance(h, (int, float)) and 150 <= h <= 215 else None})
            men[k] = pid
        return men[k]

    by_name = {}

    def named(kind, key, p, more):
        """a coach, a referee or a ground: the one of that name the graph holds, else UEFA's own"""
        if not p.get("id") or not p.get("name"):
            return None
        if (kind, p["id"]) not in by_name:
            if kind not in by_name:
                by_name[kind] = defaultdict(list)
                for i, nm in q(f"SELECT {key}, name FROM {kind}"):
                    by_name[kind][fold(nm)].append(i)
            i = reg.get(kind, src, str(p["id"]))
            hit = by_name[kind].get(fold(p["name"])) or []
            if i is None and len(hit) == 1 and reg.alias(kind, src, str(p["id"]), hit[0]):
                i = hit[0]
                G.xref(kind, i, src, str(p["id"]), "name")
            elif i is None:
                i = reg.mint(kind, src, str(p["id"]))
                G.xref(kind, i, src, str(p["id"]), f"{src}-native")
                by_name[kind][fold(p["name"])].append(i)
                n[kind + "_own"] += 1
            _fill(G, src, kind, key, i, {"name": p["name"], "name_ar": p.get("ar"), **more})
            by_name[(kind, p["id"])] = i
        return by_name[(kind, p["id"])]

    spell = {t: house(G, t, c) for t, c in (("stadium", "country"), ("coach", "nationality"), ("referee", "country"))}
    land = lambda t, code: spell[t].get(canon(code)) or lands.get(canon(code))

    # 4. each game's record
    for r in rows:
        th, ta = tm(r)[r["home"]["id"]], tm(r)[r["away"]["id"]]
        st, mid = r.get("stadium") or {}, game.get(r["id"])
        ref = next((x for x in r.get("referees") or [] if x.get("role") == "REFEREE"), {})
        pens = score(r, "penalty")
        won = str(r.get("won") or "")
        att = r.get("attendance")
        fill = {"sid": named("stadium", "sid", st, {"city": st.get("city"), "country": land("stadium", st.get("country")), "capacity": st.get("capacity"),
                                                    "lat": st.get("lat"), "lon": st.get("lon")}),
                "rid": named("referee", "rid", ref, {"country": land("referee", ref.get("country"))}),
                "attendance": att if isinstance(att, int) and att > 0 else None, "round": ROUND.get(r.get("round")),
                "et": 1 if pens or "EXTRA" in won or "PENALT" in won else None}
        if mid is None:
            mid = reg.get("match", src, str(r["id"])) or reg.mint("match", src, str(r["id"]))
            hs, as_ = score(r)
            G.put("match", {"mid": mid, "eid": edition(r), "date": day(r), "home": th, "away": ta, "hs": hs, "as_": as_, "status": "finished",
                            "pen_h": pens[0] if pens else None, "pen_a": pens[1] if pens else None, **fill}, src)
            G.xref("match", mid, src, str(r["id"]), f"{src}-native")
            idx.add(mid, day(r), th, ta)
            home, n["games_own"] = th, n["games_own"] + 1
        else:
            G.xref("match", mid, src, str(r["id"]), "date+teams")
            home = of_mid[mid][1]
            if r["id"] in redate and of_mid[mid][5] != "fotmob":          # the organiser's date
                G.c.execute("UPDATE match SET date=? WHERE mid=?", (redate[r["id"]], mid))
                n["dates_corrected"] += 1
            if moved.get(r["id"]):                                       # out of the friendlies, into its competition
                G.c.execute("UPDATE match SET eid=? WHERE mid=?", (edition(r), mid))
                n["games_moved"] += 1
            if r["id"] in rescore:
                sc = score(r)[::-1] if flip[r["id"]] else score(r)
                G.put("match", {"mid": mid, "hs": sc[0], "as_": sc[1]}, src)                  # a conflict on record; ESPN's and FotMob's scores stay
                n["scores_differ"] += 1
            if pens:
                fill["pen_h"], fill["pen_a"] = pens[::-1] if flip[r["id"]] else pens
            for k, v in fill.items():
                if v is not None:
                    G.c.execute(f"UPDATE match SET {k}=? WHERE mid=? AND {k} IS NULL", (v, mid))
            n["games_joined"] += 1
        _detail(G, r, mid, {th: "h" if th == home else "a", ta: "h" if ta == home else "a"}, tm(r), man, n, src, thin)
        for sq in r.get("lineups") or []:
            tid = tm(r).get(sq.get("team"))
            c = next((x for x in sq.get("coaches") or [] if x.get("role") == "COACH" and x.get("sex") in (None, "MALE")), None)
            kid = named("coach", "kid", c, {"born": c.get("born"), "nationality": land("coach", c.get("country"))}) if c and tid in (th, ta) else None
            if kid:
                n["coaches"] += G.c.execute("INSERT OR IGNORE INTO match_coach VALUES(?, ?, ?, ?)", (mid, "h" if tid == home else "a", kid, src)).rowcount
    return dict(n)


def _fill(G, src, table, key, i, row):
    """the row when the graph has none, else only the fields it has empty: UEFA's spelling of a name is no conflict"""
    cur = G.c.execute(f"SELECT * FROM {table} WHERE {key}=?", (i,)).fetchone()
    if cur is not None:
        cur = dict(zip(G.cols[table], cur))
        row = {k: v for k, v in row.items() if cur.get(k) in (None, "")}
    row = {k: v for k, v in row.items() if v not in (None, "")}
    if row:
        G.put(table, {key: i, **row}, src)


def _detail(G, r, mid, side, team, man, n, src, thin):
    """squads and events where the game holds none yet, or holds only the scorers of a thin source"""
    cur = G.c.execute("SELECT pid, src, goals FROM appearance WHERE mid=?", (mid,)).fetchall()
    old = [dict(zip(G.cols["event"], e)) for e in G.c.execute("SELECT * FROM event WHERE mid=?", (mid,)).fetchall()]
    stub_lu, stub_ev = bool(cur) and all(s in thin for _, s, _ in cur), bool(old) and all(e["src"] in thin for e in old)
    has_lu, has_ev = bool(cur) and not stub_lu, bool(old) and not stub_ev
    if has_lu and has_ev:
        return
    apps, of, ev = {}, {}, []
    for sq in r.get("lineups") or []:
        tid = team.get(sq.get("team"))
        if tid not in side:
            continue
        for p in sq.get("men") or []:
            pid = man(p)
            if pid is None or pid in apps:
                continue
            of[p["id"]] = tid
            apps[pid] = {"mid": mid, "pid": pid, "tid": tid, "played": 1 if p.get("start") else 0, "started": 1 if p.get("start") else 0,
                         "shirt": p.get("no"), "captain": 1 if p.get("captain") else None, "goals": 0, "assists": 0, "yellow": 0, "red": 0}

    def who(a):
        """(tid, pid) of an event's man: his squad says his team, the event only when he is in neither"""
        if not a or not a.get("id"):
            return None, None
        tid = of.get(a["id"]) or team.get(a.get("team"))
        return (tid, man(a)) if tid in side else (None, None)

    other = lambda s: "a" if s == "h" else "h"
    for e in r.get("events") or []:
        if e.get("phase") not in PLAY:
            continue
        tid, pid = who(e.get("a"))
        if pid is None:
            continue
        mi, ad, s = e.get("minute"), e.get("added") or 0, side[tid]
        if e.get("type") == "GOAL" and e.get("sub") in GOAL:
            kind = GOAL[e.get("sub")]
            ev.append([mi, ad, kind, other(s) if kind == "own_goal" else s, tid, pid, None])
        elif e.get("type") in CARD:
            ev.append([mi, ad, CARD[e["type"]], s, tid, pid, None])
        elif e.get("type") == "SUBSTITUTION":
            on = who(e.get("b"))[1]
            ev.append([mi, ad, "sub", s, tid, on, pid])
            if on in apps:
                apps[on]["played"] = 1
    if not any(e[2] in SCORED for e in ev):
        for g in r.get("scorers") or []:
            tid = of.get(g.get("id")) or team.get(g.get("team"))
            if g.get("phase") in PLAY and g.get("type") in GOAL and tid in side and g.get("id"):
                kind = GOAL[g["type"]]
                ev.append([g.get("minute"), g.get("added") or 0, kind, other(side[tid]) if kind == "own_goal" else side[tid], tid, man(g), None])
    hs, as_ = G.c.execute("SELECT hs, as_ FROM match WHERE mid=?", (mid,)).fetchone()
    goals = Counter(e[3] for e in ev if e[2] in SCORED)
    sums = (goals["h"], goals["a"]) == (hs, as_)
    if not sums:
        if goals:
            n["goals_not_adding_up"] += 1
        ev = [e for e in ev if e[2] not in SCORED]
    booked = set()
    for e in sorted(ev, key=lambda e: (e[0] or 0, e[1])):
        if e[2] == "yellow":
            booked.add(e[5])
        elif e[2] == "red" and e[5] in booked:
            e[2] = "second_yellow"
    for e in ev:
        a = apps.get(e[5])
        if a and e[2] in ("goal", "penalty_goal"):
            a["goals"] += 1
        elif a and e[2] == "yellow":
            a["yellow"] += 1
        elif a and e[2] in ("red", "second_yellow"):
            a["red"] += 1
    full = len(apps) >= 14
    if stub_lu and full:
        # the scorers give way to the squads; where the organiser's goals do not add up, the scorers keep theirs
        if sums:
            G.c.execute("DELETE FROM appearance WHERE mid=?", (mid,))
        else:
            for pid, _, g in cur:
                if pid in apps:
                    apps[pid]["goals"] = g or 0
                    G.c.execute("DELETE FROM appearance WHERE mid=? AND pid=?", (mid, pid))
        G.many("appearance", list(apps.values()), src)
        n["line_ups_over_scorers"] += 1
    elif not cur and apps:
        G.many("appearance", list(apps.values()), src)
        n["line_ups"] += 1
    rows = [{"mid": mid, "minute": e[0], "added": e[1], "type": e[2], "side": e[3], "tid": e[4], "pid": e[5], "pid2": e[6], "src": src} for e in ev]
    if has_ev:
        rows = []
    elif stub_ev and rows:
        # a thin source's goals: the organiser's stand in for them when they add up and the squads are his, else his cards
        # and substitutions go in beside them
        if sums and (full or not cur) and any(e["type"] in SCORED for e in rows):
            old = []
        else:
            rows = [e for e in rows if e["type"] not in SCORED]
        if rows:
            G.c.execute("DELETE FROM event WHERE mid=?", (mid,))
            rows = old + rows
    if rows:
        rows.sort(key=lambda e: (e["minute"] if e["minute"] is not None else 999, e["added"] or 0))
        by = defaultdict(list)
        for i, e in enumerate(rows):
            by[e["src"]].append({**e, "seq": i})
        for sc, es in by.items():
            G.many("event", es, sc)
        n["events"] += sum(1 for e in rows if e["src"] == src)

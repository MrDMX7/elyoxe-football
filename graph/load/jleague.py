"""The J.League's own record (graph/jleague_fetch.py: db/.cache/jleague.json.gz): J1 since 1993, J2 since 1999, J3 since 2014
and the League Cup since 1992. A game we hold already (schochastics' and Transfermarkt's J1) is linked and takes the
attendance and the shoot-out it lacks; the rest are new: before this source the second and third divisions and the cup had
no game at all (25 Nov 2026).

A club is the one its games vote for (the same date and score, any source; the first division's games first, the only
ones we hold); a club with no game of ours yet is FotMob's by its id, written here by hand, never by its name. Runs late,
after honours (whose list of winners makes the cup's seasons) and after the sources' copies of one game are joined.

schochastics dates three J1 seasons a year late: its «2001» is the games of 2000 over again, its «2002» those of 2001 and
half its «2003» those of 2002. The record says which: such a game is dropped when we hold it on its true day, else it moves
to that day and that season."""
import gzip, json, os
from collections import Counter
from datetime import date, timedelta
from graph.link import MatchIndex, edition_for, twin, vote_teams

FILE = "jleague.json.gz"
SRC = "jleague"
# frame -> (the source that names the competition, its id there, name, Arabic name, kind)
COMPS = {1: ("fotmob", 223, "J. League", "الدوري الياباني الممتاز", "league"), 2: ("s365", 148, "J2 League", "الدوري الياباني الدرجة الثانية", "league"),
         3: ("fotmob", 9136, "J. League 3", "الدوري الياباني الدرجة الثالثة", "league"), 11: ("fotmob", 224, "J. League Cup", "كأس الدوري الياباني", "cup")}
FOTMOB = {
    "Kashima Antlers": 4397, "Yokohama F. Marinos": 6581, "Gamba Osaka": 6582, "Nagoya Grampus": 8006, "Urawa Red Diamonds": 6244,
    "Sanfrecce Hiroshima": 6224, "Shimizu S-Pulse": 4426, "Kashiwa Reysol": 8699, "Vissel Kobe": 4688, "Júbilo Iwata": 8065,
    "Cerezo Osaka": 4692, "FC Tokyo": 4399, "Kawasaki Frontale": 6304, "Shonan Bellmare": 6180, "JEF United Chiba": 9756,
    "Tokyo Verdy": 6223, "Albirex Niigata": 4425, "Kyoto Sanga FC": 8542, "Avispa Fukuoka": 8270, "Vegalta Sendai": 162192,
    "Sagan Tosu": 162193, "Hokkaido Consadole Sapporo": 112688, "Omiya Ardija": 4398, "Oita Trinita": 4427, "Ventforet Kofu": 8539,
    "Yokohama FC": 49615, "Montedio Yamagata": 164720, "Machida Zelvia": 194011, "Tokushima Vortis": 162199,
    "Matsumoto Yamaga": 194022, "Fagiano Okayama": 164739, "V-Varen Nagasaki": 194016, "AC Nagano Parceiro": 243586,
    "Azul Claro Numazu": 614337, "Blaublitz Akita": 194015, "Cerezo Osaka U-23": 719025, "Ehime FC": 162198, "FC Gifu": 162197,
    "FC Imabari": 820969, "FC Osaka": 614335, "FC Tokyo U-23": 719026, "Fujieda MYFC": 305776, "Fukushima United": 408082,
    "Gainare Tottori": 194010, "Gamba Osaka U-23": 719027, "Giravanz Kitakyushu": 193858, "Iwaki FC": 860934,
    "Iwate Grulla Morioka": 521392, "Kagoshima United": 584867, "Kamatamare Sanuki": 243585, "Kataller Toyama": 164737,
    "Mito HollyHock": 162195, "Nara Club": 584746, "Renofa Yamaguchi": 614556, "Roasso Kumamoto": 162196, "SC Sagamihara": 422974,
    "Tegevajaro Miyazaki": 941024, "Thespa Gunma": 162194, "Tochigi City": 194029, "Tochigi SC": 164738,
    "Vanraure Hachinohe": 584880, "Zweigen Kanazawa": 194023, "YSCC Yokohama": 305775, "Kochi United": 860937}


def read(S):
    p = os.path.join(S.db, FILE)
    if not os.path.exists(p):
        return None
    with gzip.open(p, "rt", encoding="utf-8") as z:
        return json.load(z)


def _year_late(G, reg, cid, rows):
    """our J1 games the record has a year earlier (the same two clubs, the same score) and not on their own day: dropped
    or moved. A season with nine in ten of its games late is late whole (its play-off, which the record files apart)."""
    rec = {}
    for r in rows:
        if r[0] == 1:
            h, a = reg.get("team", SRC, r[4]), reg.get("team", SRC, r[5])
            rec[(r[3], h, a)] = (r[6], r[7])
            rec[(r[3], a, h)] = (r[7], r[6])

    def at(d, h, a):
        d0 = date.fromisoformat(d)
        return next(((str(d0 + timedelta(days=k)), rec[(str(d0 + timedelta(days=k)), h, a)]) for k in (0, -1, 1)
                     if (str(d0 + timedelta(days=k)), h, a) in rec), None)

    def back(d):
        return f"{int(d[:4]) - 1}{d[4:]}"

    ours = G.c.execute("""SELECT m.mid, m.eid, substr(m.date,1,10), m.home, m.away, m.hs, m.as_ FROM match m JOIN edition e ON e.eid=m.eid
                          WHERE e.cid=? AND m.date IS NOT NULL AND m.src<>?""", (cid, SRC)).fetchall()
    late, size, own = {}, Counter(eid for _, eid, *_ in ours), {}
    for mid, eid, d, h, a, hs, as_ in ours:                 # the record's game on our game's own day (a day off: the same score): one of ours each
        got = at(d, h, a)
        if got and (got[0] == d or got[1] == (hs, as_)):
            k, rank = (got[0], min(h, a), max(h, a)), (got[0] != d, got[1] != (hs, as_))
            if k not in own or rank < own[k][0]:
                own[k] = (rank, mid)
    on_day = {mid for _, mid in own.values()}
    for mid, eid, d, h, a, hs, as_ in ours:
        if d[5:] == "02-29" or mid in on_day:
            continue
        got = at(back(d), h, a)
        if got and got[1] == (hs, as_):
            late[mid] = got[0]
    n_late = Counter(eid for mid, eid, *_ in ours if mid in late)
    for mid, eid, d, h, a, hs, as_ in ours:                 # in a season with many late games, one the two sources score apart
        if mid not in late and mid not in on_day and d[5:] != "02-29" and n_late[eid] >= 0.3 * size[eid] and at(back(d), h, a):
            late[mid] = at(back(d), h, a)[0]
    n_late = Counter(eid for mid, eid, *_ in ours if mid in late)
    for mid, eid, d, *_ in ours:
        if mid not in late and d[5:] != "02-29" and n_late[eid] >= 0.9 * size[eid]:
            late[mid] = back(d)
    n = {"late_dropped": 0, "late_moved": 0}
    eids = {}
    for mid, eid, d, h, a, hs, as_ in ours:
        if mid not in late:
            continue
        true = late[mid]
        days = [str(date.fromisoformat(true) + timedelta(days=k)) for k in (0, -1, 1)]
        held = [m for (m,) in G.c.execute("""SELECT mid FROM match WHERE substr(date,1,10) IN (?,?,?) AND ((home=? AND away=?) OR (home=? AND away=?))""",
                                          (*days, h, a, a, h)) if m not in late]
        if held:
            for t in ("event", "appearance", "match_coach", "match_award"):
                G.c.execute(f"DELETE FROM {t} WHERE mid=?", (mid,))
            G.c.execute("DELETE FROM xref WHERE type='match' AND tifo_id=?", (mid,))
            n["late_dropped"] += G.c.execute("DELETE FROM match WHERE mid=?", (mid,)).rowcount
            continue
        y = true[:4]
        if y not in eids:
            eids[y] = edition_for(G, reg, SRC, f"1|{y}", cid, y)
        n["late_moved"] += G.c.execute("UPDATE match SET date=?, eid=? WHERE mid=?", (true, eids[y], mid)).rowcount
    return n


def load(G, reg, S):
    rows = read(S)
    if rows is None:
        return {"skipped": "no jleague pack"}
    n = {"rows": len(rows), "clubs_voted": 0, "clubs_fotmob": 0, "clubs_own": 0, "linked": 0, "new": 0, "attendance": 0, "shootout": 0}
    for part in ([r for r in rows if r[0] == 1], rows):
        voted = vote_teams(G, reg, SRC, [(r[3], r[4], r[5], r[6], r[7]) for r in part], any_src=True)
        for name, tid in voted.items():
            G.xref("team", tid, SRC, name, "date+score-votes")
        n["clubs_voted"] += len(voted)
    for name in sorted({x for r in rows for x in (r[4], r[5])}):
        if reg.get("team", SRC, name) is not None:
            continue
        ours = reg.get("team", "fotmob", FOTMOB[name]) if name in FOTMOB else None
        if ours is not None and G.c.execute("SELECT 1 FROM team WHERE tid=?", (ours,)).fetchone():
            got = reg.link("team", SRC, name, ours)
            if got is not None:
                G.xref("team", got, SRC, name, "fotmob-id-by-hand")
                n["clubs_fotmob"] += 1
    cids = {}
    for frame, (src, sid, name, ar, kind) in COMPS.items():
        cid = cids[frame] = reg.get("competition", src, sid) or reg.mint("competition", src, sid)
        if not G.c.execute("SELECT 1 FROM competition WHERE cid=?", (cid,)).fetchone():
            G.put("competition", {"cid": cid, "name": name, "name_ar": ar, "kind": kind, "scope": "national", "country": "JP"}, SRC)
        if not G.c.execute("SELECT 1 FROM xref WHERE type='competition' AND source=? AND source_id=?", (src, str(sid))).fetchone():
            G.xref("competition", cid, src, sid, "manual")
    n.update(_year_late(G, reg, cids[1], rows))
    seen, eids, idx, mine = set(), {}, MatchIndex(G), {}
    for frame, year, card, d, hn, an, hs, as_, ph, pa, rnd, att in rows:
        teams = []
        for nm in (hn, an):
            t = reg.get("team", SRC, nm) or reg.mint("team", SRC, nm)
            if t not in seen:
                seen.add(t)
                if not G.c.execute("SELECT 1 FROM team WHERE tid=?", (t,)).fetchone():
                    G.put("team", {"tid": t, "name": nm, "kind": "club", "country": "Japan"}, SRC)
                    G.xref("team", t, SRC, nm, f"{SRC}-native")
                    n["clubs_own"] += 1
            teams.append(t)
        h, a = teams
        mid = twin(G, idx, d, h, a, hs, as_, SRC, mine)
        if mid:
            mh = G.c.execute("SELECT home FROM match WHERE mid=?", (mid,)).fetchone()[0]
            x, y, p, q = (hs, as_, ph, pa) if mh == h else (as_, hs, pa, ph)
            mine[mid] = (x, y)
            if reg.link("match", SRC, card, mid) is not None:
                G.xref("match", mid, SRC, card, "date+teams")
            n["linked"] += 1
            if att:
                n["attendance"] += G.c.execute("UPDATE match SET attendance=? WHERE mid=? AND attendance IS NULL", (att, mid)).rowcount
            if p is not None:
                n["shootout"] += G.c.execute("UPDATE match SET pen_h=?, pen_a=? WHERE mid=? AND pen_h IS NULL", (p, q, mid)).rowcount
            continue
        season = str(year)
        if (frame, season) not in eids:
            eids[(frame, season)] = edition_for(G, reg, SRC, f"{frame}|{season}", cids[frame], season)
        mid = reg.mint("match", SRC, card)
        G.put("match", {"mid": mid, "eid": eids[(frame, season)], "date": d, "home": h, "away": a, "hs": hs, "as_": as_, "pen_h": ph, "pen_a": pa,
                        "round": rnd, "attendance": att, "status": "finished"}, SRC)
        G.xref("match", mid, SRC, card, f"{SRC}-native")
        idx.add(mid, d, h, a)
        mine[mid] = (hs, as_)
        n["new"] += 1
    return n

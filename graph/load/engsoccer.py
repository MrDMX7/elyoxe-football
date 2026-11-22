"""Every English league game of the four tiers since 1888, the test matches of 1893–98 and the FA Cup since 1871
(jalapic/engsoccerdata, graph/fetch.engsoccer). A club is linked to ours by its games (the same date and score, any
source: the clubs of 1888 are schochastics'), a game we hold already (schochastics' top flight) is linked, never added
twice. Liverpool–Manchester United held 182 league meetings for the record's 186: the Second Division of 1895/96 and
1904/05 and the 1894 test match were in no source (22 Nov 2026)."""
import csv, os
from graph.link import MatchIndex, edition_for, twin, vote_teams

TIERS = {"1": 47, "2": 48, "3": 108, "4": 109}           # FotMob: Premier League, Championship, League One, League Two
FA_CUP = 132
COMPS = {47: ("Premier League", "الدوري الإنجليزي الممتاز", "league"), 48: ("Championship", "دوري البطولة الإنجليزية", "league"),
         108: ("League One", "دوري الدرجة الأولى الإنجليزي", "league"), 109: ("League Two", "دوري الدرجة الثانية الإنجليزي", "league"),
         FA_CUP: ("FA Cup", "كأس الاتحاد الإنجليزي", "cup")}


def _rows(S):
    """[(date, season start year, home, away, hs, as_, FotMob competition, round)] of the three files"""
    out = []

    def read(name):
        p = os.path.join(S.db, f"engsoccer_{name}.csv")
        return list(csv.DictReader(open(p, encoding="utf-8", newline=""))) if os.path.exists(p) else []

    def goals(r):
        try:
            return int(r["hgoal"]), int(r["vgoal"])
        except (ValueError, TypeError, KeyError):
            return None
    for r in read("england"):
        g = goals(r)
        if g and r.get("tier") in TIERS and r.get("Date", "NA") != "NA":
            out.append((r["Date"][:10], int(r["Season"]), r["home"], r["visitor"], *g, TIERS[r["tier"]], None))
    for r in read("englandplayoffs"):
        g, div = goals(r), r.get("division")
        if not g or r.get("Date", "NA") == "NA":
            continue
        if div == "test match":                   # the top flight's last against the Second Division's first
            out.append((r["Date"][:10], int(r["Season"]), r["home"], r["visitor"], *g, 47, "test match"))
        elif div in TIERS:
            out.append((r["Date"][:10], int(r["Season"]), r["home"], r["visitor"], *g, TIERS[div], "play-off " + (r.get("round") or "")))
    for r in read("facup"):
        g = goals(r)
        if g and r.get("Date", "NA") != "NA" and r.get("nonmatch", "NA") in ("", "NA"):
            out.append((r["Date"][:10], int(r["Season"]), r["home"], r["visitor"], *g, FA_CUP, r.get("round") or None))
    return out


def load(G, reg, S):
    rows = _rows(S)
    if not rows:
        return {"skipped": "no engsoccerdata files"}
    voted = vote_teams(G, reg, "eng", [(d, h, a, hs, as_) for d, _, h, a, hs, as_, _, _ in rows], any_src=True)
    for name, tid in voted.items():
        G.xref("team", tid, "eng", name, "date+score-votes")
    # a club the votes missed (the 22 Nov trial made Brentford, Reading, Bournemouth… twice): ours of that very name with the
    # most games in an English competition — never a namesake abroad with none (Liverpool of Montevideo)
    english = {}
    for tid, name, n in G.c.execute("""SELECT t.tid, lower(t.name), count(*) FROM team t JOIN match m ON m.home=t.tid OR m.away=t.tid
                                        JOIN edition e ON e.eid=m.eid JOIN competition c ON c.cid=e.cid
                                        WHERE c.country IN ('ENG', 'England') GROUP BY t.tid"""):
        if n > english.get(name, (None, 0))[1]:
            english[name] = (tid, n)
    sch = {k[:-len(" (England)")].lower(): t for k, t in G.c.execute(
        "SELECT source_id, tifo_id FROM xref WHERE type='team' AND source='sch' AND source_id LIKE '% (England)'")}   # «Hull City (England)» is FotMob's «Hull»
    named = 0
    for name in sorted({x for r in rows for x in (r[2], r[3])}):
        ours = (english.get(name.lower()) or (None,))[0] or sch.get(name.lower())
        if reg.get("team", "eng", name) is None and ours is not None:
            got = reg.link("team", "eng", name, ours)
            if got is not None:
                G.xref("team", got, "eng", name, "name+english-games")
                named += 1
    done, eids, idx = set(), {}, MatchIndex(G)
    n = {"rows": len(rows), "clubs_voted": len(voted), "clubs_named": named, "linked": 0, "new": 0}
    for fid, (name, ar, kind) in COMPS.items():
        cid = reg.get("competition", "fotmob", fid) or reg.mint("competition", "fotmob", fid)
        if not G.c.execute("SELECT 1 FROM competition WHERE cid=?", (cid,)).fetchone():
            G.put("competition", {"cid": cid, "name": name, "name_ar": ar, "kind": kind, "country": "ENG"}, "eng")
        if not G.c.execute("SELECT 1 FROM xref WHERE type='competition' AND source='fotmob' AND source_id=?", (str(fid),)).fetchone():
            G.xref("competition", cid, "fotmob", fid, "manual")          # publish reads FotMob's id from xref
    for d, y, hn, an, hs, as_, fid, rnd in rows:
        teams = []
        for nm in (hn, an):
            t = reg.get("team", "eng", nm) or reg.mint("team", "eng", nm)
            if ("t", t) not in done:
                done.add(("t", t))
                if not G.c.execute("SELECT 1 FROM team WHERE tid=?", (t,)).fetchone():
                    G.put("team", {"tid": t, "name": nm, "kind": "club", "country": "England"}, "eng")
                    G.xref("team", t, "eng", nm, "eng-native")
            teams.append(t)
        h, a = teams
        key = f"{d}|{hn}|{an}"
        mid = twin(G, idx, d, h, a, hs, as_, "eng")
        if mid:
            if reg.link("match", "eng", key, mid) is not None:
                G.xref("match", mid, "eng", key, "date+teams")
            n["linked"] += 1
            continue
        season = f"{y}/{y + 1}"
        cid = reg.get("competition", "fotmob", fid)
        if (fid, season) not in eids:
            eids[(fid, season)] = edition_for(G, reg, "eng", f"{fid}|{season}", cid, season)
        mid = reg.mint("match", "eng", key)
        G.put("match", {"mid": mid, "eid": eids[(fid, season)], "date": d, "home": h, "away": a, "hs": hs, "as_": as_, "round": rnd, "status": "finished"}, "eng")
        G.xref("match", mid, "eng", key, "eng-native")
        idx.add(mid, d, h, a)
        n["new"] += 1
    return n

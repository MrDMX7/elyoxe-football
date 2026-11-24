"""schochastics/football-data (db/.cache/games.parquet, 1.3M league and continental results since 1888): a result
already in the graph becomes an xref of that match; the rest are new matches. Clubs link through db/history.py's
crosswalk (date+score votes, crosswalk.json); a competition (or a season of it) links to ours when 90% of its linked
games sit in one of ours. Hygiene as db/history.py: one copy per game, no placeholder teams, no «X v X»."""
import os
from collections import Counter, defaultdict
from graph.link import MatchIndex, edition_for, twin, vote_alias, vote_teams


def _season(d):
    return f"{d.year}/{d.year + 1}" if d.month >= 7 else f"{d.year - 1}/{d.year}"


def fresh(seen, key, score):
    """The row's match key: a second row of one key with another score (a placeholder date, the season's 1 July: Lens–Cannes
    2-2 and 3-1 «on 1937-07-01») is another match, key#2; the same row again is the same match."""
    k, n = key, 1
    while k in seen and seen[k] != score:
        n += 1
        k = f"{key}#{n}"
    seen[k] = score
    return k


SOVIET = {"RU", "UA", "GE", "BY", "AM", "AZ", "KZ", "UZ", "LT", "LV", "EE", "MD", "TJ", "TM", "KG"}
SOUTH_AMERICA = {"AR", "BR", "UY", "PY", "CL", "CO", "PE", "EC", "BO", "VE"}


def league_of(comp, lvl, cc, other_cc):
    """the dataset files the defunct countries' leagues under one «ddr» (23 Nov 2026: the Soviet, Yugoslav and East German
    leagues with the Cup Winners' Cup and the old Intercontinental Cup, one competition): each its own, by the clubs' countries"""
    if comp != "ddr":
        return comp
    if lvl == "international":
        return "intercontinental-cup-old" if cc in SOUTH_AMERICA or other_cc in SOUTH_AMERICA else "cup-winners-cup"
    return "yugoslavia" if cc == "YUG" else "east-germany" if cc == "DE" else "soviet-union" if cc in SOVIET else f"ddr-{cc}"


def load(G, reg, S):
    import duckdb
    from db.history import BLANK
    pq = os.path.join(S.db, "games.parquet").replace("\\", "/")
    if not os.path.exists(pq):
        return {"skipped": "no games.parquet"}
    cw = S.read(os.path.join(S.db, "crosswalk.json")) or {}
    for fid, key in sorted(cw.items(), key=lambda x: int(x[0])):
        tid = reg.link("team", "sch", key, reg.mint("team", "fotmob", int(fid)))
        if tid is not None:
            G.xref("team", tid, "sch", key, "vote")
    rows = duckdb.sql(f"""select date, home_ident, away_ident, gh, ga, competition, level, home, away, home_code
        from read_parquet('{pq}') where gh is not null and ga is not null and home_ident <> away_ident
          and home_ident not in {BLANK} and away_ident not in {BLANK}
        qualify row_number() over (partition by date, home_ident, away_ident, gh, ga, competition order by level) = 1
        order by date, competition, home_ident, away_ident""").fetchall()
    code = {}
    for r in rows:
        code.setdefault(r[1], r[9])
    # the dataset left some seasons without a league (24 Nov 2026: Australia's NSL 1977-2004 with Haiti, Panama, the Philippines,
    # Indonesia and Bhutan, 8,502 games under one «None»): each under the league its country's other seasons carry
    named = defaultdict(Counter)
    for r in rows:
        if r[5] and r[5] != "ddr" and r[6] == "national":
            named[r[9]][r[5]] += 1
    own = {cc: n.most_common(1)[0][0] for cc, n in named.items()}
    rows = [(*r[:5], league_of(r[5], r[6], r[9], code.get(r[2])) or own.get(r[9]) or f"none-{r[9]}", *r[6:]) for r in rows]
    # clubs the crosswalk lacks: the same date+score votes, on the seasons FotMob covers (since 2010/11)
    voted = vote_teams(G, reg, "sch", [(str(r[0]), r[1], r[2], r[3], r[4]) for r in rows], since="2010-07-01")
    for k, tid in voted.items():
        G.xref("team", tid, "sch", k, "date+score-votes")
    idx = MatchIndex(G)
    eid_of = {mid: eid for mid, eid in G.c.execute("SELECT mid, eid FROM match")}
    cid_of = {eid: cid for eid, cid in G.c.execute("SELECT eid, cid FROM edition")}
    season_of = {eid: s for eid, s in G.c.execute("SELECT eid, season FROM edition")}
    # FotMob's stage ids (FotMob gave Egypt's 2011/12 to 2013/14 games none: «FotMob None»): no vote, and their games move
    stage = {c for (c,) in G.c.execute("SELECT cid FROM competition WHERE name LIKE 'FotMob %'")}
    # pass 1: twins, and the competitions/editions their twins vote for
    twins, cvotes, evotes = {}, defaultdict(Counter), defaultdict(Counter)
    for i, (d, hi, ai, gh, ga, comp, lvl, hn, an, cc) in enumerate(rows):
        h, a = reg.get("team", "sch", hi), reg.get("team", "sch", ai)
        if h and a:
            mid = twin(G, idx, str(d), h, a, gh, ga, "sch")
            if mid:
                twins[i] = mid
                e = eid_of.get(mid)
                if e and cid_of[e] not in stage:
                    cvotes[comp][cid_of[e]] += 1
                    evotes[f"{comp}|{_season(d)}"][e] += 1
    vote_alias(reg, "competition", cvotes, "sch", min_n=20, share=0.9)
    vote_alias(reg, "edition", evotes, "sch", min_n=5, share=0.9)
    # pass 2: rows
    new = linked = moved = 0
    done, eids, seen = set(), {}, {}
    for i, (d, hi, ai, gh, ga, comp, lvl, hn, an, cc) in enumerate(rows):
        mk = fresh(seen, f"{d}|{hi}|{ai}", (gh, ga))
        if i in twins:
            got = reg.link("match", "sch", mk, twins[i])
            if got is not None:
                G.xref("match", got, "sch", mk, "date+teams")
                linked += 1
                e, real = eid_of.get(got), reg.get("competition", "sch", comp)
                if e and cid_of.get(e) in stage and real is not None and real not in stage:
                    to = edition_for(G, reg, "sch-stage", f"{real}|{season_of[e]}", real, season_of[e])   # the league's own, FotMob's label
                    G.c.execute("UPDATE match SET eid=? WHERE mid=?", (to, got))
                    moved += 1
                continue
        cid = reg.get("competition", "sch", comp) or reg.mint("competition", "sch", comp)
        if ("c", cid) not in done:
            done.add(("c", cid))
            G.put("competition", {"cid": cid, "name": comp, "kind": "league" if lvl == "national" else None,
                                  "scope": None if lvl == "national" else lvl, "country": cc if lvl == "national" else None}, "sch")
            G.xref("competition", cid, "sch", comp, "vote" if reg.get("competition", "sch", comp) in cid_of.values() else "sch-native")
        sk = f"{comp}|{_season(d)}"
        if ("e", sk) not in done:
            done.add(("e", sk))
            eids[sk] = edition_for(G, reg, "sch", sk, cid, _season(d))
        eid = eids[sk]
        h = reg.get("team", "sch", hi) or reg.mint("team", "sch", hi)
        a = reg.get("team", "sch", ai) or reg.mint("team", "sch", ai)
        for tid, key, nm in ((h, hi, hn), (a, ai, an)):
            if ("t", tid) not in done:
                done.add(("t", tid))
                G.put("team", {"tid": tid, "name": nm, "kind": "club"}, "sch")
                if not G.c.execute("SELECT 1 FROM xref WHERE type='team' AND source='sch' AND source_id=?", (key,)).fetchone():
                    G.xref("team", tid, "sch", key, "sch-native")
        mid = reg.mint("match", "sch", mk)
        G.put("match", {"mid": mid, "eid": eid, "date": str(d), "home": h, "away": a, "hs": gh, "as_": ga, "status": "finished"}, "sch")
        G.xref("match", mid, "sch", mk, "sch-native")
        idx.add(mid, str(d), h, a)
        new += 1
        if new % 100000 == 0:
            print(f"schochastics: {new} new", flush=True)
            G.c.commit()
    return {"rows": len(rows), "clubs_voted": len(voted), "linked": linked, "new": new, "stage_moved": moved, "comps_linked": sum(1 for k in cvotes if reg.get("competition", "sch", k))}

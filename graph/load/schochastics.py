"""schochastics/football-data (db/.cache/games.parquet, 1.3M league and continental results since 1888): a result
already in the graph becomes an xref of that match; the rest are new matches. Clubs link through db/history.py's
crosswalk (date+score votes, crosswalk.json); a competition (or a season of it) links to ours when 90% of its linked
games sit in one of ours. Hygiene as db/history.py: one copy per game, no placeholder teams, no «X v X»."""
import os
from collections import Counter, defaultdict
from graph.link import MatchIndex, twin, vote_alias


def _season(d):
    return f"{d.year}/{d.year + 1}" if d.month >= 7 else f"{d.year - 1}/{d.year}"


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
    idx = MatchIndex(G)
    eid_of = {mid: eid for mid, eid in G.c.execute("SELECT mid, eid FROM match")}
    cid_of = {eid: cid for eid, cid in G.c.execute("SELECT eid, cid FROM edition")}
    # pass 1: twins, and the competitions/editions their twins vote for
    twins, cvotes, evotes = {}, defaultdict(Counter), defaultdict(Counter)
    for i, (d, hi, ai, gh, ga, comp, lvl, hn, an, cc) in enumerate(rows):
        h, a = reg.get("team", "sch", hi), reg.get("team", "sch", ai)
        if h and a:
            mid = twin(G, idx, str(d), h, a, gh, ga, "sch")
            if mid:
                twins[i] = mid
                e = eid_of.get(mid)
                if e:
                    cvotes[comp][cid_of[e]] += 1
                    evotes[f"{comp}|{_season(d)}"][e] += 1
    vote_alias(reg, "competition", cvotes, "sch", min_n=20, share=0.9)
    vote_alias(reg, "edition", evotes, "sch", min_n=5, share=0.9)
    # pass 2: rows
    new = linked = 0
    done = set()
    for i, (d, hi, ai, gh, ga, comp, lvl, hn, an, cc) in enumerate(rows):
        if i in twins:
            got = reg.link("match", "sch", f"{d}|{hi}|{ai}", twins[i])
            if got is not None:
                G.xref("match", got, "sch", f"{d}|{hi}|{ai}", "date+teams")
                linked += 1
                continue
        cid = reg.get("competition", "sch", comp) or reg.mint("competition", "sch", comp)
        if ("c", cid) not in done:
            done.add(("c", cid))
            G.put("competition", {"cid": cid, "name": comp, "kind": "league" if lvl == "national" else None,
                                  "scope": None if lvl == "national" else lvl, "country": cc if lvl == "national" else None}, "sch")
            G.xref("competition", cid, "sch", comp, "vote" if reg.get("competition", "sch", comp) in cid_of.values() else "sch-native")
        sk = f"{comp}|{_season(d)}"
        eid = reg.get("edition", "sch", sk) or reg.mint("edition", "sch", sk)
        if ("e", eid) not in done:
            done.add(("e", eid))
            G.put("edition", {"eid": eid, "cid": cid, "season": _season(d)}, "sch")
            G.xref("edition", eid, "sch", sk, "sch-native")
        h = reg.get("team", "sch", hi) or reg.mint("team", "sch", hi)
        a = reg.get("team", "sch", ai) or reg.mint("team", "sch", ai)
        for tid, key, nm in ((h, hi, hn), (a, ai, an)):
            if ("t", tid) not in done:
                done.add(("t", tid))
                G.put("team", {"tid": tid, "name": nm, "kind": "club"}, "sch")
                if not G.c.execute("SELECT 1 FROM xref WHERE type='team' AND source='sch' AND source_id=?", (key,)).fetchone():
                    G.xref("team", tid, "sch", key, "sch-native")
        mid = reg.mint("match", "sch", f"{d}|{hi}|{ai}")
        G.put("match", {"mid": mid, "eid": eid, "date": str(d), "home": h, "away": a, "hs": gh, "as_": ga, "status": "finished"}, "sch")
        G.xref("match", mid, "sch", f"{d}|{hi}|{ai}", "sch-native")
        idx.add(mid, str(d), h, a)
        new += 1
        if new % 100000 == 0:
            print(f"schochastics: {new} new", flush=True)
            G.c.commit()
    return {"rows": len(rows), "linked": linked, "new": new, "comps_linked": sum(1 for k in cvotes if reg.get("competition", "sch", k))}

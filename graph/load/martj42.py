"""Every men's international since 1872 (martj42/international_results). A national team links when FotMob's name maps to
the dataset's (compute/national.py's aliases); a result FotMob already has becomes its xref, the rest are new matches in
a competition per tournament name."""
import csv, os
from collections import Counter, defaultdict
from graph.link import MatchIndex, edition_for, twin, vote_alias, vote_teams


# the tournaments FotMob has under one id (a manual link, spec §3.3 «manual»: too few shared games to vote before 2026)
FOTMOB = {"FIFA World Cup": 77, "AFC Asian Cup": 290, "Gulf Cup": 329, "Arab Cup": 10242, "African Cup of Nations": 289,
          "UEFA Euro": 50, "Copa América": 44, "UEFA Nations League": 9806}


def load(G, reg, S):
    from compute.national import dataset_name
    p = os.path.join(S.db, "martj42_results.csv")
    if not os.path.exists(p):
        return {"skipped": "no martj42_results.csv"}
    data = list(csv.DictReader(open(p, encoding="utf-8", newline="")))
    known = {r["home_team"] for r in data} | {r["away_team"] for r in data}
    tl = 0
    teams = G.c.execute("SELECT tid, name FROM team WHERE kind='national' ORDER BY tid").fetchall()
    # the exact name (or compute/national.py's alias) first; dataset_name's « U23»-stripped fallback only for a dataset
    # name no senior side took, so «Saudi Arabia U23» never takes Saudi Arabia's history
    for fallback in (False, True):
        for tid, name in teams:
            if fallback != name.endswith(" U23"):
                continue
            dn = dataset_name(name, known)
            if dn and reg.get("team", "martj42", dn) is None:
                got = reg.link("team", "martj42", dn, tid)
                if got is not None:
                    G.xref("team", got, "martj42", dn, "fotmob-name-alias")
                    tl += 1
    games = []
    for r in data:
        try:
            games.append((r["date"], r["home_team"], r["away_team"], int(r["home_score"]), int(r["away_score"])))
        except (ValueError, KeyError):
            pass
    for k, tid in vote_teams(G, reg, "martj42", games).items():     # national sides no name rule caught
        G.xref("team", tid, "martj42", k, "date+score-votes")
        tl += 1
    idx = MatchIndex(G)
    eid_of = {mid: eid for mid, eid in G.c.execute("SELECT mid, eid FROM match WHERE eid IS NOT NULL")}
    cid_of = {eid: cid for eid, cid in G.c.execute("SELECT eid, cid FROM edition")}
    # pass 1: the twins, and which of our competitions and editions they vote for (as schochastics)
    rows, cvotes, evotes = [], defaultdict(Counter), defaultdict(Counter)
    for r in data:
        try:
            hs, as_ = int(r["home_score"]), int(r["away_score"])
        except (ValueError, KeyError):
            continue
        h, a = (reg.get("team", "martj42", r["home_team"]) or reg.mint("team", "martj42", r["home_team"]),
                reg.get("team", "martj42", r["away_team"]) or reg.mint("team", "martj42", r["away_team"]))
        mid = twin(G, idx, r["date"], h, a, hs, as_, "martj42")
        if mid and eid_of.get(mid):
            e = eid_of[mid]
            cvotes[r["tournament"]][cid_of[e]] += 1
            evotes[f"{r['tournament']}|{r['date'][:4]}"][e] += 1
        rows.append((r, h, a, hs, as_, mid))
    for name, fid in sorted(FOTMOB.items()):
        got = reg.link("competition", "martj42", name, reg.mint("competition", "fotmob", fid))
        if got is not None:
            G.xref("competition", got, "martj42", name, "manual")
            if not G.c.execute("SELECT 1 FROM xref WHERE type='competition' AND source='fotmob' AND source_id=?", (str(fid),)).fetchone():
                G.xref("competition", got, "fotmob", fid, "manual")   # FotMob gave none of its matches (the Asian Cup): publish reads xref
    vote_alias(reg, "competition", cvotes, "martj42", min_n=10, share=0.9)
    vote_alias(reg, "edition", evotes, "martj42", min_n=3, share=0.9)
    linked = new = 0
    ours = {e for (e,) in G.c.execute("""SELECT e.eid FROM edition e JOIN xref x ON x.type='competition' AND x.source='fotmob'
                                          AND x.tifo_id=e.cid""")}               # the editions the site publishes

    def curated(name, y):
        """The curated tournament's edition of that year (or the year before: Euro 2020 and the 2021 Africa Cup were played a
        year late), when the graph holds it"""
        fid = FOTMOB.get(name)
        cid = reg.get("competition", "fotmob", fid) if fid else None
        for season in ((y, str(int(y) - 1)) if cid else ()):
            hit = G.c.execute("SELECT eid FROM edition WHERE cid=? AND season=? ORDER BY eid LIMIT 1", (cid, season)).fetchone()
            if hit:
                return hit[0]
        return None
    for r, h, a, hs, as_, mid in rows:
        for tid, nm in ((h, r["home_team"]), (a, r["away_team"])):
            G.put("team", {"tid": tid, "name": nm, "kind": "national"}, "martj42")
        key = f"{r['date']}|{r['home_team']}|{r['away_team']}"
        if mid:
            mid = reg.link("match", "martj42", key, mid)
        if mid:
            G.xref("match", mid, "martj42", key, "date+teams")
            linked += 1
            cur = G.c.execute("SELECT eid FROM match WHERE mid=?", (mid,)).fetchone()
            e = curated(r["tournament"], r["date"][:4]) if cur and cur[0] not in ours else None
            if e:                              # Transfermarkt's «FIWC»/«AFAC» held it: it is the curated tournament's game
                G.c.execute("UPDATE match SET eid=? WHERE mid=?", (e, mid))
            continue
        cid = reg.get("competition", "martj42", r["tournament"]) or reg.mint("competition", "martj42", r["tournament"])
        G.put("competition", {"cid": cid, "name": r["tournament"], "scope": "international"}, "martj42")
        y = r["date"][:4]
        eid = edition_for(G, reg, "martj42", f"{r['tournament']}|{y}", cid, y)
        mid = reg.mint("match", "martj42", key)
        G.put("match", {"mid": mid, "eid": eid, "date": r["date"], "home": h, "away": a, "hs": hs, "as_": as_, "status": "finished"}, "martj42")
        G.xref("match", mid, "martj42", key, "martj42-native")
        idx.add(mid, r["date"], h, a)
        new += 1
    return {"rows": len(data), "linked": linked, "new": new, "teams_linked": tl}

"""365Scores, read from what db/scores365.py publishes (v1/s365/): every competition's champions (the Premier League from
1888/89, the UAE league from 1973/74), the Arab final tables, and this season's results of the Arab leagues FotMob lacks.
A 365 team links through the FotMob id db/scores365.py found for it; a 365 competition links when FotMob lists one with
the same English name in the same country."""
import os, re, unicodedata
from graph.link import MatchIndex, twin


def fold(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def load(G, reg, S):
    ix = S.published("s365/index.json")
    if not ix:
        return {"skipped": "no s365/index.json"}
    countries = {str(k): v for k, v in (ix.get("countries") or {}).items()}
    fm_by = {}
    al = S.read(os.path.join(S.db, "fm_allleagues.json")) or {}
    for grp in al.get("countries") or []:
        for lg in grp.get("leagues") or []:
            fm_by.setdefault((fold(grp.get("name")), fold(lg.get("name"))), []).append(int(lg["id"]))
    n = {"teams": 0, "teams_linked": 0, "comps": 0, "comps_linked": 0, "champions": 0, "standings": 0, "matches": 0, "matches_linked": 0}
    for sid, ar, en, cc, fid in sorted(ix.get("teams") or [], key=lambda r: r[0]):
        if fid:
            tid = reg.link("team", "s365", sid, reg.mint("team", "fotmob", int(fid)))
            if tid is not None:
                G.xref("team", tid, "s365", sid, "s365-fmmap")
                n["teams_linked"] += 1
        tid = reg.get("team", "s365", sid) or reg.mint("team", "s365", sid)
        G.put("team", {"tid": tid, "name": en or None, "name_ar": ar or None, "country": (countries.get(str(cc)) or [None, None])[1]}, "s365")
        if not fid:
            G.xref("team", tid, "s365", sid, "s365-native")
        n["teams"] += 1
    eids = {}
    for row in sorted(ix.get("comps") or [], key=lambda r: r[0]):
        cid_s, ar, en, cc, ko = row[0], row[1], row[2], row[3], row[4]
        cname = (countries.get(str(cc)) or [None, None])[1]
        cands = fm_by.get((fold(cname), fold(en)), [])
        if len(cands) == 1 and reg.link("competition", "s365", cid_s, reg.mint("competition", "fotmob", cands[0])) is not None:
            G.xref("competition", reg.get("competition", "s365", cid_s), "s365", cid_s, "country+name")
            n["comps_linked"] += 1
        cid = reg.get("competition", "s365", cid_s) or reg.mint("competition", "s365", cid_s)
        G.put("competition", {"cid": cid, "name": en, "name_ar": ar, "kind": "cup" if ko else "league", "country": cname}, "s365")
        if not cands:
            G.xref("competition", cid, "s365", cid_s, "s365-native")
        n["comps"] += 1
        d = S.published(f"s365/comp/{cid_s}.json") or {}

        def edition(season):
            k = (cid, season)
            if k not in eids:
                hit = G.c.execute("SELECT eid FROM edition WHERE cid=? AND season=?", (cid, season)).fetchone()
                eids[k] = hit[0] if hit else reg.mint("edition", "s365", f"{cid_s}|{season}")
                if not hit:
                    G.put("edition", {"eid": eids[k], "cid": cid, "season": season}, "s365")
                    G.xref("edition", eids[k], "s365", f"{cid_s}|{season}", "s365-native")
            return eids[k]

        def team(sid):
            return reg.get("team", "s365", sid) or reg.mint("team", "s365", sid)

        for season, winner, vals, *_ in d.get("champions") or []:
            if winner:
                eid = edition(season)
                G.c.execute("INSERT OR IGNORE INTO honour(eid, kind, rank, tid, value, src) VALUES(?,?,?,?,?,?)",
                            (eid, "champion", 1, team(winner), ",".join(map(str, vals or [])) or None, "s365"))
                n["champions"] += 1
        for season, rows in sorted((d.get("tables") or {}).items()):
            eid = edition(season)
            if G.c.execute("SELECT 1 FROM standing WHERE eid=?", (eid,)).fetchone():
                continue
            for pos, t, p, w, dr, l, gf, ga, pts in rows:
                G.c.execute("INSERT OR IGNORE INTO standing VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (eid, "", pos, team(t), p, w, dr, l, gf, ga, pts, "s365"))
                n["standings"] += 1
        res = (d.get("live") or {}).get("results") or []
        if res:
            idx = MatchIndex(G)
            for gid, ko, sn, rnd, h, a, hs, as_, *_ in res:
                if hs is None or as_ is None:
                    continue
                th, ta = team(h), team(a)
                mid = twin(G, idx, ko[:10], th, ta, hs, as_, "s365")
                if mid:
                    mid = reg.link("match", "s365", gid, mid)
                if mid:
                    G.xref("match", mid, "s365", gid, "date+teams")
                    n["matches_linked"] += 1
                    continue
                y, mo = int(ko[:4]), int(ko[5:7])
                mid = reg.mint("match", "s365", gid)
                G.put("match", {"mid": mid, "eid": edition(f"{y}/{y + 1}" if mo >= 7 else f"{y - 1}/{y}"), "round": str(rnd) if rnd is not None else None,
                                "date": ko + ":00Z" if len(ko) == 16 else ko, "home": th, "away": ta, "hs": hs, "as_": as_, "status": "finished"}, "s365")
                G.xref("match", mid, "s365", gid, "s365-native")
                idx.add(mid, ko, th, ta)
                n["matches"] += 1
    return n

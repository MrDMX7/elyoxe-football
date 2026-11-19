"""RSSSF's Arab league seasons before the other sources start (db/rsssf.py publishes v1/history/arab/<code>.json: every
season's final table, its champion and the FotMob id of each club it could link): the tables as standings of the
country's FotMob league, the champion as an honour, and the dated cup games of db/.cache/rsssf_clubs.json as matches. A
season whose table the graph already has (365Scores) keeps it; a club RSSSF could not link is a team of its own
(`rsssf-name`, «<code>|<name>»)."""
import os
from graph.link import MatchIndex, twin


def load(G, reg, S, codes=None):
    if codes is None:
        try:
            from db.rsssf import COUNTRIES
            codes = sorted(COUNTRIES)
        except Exception as e:
            print(f"db.rsssf not importable: {e}", flush=True)
            codes = []
    n = {"seasons": 0, "standings": 0, "champions": 0, "matches": 0, "matches_linked": 0}

    def team(code, name, fid):
        if fid:
            return reg.mint("team", "fotmob", int(fid))
        k = f"{code}|{name}"
        tid = reg.get("team", "rsssf-name", k)
        if tid is None:
            tid = reg.mint("team", "rsssf-name", k)
            G.put("team", {"tid": tid, "name": name, "kind": "club"}, "rsssf")
            G.xref("team", tid, "rsssf-name", k, "rsssf-native")
        return tid

    for code in codes:
        d = S.published(f"history/arab/{code}.json")
        if not d:
            continue
        lid = d.get("league")
        if lid:
            cid = reg.mint("competition", "fotmob", int(lid))
            G.put("competition", {"cid": cid, "name": f"FotMob {lid}"}, "fotmob")
        else:
            cid = reg.get("competition", "rsssf", code) or reg.mint("competition", "rsssf", code)
            G.put("competition", {"cid": cid, "name": f"{code} top league (RSSSF)", "kind": "league"}, "rsssf")
            G.xref("competition", cid, "rsssf", code, "rsssf-native")
        for s in d.get("seasons") or []:
            season = s.get("season")
            if not season:
                continue
            hit = G.c.execute("SELECT eid FROM edition WHERE cid=? AND season=?", (cid, season)).fetchone()
            if hit:
                eid = hit[0]
            else:
                eid = reg.get("edition", "rsssf", f"{code}|{season}") or reg.mint("edition", "rsssf", f"{code}|{season}")
                G.put("edition", {"eid": eid, "cid": cid, "season": season}, "rsssf")
                G.xref("edition", eid, "rsssf", f"{code}|{season}", "rsssf-native")
            n["seasons"] += 1
            table = s.get("table") or []
            if table and not G.c.execute("SELECT 1 FROM standing WHERE eid=?", (eid,)).fetchone():
                for pos, name, fid, p, w, dr, l, gf, ga, pts in table:
                    G.c.execute("INSERT OR IGNORE INTO standing VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                                (eid, "", pos, team(code, name, fid), p, w, dr, l, gf, ga, pts, "rsssf"))
                    n["standings"] += 1
            if table and table[0][0] == 1:     # db/rsssf.py keeps a table only when its first club is the champions page's
                if G.c.execute("INSERT OR IGNORE INTO honour(eid, kind, rank, tid, src) VALUES(?,?,?,?,?)",
                               (eid, "champion", 1, team(code, table[0][1], table[0][2]), "rsssf")).rowcount:
                    n["champions"] += 1
    clubs = S.read(os.path.join(S.db, "rsssf_clubs.json")) or {}
    idx = MatchIndex(G)
    for fid in sorted(clubs, key=lambda x: int(x) if x.isdigit() else 0):
        if not fid.isdigit():
            continue
        me = reg.mint("team", "fotmob", int(fid))
        for d, opp, home, gf, ga, comp in clubs[fid].get("matches") or []:
            if not isinstance(opp, int):
                continue
            other = reg.mint("team", "fotmob", opp)
            h, a, hs, as_ = (me, other, gf, ga) if home else (other, me, ga, gf)
            mid = twin(G, idx, d, h, a, hs, as_, "rsssf")
            key = f"{d}|{min(int(fid), opp)}|{max(int(fid), opp)}"
            if mid:
                if reg.alias("match", "rsssf", key, mid):
                    G.xref("match", mid, "rsssf", key, "date+teams")
                n["matches_linked"] += 1
                continue
            ck = comp.split(":", 1)[1] if ":" in comp else comp
            cid = reg.get("competition", "rsssf", ck) or reg.mint("competition", "rsssf", ck)
            G.put("competition", {"cid": cid, "name": ck, "kind": "cup" if ck.endswith("cup") else None}, "rsssf")
            y, mo = int(d[:4]), int(d[5:7])
            season = f"{y}/{y + 1}" if mo >= 7 else f"{y - 1}/{y}"
            eid = reg.get("edition", "rsssf", f"{ck}|{season}") or reg.mint("edition", "rsssf", f"{ck}|{season}")
            G.put("edition", {"eid": eid, "cid": cid, "season": season}, "rsssf")
            mid = reg.mint("match", "rsssf", key)
            G.put("match", {"mid": mid, "eid": eid, "date": d, "home": h, "away": a, "hs": hs, "as_": as_, "status": "finished"}, "rsssf")
            G.xref("match", mid, "rsssf", key, "rsssf-native")
            idx.add(mid, d, h, a)
            n["matches"] += 1
    return n

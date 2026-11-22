"""Moves: Transfermarkt's full histories (history/.cache/transfers.json, dcaribou) for the players matched to FotMob, and
FotMob's moves of this season (v1/transfers/all.json). A club is linked when the source carries its FotMob id; else the
move keeps the source's club name only in the team table as a new team (one per source name)."""
import os
from graph.load.tm import rows, season

# Transfermarkt's clubs that are no club: a move there is the end of a career, a spell without a club, or not known
NO_CLUB = {"123": "retired", "515": "without club", "2113": "career break", "75": "unknown"}


def load(G, reg, S):
    n = {"tm": 0, "fotmob": 0}

    def club(fid, name, src):
        if fid:
            return reg.mint("team", "fotmob", int(fid))
        if not name:
            return None
        tid = reg.get("team", f"{src}-name", name) or reg.mint("team", f"{src}-name", name)
        G.put("team", {"tid": tid, "name": name}, src)
        return tid

    written = set()

    def tm_club(tmc, name):
        """a Transfermarkt club: its tie to FotMob's when the graph has one, else Transfermarkt's own record"""
        if not tmc or tmc in NO_CLUB:
            return None
        tid = reg.get("team", "tm", str(tmc)) or reg.mint("team", "tm", str(tmc))
        if tid not in written:
            written.add(tid)
            if not G.c.execute("SELECT 1 FROM team WHERE tid=?", (tid,)).fetchone():
                G.put("team", {"tid": tid, "name": name}, "tm")
        return tid

    for tmid, moves in sorted(((S.read(os.path.join(S.hist, "transfers.json")) or {}).get("players") or {}).items()):
        pid = reg.get("player", "tm", str(tmid))
        if not pid:
            continue
        for d, sn, fr, fr_id, to, to_id, fee, mv, *_ in moves:
            G.c.execute("INSERT OR IGNORE INTO transfer VALUES(?,?,?,?,?,?,?,?)",
                        (pid, club(fr_id, fr, "tm"), club(to_id, to, "tm"), d, season(sn), fee, "free" if fee == 0 else None, "tm"))
            n["tm"] += 1
    # the whole history (salimt/football-datasets transfer_history.csv, db/tmdata.py: 1.1M moves since the 1980s) for the
    # men the graph ties to Transfermarkt; a move dcaribou gave already is kept once (the table's key)
    n["tm_history"] = 0
    for r in rows(os.path.join(S.db, "tm", "transfer_history.csv")):
        pid = reg.get("player", "tm", r["player_id"])
        if not pid or not r.get("transfer_date"):
            continue
        to_id, typ = r.get("to_team_id") or "", (r.get("transfer_type") or "").lower()
        kind = NO_CLUB.get(to_id) or ("loan" if typ == "loan" else "loan_end" if "end of loan" in typ else None)
        fee = int(float(r["transfer_fee"])) if (r.get("transfer_fee") or "").replace(".", "", 1).isdigit() and float(r["transfer_fee"]) > 0 else None
        G.c.execute("INSERT OR IGNORE INTO transfer VALUES(?,?,?,?,?,?,?,?)",
                    (pid, tm_club(r.get("from_team_id"), r.get("from_team_name")), None if to_id in NO_CLUB else tm_club(to_id, r.get("to_team_name")),
                     r["transfer_date"][:10], season(r.get("season_name")), fee, kind, "tm"))
        n["tm_history"] += 1
    for m in (S.published("transfers/all.json") or {}).get("moves") or []:
        d, fpid, name, fr_id, fr, to_id, to, fee, typ = m[:9]
        pid = reg.mint("player", "fotmob", int(fpid))
        G.put("player", {"pid": pid, "name": name}, "fotmob")
        y, mo = int(d[:4]), int(d[5:7])
        G.c.execute("INSERT OR IGNORE INTO transfer VALUES(?,?,?,?,?,?,?,?)",
                    (pid, club(fr_id if fr_id not in (2, None) else None, fr, "fotmob"), club(to_id if to_id not in (2, None) else None, to, "fotmob"),
                     d, f"{y}/{y + 1}" if mo >= 7 else f"{y - 1}/{y}", fee, typ, "fotmob"))
        n["fotmob"] += 1
    return n

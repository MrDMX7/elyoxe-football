"""Moves: Transfermarkt's full histories (history/.cache/transfers.json, dcaribou) for the players matched to FotMob, and
FotMob's moves of this season (v1/transfers/all.json). A club is linked when the source carries its FotMob id; else the
move keeps the source's club name only in the team table as a new team (one per source name)."""
import os
from graph.load.tm import season


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

    for tmid, moves in sorted(((S.read(os.path.join(S.hist, "transfers.json")) or {}).get("players") or {}).items()):
        pid = reg.get("player", "tm", str(tmid))
        if not pid:
            continue
        for d, sn, fr, fr_id, to, to_id, fee, mv, *_ in moves:
            G.c.execute("INSERT OR IGNORE INTO transfer VALUES(?,?,?,?,?,?,?,?)",
                        (pid, club(fr_id, fr, "tm"), club(to_id, to, "tm"), d, season(sn), fee, "free" if fee == 0 else None, "tm"))
            n["tm"] += 1
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

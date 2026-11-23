"""Competitions known only by a code or a slug (Transfermarkt's «TR1», schochastics' «hungary», «ddr»: 589 holding a million
games on 22 Nov 2026, read on the profiles, the old clubs' and the coaches' pages) take their Arabic name from
names/comps_ar.json (names/comps.py), never over a name they have. Late in the build: those loaders make them."""
import os


def load(G, reg, S):
    names = S.read(os.path.join(S.names, "comps_ar.json")) or {}
    n = 0
    for cid, name in G.c.execute("SELECT cid, name FROM competition WHERE name_ar IS NULL OR name_ar=''").fetchall():
        ar = (names.get(name) or {}).get("ar")
        if ar:
            G.c.execute("UPDATE competition SET name_ar=? WHERE cid=?", (ar, cid))
            n += 1
    # (23 Nov 2026) the old leagues' clubs with no Transfermarkt id (Bristol Rovers, Hearts, Ferencváros: 11,067), by Tifo id
    # (names/clubs_k.py); a club merged away is not made again, a name it has stays
    t = 0
    for k, v in (S.read(os.path.join(S.names, "clubs_k_ar.json")) or {}).items():
        if k.startswith("t") and k[1:].isdigit() and v.get("ar"):
            t += G.c.execute("UPDATE team SET name_ar=? WHERE tid=? AND (name_ar IS NULL OR name_ar='')", (v["ar"], int(k[1:]))).rowcount
    return {"named": n, "clubs": t}

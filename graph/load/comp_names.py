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
    return {"named": n}

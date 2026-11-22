"""The archive job's data step (docs/superpowers/specs/2026-11-22-tifo-archive-static-design.md): from a built tifo.db, the
season files (editions/<FotMob id>.json) and the match files (matches/<FotMob id>/<season>.json) of every competition — the
same files graph/publish.py gives the site for a few — into a local folder for site/archive/build.cjs. Nothing is uploaded.

    python -m graph.archive_export --db tifo.db --out work/data [--comps 47,87]
"""
import argparse, os, sqlite3, time
from collections import Counter

from graph import publish as P


def open_graph(path):
    """the built database, read as graph.db.Graph without recreating it"""
    from graph.db import Graph
    G = Graph.__new__(Graph)
    G.path, G.c = path, sqlite3.connect(path)
    G.cols = {t: [r[1] for r in G.c.execute(f"PRAGMA table_info({t})")] for (t,) in G.c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    G.stats = Counter()
    return G


def competitions(G):
    """every FotMob competition with matches in the archive"""
    return sorted({int(fid) for (fid,) in G.c.execute("""SELECT DISTINCT x.source_id FROM xref x JOIN edition e ON e.cid=x.tifo_id
                                                          JOIN match m ON m.eid=e.eid WHERE x.type='competition' AND x.source='fotmob'""")
                   if str(fid).isdigit()})


def export(db, out, comps=None):
    G = open_graph(db)
    os.makedirs(out, exist_ok=True)
    t = time.time()
    rec = {"editions": P.editions(G, out)}
    fids = comps or competitions(G)
    rec["matches"] = P.matches(G, out, comps=tuple(fids), teams=())
    rec["people"] = P.people(G, out)
    rec["secs"] = round(time.time() - t)
    rec["competitions"] = len(fids)
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--comps", default="")
    a = ap.parse_args(argv)
    comps = [int(x) for x in a.comps.split(",") if x.strip()] or None
    print(export(a.db, a.out, comps), flush=True)


if __name__ == "__main__":
    main()

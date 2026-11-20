"""Seasons with no champion (graph/void_seasons.yaml): after every source has loaded, their champion and runner-up honours
are dropped and the edition is marked void with what happened. Other honours stand (the goals of a cancelled season were scored)."""
import os
import yaml
from graph.link import edition_for

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(G, reg, S, seasons=None):
    if seasons is None:
        seasons = yaml.safe_load(open(os.path.join(HERE, "void_seasons.yaml"), encoding="utf-8")) or {}
    n = {"seasons": 0, "honours_removed": 0}
    for fid, rows in seasons.items():
        cid = reg.get("competition", "fotmob", int(fid))
        if cid is None:
            continue
        for season, why in (rows or {}).items():
            eid = edition_for(G, reg, "void", f"{fid}|{season}", cid, season)
            n["honours_removed"] += G.c.execute("DELETE FROM honour WHERE eid=? AND kind IN ('champion', 'runner_up')", (eid,)).rowcount
            G.c.execute("UPDATE edition SET status='void', note=? WHERE eid=?", (why, eid))
            n["seasons"] += 1
    return n

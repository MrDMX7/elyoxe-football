"""Caps and goals for country from each men's national team's Wikipedia article («Most appearances», «Top goalscorers»;
fetched by the weekly `awards` stage): the totals of the players before FotMob, whose internationals our archive holds only
in part (Talyani: 161 caps, 52 goals, 1983–1997; the archive had 19 and 18). A player is found by his article's Wikidata
item, the way the awards loader finds him; one FotMob or another source knows merges in graph/load/people.py after this."""
import os
from graph import awards_fetch as AF
from graph.awards_wiki import intl_records


def load(G, reg, S):
    d = os.path.join(S.root, "graph", ".cache", "awards")
    if not os.path.exists(os.path.join(d, "items.json")) and S.s3:
        AF.restore(S, d)
    arts, items = AF._jload(os.path.join(d, "articles.json"), {}), AF._jload(os.path.join(d, "items.json"), {})
    n = {"teams": 0, "records": 0, "unlinked": 0}
    for t in arts.get("national") or []:
        h = AF.read_page(d, t)
        if not h:
            continue
        team = t.replace(" national football team", "")
        n["teams"] += 1
        for r in intl_records(h):
            f = items.get(r["person"]) or items.get(r["person"].replace(" ", "_")) or {}
            if not (f.get("qid") and f.get("human")):
                n["unlinked"] += 1
                continue
            pid = reg.get("player", "wikidata", f["qid"])
            if pid is None and f.get("tm_player"):
                pid = reg.get("player", "tm", str(f["tm_player"]))
                if pid is not None:
                    reg.link("player", "wikidata", f["qid"], pid)
            if pid is None:
                pid = reg.mint("player", "wikidata", f["qid"])
            G.put("player", {"pid": pid, "name": f.get("en") or r["name"], "name_ar": f.get("ar"), "born": f.get("born")}, "wikidata")
            G.xref("player", pid, "wikidata", f["qid"], "wiki-link")
            G.c.execute("INSERT OR REPLACE INTO intl_record VALUES(?, ?, ?, ?, ?, 'wikipedia')", (pid, team, r["caps"], r["goals"], r["career"]))
            n["records"] += 1
    return n

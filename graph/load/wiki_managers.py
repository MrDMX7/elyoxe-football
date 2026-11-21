"""Wikipedia's managers by spell (graph.wiki_managers' cache) on the benches nobody else filled: a club's match with no coach
whose date falls in exactly one Wikipedia spell is that manager's (src 'wiki'). It runs after FotMob, its lineups and
Transfermarkt, and only ever INSERTs OR IGNOREs, so they always win. The manager is the club's FotMob coach of the same
name when there is one (accents folded; else one coach with the same surname), else a coach of his own (key: his article)."""
import os
from collections import defaultdict
from datetime import date
from graph import wiki_managers as WM
from graph import awards_fetch as AF
from graph.load.coaches import fold


def load(G, reg, S, clubs=None):
    d = os.path.join(S.root, "graph", ".cache", "managers")
    if not os.path.isdir(os.path.join(d, "pages")) and S.s3:
        WM.restore(S, d)
    if not os.path.isdir(os.path.join(d, "pages")):
        return {"skipped": "no managers cache"}
    clubs = WM.clubs() if clubs is None else clubs
    today = date.today().isoformat()
    n = {"clubs": 0, "spells": 0, "coaches_new": 0, "coaches_linked": 0, "matches_assigned": 0, "ambiguous": 0}
    for fid, titles in clubs.items():
        tid = reg.get("team", "fotmob", fid)
        if tid is None:
            continue
        spells, seen = [], set()
        for t in titles:                           # the first article that gives spells (English, then Arabic): two pages' spells
            raw = AF.read_page(d, t)               # of one club overlap here and there, and an overlapped date is nobody's
            for s in WM.parse(raw, t.startswith("List of")) if raw else []:
                k = (fold(s["name"]), s["start"])
                if k not in seen:
                    seen.add(k)
                    spells.append(s)
            if spells and not t.startswith("List of"):
                break
        if not spells:
            continue
        n["clubs"] += 1
        n["spells"] += len(spells)
        bench = defaultdict(set)                     # the club's coaches already named by FotMob/Transfermarkt, by folded name
        for kid, nm in G.c.execute("""SELECT DISTINCT x.kid, c.name FROM match_coach x JOIN match m ON m.mid=x.mid JOIN coach c ON c.kid=x.kid
                                      WHERE (x.side='h' AND m.home=?) OR (x.side='a' AND m.away=?)""", (tid, tid)):
            bench[fold(nm)].add(kid)
        kids = {}
        for s in spells:
            me = fold(s["name"])
            if me in kids:
                continue
            hit = bench.get(me) or set()
            if not hit:
                last = me.split()[-1:]
                hit = {k for nm, ks in bench.items() if nm.split()[-1:] == last for k in ks}
            if len(hit) == 1:
                kids[me] = next(iter(hit))
                n["coaches_linked"] += 1
                continue
            key = s["title"] or me
            kid = reg.mint("coach", "wiki", key)
            arabic = any("؀" <= ch <= "ۿ" for ch in s["name"])     # read from an Arabic page: his Arabic name too
            if G.put("coach", {"kid": kid, "name": s["name"], **({"name_ar": s["name"]} if arabic else {})}, "wiki"):
                G.xref("coach", kid, "wiki", key, "wiki-native")
                n["coaches_new"] += 1
            kids[me] = kid
        add = []
        for mid, d_, side in G.c.execute("""SELECT m.mid, substr(m.date,1,10), CASE WHEN m.home=? THEN 'h' ELSE 'a' END FROM match m
                                            WHERE (m.home=? OR m.away=?) AND m.hs IS NOT NULL AND m.date IS NOT NULL
                                            AND NOT EXISTS (SELECT 1 FROM match_coach x WHERE x.mid=m.mid AND x.side=(CASE WHEN m.home=? THEN 'h' ELSE 'a' END))""",
                                         (tid, tid, tid, tid)).fetchall():
            who = {kids[fold(s["name"])] for s in spells if s["start"] <= d_ <= (s["end"] or today)}
            if len(who) == 1:
                add.append((mid, side, who.pop()))
            elif who:
                n["ambiguous"] += 1
        G.c.executemany("INSERT OR IGNORE INTO match_coach VALUES(?, ?, ?, 'wiki')", add)
        n["matches_assigned"] += len(add)
    return n

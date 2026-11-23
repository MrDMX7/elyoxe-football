"""Tifo is men's football (the owner, 23 Nov 2026: «كرة القدم النسائية ماباها»). Every women's competition or award leaves the
graph with its editions, honours, standings and games: one named so (Women, Féminin, Frauen, Ladies, Girls, Female,
Damallsvenskan…) or one whose honoured clubs are women's sides (FotMob's «هولندا (W)»). A woman with no other record then has
no profile (graph/archive_export.persons keeps the men with a record), and her award pages go with the awards."""
import re

WOMEN = re.compile(r"(?i)\b(women'?s?|womens|female|girls?|ladies|f[eé]minin\w*|femenin\w*|frauen\w*|damallsvenskan|nadeshiko|w-league)\b")
WOMENS_SIDE = re.compile(r"\(W\)|\bWomen\b|\bLadies\b|\bFemenino\b|\bFéminine?\b|\bFrauen\b")


def load(G, reg, S):
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    side = {t for t, n, a in q("SELECT tid, name, name_ar FROM team") if WOMENS_SIDE.search(f"{n or ''} {a or ''}")}
    out = set()
    for cid, name in q("SELECT cid, name FROM competition"):
        if WOMEN.search(name or "") or "(W)" in (name or ""):
            out.add(cid)
            continue
        clubs = [t for (t,) in q("""SELECT h.tid FROM honour h JOIN edition e ON e.eid=h.eid WHERE e.cid=? AND h.tid IS NOT NULL
                                    AND h.kind IN ('champion', 'runner_up')""", (cid,))]
        if clubs and sum(t in side for t in clubs) >= 0.8 * len(clubs):
            out.add(cid)
    n = {"competitions": len(out), "editions": 0, "honours": 0, "matches": 0}
    for cid in out:
        eids = [e for (e,) in q("SELECT eid FROM edition WHERE cid=?", (cid,))]
        for e in eids:
            n["honours"] += G.c.execute("DELETE FROM honour WHERE eid=?", (e,)).rowcount
            G.c.execute("DELETE FROM standing WHERE eid=?", (e,))
            for (mid,) in q("SELECT mid FROM match WHERE eid=?", (e,)):
                for t in ("event", "appearance", "match_coach", "match_award"):
                    G.c.execute(f"DELETE FROM {t} WHERE mid=?", (mid,))
                n["matches"] += G.c.execute("DELETE FROM match WHERE mid=?", (mid,)).rowcount
            G.c.execute("DELETE FROM xref WHERE type='edition' AND tifo_id=?", (e,))
            n["editions"] += G.c.execute("DELETE FROM edition WHERE eid=?", (e,)).rowcount
        G.c.execute("DELETE FROM player_season WHERE cid=?", (cid,))
        G.c.execute("DELETE FROM xref WHERE type='competition' AND tifo_id=?", (cid,))
        G.c.execute("DELETE FROM competition WHERE cid=?", (cid,))
    G.c.commit()
    return n

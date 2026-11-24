"""A game decided on penalties, held with the shoot-out inside its score (24 Nov 2026: 1,372 of Transfermarkt's, dcaribou's
table gives the kicks added to the goals: Brazil 4-3 Chile at the 2014 World Cup for a 1-1 and 3-2 on penalties). The goals of
the game are the ones its events hold: when they are level, each side scored no more than the score says and what is left over
reads as a shoot-out (3-0 … 5-4, or one apart from 6 on), the score becomes the draw and the rest the penalties, after extra
time. Never a league's matchday (a game short of events is not a shoot-out), never a game without events.
Runs before graph/load/twins.py: with the true score the record is the twin of another source's and the two become one."""
import re

SOURCES = ("tm",)
GOALS = ("goal", "penalty_goal", "own_goal")
FIRST_FIVE = {(1, 0), (2, 0), (2, 1), (3, 0), (3, 1), (3, 2), (4, 1), (4, 2), (4, 3), (5, 3), (5, 4)}
STAGE = re.compile(r"(?i)qualif|play ?-?offs?|preliminary|cup|pokal|copa|coupe|coppa|taca|beker|trophy|shield")


def shootout(a, b):
    """True when a-b (either way round) is a score a shoot-out ends on"""
    w, l = max(a, b), min(a, b)
    return (w, l) in FIRST_FIVE or (w >= 6 and w == l + 1)


def load(G, reg, S):
    c = G.c
    goals = {}
    marks = ",".join("?" * len(GOALS))
    for mid, side, n in c.execute(f"SELECT mid, side, count(*) FROM event WHERE type IN ({marks}) GROUP BY mid, side", GOALS):
        goals[(mid, side)] = n
    held = {mid for (mid,) in c.execute("SELECT DISTINCT mid FROM event")}
    fix = []
    for mid, rnd, hs, as_, name, kind in c.execute(f"""SELECT m.mid, m.round, m.hs, m.as_, c.name, c.kind FROM match m
            LEFT JOIN edition e ON e.eid=m.eid LEFT JOIN competition c ON c.cid=e.cid
            WHERE m.src IN ({",".join("?" * len(SOURCES))}) AND m.hs IS NOT NULL AND m.as_ IS NOT NULL AND m.hs != m.as_ AND m.pen_h IS NULL""", SOURCES):
        if mid not in held:
            continue
        g = goals.get((mid, "h"), 0)
        if g != goals.get((mid, "a"), 0) or hs < g or as_ < g or not shootout(hs - g, as_ - g):
            continue
        r = (rnd or "").lower()
        if "matchday" in r or (kind == "league" and r.startswith("group") and not STAGE.search(name or "")):
            continue
        fix.append((g, g, hs - g, as_ - g, mid))
    c.executemany("UPDATE match SET hs=?, as_=?, pen_h=?, pen_a=?, et=1 WHERE mid=?", fix)
    c.commit()
    return {"shootouts": len(fix)}

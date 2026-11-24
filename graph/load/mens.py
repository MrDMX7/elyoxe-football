"""Tifo is men's football (the owner, 23 Nov 2026: «كرة القدم النسائية ماباها»). Every women's competition or award leaves the
graph with its editions, honours, standings and games: one named so (Women, Féminin, Frauen, Ladies, Girls, Female,
Damallsvenskan, NWSL, Liga F, Vrouwen, Copa de la Reina, WSL…) or one whose honoured clubs are women's sides (FotMob's
«هولندا (W)»).

The women's sides and their players leave too (24 Nov 2026: no women's game was left, but 602 sides and 3,503 players were,
from FotMob's career histories and Wikidata's awards: «Arsenal» and «Ajax» stood twice, the second a squad of women, and
324 honours of the mixed awards (IFFHS, UNFP, Diamantbollen) named a woman):
  * a women's side is a record named so (Women, Ladies, Frauen, Vrouwen, Femminile, W.F.C., «(W)»…) that holds no game;
  * a woman is a player with a spell at a women's side and no game or season line of her own (a man never has such a spell;
    one with games who does keeps his record and loses the spell);
  * a record without a game whose squad is women (3 or more players, 80%) is a women's side, whatever its name (Portland
    Thorns, the second «Ajax»), and the rounds repeat until none is found."""
import re
from collections import defaultdict

WOMEN = re.compile(r"(?i)\b(women'?s?|womens|female|girls?|ladies|f[eé]minin\w*|femenin\w*|frauen|frauen-?(bundes)?liga|frauenpokal|vrouwen|damallsvenskan|nadeshiko"
                   r"|w-league|nwsl|wsl|liga f|copa de la reina)\b")
WOMENS_SIDE = re.compile(r"(?i)\(w\)|\((women|femenino|féminines?)\)|\b(women'?s?|womens|ladies|f[eé]minin(e|es|as?|o)?|femen[ií](no|na|l)"
                         r"|femminile|frauen|vrouwen|damen|kvinner|w\.f\.c\.?|wfc|lfc)\b|سيدات|النسائي|للنساء")
SQUAD, SHARE, ROUNDS = 3, 0.8, 8


def sides_and_players(c):
    """({women's sides}, {their players}) of one graph's connection (read-only), after the women's competitions left."""
    q = lambda s, p=(): c.execute(s, p).fetchall()
    plays = {t for (t,) in q("SELECT home FROM match UNION SELECT away FROM match")}
    side = {t for t, n, a in q("SELECT tid, name, name_ar FROM team") if t not in plays and WOMENS_SIDE.search(f"{n or ''} | {a or ''}")}
    seen = {p for (p,) in q("SELECT pid FROM appearance UNION SELECT pid FROM player_season")}
    at = defaultdict(set)
    for p, t in q("SELECT pid, tid FROM spell WHERE pid IS NOT NULL AND tid IS NOT NULL"):
        at[t].add(p)
    women = set()
    for _ in range(ROUNDS):
        new = {p for t in side for p in at.get(t, ()) if p not in seen} - women
        women |= new
        more = {t for t, ps in at.items() if t not in side and t not in plays and len(ps) >= SQUAD and len(ps & women) >= SHARE * len(ps)}
        side |= more
        if not new and not more:
            break
    return side, women


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
    side, women = sides_and_players(G.c)
    G.c.execute("CREATE TEMP TABLE out_t(i INTEGER PRIMARY KEY)")
    G.c.execute("CREATE TEMP TABLE out_p(i INTEGER PRIMARY KEY)")
    G.c.executemany("INSERT INTO out_t VALUES(?)", [(t,) for t in side])
    G.c.executemany("INSERT INTO out_p VALUES(?)", [(p,) for p in women])
    for table, col in (("spell", "tid"), ("honour", "tid"), ("standing", "tid"), ("player_season", "tid"), ("transfer", "from_tid"),
                       ("transfer", "to_tid"), ("match_award", "tid")):
        G.c.execute(f"DELETE FROM {table} WHERE {col} IN (SELECT i FROM out_t)")
    for table, col in (("spell", "pid"), ("transfer", "pid"), ("player_season", "pid"), ("injury", "pid"), ("intl_record", "pid"),
                       ("match_award", "pid")):
        G.c.execute(f"DELETE FROM {table} WHERE {col} IN (SELECT i FROM out_p)")
    n["honours"] += G.c.execute("DELETE FROM honour WHERE pid IN (SELECT i FROM out_p)").rowcount
    G.c.execute("UPDATE coach SET pid=NULL WHERE pid IN (SELECT i FROM out_p)")
    for t, k, tmp in (("team", "tid", "out_t"), ("player", "pid", "out_p")):
        G.c.execute(f"DELETE FROM xref WHERE type=? AND tifo_id IN (SELECT i FROM {tmp})", (t,))
        G.c.execute(f"DELETE FROM {t} WHERE {k} IN (SELECT i FROM {tmp})")
    G.c.execute("DROP TABLE out_t")
    G.c.execute("DROP TABLE out_p")
    n["sides"], n["players"] = len(side), len(women)
    G.c.commit()
    return n

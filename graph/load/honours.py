"""Edition honours from our own data (spec §7.3), before Wikipedia's (the first source of an honour keeps it):
  * top scorer: our count for an edition whose scoring matches have goal events (≥ 90%) and whose goals have their scorer
    (≥ 95%; own goals never count; ties share the rank, top 10), then the published scorers files (v1/history/scorers/<comp>: FotMob's leader lists and Transfermarkt
    since 2012), then RSSSF's Arab scorers (v1/history/arab/<code>);
  * champion and runner-up: a knockout edition's final in our matches (two legs: the aggregate; a draw we cannot decide is
    left), then rank 2 of a final table whose rank 1 is the edition's champion (so a table still being played never names
    a runner-up)."""
from collections import defaultdict
from graph.fm import norm_season
from graph.link import edition_for

GOALS = ("goal", "penalty_goal")


def _ranked(pairs, top=10):
    """[(key, n)] sorted by n desc -> [(rank, key, n)] with ties sharing a rank (1, 1, 3)."""
    out, last, rank = [], None, 0
    for i, (k, v) in enumerate(sorted(pairs, key=lambda x: (-x[1], str(x[0])))):
        if v != last:
            rank, last = i + 1, v
        if rank > top:
            break
        out.append((rank, k, v))
    return out


def _has(G, eid, kind):
    return G.c.execute("SELECT 1 FROM honour WHERE eid=? AND kind=? LIMIT 1", (eid, kind)).fetchone() is not None


def _put(G, eid, kind, rank, src, tid=None, pid=None, value=None):
    return G.c.execute("INSERT OR IGNORE INTO honour(eid, kind, rank, tid, pid, value, src) VALUES(?,?,?,?,?,?,?)",
                       (eid, kind, rank, tid, pid, value, src)).rowcount



def runner_up_from_tables(G):
    """The runner-up of an edition with none: its final table's second, when the table's first is the champion. A finished
    table only: its leader has met every other side once (Qatar 2013/14: 365Scores' table two games in). Run again by
    graph/load/settle.py once the team merges made a table's first the champion (RSSSF's «Al Ittihad», Al-Gharafa)."""
    got = 0
    for eid, champ, first, second, played, teams in G.c.execute("""SELECT h.eid, h.tid, s1.tid, s2.tid, s1.played,
                                                    (SELECT count(*) FROM standing s WHERE s.eid=h.eid AND s.grp=s1.grp) FROM honour h
                                                    JOIN standing s1 ON s1.eid=h.eid AND s1.rank=1 JOIN standing s2 ON s2.eid=h.eid AND s2.rank=2
                                                    WHERE h.kind='champion' AND h.rank=1""").fetchall():
        if played is not None and played < teams - 1:
            continue
        if champ == first and second and not _has(G, eid, "runner_up"):
            got += _put(G, eid, "runner_up", 1, "table", tid=second)
    return got

def load(G, reg, S, arab_codes=None):
    n = defaultdict(int)
    # 1. top scorers we can count
    cov = G.c.execute("""SELECT m.eid, count(*), sum(EXISTS(SELECT 1 FROM event v WHERE v.mid=m.mid AND v.type IN ('goal','penalty_goal','own_goal')))
                         FROM match m WHERE m.eid IS NOT NULL AND coalesce(m.hs,0)+coalesce(m.as_,0) > 0 GROUP BY m.eid""").fetchall()
    named = dict(G.c.execute("""SELECT m.eid, count(*) FROM event v JOIN match m ON m.mid=v.mid WHERE m.eid IS NOT NULL
                                 AND v.type IN ('goal','penalty_goal','own_goal') AND v.pid IS NOT NULL GROUP BY m.eid"""))
    goals = dict(G.c.execute("SELECT eid, sum(coalesce(hs,0)+coalesce(as_,0)) FROM match WHERE eid IS NOT NULL GROUP BY eid"))
    # only our competitions (FotMob's) hold whole seasons: one named by a Transfermarkt code («CL», «FAC») holds the games of
    # the clubs it covers, and crowned Messi top scorer of «CL 2012/2013» with 4 goals (23 Nov 2026)
    ours = {e for (e,) in G.c.execute("""SELECT e.eid FROM edition e JOIN xref x ON x.type='competition' AND x.source='fotmob'
                                         AND x.tifo_id=e.cid""")}
    for eid, total, with_ev in cov:
        if eid not in ours or total < 3 or with_ev < 0.9 * total or _has(G, eid, "top_scorer"):
            continue
        if named.get(eid, 0) < 0.95 * (goals.get(eid) or 0):     # most goals with no scorer (FotMob's old seasons: Bundesliga
            n["top_scorer_unnamed"] += 1                           # 2011/12, 495 of 875) would crown the wrong man
            continue
        rows = G.c.execute("""SELECT v.pid, count(*) FROM event v JOIN match m ON m.mid=v.mid
                              WHERE m.eid=? AND v.type IN ('goal','penalty_goal') AND v.pid IS NOT NULL GROUP BY v.pid""", (eid,)).fetchall()
        for rank, pid, g in _ranked(rows):
            n["top_scorer_own"] += _put(G, eid, "top_scorer", rank, "tifo", pid=pid, value=str(g))
    # 2. finals -> champion, runner-up
    legs = defaultdict(list)
    # a qualification competition's last round sends a team on, it crowns nobody (UCL qualifying 2026/27 «champion» Bodø/Glimt)
    for mid, eid, h, a, hs, as_, ph, pa in G.c.execute("""SELECT m.mid, m.eid, m.home, m.away, m.hs, m.as_, m.pen_h, m.pen_a FROM match m
                                                          JOIN edition e ON e.eid=m.eid LEFT JOIN competition c ON c.cid=e.cid
                                                          WHERE lower(trim(m.round)) IN ('final', 'the final', 'finals') AND m.hs IS NOT NULL
                                                          AND lower(coalesce(c.name, '')) NOT LIKE '%qualif%' ORDER BY m.date"""):
        legs[eid].append((h, a, hs, as_, ph, pa))
    for eid, ls in legs.items():
        if eid not in ours:                    # a final in a competition named by a Transfermarkt code: «بطل FAC» beside the FA Cup's
            continue
        teams = {ls[0][0], ls[0][1]}
        if len(ls) > 2 or any({x[0], x[1]} != teams for x in ls):
            continue
        goals = defaultdict(int)
        for h, a, hs, as_, ph, pa in ls:
            goals[h] += hs
            goals[a] += as_
        t1, t2 = sorted(teams)
        if goals[t1] == goals[t2]:
            h, a, hs, as_, ph, pa = ls[-1]
            if ph is None or pa is None or ph == pa:
                continue
            win = h if ph > pa else a
        else:
            win = t1 if goals[t1] > goals[t2] else t2
        lose = t2 if win == t1 else t1
        if not _has(G, eid, "champion"):
            n["champion_final"] += _put(G, eid, "champion", 1, "tifo", tid=win)
        if not _has(G, eid, "runner_up"):
            n["runner_up_final"] += _put(G, eid, "runner_up", 1, "tifo", tid=lose)
    n["runner_up_table"] += runner_up_from_tables(G)
    # 3. the published scorers files of our competitions
    for cid, fid in G.c.execute("SELECT tifo_id, source_id FROM xref WHERE type='competition' AND source='fotmob' ORDER BY tifo_id").fetchall():
        d = S.published(f"history/scorers/{fid}.json") or {}
        for season, data in sorted((d.get("seasons") or {}).items()):
            s = norm_season(season)
            eid = edition_for(G, reg, "scorers", f"{fid}|{s}", cid, s)
            if _has(G, eid, "top_scorer"):
                continue
            pairs = []
            for p, name, g in (data.get("goals") or []):
                if p:
                    pid = reg.mint("player", "fotmob", int(p))
                    G.put("player", {"pid": pid, "name": name}, "fotmob")
                else:
                    pid = reg.get("player", "scorers-name", f"{fid}|{name}") or reg.mint("player", "scorers-name", f"{fid}|{name}")
                    G.put("player", {"pid": pid, "name": name}, "fotmob")
                pairs.append((pid, int(g or 0)))
            for rank, pid, g in _ranked(pairs):
                n["top_scorer_files"] += _put(G, eid, "top_scorer", rank, "scorers", pid=pid, value=str(g))
    # 4. RSSSF's Arab scorers
    if arab_codes is None:
        try:
            from db.rsssf import COUNTRIES
            arab_codes = sorted(COUNTRIES)
        except Exception:
            arab_codes = []
    for code in arab_codes:
        d = S.published(f"history/arab/{code}.json") or {}
        if not d.get("league"):
            continue
        cid = reg.mint("competition", "fotmob", int(d["league"]))
        for s in d.get("seasons") or []:
            if not s.get("scorers") or not s.get("season"):
                continue
            eid = edition_for(G, reg, "rsssf", f"{code}|{s['season']}", cid, s["season"])
            if _has(G, eid, "top_scorer"):
                continue
            pairs = []
            for name, club, club_fid, g in s["scorers"]:
                pid = reg.get("player", "rsssf-name", f"{code}|{name}") or reg.mint("player", "rsssf-name", f"{code}|{name}")
                G.put("player", {"pid": pid, "name": name}, "rsssf")
                pairs.append((pid, int(g or 0)))
            for rank, pid, g in _ranked(pairs):
                n["top_scorer_rsssf"] += _put(G, eid, "top_scorer", rank, "rsssf", pid=pid, value=str(g))
    return dict(n)

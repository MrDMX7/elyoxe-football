"""Edition honours from our own data (spec §7.3), before Wikipedia's (the first source of an honour keeps it):
  * top scorer: our count for an edition whose scoring matches have goal events (≥ 90%; own goals never count; ties share
    the rank, top 10), then the published scorers files (v1/history/scorers/<comp>: FotMob's leader lists and Transfermarkt
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


def load(G, reg, S, arab_codes=None):
    n = defaultdict(int)
    # 1. top scorers we can count
    cov = G.c.execute("""SELECT m.eid, count(*), sum(EXISTS(SELECT 1 FROM event v WHERE v.mid=m.mid AND v.type IN ('goal','penalty_goal','own_goal')))
                         FROM match m WHERE m.eid IS NOT NULL AND coalesce(m.hs,0)+coalesce(m.as_,0) > 0 GROUP BY m.eid""").fetchall()
    for eid, total, with_ev in cov:
        if total < 3 or with_ev < 0.9 * total or _has(G, eid, "top_scorer"):
            continue
        rows = G.c.execute("""SELECT v.pid, count(*) FROM event v JOIN match m ON m.mid=v.mid
                              WHERE m.eid=? AND v.type IN ('goal','penalty_goal') AND v.pid IS NOT NULL GROUP BY v.pid""", (eid,)).fetchall()
        for rank, pid, g in _ranked(rows):
            n["top_scorer_own"] += _put(G, eid, "top_scorer", rank, "tifo", pid=pid, value=str(g))
    # 2. finals -> champion, runner-up
    legs = defaultdict(list)
    for mid, eid, h, a, hs, as_, ph, pa in G.c.execute("""SELECT mid, eid, home, away, hs, as_, pen_h, pen_a FROM match
                                                          WHERE eid IS NOT NULL AND lower(trim(round)) IN ('final', 'the final', 'finals')
                                                          AND hs IS NOT NULL ORDER BY date"""):
        legs[eid].append((h, a, hs, as_, ph, pa))
    for eid, ls in legs.items():
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
    for eid, champ, first, second in G.c.execute("""SELECT h.eid, h.tid, s1.tid, s2.tid FROM honour h
                                                    JOIN standing s1 ON s1.eid=h.eid AND s1.rank=1 JOIN standing s2 ON s2.eid=h.eid AND s2.rank=2
                                                    WHERE h.kind='champion' AND h.rank=1""").fetchall():
        if champ == first and second and not _has(G, eid, "runner_up"):
            n["runner_up_table"] += _put(G, eid, "runner_up", 1, "table", tid=second)
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

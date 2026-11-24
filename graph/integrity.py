"""What in the graph should not be there, counted (the coverage report's «Integrity»): each number is a fault a loader or a
pass let through, and each should fall to nothing. A check is a name, what it counts, and one SELECT that counts it."""
CHECKS = (
    ("same_game", "games held twice: one date, one home side, one away side",
     "SELECT count(*) FROM (SELECT 1 FROM match WHERE date IS NOT NULL AND home IS NOT NULL AND away IS NOT NULL GROUP BY date, home, away HAVING count(*) > 1)"),
    ("side_plays_itself", "games whose home side is their away side",
     "SELECT count(*) FROM match WHERE home = away"),
    ("game_without_season", "games in no edition",
     "SELECT count(*) FROM match WHERE eid IS NULL OR NOT EXISTS(SELECT 1 FROM edition e WHERE e.eid = match.eid)"),
    ("game_without_side", "games with a side that is no team's record",
     "SELECT count(*) FROM match m WHERE NOT EXISTS(SELECT 1 FROM team t WHERE t.tid = m.home) OR NOT EXISTS(SELECT 1 FROM team t WHERE t.tid = m.away)"),
    ("game_ahead_of_time", "games with a score, dated after today",
     "SELECT count(*) FROM match WHERE hs IS NOT NULL AND date > date('now', '+1 day')"),
    ("season_of_nothing", "editions with no game, honour, table or note",
     """SELECT count(*) FROM edition e WHERE e.note IS NULL AND NOT EXISTS(SELECT 1 FROM match m WHERE m.eid = e.eid)
        AND NOT EXISTS(SELECT 1 FROM honour h WHERE h.eid = e.eid) AND NOT EXISTS(SELECT 1 FROM standing s WHERE s.eid = e.eid)"""),
    ("season_without_competition", "editions of no competition",
     "SELECT count(*) FROM edition e WHERE NOT EXISTS(SELECT 1 FROM competition c WHERE c.cid = e.cid)"),
    ("two_champions", "seasons of a league or a cup with more than one champion",
     """SELECT count(*) FROM (SELECT 1 FROM honour h JOIN edition e ON e.eid = h.eid JOIN competition c ON c.cid = e.cid
        WHERE h.kind = 'champion' AND h.tid IS NOT NULL AND ifnull(c.kind, '') <> 'award' GROUP BY h.eid HAVING count(DISTINCT h.tid) > 1)"""),
    ("nameless_team", "teams without a name", "SELECT count(*) FROM team WHERE ifnull(name, '') = '' AND ifnull(name_ar, '') = ''"),
    ("nameless_player", "players without a name", "SELECT count(*) FROM player WHERE ifnull(name, '') = '' AND ifnull(name_ar, '') = ''"),
    ("nameless_competition", "competitions without a name, or named by a source's number",
     "SELECT count(*) FROM competition WHERE ifnull(name, '') = '' OR name GLOB 'FotMob [0-9]*'"),
    ("competition_of_no_kind", "competitions that are no league, cup, tournament, friendly or award",
     "SELECT count(*) FROM competition WHERE kind IS NULL"),
    ("transfer_ahead_of_time", "transfers dated more than two years ahead",
     "SELECT count(*) FROM transfer WHERE date > date('now', '+2 years')"),
    ("transfer_to_itself", "transfers from a club to the same club",
     "SELECT count(*) FROM transfer WHERE from_tid = to_tid"),
    ("born_after_playing", "players in a game dated before their birth",
     """SELECT count(DISTINCT p.pid) FROM player p JOIN appearance a ON a.pid = p.pid JOIN match m ON m.mid = a.mid
        WHERE length(p.born) = 10 AND length(m.date) >= 10 AND m.date < p.born"""),
    ("link_to_nothing", "source links to a team, player or competition that is not there",
     """SELECT (SELECT count(*) FROM xref x WHERE x.type = 'team' AND NOT EXISTS(SELECT 1 FROM team t WHERE t.tid = x.tifo_id))
             + (SELECT count(*) FROM xref x WHERE x.type = 'player' AND NOT EXISTS(SELECT 1 FROM player p WHERE p.pid = x.tifo_id))
             + (SELECT count(*) FROM xref x WHERE x.type = 'competition' AND NOT EXISTS(SELECT 1 FROM competition c WHERE c.cid = x.tifo_id))"""),
)


def compute(G):
    """{check: count}, in the order above"""
    return {name: G.c.execute(sql).fetchone()[0] for name, _, sql in CHECKS}


def markdown(found):
    out = ["## Integrity (each should be nothing)", "", "| check | what it counts | found |", "|---|---|---|"]
    out += [f"| {name} | {what} | {found.get(name, 0):,} |" for name, what, _ in CHECKS]
    return out + [""]

"""What the graph holds, per competition × edition and per entity type (spec §3.5): the report phases 2-5 start from."""
TYPES = ("team", "player", "coach", "referee", "stadium", "competition", "edition", "match")


def compute(G):
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    counts = {t: q(f"SELECT count(*) FROM {t}")[0][0] for t in TYPES + ("appearance", "event", "standing", "honour", "transfer", "spell", "player_season", "injury", "match_coach")}
    by_src = {t: dict(q(f"SELECT src, count(*) FROM {t} GROUP BY src")) for t in TYPES}
    linked = {t: dict(q("SELECT source, count(DISTINCT tifo_id) FROM xref WHERE type=? GROUP BY source", (t,))) for t in TYPES}
    arabic = {t: q(f"SELECT count(*) FROM {t} WHERE name_ar IS NOT NULL")[0][0] for t in ("team", "player", "coach", "referee", "competition")}
    born = q("SELECT count(*) FROM player WHERE born IS NOT NULL")[0][0]
    editions = q("""SELECT c.cid, coalesce(c.name_ar, c.name), e.season, count(m.mid),
          sum(m.hs IS NOT NULL),
          sum(EXISTS(SELECT 1 FROM appearance a WHERE a.mid=m.mid)),
          sum(EXISTS(SELECT 1 FROM event v WHERE v.mid=m.mid)),
          sum(EXISTS(SELECT 1 FROM appearance a WHERE a.mid=m.mid AND a.stats IS NOT NULL)),
          sum(EXISTS(SELECT 1 FROM appearance a WHERE a.mid=m.mid AND a.rating IS NOT NULL)),
          EXISTS(SELECT 1 FROM honour h WHERE h.eid=e.eid AND h.kind='champion'),
          EXISTS(SELECT 1 FROM honour h WHERE h.eid=e.eid AND h.kind='runner_up'),
          EXISTS(SELECT 1 FROM standing s WHERE s.eid=e.eid)
        FROM edition e JOIN competition c ON c.cid=e.cid LEFT JOIN match m ON m.eid=e.eid
        GROUP BY e.eid ORDER BY c.cid, e.season""")
    conflicts = q("SELECT type, field, kept_src, other_src, count(*) FROM conflict GROUP BY 1,2,3,4 ORDER BY 5 DESC")
    honours = [dict(zip(("kind", "src", "n", "editions"), r)) for r in q("SELECT kind, src, count(*), count(DISTINCT eid) FROM honour GROUP BY 1, 2 ORDER BY 1, 3 DESC")]
    awards = q("""SELECT c.name, c.name_ar, count(DISTINCT e.eid), min(e.season), max(e.season) FROM competition c JOIN edition e ON e.cid=c.cid
                  JOIN honour h ON h.eid=e.eid WHERE c.kind='award' GROUP BY c.cid ORDER BY 3 DESC""")
    return {"counts": counts, "by_src": by_src, "linked": linked, "arabic": arabic, "player_born": born,
            "editions": [dict(zip(("cid", "name", "season", "matches", "scores", "lineups", "events", "stats", "ratings", "champion", "runner_up", "table"), r)) for r in editions],
            "conflicts": [dict(zip(("type", "field", "kept_src", "other_src", "n"), r)) for r in conflicts],
            "honours": honours, "awards": [dict(zip(("name", "name_ar", "years", "first", "last"), r)) for r in awards]}


def markdown(cov, day, run=None):
    c = cov["counts"]
    out = [f"# Tifo graph coverage — {day}", ""]
    if run:
        out += [f"Built in {run.get('secs')} s. Loaders: " + ", ".join(f"{k} {'ok' if v['ok'] else 'FAILED'} ({v['secs']} s)" for k, v in run["loaders"].items()), ""]
    out += ["## Totals", "", "| table | rows | by source |", "|---|---|---|"]
    for t, n in c.items():
        out.append(f"| {t} | {n:,} | {', '.join(f'{s} {k:,}' for s, k in sorted(cov['by_src'].get(t, {}).items()))} |")
    out += ["", "## Links between sources (distinct Tifo ids with a row in xref)", "", "| type | " + " | ".join(["source", "ids"]) + " |", "|---|---|---|"]
    for t, d in cov["linked"].items():
        for s, k in sorted(d.items()):
            out.append(f"| {t} | {s} | {k:,} |")
    out += ["", f"Arabic names: " + ", ".join(f"{t} {n:,} of {c[t]:,}" for t, n in cov["arabic"].items()) + f". Players with a birth date: {cov['player_born']:,} of {c['player']:,}.", ""]
    out += ["## Editions", "", "| competition | season | matches | scores | lineups | events | player stats | ratings | champion | runner-up | table |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for e in cov["editions"]:
        yn = lambda v: "yes" if v else "—"
        out.append(f"| {e['name']} ({e['cid']}) | {e['season']} | {e['matches']} | {e['scores'] or 0} | {e['lineups'] or 0} | {e['events'] or 0} | {e['stats'] or 0} | {e['ratings'] or 0} | {yn(e['champion'])} | {yn(e['runner_up'])} | {yn(e['table'])} |")
    out += ["", "## Honours", "", "| kind | source | rows | editions |", "|---|---|---|---|"]
    out += [f"| {h['kind']} | {h['src']} | {h['n']:,} | {h['editions']:,} |" for h in cov.get("honours", [])]
    aw = cov.get("awards", [])
    out += ["", f"## Awards ({len(aw):,})", "", "| award | years | first | last |", "|---|---|---|---|"]
    out += [f"| {a['name_ar'] or a['name']} | {a['years']} | {a['first']} | {a['last']} |" for a in aw[:300]]
    out += ["", "## Conflicts", "", "| type | field | kept | other | n |", "|---|---|---|---|---|"]
    out += [f"| {x['type']} | {x['field']} | {x['kept_src']} | {x['other_src']} | {x['n']:,} |" for x in cov["conflicts"]]
    return "\n".join(out) + "\n"

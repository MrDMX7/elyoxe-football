"""The disagreements between sources that a rule settles (after every source, before the counts that read the scores). Each is
fixed in the data and taken off the conflict list; what no rule settles stays there for a person to review.

  * a shootout counted in the score: one source a draw, the other that draw plus the shootout (Transfermarkt's Croatia «5-3»
    Brazil, 2022, was 1-1 and 4-2 on penalties) or the shootout alone (FotMob's Brazil «0-2» Paraguay, 2011, was 0-0): the
    draw is the score, the difference the shootout;
  * the same score the other way round: one source had home and away swapped, the result is the same;
  * a birth date that is only a year (Wikidata's «2003-01-01» for a man born in 2003): the full date of that year."""


def _pair(s):
    try:
        h, a = str(s).split("-")
        return int(h), int(a)
    except (TypeError, ValueError):
        return None


def _shootout(d, x, pens):
    """x is the draw d plus a shootout (or the shootout alone, d being 0-0): the difference looks like one (the winner two or
    more, the two sides different), or is the shootout another source recorded."""
    diff = (x[0] - d[0], x[1] - d[1])
    if min(diff) < 0 or diff == (0, 0):
        return None
    if pens and (diff == pens or x == pens):
        return diff
    return diff if max(diff) >= 2 and diff[0] != diff[1] else None


def load(G, reg, S):
    n = {"shootout": 0, "swapped": 0, "birth_year_only": 0}
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    groups = {}
    for rowid, mid, field, kept, ksrc, other, osrc in q("SELECT rowid, tifo_id, field, kept, kept_src, other, other_src FROM conflict "
                                                       "WHERE type='match' AND field IN ('score', 'hs', 'as_')"):
        key = (mid, "score") if field == "score" else (mid, ksrc, osrc)
        groups.setdefault(key, []).append((rowid, field, kept, other))
    for key, rows in groups.items():
        mid = key[0]
        cur = q("SELECT hs, as_, pen_h, pen_a FROM match WHERE mid=?", (mid,))
        if not cur:
            continue
        hs, as_, ph, pa = cur[0]
        if key[1] == "score":
            k, o = _pair(rows[0][2]), _pair(rows[0][3])
        else:
            f = {r[1]: (r[2], r[3]) for r in rows}
            k = (int(f["hs"][0]) if "hs" in f else hs, int(f["as_"][0]) if "as_" in f else as_)
            o = (int(f["hs"][1]) if "hs" in f else hs, int(f["as_"][1]) if "as_" in f else as_)
        if not k or not o:
            continue
        done = None
        if k[0] != k[1] and o == (k[1], k[0]):
            done = "swapped"
        else:
            for d, x in ((k, o), (o, k)):
                if d[0] == d[1] and x != d:
                    sh = _shootout(d, x, (ph, pa) if ph is not None else None)
                    if sh:
                        G.c.execute("UPDATE match SET hs=?, as_=?, pen_h=coalesce(pen_h, ?), pen_a=coalesce(pen_a, ?) WHERE mid=?", (d[0], d[1], sh[0], sh[1], mid))
                        done = "shootout"
                        break
        if done:
            G.c.executemany("DELETE FROM conflict WHERE rowid=?", [(r[0],) for r in rows])
            n[done] += 1
    for rowid, pid, kept, other in q("SELECT rowid, tifo_id, kept, other FROM conflict WHERE type='player' AND field='born'"):
        a, b = str(kept or ""), str(other or "")
        for vague, full in ((a, b), (b, a)):
            if vague.endswith("-01-01") and not full.endswith("-01-01") and vague[:4] == full[:4] and len(full) >= 10:
                G.c.execute("UPDATE player SET born=? WHERE pid=?", (full[:10], pid))
                G.c.execute("DELETE FROM conflict WHERE rowid=?", (rowid,))
                n["birth_year_only"] += 1
                break
    return n

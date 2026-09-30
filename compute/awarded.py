"""Results a federation decided after the match (a forfeit: an ineligible player, a walk-off), which FotMob keeps as
played. competitions.yaml `awarded:` lists them with the decision's source; the numbers audit (db/audit.py) finds them
when 365Scores marks a result «Awarded» and FotMob doesn't (audit 2026-09-30: Al Minaa v Naft Maysan, Iraq Stars League
round 6, played 1-1, awarded 3-0 to Al Minaa by the Iraqi FA's disciplinary committee; our table had Al Minaa 2 points
short).

  * the fixture and the match file show the awarded score, status «awarded», the score played kept as `score_played`;
  * the table's two rows move from the result FotMob counted to the awarded one, and the group is ranked again by points
    (a stable sort: FotMob's own order stays among equal points); `adjusted` on the table says which results changed.
Nothing changes once FotMob shows the awarded score itself (its score then equals the decision).
"""
from sources import schema as S


def _pts(f, a):
    return 3 if f > a else 1 if f == a else 0


def apply_to_match(m, awarded):
    """One fixture or match detail -> the awarded version (a new dict), or the same object when nothing applies."""
    a = (awarded or {}).get(m.get("id")) if isinstance(m, dict) else None
    sc = m.get("score") if isinstance(m, dict) else None
    if not a or m.get("status") not in (S.FINISHED, S.AWARDED) or not sc:
        return m
    new = {"home": int(a["home"]), "away": int(a["away"])}
    if sc == new:
        return m
    return dict(m, score=new, score_played=sc, status=S.AWARDED, status_detail="AW", awarded_by=a.get("source"))


def _move(row, old, new):
    """A table row: take the result (for, against) `old` out and put `new` in."""
    if not row or row.get("played") is None:
        return
    for (f, a), sign in ((old, -1), (new, 1)):
        k = "won" if f > a else "drawn" if f == a else "lost"
        row[k] = (row.get(k) or 0) + sign
        row["gf"] = (row.get("gf") or 0) + sign * f
        row["ga"] = (row.get("ga") or 0) + sign * a
        row["pts"] = (row.get("pts") or 0) + sign * _pts(f, a)
    row["gd"] = (row.get("gf") or 0) - (row.get("ga") or 0)


def apply_to_standings(st, matches, awarded):
    """Adjust `st` (sources/fotmob.py standings) in place for the awarded matches among `matches` (FotMob's fixtures, before
    apply_to_match). Returns the list of adjustments."""
    if not st or not awarded:
        return []
    done = []
    for m in matches or []:
        a = awarded.get(m.get("id"))
        sc = m.get("score")
        if not a or m.get("status") != S.FINISHED or not sc:
            continue
        old = (sc["home"], sc["away"])
        new = (int(a["home"]), int(a["away"]))
        if old == new:
            continue
        h, w = m["home"]["id"], m["away"]["id"]
        for g in st.get("groups") or []:
            rows = g.get("rows") or []
            by = {r["team"]["id"]: r for r in rows}
            if h not in by or w not in by:
                continue
            _move(by[h], old, new)
            _move(by[w], (old[1], old[0]), (new[1], new[0]))
            for key, tid, o, n in (("home_rows", h, old, new), ("away_rows", w, (old[1], old[0]), (new[1], new[0]))):
                _move(next((r for r in g.get(key) or [] if r["team"]["id"] == tid), None), o, n)
            zones = [r.get("zone") for r in rows]
            rows.sort(key=lambda r: -(r.get("pts") or 0))
            for i, r in enumerate(rows):
                r["rank"], r["zone"] = i + 1, zones[i]
            done.append({"match": m["id"], "played": f"{old[0]}-{old[1]}", "awarded": f"{new[0]}-{new[1]}", "source": a.get("source")})
            break
    if done:
        st["adjusted"] = done
    return done

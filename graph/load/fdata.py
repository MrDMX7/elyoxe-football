"""football-data.co.uk's results files (graph/fetch.football_data: db/.cache/fdata/<div>-<yyyy>.csv, the big five 1995/96-
2009/10) fill what the archive's copies of those games lack: the half-time score (from 1995/96), the referee (the Premier League
from 2000/01) and the attendance. A club is the one the competition's games of the same day and score vote for; a game is the
competition's own of that day and those two clubs; nothing is minted (research/open-football-datasets-2026-11-22.md §2.3)."""
import csv, glob, os, re
from collections import Counter, defaultdict
from datetime import date, timedelta
from graph.link import MatchIndex

DIV = {"E0": 47, "SP1": 87, "I1": 55, "D1": 54, "F1": 53}


def _day(s):
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", str(s or "").strip())
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    y += (1900 if y > 50 else 2000) if y < 100 else 0
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def _int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def load(G, reg, S):
    files = sorted(glob.glob(os.path.join(S.db, "fdata", "*.csv")))
    if not files:
        return {"skipped": "no football-data files"}
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    n = Counter()
    fm_team = {t for (t,) in q("SELECT tifo_id FROM xref WHERE type='team' AND source='fotmob'")}
    rows = []
    for f in files:
        div = os.path.basename(f).split("-")[0]
        if div not in DIV:
            continue
        with open(f, encoding="latin-1", newline="") as fh:
            for r in csv.DictReader(fh):
                d = _day(r.get("Date"))
                hs, as_ = _int(r.get("FTHG")), _int(r.get("FTAG"))
                if d and r.get("HomeTeam") and hs is not None and as_ is not None:
                    rows.append((DIV[div], d, r["HomeTeam"].strip(), r["AwayTeam"].strip(), hs, as_, _int(r.get("HTHG")), _int(r.get("HTAG")),
                                 (r.get("Referee") or "").strip() or None, _int(r.get("Attendance"))))
    cid = {fid: reg.get("competition", "fotmob", fid) for fid in DIV.values()}
    games = defaultdict(list)
    ids = ",".join(str(c) for c in cid.values() if c) or "NULL"
    for mid, c, d, h, a, hs, as_ in q(f"""SELECT m.mid, e.cid, substr(m.date,1,10), m.home, m.away, m.hs, m.as_ FROM match m JOIN edition e ON e.eid=m.eid
                                          WHERE e.cid IN ({ids}) AND m.hs IS NOT NULL"""):
        games[(c, d)].append((mid, h, a, hs, as_))
    shift = lambda d, k: (date.fromisoformat(d) + timedelta(days=k)).isoformat()
    votes = defaultdict(Counter)
    for fid, d, hn, an, hs, as_, *_ in rows:
        for dd in (d, shift(d, -1), shift(d, 1)):
            for mid, h, a, ghs, gas in games.get((cid[fid], dd), ()):
                if (ghs, gas) == (hs, as_):
                    votes[(fid, hn)][h] += 1 + (h in fm_team)
                    votes[(fid, an)][a] += 1 + (a in fm_team)
    team = {}
    for k, c in votes.items():
        top = c.most_common(2)
        if top[0][1] >= 3 and (len(top) == 1 or top[0][1] >= 3 * top[1][1] or (top[0][0] in fm_team and top[1][0] not in fm_team)):
            team[k] = top[0][0]
    n["clubs"] = len(team)
    refs = {}
    for fid, d, hn, an, hs, as_, hth, hta, ref, att in rows:
        th, ta = team.get((fid, hn)), team.get((fid, an))
        if not th or not ta:
            n["club_unknown"] += 1
            continue
        hit = next((mid for dd in (d, shift(d, -1), shift(d, 1)) for mid, h, a, ghs, gas in games.get((cid[fid], dd), ())
                    if (h, a, ghs, gas) == (th, ta, hs, as_)), None)
        if not hit:
            n["no_game"] += 1
            continue
        if hth is not None and hta is not None:
            n["half_time"] += G.c.execute("UPDATE match SET ht_h=?, ht_a=? WHERE mid=? AND ht_h IS NULL", (hth, hta, hit)).rowcount
        if ref:
            if ref not in refs:
                got = q("SELECT rid FROM referee WHERE lower(name)=lower(?)", (ref,))
                refs[ref] = got[0][0] if len(got) == 1 else (reg.get("referee", "fdata", ref) or reg.mint("referee", "fdata", ref))
                if not got:
                    G.put("referee", {"rid": refs[ref], "name": ref}, "fdata")
            n["referee"] += G.c.execute("UPDATE match SET rid=? WHERE mid=? AND rid IS NULL", (refs[ref], hit)).rowcount
        if att:
            n["attendance"] += G.c.execute("UPDATE match SET attendance=? WHERE mid=? AND attendance IS NULL", (att, hit)).rowcount
    return dict(n)

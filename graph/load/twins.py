"""One game held twice (after the team merges, graph/load/teams.py and people): two records of one day with the same two teams
and the same score were one game the loaders could not tie while its teams were still two records (2,373 on 21 Nov: FotMob
and RSSSF, RSSSF and schochastics…). The better source's record is kept (graph.db SRC_RANK, then the fuller one); it takes
what only the other has (a round, a lineup, a man of the match), never a second copy of what it holds (no goal counted
twice). Three sources' records of one game are one the same way (FotMob's, Transfermarkt's and schochastics' of a Europa
League night: 353 on 23 Nov once graph/load/same_club.py had joined their clubs). Other scores, or two records of one source
on one day, stay as they are: two games (Argentina–Uruguay, 15 August 1916). Two cases of other scores are one game all the
same (24 Nov 2026, 92 on the finished graph):
- Transfermarkt's record with the shoot-out inside its score, where its events could not tell (a second leg is not level on
  the night: 1-0 and 4-1 on penalties held as 2-4). What it holds over the other sources' one score reads as a shoot-out won
  with three kicks or more: the score becomes theirs, the rest the penalties.
- schochastics' score of a cup night that went to extra time is the one after ninety minutes (Ludogorets 1-1 Rijeka for a
  3-1): where Transfermarkt holds up to three goals more and neither side fewer, its score is the game's, after extra time.
- two sources' records in one season of a league, the same side at home: a league plays that fixture once. The better
  source's score is kept and the other is written down as a conflict."""
from collections import defaultdict
from datetime import date
from graph.db import SRC_RANK
from graph.load.shootouts import shootout

DETAIL = ("event", "appearance", "match_coach", "match_award")


# a country and its successor, one side of a game (a national team never plays twice a day): martj42 files FR Yugoslavia's
# games as Serbia's and the Soviet Union's as Russia's, Fjelstul and FotMob keep the old names
SUCCESSORS = ({"yugoslavia", "serbia", "serbia and montenegro", "fr yugoslavia"}, {"soviet union", "russia", "ussr", "cis"},
              {"west germany", "germany", "germany fr"})


def load(G, reg, S):
    groups = defaultdict(list)
    side = {}                                  # a national team -> the first team of its successor family
    fam = {}
    for tid, name in G.c.execute("SELECT tid, lower(name) FROM team WHERE kind='national' OR kind IS NULL ORDER BY tid"):
        k = next((i for i, f in enumerate(SUCCESSORS) if name in f), None)
        if k is not None:
            side[tid] = fam.setdefault(k, tid)
    one = lambda t: side.get(t, t)
    for mid, day, h, a, hs, as_, src in G.c.execute("SELECT mid, substr(date,1,10), home, away, hs, as_, src FROM match WHERE date IS NOT NULL AND hs IS NOT NULL"):
        h, a = one(h), one(a)
        lo, hi = min(h, a), max(h, a)
        groups[(day, lo, hi)].append((mid, (hs, as_) if h == lo else (as_, hs), src))
    held = defaultdict(int)
    for t in DETAIL:
        for mid, n in G.c.execute(f"SELECT mid, count(*) FROM {t} GROUP BY mid"):
            held[mid] += n
    home = dict(G.c.execute("SELECT mid, home FROM match"))
    eid = dict(G.c.execute("SELECT mid, eid FROM match WHERE eid IS NOT NULL"))
    ours = {e for (e,) in G.c.execute("""SELECT e.eid FROM edition e JOIN xref x ON x.type='competition' AND x.source='fotmob'
                                          AND x.tifo_id=e.cid""")}               # the editions the site publishes
    pens = {mid for (mid,) in G.c.execute("SELECT mid FROM match WHERE pen_h IS NOT NULL")}
    league = {e for (e,) in G.c.execute("SELECT e.eid FROM edition e JOIN competition c ON c.cid=e.cid WHERE c.kind='league'")}
    pairs, turned, moved, twice, kicks, extra, late = [], [], [], [], [], [], []
    for (_, lo, _), ms in groups.items():
        if len(ms) < 2 or len({m[2] for m in ms}) < len(ms):
            continue
        if len({m[1] for m in ms}) > 1:
            tm, rest = [m for m in ms if m[2] == "tm"], [m for m in ms if m[2] != "tm"]
            if len(tm) == 1 and tm[0][0] not in pens and len({m[1] for m in rest}) == 1:
                (a, b), (x, y) = tm[0][1], rest[0][1]
                if a >= x and b >= y and max(a - x, b - y) >= 3 and shootout(a - x, b - y):
                    at_home = one(home[tm[0][0]]) == lo
                    kicks.append((*((x, y, a - x, b - y) if at_home else (y, x, b - y, a - x)), tm[0][0]))
                    ms = [(tm[0][0], (x, y), "tm")] + rest
                elif a >= x and b >= y and a + b - x - y <= 3 and {m[2] for m in rest} == {"sch"} and eid.get(tm[0][0]) not in league:
                    extra.append((tm[0][0],))
                    late += [((a, b) if one(home[m[0]]) == lo else (b, a)) + (m[0],) for m in rest]
                    ms = [tm[0]] + [(m[0], (a, b), m[2]) for m in rest]
        if len({m[1] for m in ms}) > 1 and not (len({eid.get(m[0]) for m in ms}) == 1 and eid.get(ms[0][0]) in league
                                               and len({one(home[m[0]]) for m in ms}) == 1):
            continue
        keep, *drops = sorted(ms, key=lambda m: (SRC_RANK.get(m[2], 9), -held.get(m[0], 0), m[0]))
        for i, drop in enumerate(drops):
            pairs.append((drop[0], keep[0]))
            twice += [(drop[0], m[0]) for m in [keep] + drops[:i]]
            if one(home[drop[0]]) != one(home[keep[0]]):
                turned.append((drop[0],))
        e = next((eid[d[0]] for d in drops if eid.get(d[0]) in ours), None)
        if e is not None and eid.get(keep[0]) not in ours:                # Transfermarkt's «FIWC» kept: the World Cup's season wins
            moved.append((e, keep[0]))
    G.c.executemany("UPDATE match SET hs=?, as_=?, pen_h=?, pen_a=?, et=1 WHERE mid=?", kicks)
    G.c.executemany("UPDATE match SET et=1 WHERE mid=?", extra)
    G.c.executemany("UPDATE match SET hs=?, as_=? WHERE mid=?", late)
    G.c.executemany("UPDATE match SET eid=? WHERE mid=?", moved)
    turn(G, turned)
    for t in DETAIL:                          # what the kept record holds already is never copied: a goal counted once
        G.c.executemany(f"DELETE FROM {t} WHERE mid=? AND EXISTS(SELECT 1 FROM {t} k WHERE k.mid=?)", twice)
    G.remap_many("match", pairs)
    return {"merged": len(pairs), "shootouts": len(kicks), "extra_time": len(extra), "days_apart": apart(G, held), "next_day": next_day(G, held)}


def turn(G, turned):
    """a record filed the other way round is turned first (its sides with it), so the merge sees no false disagreement"""
    G.c.executemany("UPDATE match SET home=away, away=home, hs=as_, as_=hs, ht_h=ht_a, ht_a=ht_h, pen_h=pen_a, pen_a=pen_h WHERE mid=?", turned)
    for t in ("event", "match_coach"):        # through «x»: match_coach holds one row a side, so h and a never swap in one pass
        for a, b in (("h", "x"), ("a", "h"), ("x", "a")):
            G.c.executemany(f"UPDATE {t} SET side='{b}' WHERE mid=? AND side='{a}'", turned)


NEAR = 3      # days between two sources' dates of one league game: the round's first day and the day it was played


def apart_pairs(c, held=None):
    """[(drop, keep, the day to keep or None)]: two sources' records of one league fixture (one season, the same side at home,
    the same score) on different days. RSSSF dates a round by its first day and files a postponed game under its round (on
    24 Nov 2026 Morocco's 2003/04 held 407 games for 16 sides, Egypt's 2007/08 335). Within NEAR days they are one game; any
    further apart only where one of the two is RSSSF's, in a season where no source holds a fixture twice (a league of three
    or four rounds, or one that ends in a play-off group, plays it again, perhaps to the same score: Brøndby 2-0 Nordsjælland
    in August 2018 and in May 2019). The day kept is the other source's when the better record is RSSSF's."""
    held = held or {}
    by, again, size = defaultdict(list), defaultdict(int), defaultdict(int)
    for mid, eid, day, h, a, hs, as_, src in c.execute(
            """SELECT m.mid, m.eid, substr(m.date,1,10), m.home, m.away, m.hs, m.as_, m.src FROM match m JOIN edition e ON e.eid=m.eid
               JOIN competition k ON k.cid=e.cid WHERE k.kind='league' AND m.date IS NOT NULL AND m.hs IS NOT NULL AND length(m.date)>=10"""):
        by[(eid, h, a)].append((mid, day, (hs, as_), src))
    for (eid, _, _), ms in by.items():
        size[eid] += 1
        again[eid] += len({m[3] for m in ms}) < len(ms)
    often = {e for e, n in again.items() if n >= max(3, size[e] // 20)}      # one or two are a source's own slip
    out = []
    for (eid, _, _), ms in by.items():
        if len({m[3] for m in ms}) < 2:
            continue
        kept = []                                  # [mid, day, score, {sources}]
        for mid, day, score, src in sorted(ms, key=lambda m: (SRC_RANK.get(m[3], 9), -held.get(m[0], 0), m[0])):
            best = None
            for k in kept:
                if k[2] != score or src in k[3]:
                    continue
                try:
                    gap = abs((date.fromisoformat(day) - date.fromisoformat(k[1])).days)
                except ValueError:
                    continue
                if (gap <= NEAR or (eid not in often and "rsssf" in k[3] | {src})) and (best is None or gap < best[0]):
                    best = (gap, k)
            if best is None:
                kept.append([mid, day, score, {src}, src])
                continue
            k = best[1]
            k[3].add(src)
            out.append((mid, k[0], day if k[4] == "rsssf" and src != "rsssf" and len(k[3]) == 2 else None))
    return out


def apart(G, held=None):
    found = apart_pairs(G.c, held)
    G.c.executemany("UPDATE match SET date=? WHERE mid=?", [(day, keep) for _, keep, day in found if day])
    twice = [(drop, keep) for drop, keep, _ in found]
    for t in DETAIL:
        G.c.executemany(f"DELETE FROM {t} WHERE mid=? AND EXISTS(SELECT 1 FROM {t} k WHERE k.mid=?)", twice)
    G.remap_many("match", twice)
    return len(found)


def next_day_pairs(c, held=None):
    """[(drop, keep, turned)]: two sources' records of one game on two days running, in any competition: the same two teams
    and the same score. One source dates a game by the day at the ground and another by the clock in Greenwich (a Copa
    Sudamericana night is the next day there: 421 of FotMob's and schochastics' on 24 Nov 2026, with the World Cup of 2014
    holding Russia-South Korea twice, martj42's and Transfermarkt's). No two sides meet two days running to the same score,
    but a source that holds both days holds two games: a record is never joined to one its own source is in already, and
    a record with a twin on either side of its day is left alone."""
    held = held or {}
    named = defaultdict(set)
    for mid, src in c.execute("SELECT tifo_id, source FROM xref WHERE type='match'"):
        named[mid].add(src)
    by = defaultdict(list)
    for mid, day, h, a, hs, as_, src in c.execute(
            "SELECT mid, substr(date,1,10), home, away, hs, as_, src FROM match WHERE date IS NOT NULL AND hs IS NOT NULL AND length(date)>=10"):
        lo = min(h, a)
        by[(lo, max(h, a))].append((mid, day, (hs, as_) if h == lo else (as_, hs), src, h))
    out = []
    for ms in by.values():
        if len({m[3] for m in ms}) < 2:
            continue
        kept = []                                  # [mid, day, score, {sources}, home]
        for mid, day, score, src, home in sorted(ms, key=lambda m: (SRC_RANK.get(m[3], 9), -held.get(m[0], 0), m[0])):
            mine = named[mid] | {src}
            try:
                near = [k for k in kept if k[2] == score and not (k[3] & mine) and abs((date.fromisoformat(day) - date.fromisoformat(k[1])).days) == 1]
            except ValueError:
                near = []
            if len(near) != 1:
                kept.append([mid, day, score, mine, home])
                continue
            near[0][3] |= mine
            out.append((mid, near[0][0], home != near[0][4]))
    return out


def next_day(G, held=None):
    found = next_day_pairs(G.c, held)
    if not found:
        return 0
    row = {mid: (eid, day, src) for mid, eid, day, src in G.c.execute("SELECT mid, eid, date, src FROM match")}
    kind = dict(G.c.execute("SELECT e.eid, c.kind FROM edition e JOIN competition c ON c.cid=e.cid"))
    ours = {e for (e,) in G.c.execute("SELECT e.eid FROM edition e JOIN xref x ON x.type='competition' AND x.source='fotmob' AND x.tifo_id=e.cid")}
    for drop, keep, _ in found:
        (de, dd, ds), (ke, _, ks) = row[drop], row[keep]
        # RSSSF's day is its round's first, and Transfermarkt's a national side's night by the clock in Europe: the other's is the game's
        if ks == "rsssf" or (ks == "tm" and ds == "martj42"):
            G.c.execute("UPDATE match SET date=? WHERE mid=?", (dd, keep))
        # FotMob filed a continental night among its friendlies: the game is the cup's; and the site's season wins (as above)
        if de is not None and ((kind.get(ke) == "friendly" and kind.get(de) not in ("friendly", None)) or (de in ours and ke not in ours)):
            G.c.execute("UPDATE match SET eid=? WHERE mid=?", (de, keep))
    turn(G, [(drop,) for drop, _, t in found if t])
    twice = [(drop, keep) for drop, keep, _ in found]
    for t in DETAIL:
        G.c.executemany(f"DELETE FROM {t} WHERE mid=? AND EXISTS(SELECT 1 FROM {t} k WHERE k.mid=?)", twice)
    G.remap_many("match", twice)
    return len(found)

"""One season of a competition is one edition (22 Nov 2026: the seasons lists held «1914» and «1913/1914», «2025» and
«2024/2025», two «2025/2026», Chile's league as Copa Sudamericana 1944-2001 and Morocco's second division in Botola 2006/07).
The last pass of the build, after every loader that makes editions:

1. games another source filed July-June go to FotMob's season whose games span their day (the Libertadores of 2020 ended in
   January 2021), else in a calendar era to their year (schochastics' Argentina «1936/1937», the Libertadores before 2010);
2. each edition's label in FotMob's form for its era: a year in a league of split seasons is the season that ended in it
   («1914» -> «1913/1914»), a July-June label in a calendar competition the year its games were played (with none: the year
   it ended in); «1936 - Copa de Honor» and «1936 Copa de Honor» are one;
3. a season from before the competition's first champion with no honour and none of FotMob's games leaves it (a predecessor
   or another league voted onto it: the Fairs Cup, Chile's league);
4. editions with one label are one: FotMob's keeps its honours of a kind and takes the kinds it lacks (a disagreeing champion
   is logged), its table, every game;
5. a league season held by two sources keeps the second one's games of its own clubs only (another division's, and the
   copies a club's second record holds, go aside), and one game RSSSF filed on its round's day (the same two clubs at the
   same ground, the same score, within a month) is one; other sources' dates are the game's own, so a game on another day
   is another game (Argentina's Copa de la Liga and its league).

A competition FotMob does not hold gets the same pass (25 Nov 2026: Libya, Sudan, Jordan, Yemen, the West Bank — champions
on one edition of a season and its games on another). There the games say «calendar» or «split» before any list does, a
season 365Scores or Wikipedia names keeps its games, and a list's year in a league of split seasons is read by its
champions (year_side): the season that began in it or the one that ended in it, or left as it is.

What leaves a competition is counted under «<name> (aside)», then dropped (23 Nov 2026: it leaked into the head-to-head pages)."""
import re
from collections import Counter, defaultdict
from datetime import date as Date
from graph.db import SRC_RANK
from graph.link import edition_for

FM = ("fotmob", "fotmob-trophy")
AUTH = FM + ("s365", "wiki")
LEAD = re.compile(r"\s*(\d{4})(?:/(\d{4}))?")
PLAIN_SPLIT = re.compile(r"(\d{4})/(\d{4})")
DETAIL = ("event", "appearance", "match_coach", "match_award")
PAIR_DAYS = 31
TOURNAMENT_GAP = 90            # days between two games of one national teams' tournament, at most
TOURNAMENT_DAYS = 60           # a tournament's first game to its last, at most (a World Cup: 32 days)
ORDINAL = re.compile(r"(\d{1,2})\s*$")   # «خليجي 9»: the 9th


def key(label):
    """«1936 - Copa de Honor» and «1936 Copa de Honor»: one label"""
    return re.sub(r"\s+", " ", re.sub(r"^(\d{4}(?:/\d{4})?)\s+-\s+", r"\1 ", str(label).strip())).lower()


def _end(label):
    m = LEAD.match(str(label))
    return int(m.group(2) or m.group(1)) if m else None


def _start(label):
    m = LEAD.match(str(label))
    return int(m.group(1)) if m else None


def era(fm, auth, year):
    """«split» or «calendar»: how FotMob names the competition's seasons around this year, else most of them, else how its
    other official lists (365Scores, Wikipedia) name those around it; None when nobody names any"""
    def near(labs):
        w = Counter()
        for lab in labs:
            m = LEAD.match(lab)
            if m:
                d = abs(int(m.group(2) or m.group(1)) - year)
                if d <= 3:
                    w["split" if m.group(2) else "calendar"] += 4 - d
        return ("split" if w["split"] >= w["calendar"] else "calendar") if w else None
    got = near(fm)
    if got:
        return got
    c = Counter("split" if LEAD.match(l).group(2) else "calendar" for l in fm if LEAD.match(l))
    if c:
        return "split" if c["split"] >= c["calendar"] else "calendar"
    return near(auth)


def played(months, year):
    """«calendar» or «split» from the games themselves, where no list names the seasons (24 Nov 2026: the Soviet league, March
    to November, sat cut at July into «1988/1989»). A calendar league rests over the new year and plays every month from May
    to August; a split one plays over the new year and rests in June or July. A league with a winter break and a summer one
    (Slovenia) does not say, nor do a few games. months: {«1988-07»: games}."""
    for reach in (1, 3):
        m = Counter()
        for ym, n in months.items():
            if abs(int(ym[:4]) - year) <= reach:
                m[int(ym[5:7])] += n
        total = sum(m.values())
        if total < 60:
            continue
        avg, winter = total / 12, m[12] + m[1]
        if winter < 0.3 * avg and min(m[5], m[6], m[7], m[8]) >= 0.5 * avg:
            return "calendar"
        if winter >= avg and min(m[6], m[7]) < 0.15 * avg:
            return "split"
        return None
    return None


def by_games(months, year):
    """how the league played around this year, where FotMob names none of its seasons: the nearest year within three whose
    games say (the earlier of two as near)"""
    for d in range(4):
        for y in (year - d, year + d):
            got = played(months, y)
            if got:
                return got
    return None


def canon(label, dates, era_at, blind=True):
    """the label in the competition's form for its era; None: a July-June label in a calendar competition with no games
    (which year it meant is settled against the seasons there are). blind: a year with no games in a league of split
    seasons is the season that ended in it — FotMob's lists say so; 365Scores' «2001» of Jamaica began in it, so without
    FotMob the label stays."""
    if re.fullmatch(r"\d{4}", label):
        y = int(label)
        if era_at(y) != "split":
            return label
        if not dates:
            return f"{y - 1}/{y}" if blind else label
        if sum(f"{y - 1}-07" <= d <= f"{y}-06" for d in dates) >= 0.9 * len(dates):
            return f"{y - 1}/{y}"
        if sum(f"{y}-07" <= d <= f"{y + 1}-06" for d in dates) >= 0.9 * len(dates):
            return f"{y}/{y + 1}"
        return label
    m = PLAIN_SPLIT.fullmatch(label)
    if m and int(m.group(2)) == int(m.group(1)) + 1 and era_at(int(m.group(2))) == "calendar":
        if not dates:
            return None
        for y in m.groups():
            if sum(d.startswith(y) for d in dates) >= 0.9 * len(dates):
                return y
    return label


class Pass:
    def __init__(self, G, reg):
        self.G, self.reg, self.q = G, reg, (lambda s, p=(): G.c.execute(s, p).fetchall())
        self.n = Counter()
        self.aside = {}

    def x(self, eid, sources):
        return bool(self.q(f"SELECT 1 FROM xref WHERE type='edition' AND tifo_id=? AND source IN ({','.join('?' * len(sources))}) LIMIT 1", (eid, *sources)))

    def edition(self, cid, fid, label):
        return edition_for(self.G, self.reg, "seasons", f"{fid}|{label}", cid, label)

    def aside_edition(self, cid, label):
        if cid not in self.aside:
            name = (self.q("SELECT name FROM competition WHERE cid=?", (cid,)) or [("?",)])[0][0]
            a = self.reg.get("competition", "seasons", f"{cid}|aside") or self.reg.mint("competition", "seasons", f"{cid}|aside")
            self.G.put("competition", {"cid": a, "name": f"{name} (aside)"}, "seasons")
            self.aside[cid] = a
        return edition_for(self.G, self.reg, "seasons-aside", f"{cid}|{label}", self.aside[cid], label)

    def empty(self, eid):
        return not any(self.q(f"SELECT 1 FROM {t} WHERE eid=? LIMIT 1", (eid,)) for t in ("match", "honour", "standing")) and \
            not self.q("SELECT 1 FROM edition WHERE eid=? AND (note IS NOT NULL OR status IS NOT NULL)", (eid,))

    def drop_edition(self, eid):
        self.G.c.execute("DELETE FROM xref WHERE type='edition' AND tifo_id=?", (eid,))
        self.G.c.execute("DELETE FROM edition WHERE eid=?", (eid,))

    def merge(self, keep, drop):
        G, q = self.G, self.q
        G.c.execute("UPDATE match SET eid=? WHERE eid=?", (keep, drop))
        if q("SELECT 1 FROM standing WHERE eid=? LIMIT 1", (keep,)):
            G.c.execute("DELETE FROM standing WHERE eid=?", (drop,))
        else:
            G.c.execute("UPDATE standing SET eid=? WHERE eid=?", (keep, drop))
        for (kind,) in q("SELECT DISTINCT kind FROM honour WHERE eid=?", (drop,)):
            mine = q("SELECT tid, pid, kid, src FROM honour WHERE eid=? AND kind=? ORDER BY rank LIMIT 1", (keep, kind))
            if not mine:
                G.c.execute("UPDATE honour SET eid=? WHERE eid=? AND kind=?", (keep, drop, kind))
                continue
            if kind in ("champion", "runner_up"):
                other = q("SELECT tid, src FROM honour WHERE eid=? AND kind=? ORDER BY rank LIMIT 1", (drop, kind))[0]
                if other[0] != mine[0][0]:
                    G.conflict("edition", keep, kind, mine[0][0], mine[0][3], other[0], other[1])
            G.c.execute("DELETE FROM honour WHERE eid=? AND kind=?", (drop, kind))
        note = q("SELECT note, status FROM edition WHERE eid=?", (drop,))
        if note and (note[0][0] or note[0][1]):
            G.c.execute("UPDATE edition SET note=coalesce(note, ?), status=coalesce(status, ?) WHERE eid=?", (note[0][0], note[0][1], keep))
        G.c.execute("UPDATE OR IGNORE xref SET tifo_id=? WHERE type='edition' AND tifo_id=?", (keep, drop))
        self.drop_edition(drop)
        self.n["merged"] += 1

    def tournaments(self, cid, fid):
        """0. a national teams' tournament is one edition however its sources name it (23 Nov 2026, the Gulf Cup: 365Scores'
        «خليجي 2» held the champion, the games sat in calendar years — the 16th, Dec 2003-Jan 2004, in «2003» and «2004» with
        the 17th of Dec 2004 — and Wikipedia's scorers under «2003/2004»: 56 seasons for 27). Games less than TOURNAMENT_GAP
        days apart are one tournament, named as FotMob names it, else by the year it began; «<name> N» is the Nth tournament
        when every one has games; «YYYY/YYYY» with no games is the one that ran over those two years."""
        q = self.q
        nat, n = q("""SELECT sum(th.kind='national' AND ta.kind='national'), count(*) FROM match m JOIN edition e ON e.eid=m.eid
                      JOIN team th ON th.tid=m.home JOIN team ta ON ta.tid=m.away WHERE e.cid=?""", (cid,))[0]
        if not n or (nat or 0) < 0.8 * n:
            return
        season = dict(q("SELECT eid, season FROM edition WHERE cid=?", (cid,)))
        runs = []
        for mid, d, eid in q("""SELECT m.mid, substr(m.date,1,10), m.eid FROM match m JOIN edition e ON e.eid=m.eid
                                WHERE e.cid=? AND m.date IS NOT NULL ORDER BY m.date, m.mid""", (cid,)):
            if runs and (Date.fromisoformat(d) - Date.fromisoformat(runs[-1][-1][1])).days <= TOURNAMENT_GAP:
                runs[-1].append((mid, d, eid))
            else:
                runs.append([(mid, d, eid)])
        # a run longer than a tournament (friendlies, qualifiers all year round) is none: the competition keeps its seasons
        if any((Date.fromisoformat(run[-1][1]) - Date.fromisoformat(run[0][1])).days > TOURNAMENT_DAYS for run in runs):
            return
        names = []
        for run in runs:
            fm = Counter(season[e] for _, _, e in run if self.x(e, FM))
            name = fm.most_common(1)[0][0] if fm else run[0][1][:4]
            names.append(name)
            to = None
            for mid, d, e in run:
                if season[e] != name and not self.x(e, FM):
                    to = to or self.edition(cid, fid, name)
                    self.G.c.execute("UPDATE match SET eid=? WHERE mid=?", (to, mid))
                    self.n["tournament_moved"] += 1
        for e in season:
            if q("SELECT 1 FROM edition WHERE eid=?", (e,)) and self.empty(e):
                self.drop_edition(e)
        gameless = [(e, s) for e, s in season.items() if q("SELECT 1 FROM edition WHERE eid=?", (e,)) and not q("SELECT 1 FROM match WHERE eid=? LIMIT 1", (e,))]
        nth = {e: int(m.group(1)) for e, s in gameless if not LEAD.match(s) and (m := ORDINAL.search(s))}
        if nth and max(nth.values()) == len(runs):
            for e, k in nth.items():
                self.G.c.execute("UPDATE edition SET season=? WHERE eid=?", (names[k - 1], e))
                self.n["tournament_ordinal"] += 1
        for e, s in gameless:
            m = PLAIN_SPLIT.fullmatch(s)
            hit = [nm for run, nm in zip(runs, names) if m and run[0][1][:4] == m.group(1) and run[-1][1][:4] == m.group(2)]
            if len(hit) == 1:
                self.G.c.execute("UPDATE edition SET season=? WHERE eid=?", (hit[0], e))
                self.n["tournament_span"] += 1

    def competition(self, cid, fid, kind):
        q = self.q
        self.tournaments(cid, fid)
        eds = q("SELECT eid, season FROM edition WHERE cid=? ORDER BY eid", (cid,))
        fm = [s for e, s in eds if self.x(e, FM)]
        auth = [s for e, s in eds if self.x(e, AUTH)]
        months = dict(q("""SELECT substr(m.date,1,7), count(*) FROM match m JOIN edition e ON e.eid=m.eid
                           WHERE e.cid=? AND length(m.date) >= 7 GROUP BY 1""", (cid,))) if kind == "league" else {}
        lead = bool(q("SELECT 1 FROM xref WHERE type='competition' AND tifo_id=? AND source='fotmob' LIMIT 1", (cid,)))
        if lead:
            era_at = lambda y: era(fm, auth, y) or played(months, y)
        else:                      # no FotMob: the games say first, 365Scores' and Wikipedia's lists where they do not
            seen = {}
            def era_at(y):
                if y not in seen:
                    seen[y] = by_games(months, y) or era((), auth, y)
                return seen[y]
        # 1. games another source filed July-June: to FotMob's season whose games span their day, else in a calendar era
        #    to their year (Argentina's league until 1990, the Libertadores, the CAF Champions League until 2017)
        span = [(lo, hi, e, s) for e, s in eds if self.x(e, FM) for lo, hi in
                q("SELECT min(substr(date,1,10)), max(substr(date,1,10)) FROM match WHERE eid=? AND src='fotmob'", (e,)) if lo]
        for eid, season in eds:
            if not PLAIN_SPLIT.fullmatch(season) or self.x(eid, FM) or (not lead and self.x(eid, AUTH)):
                continue               # without FotMob a season its official list names is that season
            moved = 0
            for mid, d in q("SELECT mid, substr(date,1,10) FROM match WHERE eid=? AND src <> 'fotmob' AND date IS NOT NULL", (eid,)):
                hit = [(e, s) for lo, hi, e, s in span if lo <= d <= hi]
                if len(hit) == 1:
                    to = hit[0][0] if hit[0][1] != season else None
                elif era_at(int(d[:4])) == "calendar":
                    to = self.edition(cid, fid, d[:4])
                else:
                    to = None
                if to and to != eid:
                    self.G.c.execute("UPDATE match SET eid=? WHERE mid=?", (to, mid))
                    moved += 1
            if moved:
                self.n["rebucketed"] += moved
                if self.empty(eid):
                    self.drop_edition(eid)
        eds = q("SELECT eid, season FROM edition WHERE cid=? ORDER BY eid", (cid,))
        # 2. labels in the competition's form
        lab = {}
        for eid, season in eds:
            dates = [d for (d,) in q("SELECT substr(date,1,7) FROM match WHERE eid=? AND date IS NOT NULL", (eid,))]
            lab[eid] = season if self.x(eid, FM) else canon(season, dates, era_at, blind=lead)
        if not lead:
            self.year_side(eds, lab, era_at)
        # FotMob's own label for a season in the other form wins: LaLiga's «1929» for schochastics' «1928/1929»
        fms = set(fm)
        for eid, v in lab.items():
            if not v or v in fms:
                continue
            m = PLAIN_SPLIT.fullmatch(v)
            if m and m.group(2) in fms:
                lab[eid] = m.group(2)
            elif re.fullmatch(r"\d{4}", v) and f"{int(v) - 1}/{v}" in fms:
                lab[eid] = f"{int(v) - 1}/{v}"
        # 3. before the first champion, with no honour and none of FotMob's games: not this competition's. A source whose own
        # record of the competition is this one (not a vote of its games) keeps its seasons: schochastics' Swiss league of
        # 1920-1993 under a champions list that starts in 1994 (24 Nov 2026: 74 seasons, 14,260 games)
        own = {s for (s,) in q("SELECT DISTINCT source FROM xref WHERE type='competition' AND tifo_id=? AND method <> 'vote'", (cid,))} - set(FM)
        champs = [_start(lab[e] or s) for e, s in eds if q("SELECT 1 FROM honour WHERE eid=? AND kind='champion' AND src <> 'tifo' LIMIT 1", (e,))]
        first = min((y for y in champs if y), default=None)
        for eid, season in eds:
            y = _start(lab[eid] or season)
            if first is None or y is None or y >= first or self.x(eid, FM) or q("SELECT 1 FROM honour WHERE eid=? LIMIT 1", (eid,)) \
                    or q("SELECT 1 FROM match WHERE eid=? AND src='fotmob' LIMIT 1", (eid,)) or not q("SELECT 1 FROM match WHERE eid=? LIMIT 1", (eid,)):
                continue
            if own and q(f"SELECT 1 FROM match WHERE eid=? AND src IN ({','.join('?' * len(own))}) LIMIT 1", (eid, *own)):
                continue
            self.G.c.execute("UPDATE match SET eid=? WHERE eid=?", (self.aside_edition(cid, season), eid))
            self.G.c.execute("DELETE FROM standing WHERE eid=?", (eid,))
            self.drop_edition(eid)
            del lab[eid]
            self.n["detached"] += 1
        # a July-June label with no games in a calendar competition: the year it ended in, else the one it began in
        known = {key(v) for v in lab.values() if v}
        for eid in [e for e, v in lab.items() if v is None]:
            y1, y2 = q("SELECT season FROM edition WHERE eid=?", (eid,))[0][0].split("/")
            lab[eid] = y2 if key(y2) in known or key(y1) not in known else y1
            if not lead:               # no list says which year: a year whose title is another club's is not it (Norway's cup,
                mine = self.champion(eid)   # «2025» Lillestrøm beside «2025/2026» Bodø/Glimt)
                free = [y for y in (y2, y1) if not mine or all(self.champion(e) in (None, mine) for e, v in lab.items() if v == y and e != eid)]
                lab[eid] = (lab[eid] if lab[eid] in free else free[0]) if free else f"{y1}/{y2}"
        # 4. one label, one edition
        groups = defaultdict(list)
        for eid, v in lab.items():
            groups[key(v)].append(eid)
        for k, es in groups.items():
            rank = lambda e: (0 if self.x(e, ("fotmob",)) else 1 if self.x(e, FM) else 2,
                              -q("SELECT count(*) FROM match WHERE eid=?", (e,))[0][0], e)
            es.sort(key=rank)
            keep = es[0]
            name = next((s for e in es for s in [q("SELECT season FROM edition WHERE eid=?", (e,))[0][0]] if self.x(e, FM)), lab[keep])
            for drop in es[1:]:
                self.merge(keep, drop)
            if q("SELECT season FROM edition WHERE eid=?", (keep,))[0][0] != name:
                self.G.c.execute("UPDATE edition SET season=? WHERE eid=?", (name, keep))
                self.n["relabelled"] += 1
            if kind == "league":
                self.strays(cid, keep, name)

    def champion(self, eid):
        got = self.q("SELECT tid FROM honour WHERE eid=? AND kind='champion' ORDER BY rank LIMIT 1", (eid,))
        return got[0][0] if got else None

    def leader(self, eid):
        """the club with most points in an edition's games"""
        pts = Counter()
        for h, a, hs, as_ in self.q("SELECT home, away, hs, as_ FROM match WHERE eid=? AND hs IS NOT NULL AND as_ IS NOT NULL", (eid,)):
            pts[h] += 3 if hs > as_ else hs == as_
            pts[a] += 3 if as_ > hs else hs == as_
        top = pts.most_common(2)
        return top[0][0] if top and (len(top) == 1 or top[0][1] > top[1][1]) else None

    def year_side(self, eds, lab, era_at):
        """without FotMob, a list's year for a July-June season is the one it ended in (365Scores' Sudan) or the one it began
        in (its Jamaica): the champions say which, each against the club that led the games of either season; a title of a
        season that has not ended yet is none, so the last year of a list is never a beginning. Two champions and twice the
        other side's decide for every such year whose season has games and no champion; else the labels stay."""
        q = self.q
        if not hasattr(self, "today"):
            self.today = q("SELECT max(substr(date,1,10)) FROM match WHERE hs IS NOT NULL")[0][0] or ""
        with_games = {v: e for e, v in lab.items() if v and q("SELECT 1 FROM match WHERE eid=? LIMIT 1", (e,))}
        titled = {v for e, v in lab.items() if v and q("SELECT 1 FROM honour WHERE eid=? AND kind='champion' LIMIT 1", (e,))}
        todo, votes = [], Counter()
        for eid, season in eds:
            if lab.get(eid) != season or not re.fullmatch(r"\d{4}", season) or era_at(int(season)) != "split" or q("SELECT 1 FROM match WHERE eid=? LIMIT 1", (eid,)):
                continue
            y = int(season)
            todo.append((eid, y))
            ch = q("SELECT tid FROM honour WHERE eid=? AND kind='champion' ORDER BY rank LIMIT 1", (eid,))
            if not ch:
                continue
            if f"{y + 1}-05" > self.today:
                votes["never_start"] += 1
            for side, name in (("end", f"{y - 1}/{y}"), ("start", f"{y}/{y + 1}")):
                e = with_games.get(name)
                if e and self.leader(e) == ch[0][0]:
                    votes[side] += 1
        if votes["never_start"]:
            votes["start"] = 0
            votes["end"] += 1
        side = next((s for s, o in (("end", "start"), ("start", "end")) if votes[s] >= 2 and votes[s] >= 2 * votes[o]), None)
        for eid, y in todo if side else ():   # onto a season with games and no champion of its own (Jamaica's «2022» is a title of its own beside «2022/2023»)
            to = f"{y - 1}/{y}" if side == "end" else f"{y}/{y + 1}"
            if to in with_games and to not in titled:
                lab[eid] = to
                self.n[f"years_{side}"] += 1

    def strays(self, cid, eid, season):
        """5. a league season held by two sources: the second one's games of its own clubs only, one game filed twice is one"""
        q = self.q
        rows = q("SELECT mid, src, home, away, hs, as_, substr(date,1,10), round FROM match WHERE eid=? AND date IS NOT NULL", (eid,))
        by = defaultdict(list)
        for r in rows:
            by[r[1]].append(r)
        if len(by) < 2:
            return
        def body(rs):
            """the clubs of a round robin (each with about as many games as the most), when the set is one: a club with
            under a quarter of the most is a misread line, not a club of the league (at most a tenth of the games)"""
            gp = Counter(t for r in rs for t in r[2:4])
            top = max(gp.values())
            b = {t: n for t, n in gp.items() if n >= 0.25 * top}
            ok = len(b) >= 4 and min(b.values()) >= 0.75 * top and sum(gp.values()) - sum(b.values()) <= 0.1 * sum(gp.values())
            return set(b) if ok else None
        cand = {s: body(by[s]) for s in by}
        cand = {s: c for s, c in cand.items() if c}
        most = max(len(v) for s, v in by.items() if s != "fotmob")
        if "fotmob" in by and (len(by["fotmob"]) >= 0.5 * most or "fotmob" in cand):     # FotMob leads where it holds the season
            main, core = "fotmob", {t for r in by["fotmob"] for t in r[2:4]}
        elif cand:                     # a few FotMob games (Iraq 2010/11: 2 of 700) do not decide whose clubs the league's are
            main = min((s for s in cand if s != "fotmob"), key=lambda s: (SRC_RANK.get(s, 9), -len(by[s])), default=None)
            if main is None:
                return
            core = cand[main]
        else:
            return
        pairs = Counter((r[2], r[3]) for r in by[main])
        once = all(n == 1 for n in pairs.values())
        # every pair home and away once: a second source's game of a pair already played is a copy (same score: one game;
        # another: a wrong one, aside) — UAE 2005/06-2009/10 kept 19 of them beside the FA's full seasons
        complete = once and len(pairs) == len(core) * (len(core) - 1)
        span = (min(r[6] for r in by[main]), max(r[6] for r in by[main]))   # inside its days only: Argentina's Copa de la Liga is another tournament
        mine = {(r[2], r[3]): r for r in by[main]}
        twins, aside = [], []
        for s, rs in by.items():
            if s == main:
                continue
            for mid, src, h, a, hs, as_, d, rnd in rs:
                if src == "fotmob":                               # FotMob's games never go aside
                    continue
                if rnd and (str(rnd).lower().startswith("play-off") or str(rnd).lower() == "test match"):
                    continue
                if h not in core or a not in core:
                    aside.append(mid)
                    continue
                k = mine.get((h, a))
                if k and complete and span[0] <= d <= span[1]:
                    (twins.append((mid, k[0])) if (k[4], k[5]) == (hs, as_) else aside.append(mid))
                elif k and (k[4], k[5]) == (hs, as_) and k[6] == d:            # the same game, another copy (three on one day)
                    twins.append((mid, k[0]))
                elif once and "rsssf" in (src, main) and k and (k[4], k[5]) == (hs, as_) and abs((Date.fromisoformat(k[6]) - Date.fromisoformat(d)).days) <= PAIR_DAYS:
                    twins.append((mid, k[0]))
        if aside:
            to = self.aside_edition(cid, season)
            self.G.c.executemany("UPDATE match SET eid=? WHERE mid=?", [(to, m) for m in aside])
            self.n["strays"] += len(aside)
        if twins:
            for t in DETAIL:                  # what the kept record holds already is never copied: a goal counted once
                self.G.c.executemany(f"DELETE FROM {t} WHERE mid=? AND EXISTS(SELECT 1 FROM {t} k WHERE k.mid=?)", twins)
            self.G.remap_many("match", twins)
            self.n["pair_twins"] += len(twins)


def load(G, reg, S):
    p = Pass(G, reg)
    for cid, fid, kind in G.c.execute("""SELECT c.cid, x.source_id, c.kind FROM competition c JOIN xref x ON x.type='competition'
                                          AND x.source='fotmob' AND x.tifo_id=c.cid ORDER BY c.cid""").fetchall():
        p.competition(cid, fid, kind)
    # a competition FotMob does not hold is one all the same (25 Nov 2026: Libya's champions sat on 365Scores' «2001/2002»
    # and its 240 games on schochastics' «2001/2002»; Sudan's on «2014» and «2014/2015»)
    for cid, kind in G.c.execute("""SELECT c.cid, c.kind FROM competition c WHERE NOT EXISTS(SELECT 1 FROM xref x WHERE x.type='competition'
                                    AND x.source='fotmob' AND x.tifo_id=c.cid) AND (SELECT count(*) FROM edition e WHERE e.cid=c.cid) > 1
                                    ORDER BY c.cid""").fetchall():
        p.competition(cid, f"c{cid}", kind)
    # what went aside leaves: copies of a real game, another division's, a predecessor's (23 Nov 2026: 67 «Pro League
    # (aside)» rows on the head-to-head pages; the profiles, coaches and clubs read every game too)
    for a in p.aside.values():
        for (eid,) in G.c.execute("SELECT eid FROM edition WHERE cid=?", (a,)).fetchall():
            for t in ("event", "appearance", "match_coach", "match_award"):
                G.c.execute(f"DELETE FROM {t} WHERE mid IN (SELECT mid FROM match WHERE eid=?)", (eid,))
            p.n["aside_dropped"] += G.c.execute("DELETE FROM match WHERE eid=?", (eid,)).rowcount
            G.c.execute("DELETE FROM standing WHERE eid=?", (eid,))
            G.c.execute("DELETE FROM honour WHERE eid=?", (eid,))
            p.drop_edition(eid)
        G.c.execute("DELETE FROM xref WHERE type='competition' AND tifo_id=?", (a,))
        G.c.execute("DELETE FROM competition WHERE cid=?", (a,))
    return dict(p.n)

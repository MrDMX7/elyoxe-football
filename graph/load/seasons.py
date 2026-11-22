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

What leaves a competition stays in the graph under «<name> (aside)», unpublished."""
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


def canon(label, dates, era_at):
    """the label in the competition's form for its era; None: a July-June label in a calendar competition with no games
    (which year it meant is settled against the seasons there are)"""
    if re.fullmatch(r"\d{4}", label):
        y = int(label)
        if era_at(y) != "split":
            return label
        if not dates:
            return f"{y - 1}/{y}"
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

    def competition(self, cid, fid, kind):
        q = self.q
        eds = q("SELECT eid, season FROM edition WHERE cid=? ORDER BY eid", (cid,))
        fm = [s for e, s in eds if self.x(e, FM)]
        auth = [s for e, s in eds if self.x(e, AUTH)]
        era_at = lambda y: era(fm, auth, y)
        # 1. games another source filed July-June: to FotMob's season whose games span their day, else in a calendar era
        #    to their year (Argentina's league until 1990, the Libertadores, the CAF Champions League until 2017)
        span = [(lo, hi, e, s) for e, s in eds if self.x(e, FM) for lo, hi in
                q("SELECT min(substr(date,1,10)), max(substr(date,1,10)) FROM match WHERE eid=? AND src='fotmob'", (e,)) if lo]
        for eid, season in eds:
            if not PLAIN_SPLIT.fullmatch(season) or self.x(eid, FM):
                continue
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
            lab[eid] = season if self.x(eid, FM) else canon(season, dates, era_at)
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
        # 3. before the first champion, with no honour and none of FotMob's games: not this competition's
        champs = [_start(lab[e] or s) for e, s in eds if q("SELECT 1 FROM honour WHERE eid=? AND kind='champion' AND src <> 'tifo' LIMIT 1", (e,))]
        first = min((y for y in champs if y), default=None)
        for eid, season in eds:
            y = _start(lab[eid] or season)
            if first is None or y is None or y >= first or self.x(eid, FM) or q("SELECT 1 FROM honour WHERE eid=? LIMIT 1", (eid,)) \
                    or q("SELECT 1 FROM match WHERE eid=? AND src='fotmob' LIMIT 1", (eid,)) or not q("SELECT 1 FROM match WHERE eid=? LIMIT 1", (eid,)):
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
        core |= {t for (t,) in q("SELECT tid FROM standing WHERE eid=?", (eid,))}
        pairs = Counter((r[2], r[3]) for r in by[main])
        once = all(n == 1 for n in pairs.values())
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
                if k and (k[4], k[5]) == (hs, as_) and k[6] == d:              # the same game, another copy (three on one day)
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
    return dict(p.n)

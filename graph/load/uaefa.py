"""The UAE FA's own record of the top flight (graph/uaefa_fetch.py: uaefa.ae/api, 2003/04-2016/17): every game with its
line-ups and benches, goals with their minute, substitutions and cards, the referee, the coaches, the ground and the
kick-off. The seasons before FotMob's (2003/04-2013/14) become whole; in FotMob's own (2014/15-) the FA fills only what
FotMob's game lacks, and the games both hold tie the FA's men to FotMob's.

  * a club: the FotMob club its games of the same day and score vote for (the league's games of any source), 3 votes and
    three times the next; else a club of the FA's own;
  * a man: FotMob's man who wore his shirt in a game both hold (2012/13 on: the FA keeps shirt numbers), twice and three
    times any other, or once with a name that agrees; else a man of the FA's own (/p/k<id>/) under the FA's Arabic short name;
  * a game: the graph's game of that day, those two clubs (another source's copy) takes the FA's detail and its rank (RSSSF's
    and schochastics' scorers give way to the FA's, FotMob's never); else a game of the FA's own. A game whose goals do not
    add up to its score keeps its score and loses its goals.
The owner, 22 Nov 2026: «الدوري الاماراتي… من بداية بداياته»."""
import gzip, json, os, re
from collections import Counter, defaultdict
from graph.link import MatchIndex, edition_for

FILE = "uaefa.json.gz"
LEAGUE = 538
OWN_FROM = "2014/2015"                       # FotMob's first UAE season: the FA fills, FotMob's game stays FotMob's
PLACEHOLDER = {("2008/2009", 1), ("2008/2009", 2), ("2010/2011", 1)}     # a «22:00» kick-off of every game: unknown
FOLD = [(r"\bmohamm?[ae]d\b|\bmuhamm?[ae]d\b", "mohamed"), (r"\babdull?ah?\b", "abdulla"), (r"\bal[\s-]+", "al"), (r"[^a-z ]", " ")]
WEAK = {"mohamed", "ahmed", "ali", "abdulla", "bin", "saeed", "salem", "khalid", "rashid", "hassan"}


def tokens(name):
    s = str(name or "").lower()
    for a, b in FOLD:
        s = re.sub(a, b, s)
    return {t for t in s.split() if len(t) >= 3}


def agree(a, b):
    """two spellings of one man: a shared name that is not one of the many (Mohamed, Ahmed, Ali)"""
    return bool((tokens(a) & tokens(b)) - WEAK)


def minute(e):
    m = re.fullmatch(r"\s*(\d+)\s*\+\s*(\d+)\s*", str(e.get("fulltime") or ""))
    if m:
        return int(m.group(1)), int(m.group(2))
    try:
        return int(e.get("time")), 0
    except (TypeError, ValueError):
        return None, 0


def clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip() or None


def people(team):
    """(player attributes, started, the record) of a side's XI and bench"""
    out = []
    for key, started in (("active", 1), ("substitute", 0)):
        for p in ((team or {}).get(key) or {}).get("player") or []:
            out.append((p.get("attributes") or {}, started, p))
    return out


def load(G, reg, S):
    f = os.path.join(S.db, FILE)
    if not os.path.exists(f):
        return {"skipped": "no uaefa.json.gz"}
    rows = [r for r in json.load(gzip.open(f, "rt", encoding="utf-8"))["matches"] if r.get("report")]
    cid = reg.get("competition", "fotmob", LEAGUE)
    if cid is None:
        return {"skipped": "no UAE league"}
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    n = Counter()
    fm_team = {t for (t,) in q("SELECT tifo_id FROM xref WHERE type='team' AND source='fotmob'")}

    def side(r, k):
        a = ((r["report"].get(k) or {}).get("attributes")) or {}
        return a, int(a["score"]) if str(a.get("score", "")).isdigit() else None

    def day(r):
        return str(r["report"]["attributes"].get("match_date") or "")[:10]

    # 1. clubs: the league's games of the same day and score vote
    league_games = defaultdict(list)
    for mid, d, h, a, hs, as_ in q("""SELECT m.mid, substr(m.date,1,10), m.home, m.away, m.hs, m.as_ FROM match m JOIN edition e ON e.eid=m.eid
                                      WHERE e.cid=? AND m.date IS NOT NULL AND m.hs IS NOT NULL""", (cid,)):
        league_games[d].append((h, a, hs, as_))
    votes = defaultdict(Counter)
    for r in rows:
        (h, hs), (a, as_) = side(r, "team1"), side(r, "team2")
        d = day(r)
        for dd in {d, _shift(d, -1), _shift(d, 1)}:
            for gh, ga, ghs, gas in league_games.get(dd, ()):
                if (ghs, gas) == (hs, as_):
                    votes[h.get("id")][gh] += 1 + (gh in fm_team)
                    votes[a.get("id")][ga] += 1 + (ga in fm_team)
    club = {}
    for k, c in votes.items():
        top = c.most_common(2)
        if top and top[0][1] >= 3 and (len(top) == 1 or top[0][1] >= 3 * top[1][1]):
            club[k] = reg.link("team", "uaefa", str(k), top[0][0]) or top[0][0]
            G.xref("team", club[k], "uaefa", str(k), "date+score-votes")
            n["clubs_voted"] += 1
    names = {}
    for r in rows:
        for k in ("team1", "team2"):
            a = side(r, k)[0]
            names[a.get("id")] = (a.get("name_en"), a.get("name_ar"))
    for k, (en, ar) in names.items():
        if k not in club:
            club[k] = reg.get("team", "uaefa", str(k)) or reg.mint("team", "uaefa", str(k))
            G.put("team", {"tid": club[k], "name": en, "name_ar": ar, "kind": "club", "country": "UAE"}, "uaefa")
            G.xref("team", club[k], "uaefa", str(k), "uaefa-native")
            n["clubs_own"] += 1
    # 2. the games: the graph's own copy of each, else the FA's
    idx = MatchIndex(G)
    ours = {e for (e,) in q("SELECT eid FROM edition WHERE cid=?", (cid,))}     # a copy in another competition is another game
    eid_of = dict(q("SELECT m.mid, m.eid FROM match m JOIN edition e ON e.eid=m.eid WHERE e.cid=?", (cid,)))
    game, theirs, claimed = {}, {}, set()          # claimed: a copy is one FA game's, never the next day's too
    for r in rows:
        (h, hs), (a, as_) = side(r, "team1"), side(r, "team2")
        th, ta, d = club[h.get("id")], club[a.get("id")], day(r)
        hit = None
        for mid, swapped in idx.candidates(d, th, ta):
            if eid_of.get(mid) not in ours or mid in claimed:
                continue
            row = q("SELECT hs, as_, src FROM match WHERE mid=?", (mid,))[0]
            if (row[0], row[1]) == ((as_, hs) if swapped else (hs, as_)) and not swapped:
                hit = (mid, row[2])
                break
        if hit:
            claimed.add(hit[0])
        game[r["fa"]] = hit[0] if hit else None
        theirs[r["fa"]] = hit[1] if hit else None
    # 3. men: FotMob's man who wore the same shirt in a game both hold
    pv = defaultdict(Counter)
    pname = {}
    for r in rows:
        mid = game[r["fa"]]
        if not mid or theirs[r["fa"]] != "fotmob":
            continue
        fm = defaultdict(dict)
        for pid, tid, shirt, nm in q("""SELECT a.pid, a.tid, a.shirt, p.name FROM appearance a JOIN player p ON p.pid=a.pid WHERE a.mid=?""", (mid,)):
            fm[tid][str(shirt or "")] = (pid, nm)
        for k in ("team1", "team2"):
            tid = club[side(r, k)[0].get("id")]
            for at, started, rec in people(r["report"].get(k)):
                no, faid = str(at.get("j_no") or "").strip(), at.get("player_id")
                pname[faid] = at.get("shortname_en") or at.get("name_en")
                got = fm[tid].get(no) if no else None
                if got:
                    pv[faid][got[0]] += 2 if agree(pname[faid], got[1]) or agree(at.get("name_en"), got[1]) else 1
    linked = {}
    for faid, c in pv.items():
        top = c.most_common(2)
        if top[0][1] >= 2 and (len(top) == 1 or top[0][1] >= 3 * top[1][1]):
            got = reg.link("player", "uaefa", str(faid), top[0][0])
            if got is not None:
                linked[faid] = got
                n["men_linked"] += 1

    def man(at):
        faid = at.get("player_id")
        if not faid:
            return None
        pid = linked.get(faid) or reg.get("player", "uaefa", str(faid))
        if pid is None:
            pid = reg.mint("player", "uaefa", str(faid))
        if not G.c.execute("SELECT 1 FROM player WHERE pid=?", (pid,)).fetchone():
            G.put("player", {"pid": pid, "name": clean(at.get("shortname_en") or at.get("name_en")),
                             "name_ar": clean(at.get("shortname_ar") or at.get("name_ar")),
                             "nationality": "UAE" if str(at.get("nationality_id")) == "1" else None}, "uaefa")
            G.xref("player", pid, "uaefa", str(faid), "uaefa-native")
            n["men_own"] += 1
        return pid

    def person(kind, rec):
        k = rec.get("person_id")
        if not k:
            return None
        i = reg.get(kind, "uaefa", str(k)) or reg.mint(kind, "uaefa", str(k))
        if not G.c.execute(f"SELECT 1 FROM {kind} WHERE {'rid' if kind == 'referee' else 'kid'}=?", (i,)).fetchone():
            row = {"name": clean(rec.get("shortname_en") or rec.get("name_en")), "name_ar": clean(rec.get("shortname_ar") or rec.get("name_ar"))}
            row["rid" if kind == "referee" else "kid"] = i
            G.put(kind, row, "uaefa")
            G.xref(kind, i, "uaefa", str(k), "uaefa-native")
        return i

    grounds = {}

    def ground(att):
        en, ar = (str(att.get("Stadium_en") or "").split(" / ")[-1].strip(), str(att.get("Stadium_ar") or "").split(" / ")[-1].strip())
        if not en:
            return None
        if en not in grounds:
            hit = q("SELECT sid FROM stadium WHERE lower(name)=lower(?)", (en,))
            grounds[en] = hit[0][0] if len(hit) == 1 else (reg.get("stadium", "uaefa", en) or reg.mint("stadium", "uaefa", en))
            if not hit:
                G.put("stadium", {"sid": grounds[en], "name": en, "name_ar": ar or None, "city": None, "country": "UAE"}, "uaefa")
        return grounds[en]

    # 4. each game's record
    for r in rows:
        att, season = r["report"]["attributes"], r["season"]
        (h, hs), (a, as_) = side(r, "team1"), side(r, "team2")
        th, ta = club[h.get("id")], club[a.get("id")]
        week = int(att["week"]) if str(att.get("week") or "").isdigit() else None
        t = str(att.get("match_time") or "")
        when = day(r)
        if re.fullmatch(r"\d{1,2}:\d{2}", t) and (season, week) not in PLACEHOLDER:
            hh, mm = map(int, t.split(":"))
            hh -= 4                                                   # the UAE's clock is UTC+4
            when = f"{_shift(day(r), -1) if hh < 0 else day(r)}T{hh % 24:02d}:{mm:02d}:00Z"
        ref = next((o for o in r["report"].get("match_official") or [] if str(o.get("title_id")) == "1"), None)
        mid, src = game[r["fa"]], theirs[r["fa"]]
        h1 = [side(r, k)[0].get("score_h1") for k in ("team1", "team2")]
        row = {"round": str(week) if week else None, "date": when, "home": th, "away": ta, "hs": hs, "as_": as_,
               "ht_h": int(h1[0]) if str(h1[0]).isdigit() and str(h1[1]).isdigit() else None,
               "ht_a": int(h1[1]) if str(h1[0]).isdigit() and str(h1[1]).isdigit() else None,
               "status": "finished", "sid": ground(att), "rid": person("referee", ref) if ref else None}
        if mid is None:
            mid = reg.get("match", "uaefa", str(r["fa"])) or reg.mint("match", "uaefa", str(r["fa"]))
            G.put("match", {"mid": mid, "eid": edition_for(G, reg, "uaefa", f"{LEAGUE}|{season}", cid, season), **row}, "uaefa")
            G.xref("match", mid, "uaefa", str(r["fa"]), "uaefa-native")
            idx.add(mid, day(r), th, ta)
            n["games_own"] += 1
        else:
            G.xref("match", mid, "uaefa", str(r["fa"]), "date+teams")
            if src != "fotmob":                    # RSSSF's or schochastics' copy: the FA's rank, detail, kick-off and season
                G.c.execute("UPDATE match SET src='uaefa', date=?, eid=? WHERE mid=?",
                            (when, edition_for(G, reg, "uaefa", f"{LEAGUE}|{season}", cid, season), mid))
                G.c.execute("DELETE FROM event WHERE mid=? AND src IN ('rsssf', 'sch')", (mid,))
                G.c.execute("DELETE FROM appearance WHERE mid=? AND src IN ('rsssf', 'sch')", (mid,))
            for k, v in row.items():                                    # what the copy lacks (FotMob's date and clubs stay)
                if v is not None and k not in ("home", "away", "hs", "as_"):
                    G.c.execute(f"UPDATE match SET {k}=? WHERE mid=? AND {k} IS NULL", (v, mid))
            n["games_joined"] += 1
        _detail(G, r, mid, th, ta, man, person, n)
    return dict(n)


def _detail(G, r, mid, th, ta, man, person, n):
    """line-ups, events and coaches, where the game holds none yet (FotMob's own stay)"""
    has_lu = G.c.execute("SELECT 1 FROM appearance WHERE mid=? LIMIT 1", (mid,)).fetchone()
    has_ev = G.c.execute("SELECT 1 FROM event WHERE mid=? LIMIT 1", (mid,)).fetchone()
    sides = {"team1": ("h", th), "team2": ("a", ta)}
    who, apps, ev = {}, [], []
    for k, (s, tid) in sides.items():
        for at, started, rec in people(r["report"].get(k)):
            pid = man(at)
            if pid is None:
                continue
            who[str(at.get("player_id"))] = (s, tid, pid)
            sin, sout = (rec.get("subs_in") or {}).get("time"), (rec.get("subs_out") or {}).get("time")
            played = 1 if started or sin or str(at.get("hasPlayed")) == "1" else 0
            mins = (int(sout) if str(sout).isdigit() else 90) if started else (90 - int(sin) if str(sin).isdigit() else (None if played else 0))
            apps.append({"mid": mid, "pid": pid, "tid": tid, "played": played, "started": started, "minutes": mins,
                         "shirt": str(at.get("j_no")).strip() if at.get("j_no") else None, "goals": 0, "yellow": 0, "red": 0, "assists": 0})
            cards = [("yellow", rec.get("ycard")), ("red", rec.get("rcard"))]
            for tp, c in cards:
                if isinstance(c, dict) and str(c.get("time") or "").isdigit():
                    ev.append([int(c["time"]), 0, tp, s, tid, pid, None])
    hl = r.get("en") or r.get("ar") or {}
    goals = []
    for e in hl.get("event") or []:
        tp = e.get("type")
        mi, ad = minute(e)
        s = "h" if str(e.get("club_dir")).upper() == "H" else "a"
        p = who.get(str(e.get("player_id")))
        if tp == "goal":
            own = p is not None and p[0] != s
            goals.append([mi, ad, "own_goal" if own else "goal", s, (p[1] if p else (th if s == "h" else ta)), p[2] if p else None, None])
        elif tp == "subs":
            pin, pout = who.get(str(e.get("in_player_id"))), p
            ev.append([mi, ad, "sub", s, th if s == "h" else ta, pin[2] if pin else None, pout[2] if pout else None])
    hs, as_ = G.c.execute("SELECT hs, as_ FROM match WHERE mid=?", (mid,)).fetchone()
    tally = Counter(g[3] for g in goals)
    if (tally["h"], tally["a"]) == (hs, as_):
        ev += goals
    elif goals:
        n["goals_not_adding_up"] += 1
    # a second yellow: the red of a man booked before it
    booked = set()
    for e in sorted(ev, key=lambda e: (e[0] or 0, e[1])):
        if e[2] == "yellow":
            booked.add(e[5])
        elif e[2] == "red" and e[5] in booked:
            e[2] = "second_yellow"
    by = {a["pid"]: a for a in apps}
    for e in ev:
        a = by.get(e[5])
        if a and e[2] == "goal":
            a["goals"] += 1
        elif a and e[2] == "yellow":
            a["yellow"] += 1
        elif a and e[2] in ("red", "second_yellow"):
            a["red"] += 1
    if not has_lu and apps:
        G.many("appearance", apps, "uaefa")
        n["line_ups"] += 1
    if not has_ev and ev:
        ev.sort(key=lambda e: (e[0] if e[0] is not None else 999, e[1]))
        G.many("event", [{"mid": mid, "seq": i, "minute": e[0], "added": e[1], "type": e[2], "side": e[3], "tid": e[4], "pid": e[5], "pid2": e[6]}
                         for i, e in enumerate(ev)], "uaefa")
        n["events"] += len(ev)
    for k, (s, tid) in sides.items():
        coach = next((o for o in ((r["report"].get(k) or {}).get("official") or []) if re.search(r"technical director|head coach|^coach$",
                      str(o.get("title_name_en") or ""), re.I)), None)
        if coach and not G.c.execute("SELECT 1 FROM match_coach WHERE mid=? AND side=?", (mid, s)).fetchone():
            G.c.execute("INSERT INTO match_coach VALUES(?,?,?,?)", (mid, s, person("coach", coach), "uaefa"))


def _shift(d, days):
    from datetime import date, timedelta
    try:
        return (date.fromisoformat(d[:10]) + timedelta(days=days)).isoformat()
    except ValueError:
        return d

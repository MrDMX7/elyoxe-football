"""The disagreements between sources that a rule settles (after every source, before the counts that read the scores). Each is
fixed in the data and taken off the conflict list; what no rule settles stays there for a person to review.

  * a shootout counted in the score: one source a draw, the other that draw plus the shootout (Transfermarkt's Croatia «5-3»
    Brazil, 2022, was 1-1 and 4-2 on penalties) or the shootout alone (FotMob's Brazil «0-2» Paraguay, 2011, was 0-0): the
    draw is the score, the difference the shootout;
  * the same score the other way round: one source had home and away swapped, the result is the same;
  * a birth date that is only a year (Wikidata's «2003-01-01» or «1983-00-00» for a man born in that year): the full date;
  * an honour's winners, the same men spelled two ways (our «bienve maranon», Wikipedia's «bienvenido maranon morejon»;
    «mabululo», «mabululu»): the names shown stay. A tie against one man, or two different surnames, stays for review."""
import re
import unicodedata

FOLD = str.maketrans({"æ": "ae", "ø": "o", "ß": "ss", "đ": "d", "ł": "l", "ı": "i"})


def _toks(s):
    s = unicodedata.normalize("NFKD", str(s).lower().translate(FOLD)).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+", s)


def _one_typo(a, b):
    """a and b differ by at most one letter changed, added or dropped."""
    if abs(len(a) - len(b)) > 1:
        return False
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    return a[i + 1:] == b[i + 1:] or a[i:] == b[i + 1:] or a[i + 1:] == b[i:]


def _same_man(a, b):
    """One man's two spellings: the same words; or the same number of words one letter apart (6+ letters); or every word of
    the shorter name (2+ words) starting a different word of the longer («bienve maranon» in «bienvenido maranon morejon»)."""
    a, b = _toks(a), _toks(b)
    if not a or not b:
        return False
    if a == b:
        return True
    s, l = sorted((a, b), key=len)
    if len(s) == len(l):
        x, y = "".join(s), "".join(l)
        return min(len(x), len(y)) >= 6 and _one_typo(x, y) and s[-1][0] == l[-1][0]
    if len(s) < 2:
        return False
    used = set()
    for t in s:
        j = next((j for j, u in enumerate(l) if j not in used and u.startswith(t)), None)
        if j is None:
            return False
        used.add(j)
    return True


def _same_men(a, b):
    A, B = [x for x in str(a).split(";") if x.strip()], [x for x in str(b).split(";") if x.strip()]
    if not A or len(A) != len(B):
        return False
    for x in A:
        m = next((y for y in B if _same_man(x, y)), None)
        if m is None:
            return False
        B.remove(m)
    return True


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


CLUB_WORDS = {"club", "athletic", "athletique", "athletico", "sporting", "sportive", "sports", "sport", "union", "association", "football",
              "fc", "sc", "ac", "cf", "cd", "de", "of", "the", "al", "el", "riadhi", "olympique", "olympic", "fk", "afc", "cs", "as", "us"}


def _initials(words):
    """«kawkab athletique club de marrakech» -> «kacm»; a first word of three letters or less is an abbreviation kept whole
    («kac marrakesh» -> «kacm»)"""
    ws = [w for w in words if w not in ("de", "of", "the")]
    return "".join(w if i == 0 and len(w) <= 3 else w[0] for i, w in enumerate(ws))


def same_club(a, b):
    """One club under two names (a league table's and Wikipedia's): one is the other's initials («kacm»), or one name's own
    words are all in the other's («raja club athletic» in «raja casablanca»); «wydad casablanca» and «wydad fes» stay two."""
    wa, wb = (a or "").lower().split(), (b or "").lower().split()
    if not wa or not wb:
        return False
    for x, y in ((wa, wb), (wb, wa)):
        if len(y) == 1 and len(y[0]) >= 3 and _initials(x) == y[0]:
            return True
    oa, ob = {w for w in wa if w not in CLUB_WORDS}, {w for w in wb if w not in CLUB_WORDS}
    return bool(oa and ob) and (oa <= ob or ob <= oa)


def load(G, reg, S):
    n = {"shootout": 0, "swapped": 0, "birth_year_only": 0, "same_names": 0, "no_such_team": 0, "extra_goals": 0, "same_club": 0}
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
            # a second leg one source scored with its shootout in it (Transfermarkt: Lille 2-1 Aston Villa 2024 «5-5»; FotMob's
            # old records: Real Madrid 2-1 Bayern 2012 «3-4»): the larger score less the smaller has a winner, who scored 3 to
            # 12 and won by 3 at most; the match keeps the smaller, the difference is its shootout
            for big, small in ((o, k), (k, o)):
                dh, da = big[0] - small[0], big[1] - small[1]
                if not done and ph is None and key[1] == "score" and min(dh, da) >= 0 and dh != da and 3 <= max(dh, da) <= 12 and abs(dh - da) <= 3:
                    G.c.execute("UPDATE match SET hs=?, as_=?, pen_h=?, pen_a=? WHERE mid=?", (small[0], small[1], dh, da, mid))
                    done = "shootout"
        if done:
            G.c.executemany("DELETE FROM conflict WHERE rowid=?", [(r[0],) for r in rows])
            n[done] += 1
    for rowid, pid, kept, other in q("SELECT rowid, tifo_id, kept, other FROM conflict WHERE type='player' AND field='born'"):
        a, b = str(kept or ""), str(other or "")
        for vague, full in ((a, b), (b, a)):
            year_only = lambda d: d.endswith("-01-01") or d[4:8] == "-00-"
            if year_only(vague) and not year_only(full) and vague[:4] == full[:4] and len(full) >= 10:
                G.c.execute("UPDATE player SET born=? WHERE pid=?", (full[:10], pid))
                G.c.execute("DELETE FROM conflict WHERE rowid=?", (rowid,))
                n["birth_year_only"] += 1
                break
    for rowid, kept, other in q("SELECT rowid, kept, other FROM conflict WHERE type='honour'"):
        if not re.search(r"\d", f"{kept}{other}") and _same_men(kept, other):    # «106908/None»: ids, not names
            G.c.execute("DELETE FROM conflict WHERE rowid=?", (rowid,))
            n["same_names"] += 1
    # one club under two names in a champion or runner-up disagreement («kawkab athletic club de marrakech» and «kacm»)
    for rowid, kept, other in q("SELECT rowid, kept, other FROM conflict WHERE type='honour' AND field IN ('champion', 'runner_up')"):
        if not re.search(r"\d", f"{kept}{other}") and same_club(kept, other):
            G.c.execute("DELETE FROM conflict WHERE rowid=?", (rowid,))
            n["same_club"] += 1
    # a champion or runner-up that is no team of ours (365Scores' women's and under-21 sides it never gave us) gives way
    # to the one we hold
    teams = {t for (t,) in q("SELECT tid FROM team")}
    for rowid, eid, field, kept, other in q("""SELECT rowid, tifo_id, field, kept, other FROM conflict
                                              WHERE type='honour' AND field IN ('champion', 'runner_up')"""):
        if str(kept).isdigit() and str(other).isdigit() and int(kept) not in teams and int(other) in teams:
            G.c.execute("UPDATE OR IGNORE honour SET tid=? WHERE eid=? AND kind=? AND tid=?", (int(other), eid, field, int(kept)))
            G.c.execute("DELETE FROM conflict WHERE rowid=?", (rowid,))
            n["no_such_team"] += 1
    # more goal events than goals: the shootout's kicks kept as goals (FotMob 2011, minute 121 on), then a goal kept twice
    # (the same minute, side and man); a match whose score holds its events is never touched
    G.c.execute("CREATE TEMP TABLE over_m AS SELECT m.mid FROM match m JOIN (SELECT mid, count(*) g FROM event WHERE type IN "
                "('goal','penalty_goal','own_goal') GROUP BY mid) e ON e.mid=m.mid WHERE e.g > coalesce(m.hs,0)+coalesce(m.as_,0)")
    n["extra_goals"] += G.c.execute("""DELETE FROM event WHERE mid IN (SELECT mid FROM over_m) AND minute >= 121
                                       AND type IN ('goal','penalty_goal','own_goal')""").rowcount
    n["extra_goals"] += G.c.execute("""DELETE FROM event WHERE mid IN (SELECT o.mid FROM over_m o JOIN match m ON m.mid=o.mid
                                       WHERE (SELECT count(*) FROM event v WHERE v.mid=o.mid AND v.type IN ('goal','penalty_goal','own_goal'))
                                       > coalesce(m.hs,0)+coalesce(m.as_,0))
                                       AND type IN ('goal','penalty_goal','own_goal') AND pid IS NOT NULL AND rowid NOT IN (
                                       SELECT min(rowid) FROM event WHERE type IN ('goal','penalty_goal','own_goal') AND pid IS NOT NULL
                                       GROUP BY mid, minute, side, pid)""").rowcount
    G.c.execute("DROP TABLE over_m")
    return n

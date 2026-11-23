"""Awards and edition honours from Wikipedia (spec §7): the tables graph/awards_fetch.py kept, read by graph/awards_wiki.py.

  * a table on one of our competitions' articles gives honours on that competition's editions: champion and runner-up,
    top scorer, best player, best young player, best goalkeeper, best coach. The first source of an edition's honour keeps
    it (our own counts, 365Scores, RSSSF and Fjelstul load before this); a different Wikipedia winner is a conflict;
  * every other table is an award: a competition of kind «award» (a page with one award table: the page; with several:
    page — section), each year an edition, the result honours «winner» with the source's rank and value;
  * «1960 Ballon d'Or» merges into the «Ballon d'Or» award;
  * a person reaches our player through his Wikidata item (the ids phase 1 holds) or his Transfermarkt id; else he is a
    player of his own from Wikidata (English and Arabic labels, birth date); a red link is a name only;
  * a winner born after the end of the season is dropped (a wrong link) and counted.
"""
import os, re, unicodedata
import yaml
from graph import awards_fetch as AF
from graph.awards_wiki import canonical, extract
from graph.link import edition_for

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERIC = re.compile(r"^(winners?|list of (winners|recipients|award winners)|recipients|award winners|results|by year|history|"
                     r"(list of )?(winners|champions) by (year|season)|)$", re.I)
YEAR_PAGE = re.compile(r"^(\d{4}(?:[–-]\d{2,4})?)\s+(.+)$")
# an award page or table of another sport gives nobody (23 Nov 2026: profiles carried «Gatorade Player of the Year — Track and
# field», US high-school awards). Women's football and futsal are football: their awards stay
NOT_OURS = re.compile(r"(?i)\b(gatorade|basketball|track and field|baseball|softball|volleyball|hockey|rugby|cricket|lacrosse|swimming|"
                      r"tennis|golf|wrestling|cross country|athletics|american football|handball|netball)\b")
HONOUR = {"top_scorer": "top_scorer", "best_goalkeeper": "best_goalkeeper", "best_young": "best_young", "coach": "best_coach", "winner": "best_player"}


def _conf():
    try:
        return yaml.safe_load(open(os.path.join(HERE, "awards.yaml"), encoding="utf-8")) or {}
    except OSError:
        return {}


def _ar_term(section, terms):
    s = section.lower()
    for k in sorted(terms, key=len, reverse=True):
        if k in s:
            return terms[k]
    return None


def _end_year(season):
    m = re.findall(r"\d{4}", season or "")
    return int(m[-1]) if m else None


# a link to a competition or one of its seasons is never a club ("Liga" is left out: Liga Deportiva Alajuelense is a club)
NOT_A_CLUB = re.compile(r"(^|\s)(league|cup|championships?|super\s?cup|trophy)(\s|$)|^\d{4}([–-]\d{2,4})?\s", re.I)


# a winner's cell that names a competition, its sponsor's name for it or a crowd, not a man: a league's «Names» table
# (Period | Name: «Zain Iraq League») or the FA Cup's «Sponsorship» table («Emirates FA Cup»), whose «Name» column reads as
# a winner, and FIFA Fair Play 2014 «World Cup volunteers». Whole words only: Cupido and Junior Ligue are players
COMPETITION_WORD = re.compile(r"\b(leagues?|cups?|division|liga|championships?|trophy|volunteers|sponsored)\b", re.I)


PLACEHOLDER = re.compile(r"^\W*(various( players)?|tbd|tba|n/?a|not awarded|none|unknown|vacant)?\W*$", re.I)     # a cell with no man in it


NOT_A_MAN = re.compile(r"\b\d+(st|nd|rd|th)\s+title\b|^\W*[\d\s.,]+\W*$|\b(youth|reserve|u\d{2}s?)\s+team\b", re.I)   # «24th title», «7893»


def not_a_person(name):
    return bool(name and (COMPETITION_WORD.search(name) or PLACEHOLDER.match(name) or NOT_A_MAN.search(name)))


AR_LETTER = re.compile(r"[؀-ۿ]")


def clean_name(name):
    """a man's name without Wikipedia's trailing count, club or disambiguation («Lotta Schelin (2)», «Kevin Miller (footballer)»):
    one man, not one a win; an Arabic name keeps its brackets"""
    if not name or AR_LETTER.search(name):
        return name
    return re.sub(r"\s*\([^()]*\)\s*$", "", name).strip() or name


NOISE = re.compile(r"\b(club|fc|sc|cf|ac|cd|sd|afc|the|\d+)\b")


def alike(a, b):
    """Two folded names of one club or one man: equal, the same last word (a surname), or the same once Wikipedia's extras
    are gone («al shabab al arabi club 1958 2017») and close enough letter by letter («banni yas», «fc baniyas»)."""
    from difflib import SequenceMatcher
    if not (a and b):
        return False
    if a == b or a.split()[-1:] == b.split()[-1:]:
        return True
    ja, jb = "".join(NOISE.sub(" ", a).split()), "".join(NOISE.sub(" ", b).split())
    if not ja or not jb:
        return False
    if ja == jb or (min(len(ja), len(jb)) >= 6 and (ja.startswith(jb) or jb.startswith(ja))):
        return True
    return SequenceMatcher(None, ja, jb).ratio() >= 0.88


def load(G, reg, S):
    d = os.path.join(S.root, "graph", ".cache", "awards")
    if not os.path.exists(os.path.join(d, "items.json")) and S.s3:
        AF.restore(S, d)
    arts = AF._jload(os.path.join(d, "articles.json"), {})
    items = AF._jload(os.path.join(d, "items.json"), {})
    if not arts or not items:
        return {"skipped": "no awards cache"}
    conf = _conf()
    terms, names, skip = conf.get("terms") or {}, conf.get("names") or {}, set(conf.get("skip") or [])
    comp_of = {t: fid for fid, t in (arts.get("comps") or {}).items()}
    for fid, ts in (conf.get("comp_pages") or {}).items():          # a league's list articles read like its own article
        for t in ts or []:
            comp_of.setdefault(t, str(fid))
    award_pages = set(arts.get("awards") or []) - set(comp_of)
    clubs = (S.read(os.path.join(S.db, "clubs.json")) or {}).get("clubs") or {}
    club_by_qid = {c.get("qid"): int(fid) for fid, c in clubs.items() if c.get("qid") and fid.isdigit()}
    n = {"pages": 0, "not_ours": 0, "coach_players": 0, "season_pages": 0, "tables": 0, "awards": 0, "honours": 0, "edition_honours": 0, "players_new": 0, "sanity_dropped": 0, "conflicts": 0,
         "not_a_person": 0, "own_count_replaced": 0, "season_not_own": 0, "table_not_final": 0, "season_in_play": 0}
    done = set()
    import datetime
    from graph.awards_wiki import season_over
    today = datetime.date.today().isoformat()

    def it(title):
        return items.get(title) or items.get((title or "").replace(" ", "_")) or {}

    def player(title, name, page):
        f = it(title) if title else {}
        if f.get("qid") and f.get("human"):
            pid = reg.get("player", "wikidata", f["qid"])
            if pid is None and f.get("tm_player"):
                ours = reg.get("player", "tm", str(f["tm_player"]))
                if ours is not None:
                    pid = reg.link("player", "wikidata", f["qid"], ours)
            if pid is None:
                pid = reg.mint("player", "wikidata", f["qid"])
                n["players_new"] += 1
                if f.get("tm_player"):                       # the item's Transfermarkt id names him too: later data merges
                    reg.link("player", "tm", str(f["tm_player"]), pid)
            if ("p", pid) not in done:
                done.add(("p", pid))
                t = clean_name((title or "").replace("_", " "))
                t_ar = t[3:] if t.startswith("ar:") else None            # an Arabic article's title is his Arabic name, not «ar:…»
                G.put("player", {"pid": pid, "name": f.get("en") or t_ar or t, "name_ar": f.get("ar") or t_ar, "born": f.get("born")}, "wikidata")
                G.xref("player", pid, "wikidata", f["qid"], "wiki-link")
            return pid, f.get("born")
        if title and f.get("qid"):
            return None, None                  # a link to something that is not a person
        name = clean_name(name)
        if not_a_person(name) or (title and not_a_person(title.replace("_", " "))):      # not by competition name: «Mineiro» is both
            n["not_a_person"] += 1             # a competition's own name, never a player page nor a winner
            return None, None
        key = f"{page}|{name}"
        pid = reg.get("player", "wiki-name", key) or reg.mint("player", "wiki-name", key)
        if ("p", pid) not in done:
            done.add(("p", pid))
            G.put("player", {"pid": pid, "name": name, **({"name_ar": name} if page.startswith("ar:") else {})}, "wikidata")
        return pid, None

    def coach(title, name, page):
        f = it(title) if title else {}
        key, src = (f["qid"], "wikidata") if f.get("qid") else (f"{page}|{name}", "wiki-name")
        kid = reg.get("coach", src, key) or reg.mint("coach", src, key)
        if ("k", kid) not in done:
            done.add(("k", kid))
            G.put("coach", {"kid": kid, "name": f.get("en") or name, "name_ar": f.get("ar"), "born": f.get("born")}, "wikidata")
            if f.get("qid"):                   # (23 Nov) his item: his photo, and his playing days (below)
                G.xref("coach", kid, "wikidata", f["qid"], "wiki-link")
        return kid

    not_clubs = {(t or "").replace("_", " ") for t in list(comp_of) + list(award_pages)}

    def team(title, name=None):
        f = it(title) if title else {}
        t = (title or "").replace("_", " ")
        if not f.get("qid") or t in not_clubs or NOT_A_CLUB.search(t):
            return None                        # a competition, a season or an award never wins (UAE 1990–91 «not held» linked the league)
        tid = reg.get("team", "wikidata", f["qid"])
        if tid is None and f.get("tm_club"):
            ours = reg.get("team", "tm", str(f["tm_club"]))
            if ours is not None:
                tid = reg.link("team", "wikidata", f["qid"], ours)
        if tid is None and f["qid"] in club_by_qid:
            tid = reg.link("team", "wikidata", f["qid"], reg.mint("team", "fotmob", club_by_qid[f["qid"]]))
        if tid is None:
            tid = reg.mint("team", "wikidata", f["qid"])
            if f.get("tm_club"):
                reg.link("team", "tm", str(f["tm_club"]), tid)
        if ("t", tid) not in done:
            done.add(("t", tid))
            G.put("team", {"tid": tid, "name": f.get("en") or name, "name_ar": f.get("ar")}, "wikidata")
        return tid

    def label(tid=None, pid=None, kid=None):
        t, k = ("player", "pid") if pid else ("team", "tid") if tid else ("coach", "kid")
        r = G.c.execute(f"SELECT name FROM {t} WHERE {k}=?", (pid or tid or kid,)).fetchone()
        return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", (r[0] if r else "") or "").encode("ascii", "ignore").decode().lower()).strip()

    split = {}

    def own_label(cid, season):
        """a year's honour in a league of split seasons is the season that ended in it («2016» -> «2015/2016»): its seasons
        with matches are mostly «Y/Y+1» and it has no «2016» of its own"""
        if not re.fullmatch(r"\d{4}", str(season or "")):
            return season
        if cid not in split:
            rows = G.c.execute("SELECT e.season FROM edition e WHERE e.cid=? AND EXISTS(SELECT 1 FROM match m WHERE m.eid=e.eid)", (cid,)).fetchall()
            split[cid] = (sum("/" in r[0] for r in rows) >= 0.8 * len(rows) if rows else False, {r[0] for r in rows})
        is_split, own = split[cid]
        return f"{int(season) - 1}/{season}" if is_split and season not in own else season

    def all_ours(eid):
        """our matches are the whole season: as many as its final table played (a season with no table: never known)"""
        played = G.c.execute("SELECT sum(played) FROM standing WHERE eid=?", (eid,)).fetchone()[0]
        have = G.c.execute("SELECT count(*) FROM match WHERE eid=? AND status='finished'", (eid,)).fetchone()[0]
        return bool(played) and have >= 0.95 * played / 2

    def edition_set(eid, kind, entries):
        """One source table's honours of one kind for one edition (entries: rank, tid, pid, kid, value): written when the edition
        has none of that kind yet; else the first source keeps them, and a disagreement is logged once, only when no first-place
        name of the two lists matches (the same man is often two ids: a name-only row and a linked one)."""
        entries = [e for e in entries if any(e[1:4])]
        if not entries:
            return
        if kind in ("champion", "runner_up"):    # a season still in play has a leader, no champion (any Wikipedia table)
            se = G.c.execute("SELECT season FROM edition WHERE eid=?", (eid,)).fetchone()
            if se and not season_over(se[0], today):
                n["season_in_play"] += 1
                return
        cur = G.c.execute("SELECT rank, tid, pid, kid, src FROM honour WHERE eid=? AND kind=?", (eid, kind)).fetchall()
        if cur and kind == "top_scorer" and all(c[4] == "tifo" for c in cur) and not all_ours(eid):
            G.c.execute("DELETE FROM honour WHERE eid=? AND kind=?", (eid, kind))   # our count on part of the matches (ACL 2010: 13)
            n["own_count_replaced"] += 1
            cur = []
        if cur:
            top_m, top_t = min(e[0] for e in entries), min(c[0] for c in cur)
            mine = [label(e[1], e[2], e[3]) for e in entries if e[0] == top_m]
            theirs = [label(c[1], c[2], c[3]) for c in cur if c[0] == top_t]
            if all(mine) and not any(alike(x, y) for x in mine for y in theirs):     # an Arabic-only name folds to "": no evidence
                G.conflict("honour", eid, kind, "; ".join(theirs), cur[0][4], "; ".join(mine), "wiki")
                n["conflicts"] += 1
            return
        for rank, tid, pid, kid, value in entries:
            if G.c.execute("INSERT OR IGNORE INTO honour(eid, kind, rank, tid, pid, kid, value, src) VALUES(?,?,?,?,?,?,?,?)",
                           (eid, kind, rank, tid, pid, kid, value, "wiki")).rowcount:
                n["honours"] += 1
                n["edition_honours"] += 1

    def honour(eid, kind, rank, tid=None, pid=None, kid=None, value=None, first_wins=False):
        if first_wins:
            cur = G.c.execute("SELECT tid, pid, kid, src FROM honour WHERE eid=? AND kind=? AND rank=?", (eid, kind, rank)).fetchall()
            if cur:
                if (tid, pid, kid) not in [c[:3] for c in cur]:
                    G.conflict("honour", eid, kind, "/".join(str(x) for x in cur[0][:3]), cur[0][3], f"{tid}/{pid}/{kid}", "wiki")
                    n["conflicts"] += 1
                return
        if G.c.execute("INSERT OR IGNORE INTO honour(eid, kind, rank, tid, pid, kid, value, src) VALUES(?,?,?,?,?,?,?,?)",
                       (eid, kind, rank, tid, pid, kid, value, "wiki")).rowcount:
            n["honours"] += 1

    # a redirect («FIFA World Cup Golden Ball») serves its article's HTML: every article is read once, under its own title
    # when that title is in the lists, else under the first title that reaches it; a competition's article keeps its title
    by_canon = {}
    for page in sorted(award_pages | set(comp_of)):
        if page in skip:
            continue
        html = AF.read_page(d, page)
        if not html:
            continue
        canon = canonical(html, page)
        cur = by_canon.get(canon)
        if cur is None or page == canon or (page in comp_of and cur[0] not in comp_of):
            by_canon[canon] = (page, html)
    n["redirects"] = sum(1 for p in award_pages | set(comp_of) if AF.read_page(d, p)) - len(by_canon)
    for canon in sorted(by_canon):
        page, html = by_canon[canon]
        if page not in comp_of:
            page = canon
        if page not in comp_of and NOT_OURS.search(page):
            n["not_ours"] += 1
            continue
        n["pages"] += 1
        tables = [t for t in extract(html, page) if f"{page}|{t['section']}" not in skip and not NOT_OURS.search(t["section"])]
        m = YEAR_PAGE.match(page)
        base = m.group(2) if m and m.group(2) in award_pages else page
        fid = comp_of.get(page)
        for t in tables:
            n["tables"] += 1
            if fid:                                                       # our competition's article: edition honours
                cid = reg.mint("competition", "fotmob", int(fid))
                per = {}
                for r in t["rows"]:
                    r = dict(r, season=own_label(cid, r["season"]))
                    eid = edition_for(G, reg, "wiki", f"{fid}|{r['season']}", cid, r["season"])
                    if t["kind"] in ("champion_table", "champion"):
                        per.setdefault((eid, "champion"), []).append((1, team(r["team"], r["name"]), None, None, None))
                        if r.get("runner_up"):
                            per.setdefault((eid, "runner_up"), []).append((1, team(r["runner_up"], r.get("runner_up_name")), None, None, None))
                        continue
                    if t["kind"] == "coach":
                        per.setdefault((eid, "best_coach"), []).append((r["rank"], None, None, coach(r["person"], r["name"], page), r["value"]))
                        continue
                    if t["kind"] == "winner" and not r["person"] and re.search(r"\(\d+\)$", r["name"] or ""):
                        continue                    # «CA Casablanca (1)»: an unlinked club with its title count, not a man
                    pid, born = player(r["person"], r["name"], page)
                    if pid is None:
                        continue
                    if born and _end_year(r["season"]) and int(born[:4]) > _end_year(r["season"]):
                        n["sanity_dropped"] += 1
                        continue
                    per.setdefault((eid, HONOUR.get(t["kind"], "best_player")), []).append((r["rank"], None, pid, None, r["value"]))
                for (eid, kind), entries in per.items():
                    edition_set(eid, kind, entries)
                continue
            if t["kind"] in ("champion_table", "champion"):
                continue
            generic = GENERIC.match(t["section"].strip()) or len(tables) == 1
            key = base if generic else f"{base}|{t['section']}"
            ar_page = names.get(base) or it(base).get("ar")
            name = base if generic else f"{base} — {t['section']}"
            term = None if generic else _ar_term(t["section"], terms)
            # a section's term alone («لاعب العام») loses whose award it is: with no Arabic page name the English name stands
            name_ar = ar_page if generic else (f"{ar_page} — {term}" if ar_page and term else ar_page)
            cid = reg.get("competition", "wiki", key)
            if cid is None:
                cid = reg.mint("competition", "wiki", key)
            if ("c", cid) not in done:
                done.add(("c", cid))
                G.put("competition", {"cid": cid, "name": name, "name_ar": name_ar, "kind": "award"}, "wikidata")
                G.xref("competition", cid, "wiki", key, "wiki-page")
                if it(base).get("qid"):
                    G.xref("competition", cid, "wikidata", it(base)["qid"], "wiki-page")
                n["awards"] += 1
            for r in t["rows"]:
                eid = edition_for(G, reg, "wiki", f"{key}|{r['season']}", cid, r["season"])
                if t["kind"] == "coach":
                    honour(eid, "winner", r["rank"], kid=coach(r["person"], r["name"], page), value=r["value"])
                    continue
                pid, born = player(r["person"], r["name"], page)
                if pid is None:
                    tid = team(r["person"], r["name"])          # a club or a national team (fair play, team awards)
                    if tid:
                        honour(eid, "winner", r["rank"], tid=tid, value=r["value"])
                    continue
                if born and _end_year(r["season"]) and int(born[:4]) > _end_year(r["season"]):
                    n["sanity_dropped"] += 1
                    continue
                honour(eid, "winner", r["rank"], pid=pid, tid=team(r["team"]) if r.get("team") else None, value=r["value"])
    # a season's own article: that season's honours on its competition's edition (the first source keeps an honour)
    from graph.awards_wiki import extract_season, owner
    comp_of = {str(k): v for k, v in (arts.get("comps") or {}).items()}
    for page, fid in sorted((arts.get("seasons") or {}).items()):
        if comp_of.get(str(fid)):              # another competition's season its article links (Vydra on the Premier League) goes to its own
            own = owner(page, fid, comp_of)
            if own is None:
                n["season_not_own"] += 1
                continue
            fid = own
        html = AF.read_page(d, page)
        if not html:
            continue
        got = extract_season(html, page)
        if not got["season"] or not got["rows"]:
            continue
        n["season_pages"] += 1
        cid = reg.mint("competition", "fotmob", int(fid))
        eid = edition_for(G, reg, "wiki", f"{fid}|{got['season']}", cid, got["season"])
        per, table = {}, {}
        for r in got["rows"]:
            if r["kind"] in ("champion", "runner_up"):      # the season page's league table (awards_wiki.extract_season)
                table[r["kind"]] = team(r["team"], r["name"])
                table[r["kind"] + "_name"] = r["name"]
                continue
            if r["kind"] == "best_coach":
                per.setdefault("best_coach", []).append((1, None, None, coach(r["person"], r["name"], page), None))
                continue
            pid, born = player(r["person"], r["name"], page)
            if pid is None:
                continue
            if born and _end_year(got["season"]) and int(born[:4]) > _end_year(got["season"]):
                n["sanity_dropped"] += 1
                continue
            per.setdefault(r["kind"], []).append((r["rank"], None, pid, None, r["value"]))
        if table.get("champion") and not season_over(got["season"], today):
            n["season_in_play"] += 1               # a table of a season still in play: its leader, no champion yet
        elif table.get("champion"):                # its first must be the season's champion, else it is not the final standing
            cur = {t for (t,) in G.c.execute("SELECT tid FROM honour WHERE eid=? AND kind='champion'", (eid,))}
            from graph.load.teams import alike as club_alike     # strict: «Al-Qadsia SC» is not «Kuwait SC» (awards.alike: same last word)
            names = [nm for (nm,) in G.c.execute("SELECT t.name FROM honour h JOIN team t ON t.tid=h.tid WHERE h.eid=? AND h.kind='champion'", (eid,))]
            if cur and table["champion"] not in cur and not any(club_alike(nm or "", table["champion_name"] or "") for nm in names):
                n["table_not_final"] += 1
            else:
                if not cur:
                    per["champion"] = [(1, table["champion"], None, None, None)]
                if table.get("runner_up"):
                    per["runner_up"] = [(1, table["runner_up"], None, None, None)]
        for kind, entries in per.items():
            edition_set(eid, kind, entries)
    # a coach whose Wikidata item is one of our players' is that man: his /coach/k<id>/ links his profile (23 Nov 2026)
    for kid, qid in G.c.execute("SELECT tifo_id, source_id FROM xref WHERE type='coach' AND source='wikidata'").fetchall():
        pid = reg.get("player", "wikidata", qid)
        if pid is not None:
            n["coach_players"] += G.c.execute("UPDATE coach SET pid=? WHERE kid=? AND pid IS NULL", (pid, kid)).rowcount
    return n

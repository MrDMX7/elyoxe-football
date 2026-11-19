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
import os, re
import yaml
from graph import awards_fetch as AF
from graph.awards_wiki import canonical, extract
from graph.link import edition_for

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERIC = re.compile(r"^(winners?|list of (winners|recipients|award winners)|recipients|award winners|results|by year|history|"
                     r"(list of )?(winners|champions) by (year|season)|)$", re.I)
YEAR_PAGE = re.compile(r"^(\d{4}(?:[–-]\d{2,4})?)\s+(.+)$")
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
    award_pages = set(arts.get("awards") or [])
    clubs = (S.read(os.path.join(S.db, "clubs.json")) or {}).get("clubs") or {}
    club_by_qid = {c.get("qid"): int(fid) for fid, c in clubs.items() if c.get("qid") and fid.isdigit()}
    n = {"pages": 0, "season_pages": 0, "tables": 0, "awards": 0, "honours": 0, "edition_honours": 0, "players_new": 0, "sanity_dropped": 0, "conflicts": 0}
    done = set()

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
                G.put("player", {"pid": pid, "name": f.get("en") or (title or "").replace("_", " "), "name_ar": f.get("ar"), "born": f.get("born")}, "wikidata")
                G.xref("player", pid, "wikidata", f["qid"], "wiki-link")
            return pid, f.get("born")
        if title and f.get("qid"):
            return None, None                  # a link to something that is not a person
        key = f"{page}|{name}"
        pid = reg.get("player", "wiki-name", key) or reg.mint("player", "wiki-name", key)
        if ("p", pid) not in done:
            done.add(("p", pid))
            G.put("player", {"pid": pid, "name": name}, "wikidata")
        return pid, None

    def coach(title, name, page):
        f = it(title) if title else {}
        key, src = (f["qid"], "wikidata") if f.get("qid") else (f"{page}|{name}", "wiki-name")
        kid = reg.get("coach", src, key) or reg.mint("coach", src, key)
        if ("k", kid) not in done:
            done.add(("k", kid))
            G.put("coach", {"kid": kid, "name": f.get("en") or name, "name_ar": f.get("ar"), "born": f.get("born")}, "wikidata")
        return kid

    def team(title, name=None):
        f = it(title) if title else {}
        if not f.get("qid"):
            return None
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
        n["pages"] += 1
        tables = [t for t in extract(html, page) if f"{page}|{t['section']}" not in skip]
        m = YEAR_PAGE.match(page)
        base = m.group(2) if m and m.group(2) in award_pages else page
        fid = comp_of.get(page)
        for t in tables:
            n["tables"] += 1
            if fid:                                                       # our competition's article: edition honours
                cid = reg.mint("competition", "fotmob", int(fid))
                for r in t["rows"]:
                    eid = edition_for(G, reg, "wiki", f"{fid}|{r['season']}", cid, r["season"])
                    if t["kind"] == "champion_table":
                        honour(eid, "champion", 1, tid=team(r["team"], r["name"]), first_wins=True)
                        if r.get("runner_up"):
                            honour(eid, "runner_up", 1, tid=team(r["runner_up"], r.get("runner_up_name")), first_wins=True)
                        continue
                    if t["kind"] == "coach":
                        honour(eid, "best_coach", r["rank"], kid=coach(r["person"], r["name"], page), value=r["value"], first_wins=True)
                        continue
                    pid, born = player(r["person"], r["name"], page)
                    if pid is None:
                        continue
                    if born and _end_year(r["season"]) and int(born[:4]) > _end_year(r["season"]):
                        n["sanity_dropped"] += 1
                        continue
                    honour(eid, HONOUR.get(t["kind"], "best_player"), r["rank"], pid=pid, value=r["value"], first_wins=True)
                    n["edition_honours"] += 1
                continue
            if t["kind"] == "champion_table":
                continue
            generic = GENERIC.match(t["section"].strip()) or len(tables) == 1
            key = base if generic else f"{base}|{t['section']}"
            ar_page = names.get(base) or it(base).get("ar")
            name = base if generic else f"{base} — {t['section']}"
            term = None if generic else _ar_term(t["section"], terms)
            name_ar = ar_page if generic else (f"{ar_page} — {term}" if ar_page and term else (term or ar_page))
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
    from graph.awards_wiki import extract_season
    for page, fid in sorted((arts.get("seasons") or {}).items()):
        html = AF.read_page(d, page)
        if not html:
            continue
        got = extract_season(html, page)
        if not got["season"] or not got["rows"]:
            continue
        n["season_pages"] += 1
        cid = reg.mint("competition", "fotmob", int(fid))
        eid = edition_for(G, reg, "wiki", f"{fid}|{got['season']}", cid, got["season"])
        for r in got["rows"]:
            if r["kind"] == "best_coach":
                honour(eid, "best_coach", 1, kid=coach(r["person"], r["name"], page), first_wins=True)
                continue
            pid, born = player(r["person"], r["name"], page)
            if pid is None:
                continue
            if born and _end_year(got["season"]) and int(born[:4]) > _end_year(got["season"]):
                n["sanity_dropped"] += 1
                continue
            honour(eid, r["kind"], r["rank"], pid=pid, value=r["value"], first_wins=True)
            n["edition_honours"] += 1
    return n

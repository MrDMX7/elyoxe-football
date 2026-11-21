import gzip, json, os
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import awards
from graph.awards_fetch import _key


def L(t):
    return f'<a rel="mw:WikiLink" href="./{t}">{t}</a>'


def T(body, head="Winners"):
    return f'<html><body><section><h2>{head}</h2><table class="wikitable">{body}</table></section></body></html>'.encode()


BALLON = T('<tr><th>Year</th><th>Rank</th><th>Player</th><th>Team</th><th>Points</th></tr>'
           f'<tr><td rowspan="2">1956</td><td>1st</td><td>{L("Stanley_Matthews")}</td><td>{L("Blackpool_F.C.")}</td><td>47</td></tr>'
           f'<tr><td>2nd</td><td>{L("Alfredo_Di_Stéfano")}</td><td>Real Madrid</td><td>44</td></tr>'
           f'<tr><td>1957</td><td>1st</td><td>{L("Alfredo_Di_Stéfano")}</td><td>Real Madrid</td><td>72</td></tr>'
           f'<tr><td>1958</td><td>1st</td><td>{L("Raymond_Kopa")}</td><td>Real Madrid</td><td>71</td></tr>')
YEAR_PAGE = T('<tr><th>Year</th><th>Rank</th><th>Player</th></tr>' + ''.join(
    f'<tr><td>1960</td><td>{i}</td><td>{L(p)}</td></tr>' for i, p in ((1, "Luis_Suárez_Miramontes"), (2, "Ferenc_Puskás"), (3, "Uwe_Seeler"))), "Ranking")
UAE = (b'<html><body>'
       + T('<tr><th>Season</th><th>Champion</th><th>Runner up</th></tr>' + ''.join(
           f'<tr><td>197{i}–7{i + 1}</td><td>{L("Sharjah_FC")}</td><td>{L("Al-Ahli_Dubai")}</td></tr>' for i in range(3, 6)),
           "List of champions")[12:-14]
       + T('<tr><th>Season</th><th>Player</th><th>Club</th><th>Goals</th></tr>' + ''.join(
           f'<tr><td>197{i}–7{i + 1}</td><td>{L("Scorer_%d" % i)}</td><td>{L("Sharjah_FC")}</td><td>1{i}</td></tr>' for i in range(3, 6)),
           "Top scorers by season")[12:-14]
       + b'</body></html>')

HUMAN = {"human": True, "tm_club": None}


def item(qid, en, ar=None, born="1915-02-01", tm=None):
    return {"qid": qid, "en": en, "ar": ar, "born": born, "tm_player": tm, **HUMAN}


def mk(tmp_path, pages, items, comps=None):
    d = tmp_path / "graph" / ".cache" / "awards"
    (d / "pages").mkdir(parents=True)
    for t, h in pages.items():
        (d / "pages" / (_key(t) + ".html.gz")).write_bytes(gzip.compress(h))
    (d / "pages.json").write_text(json.dumps({t: {"fetched": "2026-11-19"} for t in pages}))
    (d / "items.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    (d / "articles.json").write_text(json.dumps({"awards": sorted(t for t in pages if t not in (comps or {}).values()), "comps": comps or {}}), encoding="utf-8")
    return Sources(str(tmp_path), mirror=str(tmp_path / "mirror"), s3=False)


ITEMS = {"Stanley_Matthews": item("Q1", "Stanley Matthews", "ستانلي ماثيوز", tm="1"),
         "Alfredo_Di_Stéfano": item("Q2", "Alfredo Di Stéfano", "ألفريدو دي ستيفانو", "1926-07-04"),
         "Raymond_Kopa": item("Q3", "Raymond Kopa", None, "1931-10-13"),
         "Blackpool_F.C.": {"qid": "Q9", "en": "Blackpool F.C.", "ar": "بلاكبول", "human": False, "born": None, "tm_player": None, "tm_club": "1181"},
         "Ballon_d'Or": {"qid": "Q166177", "en": "Ballon d'Or", "ar": "الكرة الذهبية", "human": False, "born": None, "tm_player": None, "tm_club": None}}


def test_winner_links_to_our_player_through_tm_id(tmp_path):
    S = mk(tmp_path, {"Ballon d'Or": BALLON}, ITEMS)
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    ours = reg.mint("player", "fotmob", 500)
    reg.link("player", "tm", "1", ours)
    awards.load(G, reg, S)
    cid = G.c.execute("select cid from competition where kind='award'").fetchone()[0]
    assert G.c.execute("select name, name_ar from competition where cid=?", (cid,)).fetchone() == ("Ballon d'Or", "الكرة الذهبية")
    row = G.c.execute("select h.pid, h.value from honour h join edition e on e.eid=h.eid where e.cid=? and e.season='1956' and h.rank=1", (cid,)).fetchone()
    assert row == (ours, "47") and reg.get("player", "wikidata", "Q1") == ours


def test_new_winner_gets_a_wikidata_player_with_arabic_name(tmp_path):
    S = mk(tmp_path, {"Ballon d'Or": BALLON}, ITEMS)
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    awards.load(G, reg, S)
    pid = reg.get("player", "wikidata", "Q2")
    assert G.c.execute("select name, name_ar, born, src from player where pid=?", (pid,)).fetchone() == ("Alfredo Di Stéfano", "ألفريدو دي ستيفانو", "1926-07-04", "wikidata")
    assert G.c.execute("select count(*) from honour where pid=?", (pid,)).fetchone()[0] == 2      # 2nd in 1956, 1st in 1957


def test_year_page_merges_into_its_award(tmp_path):
    items = dict(ITEMS, **{t: item(f"Q{i + 20}", t.replace("_", " "), born="1935-01-01") for i, t in enumerate(("Luis_Suárez_Miramontes", "Ferenc_Puskás", "Uwe_Seeler"))})
    S = mk(tmp_path, {"Ballon d'Or": BALLON, "1960 Ballon d'Or": YEAR_PAGE}, items)
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    awards.load(G, reg, S)
    assert G.c.execute("select count(*) from competition where kind='award'").fetchone()[0] == 1
    assert G.c.execute("select count(*) from honour h join edition e on e.eid=h.eid where e.season='1960'").fetchone()[0] == 3


def test_competition_article_gives_edition_honours(tmp_path):
    items = {"Sharjah_FC": {"qid": "Q30", "en": "Sharjah FC", "ar": "الشارقة", "human": False, "born": None, "tm_player": None, "tm_club": "7"},
             "Al-Ahli_Dubai": {"qid": "Q31", "en": "Al Ahli", "ar": None, "human": False, "born": None, "tm_player": None, "tm_club": "8"},
             **{f"Scorer_{i}": item(f"Q4{i}", f"Scorer {i}", born="1950-01-01") for i in range(3, 6)}}
    S = mk(tmp_path, {"UAE Pro League": UAE}, items, comps={"538": "UAE Pro League"})
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    lg = reg.mint("competition", "fotmob", 538)
    G.put("competition", {"cid": lg, "name": "Pro League"}, "fotmob")
    sharjah = reg.mint("team", "fotmob", 102124)
    reg.link("team", "tm", "7", sharjah)
    awards.load(G, reg, S)
    assert G.c.execute("select count(*) from competition where kind='award'").fetchone()[0] == 0
    e = G.c.execute("select eid from edition where cid=? and season='1973/1974'", (lg,)).fetchone()[0]
    got = dict(G.c.execute("select kind, coalesce(tid, pid) from honour where eid=?", (e,)).fetchall())
    assert got["champion"] == sharjah and got["runner_up"] == reg.get("team", "tm", "8") and got["top_scorer"] == reg.get("player", "wikidata", "Q43")


def test_champion_disagreement_keeps_the_first_and_logs(tmp_path):
    items = {"Sharjah_FC": {"qid": "Q30", "en": "Sharjah FC", "ar": None, "human": False, "born": None, "tm_player": None, "tm_club": "7"},
             "Al-Ahli_Dubai": {"qid": "Q31", "en": "Al Ahli", "ar": None, "human": False, "born": None, "tm_player": None, "tm_club": "8"}}
    S = mk(tmp_path, {"UAE Pro League": UAE}, items, comps={"538": "UAE Pro League"})
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    lg = reg.mint("competition", "fotmob", 538)
    e = reg.mint("edition", "s365", "549|1973/1974")
    G.put("edition", {"eid": e, "cid": lg, "season": "1973/1974"}, "s365")
    other = reg.mint("team", "fotmob", 999)
    G.c.execute("insert into honour(eid, kind, rank, tid, src) values(?, 'champion', 1, ?, 's365')", (e, other))
    awards.load(G, reg, S)
    assert G.c.execute("select tid from honour where eid=? and kind='champion'", (e,)).fetchall() == [(other,)]
    assert G.c.execute("select count(*) from conflict where type='honour' and field='champion'").fetchone()[0] == 1


def test_born_after_the_year_is_dropped(tmp_path):
    items = dict(ITEMS, Raymond_Kopa=item("Q3", "Raymond Kopa", born="1990-01-01"))
    S = mk(tmp_path, {"Ballon d'Or": BALLON}, items)
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    out = awards.load(G, reg, S)
    assert out["sanity_dropped"] == 1
    assert G.c.execute("select count(*) from honour h join edition e on e.eid=h.eid where e.season='1958'").fetchone()[0] == 0


def test_season_article_gives_that_seasons_honours(tmp_path):
    aw = T('<tr><th>Award</th><th>Winner</th><th>Club</th></tr>'
           f'<tr><td>Player of the Season</td><td>{L("Omar_Abdulrahman")}</td><td>x</td></tr>'
           f'<tr><td>Best Emirati Player</td><td>{L("Ali_Mabkhout")}</td><td>x</td></tr>', "Awards")
    items = {"Omar_Abdulrahman": item("Q60", "Omar Abdulrahman", "عمر عبدالرحمن", "1991-09-20"), "Ali_Mabkhout": item("Q61", "Ali Mabkhout", "علي مبخوت", "1990-10-05")}
    S = mk(tmp_path, {"2016–17_UAE_Pro_League": aw}, items)
    art = tmp_path / "graph" / ".cache" / "awards" / "articles.json"
    a = json.loads(art.read_text(encoding="utf-8"))
    a["awards"], a["seasons"] = [], {"2016–17_UAE_Pro_League": "538"}
    art.write_text(json.dumps(a), encoding="utf-8")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    lg = reg.mint("competition", "fotmob", 538)
    awards.load(G, reg, S)
    e = G.c.execute("select eid from edition where cid=? and season='2016/2017'", (lg,)).fetchone()[0]
    got = dict(G.c.execute("select kind, pid from honour where eid=?", (e,)).fetchall())
    assert got == {"best_player": reg.get("player", "wikidata", "Q60"), "best_local": reg.get("player", "wikidata", "Q61")}


def test_a_redirect_is_read_once_as_its_article(tmp_path):
    canon = BALLON.replace(b"<html>", b'<html><head><link rel="dc:isVersionOf" href="//en.wikipedia.org/wiki/Ballon_d%27Or"/></head>')
    S = mk(tmp_path, {"Ballon d'Or": canon, "Ballon d'Or (award)": canon}, ITEMS)      # «(award)» sorts after; «Ballon d'Or A» before
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    awards.load(G, reg, S)
    assert G.c.execute("select name from competition where kind='award'").fetchall() == [("Ballon d'Or",)]
    S2 = mk(tmp_path / "b", {"Ballon d'Or": canon, "Ballon A": canon}, ITEMS)
    G2, reg2 = Graph(str(tmp_path / "t2.db")), Registry()
    awards.load(G2, reg2, S2)
    assert G2.c.execute("select name from competition where kind='award'").fetchall() == [("Ballon d'Or",)]


def test_the_same_scorer_from_two_sources_is_no_conflict_and_ties_stay(tmp_path):
    sc = T('<tr><th>Player</th><th>Club</th><th>Goals</th></tr>'
           f'<tr><td>{L("Ali_Mabkhout")}</td><td>x</td><td>25</td></tr><tr><td>{L("Other_Guy")}</td><td>x</td><td>25</td></tr>', "Top scorers")
    items = {"Ali_Mabkhout": item("Q61", "Ali Mabkhout", "علي مبخوت", "1990-10-05"), "Other_Guy": item("Q62", "Other Guy", born="1990-01-01")}
    S = mk(tmp_path, {"2016–17_UAE_Pro_League": sc, "2017–18_UAE_Pro_League": sc}, items)
    art = tmp_path / "graph" / ".cache" / "awards" / "articles.json"
    a = json.loads(art.read_text(encoding="utf-8"))
    a["awards"], a["seasons"] = [], {"2016–17_UAE_Pro_League": "538", "2017–18_UAE_Pro_League": "538"}
    art.write_text(json.dumps(a), encoding="utf-8")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    lg = reg.mint("competition", "fotmob", 538)
    e17 = reg.mint("edition", "fotmob", "538|2016/2017")
    G.put("edition", {"eid": e17, "cid": lg, "season": "2016/2017"}, "fotmob")
    ours = reg.mint("player", "fotmob", 170716)
    G.put("player", {"pid": ours, "name": "Ali Ahmed Mabkhout"}, "fotmob")
    G.c.execute("insert into honour(eid, kind, rank, pid, value, src) values(?, 'top_scorer', 1, ?, '25', 'tifo')", (e17, ours))
    awards.load(G, reg, S)
    assert G.c.execute("select count(*) from conflict").fetchone()[0] == 0          # our count names him too
    e18 = G.c.execute("select eid from edition where cid=? and season='2017/2018'", (lg,)).fetchone()[0]
    assert G.c.execute("select count(*) from honour where eid=? and kind='top_scorer' and rank=1", (e18,)).fetchone()[0] == 2


def test_a_season_that_links_the_league_itself_has_no_champion(tmp_path):
    # Wikipedia's UAE list: 1990–91 «not held (Gulf War)» with the cells linking the league's own article
    page = UAE.replace(b"</table>", ('<tr><td>1990–91</td><td>' + L("UAE_Pro_League") + ' (Gulf War)</td><td>' + L("UAE_Pro_League") + '</td></tr></table>').encode(), 1)
    items = {"Sharjah_FC": {"qid": "Q30", "en": "Sharjah FC", "ar": "الشارقة", "human": False, "born": None, "tm_player": None, "tm_club": "7"},
             "UAE_Pro_League": {"qid": "Q500", "en": "UAE Pro League", "ar": "الدوري الإماراتي للمحترفين", "human": False, "born": None, "tm_player": None, "tm_club": None}}
    S = mk(tmp_path, {"UAE Pro League": page}, items, comps={"538": "UAE Pro League"})
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    lg = reg.mint("competition", "fotmob", 538)
    G.put("competition", {"cid": lg, "name": "Pro League"}, "fotmob")
    awards.load(G, reg, S)
    assert G.c.execute("select count(*) from honour h join edition e on e.eid=h.eid where e.season='1990/1991'").fetchone()[0] == 0
    assert G.c.execute("select count(*) from team where name='UAE Pro League'").fetchone()[0] == 0
    e = G.c.execute("select eid from edition where cid=? and season='1973/1974'", (lg,)).fetchone()[0]
    assert G.c.execute("select count(*) from honour where eid=? and kind='champion'", (e,)).fetchone()[0] == 1   # the real rows still load


def test_a_link_to_another_competition_or_a_season_article_is_not_a_club(tmp_path):
    rows = ''.join(f'<tr><td>{s}</td><td>{L(c)}</td><td>{L(c)}</td></tr>' for s, c in (("1993–94", "Egyptian_Premier_League"), ("1994–95", "2026–27_UEFA_Nations_League")))
    page = UAE.replace(b"</table>", (rows + '</table>').encode(), 1)
    nc = lambda q, en: {"qid": q, "en": en, "ar": None, "human": False, "born": None, "tm_player": None, "tm_club": None}
    items = {"Egyptian_Premier_League": nc("Q501", "Egyptian Premier League"), "2026–27_UEFA_Nations_League": nc("Q502", "2026–27 UEFA Nations League"),
             "Sharjah_FC": {"qid": "Q30", "en": "Sharjah FC", "ar": "الشارقة", "human": False, "born": None, "tm_player": None, "tm_club": "7"}}
    S = mk(tmp_path, {"UAE Pro League": page}, items, comps={"538": "UAE Pro League"})
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    lg = reg.mint("competition", "fotmob", 538)
    G.put("competition", {"cid": lg, "name": "Pro League"}, "fotmob")
    awards.load(G, reg, S)
    assert G.c.execute("select count(*) from honour h join edition e on e.eid=h.eid where e.season in ('1993/1994','1994/1995')").fetchone()[0] == 0
    assert G.c.execute("select count(*) from team where name like '%League%'").fetchone()[0] == 0


def test_two_spellings_of_one_club_or_one_man_are_alike():
    assert awards.alike("al shabab al arabi", "al shabab al arabi club 1958 2017")     # Wikipedia's link carries the years
    assert awards.alike("banni yas", "fc baniyas")
    assert awards.alike("lionel messi", "messi")                                      # the same surname, as before
    assert not awards.alike("al ain", "al wahda")
    assert not awards.alike("omar khribin", "soufiane rahimi")


def test_a_leagues_list_of_champions_gives_its_editions_honours(tmp_path):
    # awards.yaml comp_pages: «List of Moroccan football champions» is Botola Pro's (FotMob 530) and «List of Algerian football
    # champions» Algeria's Ligue 1 (516): a «Winners» club column is the champion, «Name (Club, 21 goals)» the top scorer
    html = open(os.path.join(os.path.dirname(__file__), "fixtures", "awards_arab_champions.html"), "rb").read()
    club = lambda q, en: {"qid": q, "en": en, "ar": None, "human": False, "born": None, "tm_player": None, "tm_club": None}
    items = {"Wydad_AC": club("Q50", "Wydad AC"), "Maghreb_of_Fez": club("Q51", "Maghreb Fez"), "CR_Belouizdad": club("Q52", "CR Belouizdad"),
             "MSP_Batna": club("Q53", "MSP Batna"), "USM_Alger": club("Q54", "USM Alger"), "MC_Alger": club("Q55", "MC Alger"),
             "NA_Hussein_Dey": club("Q56", "NA Hussein Dey"), "Paradou_AC": club("Q57", "Paradou AC"),
             "Hassan_Akesbi": item("Q60", "Hassan Akesbi", born="1934-01-01"), "Soufiane_Benjdida": item("Q61", "Soufiane Benjdida", born="2000-01-01"),
             "Hacène_Lalmas": item("Q62", "Hacène Lalmas", born="1943-01-01"), "Adil_Boulbina": item("Q63", "Adil Boulbina", born="2003-01-01")}
    S = mk(tmp_path, {"List of Moroccan football champions": html, "List of Algerian football champions": html}, items)
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    awards.load(G, reg, S)
    assert G.c.execute("select count(*) from competition where kind='award'").fetchone()[0] == 0
    hon = lambda fid, season: dict(((k, r), (t, p, v)) for k, r, t, p, v in G.c.execute(
        "select h.kind, h.rank, h.tid, h.pid, h.value from honour h join edition e on e.eid=h.eid where e.cid=? and e.season=?",
        (reg.get("competition", "fotmob", fid), season)))
    mar = hon(530, "2025/2026")
    assert mar[("champion", 1)][0] == reg.get("team", "wikidata", "Q51") and mar[("top_scorer", 1)][1] == reg.get("player", "wikidata", "Q61")
    assert ("champion", 1) not in hon(530, "1957/1958")              # «KAC Marrakech (1)» unlinked: no club, no player
    alg = hon(516, "1965/1966")
    assert alg[("champion", 1)][0] == reg.get("team", "wikidata", "Q52") and alg[("runner_up", 1)][0] == reg.get("team", "wikidata", "Q54")
    assert alg[("top_scorer", 1)][1:] == (reg.get("player", "wikidata", "Q62"), "25")
    assert hon(516, "1964/1965")[("top_scorer", 1)][2] == "21"          # unlinked man: a name-only player with his goals
def test_a_names_or_sponsorship_table_gives_no_people(tmp_path):
    # Iraq Stars League «Names» (Period | Name) and the FA Cup «Sponsorship» (Period | Sponsor | Name): the «Name» column is the
    # competition's own name, once read as a best player / a winner; a real man whose name only looks like one (Cupido) stays
    names = T('<tr><th>Period</th><th>Name</th></tr>' + ''.join(
        f'<tr><td>{p}</td><td>{n}</td></tr>' for p, n in (("1974–88", "National Clubs First Division League"), ("1988–89", "Advanced League"),
                                                           ("2013–14", "Zain Iraq League"), ("2023–24", "Stars League"))), "Names")
    scorers = T('<tr><th>Season</th><th>Player</th><th>Goals</th></tr>' + ''.join(
        f'<tr><td>{p}</td><td>{n}</td><td>20</td></tr>' for p, n in (("1974–75", "Cupido"), ("1975–76", "Junior Ligue"), ("1976–77", "Hussein Saeed"))),
        "Top scorers")
    page = b'<html><body>' + names[12:-14] + scorers[12:-14] + b'</body></html>'
    sponsor = T('<tr><th>Period</th><th>Sponsor</th><th>Name</th></tr>' + ''.join(
        f'<tr><td>{p}</td><td>{s}</td><td>{n}</td></tr>' for p, s, n in (("1994–98", "Littlewoods", "The FA Cup sponsored by Littlewoods"),
                                                                     ("2006–11", "E.ON", "The FA Cup sponsored by E.ON"),
                                                                     ("2015–16", "Emirates", "Emirates FA Cup"))), "Sponsorship")
    fair = T('<tr><th>Year</th><th>Winner</th></tr>' + ''.join(
        f'<tr><td>{y}</td><td>{n}</td></tr>' for y, n in (("2012", "Sven Kramer"), ("2014", "World Cup volunteers"), ("2016", "Lionel Goodman"))))
    S = mk(tmp_path, {"Iraq Stars League": page, "FA Cup": sponsor, "FIFA Fair Play Award": fair}, ITEMS, comps={"25": "Iraq Stars League"})
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    reg.mint("competition", "fotmob", 25)
    out = awards.load(G, reg, S)
    got = {r[0] for r in G.c.execute("select name from player")}
    assert not got & {"National Clubs First Division League", "Advanced League", "Zain Iraq League", "Stars League",
                      "The FA Cup sponsored by Littlewoods", "The FA Cup sponsored by E.ON", "Emirates FA Cup", "World Cup volunteers"}
    assert {"Cupido", "Junior Ligue", "Hussein Saeed", "Sven Kramer", "Lionel Goodman"} <= got
    assert out["not_a_person"] == 8
    assert G.c.execute("select count(*) from honour where pid is null and tid is null and kid is null").fetchone()[0] == 0


def test_a_name_that_is_a_competition_is_not_a_person():
    for n in ("Premier League", "The FA Cup", "Fuchs Premier League", "First Division League", "World Cup volunteers",
              "The AXA sponsored FA Cup (1998–1999)The FA Cup sponsored by AXA (1999–2002)", "Liga MX", "Asian Cup Trophy",
              "AFC Championship"):
        assert awards.not_a_person(n), n
    for n in ("Cupido", "Calixte Ligue", "Junior Ligue", "Leaguer Smith", "Cupper", "Hussein Saeed", "", None):
        assert not awards.not_a_person(n), n


def test_an_arabic_wikipedia_list_gives_top_scorers_with_arabic_names(tmp_path):
    # awards.yaml comp_pages: «ar:قائمة هدافي دوري المحترفين السعودي» is the Saudi Pro League's (FotMob 536)
    html = open(os.path.join(os.path.dirname(__file__), "fixtures", "awards_ar_saudi_scorers.html"), "rb").read()
    items = {"ar:محمد_العبدلي": item("Q70", "Mohammed Al-Abdali", "محمد العبدلي", "1950-01-01")}
    S = mk(tmp_path, {"ar:قائمة هدافي دوري المحترفين السعودي": html}, items)
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    awards.load(G, reg, S)
    top = lambda season: G.c.execute("select h.pid, h.value from honour h join edition e on e.eid=h.eid where e.cid=? and e.season=? and h.kind='top_scorer'",
                                     (reg.get("competition", "fotmob", 536), season)).fetchall()
    assert top("1974/1975") == [(reg.get("player", "wikidata", "Q70"), "13")]
    (pid, _), = top("1976/1977")                                          # «ناصر عيد», no article: a name-only player in Arabic
    assert G.c.execute("select name, name_ar from player where pid=?", (pid,)).fetchone() == ("ناصر عيد", "ناصر عيد")


def _kuwait(tmp_path, champion_tid=None):
    t = ('<section><h2>League table</h2><table class="wikitable"><tr><th>Pos</th><th>Team</th><th>Pld</th><th>Pts</th></tr>'
         '<tr><td>1</td><td><a rel="mw:WikiLink" href="./Kuwait_SC" title="Kuwait SC">Kuwait SC</a></td><td>26</td><td>60</td></tr>'
         '<tr><td>2</td><td><a rel="mw:WikiLink" href="./Al-Qadsia_SC" title="Al-Qadsia SC">Al-Qadsia</a></td><td>26</td><td>55</td></tr></table></section>')
    items = {"Kuwait_SC": {"qid": "Q81", "en": "Kuwait SC", "ar": "الكويت", "human": False, "born": None, "tm_player": None, "tm_club": "81"},
             "Al-Qadsia_SC": {"qid": "Q82", "en": "Al-Qadsia SC", "ar": "القادسية", "human": False, "born": None, "tm_player": None, "tm_club": "82"}}
    S = mk(tmp_path, {"2012–13_Kuwaiti_Premier_League": ('<html><body>' + t + '</body></html>').encode()}, items, comps={"529": "Kuwait Premier League"})
    art = tmp_path / "graph" / ".cache" / "awards" / "articles.json"
    a = json.loads(art.read_text(encoding="utf-8"))
    a["awards"], a["seasons"] = [], {"2012–13_Kuwaiti_Premier_League": 529}
    art.write_text(json.dumps(a), encoding="utf-8")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    lg = reg.mint("competition", "fotmob", 529)
    kw, qd = reg.mint("team", "tm", "81"), reg.mint("team", "tm", "82")
    if champion_tid:
        e = reg.mint("edition", "fotmob", "529|2012/2013")
        G.put("edition", {"eid": e, "cid": lg, "season": "2012/2013"}, "fotmob")
        G.c.execute("insert into honour(eid, kind, rank, tid, src) values(?, 'champion', 1, ?, 's365')", (e, {"kw": kw, "qd": qd}[champion_tid]))
    awards.load(G, reg, S)
    e = G.c.execute("select eid from edition where cid=? and season='2012/2013'", (lg,)).fetchone()[0]
    return dict(G.c.execute("select kind, tid from honour where eid=?", (e,)).fetchall()), kw, qd


def test_a_season_pages_league_table_gives_the_runner_up_when_its_first_is_the_champion(tmp_path):
    got, kw, qd = _kuwait(tmp_path, "kw")
    assert got == {"champion": kw, "runner_up": qd}


def test_a_league_table_whose_first_is_not_the_champion_gives_nothing(tmp_path):
    got, kw, qd = _kuwait(tmp_path, "qd")              # a regular season before a championship round: not the final standing
    assert got == {"champion": qd}

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

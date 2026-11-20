"""A national team article's «Most appearances» and «Top goalscorers» tables (graph/awards_wiki.intl_records): every listed
player's caps, goals and years for his country, the totals FotMob's archive cannot give for the players before it."""
from graph import awards_wiki as W

def L(t, text=None):
    return f'<a rel="mw:WikiLink" href="./{t}">{text or t.replace("_", " ")}</a>'

PAGE = (('<html><body><section><h2>Player records</h2><section><h3>Most appearances</h3><table class="wikitable">'
         '<tr><th>Rank</th><th>Player</th><th>Caps</th><th>Goals</th><th>Career</th></tr>'
         f'<tr><td>1</td><td>{L("Adnan_Al_Talyani", "Adnan Al-Talyani")}</td><td>161</td><td>52</td><td>1983–1997</td></tr>'
         f'<tr><td>2</td><td>{L("Ismail_Matar")}</td><td>136</td><td>36</td><td>2003–2021</td></tr></table></section>'
         '<section><h3>Top goalscorers</h3><table class="wikitable">'
         '<tr><th>Rank</th><th>Player</th><th>Goals</th><th>Caps</th><th>Ratio</th><th>Career</th></tr>'
         f'<tr><td>1</td><td>{L("Ali_Mabkhout", "Ali Mabkhout")} (<a href="./List">list</a>)</td><td>85</td><td>115</td><td>0.74</td><td>2009–2024</td></tr>'
         f'<tr><td>2</td><td>{L("Adnan_Al_Talyani", "Adnan Al-Talyani")}</td><td>52</td><td>161</td><td>0.32</td><td>1983–1997</td></tr></table>'
         '</section></section><section><h2>Head-to-head record</h2><table class="wikitable"><tr><th>Opponent</th><th>Pld</th></tr>'
         '<tr><td>Iran</td><td>20</td></tr></table></section></body></html>').encode())


def test_both_tables_one_row_per_player():
    got = {r["person"]: r for r in W.intl_records(PAGE)}
    assert sorted(got) == ["Adnan_Al_Talyani", "Ali_Mabkhout", "Ismail_Matar"]
    assert got["Adnan_Al_Talyani"] == {"person": "Adnan_Al_Talyani", "name": "Adnan Al-Talyani", "caps": 161, "goals": 52, "career": "1983–1997"}
    assert got["Ali_Mabkhout"]["caps"] == 115 and got["Ali_Mabkhout"]["goals"] == 85 and got["Ali_Mabkhout"]["name"] == "Ali Mabkhout"


def test_national_article_titles_skip_women_and_youth():
    html = ('<a href="./United_Arab_Emirates_national_football_team">x</a><a href="./Qatar_women%27s_national_football_team">x</a>'
            '<a href="./Brazil_national_under-20_football_team">x</a><a href="./England_national_football_team#Records">x</a>').encode()
    assert W.national_articles(html) == ["England national football team", "United Arab Emirates national football team"]


def test_the_loader_finds_the_player_by_his_wikidata_item(tmp_path):
    import gzip, json
    from graph.db import Graph
    from graph.ids import Registry
    from graph.src import Sources
    from graph.load import intl_records
    from graph.awards_fetch import _key
    d = tmp_path / "graph" / ".cache" / "awards"
    (d / "pages").mkdir(parents=True)
    t = "United Arab Emirates national football team"
    (d / "pages" / (_key(t) + ".html.gz")).write_bytes(gzip.compress(PAGE))
    (d / "pages.json").write_text(json.dumps({t: {"fetched": "2026-11-20"}}))
    (d / "articles.json").write_text(json.dumps({"awards": [], "comps": {}, "national": [t]}))
    hum = lambda q, en, ar=None, tm=None: {"qid": q, "en": en, "ar": ar, "human": True, "born": None, "tm_player": tm, "tm_club": None}
    (d / "items.json").write_text(json.dumps({"Adnan_Al_Talyani": hum("Q1", "Adnan Al Talyani", "عدنان الطلياني"), "Ismail_Matar": hum("Q2", "Ismail Matar", tm="55"),
                                              "Ali_Mabkhout": {"qid": "Q3", "human": False}}, ensure_ascii=False), encoding="utf-8")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    matar = reg.mint("player", "tm", "55")
    out = intl_records.load(G, reg, Sources(str(tmp_path), mirror=str(tmp_path / "m"), s3=False))
    assert out == {"teams": 1, "records": 2, "unlinked": 1}
    rec = {p: (team, c, g, y) for p, team, c, g, y in G.c.execute("select pid, team, caps, goals, career from intl_record")}
    assert rec[reg.get("player", "wikidata", "Q1")] == ("United Arab Emirates", 161, 52, "1983–1997")
    assert rec[matar] == ("United Arab Emirates", 136, 36, "2003–2021")         # joined through his Transfermarkt id

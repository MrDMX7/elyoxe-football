"""graph/load/wikidata_facts.py: Wikidata's facts fill what the graph holds and has empty: a club by its Transfermarkt id,
a player by his item, his Transfermarkt id or his birthday with his name, a stadium by its name; never a guess between
two values, never over a field we have, never a woman's item or a year alone as a birthday."""
from graph.db import Graph
from graph.ids import Registry
from graph.load import wikidata_facts as W

Q = "<http://www.wikidata.org/entity/%s>"


def tsv(*rows):
    return "?c\t?v\n" + "\n".join("\t".join(r) for r in rows) + "\n"


def test_an_answer_is_read_by_item_with_literals_bare_and_units_paired():
    got = W.parse(tsv((Q % "Q1", '"1899-11-29T00:00:00Z"^^<http://www.w3.org/2001/XMLSchema#dateTime>'), (Q % "Q1", Q % "Q5"), (Q % "Q2", '"برشلونة"@ar'),
                      (Q % "Q3", '"1.7"^^<x>', Q % "Q11573")))
    assert got == {"Q1": ["1899-11-29T00:00:00Z", "Q5"], "Q2": ["برشلونة"], "Q3": [("1.7", "Q11573")]}


def test_single_values_only():
    assert W.day(["1987-06-24T00:00:00Z"]) == "1987-06-24"
    assert W.day(["1987-01-01T00:00:00Z"]) is None                      # a year alone
    assert W.day(["1987-06-24T00:00:00Z", "1987-06-25T00:00:00Z"]) is None
    assert W.height_of([("1.7", "Q11573")]) == 170 and W.height_of([("170", "Q174728"), ("1.70", "Q11573")]) == 170
    assert W.height_of([("17", "Q174728")]) is None and W.height_of([("170", "Q174728"), ("172", "Q174728")]) is None
    assert W.position_of(["Q268258"]) == "Center Back" and W.position_of(["Q268258", "Q336286"]) == "Defender"
    assert W.position_of(["Q268258", "Q193592"]) is None and W.position_of(["Q1369558"]) is None
    assert W.country_of(["ARG"]) == "AR" and W.country_of(["ARG", "ESP"]) is None
    assert W.country_of(["GBR"]) is None and W.country_of(["GBR"], ["England"]) == "GB-ENG"


def graph(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    G.put("team", {"tid": 1, "name": "FC Barcelona", "kind": "club"}, "fotmob")
    G.put("team", {"tid": 2, "name": "Real Madrid", "kind": "club", "country": "Spain", "name_ar": "ريال مدريد"}, "fotmob")
    G.put("team", {"tid": 3, "name": "Spain", "kind": "national", "country": "Spain"}, "fotmob")
    G.put("team", {"tid": 4, "name": "Twin A", "kind": "club"}, "fotmob")
    G.put("team", {"tid": 5, "name": "Twin B", "kind": "club"}, "fotmob")
    for tid, tm in ((1, 131), (2, 418), (3, 3375), (4, 77), (5, 78)):
        G.xref("team", tid, "tm", tm, "tm-native")
    G.put("stadium", {"sid": 10, "name": "Santiago Bernabéu", "country": "Spain"}, "fotmob")
    G.put("stadium", {"sid": 11, "name": "Estadio Municipal", "country": "Spain"}, "fotmob")
    return G, reg


CLUBS = {"club_tm": {"Q7156": ["131"], "Q8682": ["418"], "Q42267": ["3375"], "Q900": ["77", "78"]},
         "club_founded": {"Q7156": ["1899-11-29T00:00:00Z"], "Q8682": ["1902-03-06T00:00:00Z", "1903-01-01T00:00:00Z"], "Q42267": ["1920-01-01T00:00:00Z"],
                          "Q900": ["1950-01-01T00:00:00Z"]},
         "club_country": {"Q7156": ["ESP"], "Q8682": ["ESP"]}, "club_ar": {"Q7156": ["نادي برشلونة"], "Q8682": ["نادي ريال مدريد"]},
         "club_venue": {"Q7156": ["Q164027"], "Q8682": ["Q164298"], "Q900": ["Q5"]},
         "venue_en": {"Q164027": ["Camp Nou"], "Q164298": ["Santiago Bernabéu"], "Q5": ["Estadio Municipal"]},
         "venue_ar": {"Q164027": ["كامب نو"]}, "venue_cap": {"Q164027": ["99354", "105000"], "Q164298": ["81044"]},
         "venue_coord": {"Q164027": ["POINT(2.1228 41.3809)"]}, "venue_city": {"Q164027": ["Barcelona"]},
         "venue_country": {"Q164027": ["ESP"], "Q164298": ["ESP"]}}


def test_a_club_is_filled_by_its_transfermarkt_id_and_gets_its_ground(tmp_path):
    G, reg = graph(tmp_path)
    out = W.apply(G, reg, CLUBS)
    t = {r[0]: r[1:] for r in G.c.execute("select tid, founded, country, name_ar, sid from team")}
    camp = reg.get("stadium", "wikidata", "Q164027")
    assert t[1] == (1899, "Spain", "نادي برشلونة", camp)              # the country as the graph spells it
    assert t[2] == (None, "Spain", "ريال مدريد", 10)                   # two founding years: none; our Arabic name stays; the ground we hold, by name
    assert t[3] == (None, "Spain", None, None)                         # a national team is no club
    assert t[4] == (None, None, None, None) and t[5] == (None, None, None, None)      # one item for two of ours: neither
    assert G.c.execute("select name, name_ar, city, country, capacity, lat, lon from stadium where sid=?", (camp,)).fetchone() == (
        "Camp Nou", "كامب نو", "Barcelona", "Spain", 105000, 41.3809, 2.1228)
    assert G.c.execute("select capacity from stadium where sid=10").fetchone() == (81044,)
    assert G.c.execute("select capacity from stadium where sid=11").fetchone() == (None,)       # «Estadio Municipal» names no one ground
    assert sorted(G.c.execute("select tifo_id, source_id from xref where type='team' and source='wikidata'")) == [(1, "Q7156"), (2, "Q8682")]
    assert (out["team_clubs"], out["team_founded"], out["stadium_known"], out["stadium_new"], out["stadium_home"]) == (2, 1, 1, 1, 2)


def test_a_player_is_found_three_ways_and_only_his_empty_fields_filled(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    G.put("player", {"pid": 1, "name": "Lionel Messi", "born": "1987-06-24", "nationality": "ARG", "position": "Right Winger"}, "fotmob")
    G.xref("player", 1, "wikidata", "Q615", "wikipedia")
    G.put("player", {"pid": 2, "name": "Andrés Iniesta", "born": "1984-05-11"}, "fotmob")
    G.xref("player", 2, "tm", 7600, "tm-native")
    G.put("player", {"pid": 3, "name": "Omar Abdulrahman", "born": "1991-09-20"}, "fotmob")
    G.put("player", {"pid": 4, "name": "Alex Morgan", "born": "1989-07-02"}, "fotmob")
    G.put("player", {"pid": 5, "name": "John Smith", "born": "1990-03-03"}, "fotmob")
    G.put("player", {"pid": 6, "name": "Old Timer"}, "rsssf")
    G.xref("player", 6, "wikidata", "Q77", "wikipedia")
    G.put("player", {"pid": 7, "name": "Someone Else", "nationality": "UAE"}, "fotmob")
    G.put("coach", {"kid": 9, "name": "Pep Guardiola"}, "fotmob")
    G.xref("coach", 9, "wikidata", "Q164038", "wikipedia")
    G.put("coach", {"kid": 8, "name": "Other", "nationality": "Spain"}, "fotmob")
    men = ("Q615", "Q1", "Q2", "Q51", "Q52", "Q77", "Q164038")
    F = {"man_sex": {**{q: ["Q6581097"] for q in men}, "Q3": ["Q6581072"]},
         "man_tm": {"Q1": ["7600"]},
         "man_born": {"Q615": ["1987-06-24T00:00:00Z"], "Q1": ["1984-05-11T00:00:00Z"], "Q2": ["1991-09-20T00:00:00Z"], "Q3": ["1989-07-02T00:00:00Z"],
                      "Q51": ["1990-03-03T00:00:00Z"], "Q52": ["1990-03-03T00:00:00Z"], "Q77": ["1901-01-01T00:00:00Z"], "Q164038": ["1971-01-18T00:00:00Z"]},
         "man_en": {"Q2": ["Omar Abdulrahman"], "Q3": ["Alex Morgan"], "Q51": ["John Smith"], "Q52": ["John Smith"]},
         "man_ar": {"Q615": ["ليونيل ميسي"], "Q2": ["عمر عبد الرحمن أحمد الراقي العمودي"]},
         "man_died": {"Q77": ["1970-02-03T00:00:00Z"]},
         "man_pos": {"Q615": ["Q280658"], "Q1": ["Q193592"], "Q2": ["Q90326494", "Q193592"]},
         "man_height": {"Q615": [("170", "Q174728")], "Q1": [("1.71", "Q11573")]},
         "man_country": {"Q615": ["ARG", "ESP"], "Q1": ["ESP"], "Q2": ["ARE"], "Q164038": ["ESP"]},
         "man_sport": {"Q2": ["United Arab Emirates"]},
         "man_place": {"Q615": ["Rosario"], "Q1": ["Fuentealbilla"], "Q2": ["Riyadh", "Al Ain"]}}
    out = W.apply(G, reg, F)
    p = {r[0]: r[1:] for r in G.c.execute("select pid, name_ar, born, died, nationality, position, height, birthplace from player")}
    assert p[1] == ("ليونيل ميسي", "1987-06-24", None, "ARG", "Right Winger", 170, "Rosario")         # his position and country are ours
    assert p[2] == (None, "1984-05-11", None, None, "Midfielder", 171, "Fuentealbilla")                # no player says «ESP» yet: no spelling to write
    assert p[3] == (None, "1991-09-20", None, "UAE", "Midfielder", None, None)                         # the long legal name and two birthplaces: left
    assert p[4] == (None, "1989-07-02", None, None, None, None, None)                                  # a woman's item
    assert p[5] == (None, "1990-03-03", None, None, None, None, None)                                  # two men of one name and day
    assert p[6] == (None, None, "1970-02-03", None, None, None, None)                                  # born «1901»: a year, no birthday
    assert sorted(G.c.execute("select tifo_id, source_id, method from xref where type='player' and source='wikidata'")) == [
        (1, "Q615", "wikipedia"), (2, "Q1", "tm-id"), (3, "Q2", "born-name"), (6, "Q77", "wikipedia")]
    assert G.c.execute("select born, nationality from coach where kid=9").fetchone() == ("1971-01-18", "Spain")
    assert (out["player_by_item"], out["player_by_tm_id"], out["player_by_born_name"], out["coach_filled"]) == (2, 1, 1, 1)


def test_files_are_fetched_once_a_week_and_a_failed_answer_keeps_the_old_file(tmp_path):
    class S:
        db, s3 = str(tmp_path), False
    asked = []

    def get(q):
        asked.append(q)
        return tsv(*[(Q % f"Q{i}", '"x"') for i in range(4)]).encode()

    assert W.fetch(S, get=get)["fetched"] == len(W.QUERIES) == len(asked)
    assert W.fetch(S, get=get) == {"fetched": 0, "kept": len(W.QUERIES), "state": 0, "missing": 0}

    def down(q):
        raise OSError("no answer")

    assert W.fetch(S, max_age_days=0, get=down)["kept"] == len(W.QUERIES)
    assert W.read(S)["club_tm"] == {"Q0": ["x"], "Q1": ["x"], "Q2": ["x"], "Q3": ["x"]}
    assert W.load(None, None, type("E", (), {"db": str(tmp_path / "none"), "s3": False})) == {"skipped": "no Wikidata files"}

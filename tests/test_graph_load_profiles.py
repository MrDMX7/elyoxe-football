import gzip, json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import fotmob_profiles, names

PROFILE = {"id": 77, "name": "Omar A", "isCoach": False, "birthDate": {"utcTime": "1991-10-01T00:00:00.000Z"},
           "positionDescription": {"positions": [{"strPos": {"label": "Striker"}, "isMainPosition": True}]},
           "playerInformation": [{"title": "Height", "value": {"numberValue": 182}}, {"title": "Preferred foot", "value": {"key": "left"}},
                                 {"title": "Country", "value": {"fallback": "United Arab Emirates"}, "countryCode": "ARE"}],
           "careerHistory": {"careerItems": {"senior": {"teamEntries": [{"teamId": 10, "team": "Al Ain", "startDate": "2008-07-01T00:00:00", "endDate": None,
                                                                          "appearances": "300", "goals": "120", "assists": "80", "transferType": None},
                                                                         {"teamId": 11, "team": "Old Club", "startDate": 2005, "endDate": 1199145600000, "appearances": 3}]},
                                             "national team": {"teamEntries": [{"teamId": 5789, "team": "UAE", "startDate": "2011-01-01T00:00:00", "endDate": None, "appearances": "90", "goals": "40", "assists": None}]}}}}
COACH = {"id": 88, "name": "Coach K", "isCoach": True, "birthDate": {"utcTime": "1970-01-01T00:00:00.000Z"}, "playerInformation": [], "careerHistory": {}}


def mk(tmp_path):
    p = tmp_path / "db" / ".cache" / "fm" / "p"
    p.mkdir(parents=True)
    (p / "77.json.gz").write_bytes(gzip.compress(json.dumps(PROFILE).encode()))
    (p / "88.json.gz").write_bytes(gzip.compress(json.dumps(COACH).encode()))
    n = tmp_path / "names"
    n.mkdir()
    (n / "players_ar.json").write_text(json.dumps({"77": {"latin": "Omar A", "ar": "عمر أ", "source": "wikidata", "qid": "Q1"}}), encoding="utf-8")
    (n / "clubs_ar.json").write_text(json.dumps({"10": {"latin": "Al Ain", "ar": "العين", "source": "wikidata", "qid": None}}), encoding="utf-8")
    (n / "coaches_ar.json").write_text("{}")
    (n / "referees_ar.json").write_text("{}")
    return Sources(str(tmp_path), s3=False)


def test_profiles_and_names(tmp_path):
    S, G, reg = mk(tmp_path), Graph(str(tmp_path / "t.db")), Registry()
    fotmob_profiles.load(G, reg, S)
    names.load(G, reg, S)
    pid = reg.get("player", "fotmob", 77)
    row = G.c.execute("select born, nationality, height, foot, position, name_ar from player where pid=?", (pid,)).fetchone()
    assert row == ("1991-10-01", "ARE", 182, "left", "Striker", "عمر أ")
    assert G.c.execute("select count(*) from spell where pid=?", (pid,)).fetchone()[0] == 3
    assert G.c.execute("select start, end from spell where pid=? and apps=3", (pid,)).fetchone() == ("2005", "2008-01-01")
    assert G.c.execute("select national from spell where pid=? and apps=90", (pid,)).fetchone()[0] == 1
    assert G.c.execute("select name from coach").fetchall() == [("Coach K",)]
    assert G.c.execute("select source_id from xref where type='player' and source='wikidata'").fetchall() == [("Q1",)]
    assert G.c.execute("select name_ar from team where tid=?", (reg.get("team", "fotmob", 10),)).fetchone()[0] == "العين"

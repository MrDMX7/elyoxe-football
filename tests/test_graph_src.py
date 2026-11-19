import gzip, json, os
from graph.src import Sources
from graph import fm


def mk(tmp_path):
    db = tmp_path / "db" / ".cache"
    (db / "fm" / "seasons" / "538").mkdir(parents=True)
    (db / "fm" / "seasons" / "538" / "_seasons.json").write_text(json.dumps(["2025/2026", "2024/2025"]))
    (db / "fm" / "seasons" / "538" / "2024-2025.json").write_text(json.dumps([111, 112]))
    (db / "fm" / "seasons" / "77").mkdir(parents=True)
    (db / "fm" / "seasons" / "77" / "_seasons.json").write_text(json.dumps(["2026", "2022"]))
    (db / "fm" / "seasons" / "77" / "2022.json").write_text(json.dumps([222]))
    (db / "fm_allleagues.json").write_text(json.dumps({"popular": [], "international": [{"ccode": "INT", "name": "International", "leagues": [{"id": 77, "name": "World Cup"}]}],
                                                       "countries": [{"ccode": "ARE", "name": "United Arab Emirates", "leagues": [{"id": 538, "name": "Pro League"}]}]}))
    (db / "fm_ar.json").write_text(json.dumps({"LeagueMapping": {"77": "76"}, "TournamentTemplates": {"76": "كأس العالم"}, "Participants": {}}))
    return Sources(str(tmp_path), mirror=str(tmp_path / "mirror"), s3=False)


def test_read_gz_and_plain(tmp_path):
    S = mk(tmp_path)
    p = tmp_path / "x.json.gz"
    p.write_bytes(gzip.compress(b'{"a": 1}'))
    q = tmp_path / "y.json"
    q.write_text('{"b": 2}')
    assert S.read(str(p)) == {"a": 1} and S.read(str(q)) == {"b": 2} and S.read(str(tmp_path / "none.json")) is None


def test_season_map_and_calendar(tmp_path):
    labels, calendar = fm.season_map(mk(tmp_path))
    assert labels[111] == "2024/2025" and labels[222] == "2022"
    assert 77 in calendar and 538 not in calendar


def test_comp_info_names(tmp_path):
    info = fm.comp_info(mk(tmp_path))
    assert info[77]["name"] == "World Cup" and info[77]["name_ar"] == "كأس العالم" and info[77]["country"] == "INT"
    assert info[538]["country"] == "ARE" and info[538]["name_ar"] == "دوري أدنوك للمحترفين"   # competitions.yaml wins


def test_iso():
    assert fm.iso("2026-08-20T22:00:00.000Z") == "2026-08-20T22:00:00Z"
    assert fm.iso("2010-06-26") == "2010-06-26" and fm.iso(None) is None


def test_published_reads_mirror(tmp_path):
    S = mk(tmp_path)
    m = tmp_path / "mirror" / "s365"
    m.mkdir(parents=True)
    (m / "index.json").write_text('{"teams": []}')
    assert S.published("s365/index.json") == {"teams": []}
    assert S.published("s365/none.json") is None

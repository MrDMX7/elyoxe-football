"""graph/archive_export.py: every competition is exported, the ones FotMob has no number for under a number of ours, and
competitions.json names them for the archive's own pages (/c/k<Tifo id>/)."""
import json
import os
from graph.db import Graph
from graph import archive_export, publish


def world(tmp_path):
    G = Graph(str(tmp_path / "t.db"))
    G.put("competition", {"cid": 1, "name": "Pro League", "name_ar": "دوري المحترفين", "kind": "league", "country": "AE", "scope": "uae"}, "fotmob")
    G.xref("competition", 1, "fotmob", 538, "fotmob-native")
    G.put("competition", {"cid": 2, "name": "Maltese Cup", "name_ar": "كأس مالطا", "kind": "cup", "country": "MT", "scope": "national"}, "sch")
    G.xref("competition", 2, "sch", "malta-cup", "native")
    G.put("competition", {"cid": 3, "name": "Player of the Year", "kind": "award"}, "tm")
    G.put("competition", {"cid": 4, "name": "Empty Cup", "kind": "cup"}, "tm")
    for tid in (11, 12):
        G.put("team", {"tid": tid, "name": f"Club {tid}", "kind": "club"}, "sch")
    for cid, years in ((1, (2020,)), (2, (1950, 1951))):
        for y in years:
            G.put("edition", {"eid": cid * 10000 + y, "cid": cid, "season": str(y)}, "sch")
            G.put("match", {"mid": cid * 100000 + y, "eid": cid * 10000 + y, "date": f"{y}-05-01", "home": 11, "away": 12, "hs": 2, "as_": 1, "status": "finished"}, "sch")
    G.c.commit()
    return G


def numbers(G):
    return sorted(G.c.execute("SELECT tifo_id, source_id FROM xref WHERE type='competition' AND source='fotmob'").fetchall())


def test_a_competition_without_a_fotmob_number_is_published_under_one_of_ours_and_an_award_never(tmp_path):
    G = world(tmp_path)
    assert archive_export.publication_ids(G) == 2
    assert numbers(G) == [(1, "538"), (2, str(archive_export.PUB + 2)), (4, str(archive_export.PUB + 4))]
    assert archive_export.PUB + 2 in archive_export.competitions(G)


def test_the_catalogue_names_every_competition_with_seasons(tmp_path):
    G, out = world(tmp_path), str(tmp_path / "out")
    os.makedirs(out)
    archive_export.publication_ids(G)
    publish.editions(G, out)
    assert archive_export.catalogue(G, out) == {"catalogue": 2}
    rows = {r["cid"]: r for r in json.load(open(os.path.join(out, "competitions.json"), encoding="utf-8"))}
    assert sorted(rows) == [1, 2]                                  # the award and the competition without a season: no page
    assert rows[1]["id"] == 538 and rows[2]["id"] == archive_export.PUB + 2
    assert (rows[2]["name_ar"], rows[2]["kind"], rows[2]["country"], rows[2]["country_ar"]) == ("كأس مالطا", "cup", "MT", "مالطا")
    assert (rows[2]["seasons"], rows[2]["matches"], rows[2]["first"], rows[2]["last"]) == (2, 2, "1950", "1951")
    assert os.path.exists(os.path.join(out, "editions", f"{archive_export.PUB + 2}.json"))


def test_the_export_leaves_the_database_as_it_found_it(tmp_path):
    G = world(tmp_path)
    G.c.close()
    rec = archive_export.export(str(tmp_path / "t.db"), str(tmp_path / "out"))
    assert rec["ours"] == 2 and rec["catalogue"] == 2
    assert os.path.exists(os.path.join(str(tmp_path / "out"), "matches", str(archive_export.PUB + 2), "1950.json"))
    assert numbers(archive_export.open_graph(str(tmp_path / "t.db"))) == [(1, "538")]

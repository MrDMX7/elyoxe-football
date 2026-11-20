"""names/build_names.py takes the players and clubs of the graph's season files (v1/editions/<comp>.json) into its pool, so the
season archive's old scorers and champions get Arabic names (Ali Mabkhout was «Al Hajeri Ahmad Mabkhout» on 2016/17)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "names"))
import build_names as B

ED = {"seasons": [
    {"season": "2016/2017", "champion": {"fotmob": 102101, "name": "الجزيرة"}, "runner_up": {"fotmob": 9001, "name": "Al-Shabab Al-Arabi"},
     "table": [[1, 102101, "الجزيرة", 26], [8, 9001, "Al-Shabab Al-Arabi", 26], [11, None, "Emirates", 26]],
     "top_scorers": [{"rank": 1, "fotmob": 170716, "name": "Al Hajeri Ahmad Mabkhout", "value": "32"}, {"rank": 2, "fotmob": 465033, "name": "فابيو ليما", "value": "25"},
                     {"rank": 3, "fotmob": None, "name": "Zoheir Bakhit", "value": "22"}],
     "best_player": [{"rank": 1, "fotmob": 201165, "name": "Omar Abdulrahman", "value": None}], "motm": [[170716, "Al Hajeri Ahmad Mabkhout", 3]]}]}


def test_latin_named_players_with_a_fotmob_id_join_the_pool():
    got = B.graph_players(ED, 538)
    assert sorted(got) == ["170716", "201165"]                      # Arabic already, or no FotMob id: left out
    assert got["170716"] == {"name": "Al Hajeri Ahmad Mabkhout", "teams": [], "country": None, "ages": [], "comps": [538], "uae": True}


def test_latin_named_clubs_join_the_clubs_pool():
    got = B.graph_clubs(ED, 538)
    assert sorted(got) == ["9001"] and got["9001"]["name"] == "Al-Shabab Al-Arabi" and got["9001"]["club"] is True


def test_the_players_of_the_old_matches_join_the_pool():
    mf = {"matches": [{"id": "2253440", "comp": 538, "ev": [[19, 0, "yellow", "h", "Hmaid Rabei", "794114"], [68, 0, "goal", "a", "مايكل", "71419"]],
                       "lu": {"h": [["Khalid Abdullah", "999", "31", 0], ["Old One", "k12", None, 1]]}}]}
    got = B.graph_match_players(mf)
    assert sorted(got) == ["794114", "999"]                          # Arabic already, or no FotMob id: left out
    assert got["999"]["uae"] is True and got["999"]["comps"] == [538]

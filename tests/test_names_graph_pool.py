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


def test_the_old_players_without_a_fotmob_id_join_a_pool_of_their_own():
    people = {"k107599": {"name": "Adnan Al Talyani", "name_ar": "عدنان الطلياني", "born": "1964-10-30", "nat": "الإمارات", "wc": []},
              "k114377": {"name": "Youssouf Atiq", "name_ar": None, "born": None, "nat": None, "wc": []},
              "131661": {"name": "Ismail Matar", "name_ar": None, "born": "1983-04-07", "nat": "الإمارات", "wc": []}}
    mf = {"matches": [{"id": "k1", "comp": 538, "ev": [[31, 0, "goal", "a", "Ali Daei", "k226000"]], "lu": {}}]}
    got = B.people_pool(people, [mf])
    assert sorted(got) == ["k114377", "k226000"]               # Arabic already, or a FotMob id (the players' job): left out
    assert got["k226000"]["uae"] is True and got["k226000"]["historic"] is True and got["k114377"]["ages"] == []
    assert B.people_pool({"k9": {"name": "Old Man", "name_ar": None, "born": "1964-10-30"}}, [])["k9"]["ages"] == [int(B.TODAY[:4]) - 1964]


def test_an_archive_player_born_before_1978_is_not_marked_down_for_it():
    e = {"labels": {"en": "Ali Daei"}, "aliases": [], "occ": [B.FOOTBALLER], "country": [], "dob": 1969, "clubs": []}
    modern = {"name": "Ali Daei", "teams": [], "country": None, "ages": []}
    assert B.score(dict(modern, historic=True), e, {}, {})[0] > B.score(modern, e, {}, {})[0]


def test_tifo_ids_sort_with_the_fotmob_ones():
    assert sorted(["k12", "7", "k3"], key=B.idkey) == ["k3", "7", "k12"]


def test_an_old_player_whose_name_is_arabic_already_is_left_out():
    assert B.people_pool({"k1": {"name": "إيفان ديماس", "name_ar": None}}, []) == {}


def test_the_transfers_players_join_the_pool():
    # 23 Nov 2026: the transfers pages read 91 % in Latin letters: their players were in no pool (young players, new signings)
    from names import build_names as B
    moves = [["2026-11-16", 1687522, "Mohamed Amine Katiba", 2, "Free agent", 102043, "المغربي الفاسي", None, "free", 704925, "MAR", "DM"],
             ["2026-11-16", 1392383, "كارلو سينتيش", 1581, "x", 2, "Free agent", None, "free", 295763, "CRO", "GK"]]
    got = B.transfer_players(moves)
    assert list(got) == ["1687522"] and got["1687522"]["name"] == "Mohamed Amine Katiba" and got["1687522"]["country"] == "MAR"

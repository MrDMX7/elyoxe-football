from graph.award_names import distinct, places

PLACES = {"Canadian Premier League": "في الدوري الكندي الممتاز", "Greek": "في اليونان", "Chelsea F.C.": "في تشيلسي",
          "FIFA": "من فيفا", "The FA": "في إنجلترا"}


def test_a_shared_name_gets_the_league_or_country_of_its_award():
    got = distinct([(1, "Canadian Premier League Awards — Player of the Year", "لاعب العام"),
                    (2, "Greek football PSAP awards — Best Player of the Season Award", "لاعب العام"),
                    (3, "Chelsea F.C. Player of the Season — Young Player of the Year", "لاعب العام")], PLACES)
    assert got == {1: "لاعب العام في الدوري الكندي الممتاز", 2: "لاعب العام في اليونان", 3: "لاعب العام في تشيلسي"}


def test_a_name_held_once_is_left_alone():
    assert distinct([(1, "Greek football PSAP awards — Best Player", "لاعب العام"), (2, "Ballon d'Or", "الكرة الذهبية")], PLACES) == \
        {1: "لاعب العام", 2: "الكرة الذهبية"}


def test_awards_of_one_body_part_by_what_their_english_name_says():
    got = distinct([(1, "The FA Women's Football Awards — Players' Player of the Year", "لاعب العام"),
                    (2, "The FA Women's Football Awards — International Young Player of the Year", "لاعب العام"),
                    (3, "Greek football PSAP awards — Best Foreign Player of the Season Award", "لاعب الموسم"),
                    (4, "Greek football PSAP awards — Best Young Player of the Season Award", "لاعب الموسم")], PLACES)
    assert got[1] == "لاعب العام في إنجلترا للسيدات باختيار اللاعبين"
    assert got[2] == "لاعب العام في إنجلترا للسيدات للشباب"
    assert got[3] == "لاعب الموسم في اليونان للأجانب"
    assert got[4] == "لاعب الموسم في اليونان للشباب"


def test_a_place_the_name_already_says_is_not_repeated():
    got = distinct([(1, "FIFA World Player of the Year", "لاعب العام من فيفا"), (2, "FIFA World Player of the Year — Women", "لاعب العام من فيفا")], PLACES)
    assert got == {1: "لاعب العام من فيفا", 2: "لاعب العام من فيفا للسيدات"}


def test_what_no_rule_parts_keeps_no_arabic_name_rather_than_a_shared_one():
    got = distinct([(1, "Golden Foot — Winners", "القدم الذهبية"), (2, "Golden Foot — Legends", "القدم الذهبية")], PLACES)
    assert got == {1: None, 2: None}


def test_no_arabic_name_stays_none():
    assert distinct([(1, "A-League Men Coach of the Year", None), (2, "A-League Men Goal of the Year", None)], PLACES) == {1: None, 2: None}


def test_the_catalogue_in_awards_yaml_loads():
    p = places()
    assert p["Greek"] == "في اليونان" and all(v.startswith(("في ", "من ")) for v in p.values())

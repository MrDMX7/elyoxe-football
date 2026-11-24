"""db/rsssf.league_rounds: the league's matches round by round from an RSSSF season page — the date from the round's
heading, the score, and the scorers in brackets in either of RSSSF's two shapes (2003/04: «Name 3, 44; Name 81»,
1999/2000: «Name (12'; 64') - Name (52')»)."""
from db import rsssf as R

UAE04 = """United Arab Emirates 2003/04

Round 1 [Jan 25]

Group 1
Al-Nasr       0-5 Al-Ain       [Isaac Nassib 3, 44, Rodrigo Mendes 81, Ali Al-Wahibi 90, Mohamed Omar 92]
Al-Khaleej    1-4 Al-Shabab    [Renato Oliveira 20; Walid Obaid 9, Salem Saad 56, 67, Giraldo 82]
Group 2
Al-Ittihad    0-0 Al-Wasl

Round 3 [Feb 5]
Sharjah       1-2 Al-Shabab    [Abdulrahman Fadhel 78og; Giraldo 68, Jadilson 88]

Round 4
Group 1 [Feb 22]
Al-Shabab     1-0 Al-Jazeera   [Giraldo 89]

PRESIDENT CUP 2004
Al-Ain        3-0 Al-Wasl      [x 1, 2, 3]
"""

UAE00 = """United Arab Emirates 1999/2000

Round 1 [Sep 22]
Wahda                5-2 Bani Yas
  [Adib Obaid (12'; 64'), Dane Fayne (21'),Haydar Ali (30'), Abdulrahim
   Juma'a (74') - Campo Romeo (52'; 85')]
Round 2 [Jan 8]
Wasl                 2-3 Ahly
  [Nasser Eissa (26'), Zoheir Bakhit (53') - Rashid Bin-Mahmoud (4'; 49'; 67')]
"""


def test_round_by_round_with_dates_and_scorers():
    ms = R.league_rounds(UAE04, "United Arab Emirates 2003/04")
    assert [(m[0], m[1], m[2], m[3], m[4]) for m in ms] == [
        ("2004-01-25", "Al-Nasr", "Al-Ain", 0, 5), ("2004-01-25", "Al-Khaleej", "Al-Shabab", 1, 4), ("2004-01-25", "Al-Ittihad", "Al-Wasl", 0, 0),
        ("2004-02-05", "Sharjah", "Al-Shabab", 1, 2), ("2004-02-22", "Al-Shabab", "Al-Jazeera", 1, 0)]       # the cup after the heading is not the league
    assert ms[0][5] == [["a", "Isaac Nassib", 3, "goal"], ["a", "Isaac Nassib", 44, "goal"], ["a", "Rodrigo Mendes", 81, "goal"],
                        ["a", "Ali Al-Wahibi", 90, "goal"], ["a", "Mohamed Omar", 92, "goal"]]
    assert ms[1][5][0] == ["h", "Renato Oliveira", 20, "goal"] and len(ms[1][5]) == 5
    assert ms[3][5][0] == ["h", "Abdulrahman Fadhel", 78, "own_goal"]
    assert ms[2][5] == []


def test_the_other_shape_and_a_scorers_line_that_wraps():
    ms = R.league_rounds(UAE00, "United Arab Emirates 1999/2000")
    assert [(m[0], m[1], m[2], m[3], m[4]) for m in ms] == [("1999-09-22", "Wahda", "Bani Yas", 5, 2), ("2000-01-08", "Wasl", "Ahly", 2, 3)]
    assert [g[1] for g in ms[0][5]] == ["Adib Obaid", "Adib Obaid", "Dane Fayne", "Haydar Ali", "Abdulrahim Juma'a", "Campo Romeo", "Campo Romeo"]
    assert ms[1][5][-1] == ["a", "Rashid Bin-Mahmoud", 67, "goal"]


def test_scorers_that_do_not_add_up_to_the_score_are_left_out():
    ms = R.league_rounds("X 2003/04\n\nRound 1 [Jan 25]\nA   2-0 B   [Only One 5]\n", "X 2003/04")
    assert ms[0][3:5] == (2, 0) or ms[0][3:5] == [2, 0]
    assert ms[0][5] == []


def test_the_league_ends_where_the_cups_or_the_promotions_begin():
    page = ("X 1999/00\n\nRound 1 [Sep 22]\nWahda   5-0 Bani Yas\n\nPromoted: Sharjah and Al-Ahly (Fujeira)\n\nCups 1999/2000\n\nFederation Cup\n"
            "Group A\nRound 1 [Sep 22]\nWahda   3-0 Ittihad\n")
    assert [m[1:3] for m in R.league_rounds(page, "X 1999/00")] == [["Wahda", "Bani Yas"]]
    page2 = "X 2001/02\n\nRound 1 [Sep 22]\nAin   1-0 Nasr\n\nSuper Cup 2002 (between Top-4 league)\n\nSemifinals\nAin   2-0 Wasl\n"
    assert len(R.league_rounds(page2, "X 2001/02")) == 1
    page3 = "X 1998/99\n\nRound 1 [Sep 22]\nAin   1-0 Nasr\n\nEmir's Cup\n\nQuarterfinals\nAin   2-0 Wasl\n"
    assert len(R.league_rounds(page3, "X 1998/99")) == 1


def test_a_table_row_or_a_note_about_relegation_is_not_the_end():
    page = ("X 1999/00\n\nTable:\n 1.Al-Ain      22 14  4  4  41-20  46\n12.Al-Khaleej  22  4  4 14  21-54  16  Relegated\n"
            "    no relegation this season\n\nRound 1 [Sep 22]\nWahda   5-0 Bani Yas\n\nCups 1999/2000\nRound 1 [Sep 22]\nWahda   3-0 Ittihad\n")
    assert [m[1:3] for m in R.league_rounds(page, "X 1999/00")] == [["Wahda", "Bani Yas"]]


def test_a_match_lines_short_name_is_its_seasons_table_name():
    names = ["Al-Shabab", "Al-Sha'ab", "Ras Al-Khaima", "Al-Ahly (Fujeira)", "Al-Ahly", "Al-Khaleej", "Al-Wasl", "Al-Ittihad (Kalba)"]
    assert R.table_name("Shabab", names) == "Al-Shabab"
    assert R.table_name("Sha'ab", names) == "Al-Sha'ab"
    assert R.table_name("R Khaima", names) == "Ras Al-Khaima"
    assert R.table_name("Ahly F", names) == "Al-Ahly (Fujeira)"
    assert R.table_name("Khaleej", names) == "Al-Khaleej"
    assert R.table_name("Ahly", names) == "Al-Ahly"                       # the same key beats a longer name it starts
    assert R.table_name("Nowhere", names) == "Nowhere"


def test_one_name_in_two_tables_spelled_two_ways_is_one_row():
    names = ["Al Ain", "Al-Ain", "Al Ahly", "Al-Ahly", "Bani Yas"]
    assert R.table_name("Ain", names) in ("Al Ain", "Al-Ain")
    assert R.table_name("Ahly", names) in ("Al Ahly", "Al-Ahly")


def test_a_date_that_does_not_exist_is_not_kept():
    page = "X 2001/02\n\nRound 1 [Feb 30]\nAin   1-0 Nasr\nRound 2 [Mar 3]\nWasl   2-0 Ahli\n"
    assert [m[0] for m in R.league_rounds(page, "X 2001/02")] == ["2002-03-03"]


def test_a_date_under_a_match_is_no_scorer_list():
    """Algeria 2006/07: «OM Ruisseau 1-0 JS Kabylie» then «[Mar 15]», the replay's date: 496 goals by «Mar», «Dec», «Feb»"""
    assert R._scorers("[Mar 15]", 1, 0) == []
    assert R._scorers("[Feb 24, 25?]", 2, 0) == []
    assert R._scorers("[Marcos 15]", 1, 0) == [["h", "Marcos", 15, "goal"]]


def test_an_unknown_scorer_and_an_own_goal_are_goals_with_no_name():
    """Iraq 2004/05: «[Khalid Mushir 17, Jassim M. Sulaiman 58; ? 30]», «[..., own goal 37; Amir Mushrif 27]»"""
    assert R._scorers("[Khalid Mushir 17, Jassim M. Sulaiman 58; ? 30]", 2, 1)[-1] == ["a", None, 30, "goal"]
    assert R._scorers("[Khalid Mushir 10pen, own goal 37; Amir Mushrif 27]", 2, 1)[1] == ["h", None, 37, "own_goal"]


def test_an_own_goal_written_out_in_the_minutes():
    """«[Fahad Massoud (10' own goal) - Bouri Lah (48')]»: an own goal, not Fahad Massoud's goal"""
    assert R._scorers("[Fahad Massoud (10' own goal) - Bouri Lah (48')]", 1, 1) == [["h", "Fahad Massoud", 10, "own_goal"], ["a", "Bouri Lah", 48, "goal"]]


ALG08 = """Algeria 2007/08

Championnat National Division 1
Coupe Nationale
Championnat Division 2

Championnat National Division 1

Round 1 [Aug 23]
ES Sétif         3-1 MC Oran
JSM Béjaïa       0-0 CR Bélouizdad

Round 2 [Aug 30]
MC Oran          1-1 JSM Béjaïa

Coupe Nationale

Round 1 [Dec 27]
USM Sétif        1-0 MC Oran

Championnat Division 2

Round 1 [Aug 24]
MO Béjaïa        2-0 USM Blida
"""


def test_a_club_with_an_accent_in_its_name_keeps_its_games():
    assert [(r[0], r[1], r[2]) for r in R.league_rounds(ALG08, "Algeria 2007/08")][:2] == [
        ("2007-08-23", "ES Sétif", "MC Oran"), ("2007-08-23", "JSM Béjaïa", "CR Bélouizdad")]


def test_the_french_headings_end_the_league_but_not_in_the_list_of_contents():
    assert len(R.league_rounds(ALG08, "Algeria 2007/08")) == 3
    for h in ("Coupe du Trône", "Championnat Division 3 (Division Inter-Régions)", "Ligue 2", "GNF 2", "Second Level (Division d'Honneur)", "Super Coupe"):
        assert R.LEAGUE_END_FR.match(h), h
    for h in ("Championnat National Division 1", "Ligue 1", "Round 2", "Round 20 [Apr 4]", "Final Table:"):
        assert not R.LEAGUE_END_FR.match(h), h

"""db/world.py: the encyclopedia is men's football (the owner, 23 Nov 2026: «كرة القدم النسائية ماباها»). 214 of its 3,664 clubs
were women's sides (FotMob's «(W)»: Motherwell (W), Fiorentina (W), AFC Toronto (W)) from leagues whose names never say so
(Toppserien, Damallsvenskan, the Northern Super League), with 3,756 players."""
from db import world as W


def test_a_womens_side_and_a_league_of_them_are_left_out():
    assert W.mens([[1, "Motherwell", 1], [2, "Motherwell (W)", 2], [3, "Hibernian", 3]]) == [[1, "Motherwell", 1], [3, "Hibernian", 3]]
    assert W.mens([[2, "Lyn Fotball (W)", 1], [4, "Rosenborg (W)", 2], [5, "Vålerenga", 3]]) == []        # a women's league
    assert W.SKIP.search("Frauen-Bundesliga") and W.SKIP.search("Division 1 Féminine") and W.SKIP.search("Damallsvenskan")

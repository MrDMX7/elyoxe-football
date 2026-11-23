"""graph/load/schochastics.py: the dataset files the defunct countries' leagues under one «ddr» (23 Nov 2026: the Soviet,
Yugoslav and East German leagues, 1936-1992, with the Cup Winners' Cup and the Intercontinental Cup, all one competition;
its clubs read Dinamo Zagreb, Dinamo Moskva, Dynamo Kyiv)."""
from graph.load.schochastics import league_of


def test_the_defunct_countries_leagues_and_cups_are_each_their_own():
    assert league_of("ddr", "national", "YUG", "YUG") == "yugoslavia"
    assert league_of("ddr", "national", "DE", "DE") == "east-germany"
    for cc in ("RU", "UA", "GE", "BY", "AM", "AZ", "KZ", "UZ", "LT", "LV", "EE", "MD", "TJ", "TM", "KG"):
        assert league_of("ddr", "national", cc, "RU") == "soviet-union"
    assert league_of("ddr", "international", "ES", "AR") == "intercontinental-cup-old"
    assert league_of("ddr", "international", "BR", "IT") == "intercontinental-cup-old"
    assert league_of("ddr", "international", "ES", "ENG") == "cup-winners-cup"
    assert league_of("hungary", "national", "HU", "HU") == "hungary"            # every other competition as the dataset names it

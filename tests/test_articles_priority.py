"""news/articles/priority.py: the spec's priority list (owner, spec review: the full list) and every Arab national team."""
from news.articles import priority as P


def test_the_priority_list_holds_the_spec_competitions():
    comps = P.priority_comps()
    for cid in (538, 11027, 9943, 11026,      # UAE league and cups
                536, 9942, 10074,             # Saudi
                535, 519, 9941, 10314,        # Qatar, Egypt
                530, 11840,                   # Morocco
                525, 10622, 9469,             # AFC Champions League Elite (and its qualification), Two
                42, 47, 87, 55, 54, 53):      # UEFA Champions League, the big five
        assert cid in comps, cid


def test_an_arab_national_team_makes_any_match_a_priority():
    assert 5789 in P.arab_teams() and 7795 in P.arab_teams()      # UAE, Saudi Arabia (countries.yaml arab: true)
    assert P.is_priority(114, 5789, 9999)                          # a friendly of the UAE
    assert not P.is_priority(114, 9998, 9999)                      # a friendly of two non-Arab sides
    assert P.is_priority(47, 1, 2)                                 # any Premier League match

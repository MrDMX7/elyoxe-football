"""names/people_bulk.py: Arabic names for the archive's men, in bulk (Wikidata labels by item, then Gemini)."""
from names import people_bulk as P


def test_wikidata_labels_by_item_keep_media_spellings_only():
    rows = [{"p": {"value": "http://www.wikidata.org/entity/Q1"}, "ar": {"value": "آلان سميث"}},
            {"p": {"value": "http://www.wikidata.org/entity/Q2"}, "ar": {"value": "ڤيكتور"}},
            {"p": {"value": "http://www.wikidata.org/entity/Q3"}, "ar": {"value": "Victor"}}]
    assert P.labels(rows) == {"Q1": "آلان سميث"}


def test_the_most_seen_men_go_first():
    pool = {"k1": {"weight": 2}, "k2": {"weight": 30}, "k3": {"weight": 5}}
    assert P.order(pool) == ["k2", "k3", "k1"]

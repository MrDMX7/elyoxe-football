"""names/tm_clubs.py: the Arabic names of the Transfermarkt clubs FotMob never names."""
from names import tm_clubs as T


def test_wikidata_rows_give_an_arabic_name_per_transfermarkt_id_and_bot_spellings_are_refused():
    rows = [{"tm": {"value": "305"}, "ar": {"value": "بورت فايل"}},
            {"tm": {"value": "506"}, "ar": {"value": "يوفنتوس بريمافيرا"}},
            {"tm": {"value": "7"}, "ar": {"value": "ڤيتوريا"}},                    # پ/چ/ڤ/گ: a bot's transliteration, not media's
            {"tm": {"value": "8"}, "ar": {"value": "Club 8"}}]
    assert T.wd_map(rows) == {"305": "بورت فايل", "506": "يوفنتوس بريمافيرا"}

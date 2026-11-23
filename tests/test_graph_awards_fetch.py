import json
from graph import awards_fetch as AF

class FakeHTTP:
    def __init__(self, pages, fail=()):
        self.pages, self.fail, self.calls = pages, set(fail), []
    def get(self, url):
        self.calls.append(url)
        for k, v in self.pages.items():
            if k in url and k not in self.fail:
                return v
        raise OSError("boom " + url)

def test_failed_page_keeps_the_last_copy(tmp_path):
    good = FakeHTTP({"Ballon_d'Or": b"<html>v1</html>"})
    AF.fetch_pages(good, str(tmp_path), ["Ballon d'Or"], max_age_days=0)
    bad = FakeHTTP({}, fail={"Ballon_d'Or"})
    got = AF.fetch_pages(bad, str(tmp_path), ["Ballon d'Or"], max_age_days=0)
    assert got["failed"] == 1 and AF.read_page(str(tmp_path), "Ballon d'Or") == b"<html>v1</html>"

def test_items_resolve_humans_and_tm_ids(tmp_path):
    pp = {"query": {"pages": [{"title": "Lionel Messi", "pageprops": {"wikibase_item": "Q615"}}], "normalized": [{"from": "Lionel_Messi", "to": "Lionel Messi"}]}}
    ent = {"entities": {"Q615": {"labels": {"ar": {"value": "ليونيل ميسي"}, "en": {"value": "Lionel Messi"}},
           "claims": {"P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}], "P569": [{"mainsnak": {"datavalue": {"value": {"time": "+1987-06-24T00:00:00Z"}}}}],
                      "P2446": [{"mainsnak": {"datavalue": {"value": "28003"}}}]}}}}
    http = FakeHTTP({"pageprops": json.dumps(pp).encode(), "wbgetentities": json.dumps(ent).encode()})
    items = AF.resolve(http, str(tmp_path), ["Lionel_Messi"])
    assert items["Lionel_Messi"] == {"qid": "Q615", "human": True, "born": "1987-06-24", "ar": "ليونيل ميسي", "en": "Lionel Messi", "tm_player": "28003", "tm_club": None}


def test_pick_seasons_takes_turns_and_keeps_a_budget():
    links = {"538": ["2025–26_UAE_Pro_League", "2024–25_UAE_Pro_League", "2023–24_UAE_Pro_League"], "536": ["2025–26_Saudi_Pro_League", "2024–25_Saudi_Pro_League"]}
    got = AF.pick_seasons(links, have={"2025–26_UAE_Pro_League"}, budget=3)
    assert got == {"2025–26_UAE_Pro_League": "538", "2024–25_UAE_Pro_League": "538", "2025–26_Saudi_Pro_League": "536", "2024–25_Saudi_Pro_League": "536"}


def test_ar_titles_come_from_arabic_wikipedia(tmp_path):
    http = FakeHTTP({"ar.wikipedia.org/api/rest_v1/page/html/": b"<html>ar</html>"})
    AF.fetch_pages(http, str(tmp_path), ["ar:الدوري الكويتي"], max_age_days=0)
    assert "ar.wikipedia.org" in http.calls[0] and "ar%3A" not in http.calls[0]
    assert AF.read_page(str(tmp_path), "ar:الدوري الكويتي") == b"<html>ar</html>"


def test_ar_links_resolve_through_arabic_wikipedia(tmp_path):
    pp = {"query": {"pages": [{"title": "نادي الكويت", "pageprops": {"wikibase_item": "Q7"}}], "normalized": [{"from": "نادي_الكويت", "to": "نادي الكويت"}]}}
    ent = {"entities": {"Q7": {"labels": {"ar": {"value": "نادي الكويت"}, "en": {"value": "Kuwait SC"}}, "claims": {}}}}
    http = FakeHTTP({"ar.wikipedia.org/w/api.php?action=query": json.dumps(pp).encode(), "wbgetentities": json.dumps(ent).encode()})
    items = AF.resolve(http, str(tmp_path), ["ar:نادي_الكويت"])
    assert items["ar:نادي_الكويت"]["qid"] == "Q7" and items["ar:نادي_الكويت"]["en"] == "Kuwait SC"
    assert not any("en.wikipedia.org" in c for c in http.calls)


def test_a_competition_with_no_wikidata_item_in_its_champions_file_is_named_in_the_config():
    # the Arab Cup (10242) and the Gulf Cup (329): no item in v1/history/champions, so their season pages were never read
    from graph import awards_fetch as AF
    got = AF.with_overrides({"50": "UEFA European Championship"}, {"comp_articles": {10242: "FIFA Arab Cup", 50: "Other"}})
    assert got == {"50": "UEFA European Championship", "10242": "FIFA Arab Cup"}

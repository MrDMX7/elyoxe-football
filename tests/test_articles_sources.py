# tests/test_articles_sources.py
"""news/articles/sources.py with fake fetchers (no network):
- Google News links are decoded and the texts extracted;
- X posts are read as they are;
- official first, at most 3;
- a story whose links all fail keeps its headlines and descriptions, and the counts say so."""
from news.articles import sources as SRC

HTML = "<html><head><meta property='og:image' content='https://img/x.jpg'></head><body><article><p>" + ("خبر كامل. " * 80) + "</p></article></body></html>"
ITEMS = {"a": {"source": "AS", "lang": "es", "tier": "paper", "url": "https://news.google.com/rss/articles/AAA", "title": "t a", "desc": "d a"},
         "b": {"source": "Club", "lang": "en", "tier": "official", "url": "https://x.com/club/status/1", "title": "Official: X joins", "desc": "Official: X joins the club."},
         "c": {"source": "BBC", "lang": "en", "tier": "paper", "url": "https://www.bbc.co.uk/sport/1", "title": "t c", "desc": ""},
         "d": {"source": "Kooora", "lang": "ar", "tier": "paper", "url": "https://www.kooora.com/1", "title": "t d", "desc": ""}}
STORY = {"items": ["a", "b", "c", "d"]}


def test_official_first_three_at_most_texts_and_images():
    got, n = SRC.collect(STORY, ITEMS, resolve=lambda u: "https://as.com/1", fetch_html=lambda u: HTML)
    assert got[0]["source"] == "Club" and got[0]["text"].startswith("Official: X joins") and len(got) == 3
    assert all("خبر كامل" in g["text"] and g["image"] == "https://img/x.jpg" for g in got[1:])
    assert n == {"links": 3, "decoded": 1, "texts": 3}


def test_links_that_cannot_be_read_keep_the_headline_and_description():
    got, n = SRC.collect(STORY, ITEMS, resolve=lambda u: None, fetch_html=lambda u: None)
    web = [g for g in got if g["source"] != "Club"]
    assert web and all(g["text"].startswith("t ") and g["image"] is None for g in web)
    assert n["decoded"] == 0 and n["texts"] == 0

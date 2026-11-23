"""names/site_latin.py: the names the live pages still show in Latin letters, collected for naming (23 Nov 2026)."""
from names import site_latin as SL


def test_latin_spans_counted_the_subtitle_and_entities_handled():
    h = ('<h1>سامي الجابر</h1><p class="muted"><span class="lat">Sami Al-Jaber</span></p>'
         '<li><span class="lat">Mustapha Ghorbal</span></li><li><span class="lat">Mustapha Ghorbal</span></li>'
         '<td><span class="lat">Brighton &amp; Hove Albion</span></td><span class="lat">x</span>')
    assert SL.spans(h) == {"Mustapha Ghorbal": 2, "Brighton & Hove Albion": 1}      # the subtitle under an Arabic name is no gap


def test_pages_to_read_every_small_kind_and_a_sample_of_a_big_one():
    paths = ["/arabs/", "/arabs/coaches/", "/memorable/"] + [f"/p/k{i}/" for i in range(500)]
    got = SL.pages(paths, every=100, sample=20, seed=1)
    assert {"/arabs/", "/arabs/coaches/", "/memorable/"} <= set(got)
    assert sum(1 for p in got if p.startswith("/p/k")) == 20


def test_an_answer_is_kept_only_in_arabic_letters():
    assert SL.accept("مصطفى غربال") == "مصطفى غربال"
    assert SL.accept("  الدوري الألماني تحت 19 ") == "الدوري الألماني تحت 19"
    assert SL.accept("Kooora") is None and SL.accept("") is None and SL.accept("بي BBC") is None


def test_the_pool_skips_what_is_named_most_seen_first():
    seen = {"Al Ain": 3, "Mustapha Ghorbal": 9, "Kooora": 40}
    have = {"Al Ain": {"ar": "العين"}}
    assert SL.todo(seen, have, kept={"Kooora"}) == ["Mustapha Ghorbal"]

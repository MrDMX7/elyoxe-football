from graph.ids import Registry
from graph.load import fjelstul


def test_a_fjelstul_key_tied_through_an_unlinked_wikidata_item_goes_with_it():
    # Mohamed Hamed (FotMob 1596110) once held Salah's Q1354960, so Fjelstul's Salah (P-75890) was tied to him; the names
    # loader unlinks the qid, and the Fjelstul key must not keep Salah's World Cup on the wrong man
    reg = Registry()
    hamed = reg.mint("player", "fotmob", 1596110)
    reg.link("player", "wikidata", "Q1354960", hamed)
    reg.link("player", "fjelstul", "P-75890", hamed)
    reg.unlink("player", "wikidata", "Q1354960")
    fjelstul.stale(reg, "P-75890", "Q1354960")
    assert reg.get("player", "fjelstul", "P-75890") is None
    assert reg.get("player", "fotmob", 1596110) == hamed


def test_a_fjelstul_key_whose_wikidata_item_was_not_unlinked_stays():
    reg = Registry()
    pid = reg.mint("player", "fotmob", 1)
    reg.link("player", "wikidata", "Q1", pid)
    reg.link("player", "fjelstul", "P-1", pid)
    fjelstul.stale(reg, "P-1", "Q1")
    fjelstul.stale(reg, "P-1", None)
    assert reg.get("player", "fjelstul", "P-1") == pid

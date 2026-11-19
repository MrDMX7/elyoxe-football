import json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph import aliases


def setup(tmp_path):
    root = tmp_path
    (root / "names").mkdir()
    (root / "news").mkdir()
    (root / "db" / ".cache").mkdir(parents=True)
    (root / "names" / "players_ar.json").write_text(json.dumps({
        "1572471": {"latin": "Marcos André", "ar": "ماركوس أندريه", "qid": "Q1"},
        "900": {"latin": "Hugo", "ar": "هوغو", "qid": None},
        "901": {"latin": "Serginho", "ar": "سيرجينيو", "qid": "Q2"}}), encoding="utf-8")
    (root / "names" / "players_ar_aka.json").write_text(json.dumps({"1572471": {"qid": "Q1", "aka": ["ماركوس اندريه"]}}), encoding="utf-8")
    (root / "news" / "aliases.yaml").write_text("people:\n  ماركوس مايا: Marcos André\n  Marcos: Marcos André\n  هوجو نيتو: Hugo\n", encoding="utf-8")
    (root / "db" / ".cache" / "wd_ar.json").write_text(json.dumps({
        "Q2": {"label": "سيرجينيو", "aliases": ["سيرجيو بيريرا", "سيرجيو"], "at": "2026-11-19"}}), encoding="utf-8")
    m = root / "mirror" / "s365"
    m.mkdir(parents=True)
    (m / "index.json").write_text(json.dumps({"teams": [[50, "العين", "Al Ain", 1, 102117]],
                                              "players": [[7, "سيرجينيو ريبيرو", "Serginho", 50], [8, "هوغو", "Hugo", 99]]}), encoding="utf-8")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    for fid, name, ar in ((1572471, "Marcos André", "ماركوس أندريه"), (900, "Hugo", "هوغو"), (901, "Serginho", "سيرجينيو")):
        pid = reg.mint("player", "fotmob", fid)
        G.put("player", {"pid": pid, "name": name, "name_ar": ar}, "fotmob")
        G.xref("player", pid, "fotmob", fid, "fotmob-native")
    ain = reg.mint("team", "fotmob", 102117)
    G.xref("team", ain, "fotmob", 102117, "fotmob-native")
    m1 = reg.mint("match", "fotmob", 1)
    G.put("match", {"mid": m1, "date": "2026-11-01"}, "fotmob")
    G.many("appearance", [{"mid": m1, "pid": reg.get("player", "fotmob", 901), "tid": ain, "played": 1}], "fotmob")
    G.c.commit()
    return G, Sources(str(root), mirror=str(root / "mirror"), s3=False)


def test_every_arabic_form_per_fotmob_player(tmp_path):
    G, S = setup(tmp_path)
    out = aliases.build(G, S, learned={"900": {"هوجو نيتو": {"n": 3}}, "901": {"سيرجيو": {"n": 1}}})
    p = out["players"]
    assert set(p["1572471"]) == {"ماركوس أندريه", "ماركوس اندريه", "ماركوس مايا"}
    assert set(p["900"]) == {"هوغو", "هوجو نيتو"}                          # his own one-word name stays
    assert set(p["901"]) == {"سيرجينيو", "سيرجيو بيريرا", "سيرجينيو ريبيرو"}   # «سيرجيو» alone is only a first name: out
    assert "generated" in out


def test_365_names_need_the_same_club(tmp_path):
    G, S = setup(tmp_path)
    p = aliases.build(G, S, learned={})["players"]
    assert "سيرجينيو ريبيرو" in p["901"]                                    # his club in 365 is his FotMob club
    assert not any(f for f in p.get("900", []) if f != "هوغو" and f != "هوجو نيتو")   # 365's «هوغو» is another club's Hugo


def test_wikidata_arabic_forms_are_fetched_once_a_month(tmp_path):
    from graph import fetch

    class H:
        calls = 0

        def get(self, url):
            H.calls += 1
            return json.dumps({"entities": {"Q2": {"labels": {"ar": {"value": "سيرجينيو"}}, "aliases": {"ar": [{"value": "سيرجيو بيريرا"}]}}}}).encode()

    (tmp_path / "db" / ".cache").mkdir(parents=True)
    S = Sources(str(tmp_path), s3=False)
    got = fetch.wikidata_ar(S, ["Q2"], http=H())
    assert got["Q2"]["label"] == "سيرجينيو" and got["Q2"]["aliases"] == ["سيرجيو بيريرا"]
    fetch.wikidata_ar(S, ["Q2"], http=H())
    assert H.calls == 1


def test_an_arabic_name_held_in_name_counts(tmp_path):
    G, S = setup(tmp_path)
    reg = Registry()
    pid = 9999
    G.put("player", {"pid": pid, "name": "علي أحمد مبخوت"}, "fotmob")       # the scorers file gave the Arabic name as the name
    G.xref("player", pid, "fotmob", 170716, "fotmob-native")
    assert aliases.build(G, S, learned={})["players"]["170716"] == ["علي أحمد مبخوت"]

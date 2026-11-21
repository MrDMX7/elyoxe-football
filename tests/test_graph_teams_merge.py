from graph import build
from graph.db import Graph
from graph.load import teams as T

ALIAS = {T.fold("Sporting KC"): T.fold("Sporting Kansas City"), T.fold("Hearts"): T.fold("Heart of Midlothian")}


def t(tid, name, country, fm, kind=None):
    return (tid, name, country, kind, fm)


def test_accent_and_noise_fold_into_the_fotmob_record():
    teams = [t(1, "Stabæk", "Norway", True), t(2, "Stabaek", "Norway", False), t(3, "Najran SC", "Saudi Arabia", True),
             t(4, "Najran", "Saudi Arabia", False)]
    assert T.pairs(teams) == [(2, 1), (4, 3)]


def test_alias_list_for_abbreviations():
    teams = [t(1, "Sporting Kansas City", "USA", True), t(2, "Sporting KC", "USA", False),
             t(3, "Heart of Midlothian", "Scotland", True), t(4, "Hearts", "Scotland", False)]
    assert T.pairs(teams, alias=ALIAS) == [(2, 1), (4, 3)]


def test_never_two_fotmob_records_nor_across_countries():
    teams = [t(1, "Al Nasr", "Egypt", True), t(2, "Al Nasr", "Saudi Arabia", True), t(3, "Al-Nasr", "UAE", False)]
    assert T.pairs(teams) == []


def test_no_prefix_no_last_word_no_reserves_no_teams_that_met():
    teams = [t(1, "Olympiakos", "Greece", True), t(2, "Olympiakos Volou", "Greece", False),
             t(3, "AC Milan", "Italy", True), t(4, "Inter Milan", "Italy", False),
             t(5, "Benfica", "Portugal", True), t(6, "Benfica (W)", "Portugal", False), t(7, "Benfica B", "Portugal", False),
             t(8, "Metalist Kharkiv", "Ukraine", True), t(9, "Metalist 1925 Kharkiv", "Ukraine", False),
             t(10, "Paris FC", "France", True), t(11, "Paris", "France", False),
             t(12, "Internacional", "Brazil", True), t(13, "Internacional-BA", "Brazil", False), t(14, "Santa Cruz (AL)", "Brazil", False),
             t(15, "Parnahyba", "Brazil", True), t(16, "Parahyba", "Brazil", False)]
    assert T.pairs(teams, met={(10, 11)}, never={(T.fold("Parahyba"), T.fold("Parnahyba"))}) == []
    assert (T.fold("Parahyba FC"), T.fold("Parnahyba")) in T.apart()


def test_two_fotmob_fits_stay_apart():
    teams = [t(1, "Al Ahli", "Saudi Arabia", True), t(2, "Al-Ahli", "Saudi Arabia", True), t(3, "Al Ahli", "Saudi Arabia", False)]
    assert T.pairs(teams) == []


def test_historic_uae_clubs_and_era_names_stay_separate():
    teams = [t(102119, "Shabab Al Ahli", "UAE", True), t(5, "Shabab Al-Ahli", "UAE", False),
             t(7, "Al Shabab", "UAE", False), t(8, "Al-Shabab", "UAE", True)]
    assert T.pairs(teams, guard={T.fold("Al Shabab")}, era={102119}) == []
    g, e = T.guarded()
    assert T.fold("Al-Shabab Al-Arabi") in g and 102119 in e


def test_yaml_aliases_read():
    a = T.aliases()
    assert a[T.fold("Sporting KC")] == T.fold("Sporting Kansas City")
    assert a[T.fold("America Mineiro")] == T.fold("America MG")
    assert a[T.fold("Emirates")] == T.fold("Emirates Club")
    assert not any(k in a for k in (T.fold("Al Shabab"), T.fold("Dubai"), T.fold("Al Ahli")))


def test_load_remaps_and_settles_the_honour_conflict(tmp_path):
    G = Graph(str(tmp_path / "t.db"))
    G.c.executemany("INSERT INTO team(tid, name, country, src) VALUES(?,?,?,?)",
                    [(30, "Sporting Kansas City", "USA", "fotmob"), (8674, "Sporting KC", "USA", "s365"),
                     (31, "LA Galaxy", "USA", "fotmob")])
    G.xref("team", 30, "fotmob", "6604", "native")
    G.xref("team", 31, "fotmob", "6637", "native")
    G.c.execute("INSERT INTO honour(eid, kind, rank, tid, src) VALUES(1, 'champion', 1, 8674, 's365')")
    G.conflict("honour", 1, "champion", "8674", "s365", "30", "fotmob")
    G.conflict("honour", 2, "champion", "31", "s365", "30", "fotmob")
    out = T.load(G, None, None)
    assert out == {"merged": 1, "conflicts_settled": 1}
    assert G.c.execute("SELECT tid FROM honour").fetchall() == [(30,)]
    assert G.c.execute("SELECT count(*) FROM team WHERE tid=8674").fetchone()[0] == 0
    assert G.c.execute("SELECT tifo_id FROM conflict").fetchall() == [(2,)]


def test_build_runs_teams_after_people_before_settle():
    o = build.ORDER
    assert o.index("people") < o.index("teams") < o.index("settle")

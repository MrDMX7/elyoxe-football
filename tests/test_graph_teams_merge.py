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


DUBAI = [("UAE", ["rsssf-name:uae|Dubai", "sch:Dubai (United Arab Emirates)"])]
KEYED = {"rsssf-name:uae|Dubai": 19755, "sch:Dubai (United Arab Emirates)": 19770, "fotmob:102119": 659}


def dubai(*extra):
    return [t(659, "Shabab Al Ahli", "UAE", True), t(19755, "Dubai", "UAE", False), t(19770, "Dubai", "UAE", False), *extra]


def test_alias_list_joins_two_non_fotmob_records_into_the_lower_id():
    # the old Dubai CSC, once from RSSSF and once from schochastics: one club, kept under the lower Tifo id
    assert T.pairs(dubai(), guard={T.fold("Dubai")}, era={659}, keyed=KEYED, groups=DUBAI) == [(19770, 19755)]
    # the name rule alone never joins them (no FotMob record), and never folds Dubai into Shabab Al Ahli (the 2017 merger)
    assert T.pairs(dubai(), guard={T.fold("Dubai")}, era={659}) == []
    assert T.pairs(dubai(), era={659}) == []


def test_explicit_join_refused_across_countries_with_fotmob_or_when_they_met():
    assert T.pairs(dubai(), keyed=KEYED, groups=[("KSA", DUBAI[0][1])]) == []
    assert T.pairs(dubai(), keyed=KEYED, groups=[("UAE", ["fotmob:102119", "rsssf-name:uae|Dubai"])]) == []
    assert T.pairs(dubai(), met={(19755, 19770)}, keyed=KEYED, groups=DUBAI) == []
    assert T.pairs(dubai(), keyed=KEYED, groups=[("UAE", ["rsssf-name:uae|Dubai", "sch:nobody"])]) == []


def test_explicit_join_chains_into_fotmob_when_the_kept_record_folds():
    # 9's name alone folds into nothing; joined to 5, it goes where 5 goes
    teams = [t(1, "Al Jaish", "IRQ", True), t(5, "Al-Jaish", "IRQ", False), t(9, "Army Club Baghdad", "IRQ", False)]
    keyed = {"rsssf-name:iraq|Al-Jaish": 5, "sch:Al Jaish (Iraq)": 9}
    assert T.pairs(teams, keyed=keyed, groups=[("IRQ", list(keyed))]) == [(5, 1), (9, 1)]


def test_yaml_joins_read():
    g = dict((tuple(k), c) for c, k in T.joins())
    assert g[tuple(DUBAI[0][1])] == "UAE"
    assert all(len(k) >= 2 and c for c, k in T.joins())
    assert not any("102119" in x or "fotmob:" in x for _, k in T.joins() for x in k)


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


def test_transfermarkts_national_team_record_folds_into_fotmobs_national_team():
    from graph.load.teams import national_pairs
    # (tid, name, country, kind, fotmob): FotMob holds Mexico twice (370 with 1,015 matches, 4192 with none)
    teams = [(370, "Mexico", None, "national", True), (4192, "Mexico", None, "national", True), (17835, "Mexico", None, None, False),
             (1320, "UAE", None, "national", True), (18779, "United Arab Emirates", None, None, False),
             (500, "Mexico", "MEX", "club", False), (18275, "Serbia", None, None, False)]
    played = {370: 1015, 4192: 0, 1320: 620, 17835: 25, 18779: 4, 500: 30, 18275: 12}
    share = {17835: 0.72, 18779: 1.0, 500: 0.0, 18275: 0.67}        # of its games, against national teams
    assert national_pairs(teams, frozenset(), played, share) == [(17835, 370), (18779, 1320)]   # Serbia: no FotMob record to join


def test_a_national_record_that_met_fotmobs_is_another_team():
    from graph.load.teams import national_pairs
    teams = [(370, "Mexico", None, "national", True), (17835, "Mexico", None, None, False)]
    assert national_pairs(teams, frozenset({(370, 17835)}), {370: 9, 17835: 9}, {17835: 1.0}) == []

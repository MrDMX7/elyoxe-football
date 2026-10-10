"""Phase 1 of the transfers on the site (spec docs/superpowers/specs/2026-10-09-transfers-design.md): the ledger
v1/transfers/all.json -> /transfers/, /transfers/<league>/ and the club's «انتقالات هالموسم» (site/lib/transfers.cjs)."""
import json, os, shutil, subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")

# [date, pid, name, from id, from, to id, to, fee, kind, mv, cc, pos]
MOVES = [["2026-09-05", 2, "محمد", 20, "B", 30, "C", 3000000, "fee", None, "EGY", "DM"],
         ["2026-08-20", 3, "Kane", 30, "C", 40, "D", 90000000, "fee", None, "ENG", "ST"],
         ["2026-08-01", 1, "سالم", 10, "A", 20, "B", None, "free", None, "UAE", None],
         ["2026-07-15", 4, "Loanee", 20, "B", 50, "E", None, "loan", None, "BRA", None],
         ["2026-03-01", 5, "Old", 20, "B", 60, "F", 1000000, "fee", None, "KSA", None]]


def run(js):
    r = subprocess.run(["node", "-e", "const T = require(process.argv[1] + '/site/lib/transfers.cjs');\n" + js, ROOT],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_season_moves_and_a_clubs_window():
    out = run(f"""const M = {json.dumps(MOVES)}; const s = T.season(M, "2026-06-01");
console.log(JSON.stringify([s.length, T.forClub(s, 20)]));""")
    n, c = out
    assert n == 4                                                      # March is last season
    assert [m[1] for m in c["in"]] == [1] and [m[1] for m in c["out"]] == [2, 4]
    assert c["spent"] == 0 and c["received"] == 3000000


def test_top_fees_arab_players_and_a_league():
    out = run(f"""const M = {json.dumps(MOVES)}; const s = T.season(M, "2026-06-01");
console.log(JSON.stringify([T.top(s, 2).map(m => m[1]), T.arabs(s).map(m => m[1]), T.league(s, {{ 20:1, 30:1 }}).map(m => m[1])]));""")
    assert out == [[3, 2], [2, 1], [2, 3, 1, 4]]


def test_a_move_row_in_arabic_with_links_and_fee():
    out = run(f"""const M = {json.dumps(MOVES)};
console.log(JSON.stringify([T.row(M[1]), T.row(M[2]), T.row(M[3]), T.row(["2026-08-01", 9, "X", 2, "Free agent", 20, "B", null, "", null, null, null])]));""")
    kane, salem, loan, freeagent = out
    assert '<a href="/p/3/">' in kane and 'href="/t/30/"' in kane and 'href="/t/40/"' in kane and "€90" in kane and "مليون" in kane
    assert "انتقال حر" in salem and "سالم" in salem and "<span class=\"lat\">Kane</span>" not in salem
    assert '<span class="lat">Kane</span>' in kane                    # a Latin name is marked as Latin
    assert "إعارة" in loan
    assert "لاعب حر" in freeagent and 'href="/t/2/"' not in freeagent   # FotMob's «free agent» club (id 2) is no club


def test_the_sites_arabic_names_win():
    out = run(f"""const M = {json.dumps(MOVES)}; console.log(JSON.stringify(T.row(M[1], {{ pname:id => id === 3 ? "هاري كين" : null, cname:id => id === 40 ? "دي" : null }})));""")
    assert "هاري كين" in out and ">لـدي<" in out and "Kane" not in out


def test_the_club_section_says_spent_and_received():
    out = run(f"""const M = {json.dumps(MOVES)}; console.log(JSON.stringify(T.clubSection(T.forClub(T.season(M, "2026-06-01"), 20))));""")
    assert "جاه" in out and "راح" in out and "€3" in out
    assert run("console.log(JSON.stringify(T.clubSection(T.forClub([], 20))))") == ""


def test_the_preposition_reads_right():
    """«للهلال» not «لـالهلال» (the build's «لـال» fix cannot reach across the link), and no club is just «بدون نادي»."""
    out = run(f"""const a = ["2026-09-03", 7, "غابرييل", 9825, "أرسنال", 8, "الهلال", 70000000, "fee", null, "BRA", null];
const b = ["2026-08-01", 8, "بنزيما", 8, "الهلال", 2, "Free agent", null, "free", null, "FRA", null];
console.log(JSON.stringify([T.row(a), T.row(a, {{ side:"out" }}), T.row(b), T.row(b, {{ side:"out" }}), T.row(b, {{ side:"in" }})]));""")
    both, out_, free, free_out, free_in = out
    assert ">للهلال</a>" in both and "لـ<a" not in both and "لـال" not in both
    assert ">للهلال</a>" in out_
    assert "صار بدون نادي" in free and "لـبدون" not in free and "لبدون" not in free
    assert "صار بدون نادي" in free_out and "انتقال حر" not in free_out   # «صار بدون نادي انتقال حر» says it twice
    assert "من <a" in free_in and ">الهلال<" in free_in


RUM = [{"k": "fm1", "pid": 7, "name": "مارتينيلي", "from": [9825, "أرسنال"], "to": [8, "الهلال"], "first": "2026-08-01", "last": "2026-09-11", "prob": "High",
        "fee": 70000000, "stage": "agreed", "stories": [["s1", "اتفاق بين الهلال وأرسنال", "2026-09-11", "Fabrizio"]], "out": None},
       {"k": "n11", "pid": 11, "name": "إيليفن", "from": None, "to": None, "first": "2026-09-12", "last": "2026-09-12", "prob": None, "fee": None,
        "stage": "talks", "stories": [], "out": None},
       {"k": "fm3", "pid": 9, "name": "ناين", "from": [30, "C"], "to": [8, "الهلال"], "first": "2026-07-01", "last": "2026-07-20", "prob": "Low", "fee": None,
        "stage": None, "stories": [], "out": "no"}]


def test_a_rumour_row_says_how_far_it_got_and_who_said_it():
    a, b, c = run(f"const R = {json.dumps(RUM)}; console.log(JSON.stringify(R.map(r => T.rumourRow(r))));")
    assert '<a href="/p/7/">مارتينيلي</a>' in a and "للهلال" in a and "اتفاق" in a and "Fabrizio" in a and "اتفاق بين الهلال وأرسنال" in a
    assert "مفاوضات" in b and "صار بدون نادي" not in b and "من " not in b.split("</a>", 1)[1][:30]
    assert "ما صدقت" in c and "احتمال ضعيف" in c


def test_rumours_about_a_club_or_a_player_open_first():
    out = run(f"const R = {json.dumps(RUM)}; console.log(JSON.stringify([T.rumoursOf(R, {{ club:8 }}).map(r => r.k), T.rumoursOf(R, {{ pid:11 }}).map(r => r.k), T.rumoursOf(R, {{ club:8, open:1 }}).map(r => r.k)]));")
    assert out == [["fm1", "fm3"], ["n11"], ["fm1"]]


def test_contracts_ending_by_next_june():
    P = {"1": {"name": "A", "team": 8, "contract": "2027-06-30", "pos": "Keeper"}, "2": {"name": "B", "team": 8, "contract": "2028-06-30"},
         "3": {"name": "C", "team": 9, "contract": "2026-12-31"}, "4": {"name": "D", "team": 9, "contract": None}, "5": {"name": "E", "team": 9, "contract": "2026-09-30"}}
    out = run(f"console.log(JSON.stringify(T.expiring({json.dumps(P)}, '2026-10-09')))")
    assert out == {"until": "2027-06-30", "players": [["3", "C", 9, "2026-12-31"], ["1", "A", 8, "2027-06-30"]]}


def test_who_spent_most_clubs_and_leagues():
    out = run(f"""const M = {json.dumps(MOVES)}; const s = T.season(M, "2026-06-01");
const r = T.spending(s, {{ "20":["B", 536], "30":["C", 536], "40":["D", 47], "10":["A", 536] }});
console.log(JSON.stringify([r.clubs.map(c => [c.id, c.spent, c.received]), r.leagues]));""")
    clubs, leagues = out
    assert clubs[:2] == [["40", 90000000, 0], ["30", 3000000, 90000000]]       # by money spent
    assert leagues == [["47", 90000000, 0], ["536", 3000000, 93000000]]      # a move inside one league counts on both sides


def test_players_without_a_club_now():
    M = [["2026-09-03", 8, "بنزيما", 8, "الهلال", 2, "Free agent", None, "free", 15000000, "FRA", None],
         ["2026-08-01", 9, "X", 5, "E", 2, "Free agent", None, "free", None, None, None],
         ["2026-09-01", 9, "X", 2, "Free agent", 6, "F", None, "free", None, None, None],          # signed again: not free
         ["2026-07-01", 10, "Y", 7, "G", None, None, None, "", 500000, None, None]]
    out = run(f"console.log(JSON.stringify(T.freeAgents({json.dumps(M)}).map(m => [m[1], m[0]])))")
    assert out == [[8, "2026-09-03"], [10, "2026-07-01"]]                     # the dearest first


def test_which_sources_came_true():
    """Owner 2026-10-10 item 8: «أصدق مصدر»: every closed rumour counts for each source that carried it (FotMob's source and the
    news stories'); a source needs 3 closed rumours to be ranked, by the share that came true."""
    R = [{"k": "a", "src": "Sky", "stories": [["s", "t", "2026-09-01", "Fabrizio"]], "out": "done"},
         {"k": "b", "src": "Sky", "stories": [], "out": "no"},
         {"k": "c", "src": "Sky", "stories": [["s2", "t", "2026-09-01", "Fabrizio"]], "out": "done"},
         {"k": "d", "src": None, "stories": [["s3", "t", "2026-09-01", "Fabrizio"]], "out": "done"},
         {"k": "e", "src": "Marca", "stories": [], "out": "no"},
         {"k": "f", "src": "Sky", "stories": [], "out": None}]
    out = run(f"console.log(JSON.stringify(T.sources({json.dumps(R)})))")
    assert out == {"ranked": [["Fabrizio", 3, 3, 0, 0], ["Sky", 3, 2, 1, 1]], "few": [["Marca", 1, 0, 1, 0]]}   # [name, closed, true, not, open]

from graph.awards_wiki import extract, season_label, grid
from lxml import html as LH

def T(body, head="Winners"):
    return f'<html><body><section><h2>{head}</h2><table class="wikitable">{body}</table></section></body></html>'.encode()

PODIUM = T('<tr><th>Year</th><th>Rank</th><th>Player</th><th>Team</th><th>Points</th></tr>'
           '<tr><td rowspan="3">1956</td><td>1st</td><td><a rel="mw:WikiLink" href="./Stanley_Matthews">Stanley Matthews</a></td><td><a rel="mw:WikiLink" href="./Blackpool_F.C.">Blackpool</a></td><td>47</td></tr>'
           '<tr><td>2nd</td><td><a rel="mw:WikiLink" href="./Alfredo_Di_Stéfano">Di Stéfano</a></td><td>Real Madrid</td><td>44</td></tr>'
           '<tr><td>3rd</td><td><a rel="mw:WikiLink" href="./Raymond_Kopa">Kopa</a></td><td>Real Madrid</td><td>33</td></tr>'
           '<tr><td>1957</td><td>1st</td><td><a rel="mw:WikiLink" href="./Alfredo_Di_Stéfano">Di Stéfano</a></td><td>Real Madrid</td><td>72</td></tr>')

def test_season_label():
    assert season_label("1973–74") == "1973/1974" and season_label("2023–24[16]") == "2023/2024"
    assert season_label("2009") == "2009" and season_label("1999–00") == "1999/2000" and season_label("Total") is None

def test_rowspan_year_covers_the_podium():
    t = extract(PODIUM, "Ballon d'Or")
    assert len(t) == 1 and t[0]["kind"] == "winner" and t[0]["who"] == "person"
    rows = t[0]["rows"]
    assert [(r["season"], r["rank"], r["person"], r["value"]) for r in rows[:3]] == [
        ("1956", 1, "Stanley_Matthews", "47"), ("1956", 2, "Alfredo_Di_Stéfano", "44"), ("1956", 3, "Raymond_Kopa", "33")]
    assert rows[0]["team"] == "Blackpool_F.C." and rows[3]["season"] == "1957"

def test_summary_tables_are_skipped():
    wins = T('<tr><th>Player</th><th>Wins</th></tr>' + ''.join(f'<tr><td><a rel="mw:WikiLink" href="./P{i}">P{i}</a></td><td>{i}</td></tr>' for i in range(5)), "Wins by player")
    assert extract(wins, "Ballon d'Or") == []

def test_kind_and_redlink_and_champion_table():
    sc = T('<tr><th>Season</th><th>Player</th><th>Club</th><th>Goals</th></tr>'
           '<tr><td>1973–74</td><td>Saeed Hareb</td><td><a rel="mw:WikiLink" href="./Al_Ahli">Al Ahli</a></td><td></td></tr>'
           '<tr><td>1974–75</td><td><a rel="mw:WikiLink" href="./Suhail_Salim?action=edit&amp;redlink=1">Suhail Salim</a></td><td>Al Ahli</td><td>14</td></tr>'
           '<tr><td>1975–76</td><td><a rel="mw:WikiLink" href="./Ahmed_X">Ahmed X</a></td><td>Al Ain</td><td>12</td></tr>', "Top scorers by season")
    t = extract(sc, "UAE Pro League")[0]
    assert t["kind"] == "top_scorer" and [r["person"] for r in t["rows"]] == [None, None, "Ahmed_X"]
    assert [r["name"] for r in t["rows"][:2]] == ["Saeed Hareb", "Suhail Salim"] and t["rows"][1]["value"] == "14"
    ch = T('<tr><th>Season</th><th>Champion</th><th>Runner up</th></tr>' + ''.join(
        f'<tr><td>197{i}–7{i + 1}</td><td><a rel="mw:WikiLink" href="./C{i}">C{i}</a></td><td><a rel="mw:WikiLink" href="./R{i}">R{i}</a></td></tr>' for i in range(3, 6)), "List of champions")
    c = extract(ch, "UAE Pro League")[0]
    assert c["kind"] == "champion_table" and c["who"] == "team"
    assert (c["rows"][0]["season"], c["rows"][0]["team"], c["rows"][0]["runner_up"]) == ("1973/1974", "C3", "R3")


def L(t):
    return f'<a rel="mw:WikiLink" href="./{t}">{t}</a>'


def test_header_above_a_separator_row_and_style_text():
    h = T('<tr><th>Year</th><th>Rank</th><th>Player</th><th>Team</th><th><style>.x{}</style>Points</th></tr>'
          '<tr><th colspan="5">Ballon d\'Or (1956–2009)</th></tr>'
          + ''.join(f'<tr><td>{y}</td><td>1st</td><td>{L("P" + str(y))}</td><td>T</td><td>9</td></tr>' for y in (1956, 1957, 1958))
          + '<tr><th colspan="5">FIFA Ballon d\'Or (2010–2015)</th></tr>'
          + '<tr><td>2010</td><td>1st</td><td>' + L("Lionel_Messi") + '</td><td>T</td><td>22</td></tr>')
    t = extract(h, "Ballon d'Or")[0]
    assert [r["season"] for r in t["rows"]] == ["1956", "1957", "1958", "2010"] and t["rows"][3]["value"] == "22"


def test_summaries_alltime_nominees_and_best_xi_are_skipped():
    multi = T('<tr><th>Player</th><th>Wins</th><th>Seasons</th></tr>' + ''.join(f'<tr><td>{L("P%d" % i)}</td><td>2</td><td>200{i}–0{i + 1}, 201{i}–1{i + 1}</td></tr>' for i in range(4)), "Multiple winners")
    alltime = T('<tr><th>Rank</th><th>Name</th><th>Club</th><th>Years</th><th>Goals</th></tr>' + ''.join(f'<tr><td>{i}</td><td>{L("P%d" % i)}</td><td>C</td><td>200{i}–</td><td>9{i}</td></tr>' for i in range(4)), "All-time top scorers")
    nominees = T('<tr><th>Year</th><th>Player</th></tr>' + ''.join(f'<tr><td>2006</td><td>{L("P%d" % i)}</td></tr>' for i in range(8)), "Nominees")
    xi = T('<tr><th>Tournament</th><th>Goalkeeper</th><th>Defenders</th><th>Midfielders</th></tr>' + ''.join(f'<tr><td>19{i}0</td><td>{L("G%d" % i)}</td><td>D</td><td>M</td></tr>' for i in range(3, 7)), "Media's selection")
    for h in (multi, alltime, nominees, xi):
        assert extract(h, "X") == []


def test_an_awards_table_with_several_award_columns_splits():
    h = T('<tr><th>Season</th><th>Player of the Season</th><th>Young Player</th><th>Coach</th></tr>'
          + ''.join(f'<tr><td>201{i}–1{i + 1}</td><td>{L("P%d" % i)}</td><td>{L("Y%d" % i)}</td><td>{L("C%d" % i)}</td></tr>' for i in range(3)), "Awards")
    got = {t["kind"]: [r["person"] for r in t["rows"]] for t in extract(h, "Saudi Pro League")}
    assert got == {"winner": ["P0", "P1", "P2"], "best_young": ["Y0", "Y1", "Y2"], "coach": ["C0", "C1", "C2"]}
    assert {t["section"] for t in extract(h, "Saudi Pro League")} == {"Awards — Player of the Season", "Awards — Young Player", "Awards — Coach"}

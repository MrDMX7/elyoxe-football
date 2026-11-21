import os
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


def test_season_page_awards_and_scorers():
    from graph.awards_wiki import extract_season, season_links
    aw = T('<tr><th>Award</th><th>Winner</th><th>Club</th></tr>'
           f'<tr><td>Player of the Season</td><td>{L("Omar_Abdulrahman")}</td><td>{L("Al_Ain_FC")}</td></tr>'
           f'<tr><td>Best Emirati Player</td><td>{L("Ali_Mabkhout")}</td><td>{L("Al_Jazira_Club")}</td></tr>'
           f'<tr><td>Goalkeeper of the Season</td><td>{L("Khalid_Eisa")}</td><td>{L("Al_Ain_FC")}</td></tr>'
           f'<tr><td>Coach of the Season</td><td>{L("Zlatko_Dalić")}</td><td>{L("Al_Ain_FC")}</td></tr>'
           f'<tr><td>Fans\' favourite chant</td><td>{L("X")}</td><td></td></tr>', "Awards")
    sc = T('<tr><th>Rank</th><th>Player</th><th>Club</th><th>Goals</th></tr>'
           f'<tr><td>1</td><td>{L("Ali_Mabkhout")}</td><td>{L("Al_Jazira_Club")}</td><td>33</td></tr>'
           f'<tr><td>2</td><td>{L("Sebastián_Tagliabúe")}</td><td>{L("Al_Wahda_FC")}</td><td>25</td></tr>'
           f'<tr><td>3</td><td>{L("Y")}</td><td></td><td>20</td></tr>', "Top scorers")
    page = b"<html><body>" + aw[12:-14] + sc[12:-14] + b"</body></html>"
    got = extract_season(page, "2016–17 UAE Pro League")
    assert got["season"] == "2016/2017"
    kinds = [(r["kind"], r["rank"], r["person"]) for r in got["rows"]]
    assert ("best_player", 1, "Omar_Abdulrahman") in kinds and ("best_local", 1, "Ali_Mabkhout") in kinds
    assert ("best_goalkeeper", 1, "Khalid_Eisa") in kinds and ("best_coach", 1, "Zlatko_Dalić") in kinds
    assert ("top_scorer", 1, "Ali_Mabkhout") in kinds and ("top_scorer", 2, "Sebastián_Tagliabúe") in kinds
    assert not any(r["person"] == "X" for r in got["rows"])               # an award we don't model
    links = season_links(b'<a rel="mw:WikiLink" href="./2016%E2%80%9317_UAE_Pro_League">x</a><a rel="mw:WikiLink" href="./Al_Ain_FC">y</a>'
                         b'<a rel="mw:WikiLink" href="./1973%E2%80%9374_UAE_Football_League">z</a><a rel="mw:WikiLink" href="./2016_in_UAE_football">w</a>')
    assert links == ["2016–17_UAE_Pro_League", "1973–74_UAE_Football_League"]


def test_canonical_title_and_not_awarded_rows():
    from graph.awards_wiki import canonical
    h = b'<html><head><link rel="dc:isVersionOf" href="//en.wikipedia.org/wiki/FIFA_World_Cup_awards"/></head><body></body></html>'
    assert canonical(h, "FIFA World Cup Golden Ball") == "FIFA World Cup awards"
    assert canonical(b"<html><body></body></html>", "Ballon d'Or") == "Ballon d'Or"
    t = T('<tr><th>Year</th><th>Player</th></tr>' + ''.join(f'<tr><td>{y}</td><td>{x}</td></tr>' for y, x in
          ((2001, L("A")), (2002, "Not awarded"), (2003, L("B")), (2004, "—"), (2005, L("C")), (2020, "Cancelled due to COVID-19"))))
    assert [r["season"] for r in extract(t, "X")[0]["rows"]] == ["2001", "2003", "2005"]


def test_season_scorers_without_a_rank_column_rank_by_goals():
    from graph.awards_wiki import extract_season
    sc = T('<tr><th>Player</th><th>Club</th><th>Goals</th></tr>'
           f'<tr><td>{L("A")}</td><td>x</td><td>8</td></tr><tr><td>{L("B")}</td><td>x</td><td>8</td></tr><tr><td>{L("C")}</td><td>x</td><td>6</td></tr>', "Top goalscorers")
    got = extract_season(sc, "2024–25 UEFA Nations League")
    assert [(r["person"], r["rank"]) for r in got["rows"]] == [("A", 1), ("B", 1), ("C", 3)]


ARAB = open(os.path.join(os.path.dirname(__file__), "fixtures", "awards_arab_champions.html"), "rb").read()


def test_arab_champions_list_gives_champion_runner_up_and_scorer_with_goals():
    t = {(x["section"], x["kind"]): x for x in extract(ARAB, "List of Algerian football champions")}
    ch = t[("List of champions", "champion_table")]["rows"]
    assert [(r["season"], r["team"], r["runner_up"]) for r in ch] == [
        ("1964/1965", "CR_Belouizdad", "MSP_Batna"), ("1965/1966", "CR_Belouizdad", "USM_Alger"), ("2024/2025", "MC_Alger", "CR_Belouizdad")]
    sc = t[("List of champions — Top goalscorer", "top_scorer")]["rows"]
    assert [(r["season"], r["person"], r["name"], r["team"], r["value"]) for r in sc] == [
        ("1964/1965", None, "Hocine Saadi", "NA_Hussein_Dey", "21"), ("1965/1966", "Hacène_Lalmas", "Hacène Lalmas", "CR_Belouizdad", "25"),
        ("2024/2025", "Adil_Boulbina", "Adil Boulbina", "Paradou_AC", "20")]


def test_a_winners_column_beside_a_scorer_column_is_the_champion():
    t = {x["kind"]: x for x in extract(ARAB, "List of Moroccan football champions") if x["section"].startswith("After")}
    assert t["champion"]["who"] == "team"
    assert [(r["season"], r["team"]) for r in t["champion"]["rows"]] == [("1956/1957", "Wydad_AC"), ("1957/1958", None), ("2025/2026", "Maghreb_of_Fez")]
    assert [(r["season"], r["person"], r["name"]) for r in t["top_scorer"]["rows"]] == [
        ("1956/1957", None, "Abdelkarim Zidani"), ("1957/1958", "Hassan_Akesbi", "Hassan Akesbi"), ("2025/2026", "Soufiane_Benjdida", "Soufiane Benjdida")]


# ---- Arabic Wikipedia list pages («ar:» titles): Arabic headers, Arabic-Indic digits, links kept as «ar:» titles
def _fx(name):
    return open(os.path.join(os.path.dirname(__file__), "fixtures", name), "rb").read()


def test_season_label_reads_arabic_digits_and_long_years():
    assert season_label("٢٠١٩–٢٠") == "2019/2020" and season_label("2019-2020") == "2019/2020" and season_label("۱۹۹۸") == "1998"


def test_arabic_saudi_scorers_by_season():
    t = extract(_fx("awards_ar_saudi_scorers.html"), "ar:قائمة هدافي دوري المحترفين السعودي")
    assert len(t) == 1 and t[0]["kind"] == "top_scorer" and t[0]["who"] == "person"
    rows = t[0]["rows"]
    first = rows[0]
    assert (first["season"], first["person"], first["name"], first["team"], first["value"]) == (
        "1974/1975", "ar:محمد_العبدلي", "محمد سعد العبدلي", "ar:نادي_النصر_(السعودية)", "13")
    assert "1975/1976" not in {r["season"] for r in rows}                # «أُلغي»: cancelled, no winner
    nasser = next(r for r in rows if r["season"] == "1976/1977")
    assert nasser["person"] is None and nasser["name"] == "ناصر عيد" and nasser["team"] == "ar:نادي_القادسية_(السعودية)"
    assert len({r["season"] for r in rows}) >= 45


def test_arabic_kuwait_scorers_and_egypt_scorers():
    k = extract(_fx("awards_ar_kuwait.html"), "ar:الدوري الكويتي")
    assert [x["kind"] for x in k] == ["top_scorer"]
    r = next(x for x in k[0]["rows"] if x["season"] == "1962/1963")
    assert (r["person"], r["team"], r["value"]) == ("ar:عبد_الرحمن_الدولة", "ar:النادي_العربي_(الكويت)", "15 هدف")
    e = extract(_fx("awards_ar_egypt_scorers.html"), "ar:قائمة هدافي الدوري المصري الممتاز")
    assert [x["kind"] for x in e] == ["top_scorer"]
    r = next(x for x in e[0]["rows"] if x["season"] == "1949/1950")
    assert (r["person"], r["name"], r["value"], r["team"]) == ("ar:حمديتو_أحمد", "حمديتو أحمد", "10", "ar:نادي_الترسانة_(مصر)")


def test_arabic_champion_and_runner_up_headers():
    L = lambda t: f'<a rel="mw:WikiLink" href="./{t}">{t}</a>'
    body = '<tr><td>الموسم</td><td>البطل</td><td>الوصيف</td></tr>' + ''.join(
        f'<tr><td>{s}</td><td>{L("نادي_الكويت")}</td><td>{L("نادي_القادسية_(الكويت)")}</td></tr>' for s in ("١٩٧٣–٧٤", "1974-1975", "1975–76"))
    t = extract(T(body, "الأبطال"), "ar:الدوري الكويتي")
    assert len(t) == 1 and t[0]["kind"] == "champion_table"
    assert [(r["season"], r["team"], r["runner_up"]) for r in t[0]["rows"]][:2] == [
        ("1973/1974", "ar:نادي_الكويت", "ar:نادي_القادسية_(الكويت)"), ("1974/1975", "ar:نادي_الكويت", "ar:نادي_القادسية_(الكويت)")]

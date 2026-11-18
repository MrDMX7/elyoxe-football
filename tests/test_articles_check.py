"""news/articles/check.py: the failures the blind tests showed (spec, «Checks»), and the right texts that must pass."""
import json
from pathlib import Path
from news.articles import check as C, facts as F

FX = Path(__file__).parent / "fixtures" / "articles"
MD = json.loads((FX / "match_5181860.json").read_text(encoding="utf-8"))
SHEET, _ = F.report_sheet(MD, None, None, {"players": {}, "coaches": {}, "referees": {}})
H, A = MD["home"]["name_ar"], MD["away"]["name_ar"]


def art(*paras, headline="عنوان", standfirst="مقدمة"):
    return {"headline": headline, "standfirst": standfirst, "sections": [{"subhead": "قسم", "paragraphs": list(paras)}], "facts_box": []}


def test_a_correct_line_passes():
    line = f"فاز {A} على {H} بنتيجة {MD['score']['away']}-{MD['score']['home']}."
    assert C.check_article(art(line), SHEET, MD) == []


def test_a_number_not_in_the_sheet_fails():
    assert C.check_article(art(f"سجل {A} 973 هدفاً."), SHEET, MD)          # 7 is in this sheet (a stat); 973 is in none


def test_latin_letters_fail_but_xg_and_var_pass():
    assert C.check_article(art("سجل Kane الهدف."), SHEET, MD)
    assert not [f for f in C.check_article(art("بلغت الأهداف المتوقعة xG للفريق رقماً، وتدخل VAR."), SHEET, MD) if "Latin" in f]


def test_dates_times_word_numbers_and_thousands_are_read_as_the_sheet_has_them():
    sheet = dict(SHEET, **{"الموعد بتوقيت الإمارات": "2026-11-08T22:00:00+04:00", "الحضور": 69788,
                           "النتيجة النهائية": f"{H} 3 - 0 {A}"})
    line = "أقيمت المباراة في 8 نوفمبر عند 10:00 مساءً أمام 69,788 متفرج، وانتهت بثلاثية نظيفة."
    assert C.check_article(art(line), sheet, None) == []


def test_a_shootout_line_passes():
    sheet = dict(SHEET, **{"ركلات الترجيح": f"{H} 4 - 3 {A}"})
    assert C.check_article(art(f"حسم {H} التأهل بركلات الترجيح 4-3."), sheet, None) == []


def test_a_goal_credited_to_the_wrong_player_fails():
    # spec, «Testing»: the checks catch a wrong scorer (site/ai/checks.check_events on the match's lineups and names)
    sheet, _ = F.report_sheet(MD, None, None, F.load_names())
    first = next(e for e in sheet["الأحداث بالترتيب"] if e["حدث"].startswith("هدف"))
    assert C.check_article(art(f"سجل {first['اللاعب']} الهدف في الدقيقة {first['دقيقة']}."), sheet, MD) == []
    wrong = "أوناي سيمون"                                                    # Spain's goalkeeper, no goal
    assert C.check_article(art(f"سجل {wrong} الهدف في الدقيقة {first['دقيقة']}."), sheet, MD)


def test_a_text_far_from_the_type_length_fails():
    # spec: a match report is 300-400 words; an empty or a 900-word answer is not one
    short = art("فاز الفريق.")
    assert [f for f in C.check_article(short, SHEET, None, words=(300, 400)) if "words" in f]
    ok = art(*["كلمة " * 50] * 7)                                             # 350 words
    assert not [f for f in C.check_article(ok, SHEET, None, words=(300, 400)) if "words" in f]

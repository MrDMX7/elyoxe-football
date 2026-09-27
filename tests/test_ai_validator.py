"""Deterministic guards on generated Tifo text (site/ai/gen.py): result check, rank/points check, zero counts, grammar."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "site", "ai"))
import gen

ROWS = {"الشارقة": {"rank": 5, "pts": 9}, "الظفرة": {"rank": 12, "pts": 3}, "الجزيرة": {"rank": 1, "pts": 13}, "العين": {"rank": 2, "pts": 13},
        "بني ياس": {"rank": 14, "pts": 1}, "شباب الأهلي": {"rank": 3, "pts": 10}, "الأهلي": {"rank": 7, "pts": 8}}

def test_leader_claim_for_non_leader_is_caught():
    assert gen.check_table("الشارقة يتصدر مركز 5 بـ 9 نقاط من 5 مباريات", ROWS)
    assert gen.keep_lines(["الشارقة يتصدر مركز 5 بـ 9 نقاط من 5 مباريات", "سطر", "سطر", "سطر"], ROWS, 4, "t") is None

def test_correct_rank_and_points_pass():
    assert gen.check_table("الشارقة في المركز 5 برصيد 9 نقاط، والظفرة في المركز 12 وعنده 3 نقاط.", ROWS) is None
    assert gen.check_table("المتصدر الجزيرة بـ 13 نقطة", ROWS) is None
    assert gen.check_table("بني ياس في المركز 14 وعنده نقطة وحدة بس", ROWS) is None

def test_wrong_rank_or_points_caught():
    assert gen.check_table("الظفرة في المركز 11 برصيد 3 نقاط", ROWS)
    assert gen.check_table("العين في المركز 2 برصيد 12 نقطة", ROWS)
    assert gen.check_table("المتصدر العين بـ 13 نقطة", ROWS)
    assert gen.check_table("بني ياس عنده نقطة وحدة", {"بني ياس": {"rank": 14, "pts": 2}})

def test_claims_attach_to_the_nearest_team():
    # «شباب الأهلي» must not be read as «الأهلي»; each clause checks its own team
    assert gen.check_table("شباب الأهلي في المركز 3 بـ 10 نقاط، والأهلي في المركز 7", ROWS) is None
    assert gen.check_table("الوصل فاز، والجزيرة المتصدر برصيد 13", ROWS) is None

def test_goal_difference_is_not_points():
    assert gen.check_table("الشارقة في المركز 5 بفارق 4 نقاط عن المتصدر", ROWS) is None

def test_line_drop_keeps_the_rest():
    lines = ["الشارقة في المركز 5", "الظفرة في المركز 9", "توقعات تيفو 69%", "المباراة الجمعة 16 أكتوبر"]
    assert gen.keep_lines(lines, ROWS, 3, "t") == [lines[0], lines[2], lines[3]]
    assert gen.keep_lines(lines, ROWS, 4, "t") is None

def test_result_check():
    md = {"home": {"id": 1, "name_ar": "مارسيليا"}, "away": {"id": 2, "name_ar": "باريس سان جيرمان"}, "score": {"home": 1, "away": 2}}
    assert gen.check_result("سجّل باريس سان جيرمان هدفين من 10 تسديدات", md) is None
    assert gen.check_result("سجّل مارسيليا هدفه الوحيد من 4 تسديدات", md) is None
    assert gen.check_result("سجّل باريس سان جيرمان 3 أهداف", md)
    assert gen.check_result("مارسيليا فاز على باريس سان جيرمان", md)
    assert gen.check_result("باريس سان جيرمان خسر", md)

def test_zero_counts_and_duals():
    assert gen.ZERO.search("ليتشي كان مب قادر يصنع أكثر عن 0 فرصة محققة")
    assert not gen.ZERO.search("بنسبة 60% و 10 تسديدات")
    assert gen.grammar("وصنع 2 فرص محققة في 2 مباراة") == "وصنع فرصتين محققتين في مباراتين"
    assert gen.grammar("فاز 12 مباراة") == "فاز 12 مباراة"
    assert gen.grammar("الإمارات فاز، والبحرين خسر", ["الإمارات", "البحرين"]) == "منتخب الإمارات فاز، ومنتخب البحرين خسر"

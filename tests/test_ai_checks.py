"""site/ai/checks.py: timeline, history, half-time counts and player-name checks, on the real errors the Sonnet samples made
(2026-09-27) and on the true statements next to them. Match data is copied from /v1/match/{id}.json (ids in the names)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "site", "ai"))
import checks, gen

def ev(minute, typ, side, pid, name):
    return {"minute": minute, "type": typ, "team": side, "player": {"id": pid, "name": name}}
T = lambda i, ar: {"id": i, "name_ar": ar, "name": ar}

# 5802945: Marseille 1-2 PSG; goals 66' (PSG), 72' (OM), 74' (PSG); Weah's second yellow 77'
PSG = {"home": T(8592, "مارسيليا"), "away": T(9847, "باريس سان جيرمان"), "score": {"home": 1, "away": 2},
       "events": [ev(66, "goal", "away", 1, "Ferrán Torres"), ev(72, "goal", "home", 2, "Angel Gomes"), ev(74, "goal", "away", 3, "Marquinhos"), ev(77, "second_yellow", "home", 4, "Timothy Weah")]}
# 5868079: Valencia 2-3 Real Sociedad; 26' RS, 57' VAL, 75' RS pen, 84' own goal for VAL, 90' RS (the winner)
RSO = {"home": T(10267, "فالنسيا"), "away": T(8560, "ريال سوسيداد"), "score": {"home": 2, "away": 3},
       "events": [ev(26, "goal", "away", 11, "Luka Sučić"), ev(57, "goal", "home", 12, "Aaron Mayol"), ev(75, "penalty_goal", "away", 13, "Carlos Soler"),
                  ev(84, "own_goal", "home", 14, "Luken Beitia"), ev(90, "goal", "away", 15, "Ander Barrenetxea")]}
# 1000020526: Ajman 3-2 Sharjah after 0-2; h2h before it: Ajman 3 wins, 6 draws, Sharjah 11
AJM = {"home": T(1, "عجمان"), "away": T(2, "الشارقة"), "score": {"home": 3, "away": 2},
       "events": [ev(12, "goal", "away", 21, "Cheickna Doumbia"), ev(38, "goal", "away", 21, "Cheickna Doumbia"), ev(72, "goal", "home", 22, "Sékou Gassama"), ev(74, "goal", "home", 23, "Jobson"), ev(90, "goal", "home", 24, "Victor Henrique")]}
# 1000020522: Al Wahda 1-0 Sharjah (own goal 10', filed under Al Wahda)
WAH = {"home": T(3, "الوحدة"), "away": T(2, "الشارقة"), "score": {"home": 1, "away": 0}, "events": [ev(10, "own_goal", "home", 31, "Kodjo Laba")]}
# 6150375: DH Jadidi 2-6 Meknes; Meknes 10' 13' (pens) 26' 35' then 46' 80'
MEK = {"home": T(5, "الدفاع الحسني الجديدي"), "away": T(6, "النادي المكناسي"), "score": {"home": 2, "away": 6},
       "events": [ev(10, "penalty_goal", "away", 41, "A"), ev(13, "penalty_goal", "away", 41, "A"), ev(26, "goal", "away", 42, "B"), ev(35, "goal", "away", 43, "C"),
                  ev(46, "goal", "away", 44, "D"), ev(62, "goal", "home", 45, "E"), ev(73, "penalty_goal", "home", 46, "F"), ev(80, "goal", "away", 47, "G")]}

def test_goals_after_red_card_when_they_came_before():
    assert checks.check_events("باريس سان جيرمان سيطر بالاستحواذ 61% وسجّل هدفين من 10 تسديدات على المرمى بعد طرد ويا من مارسيليا.", PSG)
    assert checks.check_events("مارسيليا اكتفى بـ39% استحواذ و4 فرص محققة بس، وسجّل هدفه الوحيد في الدقيقة 72.", PSG) is None

def test_winning_goal_must_be_the_decisive_one():
    t = checks.timeline(RSO); assert t["decisive"]["min"] == 90
    assert checks.check_events("ريال سوسيداد فاز 3-2 وسجّل هدف الفوز من ضربة يزاء وهدف تاني في الدقيقة 90.", RSO)
    assert checks.check_events("ريال سوسيداد سجّل هدف الفوز في الدقيقة 90.", RSO) is None
    assert checks.check_events("سجّل ريال سوسيداد هدف الحسم في الدقيقة 75.", RSO)

def test_first_win_claim_needs_the_h2h_to_agree():
    ev_in = {"head_to_head": {"home_wins": 3, "draws": 6, "away_wins": 11}}
    assert checks.check_history("ويعتبر أول فوز على الشارقة بعد مواجهات كانت الكفة فيها لصالح الشارقة.", ev_in)
    assert checks.check_history("أول فوز لعجمان هالموسم.", {})   # no evidence in the input at all
    assert checks.check_history("عجمان فاز على الشارقة 3-2.", ev_in) is None

def test_streak_numbers_must_be_in_the_input():
    assert checks.check_history("بني ياس ما فاز من 8 مباريات.", {"home_table": {"form": "LLLDL"}})
    assert checks.check_history("بني ياس عنده 8 مباريات ورا بعض بدون فوز.", {"records_at_stake": ["بني ياس بدون فوز في 8 مباريات"]}) is None

def test_comeback_needs_the_winner_to_have_trailed():
    assert checks.check_events("عجمان قلبها على الشارقة وفاز 3-2.", AJM) is None
    assert checks.check_events("الوحدة قلب النتيجة وفاز على الشارقة.", WAH)

def test_named_scorer_and_minute():
    assert checks.check_events("سجّل Marquinhos في الدقيقة 74.", PSG) is None
    assert checks.check_events("سجّل Marquinhos في الدقيقة 66.", PSG)
    assert checks.check_events("سجّل Angel Gomes في الدقيقة 72.", PSG) is None

def test_half_counts_are_checked_against_that_half():
    why, rest = checks.check_halves("النادي المكناسي سجّل 4 أهداف بالشوط الأول بس من ركلتي جزا وهدفين من اللعب.", MEK)
    assert why is None and "4 أهداف" not in rest
    assert gen.check_result(rest, MEK) is None                   # the Sonnet line no longer trips the full-time count
    assert checks.check_halves("النادي المكناسي سجّل 5 أهداف في الشوط الأول.", MEK)[0]
    assert checks.check_halves("النادي المكناسي سجّل هدفين في الشوط الثاني.", MEK)[0] is None

def test_latin_names_become_arabic_or_are_reported():
    players = {"21": {"lat": "Cheickna Doumbia", "ar": "شيكنا دومبيا", "side": "away"}, "99": {"lat": "Nobody Known", "ar": None, "side": "home"}}
    text, left = checks.arabic_names("سجل Cheickna Doumbia هدفين.", players)
    assert text == "سجل شيكنا دومبيا هدفين." and left == []
    text, left = checks.arabic_names("سجل Nobody Known هدف.", players)
    assert left == ["Nobody", "Known"]

def test_form_runs_must_exist_in_the_form_data():
    # Sonnet preview 1000020530: Al Dhafra's form is L L L L W, so «سلسلة خسارتين متتاليتين» is wrong
    ev_in = {"home_table": {"form": ["W", "L", "W", "W", "L"]}, "away_table": {"form": ["L", "L", "L", "L", "W"]}}
    assert checks.check_history("وآخر فوز له كان بعد سلسلة خسارتين متتاليتين قبلها.", ev_in)
    assert checks.check_history("فاز بعد 4 خسارات متتالية.", ev_in) is None
    assert checks.check_history("فاز بعد 4 خسارات متتالية.", {})

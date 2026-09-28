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

def test_leader_words_include_tasaddur_and_sadara():
    rows = {"الإمارات": {"rank": 2, "pts": 3}, "البحرين": {"rank": 4, "pts": 0}, "الشارقة": {"rank": 5, "pts": 9}, "الجزيرة": {"rank": 1, "pts": 13}}
    # Haiku v2, quick 6052085 and preview 1000020530
    assert gen.check_table("البحرين في المركز 4 بـ 0 نقاط والإمارات تصدرت مع 3 نقاط بالمجموعة الثانية.", rows)
    assert gen.check_table("الشارقة يملك 3 انتصارات في 5 مباريات وفي الصدارة النسبية بـ 9 نقاط.", rows)
    assert gen.check_table("الجزيرة في الصدارة بـ 13 نقطة.", rows) is None
    assert gen.check_table("الشارقة على بعد 4 نقاط من الصدارة.", rows) is None

def test_own_goal_beneficiary():
    # Haiku v2, 5868079: Luken Beitia's own goal (84') counted for Valencia
    assert checks.check_events("فالنسيا ضيّع 3 فرص محققة، وتلقى هدف عكسي في الدقيقة 84 من لوكين بيتيا لصالح ريال سوسيداد.", RSO)
    assert checks.check_events("فالنسيا سجّل هدف عكسي لصالح فالنسيا في الدقيقة 84.", RSO) is None
    assert checks.check_events("الوحدة فاز بهدف عكسي لصالح الوحدة في الدقيقة 10.", WAH) is None

def test_straight_red_vs_second_yellow():
    # Haiku v2, 5802945: Weah's red was a second yellow
    assert checks.check_events("مارسيليا خسر اللاعب تيموثي ويا بالطرد المباشر في الدقيقة 77.", PSG)
    assert checks.check_events("انطرد تيموثي ويا بالإنذار الثاني في الدقيقة 77.", PSG) is None
    STRAIGHT = dict(PSG, events=PSG["events"][:3] + [ev(77, "red", "home", 4, "Timothy Weah")])
    assert checks.check_events("انطرد تيموثي ويا بالإنذار الثاني في الدقيقة 77.", STRAIGHT)

def test_form_counts_must_match():
    ev_in = {"home_table": {"form": ["W", "L", "W", "W", "L"]}, "away_table": {"form": ["L", "L", "L", "L", "W"]}}
    # Haiku v3 preview 1000020530: Sharjah is W L W W L
    assert checks.check_history("الشارقة والفورمة تبع آخر 5 لقاءات فيها انتصارين وهزيمتين.", ev_in)
    assert checks.check_history("الشارقة فورمته في آخر 5: 3 انتصارات وخسارتين.", ev_in) is None
    assert gen.grammar("سجله 2 فوز و2 خسارة وتعادل") == "سجله فوزين وخسارتين وتعادل"

def test_half_counts_ignore_deficits_scores_and_check_conceded():
    # the 3 false positives of the 21:25 run (summary 1000020526, thread 1000020526, why 6150375)
    assert checks.check_halves("هالفوز يعتبر مفاجئ لعجمان بعد ما كان متأخر بهدفين في الشوط الأول.", AJM)[0] is None
    assert checks.check_halves("بهالفوز عجمان يقلب النتيجة من 0-2 إلى 3-2 في الشوط الثاني كامل", AJM)[0] is None
    why, rest = checks.check_halves("سجل الدفاع الحسني الجديدي هدفين من 5 تسديدات على المرمى واستقبل 4 أهداف في الشوط الأول.", MEK)
    assert why is None and gen.check_result(rest, MEK) is None
    assert checks.check_halves("الدفاع الحسني الجديدي استقبل 3 أهداف في الشوط الأول.", MEK)[0]
    assert checks.check_halves("عجمان سجل 3 أهداف في الشوط الثاني.", AJM)[0] is None
    assert checks.check_halves("عجمان سجل هدفين في الشوط الثاني.", AJM)[0]

def test_club_without_arabic_name_gets_one():
    assert gen.team_ar({"id": 570488, "name": "Widad Temara", "name_ar": None}) == "وداد تمارة"   # names/clubs_ar.json
    assert gen.team_ar({"id": 102124, "name": "Sharjah"}) == "الشارقة"                            # teams_ar.yaml

def test_plurals_after_three_to_ten_and_faqat():
    assert gen.grammar("كان فيها 5 خسارة و4 تعادل و10 فوز و13 فوز") == "كان فيها 5 خسارات و4 تعادلات و10 انتصارات و13 فوز"
    assert gen.grammar("11 فوز مقابل 3 فوز لعجمان فقط.") == "11 فوز مقابل 3 انتصارات لعجمان بس."
    assert gen.grammar("3 تسديدات بس فقط على المرمى") == "3 تسديدات بس على المرمى"
    assert gen.grammar("فقط 2 فوز") == "بس فوزين"

def test_audit_w13a_generic_rules():
    neutral = {"neutral": True, "venue_city": "Jeddah"}
    assert checks.check_history("منتخب قطر يبا يراوي الجميع قوته برا أرضه ويحقق نتيجة إيجابية.", neutral)
    assert checks.check_history("منتخب قطر يبا يراوي الجميع قوته برا أرضه.", {"neutral": False}) is None
    assert checks.check_history("نسب توقعات تيفو مب متوفرة الحين للمباراة.", {})
    assert checks.check_history("هذا فوزه رقم 2 في البطولة.", {})
    assert checks.check_history("مفتاح المباراة: مفتاح المباراة.", {})
    assert checks.check_history("مفتاح المباراة: هجوم الشارقة اللي سجل 10 أهداف قدام دفاع استقبل 9.", {}) is None

def test_meta_phrases_and_24h_times():
    assert checks.check_history("منتخب الإمارات فورمته فوز واحد مسجل بالبيانات.", {})
    assert checks.check_history("منتخب الإمارات المتصدر بفارق نظافة شبكته.", {})
    assert checks.check_history("منتخب الإمارات ما استقبل أي هدف في مباراتين.", {}) is None
    assert gen.grammar("يوم 2 أكتوبر 2026 الساعة 5:15 عصرا بتوقيت الإمارات") == "يوم 2 أكتوبر 2026 الساعة 17:15 بتوقيت الإمارات"
    assert gen.grammar("الساعة 9:30 مساءً") == "الساعة 21:30"
    assert gen.grammar("الساعة 19:45") == "الساعة 19:45"

def test_qa_0928_day_word_and_forbidden_forms():
    import datetime as dt
    now = dt.datetime(2026, 9, 28, 10)
    assert [gen.day_word(x, now) for x in ("2026-09-28T20:00:00+04:00", "2026-09-28T15:00:00+04:00", "2026-09-29T17:00:00+04:00", "2026-10-02T17:00:00+04:00")] == ["الليلة", "اليوم", "بكرة", "الجمعة"]
    assert gen.emirati("ووش على المحك، ومين سجل، وش صار") == "وشو على المحك، ومنو سجل، شو صار"
    assert checks.check_history("مين كان مسيطر دقيقة بدقيقة", {})
    assert checks.check_history("منو كان مسيطر دقيقة بدقيقة", {}) is None

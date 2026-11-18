"""news/: entity linking, classification, story merging. Every case is a mistake seen on live headlines on 2026-09-30."""
from news import entities as E, classify as C, cluster as K

TEAMS = {
    "101918": {"name": "Al Nassr FC", "name_ar": "النصر", "country": {"iso2": "SA"}, "comps": [536]},
    "102123": {"name": "Al-Nasr SC", "name_ar": "النصر", "country": {"iso2": "AE"}, "comps": [538]},
    "101710": {"name": "Al Nasr", "name_ar": "النصر", "country": {"iso2": "KW"}, "comps": [529]},
    "8577": {"name": "Al Ittihad", "name_ar": "الاتحاد", "country": {"iso2": "SA"}, "comps": [536]},
    "101762": {"name": "Al Masry", "name_ar": "المصري", "country": {"iso2": "EG"}, "comps": [519]},
    "8456": {"name": "Manchester City", "name_ar": "مانشستر سيتي", "country": {"iso2": "GB-ENG"}, "comps": [47]},
    "10260": {"name": "Manchester United", "name_ar": "مانشستر يونايتد", "country": {"iso2": "GB-ENG"}, "comps": [47]},
    "10703": {"name": "Egypt", "name_ar": "مصر", "country": {"iso2": "EG"}, "comps": [289]},
    "1517695": {"name": "Nations", "name_ar": "نيشنز", "country": None, "comps": [9806]},
    "960720": {"name": "Inter Miami CF", "name_ar": "إنتر ميامي", "country": {"iso2": "US"}, "comps": [130]},
    "1552577": {"name": "United FC", "name_ar": "يونايتد", "country": {"iso2": "AE"}, "comps": [538]},
    "10261": {"name": "Newcastle United", "name_ar": "نيوكاسل", "country": {"iso2": "GB-ENG"}, "comps": [47]},
    "102124": {"name": "Sharjah Cultural Club", "name_ar": "الشارقة", "country": {"iso2": "AE"}, "comps": [538]},
    "102117": {"name": "Al-Ain", "name_ar": "العين", "country": {"iso2": "AE"}, "comps": [538]},
    "9847": {"name": "Paris Saint-Germain", "name_ar": "باريس سان جيرمان", "country": {"iso2": "FR"}, "comps": [53]},
    "8634": {"name": "Barcelona", "name_ar": "برشلونة", "country": {"iso2": "ES"}, "comps": [87]},
}
PLAYERS = {
    "30981": {"latin": "Lionel Messi", "ar": "ليونيل ميسي"},
    "1131947": {"latin": "Ahmed Adel Messi", "ar": "أحمد عادل ميسي"},
    "701154": {"latin": "Kylian Mbappé", "ar": "كيليان مبابي"},
    "1426809": {"latin": "Ethan Mbappé", "ar": "إيثان مبابي"},
    "859042": {"latin": "Show", "ar": "شو"},
    "500001": {"latin": "Fawzi Ben Hamla", "ar": "فوزي بن حملة"},
    "500002": {"latin": "Omar Al Awda", "ar": "عمر العودة"},
    "500003": {"latin": "Lloyd Kelly", "ar": "لويد كيلي"},
    "500004": {"latin": "Cristiano Ronaldo", "ar": "كريستيانو رونالدو"},
}
ALIASES = {"teams": {"Man City": "Manchester City", "Man Utd": "Manchester United"}, "people": {"Cristiano": "Cristiano Ronaldo"}}
D = E.build(TEAMS, PLAYERS, {}, {}, ALIASES, national_comps=frozenset({289}))
D.player_team = {500003: 10260}


def names(text, query=None):
    return {D.names[e] for e in E.link(D, text, query)}


def test_ambiguous_club_settled_by_nisba_or_cue_else_skipped():
    assert names("نجم النصر السعودي يصف رونالدو") >= {"النصر"} and ("team", 101918) in E.link(D, "نجم النصر السعودي يصف رونالدو")
    assert ("team", 102123) in E.link(D, "النصر يفوز في دوري أدنوك")
    assert "النصر" not in names("النصر يفوز")                          # no cue: better no link than a wrong one


def test_common_words_are_not_people_or_clubs():
    assert names("فيفا يتهم يويفا بشن حملة تضليل") == set()             # «حملة» is not Fawzi Ben Hamla
    assert names("أفكر في العودة لأوروبا") == set()                     # «العودة» is not Omar Al Awda
    assert names("Who continues to show how important they are?") == set()   # «show» / the team «Nations»
    assert "المصري" not in names("حسام حسن: المنتخب المصري لا يقف على أحد")
    assert "الاتحاد" not in names("فيفا والاتحاد الأوروبي في أزمة")


def test_stars_and_weak_surnames():
    assert names("هل يعتزل ميسي في 2026؟") == {"ليونيل ميسي"}           # a star by one word, not Ahmed Adel Messi
    assert names("Mbappé esquivó el quirófano") == {"كيليان مبابي"}
    assert "لويد كيلي" not in names("Toone and Kelly miss out")          # a weak surname without the club
    assert "لويد كيلي" in names("Kelly signs a new deal with Man Utd")   # ... with the club it counts
    assert names("Enigma Cristiano") == {"كريستيانو رونالدو"}


def test_country_is_a_national_team_after_montakhab_or_at_the_start():
    assert "مصر" in names("مصر تكتسح جنوب السودان بخماسية")
    assert "مصر" in names("مدرب منتخب مصر يعلن القائمة")
    assert "مصر" not in names("حادث سير خطير في مصر")


def test_arabic_clitics():
    assert "مانشستر سيتي" in names("صدمة لمانشستر سيتي بعد الحكم")      # the «ل» is read through
    assert "ليونيل ميسي" in names("مشجع يستفز ميسي")


def test_classify_kinds_and_transfer_stages():
    assert C.classify({"title": "Fabrizio: here we go! Olise to Real Madrid"}) == {"kind": "transfer", "stage": "here_we_go", "here_we_go": True}
    assert C.classify({"title": "Oficial: el Madrid ficha a Olise"})["stage"] == "official"
    assert C.classify({"title": "عرض رسمي من النصر لتجديد عقد العقيدي"})["kind"] == "transfer"
    assert C.classify({"title": "إصابة نواف العقيدي تصدم النصر"})["kind"] == "injury"
    assert C.other_sport({"title": "الزمالك أمام الجزيرة ببطولة بني ياس الدولية للطائرة"})
    assert not C.other_sport({"title": "الزمالك يفوز على الأهلي"})


def test_official_only_when_the_headline_says_the_deal_is_done():
    # 2026-10-06: «أرسنال وريال مدريد وبرشلونة يدخلون سباق ضم هالاند» went out as رسمي (one loose «official» in the cluster)
    for t in ["Oficial: el Madrid ficha a Olise", "رسمياً.. الهلال يعلن التعاقد مع روبن نيفيز",
              "Arsenal complete the signing of Eze from Crystal Palace", "OFFICIAL: Liverpool sign Isak for record fee"]:
        assert C.classify({"title": t})["stage"] == "official", t
    for t in ["تجديد عقد رافينها مع برشلونة.. وموعد الإعلان الرسمي", "عرض رسمي من النصر لتجديد عقد العقيدي",
              "Official bid from Chelsea for Garnacho rejected", "Man United confirm interest in a transfer for Osimhen",
              "Arda Güler's new deal at Real Madrid will be also officially signed soon."]:
        assert C.classify({"title": t})["stage"] != "official", t
    assert C.classify({"title": "Transfer news", "desc": "The deal is official, says the agent"})["stage"] != "official"   # a description never


def _item(i, title, lang="en", kind="other", at="2026-09-29T10:00:00Z", source="BBC Sport"):
    it = {"id": i, "title": title, "lang": lang, "kind": kind, "at": at, "source": source, "url": "u" + i, "tier": "paper"}
    it["anchor"] = [list(e) for e in E.link(D, title)]
    it["entities"] = it["anchor"]
    it["topic"] = E.topic(D, title)
    return it


def test_stories_merge_on_the_headline_not_on_a_passing_mention():
    stories = {}
    a = _item("1", "Man City found guilty on all charges", kind="official")
    b = _item("2", "Oficial: la Premier confirma el escándalo del Manchester City", "es", "official", source="AS")
    c = _item("3", "Messi scores again for Inter Miami", kind="match")
    d = _item("4", "Ronaldo: Messi is the best", kind="statement")
    K.assign(stories, [a, b, c, d])
    by = {tuple(sorted(s["items"])) for s in stories.values()}
    assert ("1", "2") in by                                          # one story, two languages
    assert ("3",) in by and ("4",) in by                             # sharing Messi is not enough for general news


def test_womens_items_are_told_apart():
    assert C.womens({"title": "PRESS CONFERENCE | Renée Slegers", "desc": "Arsenal Women head coach speaks ahead of the WSL game"})
    assert C.womens({"title": "Resumen del Barça Femení"})
    assert C.womens({"title": "PRESS CONFERENCE | Renée Slegers previews Chelsea clash", "desc": "Watch it live. #arsenal #awfc Subscribe"})
    assert not C.womens({"title": "Arteta press conference ahead of Newcastle"})


def _chain():
    a = _item("1", "Lionel Messi wants Manchester City move", kind="transfer", at="2026-09-29T10:00:00Z")
    b = _item("2", "Lionel Messi and Cristiano Ronaldo to Manchester City?", kind="transfer", at="2026-09-29T11:00:00Z")
    c = _item("3", "Cristiano Ronaldo hints at a move", kind="transfer", at="2026-09-29T12:00:00Z")
    return a, b, c


def test_a_story_is_anchored_on_its_first_headline_not_on_all_it_took_in():
    # 2026-10-06: «Haaland and Arsenal» took in Raphinha through a shared club, then Raphinha's items, then Arteta's contract
    stories = {}
    K.assign(stories, list(_chain()))
    assert {tuple(sorted(s["items"])) for s in stories.values()} == {("1", "2"), ("3",)}   # Ronaldo came in with item 2, not the story


def test_rebuild_splits_a_story_the_old_rules_chained():
    a, b, c = _chain()
    old = K.new_story(a)
    for x in (b, c):
        K.add(old, x)
    old.pop("seed")                                                   # as the old rules left it in the state
    items = {x["id"]: x for x in (a, b, c)}
    stories, rebuilt, named = K.rebuild({old["id"]: old}, items)
    assert {tuple(sorted(s["items"])) for s in stories.values()} == {("1", "2"), ("3",)}
    assert ("player", 500004) in named                               # Ronaldo's page is written again without the Messi story
    gone = K.new_story(_item("9", "Lionel Messi scores", kind="match", at="2026-09-20T10:00:00Z"))
    gone["items"] = ["9"]
    assert gone["id"] in K.rebuild({gone["id"]: gone}, items)[0]       # no item of it kept: it stays until it ages out
    gone.update(kind="transfer", stage="official")
    assert K.rebuild({gone["id"]: gone}, items)[0][gone["id"]]["stage"] is None   # but an «official» it cannot check is not claimed


def test_a_story_credits_its_stage_to_its_subjects_and_shows_the_headline_that_reached_it():
    # 2026-10-06: Güler went out as «official» through Raphinha's story (a merged tweet named him), under the headline
    # «رونالدينيو سبب انتقال رافينيا إلى برشلونة»
    from news import run as R
    a = _item("1", "Lionel Messi transfer to Manchester City talked up", kind="transfer", at="2026-09-29T10:00:00Z")
    b = _item("2", "Official: Lionel Messi and Cristiano Ronaldo sign for Manchester City", kind="transfer", at="2026-09-29T11:00:00Z")
    for x in (a, b):
        x.update(C.classify(x))
    stories = {}
    K.assign(stories, [a, b])
    (s,) = stories.values()
    assert s["stage"] == "official"
    items = {"1": a, "2": b}
    t = {p["player"]["id"]: p["stage"] for p in R.transfers([s], items, D)}
    assert t == {30981: "official"}                                    # Messi; Ronaldo only came in with the second headline
    card = R.display(s, items, D)
    assert card["title"].startswith("Official:") and {e["id"] for e in card["entities"]} == {30981, 8456}
    assert 500004 in {m["id"] for m in card["mentions"]}


def test_the_rumour_meter():
    # «مؤشر صحة الإشاعة» (owner's second list 4): the strongest outlet, how many carry it, how far the deal got
    from news import run as R
    src = lambda *tiers: [{"tier": t} for t in tiers]
    tr = lambda **kw: dict({"kind": "transfer", "stage": "rumour"}, **kw)
    assert R.credibility(tr(), src("aggregator"))["v"] == 15                               # one site copying another: weak
    assert R.credibility(tr(), src("paper", "aggregator", "aggregator", "aggregator"))["v"] == 46
    assert R.credibility(tr(stage="talks"), src("journalist", "paper", "paper")) == {"v": 86, "n": 3, "best": "journalist"}
    assert R.credibility(tr(here_we_go=True), src("journalist"))["v"] == 92
    assert R.credibility(tr(stage="official"), src("paper"))["v"] == 100
    assert R.credibility({"kind": "injury"}, src("paper")) is None


# ------------------------------------------------------------------ Arabic headlines only (owner 2026-10-09)
def test_the_headline_is_arabic_whenever_an_arabic_source_has_the_story():
    from news import run as NR
    ar = {"lang": "ar", "title": "مورينيو يشن هجوما على مبابي"}
    en = {"lang": "en", "title": "Mourinho: Mbappé to start"}
    assert NR.pick_title({}, en, [en, ar]) == ("مورينيو يشن هجوما على مبابي", "ar")      # an Arabic source beats a foreign stage item
    assert NR.pick_title({}, None, [en, ar]) == ("مورينيو يشن هجوما على مبابي", "ar")
    assert NR.pick_title({"title_ar": "خلاصة"}, en, [en]) == ("خلاصة", "ar")
    assert NR.pick_title({}, en, [en]) == ("Mourinho: Mbappé to start", "en")
    assert NR.pick_title({}, None, []) == ("", "")


def test_only_arabic_headlines_are_published():
    """27 % of /news/ (41 of 150) was English, Spanish or German once headline rewriting was switched off (2026-10-09)."""
    from news import run as NR
    rows = [{"id": 1, "title_lang": "ar"}, {"id": 2, "title_lang": "en"}, {"id": 3, "title_lang": "es"}, {"id": 4, "title_lang": "ar"}]
    assert [r["id"] for r in NR.arabic_only(rows)] == [1, 4]
    assert [r["id"] for r in NR.arabic_only(rows, 1)] == [1]


def test_a_lone_united_is_the_uae_club_only_beside_the_uae():
    # 2026-11-18: «نيوكاسل يونايتد» and Pochettino's «يونايتد» were linked to the UAE's United FC
    uae = ("team", 1552577)
    assert uae not in E.link(D, "راتب توني يعقد انتقاله إلى نيوكاسل يونايتد")
    assert uae not in E.link(D, "بوكيتينو: قيادة يونايتد أصعب قراراتي")
    assert uae not in E.link(D, "مانشستر يونايتد يخسر") and ("team", 10260) in E.link(D, "مانشستر يونايتد يخسر")
    assert uae in E.link(D, "يونايتد والشارقة يتعادلان 1-1")                      # beside a UAE club
    assert uae in E.link(D, "يونايتد يفوز في كأس مصرف أبوظبي الإسلامي")              # a UAE cue
    assert uae in E.link(D, "نادي يونايتد يعلن مدربه الجديد")                        # «نادي» names the club itself


def test_two_clubs_alone_are_not_one_story():
    # 2026-11-18: «قائد برشلونة», Balde and Gvardiol were one story because every headline named PSG and Barcelona
    stories = {}
    rows = [("1", "بـ65 مليون يورو.. باريس سان جيرمان ينقض على قائد برشلونة"),
            ("2", "باريس سان جيرمان يجهز 65 مليون يورو لخطف قائد برشلونة"),
            ("3", "باريس سان جيرمان يستهدف نجم برشلونة مقابل 65 مليون يورو"),
            ("4", "تابع باريس سان جيرمان ضد برشلونة"),
            ("5", "باريس سان جيرمان يخطط لخطف منبوذ برشلونة"),
            ("6", "خرج من حسابات فليك.. باريس سان جيرمان يسعى لضم بالدي من برشلونة"),
            ("7", "باريس سان جيرمان يراقب وضع بالدي مع برشلونة تمهيداً لضمه")]
    K.assign(stories, [_item(i, t, "ar", at=f"2026-11-14T1{i}:00:00Z") for i, t in rows])
    by = {tuple(sorted(s["items"])) for s in stories.values()}
    assert ("1", "2", "3") in by                          # one story, three outlets: 65 million for the captain
    assert ("6", "7") in by                               # Balde, twice
    assert ("4",) in by and ("5",) in by                  # a stream link, and «منبوذ» shares only the verb


def test_a_match_between_two_clubs_needs_no_more_than_its_headlines():
    stories = {}
    a = _item("1", "برشلونة يفوز على باريس سان جيرمان 2-1", "ar", "match")
    b = _item("2", "باريس سان جيرمان يخسر أمام برشلونة 1-2 في دوري الأبطال", "ar", "match", at="2026-09-29T11:00:00Z")
    K.assign(stories, [a, b])
    assert len(stories) == 1


def test_a_club_named_after_its_city_is_not_the_city():
    # 2026-11-18: Al Ain's page had the book fair, the municipality, «رأس العين» and al-ain.com; Sharjah's had the ruler,
    # the book fair and the «#الشارقة_الرياضية» channel tag on other clubs' goals
    ain, shj = ("team", 102117), ("team", 102124)
    for t in ("انطلاق فعاليات الدورة الـ17 من «مهرجان العين للكتاب»", "بلدية العين تنفذ 7 مشاريع مستقبلية",
              "290 حالة تسمم في رأس العين", "مسؤول في مايكروسوفت يكشف لـ«العين الإخبارية» أسباب العطل",
              "وادي دجلة يدخل معسكرا مغلقا بالعين السخنة", "مشروع تعليب مياه العين"):
        assert ain not in E.link(D, t), t
    for t in ("حاكم الشارقة يهنئ ملك المغرب", "معرض الشارقة الدولي للكتاب يودع القراء",
              "منصور محمد يضاعف النتيجة الإمارات 2-0 ماكاو #الشارقة_الرياضية"):
        assert shj not in E.link(D, t), t
    assert ain in E.link(D, "العين يستعيد توازنه بالفوز على حتا") and ain in E.link(D, "نادي العين الرياضي يعلن مدربه")
    assert shj in E.link(D, "يونايتد والشارقة يتعادلان 1-1")


def test_a_city_search_keeps_only_football():
    item = lambda title, ents=(): {"title": title, "entities": [list(e) for e in ents]}
    assert not C.football(item("أدوية السكري والسمنة لا تضر العين"))
    assert not C.football(item("غرفة الشارقة تطلق مجموعة عمل قطاع الرعاية الصحية"))
    assert C.football(item("4 مباريات تشعل غضب العين"))
    assert C.football(item("إيفيتش يعلن قائمة العين", [("coach", 1), ("team", 102117)]))     # a coach: football
    assert C.football(item("العين يصل إلى حتا", [("team", 102117), ("team", 5)]))              # two clubs: football
    assert C.other_sport({"title": "«طحان الوثبة» بطل كأس حمدان بن راشد بمضمار الشارقة"})


def test_the_bank_is_not_its_club():
    from news import run as R
    Db = E.build(dict(TEAMS, **{"687954": {"name": "National Bank", "name_ar": "البنك الأهلي", "country": {"iso2": "EG"}, "comps": [519]}}),
                 PLAYERS, {}, {}, ALIASES)
    bank = ["team", 687954]
    it = {"title": "لو معاك 100 ألف جنيه.. احسب أرباحك من شهادات البنك الأهلي 2026"}
    R.link_item(Db, it)
    assert bank not in it["anchor"] and bank not in it["entities"]
    it = {"title": "البنك الأهلي يتعادل في الدوري المصري"}
    R.link_item(Db, it)
    assert bank in it["anchor"]

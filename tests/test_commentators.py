"""news/commentators.py («منو يعلّق؟»): Kooora's daily channel/commentator articles parsed and tied to FotMob fixtures.
Fixtures: three real articles (19, 27 and 30 September 2026, scripts and links stripped) and the FotMob fixtures that kick
off within 20 minutes of their times (every league FotMob lists, so the distractors are real). No network."""
from datetime import date, datetime, timedelta, timezone

from conftest import load
from news import commentators as C

UTC = timezone.utc


class Fake:
    """A store with public JSON only: {path: obj}."""

    def __init__(self, files):
        self.files = files

    def get_json(self, path, public=True):
        return self.files.get(path)


def article(ymd):
    a = load(f"kooora_tv_{ymd}.json")
    d = C.title_day(a["headline"])
    return d, C.parse_article(a["body"], d)


def fixtures(ymd):
    fx = load(f"tv_fixtures_{ymd}.json")
    d = datetime.strptime(ymd, "%Y%m%d").date()
    nxt = (d + timedelta(days=1)).strftime("%Y%m%d")
    st = Fake({f"all/{ymd}.json": fx, f"all/{nxt}.json": fx})
    return C.load_fixtures(st, ymd) + C.load_fixtures(st, nxt)


def line(lines, home):
    return next(ln for ln in lines if ln["home"] == home)


# ---------------------------------------------------------------- the article
def test_the_day_comes_from_the_headline_not_the_slug():
    assert C.title_day("جدول مباريات اليوم الأربعاء 30 سبتمبر 2026 .. القنوات الناقلة والمعلقين") == date(2026, 9, 30)
    assert C.title_day("جدول مباريات اليوم الأحد 19 يوليو 2026 في كأس العالم .. القنوات الناقلة والمعلقين") == date(2026, 7, 19)
    assert C.title_day("جدول مباريات اليوم السبت 16 مايو/أيار 2026 .. القنوات الناقلة والمعلقين") == date(2026, 5, 16)
    assert C.title_day("ما القنوات الناقلة لمباراة الأرجنتين وبوليفيا الودية؟") is None      # a single-match piece: no commentators
    # the where-to-watch sitemap has no titles: a slug that says «الخميس 24» on an article first published on the 26th
    # (Kooora reuses slugs) is a stale copy and is skipped; a slug that fits its lastmod is kept
    xml = ("<urlset><url><loc>https://www.kooora.com/%D9%83/%D8%A3/%D8%AC%D8%AF%D9%88%D9%84-%D9%85%D8%A8%D8%A7%D8%B1%D9%8A%D8%A7%D8%AA-%D8%A7%D9%84%D9%8A%D9%88%D9%85"
           "-%D8%A7%D9%84%D8%AE%D9%85%D9%8A%D8%B3-24-%D8%B3%D8%A8%D8%AA%D9%85%D8%A8%D8%B1-2026-%D8%A7%D9%84%D9%82%D9%86%D9%88%D8%A7%D8%AA-%D8%A7%D9%84%D9%86%D8%A7%D9%82%D9%84%D8%A9-"
           "%D9%88%D8%A7%D9%84%D9%85%D8%B9%D9%84%D9%82%D9%8A%D9%86/bltaf97837a756cf11a</loc><lastmod>2026-09-25T21:00:03.119Z</lastmod></url>"
           "<url><loc>https://www.kooora.com/%D9%83/%D8%A3/%D8%AC%D8%AF%D9%88%D9%84-%D9%85%D8%A8%D8%A7%D8%B1%D9%8A%D8%A7%D8%AA-%D8%A7%D9%84%D9%8A%D9%88%D9%85"
           "-%D8%A7%D9%84%D8%AE%D9%85%D9%8A%D8%B3-24-%D8%B3%D8%A8%D8%AA%D9%85%D8%A8%D8%B1-2026-%D8%A7%D9%84%D9%82%D9%86%D9%88%D8%A7%D8%AA-%D8%A7%D9%84%D9%86%D8%A7%D9%82%D9%84%D8%A9-"
           "%D9%88%D8%A7%D9%84%D9%85%D8%B9%D9%84%D9%82%D9%8A%D9%86/blt9908a3d13a6041ac</loc><lastmod>2026-09-23T21:00:00.790Z</lastmod></url></urlset>")
    got = C.sitemap_articles(xml)
    assert [(a["id"], a["day"]) for a in got] == [("blt9908a3d13a6041ac", "2026-09-24")]


def test_clocks_are_converted_and_cross_checked():
    ko, ok = C.kickoffs("20:30 السعودية، 21:30 الإمارات", date(2026, 9, 30))
    assert ok and ko == [datetime(2026, 9, 30, 17, 30, tzinfo=UTC)]
    ko, ok = C.kickoffs("16:00 مصر، 14:00 المغرب", date(2026, 9, 26))                 # «م» of «مصر» is not «مساءً»
    assert ok and ko == [datetime(2026, 9, 26, 13, 0, tzinfo=UTC)]
    ko, ok = C.kickoffs("16:30 السعودية، 17:30 الإمارا", date(2026, 5, 16))           # a word cut short in the article
    assert ok and ko == [datetime(2026, 5, 16, 13, 30, tzinfo=UTC)]
    assert C.kickoffs("13:00 السعودية، 12:00 الإمارات", date(2026, 9, 25))[1] is False  # the two clocks disagree: no time trusted
    ko, ok = C.kickoffs("02:00 السعودية، 03:00 الإمارات", date(2026, 9, 28))           # after midnight: this night or the next
    assert ok and datetime(2026, 9, 28, 23, 0, tzinfo=UTC) in ko


def test_channels_one_name_each_and_no_ads():
    ch = lambda s: (C.channel(s) or {}).get("name")
    assert ch("beIN Sports 1") == ch("beIN SPORTS 1") == ch("بى ان سبورت 1HD") == ch("beIN Sports Mena 1") == "beIN SPORTS 1"
    assert ch("beIN Xtra 2") == "beIN SPORTS XTRA 2" and ch("beIN Sports") == "beIN SPORTS"
    assert ch("MBC شاهد رياضة") == ch("شاهد MBC") == "شاهد" and ch("MBC ACTION") == "MBC Action"
    assert ch("الكأس 1") == "الكأس 1" and ch("قنوات الكأس") == "الكأس" and ch("الشارقة الرياضية 2") == "الشارقة الرياضية 2"
    assert C.channel("الكويت الرياضية")["country"] == "KW" and C.channel("beIN Sports 3")["country"] is None
    assert C.channel("ثمانية 2")["linear"] and not C.channel("تطبيق ثمانية")["linear"] and not C.channel("stc tv")["linear"]
    assert C.channel("Nord VPN") is None and C.channel("TV Globo") is None and C.channel("لا يوجد") is None


def test_commentators_spelled_once_and_blanks_dropped():
    assert C.commentators("لم يعلن ") == [] and C.commentators("-") == [] and C.commentators("") == []
    assert C.commentators("عبد الله الغامدي") == ["عبدالله الغامدي"]
    assert C.commentators("حفيظ الدراجي") == ["حفيظ دراجي"]
    assert C.commentators("بكر علوان / سمير المعيرفي") == ["بكر علوان", "سمير المعيرفي"]
    assert C.commentators("المعلق: عصام الشوالي") == ["عصام الشوالي"]


def test_rowspans_several_channels_and_a_second_voice():
    d, lines = article("20260927")
    assert len(lines) == 10
    bh = line(lines, "البحرين")
    assert [c["ch"]["name"] for c in bh["channels"]] == ["الشارقة الرياضية", "الكأس 1", "الكويت الرياضية", "عمان الرياضية"]
    assert bh["channels"][1]["comm"] == ["بكر علوان", "سمير المعيرفي"]           # «الكأس 1» spans three rows, two names
    jo = line(lines, "الأردن")                                                    # a table without a commentator column
    assert [(c["ch"]["name"], c["comm"]) for c in jo["channels"]] == [("الأردن الرياضية", [])]
    d, lines = article("20260919")
    st = line(lines, "شتوتجارت")                                                  # «MBC ACTION» sits in a row under a rowspan
    assert [(c["ch"]["name"], c["comm"]) for c in st["channels"]] == [("شاهد", ["نور الدين آيت علي"]), ("MBC Action", ["نور الدين آيت علي"])]
    assert line(lines, "روما")["channels"][0]["comm"] == ["فارس عوض"]            # header «التعليق»
    assert line(lines, "أينتراخت فرانكفورت")["channels"][0]["comm"] == ["عبدالعزيز السبر"]   # header left empty


# ---------------------------------------------------------------- the matching
def test_lines_find_their_fixture_among_every_league_at_that_hour():
    d, lines = article("20260919")
    m, fx, un, dr = C.match_all(lines, fixtures("20260919"), d)
    want = {"5868078": "إشبيلية", "5749681": "روما", "5802940": "ليون", "5881172": "بوروسيا مونشنجلادباح", "5881177": "شتوتجارت",
            "6072167": "صن داونز", "5795463": "نوتنجهام فورست", "5868073": "سيلتا فيجو"}
    for mid in want:
        assert mid in m, want[mid]
    assert m["5795457"] == [{"channel": "beIN SPORTS 1", "commentator": "عصام الشوالي"}]              # برايتون - آرسنال
    # «دوري جوي» lines FotMob does not list stay out, even with الاتحاد (W) - النصر (W) at the same minute
    assert {u["home"] for u in un} == {"الفيصلي", "التعاون", "ضمك", "الجبلين"}
    assert not dr
    assert len(m) == 26


def test_swapped_home_away_and_a_friendly_without_voice():
    d, lines = article("20260927")
    m, fx, un, dr = C.match_all(lines, fixtures("20260927"), d)
    assert "6052084" in m and fx["6052084"]["home"] == "اليمن"                  # Kooora wrote «قطر - اليمن»
    assert m["6280210"] == [{"channel": "الأردن الرياضية", "commentator": None, "country": "JO"}]
    assert m["6052085"][1] == {"channel": "الكأس 1", "commentator": "بكر علوان", "commentators": ["بكر علوان", "سمير المعيرفي"], "country": "QA"}
    assert len(m) == 10 and not un


def test_typos_and_spellings_still_match_on_time():
    d, lines = article("20260930")
    m, fx, un, dr = C.match_all(lines, fixtures("20260930"), d)
    assert set(m) == {"6052086", "6052087", "6040249"}                          # «إرتريا - جنوب أفريفيا» included


def test_one_exact_common_name_is_not_enough():
    """«القادسية - الأهلي» (Saudi) at the minute Qatar's «الأهلي - الشحانية» kicks off: no match (swap + weak second name)."""
    ko = datetime(2026, 9, 20, 18, 0, tzinfo=UTC)
    ln = {"home": "القادسية", "away": "الأهلي", "time": "21:00 السعودية", "competition": "دوري جوي", "kickoffs": [C.iso(ko)], "time_ok": True,
          "channels": [{"raw": "stc tv", "ch": C.channel("stc tv"), "comm": []}]}
    fx = [{"id": 1, "ko": ko, "home": {"id": 11, "names": ["الأهلي"]}, "away": {"id": 12, "names": ["الشحانية"]}, "comp": 535, "comp_name_ar": "دوري نجوم قطر"}]
    f, why = C.match_line(ln, fx, ko.date())
    assert f is None and "names differ" in why


def test_women_and_youth_sides_never_stand_in():
    assert C.name_sim("الاتحاد", "الاتحاد (W)") < 0.5 and C.name_sim("الإمارات", "الإمارات تحت 23") < 0.5
    assert C.name_sim("ليون", "ليون") == 1.0 and C.name_sim("رين", "ستاد رين") >= 0.85
    assert C.name_sim("روسيا البيضاء", "بيلاروس") == 1.0 and C.name_sim("المجر", "هنغاريا") == 1.0
    assert C.name_sim("مانشستر سيتي", "مانشستر يونايتد") < 0.72


def test_a_voice_on_two_overlapping_matches_is_dropped():
    ko = datetime(2026, 9, 26, 18, 45, tzinfo=UTC)
    mk = lambda h, a, ch: {"home": h, "away": a, "time": "", "competition": "", "kickoffs": [C.iso(ko)], "time_ok": True,
                           "channels": [{"raw": ch, "ch": C.channel(ch), "comm": ["حسن العيدروس"]}]}
    lines = [mk("إنجلترا", "إسبانيا", "beIN Sports 1"), mk("التشيك", "كرواتيا", "beIN Sports 2")]
    fx = [{"id": 1, "ko": ko, "home": {"id": 1, "names": ["إنجلترا"]}, "away": {"id": 2, "names": ["إسبانيا"]}},
          {"id": 2, "ko": ko, "home": {"id": 3, "names": ["التشيك"]}, "away": {"id": 4, "names": ["كرواتيا"]}}]
    m, _, _, dr = C.match_all(lines, fx, ko.date())
    assert m["1"] == [{"channel": "beIN SPORTS 1", "commentator": None}] and m["2"][0]["commentator"] is None
    assert len(dr) == 2
    lines[1]["channels"][0] = {"raw": "beIN Sports 1", "ch": C.channel("beIN Sports 1"), "comm": ["جواد بدة"]}   # one channel, two matches
    m, _, _, dr = C.match_all(lines, fx, ko.date())
    assert not m and {x["why"] for x in dr} == {"channel carries two overlapping matches"}


def _feeds(d):
    read = lambda n: open(str(__import__("conftest").FIX / n), encoding="utf-8").read()
    return {"kooora-feed": {d.isoformat(): {"url": "k", "at": "2026-09-30T19:30:00Z", "lines": C.kooora_feed_lines(read("kooora_feed_20261001.html"), d)}},
            "yallakora": {d.isoformat(): {"url": "y", "at": "2026-09-30T19:30:00Z", "lines": C.yallakora_lines(read("yallakora_20261001.html"), d)}}}


def test_schedules_publish_only_the_channel_both_give():
    """1 October 2026: Kooora's TV feed and Yallakora agree on beIN 4 and 3, and swap beIN 1 and 2 on two matches."""
    d, fx = date(2026, 10, 1), fixtures("20261001")
    doc = C.build_days([d], {}, lambda x: fx if x == d else [], "g", _feeds(d))[d]
    assert doc["matches"]["5181830"] == [{"channel": "beIN SPORTS 4", "commentator": None, "from": "schedules"}]     # اليونان - هولندا
    assert doc["matches"]["5181866"] == [{"channel": "beIN SPORTS 3", "commentator": None, "from": "schedules"}]     # ويلز - النرويج
    assert "5181829" not in doc["matches"] and "5181865" not in doc["matches"]
    assert {x["match"] for x in doc["disputed"]} == {"5181829", "5181865"}
    assert "6040250" not in doc["matches"]                    # غينيا - كينيا: only Yallakora names a channel
    assert {s["key"] for s in doc["sources"]} == {"kooora-feed", "yallakora"}
    # handball («الزمالك - الأهلي» on ON Sport) and women's football never enter
    assert not any("الزمالك" in l["home"] for l in _feeds(d)["yallakora"][d.isoformat()]["lines"])


def test_the_article_wins_and_takes_the_agreed_number():
    d, fx = date(2026, 10, 1), fixtures("20261001")
    ko = [C.iso(datetime(2026, 10, 1, 18, 45, tzinfo=UTC))]
    ln = lambda h, a, ch, v: {"home": h, "away": a, "time": "", "competition": "دوري الأمم الأوروبية", "kickoffs": ko, "time_ok": True,
                              "channels": [{"raw": ch, "ch": C.channel(ch), "comm": [v]}]}
    arts = {d.isoformat(): {"url": "a", "lines": [ln("اليونان", "هولندا", "beIN Sports", "عصام الشوالي"), ln("ألمانيا", "صربيا", "beIN Sports 3", "حفيظ دراجي")]}}
    doc = C.build_days([d], arts, lambda x: fx if x == d else [], "g", _feeds(d))[d]
    assert doc["matches"]["5181830"] == [{"channel": "beIN SPORTS 4", "commentator": "عصام الشوالي"}]      # «beIN SPORTS» + both say 4
    assert doc["matches"]["5181829"] == [{"channel": "beIN SPORTS 3", "commentator": "حفيظ دراجي"}]       # the article, as written
    assert "5181866" not in doc["matches"]         # the schedules' beIN 3 for ويلز - النرويج clashes with the article's beIN 3
    assert any(x["match"] == "5181866" and "already carries" in x["why"] for x in doc["disputed"])


def test_a_match_after_midnight_goes_to_the_next_days_file():
    """Kooora's list for the 28th runs to «02:00 السعودية» (03:00 UAE on the 29th): the site reads that match in 20260929.json."""
    ko = datetime(2026, 9, 28, 23, 0, tzinfo=UTC)
    ln = {"home": "كولومبوس كرو", "away": "إنتر ميامي", "time": "02:00 السعودية، 03:00 الإمارات", "competition": "الدوري الأمريكي",
          "kickoffs": [C.iso(k) for k in C.kickoffs("02:00 السعودية، 03:00 الإمارات", date(2026, 9, 28))[0]], "time_ok": True,
          "channels": [{"raw": "Apple TV", "ch": C.channel("Apple TV"), "comm": []}]}
    arts = {"2026-09-28": {"url": "u28", "lines": [ln]}, "2026-09-29": {"url": "u29", "lines": []}}
    fx = {date(2026, 9, 29): [{"id": 5071387, "ko": ko, "home": {"id": 1, "names": ["كولومبوس كرو"]}, "away": {"id": 2, "names": ["إنتر ميامي"]}}]}
    docs = C.build_days([date(2026, 9, 28), date(2026, 9, 29)], arts, lambda d: fx.get(d, []), "2026-09-28T22:00:00Z")
    assert "5071387" not in docs[date(2026, 9, 28)]["matches"] and "5071387" in docs[date(2026, 9, 29)]["matches"]
    assert [s["url"] for s in docs[date(2026, 9, 29)]["sources"]] == ["u28"]

"""«منو يعلّق؟» — which channel carries each match and who calls it (owner 2026-09-30: «اريد حتى معلقين القنوات العربية
المشهورة يبينون منو بيكونون»).

  python -m news.commentators                  # production (the Fold's tifo-journal job calls run() after the news)
  python -m news.commentators --local DIR      # everything under DIR
  python -m news.commentators --date 20260926  # one day again (re-fetches that day's article), prints what it matched
  python -m news.commentators --article F.html --date 20260926 --dry    # parse a saved article page, print, write nothing

Source: Kooora's daily article «جدول مباريات اليوم <day> .. القنوات الناقلة والمعلقين» (published ~01:00 UAE, edited during
the day). It is found through Kooora's Google-News sitemap (45 KB, two days of articles, each with its lastmod), never
through the 1.2 MB homepage; the headline gives the day (slugs are reused: «…الخميس-24-سبتمبر…» carried the 25th and 26th).
Read-only, a normal browser User-Agent, the sitemap at most every 30 min (every run from 00:40 to 02:30 UAE while the
new article is due), an article only when its lastmod moved and at most hourly.

Each table row group becomes a line {competition, home, away, kickoff candidates, channels:[{channel, commentators}]}.
A line is tied to a FotMob match only on evidence: kickoff within 20 min of the article's time (Saudi/UAE/Egypt/Morocco/…
clocks, converted and cross-checked), both team names close (Arabic folding, ج/غ spellings, aliases), the competition as a
tie-break, and a clear margin over the next candidate. Anything else goes to `unmatched` with the reason. A commentator
booked on two matches that overlap, or a numbered channel carrying two overlapping matches, is dropped: a wrong name is
worse than none.

Two schedules (Kooora's fixtures page, Yallakora's match centre) add a channel, never a voice, where both give the same
number (FEEDS below): tomorrow's matches before the article is out, and the number behind the article's bare «beIN SPORTS».

Published (public): v1/tv/<yyyymmdd>.json, one per UAE kickoff day
  {generated, date, sources:[{key, name, url, updated}],
   matches:{<matchId>:[{channel, commentator, commentators?, country?, from?}]},   from: "schedules" = channel only
   fixtures:{<matchId>:{home, away, ko, comp}}, unmatched:[{home, away, time, competition, channels, why}], dropped:[…], disputed:[…]}
State (private): state/tv/state.json"""
import argparse, difflib, gzip, html as H, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BUCKET = os.environ.get("BUCKET", "elyoxe-football-574771023173-ap-south-1")
STATE = "tv/state.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
KOOORA = "https://www.kooora.com"
SITEMAP = KOOORA + "/sitemap/google-news.xml"
SITEMAP_WTW = KOOORA + "/sitemap/editorial-where-to-watch.xml"
SITEMAP_EVERY = 30 * 60          # seconds between sitemap reads, outside the publication window
ARTICLE_EVERY = 60 * 60          # an article is re-read at most hourly, and only when its lastmod moved
UTC = timezone.utc
UAE = timezone(timedelta(hours=4))


def now_utc():
    return datetime.now(UTC)


def iso(t):
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if t else None


def parse_iso(s):
    if not s:
        return None
    try:
        t = datetime.fromisoformat(str(s).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return (t if t.tzinfo else t.replace(tzinfo=UTC)).astimezone(UTC)


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip", "Accept-Language": "ar,en;q=0.8",
                                               "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    return body.decode("utf-8", "replace")


# ------------------------------------------------------------------------------------------------ Arabic text
# code points by number (an editor or a heredoc turns escapes into invisible marks): tashkeel, Quranic marks, tatweel
_TASHKEEL = re.compile("[" + "".join(chr(a) + "-" + chr(b) for a, b in ((0x0610, 0x061A), (0x064B, 0x065F), (0x06D6, 0x06ED)))
                       + chr(0x0670) + chr(0x0640) + "]")
_BIDI = dict.fromkeys((0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069))
_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي", "ڤ": "ف", "ڨ": "ج",
                       "گ": "ك", "ک": "ك", "پ": "ب", "چ": "ج", "ی": "ي", "ھ": "ه", "ء": None})


def fold(s):
    """Letters only, one form per letter: hamza seats, ta marbuta, alef maqsura, tashkeel and tatweel folded away."""
    s = _TASHKEEL.sub("", H.unescape(str(s or ""))).translate(_FOLD).lower()
    s = re.sub(r"[^\w\s]", " ", s).replace("_", " ")
    return re.sub(r"\s+", " ", s).strip()


def clean(s):
    return re.sub(r"\s+", " ", H.unescape(str(s or "")).translate(_BIDI).replace("\xa0", " ")).strip()


AR = re.compile("[" + chr(0x0600) + "-" + chr(0x06FF) + "]")


# ------------------------------------------------------------------------------------------------ days and clocks
MONTHS = {"يناير": 1, "كانون الثاني": 1, "فبراير": 2, "شباط": 2, "مارس": 3, "اذار": 3, "ابريل": 4, "نيسان": 4, "مايو": 5,
          "ايار": 5, "يونيو": 6, "يونيه": 6, "حزيران": 6, "يوليو": 7, "يوليه": 7, "تموز": 7, "اغسطس": 8, "اب": 8,
          "سبتمبر": 9, "ايلول": 9, "اكتوبر": 10, "تشرين الاول": 10, "نوفمبر": 11, "تشرين الثاني": 11, "ديسمبر": 12,
          "كانون الاول": 12}
_MON_RE = "|".join(sorted(MONTHS, key=len, reverse=True))
DAY_RE = re.compile(r"(\d{1,2})\s+(" + _MON_RE + r")(?:\s*/?\s*(?:" + _MON_RE + r"))?\s+(20\d\d)")   # «16 مايو/أيار 2026»


def title_day(title):
    """«جدول مباريات اليوم الأربعاء 30 سبتمبر 2026 .. القنوات الناقلة والمعلقين» -> date(2026, 9, 30); None for any other
    headline (the per-match «القنوات الناقلة لمباراة…» pieces carry no commentators)."""
    f = fold(title)
    if "جدول مباريات اليوم" not in f or "المعلق" not in f:
        return None
    m = DAY_RE.search(f)
    if not m:
        return None
    try:
        return date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
    except ValueError:
        return None


# The clocks an article quotes. Fixed offsets where the country has no daylight saving; zoneinfo where it does (Egypt,
# Lebanon, Palestine). Morocco's clock is the least sure: tzdata 2026d puts it on UTC+0 from late September 2026 while
# Kooora's own lines («16:00 مصر، 14:00 المغرب» on the 26th) still count +1, and the phone's tzdata may be older still.
# Only the surest clock the line gives decides (fixed > zoneinfo > Morocco); the others are ignored.
ZONES = [("الامارات", 4), ("ابوظبي", 4), ("دبي", 4), ("سلطنه عمان", 4), ("عمان", 4), ("مسقط", 4),
         ("السعوديه", 3), ("مكه المكرمه", 3), ("مكه", 3), ("الرياض", 3), ("قطر", 3), ("الدوحه", 3), ("الكويت", 3),
         ("البحرين", 3), ("العراق", 3), ("بغداد", 3), ("اليمن", 3), ("الاردن", 3), ("سوريا", 3), ("دمشق", 3),
         ("مصر", "Africa/Cairo"), ("القاهره", "Africa/Cairo"), ("لبنان", "Asia/Beirut"), ("بيروت", "Asia/Beirut"),
         ("فلسطين", "Asia/Hebron"), ("القدس", "Asia/Hebron"), ("ليبيا", 2), ("طرابلس", 2), ("السودان", 2), ("الخرطوم", 2),
         ("تونس", 1), ("الجزائر", 1), ("المغرب", "Africa/Casablanca"), ("الرباط", "Africa/Casablanca"),
         ("موريتانيا", 0), ("نواكشوط", 0), ("غرينتش", 0), ("جرينتش", 0), ("gmt", 0)]
TIER = {z: (0 if isinstance(off, int) else 2 if off == "Africa/Casablanca" else 1) for z, off in ZONES}
# on clean() text (fold() would turn «19:30» into «19 30»); «م»/«ص» count only as a whole word, never the first letter of «مصر»
TIME_RE = re.compile(r"(\d{1,2})\s*[:.]\s*(\d{2})\s*(?:(صباحاً|صباحا|مساءً|مساء|ص|م)(?=[\s،,.)]|$))?\s*([^\d]*)")


def _zone(word):
    w = fold(word).replace("بتوقيت", "").strip(" ،,-()")
    if not w:
        return None
    for z, off in ZONES:
        if w.startswith(z) or (len(w) >= 5 and z.startswith(w)):   # «الإمارا» (a cut-off word in one article) still counts
            return z, off
    return None


def _tz(off):
    if isinstance(off, int):
        return timezone(timedelta(hours=off))
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(off)
    except Exception:
        return None


def kickoffs(text, day):
    """«20:30 السعودية، 21:30 الإمارات» on `day` -> (sorted distinct UTC kickoffs, consistent?). Times before 07:00 may be
    the night after the article's day, so both calendar days are offered; the matcher keeps whichever has a fixture."""
    got = []
    for m in TIME_RE.finditer(clean(text).replace("٫", ":")):
        hh, mm, ampm, rest = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)
        if hh > 23 or mm > 59:
            continue
        if ampm and ampm.startswith("م") and hh < 12:
            hh += 12
        z = _zone(rest)
        if not z:
            continue
        tz = _tz(z[1])
        if tz is None:
            continue
        for extra in ((0, 1) if hh < 7 else (0,)):
            loc = datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz) + timedelta(days=extra)
            got.append((loc.astimezone(UTC), z[0], extra))
    if not got:
        return [], False
    best = min(TIER[g[1]] for g in got)
    base = [g for g in got if TIER[g[1]] == best]    # a Gulf clock decides; Egypt next; Morocco only when it is all there is
    same = [g[0] for g in base if g[2] == 0]
    ok = bool(same) and max(same) - min(same) <= timedelta(minutes=5)
    return sorted({g[0] for g in base}), ok


# ------------------------------------------------------------------------------------------------ channels
# key, display, country (None = pan-Arab), linear (a real channel that can show one match at a time; apps and platforms
# can show many). Patterns run on fold()ed text.
CHANNELS = [
    (r"^(?:bein|بي ?ان|بى ?ان|بين)\s*(?:sports?|سبورتس?|سبورت|سبورتز)?\s*(?:mena)?\s*(?P<n>\d{1,2})\s*(?:hd|اتش دي)?$",
     "bein-{n}", "beIN SPORTS {n}", None, True),
    (r"^(?:bein|بي ?ان|بى ?ان)\s*(?:sports?|سبورتس?)?\s*(?:max|ماكس)\s*(?P<n>\d{1,2})\s*(?:hd)?$", "bein-max-{n}", "beIN SPORTS MAX {n}", None, True),
    (r"^(?:bein|بي ?ان|بى ?ان)\s*(?:sports?|سبورتس?)?\s*(?:xtra|extra|اكسترا|إكسترا)\s*(?P<n>\d{1,2})\s*(?:hd)?$", "bein-xtra-{n}", "beIN SPORTS XTRA {n}", None, True),
    (r"^(?:bein|بي ?ان|بى ?ان)\s*(?:sports?|سبورتس?)?\s*(?:premium|بريميوم)\s*(?P<n>\d{1,2})\s*(?:hd)?$", "bein-premium-{n}", "beIN SPORTS PREMIUM {n}", None, True),
    (r"^(?:bein|بي ?ان|بى ?ان)\s*(?:sports?|سبورتس?)?\s*(?:eng|english|الانجليزيه|انجليزي)\s*(?P<n>\d{1,2})?\s*(?:hd)?$", "bein-en-{n}", "beIN SPORTS English {n}", None, True),
    (r"^(?:قنوات\s*)?(?:bein|بي ?ان|بى ?ان)\s*(?:sports?|سبورتس?|سبورت)?\s*(?:hd|mena)?$", "bein", "beIN SPORTS", None, False),
    (r"^(?:bein\s*(?:sports?)?\s*connect|بي ان كونكت)$", "bein-connect", "beIN SPORTS CONNECT", None, False),
    (r"^(?:تطبيق\s*)?(?:tod|تود)(?:\s*tv)?$", "tod", "TOD", None, False),
    (r"^(?:ssc|اس اس سي|اس\.اس\.سي)\s*(?:sports?|سبورت)?\s*(?P<n>\d)?\s*(?:hd)?$", "ssc-{n}", "SSC {n}", "SA", True),
    (r"^(?:ssc|اس اس سي)\s*(?:extra|اكسترا)\s*(?P<n>\d)?\s*(?:hd)?$", "ssc-extra-{n}", "SSC EXTRA {n}", "SA", True),
    (r"^(?:تطبيق\s*)?(?:ثمانيه|thmanyah)\s*(?P<n>\d)?$", "thmanyah-{n}", "ثمانية {n}", "SA", None),
    (r"^(?:stc\s*tv|اس تي سي(?: تي في)?|stc)$", "stctv", "stc tv", "SA", False),
    (r"^(?:mbc\s*)?(?:شاهد|shahid)(?:\s*(?:vip|رياضه|mbc|في اي بي))?(?:\s*mbc)?$", "shahid", "شاهد", None, False),
    (r"^(?:mbc\s*action|ام بي سي اكشن)$", "mbc-action", "MBC Action", None, True),
    (r"^(?:mbc\s*(?:مصر|masr)|ام بي سي مصر)\s*(?P<n>\d)?$", "mbc-masr-{n}", "MBC مصر {n}", "EG", True),
    (r"^(?:ad\s*sports?|abu\s*dhabi\s*sports?|ابوظبي الرياضيه|ابو ظبي الرياضيه)\s*(?P<n>\d)?\s*(?:hd)?$", "ad-{n}", "أبوظبي الرياضية {n}", "AE", True),
    (r"^(?:dubai\s*sports?|دبي الرياضيه)\s*(?P<n>\d)?\s*(?:hd)?$", "dubai-{n}", "دبي الرياضية {n}", "AE", True),
    (r"^(?:sharjah\s*sports?|الشارقه الرياضيه)\s*(?P<n>\d)?\s*(?:hd)?$", "sharjah-{n}", "الشارقة الرياضية {n}", "AE", True),
    (r"^(?:قنوات\s*)?(?:الكاس|alkass)\s*(?P<n>\d|one|two|الاولي|الثانيه)?\s*(?:hd)?$", "alkass-{n}", "الكأس {n}", "QA", True),
    (r"^(?:الكويت الرياضيه|ktv\s*sports?)\s*(?P<n>\d|بلس|plus)?\s*(?:hd)?$", "ktv-{n}", "الكويت الرياضية {n}", "KW", True),
    (r"^(?:عمان الرياضيه|oman\s*sports?)\s*(?P<n>\d)?\s*(?:hd)?$", "oman-{n}", "عمان الرياضية {n}", "OM", True),
    (r"^(?:السعوديه الرياضيه|الرياضيه السعوديه|ksa\s*sports?)\s*(?P<n>\d)?\s*(?:hd)?$", "ksa-{n}", "السعودية الرياضية {n}", "SA", True),
    (r"^(?:البحرين الرياضيه|bahrain\s*sports?)\s*(?P<n>\d)?$", "bahrain-{n}", "البحرين الرياضية {n}", "BH", True),
    (r"^(?:الاردن الرياضيه|jordan\s*sports?)\s*(?P<n>\d)?$", "jordan-{n}", "الأردن الرياضية {n}", "JO", True),
    (r"^(?:العراقيه الرياضيه|الرياضيه العراقيه)\s*(?P<n>\d)?$", "iraqiya-{n}", "العراقية الرياضية {n}", "IQ", True),
    (r"^(?:on\s*(?:time\s*)?sports?|اون\s*(?:تايم\s*)?سبورتس?)\s*(?P<n>\d|plus|بلس|max|ماكس)?\s*(?:hd)?$", "on-{n}", "أون سبورت {n}", "EG", True),
    (r"^(?:الرياضيه المغربيه|arryadia|الرياضيه)$", "arryadia", "الرياضية المغربية", "MA", True),
    (r"^(?:apple\s*tv|ابل تي في)$", "appletv", "Apple TV", None, False),
    (r"^(?:يوتيوب|youtube)(?:\s.*)?$", "youtube", "يوتيوب", None, False),
]
CHANNELS = [(re.compile(p), k, d, c, lin) for p, k, d, c, lin in CHANNELS]
_WORDNUM = {"one": "1", "two": "2", "الاولي": "1", "الثانيه": "2", "plus": "بلس", "بلس": "بلس", "max": "ماكس", "ماكس": "ماكس"}
NOT_CHANNEL = re.compile(r"vpn|اشترك|شاهد من هنا|^لا يوجد|غير منقول|لم يعلن|لم تعلن|^-+$|^—$|^غير متوفر|^لا توجد")


def channel(raw):
    """Raw cell text -> {key, name, country, linear} or None (an ad, «لا يوجد», a channel from outside the Arab world)."""
    t = clean(raw)
    if not t:
        return None
    f = fold(t)
    f = re.sub(r"^(?:قناه|قنوات)\s+(?=\S)", "", f).strip()
    f = re.sub(r"\s*(?:hd|اتش دي)$", "", f).strip() or f
    if not f or NOT_CHANNEL.search(f):
        return None
    for rx, key, disp, country, linear in CHANNELS:
        m = rx.match(f)
        if not m:
            continue
        n = (m.groupdict().get("n") or "").strip()
        n = _WORDNUM.get(n, n)
        k = key.replace("-{n}", "-" + n if n else "").replace("{n}", n)
        name = re.sub(r"\s+", " ", disp.replace("{n}", n)).strip()
        lin = linear if linear is not None else bool(n)       # «ثمانية 1» is a channel; «ثمانية» alone is the app
        return {"key": k, "name": name, "country": country, "linear": bool(lin)}
    if AR.search(t):                                          # an Arabic channel the table doesn't know: keep its own name
        return {"key": "x-" + f.replace(" ", "-"), "name": t, "country": None, "linear": False}
    return None                                               # Latin and unknown: TV Globo, fuboTV — not for our viewers


# ------------------------------------------------------------------------------------------------ commentators
# One spelling per famous voice (fold() form of every variant -> the name printed). Everyone else keeps the article's
# spelling, with «عبد الله» written «عبدالله».
FAMOUS = ["عصام الشوالي", "حفيظ دراجي", "رؤوف خليف", "علي سعيد الكعبي", "فارس عوض", "عامر عبدالله", "يوسف سيف", "جواد بدة",
          "حسن العيدروس", "فهد العتيبي", "عيسى الحربين", "خليل البلوشي", "محمد بركات", "أحمد الطيب", "نوفل باشي",
          "عبدالله الغامدي", "عامر الخوذيري", "علي محمد علي", "أحمد البلوشي", "محمد السعدي", "حسن العيدروس", "جواد بدة",
          "عبدالله الحربي", "عبدالله السعدي", "عصام عبده", "عبدالعزيز السبر", "محمد الشامسي", "أحمد الحامد", "أيمن جادة",
          "مدحت شلبي", "محمد الكواليني", "سوار الذهب", "طارق الملا", "مصطفى ناظم", "موسى عيد", "محمد الهنائي",
          "سمير المعيرفي", "علي الشمري", "حماد العنزي", "محمد العتيبي", "خالد الحدي", "صلاح الحمداني", "بكر علوان",
          "أحمد الكعبي", "محمد النحوي", "منتصر الأزهري", "باسم الزير", "أحمد عبده", "أحمد فؤاد", "محمد فوزي",
          "نور الدين آيت علي", "فهد عريشي", "أنيس السحباني", "فهد الدريبي", "سمير اليعقوبي", "فيصل الهندي", "أحمد الخير",
          "محمد حسين", "عبدالله الشهري", "أحمد النفيسة", "سليمان الشريف", "محمد موسى", "علي الغيلاني", "حسن العيدروس"]
VARIANTS = {"حفيظ الدراجي": "حفيظ دراجي", "عصام شوالي": "عصام الشوالي", "رءوف خليف": "رؤوف خليف", "رووف خليف": "رؤوف خليف",
            "حسن عيدروس": "حسن العيدروس", "علي الكعبي": None, "عامر عبد الله": "عامر عبدالله", "عيسي الحربين": "عيسى الحربين",
            "خليل بلوشي": "خليل البلوشي", "يوسف سيف الدين": None, "فهد عتيبي": "فهد العتيبي"}
NOT_NAME = re.compile(r"^(?:لم ?يعلن|لم ?تعلن|لم ?يحدد|لم ?يتحدد|لم ?يتم|غير (?:محدد|معروف|متوفر|معلن)|بدون(?: تعليق)?|لا يوجد|"
                      r"يعلن لاحقا|سيعلن|يحدد لاحقا|لاحقا|قريبا|tba|tbd|-+|—|\?+|x)$")
TITLES = re.compile(r"^(?:المعلق(?: الرياضي)?|الكابتن|كابتن|تعليق|بصوت|المعلقين)\s*[:：]?\s*")


def _ckey(s):
    """fold() plus «عبد الله» == «عبدالله»: the key two spellings of one person share."""
    return re.sub(r"\bعبد\s+(?=ال)", "عبد", fold(s)).replace(" ", "")


_FAMOUS = {}
for _n in FAMOUS:
    _FAMOUS[_ckey(_n)] = _n
for _v, _n in VARIANTS.items():
    if _n:
        _FAMOUS[_ckey(_v)] = _n


def commentators(raw):
    """Raw cell -> list of names (empty when none was announced). «بكر علوان / سمير المعيرفي» is two."""
    t = clean(raw)
    if not t:
        return []
    t = re.sub(r"\([^)]*\)", " ", t)                  # «(من الاستوديو)»
    out = []
    for part in re.split(r"\s*(?:/|،|,|\+|&| و(?=\s)|\s-\s)\s*", t):
        p = TITLES.sub("", clean(part)).strip(" .:-–—")
        if not p or NOT_NAME.match(fold(p)):
            continue
        if not AR.search(p) or re.search(r"\d", p) or len(p) > 40:
            continue
        words = p.split()
        if len(words) < 2 or len(words) > 5:
            continue
        name = _FAMOUS.get(_ckey(p))
        if not name:
            name = re.sub(r"\bعبد\s+(?=ال)", "عبد", p)   # the article's spelling, «عبد الله» joined
        if name not in out:
            out.append(name)
    return out


# ------------------------------------------------------------------------------------------------ the article
class _Blocks(HTMLParser):
    """Article body -> [("h", text)] and [("table", rows)]: rows of cells {text, rs, cs, th}. Tables inside tables are flat."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.stack, self.h, self.buf = [], [], None, []
        self.rows, self.row, self.cell, self.depth, self.skip = None, None, None, 0, 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self.rows is None:
            self.h = []
        elif tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.rows = []
        elif tag == "tr" and self.rows is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            def num(v):
                try:
                    return max(1, min(int(v or 1), 60))
                except ValueError:
                    return 1
            self.cell = {"text": [], "rs": num(a.get("rowspan")), "cs": num(a.get("colspan")), "th": tag == "th"}
        elif tag in ("br", "p", "div", "li") and self.cell is not None:
            self.cell["text"].append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self.h is not None:
            t = clean("".join(self.h))
            if t:
                self.out.append(("h", t))
            self.h = None
        elif tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.cell["text"] = clean("".join(self.cell["text"]))
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.row is not None and self.rows is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == "table":
            self.depth = max(0, self.depth - 1)
            if self.depth == 0 and self.rows is not None:
                self.out.append(("table", self.rows))
                self.rows = self.row = self.cell = None

    def handle_data(self, data):
        if self.skip:
            return
        if self.cell is not None:
            self.cell["text"].append(data)
        elif self.h is not None:
            self.h.append(data)


def grid(rows):
    """Rows with rowspan/colspan -> a rectangular grid of cell dicts (the same dict repeated where it spans)."""
    out, pending = [], {}
    for r in rows:
        line, col, cells = [], 0, list(r)
        while cells or any(c >= col for c in pending):
            if col in pending:
                left, cell = pending[col]
                line.append(cell)
                if left > 1:
                    pending[col] = (left - 1, cell)
                else:
                    del pending[col]
                col += 1
                continue
            if not cells:
                line.append(None)
                col += 1
                continue
            c = cells.pop(0)
            for _ in range(c["cs"]):
                line.append(c)
                if c["rs"] > 1:
                    pending[col] = (c["rs"] - 1, c)
                col += 1
        while line and line[-1] is None:
            line.pop()
        out.append(line)
    return out


ROLE = [("match", re.compile(r"مباراه|المباراه|اللقاء|الفريقين|المواجهه")), ("time", re.compile(r"موعد|توقيت|الوقت|الساعه")),
        ("channel", re.compile(r"قناه|قنوات|الناقل")), ("comm", re.compile(r"معلق|تعليق"))]
SEP = re.compile(r"\s+(?:-|–|—|×|x|ضد|vs\.?)\s+|\s*[-–—]\s*")
SKIP_HEAD = re.compile(r"جدول مباريات اليوم|كيف تشاهد|القنوات الناقله لمباريات|طالع الجدول|ما القنوات|شاهد")


def _roles(header):
    """Header cells -> {role: column}. Empty header cells take the roles left over, in table order."""
    roles, free = {}, []
    for i, c in enumerate(header):
        f = fold(c["text"]) if c else ""
        hit = next((r for r, rx in ROLE if rx.search(f) and r not in roles), None)
        if hit:
            roles[hit] = i
        else:
            free.append(i)
    for r in [r for r, _ in ROLE if r not in roles]:
        if free:
            roles[r] = free.pop(0)
    return roles


def split_match(text):
    t = clean(text)
    parts = [p.strip() for p in SEP.split(t, maxsplit=1)] if SEP.search(t) else []
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None
    return parts[0], parts[1]


def parse_article(body, day):
    """Article HTML body + its day -> lines [{competition, home, away, time, kickoffs, time_ok, channels:[{raw, ch, comm}]}]."""
    p = _Blocks()
    p.feed(body or "")
    p.close()
    lines, comp = [], ""
    for kind, x in p.out:
        if kind == "h":
            f = fold(x)
            if not SKIP_HEAD.search(f):
                comp = x
            continue
        g = grid(x)
        if not g:
            continue
        head = next((r for r in g[:2] if r and (all(c and c["th"] for c in r if c) or
                                                  any(c and ROLE[0][1].search(fold(c["text"])) for c in r))), None)
        roles = _roles(head) if head else {"match": 0, "time": 1, "channel": 2, "comm": 3}
        if "match" not in roles or "channel" not in roles:
            continue
        cur, sub = None, comp
        for r in g:
            if r is head or not r:
                continue
            cell = lambda role: (r[roles[role]] if role in roles and roles[role] < len(r) else None)
            mc = cell("match")
            if mc is None:
                continue
            distinct = {id(c) for c in r if c}
            if len(distinct) == 1 and not split_match(mc["text"]):     # a full-width row: a sub-heading inside the table
                sub = mc["text"] or sub
                continue
            teams = split_match(mc["text"])
            if not teams:
                continue
            tc, cc, kc = cell("time"), cell("channel"), cell("comm")
            if cur is None or cur["_cell"] is not mc:
                ko, ok = kickoffs(tc["text"] if tc else "", day)
                cur = {"_cell": mc, "competition": sub, "home": teams[0], "away": teams[1], "time": tc["text"] if tc else "",
                       "kickoffs": [iso(k) for k in ko], "time_ok": ok, "channels": []}    # ISO strings: the lines live in the JSON state
                lines.append(cur)
            raw = cc["text"] if cc else ""
            names = commentators(kc["text"]) if kc and kc is not mc and kc is not cc else []
            slot = next((c for c in cur["channels"] if c["raw"] == raw), None)
            if slot is None:
                slot = {"raw": raw, "ch": channel(raw), "comm": []}
                cur["channels"].append(slot)
            for n in names:
                if n not in slot["comm"]:
                    slot["comm"].append(n)
    for ln in lines:
        ln.pop("_cell", None)
        ln["channels"] = [c for c in ln["channels"] if c["ch"]]
    return lines


def page_data(page):
    """Kooora pages are Next.js: the content is the JSON in __NEXT_DATA__ (props.pageProps.data)."""
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', page, re.S)
    if not m:
        raise ValueError("no __NEXT_DATA__ on the page")
    return ((json.loads(m.group(1)).get("props") or {}).get("pageProps") or {}).get("data")


def next_data(page):
    art = (page_data(page) or {}).get("article")
    if not art or not art.get("body"):
        raise ValueError("no article body in __NEXT_DATA__")
    return art


def sitemap_articles(xml):
    """Kooora's google-news sitemap -> the daily commentator articles [{id, url, title, day, lastmod, published}]."""
    out = []
    for u in re.findall(r"<url>(.*?)</url>", xml, re.S):
        loc = re.search(r"<loc>([^<]+)</loc>", u)
        if not loc:
            continue
        url = H.unescape(loc.group(1)).strip()
        title = re.search(r"<news:title>([^<]+)</news:title>", u)
        # the where-to-watch sitemap has no titles: the slug stands in, and its day must fit the lastmod (slugs are reused)
        t = H.unescape(title.group(1)) if title else urllib.parse.unquote(url).rstrip("/").rsplit("/", 2)[-2].replace("-", " ")
        d = title_day(t)
        if not d:
            continue
        lm = re.search(r"<lastmod>([^<]+)</lastmod>", u)
        pub = re.search(r"<news:publication_date>([^<]+)</news:publication_date>", u)
        published = parse_iso(pub.group(1)) if pub else (parse_iso(lm.group(1)) if lm and not title else None)
        if published:   # a headline whose day is not the UAE day it went out (or the next) is a stale copy: skip it
            pd = (published + timedelta(hours=4)).date()
            if d not in (pd, pd + timedelta(days=1)):
                continue
        out.append({"id": urllib.parse.unquote(url).rstrip("/").rsplit("/", 1)[-1], "url": url, "title": t, "day": d.isoformat(),
                    "lastmod": lm.group(1).strip() if lm else None, "published": iso(published)})
    return out


# ------------------------------------------------------------------------------------------------ channel-only schedules
# Two schedules name the channel (never the voice) days ahead: Kooora's fixtures page (a TV-listings feed of every country's
# channels; the Arab ones are kept) and Yallakora's match centre (Egypt's view, one channel per match). They only ever
# publish together: a numbered channel both give for a fixture fills a match the day's article does not cover (tomorrow's,
# before the article is out) and names the number where the article only says «beIN SPORTS». They never override the
# article. On 1 October 2026 they agreed on 5 of 7 Nations League matches and swapped beIN 1 and 2 on the other two.
FEED_EVERY = 3 * 3600
NOT_FOOTBALL = re.compile(r"ihf|handball|basket|fiba|volley|fivb|tennis|squash|futsal|beach|esport|اليد|السله|الطايره|التنس|"
                          r"الاسكواش|الصالات|الشاطييه|سيدات|للسيدات|نسايي")


def _feed_channels(names):
    """Numbered/national channels only (a platform such as TOD or beIN CONNECT carries everything and proves nothing);
    beIN's English channels are not for this site."""
    seen, out = set(), []
    for n in names:
        ch = channel(n or "")
        if not ch or not ch["linear"] or ch["key"].startswith("bein-en") or ch["key"] in seen:
            continue
        seen.add(ch["key"])
        out.append(ch)
    return out


def kooora_feed_url(d):
    return KOOORA + "/" + urllib.parse.quote("كرة-القدم/مواعيد-المباريات") + "/" + d.isoformat()


def kooora_feed_lines(page, d=None):
    """Kooora's fixtures page (props.pageProps.data: [{competition, matches:[{startDate, teamA, teamB, tvChannels}]}])."""
    out = []
    for c in page_data(page) or []:
        comp = clean((c.get("competition") or {}).get("name"))
        if NOT_FOOTBALL.search(fold(comp)):
            continue
        for x in c.get("matches") or []:
            ko = parse_iso(x.get("startDate"))
            chans = _feed_channels(t.get("name") for t in x.get("tvChannels") or [])
            if not ko or not chans:
                continue
            out.append({"competition": comp, "home": clean((x.get("teamA") or {}).get("name")), "away": clean((x.get("teamB") or {}).get("name")),
                        "time": iso(ko), "kickoffs": [iso(ko)], "time_ok": True, "channels": [{"raw": ch["name"], "ch": ch, "comm": []} for ch in chans]})
    return out


def yallakora_url(d):
    return f"https://www.yallakora.com/matches-center?date={d.month}/{d.day}/{d.year}"


def yallakora_lines(page, d):
    """Yallakora's match centre for an Egyptian day: cards per tournament, one channel and a Cairo time per match."""
    out, cairo = [], _tz("Africa/Cairo")
    for card in re.split(r'<div class="\d+ matchCard', page)[1:]:
        tour = re.search(r"<h2>\s*([^<]+?)\s*</h2>", card)
        tname = clean(tour.group(1)) if tour else ""
        if NOT_FOOTBALL.search(fold(tname)):
            continue
        for it in re.split(r"liveScoreMatchId=", card)[1:]:
            href = re.search(r'href="/([^/"]+)/', it)
            if href and NOT_FOOTBALL.search(href.group(1).lower()):
                continue
            ch = re.search(r'<div class="channel[^"]*">([^<]*)</div>', it)
            a = re.search(r'teamA">.*?<p>([^<]*)</p>', it, re.S)
            b = re.search(r'teamB">.*?<p>([^<]*)</p>', it, re.S)
            t = re.search(r'<span class="time">\s*(\d{1,2}):(\d{2})\s*</span>', it)
            chans = _feed_channels([H.unescape(ch.group(1))] if ch else [])
            if not (chans and a and b and t and cairo):
                continue
            ko = datetime(d.year, d.month, d.day, int(t.group(1)), int(t.group(2)), tzinfo=cairo).astimezone(UTC)
            out.append({"competition": tname, "home": clean(a.group(1)), "away": clean(b.group(1)), "time": iso(ko), "kickoffs": [iso(ko)],
                        "time_ok": True, "channels": [{"raw": c["name"], "ch": c, "comm": []} for c in chans]})
    return out


FEEDS = {"kooora-feed": ("كووورة (جدول المباريات)", kooora_feed_url, kooora_feed_lines),
         "yallakora": ("يلا كورة", yallakora_url, yallakora_lines)}


# ------------------------------------------------------------------------------------------------ our fixtures
STOP = {"نادي", "منتخب", "فريق", "fc", "sc", "cf", "ac", "cd", "club", "كلوب"}
NISBA = {"مصري", "سعودي", "قطري", "اماراتي", "كويتي", "بحريني", "عماني", "اردني", "عراقي", "سوري", "لبناني", "ليبي", "تونسي",
         "جزائري", "مغربي", "سوداني", "يمني", "فلسطيني", "الاماراتي", "المصري", "السعودي"}
WOMEN = re.compile(r"(?:^|\s)(?:w|سيدات|للسيدات|النسائي|نساء)(?:\s|$)")
YOUTH = re.compile(r"(?:u|تحت\s*)(\d\d)|(?:^|\s)(?:الاولمبي|اولمبي|للشباب|الناشئين|رديف|الرديف|b|ii|2)(?:\s|$)")   # «برشلونة 2» is the reserves
GENERIC = {"سيتي", "يونايتد", "ريال", "اتلتيكو", "اتليتيكو", "سبورتنج", "سبورتينج", "ديبورتيفو", "انتر", "دينامو", "سانت", "سان",
           "اتلتيك", "ريد", "تاون", "روفرز", "وندررز", "واندررز", "اولمبيك", "رياضي", "الرياضي", "ستاد", "اتحاد", "الاتحاد",
           "الاهلي", "اهلي", "النصر", "نصر", "الهلال", "هلال", "الشباب", "شباب", "الوحده", "وحده", "النجم", "نجم", "الجيش",
           "جيش", "الشرطه", "شرطه", "جزر", "جمهوريه", "الوطني", "للسيدات", "تحت",
           "اف", "سي", "ايه", "اس", "اي", "بي"}   # «إف سي», «إيه سي»: ignorable as the extra part of a name, never enough alone
# words that make another team of the same stem («جنوب السودان», «كوريا الشمالية», «غينيا الاستوائية», «الكونغو الديمقراطية»):
# _QCLASS below, in team_key() form
ALIASES = [("روسيا البيضاء", "بيلاروس", "بيلاروسيا"), ("المجر", "هنغاريا", "هنجاريا"), ("كاب فيردي", "كابو فيردي", "الرأس الأخضر"),
           ("كوت ديفوار", "ساحل العاج"), ("التشيك", "جمهورية التشيك", "تشيكيا"), ("أمريكا", "الولايات المتحدة", "الولايات المتحدة الأمريكية"),
           ("تركيا", "تركيه"), ("الكونغو الديمقراطية", "جمهورية الكونغو الديمقراطية", "الكونغو الديموقراطية", "كونغو الديمقراطية"),
           ("الجبل الأسود", "مونتينيغرو", "مونتنيغرو"), ("مقدونيا الشمالية", "مقدونيا"),
           ("الإمارات", "الإمارات العربية المتحدة"), ("السعودية", "المملكة العربية السعودية"), ("سوريا", "سورية"),
           ("إسواتيني", "سوازيلاند"), ("جزر القمر", "القمر"), ("هولندا", "هولاندا"), ("إنجلترا", "انكلترا"),
           ("باريس سان جيرمان", "باريس سان جرمان", "بي إس جي"), ("إنتر", "إنتر ميلان", "انترناسيونالي"),
           ("بايرن ميونخ", "بايرن ميونيخ", "بايرن"), ("مانشستر يونايتد", "مان يونايتد"), ("مانشستر سيتي", "مان سيتي"),
           ("أتلتيكو مدريد", "أتليتكو مدريد", "أتلتيكو"), ("ريال مدريد", "الريال")]
_ALIAS = {}
for _grp in ALIASES:
    for _a in _grp:
        _ALIAS.setdefault(fold(_a), set()).update(fold(x) for x in _grp)


def team_key(s):
    words = [w[2:] if w.startswith("ال") and len(w) > 4 else w for w in fold(s).split()]
    return " ".join(w for w in words if w not in STOP)


def skel(s):
    """Consonants only, ج for غ: «نوتنجهام» == «نوتنغهام», «إرتريا» == «إريتريا»."""
    k = team_key(s).replace(" ", "").replace("غ", "ج")
    return re.sub(r"[اويىه]", "", k) or k


GENERIC = {team_key(w) for w in GENERIC} | GENERIC          # the token forms name_sim compares («الاهلي» -> «اهلي»)
NISBA = {team_key(w) for w in NISBA} | NISBA
_QCLASS = {team_key(k): v for k, v in {"جنوب": "S", "الجنوبية": "S", "شمال": "N", "الشمالية": "N", "شرق": "E", "الشرقية": "E",
                                       "غرب": "W", "الغربية": "W", "الديمقراطية": "D", "الديموقراطية": "D", "الاستوائية": "Q",
                                       "الإستوائية": "Q", "الوسطى": "C", "بيساو": "B", "الجديدة": "J"}.items()}


def _quals(tokens):
    return {_QCLASS[t] for t in tokens if t in _QCLASS}


def _marks(f):
    y = YOUTH.search(f)
    return (bool(WOMEN.search(f)), (y.group(1) or y.group(0).strip()) if y else None)


def name_sim(a, b):
    """0..1: how sure two spellings are one team (1.0 = the same after folding or a known alias)."""
    fa, fb = fold(a), fold(b)
    if not fa or not fb:
        return 0.0
    if _marks(fa) != _marks(fb):                                # a women's or an U-21 side is never the first team
        return 0.2
    if fa == fb or fb in _ALIAS.get(fa, ()) or team_key(a) == team_key(b):
        return 1.0
    ka, kb = team_key(a), team_key(b)
    ta, tb = set(ka.split()), set(kb.split())
    if _quals(ta) != _quals(tb):                                # south/north, equatorial, democratic…: another country
        return 0.3
    small, big = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    sub = 0.0
    if small:
        sk_small = {skel(w) for w in small}
        if all(w in big or skel(w) in {skel(x) for x in big} for w in small):
            rest = {w for w in big if w not in small and skel(w) not in sk_small}
            distinct = any(len(w) >= 4 and w not in GENERIC for w in small)
            if rest and all(w in GENERIC for w in rest):
                sub = 0.9                                         # «رين» / «ستاد رين», «إيبسويتش» / «إيبسويتش تاون»
            elif rest and all(w in NISBA for w in rest):
                sub = 0.8                                         # «الأهلي» / «الأهلي المصري»: the time and the opponent decide
            elif distinct:
                sub = 0.8                                         # «دورتموند» / «بوروسيا دورتموند»
            else:
                sub = 0.5                                         # «ريال» alone is not «ريال مدريد»
    sa, sb = skel(a), skel(b)
    r1 = difflib.SequenceMatcher(None, ka.replace(" ", ""), kb.replace(" ", "")).ratio()
    r2 = difflib.SequenceMatcher(None, sa, sb).ratio() * 0.97 if min(len(sa), len(sb)) >= 3 else 0.0
    r = max(r1, r2)
    if min(len(ka), len(kb)) <= 4 and r < 0.9:                  # short names: «مالي»/«مالطا» are not one team
        r *= 0.8
    # a shared word with different rest is two clubs: «مانشستر سيتي»/«مانشستر يونايتد», «ريال مدريد»/«ريال بيتيس»
    only_a, only_b = ta - tb, tb - ta
    if ta & tb and only_a and only_b and not sub:
        def wsim(x, y):
            return max(difflib.SequenceMatcher(None, x, y).ratio(), difflib.SequenceMatcher(None, skel(x), skel(y)).ratio())
        if max(wsim(x, y) for x in only_a for y in only_b) < 0.7:
            r = min(r, 0.6)
    return max(sub, r)


def comp_sim(heading, cand):
    """Kooora's heading («الدوري الإسباني - الجولة 7») against a fixture's competition name: a tie-break only."""
    h = team_key(re.split(r"\s+-\s+|\s*[-–]\s*(?:الجوله|الدور|نصف|ربع|النهائي|المجموعه)", heading or "")[0])
    names = [n for n in (cand.get("comp_name_ar"), cand.get("comp_name")) if n]
    if not h or not names:
        return 0.0
    hs = set(h.split())
    best = 0.0
    for n in names:
        k = team_key(n)
        ks = set(k.split())
        j = len(hs & ks) / max(1, len(hs | ks))
        best = max(best, j, difflib.SequenceMatcher(None, h, k).ratio() * 0.8)
    return best


def _team(x):
    """A team from a day file or the compact all-matches file: dict, [id, name], or a bare name."""
    if isinstance(x, dict):
        names = [x.get(k) for k in ("name_ar", "ar", "n_ar", "short_ar", "name", "n", "name_en") if x.get(k)]
        return {"id": x.get("id") or x.get("i"), "names": names}
    if isinstance(x, (list, tuple)):
        return {"id": x[0] if x else None, "names": [str(v) for v in x[1:] if isinstance(v, str)]}
    if isinstance(x, str):
        return {"id": None, "names": [x]}
    if isinstance(x, int):
        return {"id": x, "names": []}
    return {"id": None, "names": []}


def load_fixtures(store, ymd, clubs_ar=None):
    """Our matches of one UAE day: v1/day/<ymd>.json (our competitions, Arabic names) and, when it exists,
    v1/all/<ymd>.json (every match FotMob lists that day; schema read loosely)."""
    out, seen = [], set()

    def add(m, src, teams_map=None, comps_map=None):
        if isinstance(m, (list, tuple)):
            return
        mid = m.get("id") or m.get("i")
        if not mid or str(mid) in seen:
            return
        ko = parse_iso(m.get("kickoff_utc") or m.get("ko") or m.get("utc") or m.get("t") or m.get("time"))
        if not ko:
            return
        h, a = _team(m.get("home") if "home" in m else m.get("h")), _team(m.get("away") if "away" in m else m.get("a"))
        for t in (h, a):
            if t["id"] is not None and teams_map and str(t["id"]) in teams_map:
                v = teams_map[str(t["id"])]
                t["names"] = [n for n in ([v] if isinstance(v, str) else [v.get("name_ar") or v.get("ar"), v.get("name")]) if n] + t["names"]
            if t["id"] is not None and clubs_ar and str(t["id"]) in clubs_ar:
                v = clubs_ar[str(t["id"])]
                if v.get("ar") and v["ar"] not in t["names"]:
                    t["names"].append(v["ar"])
        comp = m.get("comp") or m.get("league") or m.get("c")
        comp_id = comp.get("id") if isinstance(comp, dict) else comp
        cn = m.get("comp_name_ar") or (comp.get("name_ar") if isinstance(comp, dict) else None) or (comps_map or {}).get(str(comp_id))
        if isinstance(cn, dict):
            cn = cn.get("name_ar") or cn.get("ar")
        seen.add(str(mid))
        out.append({"id": int(mid) if str(mid).isdigit() else mid, "ko": ko, "home": h, "away": a, "comp": comp_id,
                    "comp_name_ar": cn, "comp_name": (comp.get("name") if isinstance(comp, dict) else None) or m.get("comp_name"),
                    "status": m.get("status"), "src": src})

    d = store.get_json(f"day/{ymd}.json") or {}
    for m in d.get("matches") or []:
        add(m, "day")
    try:
        a = store.get_json(f"all/{ymd}.json") or {}
    except Exception:
        a = {}
    rows = a.get("matches") or []
    fields = a.get("fields")
    tm, cm = a.get("teams") or {}, a.get("comps") or a.get("leagues") or {}
    for m in rows:
        if isinstance(m, (list, tuple)) and fields:
            m = dict(zip(fields, m))
        if isinstance(m, dict):
            add(m, "all", tm if isinstance(tm, dict) else None, cm if isinstance(cm, dict) else None)
    return out


# ------------------------------------------------------------------------------------------------ matching
WINDOW = timedelta(minutes=20)


def _best(name, team):
    return max([name_sim(name, n) for n in team["names"]] or [0.0])


def _side(line, cand):
    """(best orientation score pair, swapped?) for one fixture."""
    d = (_best(line["home"], cand["home"]), _best(line["away"], cand["away"]))
    s = (_best(line["home"], cand["away"]), _best(line["away"], cand["home"]))
    return (d, False) if sum(d) >= sum(s) - 0.05 else (s, True)


def _stem(a, team):
    """Do two names share a real word (by consonants)? «الكونغو» and «الكونغو الديموقراطية» do; «القادسية» and «الشحانية» don't."""
    ta = {skel(w) for w in team_key(a).split() if w not in GENERIC and len(w) >= 3}
    return any(ta & {skel(w) for w in team_key(n).split() if w not in GENERIC and len(w) >= 3} for n in team["names"])


def _anchor(line, pool, fixtures):
    """A team plays one match at a time: one side named exactly (a distinctive name no other fixture of the day answers to),
    the article's kickoff, and an opponent that shares a word with ours (Kooora's «الكونغو» for DR Congo, «السودان» for
    South Sudan) identify the fixture. Returns [(score, fixture, h, a, swapped)]."""
    out = []
    for f in pool:
        for mine, other, ft, fo, sw in ((line["home"], line["away"], f["home"], f["away"], False), (line["away"], line["home"], f["away"], f["home"], False),
                                        (line["home"], line["away"], f["away"], f["home"], True), (line["away"], line["home"], f["home"], f["away"], True)):
            k = team_key(mine)
            if _best(mine, ft) < 0.999 or any(w in GENERIC for w in k.split()) or len(k.replace(" ", "")) < 4:
                continue
            if any(g is not f and max(_best(mine, g["home"]), _best(mine, g["away"])) >= 0.9 for g in fixtures):
                continue
            if not _stem(other, fo):
                continue
            h, a = (1.0, _best(other, fo)) if mine == line["home"] else (_best(other, fo), 1.0)
            out.append((h + a - 0.5, f, h, a, sw))
            break
    return out


def match_line(line, fixtures, day):
    """One article line -> (fixture, info) or (None, why). Never a guess: the time and both names must agree, or the time,
    one exact and distinctive name, and an opponent of the same stem (_anchor)."""
    kos = [k for k in (parse_iso(x) if isinstance(x, str) else x for x in line.get("kickoffs") or []) if k]
    if kos:
        pool = [f for f in fixtures if any(abs(f["ko"] - k) <= WINDOW for k in kos)]
        timed = line.get("time_ok")
    else:
        pool = [f for f in fixtures if (f["ko"] + timedelta(hours=4)).date() == day]
        timed = False
    if not pool:
        return None, "no fixture at that time" if kos else "no time and no fixture that day"
    scored = []
    for f in pool:
        (sh, sa), swapped = _side(line, f)
        lo = min(sh, sa)
        cs = comp_sim(line.get("competition"), f)
        need = 0.72 if timed else 0.88                 # both names; a home/away swap needs them clearly (neutral grounds)
        if swapped:
            need = max(need, 0.85)
        if lo < need:
            continue
        scored.append((sh + sa + 0.15 * cs - (0.05 if swapped else 0), f, sh, sa, swapped))
    anchored = False
    if not scored and timed:
        scored = _anchor(line, pool, fixtures)
        if len(scored) == 1:
            f, sh, sa, sw = scored[0][1:]
            return f, {"score": round(scored[0][0], 2), "home": round(sh, 2), "away": round(sa, 2), "swapped": sw, "anchor": True}
        anchored = bool(scored)
        scored = []
    if not scored:
        if anchored:
            return None, "one exact name fits two fixtures"
        best = max(pool, key=lambda f: sum(_side(line, f)[0]))
        (sh, sa), _ = _side(line, best)
        return None, f"names differ (closest: {best['home']['names'][:1]} - {best['away']['names'][:1]}, {sh:.2f}/{sa:.2f})"
    scored.sort(key=lambda x: -x[0])
    top = scored[0]
    if len(scored) > 1 and top[0] - scored[1][0] < 0.25:
        return None, "two fixtures fit"
    if top[2] < 0.97 or top[3] < 0.97:          # a one-sided or fuzzy hit: the exact team must not play elsewhere at that time
        for f in pool:
            if f is top[1]:
                continue
            (h2, a2), _ = _side(line, f)
            if max(h2, a2) >= 0.97:
                return None, "one name fits two fixtures"
    return top[1], {"score": round(top[0], 2), "home": round(top[2], 2), "away": round(top[3], 2), "swapped": top[4]}


def overlap(a, b):
    return abs(a - b) < timedelta(minutes=110)


def match_all(lines, fixtures, day):
    """Lines -> ({matchId: [entries]}, {matchId: fixture}, unmatched, dropped)."""
    uniq = {}
    for f in fixtures:                     # a postponed match can sit in two day files: one fixture, not «two fixtures fit»
        uniq.setdefault(str(f["id"]), f)
    fixtures = list(uniq.values())
    got, unmatched = {}, []
    for ln in lines:
        if not ln["channels"]:
            continue
        f, info = match_line(ln, fixtures, day)
        if f is None:
            unmatched.append({"home": ln["home"], "away": ln["away"], "time": ln["time"], "competition": ln["competition"],
                              "channels": [{"channel": c["ch"]["name"], "commentators": c["comm"]} for c in ln["channels"]], "why": info})
            continue
        prev = got.get(f["id"])
        if prev and prev[1]["score"] >= info["score"]:
            unmatched.append({"home": ln["home"], "away": ln["away"], "time": ln["time"], "competition": ln["competition"],
                              "channels": [{"channel": c["ch"]["name"], "commentators": c["comm"]} for c in ln["channels"]],
                              "why": "another line already took this fixture"})
            continue
        got[f["id"]] = (f, info, ln)
    # sanity: one voice cannot call two overlapping matches; one numbered channel cannot air two
    dropped = []
    booked = {}
    for mid, (f, info, ln) in got.items():
        for c in ln["channels"]:
            for n in c["comm"]:
                booked.setdefault(("comm", n), []).append((mid, f["ko"]))
            if c["ch"]["linear"]:
                booked.setdefault(("ch", c["ch"]["key"]), []).append((mid, f["ko"]))
    bad = set()
    for (kind, k), uses in booked.items():
        for i in range(len(uses)):
            for j in range(i + 1, len(uses)):
                if uses[i][0] != uses[j][0] and overlap(uses[i][1], uses[j][1]):
                    bad.add((kind, k, uses[i][0]))
                    bad.add((kind, k, uses[j][0]))
    out, fx = {}, {}
    for mid, (f, info, ln) in got.items():
        entries = []
        for c in ln["channels"]:
            if ("ch", c["ch"]["key"], mid) in bad:
                dropped.append({"match": mid, "channel": c["ch"]["name"], "commentators": c["comm"], "why": "channel carries two overlapping matches"})
                continue
            names = [n for n in c["comm"] if ("comm", n, mid) not in bad]
            for n in c["comm"]:
                if n not in names:
                    dropped.append({"match": mid, "channel": c["ch"]["name"], "commentators": [n], "why": "commentator booked on two overlapping matches"})
            e = {"channel": c["ch"]["name"], "commentator": names[0] if names else None}
            if len(names) > 1:
                e["commentators"] = names
            if c["ch"]["country"]:
                e["country"] = c["ch"]["country"]
            if not any(x["channel"] == e["channel"] for x in entries):
                entries.append(e)
        if entries:
            out[str(mid)] = entries
            name = lambda t: next((n for n in t["names"] if AR.search(n)), t["names"][0] if t["names"] else "")
            fx[str(mid)] = {"home": name(f["home"]), "away": name(f["away"]), "ko": iso(f["ko"]), "comp": f.get("comp_name_ar") or ""}
    return out, fx, unmatched, dropped


# ------------------------------------------------------------------------------------------------ the run
def _clubs_ar():
    try:
        with open(os.path.join(ROOT, "names", "clubs_ar.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def ymd(d):
    return d.strftime("%Y%m%d")


def due_window(t):
    """00:40-02:30 UAE: the new day's article is due; the sitemap is read every run then."""
    u = t.astimezone(UAE)
    m = u.hour * 60 + u.minute
    return 40 <= m <= 150


def uae_day(t):
    return (t + timedelta(hours=4)).date()


def _number(article_name, agreed):
    """«beIN SPORTS» in the article + the schedules agreeing on «beIN SPORTS 3» -> «beIN SPORTS 3» (only one candidate)."""
    if re.search(r"\d", article_name):
        return article_name
    hits = [n for n in agreed if n.startswith(article_name + " ") and re.fullmatch(r"\d{1,2}", n[len(article_name) + 1:])]
    return hits[0] if len(hits) == 1 else article_name


def build_days(targets, arts, fixtures_of, gen, feeds=None):
    """One file per UAE day X: the matches that kick off on X, from X's article and from the previous day's (whose list
    runs past midnight: «02:00 السعودية» is X's early morning); the unmatched and dropped lines of X's own article.
    Then the schedules (FEEDS): where both name the same numbered channel for a fixture, that channel fills a match the
    article does not have, or gives the article's «beIN SPORTS» its number. Disagreements are listed, never published."""
    feeds = feeds or {}
    arts_res, feed_res = {}, {}
    for d in sorted({x - timedelta(days=k) for x in targets for k in (0, 1)}):
        pool = None
        a = arts.get(d.isoformat()) or {}
        if a.get("lines"):
            pool = fixtures_of(d) + fixtures_of(d + timedelta(days=1))
            arts_res[d] = (a, match_all(a["lines"], pool, d))
        for key, per in feeds.items():
            f = per.get(d.isoformat()) or {}
            if f.get("lines"):
                pool = pool if pool is not None else fixtures_of(d) + fixtures_of(d + timedelta(days=1))
                feed_res[(key, d)] = (f, match_all(f["lines"], pool, d))
    docs = {}
    for x in targets:
        matches, fx, srcs, disputed = {}, {}, [], []
        for d in (x - timedelta(days=1), x):
            if d not in arts_res:
                continue
            a, (m, f, _, _) = arts_res[d]
            took = False
            for mid, es in m.items():
                if uae_day(parse_iso(f[mid]["ko"])) == x:
                    matches[mid], fx[mid], took = [dict(e) for e in es], f[mid], True
            if took or d == x:
                srcs.append({"key": "kooora", "name": "كووورة", "url": a.get("url"), "updated": a.get("lastmod") or a.get("published")})
        # the schedules: per fixture of day X, the channels each one gives
        by, fx_s, used = {}, {}, {}
        for (key, d), (f, (m, fxx, _, _)) in feed_res.items():
            if d not in (x - timedelta(days=1), x):
                continue
            for mid, es in m.items():
                if uae_day(parse_iso(fxx[mid]["ko"])) != x:
                    continue
                by.setdefault(mid, {}).setdefault(key, {}).update({e["channel"]: e for e in es})
                fx_s[mid] = fxx[mid]
                used.setdefault(key, f)
        took_keys = set()
        for mid, per in by.items():
            if len(per) < 2:
                continue                                        # one schedule alone never publishes
            agreed = set.intersection(*[set(v) for v in per.values()])
            if mid in matches:
                for e in matches[mid]:
                    n = _number(e["channel"], agreed)
                    if n != e["channel"]:
                        e["channel"] = n
                        took_keys.update(per)
                named = {e["channel"] for e in matches[mid]}
                if agreed and not agreed & named:
                    disputed.append({"match": mid, "article": sorted(named), "schedules": sorted(agreed), "why": "the schedules agree on another channel"})
                continue
            if not agreed:
                disputed.append({"match": mid, "schedules": {k: sorted(v) for k, v in per.items()}, "why": "the schedules disagree"})
                continue
            any_e = next(iter(per.values()))
            matches[mid] = [{"channel": n, "commentator": None, **({"country": any_e[n]["country"]} if any_e[n].get("country") else {}), "from": "schedules"}
                            for n in sorted(agreed)]
            fx[mid] = fx_s[mid]
            took_keys.update(per)
        # a numbered channel the schedules add cannot air two overlapping matches of the day (the article's entries win)
        seen = []
        for mid, es in matches.items():
            ko = parse_iso(fx[mid]["ko"])
            for e in es:
                if re.search(r"\d", e["channel"]):
                    seen.append((e["channel"], ko, mid, e.get("from") == "schedules"))
        clash = set()
        for i, (c1, k1, m1, s1) in enumerate(seen):
            for c2, k2, m2, s2 in seen[i + 1:]:
                if c1 == c2 and m1 != m2 and overlap(k1, k2):
                    clash.update({(c1, m1)} if s1 and not s2 else {(c2, m2)} if s2 and not s1 else {(c1, m1), (c2, m2)} if s1 and s2 else set())
        for c, mid in clash:
            matches[mid] = [e for e in matches[mid] if not (e["channel"] == c and e.get("from") == "schedules")]
            disputed.append({"match": mid, "schedules": [c], "why": "that channel already carries another match then"})
            if not matches[mid]:
                del matches[mid]
                fx.pop(mid, None)
        for key in sorted(took_keys):
            srcs.append({"key": key, "name": FEEDS[key][0], "url": used[key].get("url"), "updated": used[key].get("at")})
        own = arts_res.get(x)
        docs[x] = {"generated": gen, "date": x.isoformat(), "sources": [s for s in srcs if s["url"]], "matches": matches, "fixtures": fx,
                   "unmatched": own[1][2] if own else [], "dropped": own[1][3] if own else [], "disputed": disputed}
    return docs


def run(store, now=None, log=print, force_day=None, article_html=None, dry=False):
    """One pass: maybe read the sitemap, maybe read an article, always re-match and publish today's and tomorrow's files."""
    t0 = time.time()
    now = now or now_utc()
    state = store.get_state(STATE) or {}
    arts = state.get("articles") or {}
    errors = {}
    today = (now + timedelta(hours=4)).date()
    days = [force_day] if force_day else [today, today + timedelta(days=1)]

    # ---- find the articles
    def read_sitemap(url, key):
        try:
            for a in sitemap_articles(fetch(url)):
                old = arts.get(a["day"]) or {}
                if old.get("id") and old["id"] != a["id"] and (old.get("lastmod") or "") > (a.get("lastmod") or ""):
                    continue                                    # two pieces for one day: the newer edit wins
                arts[a["day"]] = {**old, **a} if old.get("id") == a["id"] else a
            state[key] = {"at": iso(now)}
        except Exception as e:                                  # a sitemap failing keeps what we had
            errors[key] = str(e)[:200]

    last = parse_iso((state.get("sitemap") or {}).get("at"))
    if article_html is None and (force_day or not last or (now - last).total_seconds() >= SITEMAP_EVERY or due_window(now)):
        read_sitemap(SITEMAP, "sitemap")
    # the google-news sitemap keeps two days: an older day (a hand re-run), or today's piece missing from it by 02:00 UAE,
    # is looked up in the where-to-watch sitemap (90 KB, six months), at most every 2 hours
    lw = parse_iso((state.get("sitemap_wtw") or {}).get("at"))
    missing = [d for d in days if not (arts.get(d.isoformat()) or {}).get("url") and (force_day or (d == today and (now + timedelta(hours=4)).hour >= 2))]
    if article_html is None and missing and (force_day or not lw or (now - lw).total_seconds() >= 7200):
        read_sitemap(SITEMAP_WTW, "sitemap_wtw")

    # ---- read the articles that moved
    for d in days:
        a = arts.get(d.isoformat())
        if article_html is not None:
            a = arts[d.isoformat()] = {**(a or {}), "url": (a or {}).get("url"), "day": d.isoformat()}
            try:
                art = next_data(article_html)
                a.update({"lines": parse_article(art["body"], d), "title": art.get("headline"), "fetched": iso(now),
                          "fetched_lastmod": a.get("lastmod"), "published": art.get("publishTime")})
            except Exception as e:
                errors[d.isoformat()] = str(e)[:200]
            continue
        if not a or not a.get("url"):
            continue
        fetched = parse_iso(a.get("fetched"))
        moved = a.get("fetched_lastmod") != a.get("lastmod")
        if force_day or not fetched or (moved and (now - fetched).total_seconds() >= ARTICLE_EVERY):
            try:
                art = next_data(fetch(a["url"]))
                if title_day(art.get("headline") or "") not in (d, None):
                    raise ValueError(f"headline day {title_day(art.get('headline') or '')} is not {d}")
                a.update({"lines": parse_article(art["body"], d), "title": art.get("headline"), "fetched": iso(now),
                          "fetched_lastmod": a.get("lastmod"), "updated": art.get("updateTime")})
            except Exception as e:
                errors[d.isoformat()] = str(e)[:200]
                a["fetched"] = iso(now)                          # a broken page is retried after the hour, not every run

    # ---- the channel-only schedules, every 3 hours per day (a failure keeps the last lines)
    feeds = state.get("feeds") or {}
    for key, (_, url_of, parse) in FEEDS.items():
        per = feeds.setdefault(key, {})
        for d in (days if article_html is None else []):
            f = per.get(d.isoformat()) or {}
            last_f = parse_iso(f.get("at"))
            if not force_day and last_f and (now - last_f).total_seconds() < FEED_EVERY:
                continue
            url = url_of(d)
            try:
                per[d.isoformat()] = {"at": iso(now), "url": url, "lines": parse(fetch(url), d)}
            except Exception as e:
                errors[f"{key} {d.isoformat()}"] = str(e)[:200]
                per[d.isoformat()] = {**f, "at": iso(now)}
    state["feeds"] = feeds

    # ---- match and publish
    gen = iso(now)
    clubs, cache = _clubs_ar(), {}

    def fixtures_of(d):
        if d not in cache:
            try:
                cache[d] = load_fixtures(store, ymd(d), clubs)
            except Exception as e:                              # a day file we cannot read: that day just matches nothing
                errors["fixtures " + ymd(d)] = str(e)[:200]
                cache[d] = []
        return cache[d]

    built = build_days(days, arts, fixtures_of, gen, feeds)
    summary, docs = {}, {}
    for d, doc in built.items():
        a = arts.get(d.isoformat()) or {}
        docs[d.isoformat()] = doc
        summary[d.isoformat()] = {"lines": len(a.get("lines") or []), "matched": len(doc["matches"]),
                                  "voices": sum(1 for es in doc["matches"].values() if any(e.get("commentator") for e in es)),
                                  "from_schedules": sum(1 for es in doc["matches"].values() if all(e.get("from") == "schedules" for e in es)),
                                  "unmatched": len(doc["unmatched"]), "dropped": len(doc["dropped"]), "disputed": len(doc["disputed"]),
                                  "fixtures": len(fixtures_of(d))}
        if not dry:
            store.put_json(f"tv/{ymd(d)}.json", doc, cache="warm")
    keep = (today - timedelta(days=3)).isoformat()
    state["articles"] = {k: v for k, v in arts.items() if k >= keep}
    state["feeds"] = {k: {d: v for d, v in per.items() if d >= keep} for k, per in feeds.items()}
    state["run"] = {"at": gen, "days": summary, "errors": errors, "secs": round(time.time() - t0, 1)}
    if not dry:
        store.put_state(STATE, state)
    log(json.dumps({"tv": state["run"]}, ensure_ascii=False))
    return docs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--local")
    ap.add_argument("--date", help="YYYYMMDD (UAE day) to redo")
    ap.add_argument("--article", help="a saved Kooora article page to parse instead of fetching")
    ap.add_argument("--dry", action="store_true", help="write nothing, print the result")
    a = ap.parse_args(argv)
    from store import Store, S3Backend, LocalBackend
    store = Store(LocalBackend(a.local)) if a.local else Store(S3Backend(BUCKET))
    day = datetime.strptime(a.date, "%Y%m%d").date() if a.date else None
    page = open(a.article, encoding="utf-8").read() if a.article else None
    docs = run(store, force_day=day, article_html=page, dry=a.dry)
    if a.dry or a.date:
        for d, doc in docs.items():
            print(json.dumps({k: doc[k] for k in ("date", "matches", "unmatched", "dropped", "disputed")}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

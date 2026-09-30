"""Official videos for Tifo's matches (owner 2026-09-30: «أول ما يتوفر فيديو رسمي سواء يوتيوب او سوشال ميديا فيه القول ينرفق
عدال للهدف اضغط لمشاهدته، ونفس الشي ملخص المباراة للمباريات»).

  python -m news.media [--local DIR] [--dry] [--explain [MATCH_ID]]      # also a step of news.run (every 15 min on the Fold)

For every match of our competitions that is live or finished in the last 48 h, it looks for the official highlights and a
clip per goal in what the official channels published after kickoff: the YouTube channels of news/sources.yaml (`youtube:`,
read for the journal anyway, and `media:`, read only here), the official X accounts the laptop's reader follows (posts that
carry a video), and FotMob's own highlights link in the match file. Every check has to agree before a video is attached: a
missing video costs nothing, a wrong one costs the page.

A highlights video names both teams (any language, clitics read through, «🇯🇴 🆚 🇸🇾»), says it is a summary (ملخص، أهداف
المباراة, highlights, resumen, sintesi, résumé, Zusammenfassung…), came out after the final whistle (or at half-time), is not
live, a full replay, a preview, a press conference, a women's or youth match, another sport, a game simulation or an old match
(any year, season or date in it must be this match's), and any score in it happened in this match. A goal clip names the
scorer (Latin or Arabic, full name or a surname no teammate or opponent shares) — or says which side scored when that side
had one goal so far («GOAL FOR PERU!») — says it is a goal (or a shot that went in), came out after that goal was scored,
is tied to the match (a team named, the club's or federation's own channel, or the competition's channel), and its score,
minute, penalty, own-goal, equaliser and «second goal» words agree with the event. Two goals by one player are told apart
by those, or by when the clip came out; otherwise the clip is left out. During a live match a clip waits for a match file
read 10 minutes after it came out, so the goal it shows is already in the file.

Published (public, v1/):
  media/<matchId>.json   {generated, match, highlights: [video], goals: {"<minute>-<playerId>": [video]}}
                         video = {id, url, title, source (youtube|x), channel, published, image, embed, vertical, lang, conf,
                         found_by (tifo|fotmob), kind (highlights only: summary|goals)}
  media/recent.json      {generated, matches: [{id, comp, kickoff_utc, status, score, home, away, highlights, goals}]}
State (private): state/news/media.json — videos seen (4 days), the match files already read, what each media file holds,
the embed checks."""
import argparse, concurrent.futures as CF, hashlib, json, os, re, sys, time, unicodedata, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from news import readers as RD
from news.entities import norm, ar_variants, LATIN_STOP, AR_STOP

STATE = "news/media.json"
WINDOW_H = 48                 # a match is followed this long after kickoff (live polling on the site, goal clips)
FOLLOW_H = 7 * 24             # ... and its highlights this long (late extended highlights)
KEEP_VIDEOS_H = 96            # videos are kept this long (the matching runs again on them every run)
LIVE = {"live", "ht"}
DONE = {"finished", "awarded"}
NATIONAL_EXTRA = {329, 77, 10242, 11156}      # national-team competitions whose scope is not "national"
UTC = timezone.utc


def now():
    return datetime.now(UTC)


def iso(t):
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if t else None


def ptime(s):
    if not s:
        return None
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (t if t.tzinfo else t.replace(tzinfo=UTC)).astimezone(UTC)


# ------------------------------------------------------------------------------------------------ text
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
BIDI = re.compile("[​-‏‪-‮⁦-⁩﻿]")
PARTICLES = {"de", "del", "della", "di", "da", "do", "dos", "das", "du", "des", "of", "the", "von", "van", "der", "den", "y", "e"}


def prep(s):
    """Raw title -> text for norm(): Western digits, no bidi marks, hashtags split («#AtletiRealMadrid» -> «Atleti Real Madrid»,
    «#السعودية_العراق» -> «السعودية العراق»), possessives dropped («Kane's» -> «Kane»)."""
    s = unicodedata.normalize("NFKC", BIDI.sub("", (s or "").translate(AR_DIGITS))).replace("’", "'").replace("`", "'")   # 𝗠𝗔𝗧𝗖𝗛 -> MATCH
    s = re.sub(r"#(\w+)", lambda m: " " + re.sub(r"(?<=[a-z])(?=[A-Z])|_", " ", m.group(1)) + " ", s)
    return re.sub(r"(?i)(?<=[a-z])'s\b", "", s)


def join_abd(tt):
    """«عبد الله» and «عبدالله» are one name: glue «عبد» to the next word, on both sides of every comparison."""
    out, i = [], 0
    while i < len(tt):
        if tt[i] == "عبد" and i + 1 < len(tt):
            out.append("عبد" + tt[i + 1]); i += 2
        else:
            out.append(tt[i]); i += 1
    return out


def toks(s):
    return join_abd(norm(prep(s)).split())


def alts(tt):
    """Each token with the forms its Arabic clitics hide («والعراق» -> العراق, «لمنتخب» -> منتخب, «وهدف» -> هدف). Looser than
    the journal's linker (a 3-letter remainder counts): a form still has to match a whole name or keyword to mean anything."""
    out = []
    for t in tt:
        v = set(ar_variants(t))
        if len(t) >= 4 and t[0] in "وبلفك" and "ء" <= t[1] <= "ي":
            v.add(t[1:])
        out.append(v)
    return out


def has(al, phrase):
    """phrase (a token tuple) somewhere in the token alternatives."""
    n = len(phrase)
    for i in range(len(al) - n + 1):
        if all(phrase[j] in al[i + j] for j in range(n)):
            return True
    return False


def phrases(words):
    return [tuple(toks(w)) for w in words if toks(w)]


# a summary of the match
HL_WORDS = phrases([
    "highlights", "highlight", "extended highlights", "all goals", "goals and highlights", "match recap", "recap", "resumen",
    "resumen y goles", "goles del partido", "sintesi", "maxi sintesi", "résumé", "resume du match", "buts du match",
    "zusammenfassung", "alle tore", "melhores momentos", "gols da partida", "resumo", "samenvatting",
    "ملخص", "ملخص المباراة", "أهداف مباراة", "أهداف المباراة", "ملخص وأهداف", "جميع الأهداف", "أهداف اللقاء", "ملخص اللقاء"])
SUMMARY_WORDS = phrases(["highlights", "highlight", "recap", "resumen", "sintesi", "résumé", "zusammenfassung", "melhores momentos",
                         "resumo", "samenvatting", "ملخص"])
# a goal, or a shot the title says went in (language-specific words only for that channel's language)
GOAL_WORDS = phrases([
    "goal", "gol", "golazo", "golaço", "golo", "goool", "gooool", "scores", "scored", "scoring", "strike", "stunner", "screamer",
    "rocket", "banger", "volley", "header", "heads in", "heads home", "finish", "finishes", "free kick", "freekick", "penalty",
    "spot kick", "tap in", "winner", "match winner", "game winner", "equaliser", "equalizer", "opener", "brace", "hat trick",
    "hattrick", "curler", "bicycle kick", "overhead kick", "nets", "makes it", "doubles the lead", "golpazo",
    "هدف", "الهدف", "هدفا", "هدفين", "ثنائية", "ثلاثية", "هاتريك", "يسجل", "سجل", "يحرز", "أحرز", "تسجيل", "التسجيل", "قذيفة", "صاروخية", "رأسية",
    "ركلة جزاء", "ركلة حرة", "مقصية", "يهز الشباك", "هز الشباك", "هدف التعادل", "هدف الفوز"])
GOAL_WORDS_LANG = {"es": phrases(["anota", "marca", "tanto", "penalti", "penal", "cabezazo", "remate"]),
                   "pt": phrases(["marca", "golaço", "pênalti"]),
                   "it": phrases(["rete", "segna", "rigore", "punizione"]),
                   "fr": phrases(["but", "buteur", "marque", "coup franc", "pénalty"]),
                   "de": phrases(["tor", "treffer", "elfmeter", "trifft"])}
PLURAL_GOALS = phrases(["goals", "gols", "goles", "buts", "tore", "أهداف", "الأهداف", "هدفين", "ثنائية", "هاتريك",
                        "hat trick", "hattrick", "brace", "twice", "double", "doblete", "doppietta"])
MANY_GOALS = phrases(["brace", "twice", "hat trick", "hattrick", "both goals", "doblete", "doppietta", "doublé", "هدفين", "ثنائية",
                      "هاتريك", "ثلاثية"])
PEN_WORDS = phrases(["penalty", "penalti", "penal", "pen", "spot kick", "rigore", "elfmeter", "pénalty", "ركلة جزاء", "بلنتي", "جزاء"])
OWN_WORDS = phrases(["own goal", "autogol", "autogoal", "autorete", "eigentor", "csc", "contre son camp", "هدف عكسي", "عكسي",
                     "في مرماه", "بالخطأ"])
FK_WORDS = phrases(["free kick", "freekick", "ركلة حرة", "tiro libre", "punizione", "coup franc", "freistoss"])
# «هدف التعادل» names the goal that levelled the score; «الهدف الثاني» the team's (or the match's) second goal
EQ_WORDS = phrases(["هدف التعادل", "التعادل", "equaliser", "equalizer", "equalises", "equalizes", "levels it", "el empate", "gol del empate",
                    "pareggio", "égalisation", "ausgleich"])
ORD_WORDS = {1: phrases(["الهدف الأول", "هدف أول", "first goal", "opener", "opening goal", "primer gol", "primo gol", "premier but"]),
             2: phrases(["الهدف الثاني", "second goal", "segundo gol", "secondo gol", "deuxième but"]),
             3: phrases(["الهدف الثالث", "third goal", "tercer gol", "terzo gol", "troisième but"]),
             4: phrases(["الهدف الرابع", "fourth goal", "cuarto gol", "quarto gol"]),
             5: phrases(["الهدف الخامس", "fifth goal", "quinto gol"])}

# never a match summary or a goal clip
NEG_ALWAYS = phrases([
    "live", "livestream", "live stream", "watch live", "en vivo", "en directo", "en direct", "in diretta", "diretta", "relive",
    "re live", "watchalong", "watch along", "مباشر", "بث مباشر", "البث المباشر", "full match", "full game", "المباراة كاملة",
    "partido completo", "match complet", "partita completa", "jogo completo", "ganzes spiel", "preview", "pre match", "prematch",
    "build up", "previa", "avant match", "vorbericht", "قبل المباراة", "قبل مواجهة", "قبل لقاء", "استعدادات", "استعدادا",
    "تحضيرات", "press conference", "presser", "news conference", "interview", "interviews", "reaction", "reacts", "react",
    "post match", "رد فعل", "مؤتمر", "المؤتمر الصحفي", "تصريحات", "تصريح", "يتحدث", "حديث", "rueda de prensa", "declaraciones",
    "entrevista", "conference de presse", "pressekonferenz", "conferenza stampa", "intervista", "training", "trains",
    "entrenamiento", "entrainement", "allenamento", "تدريب", "تدريبات", "التدريبات", "behind the scenes", "كواليس", "inside",
    "tunnel", "all access", "vlog", "unseen", "efootball", "pes", "simulation", "gameplay", "prediction", "predictions",
    "توقعات", "توقع", "pronostico", "podcast", "بودكاست", "برنامج", "الاستوديو التحليلي", "studio", "episode", "حلقة", "الحلقة",
    "analysis", "تحليل", "brawl", "fight", "scuffle", "عراك", "شجار", "fans", "جماهير", "الجماهير", "المدرجات", "trailer",
    "promo", "tickets", "تذاكر", "kit", "جولة خاصة", "تغطية خاصة",
    # another sport between the same two countries (a broadcaster's channel carries them all)
    "volleyball", "voleibol", "basketball", "baloncesto", "basket", "handball", "balonmano", "tennis", "tenis", "futsal", "rugby",
    "cricket", "beach soccer", "esports", "efootball", "nba", "golf", "boxing", "ufc", "mma", "padel", "كرة الطائرة", "الطائرة",
    "كرة السلة", "السلة", "كرة اليد", "اليد", "التنس", "كرة الصالات", "الصالات", "الشاطئية", "الملاكمة", "الجولف", "كرة الماء",
    "البادل", "الرياضات الإلكترونية", "ألعاب القوى", "السباحة", "الفروسية", "الهجن", "جوجيتسو", "فورمولا"])
# women's and youth football (the match itself is checked for a youth side before a youth word is held against a video)
WOMEN = phrases([
    "women", "womens", "woman", "ladies", "femenino", "femenina", "femeni", "feminine", "feminin", "féminine", "frauen", "donne",
    "femminile", "wsl", "nwsl", "uwcl", "liga f", "d1 arkema", "wafcon", "lionesses", "matildas", "uswnt", "wnt", "banyana",
    "super falcons", "nadeshiko", "football ferns", "lady", "girls", "سيدات", "للسيدات", "السيدات", "النسائي", "نسائي", "النسائية",
    "الفتيات", "لبؤات", "femenil", "awfc", "lfcw", "mcwfc", "cfcw", "mufcw", "fcbfemeni", "wwc", "fifawwc", "barclayswsl"])
YOUTH = phrases([
    "primavera", "juvenil", "juveniles", "castilla", "academy", "youth", "youth league", "pl2", "premier league 2", "next gen",
    "reserves", "reserve", "friendship cup", "للناشئين", "الناشئين", "ناشئين", "للشباب", "منتخب الشباب", "الأولمبي",
    "المنتخب الأولمبي", "الرديف", "أكاديمية", "juniors cup"])
YOUTH_AGE = re.compile(r"(?i)(?:\bu[- ]?|\bsub[- ]?|\bunder[- ]?|تحت\s*|\bu)(1[3-9]|2[0-3])\b|\b(1[3-9]|2[0-3])s\b")
# a compilation or an old match: never a goal clip; a summary only when its score is this match's final score
NEG_OLD = phrases([
    "throwback", "on this day", "rewind", "flashback", "memories", "memory", "ذكريات", "من الذاكرة", "زمان", "legends", "legend",
    "classic", "classics", "retro", "vintage", "all time", "best goals", "best of", "top 10", "top 5", "top ten",
    "top five", "top 20", "ranking", "every goal", "all the goals", "goals of the", "of the month", "of the season", "so far",
    "this season", "season so far", "career", "compilation", "mix", "افضل اهداف", "أجمل أهداف", "أجمل", "أفضل", "اهداف الجولة",
    "هدف الشهر", "هدف الموسم", "goal of the month", "goal of the season", "vote", "تصويت", "mejores goles", "los mejores",
    "i migliori", "les plus beaux", "melhores gols", "milestone", "anniversary", "years ago", "first goals", "100 goals",
    "all goals of", "every free kick", "goals in", "في الموسم", "هذا الموسم", "مسيرة"])
# a goal clip that is something else: a save, a miss, an assist, a disallowed goal, a skill
NEG_GOAL = phrases([
    "assist", "assists", "save", "saves", "saved", "تصدي", "تصديات", "atajada", "atajadon", "parata", "parade", "miss", "missed",
    "misses", "ضائع", "يهدر", "أهدر", "إهدار", "falla", "disallowed", "ruled out", "ملغي", "إلغاء", "الغاء", "anulado",
    "annullato", "offside", "تسلل", "var", "skills", "skill", "nutmeg", "dribble", "مهارة", "مهارات", "woodwork", "post", "crossbar",
    "القائم", "العارضة", "celebration", "celebrations", "احتفال", "reaction", "red card", "طرد", "tackle", "block", "clearance",
    "goal line", "chance", "chances", "فرصة", "almost", "nearly", "so close", "close call", "denied", "no goal", "not a goal", "كاد",
    "كادت", "قريب", "casi", "quasi", "presque", "beinahe", "atajadón", "حارس", "keeper", "goalkeeper"])
# the word itself (the rule that picks the match's only goal so far needs it; a «strike» or a «penalty» may be anything)
GOAL_STRICT = phrases(["goal", "gol", "golazo", "golaço", "golo", "goool", "gooool", "gool", "هدف", "الهدف", "هدفا"])
GOAL_STRICT_LANG = {"fr": phrases(["but"]), "de": phrases(["tor"]), "it": phrases(["rete"])}
# between «goal» and the team it is for: «GOAL FOR PERU», «¡GOOL DE MÉXICO!», «هدف لمنتخب عمان». A word of these has to be
# there: «¡GOLAZO! Mexico vs Peru» is any goal of that match (the home side is only written first)
LINK = {"for", "de", "del", "by", "fur", "für", "pour", "per", "para", "منتخب", "المنتخب", "لمنتخب", "للمنتخب", "لـ"}
ARTICLE = {"the", "la", "el", "le", "di", "du", "a", "l"}
FLAG = re.compile(r"((?:[\U0001F1E6-\U0001F1FF]{2})|\U0001F3F4[\U000E0061-\U000E007A]+\U000E007F)\s*(?:\U0001F19A|vs\.?|v|x|×|-|–|—)\s*"
                  r"((?:[\U0001F1E6-\U0001F1FF]{2})|\U0001F3F4[\U000E0061-\U000E007A]+\U000E007F)", re.I)


def flag_iso(f):
    """🇯🇴 -> JO; the England/Scotland/Wales tag flags -> GB-ENG / GB-SCT / GB-WLS."""
    if f.startswith("\U0001F3F4"):
        tag = "".join(chr(ord(c) - 0xE0000) for c in f[1:-1]).upper()        # "GBENG"
        return {"GBENG": "GB-ENG", "GBSCT": "GB-SCT", "GBWLS": "GB-WLS"}.get(tag)
    return "".join(chr(ord(c) - 0x1F1E6 + 65) for c in f)
MONTHS = {m: i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september",
                                           "october", "november", "december"])}
MONTHS.update({norm(m): i + 1 for i, m in enumerate(["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر",
                                                      "أكتوبر", "نوفمبر", "ديسمبر"])})
MONTHS.update({"ايار": 5, "حزيران": 6, "تموز": 7, "اب": 8, "ايلول": 9, "تشرين الاول": 10})

SCORE = re.compile(r"(?<![\d/.:+])(\d{1,2})\s*(?:-|–|—|:|×|x|X)\s*(\d{1,2})(?![\d/.:]|\s*[-–/]\s*\d)")
SEASON = re.compile(r"(?<!\d)(20\d\d)\s*[/-]\s*((?:20)?\d\d)(?!\d)|(?<![\d/])(\d\d)/(\d\d)(?![\d/])")
YEAR = re.compile(r"(?<![\d/.-])(19\d\d|20\d\d)(?![\d/.-])")
DATE = re.compile(r"(?<!\d)(\d{1,2})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(20\d\d)(?!\d)|(?<!\d)(20\d\d)-(\d\d)-(\d\d)(?!\d)")
MINUTE = re.compile(r"(?<![\d.:/-])(\d{1,3})\s*(?:\+\s*(\d{1,2}))?\s*['’′](?!\w)|(?:الدقيقة|الدقيقه|minute|minuto|min\.?)\s*(\d{1,3})(?:\s*\+\s*(\d{1,2}))?"
                    r"|(?<!\d)(\d{1,3})(?:st|nd|rd|th)[\s-]+min", re.I)


class Text:
    """Everything the checks need from a title (and the first lines of a description)."""

    def __init__(self, title, desc="", lang="en"):
        self.raw = unicodedata.normalize("NFKC", BIDI.sub("", (title or "").translate(AR_DIGITS)))
        self.tt = toks(title)
        self.al = alts(self.tt)
        head = (desc or "")[:200]
        self.dal = alts(toks(head))                          # the description's head: women/youth words only
        self.lang = lang
        self.hl = any(has(self.al, p) for p in HL_WORDS)
        self.summary = any(has(self.al, p) for p in SUMMARY_WORDS)       # a summary, not only the goals («أهداف المباراة»)
        gw = GOAL_WORDS + GOAL_WORDS_LANG.get(lang, [])
        self.goal = any(has(self.al, p) for p in gw) or bool(re.search(r"(?i)\bgo{2,}l\b|\bgo+la[cç]o\b", self.raw))
        # «Full Match Highlights» (MLS) is a summary of the whole match, not the replay «FULL MATCH»
        full_hl = has(self.al, ("full", "match", "highlights")) or has(self.al, ("full", "game", "highlights"))
        self.neg = next((" ".join(p) for p in NEG_ALWAYS if has(self.al, p) and not (full_hl and p[:1] == ("full",))), None)
        self.women = next((" ".join(p) for p in WOMEN if has(self.al, p) or has(self.dal, p)), None)
        self.youth = next((" ".join(p) for p in YOUTH if has(self.al, p) or has(self.dal, p)), None)
        ages = [int(a or b) for a, b in YOUTH_AGE.findall(self.raw + " " + prep(head))]
        self.youth_age = ages[0] if ages else None
        self.old = next((" ".join(p) for p in NEG_OLD if has(self.al, p)), None)
        self.neg_goal = next((" ".join(p) for p in NEG_GOAL if has(self.al, p)), None)
        self.plural = any(has(self.al, p) for p in PLURAL_GOALS) and not self.hl
        self.many = any(has(self.al, p) for p in MANY_GOALS)
        self.pen = any(has(self.al, p) for p in PEN_WORDS)
        self.own = any(has(self.al, p) for p in OWN_WORDS)
        self.fk = any(has(self.al, p) for p in FK_WORDS)
        self.eq = any(has(self.al, p) for p in EQ_WORDS)
        self.ordinal = next((n for n, ps in ORD_WORDS.items() if any(has(self.al, p) for p in ps)), None)
        strict = GOAL_STRICT + GOAL_STRICT_LANG.get(lang, [])
        self.goal_at = [i for i in range(len(self.al)) if any(p[0] in self.al[i] and has(self.al[i:i + len(p)], p) for p in strict)]
        self.flags = [(flag_iso(a), flag_iso(b)) for a, b in FLAG.findall(title or "")]   # «🇯🇴 🆚 🇸🇾»
        self.scores = [(int(a), int(b)) for a, b in SCORE.findall(self.raw) if int(a) <= 15 and int(b) <= 15]
        self.seasons, self.years, self.dates, self.minutes = [], [], [], []
        for m in SEASON.finditer(self.raw):
            if m.group(1):
                a, b = int(m.group(1)), int(m.group(2)[-2:])
            else:
                a, b = 2000 + int(m.group(3)), int(m.group(4))
            if (a + 1) % 100 == b:
                self.seasons.append(a)
        stripped = SEASON.sub(" ", DATE.sub(" ", self.raw))
        self.years = [int(y) for y in YEAR.findall(stripped)]
        for m in DATE.finditer(self.raw):
            if m.group(4):
                self.dates.append([(int(m.group(4)), int(m.group(5)), int(m.group(6)))])
            else:
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                self.dates.append([(y, mo, d), (y, d, mo)])      # d-m-y or the US m/d/y
        for m in re.finditer(r"(\d{1,2})\s+([^\W\d_]+(?:\s+[^\W\d_]+)?)\s+(20\d\d)", norm(prep(title))):
            mo = MONTHS.get(m.group(2)) or MONTHS.get(m.group(2).split()[0])
            if mo:
                self.dates.append([(int(m.group(3)), mo, int(m.group(1)))])
        for m in MINUTE.finditer(self.raw):
            mm = m.group(1) or m.group(3) or m.group(5)
            if mm and int(mm) <= 130:
                self.minutes.append((int(mm), int(m.group(2) or m.group(4) or 0)))


# ------------------------------------------------------------------------------------------------ names
LAT_AFFIX = {"fc", "cf", "sc", "ac", "afc", "as", "ss", "ssc", "us", "ud", "cd", "rc", "rcd", "sd", "ca", "cp", "sv", "vfb", "vfl",
             "tsg", "fsv", "bsc", "ogc", "osc", "losc", "sfc", "fk", "sk", "nk", "bk", "club", "cultural", "calcio", "1", "04", "05",
             "cf", "kfc", "saudi"}
GENERIC = {"real", "united", "city", "inter", "sporting", "athletic", "atletico", "athletico", "national", "olympic", "olympique",
           "union", "racing", "club", "town", "rovers", "wanderers", "albion", "hotspur", "the", "al", "el", "sport", "sports",
           "stars", "star", "young", "boys", "county", "borussia", "eintracht", "dynamo", "dinamo", "deportivo", "nacional",
           "independiente", "instituto", "central", "juniors", "junior", "fc", "sc", "ac", "cf", "cd", "saint", "san", "santa",
           "st", "paris", "madrid", "milan", "manchester", "munchen", "munich", "lisbon", "rome", "roma", "como", "nice", "lens",
           "angers", "remo", "bahia", "tigre", "union", "vitoria", "santos", "america", "guarani", "liverpool", "everton",
           "الاتحاد", "الاهلي", "النصر", "الشباب", "الوحده", "الجزيره", "العربي", "الشرطه", "الهلال", "الريان", "الساحل",
           "المصري", "الترجي", "النجم", "الوداد", "الرجاء", "الجيش", "القادسيه", "الخليج", "الفتح", "التعاون", "الوصل",
           "العين", "الظفره", "منتخب", "المنتخب", "نادي", "فريق", "يونايتد", "سيتي", "ريال", "انتر", "قطر", "الكويت", "عمان"}
AR_PREFIX = {"نادي", "فريق", "منتخب", "المنتخب"}
# given names that are also written last («حامد عبد الله»): never a surname on their own
AR_GIVEN = {norm(x) for x in AR_STOP} | {norm(x) for x in [
    "حامد", "حمد", "ياسين", "يونس", "إسماعيل", "إبراهيم", "عماد", "وليد", "أسامة", "شريف", "عمرو", "هشام", "نبيل", "كمال",
    "زكريا", "سفيان", "حمزة", "أنس", "أيوب", "عثمان", "يحيى", "آدم", "نادر", "بلال", "مروان", "فراس", "غازي", "صلاح", "عبده",
    "حسام", "رضا", "مهند", "معاذ", "ماهر", "باسم", "وائل", "رامي", "شادي", "فادي", "عصام", "سامر", "مجدي", "لؤي", "قاسم",
    "مصطفى", "عيسى", "موسى", "مالك", "خليل", "سليمان", "داود", "هاني", "عادل", "عبدالرحمن", "عبدالعزيز", "عبدالله"]}


def _clean(tt):
    return [t for t in tt if t not in PARTICLES]


def team_forms(names_latin, names_ar, national=False):
    """-> {token tuple: strength}; strength 2 = names the team alone, 1 = only next to the other team or on its own channel.
    A national team's country name is strong («الكويت», «Oman»); the same word as a club's name is weak (Kuwait SC «نادي الكويت»).
    «المنتخب العماني» stays whole: a nisba alone («العماني») is anyone from Oman."""
    out = {}

    def put(tt, st=None):
        tt = tuple(t for t in tt if t)
        if not tt or (len(tt) == 1 and len(tt[0]) < 3):
            return
        if st is None:
            one = len(tt) == 1
            st = 1 if one and (tt[0].isdigit() or len(tt[0]) < (3 if national else 4) or (not national and tt[0] in GENERIC)) else 2
        out[tt] = max(out.get(tt, 0), st)

    for n in names_latin:
        tt = toks(n)
        if not tt:
            continue
        put(tt); put(_clean(tt))
        core = [t for t in _clean(tt)]
        while core and core[0] in LAT_AFFIX:
            core = core[1:]
        while core and core[-1] in LAT_AFFIX:
            core = core[:-1]
        put(core)
        if core and core[0] in ("al", "el") and len(core) > 1:     # «Al-Hilal» -> «hilal», «alhilal»
            put(core[1:]); put(["".join(core[:2])] + core[2:])
    for n in names_ar:
        tt = toks(n)
        if not tt:
            continue
        put(tt)
        if not national:
            put([t for t in tt if t not in AR_PREFIX])
    return out


def player_forms(latin, ars, nick=()):
    """-> {token tuple: strength}: 3 = full name, 2 = a surname or a one-word name that is long and not common, 1 = weak."""
    out = {}

    def put(tt, st):
        tt = tuple(tt)
        if tt and (len(tt) > 1 or len(tt[0]) >= 3):
            out[tt] = max(out.get(tt, 0), st)

    for n in [x for x in [latin] if x and x != "<TBD>"]:
        tt = toks(n)
        if not tt:
            continue
        if len(tt) == 1:
            put(tt, 2 if len(tt[0]) >= 5 and tt[0] not in LATIN_STOP else 1)
            continue
        put(tt, 3); put(_clean(tt), 3)
        last = tt[-1]
        if tt[-2] in ("al", "el", "ben", "bin", "abu", "ibn", "di", "de", "da", "van", "von", "dos", "le", "la"):
            put(tt[-2:], 2); put(["".join(tt[-2:])], 2)
        if len(last) >= 5 and last not in LATIN_STOP:
            put([last], 2)
        if len(tt) >= 3:                                  # «Abdullah Al Salem» -> «Abdullah Salem» is not a form; the first + last is
            put([tt[0], last], 3)
    for n in ars:
        tt = [t for t in toks(n) if t]
        if not tt:
            continue
        put(tt, 3 if len(tt) > 1 else (2 if len(tt[0]) >= 5 else 1))
        if len(tt) >= 3:
            put([tt[0], tt[-1]], 3)                       # «ناصر سلطان سيف الرواحي» -> «ناصر الرواحي»
        last = tt[-1]
        # a surname alone: a family name («الحمدان», «الرواحي») or a long one that is not also a given name («حامد عبد الله»
        # is Hamed the first name; «جيان» of Afena-Gyan is «Jean» in another title)
        if len(tt) > 1 and last not in AR_GIVEN and len(last) >= 5:
            put([last], 2)
    for n in nick:
        tt = toks(n)
        if tt:
            put(tt, 3 if len(tt) > 1 or len(tt[0]) >= 5 else 2)
    return out


class Names:
    """Name data: teams.json, names/*.json, news/aliases.yaml, news/nations.json, and FotMob's Arabic map when present."""

    def __init__(self, teams=None, players_ar=None, clubs_ar=None, fm=None, aliases=None, nations=None, national_comps=frozenset()):
        self.teams = teams or {}
        self.players_ar = players_ar or {}
        self.clubs_ar = clubs_ar or {}
        self.fm = fm or {}
        self.nations = nations or {}
        self.national_comps = set(national_comps)
        al = aliases or {}
        self.team_alias = {}
        for a, target in (al.get("teams") or {}).items():
            self.team_alias.setdefault(norm(target), []).append(a)
        for a, target in (al.get("media_teams") or {}).items():
            self.team_alias.setdefault(norm(target), []).append(a)
        self.people = {}
        for a, target in (al.get("people") or {}).items():
            self.people.setdefault(norm(target), []).append(a)
        self._tf, self._pf = {}, {}

    def iso_of(self, team):
        t = self.teams.get(str(team.get("id"))) or {}
        c = t.get("country") or {}
        if c.get("national") and c.get("iso2"):
            return c["iso2"]
        return (self.nations.get("fotmob") or {}).get(team.get("name")) or (self.nations.get("en") or {}).get(team.get("name"))

    def team(self, team, national):
        key = (team.get("id"), national)
        if key in self._tf:
            return self._tf[key]
        tj = self.teams.get(str(team.get("id"))) or {}
        lat = [team.get("name"), tj.get("name")] + self.team_alias.get(norm(team.get("name") or ""), [])
        ar = [team.get("name_ar"), tj.get("name_ar"), (self.clubs_ar.get(str(team.get("id"))) or {}).get("ar"),
              (self.fm.get("teams") or {}).get(str(team.get("id")))]
        if national:
            iso = self.iso_of(team)
            for n in (self.nations.get("names") or {}).get(iso, []) if iso else []:
                (ar if re.search("[؀-ۿ]", n) else lat).append(n)
        f = team_forms([x for x in lat if x], [x for x in ar if x], national)
        self._tf[key] = f
        return f

    def player(self, pid, name):
        if pid in self._pf:
            return self._pf[pid]
        ars = [(self.players_ar.get(str(pid)) or {}).get("ar"), (self.fm.get("players") or {}).get(str(pid))]
        f = player_forms(name, [x for x in ars if x], self.people.get(norm(name or ""), []))
        self._pf[pid] = f
        return f


# ------------------------------------------------------------------------------------------------ matches
def goals_of(md):
    """Goal events in the order they happened, with the wall-clock time before which each cannot have been scored."""
    out = []
    for e in md.get("events") or []:
        if e.get("type") not in ("goal", "penalty_goal", "own_goal") or not e.get("player") or not e["player"].get("id"):
            continue
        if (e["player"].get("name") or "") == "<TBD>":
            continue
        out.append(dict(e, lb=goal_time(md, e.get("minute"), e.get("added"))))
    out.sort(key=lambda e: (e["lb"] or datetime.max.replace(tzinfo=UTC)))
    return out


def goal_time(md, minute, added):
    """The earliest moment a goal at `minute` (+added) can have been scored, from the real half starts when FotMob has them."""
    try:
        m, a = int(minute), int(added or 0)
    except (TypeError, ValueError):
        return None
    P = md.get("periods") or {}
    k = ptime(md.get("kickoff_utc"))
    h1 = ptime(P.get("firstHalfStarted")) or k
    h2 = ptime(P.get("secondHalfStarted"))
    if not h1:
        return None
    if m <= 45:
        return h1 + timedelta(minutes=m - 1 + a)
    if m <= 90:
        return (h2 + timedelta(minutes=m - 46 + a)) if h2 else h1 + timedelta(minutes=m - 1 + 15 + a)
    e1 = ptime(P.get("firstExtraHalfStarted")) or ptime(P.get("extraTimeFirstHalfStarted"))
    if e1:
        return e1 + timedelta(minutes=m - 91 + a)
    return (h2 + timedelta(minutes=45 + 3 + m - 91 + a)) if h2 else h1 + timedelta(minutes=m - 1 + 20 + a)


def match_end(md):
    P = md.get("periods") or {}
    e = ptime(P.get("gameEnded")) or ptime(P.get("secondHalfEnded"))
    if e:
        return e
    if md.get("status") in DONE:
        k = ptime(md.get("kickoff_utc"))
        return k + timedelta(minutes=115) if k else None
    return None


def running_scores(md, goals):
    s = [(0, 0)]
    for g in goals:
        if g.get("score"):
            s.append((g["score"].get("home"), g["score"].get("away")))
    if md.get("score"):
        s.append((md["score"].get("home"), md["score"].get("away")))
    return s


def score_at(md, goals, t):
    """The score once every goal whose earliest time is before t counts (the goals' lb are lower bounds)."""
    sc = (0, 0)
    for g in goals:
        if g["lb"] and g["lb"] <= t and g.get("score"):
            sc = (g["score"].get("home"), g["score"].get("away"))
    return sc


def either(a, b):
    return a == b or a == (b[1], b[0])


def youth_age_of(md):
    for side in ("home", "away"):
        m = re.search(r"\bU-?(1[3-9]|2[0-3])\b", (md.get(side) or {}).get("name") or "")
        if m:
            return int(m.group(1))
    return None


def dates_ok(tx, md):
    k = ptime(md.get("kickoff_utc"))
    if not k:
        return True, None
    for s in tx.seasons:        # «2025/26»: the season must hold this match (a calendar-year league writes one year)
        lo, hi = datetime(s, 6, 1, tzinfo=UTC) - timedelta(days=60), datetime(s + 1, 7, 31, tzinfo=UTC)
        if not lo <= k <= hi:
            return False, f"season {s}/{(s + 1) % 100:02d}"
    for y in tx.years:
        if abs(y - k.year) > 1:
            return False, f"year {y}"
    days = {(k + timedelta(hours=h)).date() for h in (-12, 0, 4, 12)}
    for opts in tx.dates:
        ok = False
        for y, mo, d in opts:
            try:
                ok = ok or datetime(y, mo, d).date() in days
            except ValueError:
                pass
        if not ok:
            return False, "date"
    return True, None


# ------------------------------------------------------------------------------------------------ channels and videos
def channels(cfg):
    """Every YouTube channel media.py may read: the journal's `youtube:` block (clubs, leagues) and the `media:` block."""
    out = []
    for y in cfg.get("youtube") or []:
        kind = "club" if y.get("team") else "league" if y.get("comp") else "confed"
        out.append({"key": y["key"], "id": y["channel"], "name": y["name"], "lang": y.get("lang", "en"), "kind": y.get("kind", kind),
                    "team": int(y["team"]) if y.get("team") else None,
                    "comps": set(y.get("comps") or ([y["comp"]] if y.get("comp") else [])) or None, "journal": True})
    for y in ((cfg.get("media") or {}).get("youtube") or []):
        out.append({"key": y["key"], "id": y["channel"], "name": y["name"], "lang": y.get("lang", "ar"), "kind": y.get("kind", "broadcaster"),
                    "team": int(y["team"]) if y.get("team") else None, "comps": set(y.get("comps") or []) or None, "journal": False})
    return out


def feed_url(ch):
    return "https://www.youtube.com/feeds/videos.xml?channel_id=" + ch["id"]


def yt_id(url):
    m = re.search(r"(?:v=|/shorts/|youtu\.be/|/embed/)([\w-]{11})", url or "")
    return m.group(1) if m else None


def video_from_item(it, ch):
    vid = yt_id(it.get("url"))
    if not vid or not it.get("at"):
        return None
    return {"id": vid, "source": "youtube", "url": "https://www.youtube.com/watch?v=" + vid, "vertical": "/shorts/" in (it.get("url") or ""),
            "title": (it.get("title") or "")[:300], "desc": (it.get("desc") or "")[:300], "at": it["at"], "ch": ch["key"],
            "image": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"}


def fetch_feeds(chs, prefetched=None, workers=6):
    """-> ({channel key: [items]}, {key: error}). Prefetched items (news.run already read the journal's channels) are reused."""
    got, errs, todo = {}, {}, []
    for ch in chs:
        if prefetched and ch["key"] in prefetched:
            got[ch["key"]] = prefetched[ch["key"]]
        else:
            todo.append(ch)

    def one(ch):
        src = {"key": ch["key"], "kind": "youtube", "lang": ch["lang"], "tier": "official", "name": ch["name"], "url": feed_url(ch)}
        return ch["key"], RD.read_source(src)

    with CF.ThreadPoolExecutor(max_workers=workers) as ex:
        for key, (items, err) in ex.map(one, todo):
            got[key] = items
            if err:
                errs[key] = err
    return got, errs


def x_videos(box, accounts):
    """The official accounts' posts that carry a video (news/xreader.js marks them `video`), as videos."""
    names = {a["handle"].lower(): a for a in accounts or []}
    out = []
    for p in (box or {}).get("items") or []:
        a = names.get((p.get("handle") or "").lower())
        if not a or a.get("tier") != "official" or not p.get("video") or not p.get("at"):
            continue
        out.append({"id": "x" + str(p["id"]), "source": "x", "url": p["url"], "vertical": False, "title": (p.get("text") or "")[:300],
                    "desc": "", "at": ptime(p["at"]) and iso(ptime(p["at"])), "ch": "x_" + a["handle"].lower(), "image": p.get("image")})
    return out


def x_channels(accounts):
    return [{"key": "x_" + a["handle"].lower(), "id": a["handle"], "name": a.get("name") or a["handle"], "lang": a.get("lang", "en"),
             "kind": "club" if a.get("team") else "league" if a.get("comp") else "confed", "team": int(a["team"]) if a.get("team") else None,
             "comps": {int(a["comp"])} if a.get("comp") else None, "journal": True, "platform": "x"}
            for a in accounts or [] if a.get("tier") == "official"]


# ------------------------------------------------------------------------------------------------ matching
class Ctx:
    """The matches of the window, their names and goals, indexed by the first token of every name form."""

    def __init__(self, matches, names):
        self.matches = {m["id"]: m for m in matches}
        self.names = names
        self.index = {}            # first token -> [(form tuple, ("team"|"player", id, match id or None), strength)]
        self.goals = {}            # match id -> goal events (with lb)
        self.youth = {}
        self.scorers = {}          # player id -> [(match id, goal)]
        self.iso = {}              # a national team's country code -> its team id (flags: «🇯🇴 🆚 🇸🇾»)
        for m in matches:
            nat = m.get("comp") in names.national_comps
            for side in ("home", "away"):
                t = m.get(side) or {}
                for form, st in names.team(t, nat).items():
                    self.index.setdefault(form[0], []).append((form, ("team", t.get("id")), st))
                if nat and names.iso_of(t):
                    self.iso.setdefault(names.iso_of(t), set()).add(t.get("id"))
            gs = goals_of(m)
            self.goals[m["id"]] = gs
            self.youth[m["id"]] = youth_age_of(m)
            surn = {}
            for g in gs:
                p = g["player"]
                for form, st in names.player(p["id"], p.get("name")).items():
                    surn.setdefault(form, set()).add(p["id"])
            for g in gs:
                p = g["player"]
                self.scorers.setdefault(p["id"], []).append((m["id"], g))
            for form, pids in surn.items():   # a surname two scorers of the match share names neither
                for pid in pids:
                    st = self.names.player(pid, None).get(form, 0)
                    if len(pids) > 1 and len(form) == 1:
                        continue
                    self.index.setdefault(form[0], []).append((form, ("player", pid), st))
        for k in self.index:     # one entry per (form, entity)
            seen, lst = set(), []
            for f in self.index[k]:
                if (f[0], f[1]) not in seen:
                    seen.add((f[0], f[1])); lst.append(f)
            self.index[k] = lst

    def mentions(self, al, flags=(), spans=None):
        """Longest forms first, spans never overlap; one span may name several entities (they are told apart later).
        Two flags joined by «🆚»/vs name two national teams. `spans` (a list) receives (start, end, kind, id)."""
        found = []
        for i in range(len(al)):
            for a in al[i]:
                for form, ent, st in self.index.get(a, ()):
                    n = len(form)
                    if i + n <= len(al) and all(form[j] in al[i + j] for j in range(1, n)):
                        found.append((i, i + n, ent, st))
        found.sort(key=lambda f: (-(f[1] - f[0]), f[0]))
        used, taken, out = set(), set(), []
        for s, e, ent, st in found:
            if (s, e) in taken or not (set(range(s, e)) & used):
                out.append((s, e, ent, st)); used |= set(range(s, e)); taken.add((s, e))
        teams, players = {}, {}
        for s, e, (k, i), st in out:
            d = teams if k == "team" else players
            d[i] = max(d.get(i, 0), st)
            if spans is not None:
                spans.append((s, e, k, i))
        for a, b in flags:
            for iso in (a, b):
                for tid in self.iso.get(iso, ()):
                    teams[tid] = max(teams.get(tid, 0), 2)
        return teams, players


def check_highlights(v, ch, tx, md, gs, teams, youth_m, t_pub):
    """-> (conf, None) or (None, reason) for one video and one match."""
    h, a = md["home"]["id"], md["away"]["id"]
    own = ch.get("team")
    sh, sa = teams.get(h, 0), teams.get(a, 0)
    if own in (h, a):                     # the club's or federation's own channel may name only the opponent
        sh, sa = (max(sh, 1), sa) if own == h else (sh, max(sa, 1))
    if not (sh and sa):
        return None, "teams"
    # two short or shared names («الجزيرة ضد الوحدة», «ROMA-INTER») are enough on the competition's or the club's own channel
    scoped = own in (h, a) or bool(ch.get("comps") and md.get("comp") in ch["comps"])
    if max(sh, sa) < 2 and not scoped:
        return None, "weak names"
    if ch.get("comps") and md.get("comp") not in ch["comps"] and own not in (h, a):
        return None, "not this channel's competition"
    k = ptime(md.get("kickoff_utc"))
    if not k or t_pub < k + timedelta(minutes=40):
        return None, "before the match"
    if t_pub > k + timedelta(hours=FOLLOW_H):
        return None, "too late"
    # a summary comes out after the final whistle, or at half-time (the first half's); anything out while the ball is in
    # play is something else (last season's meeting posted as a reminder has this match's score one time in a thousand)
    P, end = md.get("periods") or {}, match_end(md)
    ht0 = ptime(P.get("firstHalfEnded")) or k + timedelta(minutes=47)
    ht1 = ptime(P.get("secondHalfStarted")) or k + timedelta(minutes=65)
    if not (end and t_pub >= end - timedelta(minutes=10)) and not (ht0 - timedelta(minutes=2) <= t_pub <= ht1 + timedelta(minutes=20)):
        return None, "out while the match was being played"
    ok, why = dates_ok(tx, md)
    if not ok:
        return None, why
    ya = youth_m
    if tx.youth and not ya:
        return None, "youth: " + tx.youth
    if tx.youth_age and tx.youth_age != ya:
        return None, f"U{tx.youth_age}"
    rs = running_scores(md, gs)
    final = (md["score"]["home"], md["score"]["away"]) if md.get("score") else None
    now_sc = score_at(md, gs, t_pub)
    conf = 60
    if tx.scores:
        if not all(any(either(s, r) for r in rs) for s in tx.scores):
            return None, "a score this match never had"
        if not any(either(s, now_sc) or (final and either(s, final)) for s in tx.scores):
            return None, "not the score at the time"
        conf += 15
    if tx.old:
        end = match_end(md)
        if not (tx.scores and final and any(either(s, final) for s in tx.scores) and end and t_pub <= end + timedelta(hours=24)):
            return None, "old/compilation: " + tx.old
    if own in (h, a) or (ch.get("comps") and md.get("comp") in ch["comps"]):
        conf += 10
    end = match_end(md)
    if end and end - timedelta(minutes=10) <= t_pub <= end + timedelta(hours=12):
        conf += 10
    if min(sh, sa) >= 2:
        conf += 5
    return conf, None


def known_until(md):
    """Until when the match file's goal list is complete: for ever once it was read after the final whistle, else the time
    it was read (a clip out during a live match waits for a file read 10 min later, so its goal is already in it)."""
    if md.get("_fstatus") in DONE or not md.get("_fetched"):
        return datetime.max.replace(tzinfo=UTC)
    return ptime(md["_fetched"]) or datetime.min.replace(tzinfo=UTC)


def check_goal(v, ch, tx, md, g, gs, teams, players, t_pub, unnamed=False):
    h, a = md["home"]["id"], md["away"]["id"]
    own = ch.get("team")
    pid = g["player"]["id"]
    pst = 3 if unnamed else players.get(pid, 0)
    if pst < 2:
        return None, "scorer not named"
    if t_pub + timedelta(minutes=10) > known_until(md):
        return None, "the match file may not have that goal yet"
    named = teams.get(h, 0) or teams.get(a, 0)
    linked = own in (h, a) or named or (ch.get("comps") and md.get("comp") in ch["comps"])
    if not linked:
        return None, "not tied to the match"
    if own and own not in (h, a) and not named:
        return None, "another team's channel"
    if ch.get("comps") and md.get("comp") not in ch["comps"] and own not in (h, a):
        return None, "not this channel's competition"
    lb = g.get("lb")
    if not lb or t_pub < lb - timedelta(minutes=2):
        return None, "before the goal"
    end = match_end(md) or (lb + timedelta(hours=2))
    if t_pub > end + timedelta(hours=36):
        return None, "too late"
    if not (own in (h, a) or named) and t_pub > lb + timedelta(hours=6):
        return None, "competition channel, long after the goal"
    ok, why = dates_ok(tx, md)
    if not ok:
        return None, why
    if tx.pen and g["type"] != "penalty_goal":
        return None, "penalty words, not a penalty"
    if tx.fk and g["type"] == "penalty_goal":
        return None, "free kick words, a penalty"
    if tx.own and g["type"] != "own_goal":
        return None, "own-goal words"
    conf = 55 + (10 if unnamed else 15 if pst >= 3 else 5)
    if named:
        conf += 10
    if own in (h, a):
        conf += 10
    after = (g["score"]["home"], g["score"]["away"]) if g.get("score") else None
    if tx.scores:
        if not after or not any(either(s, after) for s in tx.scores):
            return None, "score is not this goal's"
        conf += 10
    if tx.minutes:
        if not any(abs(mm - int(g.get("minute") or 0)) <= 1 for mm, ad in tx.minutes):
            return None, "minute is not this goal's"
        conf += 10
    if tx.eq:
        if not after or after[0] != after[1]:
            return None, "equaliser words, the score is not level"
        conf += 5
    if tx.ordinal and after:
        side = g.get("team")                    # the side the goal counts for (FotMob credits an own goal to the side it helps)
        mine = after[0] if side == "home" else after[1] if side == "away" else None
        if tx.ordinal not in (mine, after[0] + after[1]):
            return None, f"goal number {tx.ordinal} words"
        conf += 5
    if t_pub <= lb + timedelta(minutes=45):
        conf += 5
    return conf, None


def only_goal(ctx, v, ch, tx, teams, spans, t_pub, note):
    """A clip that names no scorer («GOAL FOR PERU! Mexico vs Peru», «¡GOOL DE MÉXICO!») is the match's goal only when it
    says which side scored, that side has exactly one goal the clip can show (scored before it came out, the next goal
    of the match not yet possible), and the match is named. -> [(conf, match id, goal)] or []."""
    if not tx.goal_at:
        return []
    # the side right after the goal word: «goal [for] <team>», «هدف [لمنتخب] <team>»
    side_ids = set()
    for i in tx.goal_at:
        j, linked = i + 1, False
        while j < len(tx.al) and tx.al[j] & (LINK | ARTICLE):
            linked = linked or bool(tx.al[j] & LINK)
            j += 1
        if linked:     # the team's span may start on the link word itself («لمنتخب السعودية» is a name form too)
            side_ids |= {tid for s, e, k, tid in spans if k == "team" and i < s <= j}
    if not side_ids:
        return []
    out = []
    for mid, md in ctx.matches.items():
        h, a = md["home"]["id"], md["away"]["id"]
        own = ch.get("team")
        if not ((h in teams or own == h) and (a in teams or own == a)) or max(teams.get(h, 0), teams.get(a, 0)) < 2:
            continue
        scorer_side = [s for s, tid in (("home", h), ("away", a)) if tid in side_ids]
        if len(scorer_side) != 1:
            continue
        gs = [g for g in ctx.goals[mid] if g.get("lb")]
        mine = [g for g in gs if g.get("team") == scorer_side[0]]
        shown = [g for g in mine if g["lb"] <= t_pub + timedelta(minutes=2)]
        if len(shown) != 1 or shown[0]["type"] == "own_goal":    # an own goal's side is the one it helps: not trusted here
            note(v, mid, "goal (unnamed)", f"{len(shown)} goals of that side before it came out"); continue
        g = shown[0]
        if t_pub > g["lb"] + timedelta(hours=6):
            note(v, mid, "goal (unnamed)", "long after the goal"); continue
        conf, why = check_goal(v, ch, tx, md, g, ctx.goals[mid], teams, {}, t_pub, unnamed=True)
        note(v, mid, f"goal (unnamed) {g.get('minute')}' {g['player'].get('name')}", conf if conf else why)
        if conf and conf >= 70:
            out.append((conf, mid, g))
    return out if len({o[1] for o in out}) == 1 else []


def classify(tx):
    if tx.neg or tx.women:
        return None
    if tx.hl:
        return "hl"
    if tx.goal:
        return "goal"
    return None


def attach(videos, matches, names, chmap, trace=None, blocked=()):
    """-> {match id: {"highlights": [(video, conf)], "goals": {key: [(video, conf)]}}}. `trace` (a list) collects every
    decision for --explain and the tests."""
    ctx = Ctx(matches, names)
    out = {}

    def note(v, mid, what, res):
        if trace is not None:
            trace.append({"video": v["id"], "title": v["title"], "ch": v["ch"], "match": mid, "what": what, "result": res})

    for v in videos:
        if v["id"] in blocked:
            continue
        ch = chmap.get(v["ch"])
        t_pub = ptime(v.get("at"))
        if not ch or not t_pub:
            continue
        tx = Text(v["title"], v.get("desc"), ch.get("lang", "en"))
        kind = classify(tx)
        if not kind:
            if trace is not None and (tx.hl or tx.goal):
                note(v, None, "skip", tx.neg or tx.women)
            continue
        spans = []
        teams, players = ctx.mentions(tx.al, tx.flags if kind == "hl" else (), spans)
        if kind == "hl":
            cands = []
            for mid, md in ctx.matches.items():
                h, a = md["home"]["id"], md["away"]["id"]
                if not ((h in teams or ch.get("team") == h) and (a in teams or ch.get("team") == a)):
                    continue
                conf, why = check_highlights(v, ch, tx, md, ctx.goals[mid], teams, ctx.youth[mid], t_pub)
                note(v, mid, "highlights", conf if conf else why)
                if conf and conf >= 70:
                    cands.append((conf, -abs((t_pub - (match_end(md) or t_pub)).total_seconds()), mid))
            if cands:
                cands.sort(reverse=True)
                if len(cands) > 1 and cands[0][:1] == cands[1][:1] and cands[0][2] != cands[1][2]:
                    note(v, None, "highlights", "ambiguous: " + ",".join(str(c[2]) for c in cands[:3]))
                    continue
                out.setdefault(cands[0][2], {"highlights": [], "goals": {}})["highlights"].append((v, cands[0][0]))
            continue
        # a goal clip
        if tx.neg_goal or tx.old or tx.youth or tx.hl:
            if trace is not None and players:
                note(v, None, "goal", "no: " + str(tx.neg_goal or tx.old or tx.youth))
            continue
        hits = []
        for pid in players:
            for mid, g in ctx.scorers.get(pid, []):
                md = ctx.matches[mid]
                conf, why = check_goal(v, ch, tx, md, g, ctx.goals[mid], teams, players, t_pub)
                note(v, mid, f"goal {g.get('minute')}' {g['player'].get('name')}", conf if conf else why)
                if conf and conf >= 70:
                    hits.append((conf, mid, g))
        if not hits and not players:
            hits = only_goal(ctx, v, ch, tx, teams, spans, t_pub, note)
        if not hits:
            continue
        mids = {h[1] for h in hits}
        if len(mids) > 1:
            note(v, None, "goal", "two matches: " + ",".join(str(m) for m in mids)); continue
        mid = hits[0][1]
        pids = {h[2]["player"]["id"] for h in hits}
        if len(pids) > 1:
            note(v, mid, "goal", "two scorers named"); continue
        if len(hits) > 1:
            # one player's goals that were all scored before the clip came out (a later one fails the timing check), and neither
            # score nor minute in the title chose one: a brace/hat-trick clip shows them all, any other clip is left out
            if not tx.many:
                note(v, mid, "goal", "which of his goals?"); continue
        elif tx.plural and not tx.many:
            note(v, mid, "goal", "goals, one scored"); continue
        for conf, mid_, g in hits:
            key = f"{g.get('minute')}-{g['player']['id']}"
            out.setdefault(mid_, {"highlights": [], "goals": {}})["goals"].setdefault(key, []).append((v, conf))
    return out


# ------------------------------------------------------------------------------------------------ the step
def window(store, t, cache, workers=6):
    """The matches to follow: live, or finished and kicked off in the last 48 h (goal clips and highlights), and for their
    highlights only the finished ones of the last 7 days (a league uploads its extended highlights days later: the UAE Pro
    League's League Cup round came out 5 days after). Day files: the UAE dates of the last 4 days; older matches come from the
    cache. Match files: read again while live, when the score or status moved, and every 3 h until a day after kickoff;
    after that the cached file is final."""
    days = [(t + timedelta(hours=4) - timedelta(days=d)).strftime("%Y%m%d") for d in (0, 1, 2, 3)]
    ms = {}
    for d in days:
        try:
            x = store.get_json(f"day/{d}.json") or {}
        except Exception:
            x = {}
        for m in x.get("matches") or []:
            ms[m["id"]] = m
    far = t - timedelta(hours=FOLLOW_H)
    keep = [m for m in ms.values() if (m.get("status") in LIVE or m.get("status") in DONE)
            and ptime(m.get("kickoff_utc")) and ptime(m["kickoff_utc"]) >= far]
    seen = {m["id"] for m in keep}
    for c in cache.values():       # the day files are gone: what we read then
        d = c.get("doc") or {}
        if d.get("id") not in seen and d.get("status") in DONE and ptime(d.get("kickoff_utc")) and ptime(d["kickoff_utc"]) >= far:
            keep.append(dict(d)); seen.add(d["id"])
    need = []
    for m in keep:
        c = cache.get(str(m["id"]))
        sig = f"{m.get('status')}|{json.dumps(m.get('score'))}"
        k = ptime(m["kickoff_utc"])
        at = ptime((c or {}).get("at"))
        # a finished match is read again every 3 h for a day (FotMob adds its highlights link and corrects scorers), then kept
        fresh_ok = c and c.get("sig") == sig and m.get("status") not in LIVE and at and at > k + timedelta(hours=2) and \
            (at > t - timedelta(hours=3) or at > k + timedelta(hours=24))
        if not fresh_ok:
            need.append((m, sig))

    def one(ms_):
        m, sig = ms_
        try:
            return m, sig, store.get_json(f"match/{m['id']}.json")
        except Exception:
            return m, sig, None

    with CF.ThreadPoolExecutor(max_workers=workers) as ex:
        for m, sig, md in ex.map(one, need):
            if md:
                cache[str(m["id"])] = {"sig": sig, "at": iso(t), "doc": slim(md)}
    out = []
    for m in keep:
        c = cache.get(str(m["id"]))
        doc = dict(c["doc"]) if c else slim(m)
        # what the goal list is good for: read after the final whistle = complete; read live = complete up to that moment
        doc["_fetched"], doc["_fstatus"] = (c["at"], c["doc"].get("status")) if c else (iso(t), "summary")
        doc["status"], doc["score"] = m.get("status"), m.get("score") or doc.get("score")
        out.append(doc)
    for k_ in list(cache):
        c = cache[k_]
        if not ptime(c.get("doc", {}).get("kickoff_utc")) or ptime(c["doc"]["kickoff_utc"]) < far - timedelta(hours=24):
            del cache[k_]
    return out


def slim(md):
    keep = ("id", "comp", "kickoff_utc", "status", "score", "periods", "highlights")
    d = {k: md.get(k) for k in keep}
    for side in ("home", "away"):
        t = md.get(side) or {}
        d[side] = {"id": t.get("id"), "name": t.get("name"), "name_ar": t.get("name_ar")}
    d["events"] = [{k: e.get(k) for k in ("type", "minute", "added", "team", "player", "score", "clip")}
                   for e in md.get("events") or [] if e.get("type") in ("goal", "penalty_goal", "own_goal")]
    return d


def oembed(vid):
    """YouTube's oEmbed: 200 = public and embeddable, 401 = embedding off (link only), 404/400 = gone or private."""
    try:
        r = urllib.request.urlopen(urllib.request.Request("https://www.youtube.com/oembed?format=json&url=" +
                                                          urllib.parse.quote("https://www.youtube.com/watch?v=" + vid), headers={"User-Agent": RD.UA}), timeout=15)
        d = json.loads(r.read())
        return {"s": 200, "title": d.get("title"), "author": d.get("author_name")}
    except urllib.error.HTTPError as e:
        return {"s": e.code}
    except Exception:
        return {"s": 0}


def card(v, conf, chmap, found="tifo", kind=None):
    ch = chmap.get(v.get("ch")) or {}
    c = {"id": v["id"], "url": v["url"], "title": v.get("title"), "source": v.get("source", "youtube"),
         "channel": ch.get("name") or v.get("channel") or "", "published": v.get("at"), "image": v.get("image"),
         "embed": v.get("embed", v.get("source") == "youtube"), "vertical": bool(v.get("vertical")), "lang": ch.get("lang"),
         "conf": conf, "found_by": found}
    if kind:
        c["kind"] = kind            # highlights: "summary" (ملخص) or "goals" (the goals only, «أهداف المباراة»)
    return c


def load_names(store, cfg_national, cache_dir=None):
    import yaml
    rd = lambda p: json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    teams = (store.get_json("teams.json") or {}).get("teams") or {}
    fm = {}
    cache_dir = cache_dir or os.path.join(HERE, ".cache")
    fp = os.path.join(cache_dir, "fm_names_ar.json")
    try:
        if not os.path.exists(fp) or time.time() - os.path.getmtime(fp) > 86400:
            got = store.get_json("history/fm/names_ar.json")
            if got:
                os.makedirs(cache_dir, exist_ok=True)
                with open(fp, "w", encoding="utf-8", newline="\n") as f:
                    json.dump({"teams": got.get("teams") or {}, "players": got.get("players") or {}}, f, ensure_ascii=False)
        fm = rd(fp)
    except Exception:
        fm = rd(fp)
    al = yaml.safe_load(open(os.path.join(HERE, "aliases.yaml"), encoding="utf-8")) or {}
    return Names(teams, rd(os.path.join(ROOT, "names", "players_ar.json")), rd(os.path.join(ROOT, "names", "clubs_ar.json")), fm, al,
                 rd(os.path.join(HERE, "nations.json")), cfg_national)


def national_comps():
    import config
    return frozenset(c["id"] for c in config.competitions() if c.get("scope") == "national" or c["id"] in NATIONAL_EXTRA)


def needed(chs, matches):
    """The channels worth reading this run: a club's or federation's when its team played, a league's when its competition
    did, a broadcaster's or confederation's always."""
    teams = {t for m in matches for t in (m["home"]["id"], m["away"]["id"])}
    comps = {m.get("comp") for m in matches}
    out = []
    for ch in chs:
        if ch.get("team"):
            if ch["team"] in teams:
                out.append(ch)
        elif ch.get("comps"):
            if ch["comps"] & comps:
                out.append(ch)
        else:
            out.append(ch)
    return out


def step(store, cfg, t=None, prefetched=None, xbox=None, dry=False, explain=None, log=print):
    """One run: read what is needed, match, write the media files that changed. Returns a summary dict."""
    t0 = time.time()
    t = t or now()
    st = store.get_state(STATE) or {}
    cache = st.setdefault("matches", {})
    matches = window(store, t, cache)
    if not matches:                   # nothing live or finished in the last 48 h: nothing to read
        st["run"] = {"at": iso(t), "matches": 0, "secs": round(time.time() - t0, 1)}
        if not dry:
            store.put_state(STATE, st)
        return dict(st["run"], found={})
    chs = channels(cfg)
    xacc = (cfg.get("x") or {}).get("accounts") or []
    chmap = {c["key"]: c for c in chs + x_channels(xacc)}
    want = needed(chs, matches) if matches else []
    feeds, errs = fetch_feeds(want, prefetched) if want else ({}, {})
    vids = st.setdefault("videos", {})
    for key, items in feeds.items():
        ch = chmap.get(key)
        for it in items or []:
            v = video_from_item(it, ch)
            if v and v["id"] not in vids:
                vids[v["id"]] = v
    for v in x_videos(xbox, xacc):
        vids.setdefault(v["id"], v)
    cut = iso(t - timedelta(hours=KEEP_VIDEOS_H))
    for k in [k for k, v in vids.items() if (v.get("at") or "") < cut]:
        del vids[k]
    names = load_names(store, national_comps())
    blocked = set(str(x) for x in ((cfg.get("media") or {}).get("block") or []))
    trace = [] if explain is not None else None
    found = attach(list(vids.values()), matches, names, chmap, trace, blocked)
    # FotMob's own links: the match's highlights and a clip per goal event
    for md in matches:
        hl = md.get("highlights")
        for h in (hl if isinstance(hl, list) else [hl] if hl else []):
            vid = yt_id(h.get("url"))
            if not vid or vid in blocked:
                continue
            v = vids.get(vid) or {"id": vid, "source": "youtube", "url": "https://www.youtube.com/watch?v=" + vid, "title": None,
                                   "at": None, "ch": None, "image": h.get("image") or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"}
            found.setdefault(md["id"], {"highlights": [], "goals": {}})["highlights"].append((dict(v, fotmob=True), 100))
        for e in md.get("events") or []:
            vid = yt_id(e.get("clip")) if e.get("clip") else None
            if vid and e.get("player") and e["player"].get("id") and vid not in blocked:
                v = vids.get(vid) or {"id": vid, "source": "youtube", "url": "https://www.youtube.com/watch?v=" + vid, "title": None,
                                       "at": None, "ch": None, "image": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"}
                found.setdefault(md["id"], {"highlights": [], "goals": {}})["goals"].setdefault(
                    f"{e.get('minute')}-{e['player']['id']}", []).append((dict(v, fotmob=True), 100))
    # embed checks, once per attached YouTube video (a gone video is dropped, a no-embed one opens on YouTube)
    oe = st.setdefault("oembed", {})
    todo = {v["id"] for r in found.values() for v, _ in r["highlights"] + [x for l in r["goals"].values() for x in l]
            if v.get("source") == "youtube" and (v["id"] not in oe or (oe[v["id"]].get("s") in (0, None) and
                                                                       (ptime(oe[v["id"]].get("at")) or t) < t - timedelta(hours=1)))}
    if todo and not dry:
        with CF.ThreadPoolExecutor(max_workers=4) as ex:
            for vid, r in zip(todo, ex.map(oembed, todo)):
                oe[vid] = dict(r, at=iso(t))
    for k in [k for k, v in oe.items() if (v.get("at") or "") < iso(t - timedelta(days=7))]:
        del oe[k]
    gen = iso(t)
    outs = st.setdefault("out", {})
    written, recent = 0, []
    for md in matches:
        r = found.get(md["id"])
        if not r:
            continue

        def pack(lst, hl=False):
            seen, res = set(), []
            for v, conf in lst:
                o = oe.get(v["id"], {})
                if v["id"] in seen or o.get("s") in (400, 403, 404):
                    continue
                seen.add(v["id"])
                title = v.get("title") or o.get("title")
                c = card(dict(v, embed=(o.get("s") != 401) if v.get("source") == "youtube" else False, title=title, channel=o.get("author")),
                         conf, chmap, "fotmob" if v.get("fotmob") else "tifo", ("summary" if Text(title or "ملخص").summary else "goals") if hl else None)
                res.append(c)
            return res

        end = match_end(md)
        hl = pack(r["highlights"], hl=True)
        # the full summary first (out after the final whistle), one that plays on the page before one that opens YouTube
        # (beIN turns embedding off), Arabic channels before others, then the most confident, then the first out
        hl.sort(key=lambda c: (0 if (end and ptime(c.get("published")) and ptime(c["published"]) >= end - timedelta(minutes=5)) or c["found_by"] == "fotmob" else 1,
                               0 if c.get("embed") else 1, 0 if c.get("kind") == "summary" else 1, 0 if c.get("lang") == "ar" else 1,
                               -(c.get("conf") or 0), c.get("published") or ""))
        goals = {k: sorted(pack(l), key=lambda c: (0 if c.get("embed") else 1, 0 if c.get("lang") == "ar" else 1, -(c.get("conf") or 0), c.get("published") or ""))
                 for k, l in r["goals"].items()}
        goals = {k: l for k, l in goals.items() if l}
        if not hl and not goals and str(md["id"]) not in outs:
            continue
        doc = {"generated": gen, "match": md["id"], "highlights": hl, "goals": goals}
        h = hashlib.md5(json.dumps({k: v for k, v in doc.items() if k != "generated"}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if outs.get(str(md["id"])) != h:
            if not dry:
                store.put_json(f"media/{md['id']}.json", doc, cache="hot")
            outs[str(md["id"])] = h
            written += 1
        recent.append({"id": md["id"], "comp": md.get("comp"), "kickoff_utc": md.get("kickoff_utc"), "status": md.get("status"),
                       "score": md.get("score"), "home": md.get("home"), "away": md.get("away"), "highlights": len(hl),
                       "goals": sum(len(l) for l in goals.values())})
    for k in [k for k in outs if k not in {str(m["id"]) for m in matches} and k not in cache]:
        del outs[k]
    recent.sort(key=lambda r: r.get("kickoff_utc") or "", reverse=True)
    rdoc = {"generated": gen, "matches": recent}
    rh = hashlib.md5(json.dumps(recent, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if st.get("recent_hash") != rh and not dry:
        store.put_json("media/recent.json", rdoc, cache="hot")
        st["recent_hash"] = rh
    st["run"] = {"at": gen, "matches": len(matches), "channels": len(want), "videos": len(vids), "with_media": len(recent),
                 "written": written, "errors": errs, "secs": round(time.time() - t0, 1)}
    if not dry:
        store.put_state(STATE, st)
    if explain is not None:
        for tr in trace:
            if explain in (True, "all") or str(tr.get("match")) == str(explain):
                log(json.dumps(tr, ensure_ascii=False))
    return dict(st["run"], found={m: {"highlights": len(r["highlights"]), "goals": len(r["goals"])} for m, r in found.items()})


def main(argv=None):
    import yaml
    from store import Store, S3Backend, LocalBackend
    ap = argparse.ArgumentParser()
    ap.add_argument("--local"); ap.add_argument("--dry", action="store_true"); ap.add_argument("--explain", nargs="?", const="all")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    bucket = os.environ.get("BUCKET", "elyoxe-football-574771023173-ap-south-1")
    store = Store(LocalBackend(a.local)) if a.local else Store(S3Backend(bucket))
    cfg = yaml.safe_load(open(os.path.join(HERE, "sources.yaml"), encoding="utf-8"))
    xbox = store.get_state("news/x-inbox.json") or {}
    res = step(store, cfg, xbox=xbox, dry=a.dry, explain=a.explain)
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

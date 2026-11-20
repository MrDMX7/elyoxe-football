"""The Arab leagues before the other databases start (owner 2026-09-30: «العين يعطيك مبارياته فقط من سنة 2000»), from RSSSF
(the Rec.Sport.Soccer Statistics Foundation): every season's page of each Arab league — final table, the matches it
lists (Super Cup rounds, cups, sometimes the whole season), top scorers — back to the 1970s.

    python -m db.rsssf [--upload] [--country uae]

Pages: tables<letter>/<code>champ.html lists the champions and links the seasons (<code>95.html…). Plain text; parsed
with the three shapes they use: table rows «1.Al-Shabab  18 12 5 1 26- 9 29», result rows «13/4  A  v  B  1-2», scorer
rows «22 Name (Club)» / «Name (Club) 22».

The season's table is its final standing: a season played in stages (first phase, then a championship round) takes the
championship round, then the other clubs in their first-phase order; the table's first club must be the champion the
champions page names for that season, else the season gets no table (a wrong order is worse than none).

A club name is linked to our FotMob id within its country (national teams never): the same name, else every word of
RSSSF's name in exactly one of ours, else a close spelling with the same initials (Al-Sinaa is not Al-Minaa), with the
city in brackets tried first («Al-Ittihad (Kalba)»), plus the country's old names below. The abbreviations that make a
club (WAC, Raja, MO, CS, USM…) are part of its name: «MO Constantine» is not «CS Constantine». Two different names that
share a season's table are two clubs, so they can't both be ours: when they link to one FotMob club, the one that
carries its name keeps it, else neither; two rows of one season on one club are both left unlinked.
Out: v1/history/arab/<code>.json (every season: table, scorers, champion) and db/.cache/rsssf_clubs.json (per FotMob
club: positions per season and the dated matches) that db/history.py merges into the club histories.
Undated result lines («Ittihad K 0-1 Ain» under «Round 1») are not kept: db/history.py places every match by its date.
"""
import argparse, difflib, html as H, json, os, re, sys, time, unicodedata, urllib.request
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from store import Store, S3Backend  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
CACHE = os.path.join(HERE, ".cache", "rsssf")
# code, page folder letter, ISO for our teams, our league id, old names -> today's club («» = no club of ours)
COUNTRIES = {
    # renamed clubs map to today's name. Al-Ahli Dubai is the club FotMob carries on as Shabab Al-Ahli; Al-Shabab (Dubai,
    # later Al-Shabab Al-Arabi) was absorbed in the 2017 merger and stays itself: its seasons and titles are not Shabab
    # Al-Ahli's. «Ittihad» alone in a UAE table is Ittihad Kalba (Kalba Union).
    "uae": ("u", "AE", 538, {"al oroba": "sharjah", "al ahli dubai": "shabab al ahli", "al ahly dubai": "shabab al ahli", "al ahli": "shabab al ahli",
                             "al ahly": "shabab al ahli", "shabab al ahli dubai": "shabab al ahli", "al shabab al ahli": "shabab al ahli",
                             "al shabab al ahli dubai": "shabab al ahli", "shabab al ahli": "shabab al ahli",
                             "al ittihad kalba": "kalba", "ittihad kalba": "kalba", "kalba union": "kalba", "ittihad": "kalba", "al ittihad": "kalba",
                             "ittihad k": "kalba", "al shabab": "", "shabab": "", "al shabab dubai": "", "al shabab al arabi": "", "shabab al arabi": ""}),
    "sau": ("s", "SA", 536, {}), "qat": ("q", "QA", 535, {"maitheer": "muaither"}), "kuw": ("k", "KW", 529, {}),
    # FotMob's «Olympic El Qanah» is القناة (Canal, RSSSF «Qanah», lately «Olympi El-Qanal»); «Olympic» is Alexandria's Olympic
    # Club. «Petrojet-Suez» is بتروجيت; «Suez» is another club
    "egy": ("e", "EG", 519, {"qanah": "olympic el qanah", "el qanah": "olympic el qanah", "al qanah": "olympic el qanah", "al qanah suez": "olympic el qanah",
                             "al qanat suez": "olympic el qanah", "olympi el qanal": "olympic el qanah", "olympic": "", "olympic alexandria": "",
                             "petrojet": "petrojet suez", "suez": "", "al suez": "", "suez suez": ""}),
    # WAC is Wydad, «Kénitra AC» KAC, «CA Khénifra» Chabab Atlas; USK Alger was USM Alger's name in 1977-89; ES Sahel, Espérance ST,
    # AS Marsa, ES Métlaoui are how RSSSF writes FotMob's «Etoile du Sahel», «Espérance», «Avenir de La Marsa», «Etoile Métlaoui»
    "maro": ("m", "MA", 530, {"wac casablanca": "wydad casablanca", "wac": "wydad casablanca", "wydad ac": "wydad casablanca", "wydad casablanca": "wydad casablanca",
                              "wydad athletic casablanca": "wydad casablanca", "kenitra ac": "kac kenitra", "ca khenifra": "chabab atlas khenifra",
                              "cod meknes": "codm meknes", "ma tetouan": "mat tetouan"}),
    "alg": ("a", "DZ", 516, {"usk alger": "usm alger"}),
    "tun": ("t", "TN", 544, {"es sahel": "etoile sahel", "esperance st": "esperance", "esperance sportive tunis": "esperance", "est": "esperance",
                             "as marsa": "avenir marsa", "es metlaoui": "etoile metlaoui"}),
    "iraq": ("i", "IQ", 524, {}),
    "oman": ("o", "OM", None, {}), "jord": ("j", "JO", None, {}),
}


def get(path):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, path.replace("/", "_"))
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < 20 * 86400:
        return open(p, encoding="utf-8").read()
    try:
        raw = urllib.request.urlopen(urllib.request.Request("https://www.rsssf.org/" + path, headers={"User-Agent": "Mozilla/5.0 (elyoxe-tifo)"}), timeout=60).read()
    except Exception:
        return None
    t = raw.decode("latin-1")
    open(p, "w", encoding="utf-8").write(t); time.sleep(0.5)
    return t


def text(h):
    return H.unescape(re.sub(r"<[^>]+>", "", h or ""))


def fold(s, paren=False):
    """lower-case ASCII words; what's in brackets (the city: «Al-Ahli (Dubai)») is dropped, or kept with paren=True"""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b([dl])'", r"\1 ", s).replace("'", "")        # «d'Agadir» = «d Agadir», but «Al-Ra'ed» = «Al-Raed»
    s = re.sub(r"\((.*?)\)", r" \1 " if paren else " ", s)
    s = re.sub(r"\b(fc|sc|club|cultural|saudi|dubai fc)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


# spellings RSSSF and FotMob write differently
SPELL = {"ahly": "ahli", "sad": "sadd", "saad": "sadd", "masri": "masry", "ismaili": "ismaily", "mehalla": "mahalla", "mokaoulun": "mokawloon",
         "qadisiya": "qadsiah", "qadsia": "qadsiah", "qadissiyah": "qadsiah", "qadeseya": "qadsiah", "qadisiyah": "qadsiah", "ittifaq": "ettifaq",
         "taawon": "taawoun", "taawun": "taawoun", "shabab": "shabab", "nasr": "nassr", "hilal": "hilal", "zamalek": "zamalek", "wakra": "wakrah",
         "gharafa": "gharafa", "gharrafa": "gharafa", "rayyan": "rayyan", "kuwait": "kuwait", "salmiya": "salmiyah", "fehayheel": "fahaheel", "arabi": "arabi"}
RESERVE = re.compile(r"\s(2|b|ii|reserves?|youth|juniors?|u ?\d\d)$")      # «Al-Sadd 2», «Al-Minaa B»: a club's second team, never the club
# words one side writes and the other drops. The North African abbreviations (AS, CS, ES, JS, MC, CR, USM, MO, WAC, FAR…)
# are NOT here: they tell the clubs of one city apart («MO Constantine» / «CS Constantine», «WAC» / «Raja Casablanca»)
GENERIC = {"de", "du", "la", "le", "d", "l", "club", "sporting"}
# ... but a prefix FotMob leaves out («ES Zarzis» / «Zarzis», «Hassania US d'Agadir» / «Hassania Agadir») may be the only
# words RSSSF's name has beyond ours
ABBR = {"as", "cs", "es", "js", "mc", "cr", "usm", "us", "ca", "cb", "rc", "om", "usmh", "nrb", "ob", "mo", "ss", "ac"}


def canon(f):
    ws = [SPELL.get(w, w) for w in f.split()]
    core = [w for w in ws if w not in GENERIC]
    return " ".join(core or ws)


def nk(name):
    """a name's key inside one page: «Wasl» and «Al-Wasl» are the same row"""
    return " ".join(sorted(set(canon(fold(name)).split()) - {"al", "el"}))


def initials(a, b):
    """a close spelling, not another club: every word of the shorter name has a word in the other with the same first
    letter (Semouha / Smouha, Wahda / Wehda), and an abbreviation only matches itself (USM Sétif is not ES Sétif, Al-Sinaa
    is not Al-Minaa)"""
    A, B = [w for w in a.split() if w not in ("al", "el")], [w for w in b.split() if w not in ("al", "el")]
    short, long_ = (A, B) if len(A) <= len(B) else (B, A)
    return bool(short) and all(any((w == x) if min(len(w), len(x)) <= 3 else w[0] == x[0] for x in long_) for w in short)


ROW = re.compile(r"^\s*(\d{1,2})\.\s*(.+?)\s{2,}(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s*-\s*(\d{1,3})\s+(-?\d{1,3})")
ROW2 = re.compile(r"^\s*(\d{1,2})\.?\s+([A-Za-z][A-Za-z' .()/-]+?)\s{2,}(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(-?\d{1,3})")
# a club level on points with the row above it has no number («       Al Shabab    26 17 6 3 48-25 40»): same place
TIE = re.compile(r"^\s{2,}([A-Za-z][A-Za-z' .()/-]+?)\s{2,}(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s*-\s*(\d{1,3})\s+(-?\d{1,3})")
RES = re.compile(r"^\s*(?:(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?)?\s+([A-Z][A-Za-z' .()-]+?)\s+v\s+([A-Z][A-Za-z' .()-]+?)\s{2,}(\d{1,2})\s*[-/]\s*(\d{1,2})\b")
SC1 = re.compile(r"^\s*(\d{1,2})\s+([A-Z][^()\d]+?)\s+\(([^)]+)\)")
SC2 = re.compile(r"^\s*([A-Z][^()\d]+?)\s+\(([^)]+)\)\s+(\d{1,2})\s*$")
# a table's heading: the stage that decides the title, or one that doesn't
FINAL = re.compile(r"(second|2nd|third|3rd|final|last|championship|champions|title|super)\s*(phase|stage|round|league|group|pool|play-?offs?|table|standings|tournament)"
                   r"|championship|play-?offs? (for|round)|(stage|phase)\s*(2|ii|two|3|iii|three)\b", re.I)
NOTFINAL = re.compile(r"relegation|promotion|second division|lower|bottom|qualif|play-?out|\bgroup\s+[a-h1-8]\b|\bpool\s+[a-h1-8]\b|first (phase|stage|round)", re.I)
LABEL = re.compile(r"(final\s+)?(table|standings|classification)\s*:?", re.I)


def label_of(lines, i):
    """the nearest heading above line i, with a bare «Table:» joined to the line above it"""
    out = []
    for x in reversed(lines[max(0, i - 15):i]):
        s = x.strip()
        if not s or re.fullmatch(r"[\s\-=_.*~+]+", s):
            continue
        out.append(s)
        if not LABEL.fullmatch(s):
            break
    return " | ".join(reversed(out))


def cup_heading(lines, i):
    """«PRESIDENT CUP 1997» (or a «… Cup» heading underlined): the league part of the page ends here"""
    s = lines[i].strip()
    letters = [c for c in s if c.isalpha()]
    if "CUP" in s and letters and sum(c.isupper() for c in letters) >= 0.7 * len(letters):
        return True
    nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
    return bool(re.search(r"\bcup\b", s, re.I)) and bool(re.fullmatch(r"[=\-]{3,}", nxt)) and len(s) <= 60


def parse_season(t, label):
    """(tables, results, scorers): every table block of the league part of the page, with its heading, first to last"""
    lines = t.splitlines()
    blocks, cur, seen = [], None, set()
    for i, l in enumerate(lines):
        if cup_heading(lines, i):
            break
        m = ROW.match(l) or ROW2.match(l)
        if m:
            if cur is None:
                cur = {"label": label_of(lines, i), "rows": []}
            cur["rows"].append([int(m.group(1)), m.group(2).strip(), *[int(m.group(k)) for k in range(3, 10)]])
            continue
        m = TIE.match(l) if cur is not None else None
        if m:
            cur["rows"].append([cur["rows"][-1][0], m.group(1).strip(), *[int(m.group(k)) for k in range(2, 9)]])
            continue
        if cur is not None and not re.fullmatch(r"[\s\-=_.*~+]*", l):      # a blank line or text ends the table; «- - -» lines don't
            blocks.append(cur); cur = None
        elif cur is not None and not l.strip():
            blocks.append(cur); cur = None
    if cur is not None:
        blocks.append(cur)
    tables = []
    for b in blocks:
        key = tuple((r[0], nk(r[1]), r[8]) for r in b["rows"])
        if len(b["rows"]) >= 3 and key not in seen:        # the same table printed again after the rounds counts once
            seen.add(key); tables.append(b)
    results, scorers = [], []
    sc_at = next((i for i, l in enumerate(lines) if re.search(r"top ?scorers?|topscorer|goalscorers", l, re.I)), None)
    if sc_at is not None:
        for l in lines[sc_at + 1:sc_at + 25]:
            m = SC1.match(l)
            if m:
                scorers.append([m.group(2).strip(), m.group(3).strip(), int(m.group(1))]); continue
            m = SC2.match(l)
            if m:
                scorers.append([m.group(1).strip(), m.group(2).strip(), int(m.group(3))]); continue
            if scorers and not l.strip():
                break
    y1, y2 = season_years(label)
    section = "league"
    for l in lines:
        if re.search(r"cup|super|final|round|quarter|semi", l, re.I) and not RES.match(l):
            section = "cup" if re.search(r"cup|final|round|quarter|semi", l, re.I) else section
        m = RES.match(l)
        if m and y1:
            d, mo = m.group(1), m.group(2)
            if d and mo:
                y = y2 if int(mo) <= 7 else y1
                results.append([f"{y}-{int(mo):02d}-{int(d):02d}", m.group(4).strip(), m.group(5).strip(), int(m.group(6)), int(m.group(7)), section])
    return tables, results, scorers


# ---- the league's matches round by round (graph phase 7: the old seasons' match pages). RSSSF writes a round's date in its
# heading («Round 1 [Jan 25]», «Group 1 [Feb 22]», «[Mar 4]») and each match on a line of its own, its scorers in brackets after
# it or on the next lines, in one of two shapes: «[Isaac Nassib 3, 44, Rodrigo Mendes 81; Walid Obaid 9]» (home ; away) or
# «[Adib Obaid (12'; 64'), Dane Fayne (21') - Campo Romeo (52')]» (home - away). An «og» goal stays on the side it counted for.
MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
DATE_IN = re.compile(r"\[\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})\b[^\]]*\]", re.I)
MATCH = re.compile(r"^\s*([A-Za-z][A-Za-z'.\- ()]*?)\s+(\d{1,2})-(\d{1,2})\s+([A-Za-z][A-Za-z'.\- ()]*?)\s*(\[.*)?$")
# a heading at the line's start: «Cups 1999/2000», «Emir's Cup», «Super Cup 2002», «Promoted: ...», «Second Division» (never a
# table row's «Relegated» or an indented «no relegation this season»)
LEAGUE_END = re.compile(r"^(?:(?:[A-Za-z][A-Za-z'.\-]*\s+)*cups?\b.*|promoted\b.*|relegated\b.*|(?:second|first|third) division\b.*|division\s+\d.*)$", re.I)
NOT_SCORERS = re.compile(r"\b(aet|pen|awd|abd|annulled|walkover|w/o)\b", re.I)


def _minutes(s):
    out = []
    for m in re.finditer(r"(\d{1,3})\s*'?\s*(og|pen|p)?", s):
        out.append((int(m.group(1)), "own_goal" if (m.group(2) or "").lower() == "og" else "goal"))
    return out


def _side(s, side):
    """one side's scorers: «Name 3, 44, Other 81» or «Name (12'; 64'), Other (21')»"""
    goals = []
    if "(" in s:
        for m in re.finditer(r"([^(),]+?)\s*\(([^)]*)\)", s):
            name = re.sub(r"\s+", " ", m.group(1)).strip(" ,")
            goals += [[side, name, mi, kind] for mi, kind in _minutes(m.group(2))]
        return goals
    name = None
    for part in s.split(","):
        m = re.match(r"\s*([^\d]*?)\s*(\d{1,3}\s*(?:og|pen|p)?)\s*$", part, re.I)
        if not m:
            continue
        if m.group(1).strip():
            name = re.sub(r"\s+", " ", m.group(1)).strip()
        if name:
            goals += [[side, name, mi, kind] for mi, kind in _minutes(m.group(2))]
    return goals


def _scorers(text, hs, as_):
    """[[side, name, minute, goal|own_goal]] when they add up to the score, else [] (a scorer list RSSSF left short)"""
    body = text.strip().lstrip("[").rstrip("]")
    if not body or NOT_SCORERS.search(body) and not re.search(r"\d+\s*'", body) and ";" not in body:
        return []
    if "(" in body:
        depth, cut = 0, None
        for i, ch in enumerate(body):
            depth += ch == "("
            depth -= ch == ")"
            if depth == 0 and body[i:i + 3] == " - ":
                cut = i
                break
        home, away = (body[:cut], body[cut + 3:]) if cut is not None else ((body, "") if as_ == 0 else ("", body) if hs == 0 else (body, ""))
    else:
        home, away = (body.split(";", 1) + [""])[:2] if ";" in body else ((body, "") if as_ == 0 else ("", body) if hs == 0 else (body, ""))
    goals = _side(home, "h") + _side(away, "a")
    if sum(1 for g in goals if g[0] == "h") != hs or sum(1 for g in goals if g[0] == "a") != as_:
        return []
    return goals


def table_name(n, names):
    """the season table's row a match line's short name means: the same name, the same key («Shabab» / «Al-Shabab»), every
    word the start of a word of it, its city included («R Khaima» / «Ras Al-Khaima», «Ahly F» / «Al-Ahly (Fujeira)»), or a
    close spelling — and only when one row fits; else the name as written"""
    if n in names:
        return n
    words = [w for w in fold(n).split() if w not in ("al", "el")]
    city = lambda x: " ".join(sorted(set(canon(fold(x, paren=True)).split()) - {"al", "el"}))   # the key, its city kept
    tests = (lambda r: city(n) == city(r), lambda r: nk(n) == nk(r),
             lambda r: bool(words) and all(any(x.startswith(w) for x in fold(r, paren=True).split()) for w in words),
             lambda r: variant(n, r))
    for test in tests:
        hit = list(dict.fromkeys(r for r in names if test(r)))       # in the order given: the season's published table first
        if hit and len({city(r) for r in hit}) == 1:        # one row, or one name written two ways in two tables («Al Ain», «Al-Ain»)
            return hit[0]
    return n


def league_rounds(t, label):
    """[[date, home, away, hs, as, scorers]] of the league part of a season page (up to the first cup heading)"""
    lines = t.splitlines()
    y1, y2 = season_years(label)
    if not y1:
        return []
    out, day = [], None
    i = 0
    while i < len(lines):
        l = lines[i]
        if cup_heading(lines, i) or (len(l.strip()) <= 60 and l[:1].strip() and not MATCH.match(l) and LEAGUE_END.match(l.strip())):
            break
        m = MATCH.match(l)
        if not m:
            d = DATE_IN.search(l)
            if d:
                mo, dd = MONTHS[d.group(1).lower()[:3]], int(d.group(2))
                try:                                       # a date that does not exist («Feb 30») dates nothing
                    day = date(y2 if mo <= 7 else y1, mo, dd).isoformat()
                except ValueError:
                    day = None
            i += 1
            continue
        h, hs, as_, a, rest = m.group(1).strip(), int(m.group(2)), int(m.group(3)), m.group(4).strip(), m.group(5) or ""
        if not rest and i + 1 < len(lines) and lines[i + 1].strip().startswith("["):
            i += 1
            rest = lines[i]
        while rest and "]" not in rest and i + 1 < len(lines):      # a scorers list that wraps onto the next lines
            i += 1
            rest += " " + lines[i].strip()
        if day:
            out.append([day, h, a, hs, as_, _scorers(rest, hs, as_) if rest else []])
        i += 1
    return out


def season_years(label):
    m = re.search(r"(\d{4})\s*/\s*(\d{2,4})", label or "")
    if m:
        a = int(m.group(1)); b = m.group(2)
        return a, (int(b) if len(b) == 4 else a // 100 * 100 + int(b) + (100 if int(b) < a % 100 else 0))
    m = re.search(r"(\d{4})", label or "")
    return (int(m.group(1)), int(m.group(1))) if m else (None, None)


def champions(t):
    """{(first year, last year): [champion's name]} from the champions page's first list (the league; «not completed»,
    «abandoned» give none). Only the first list: the later ones (Qatar's official championship, Morocco after independence,
    regional leagues, amateur leagues) often spell the champion otherwise than the season pages do, and a season whose
    champion isn't known here keeps its first table, as before."""
    out, started = {}, False
    for l in (t or "").splitlines():
        m = re.match(r"^\s*(\d{4}(?:\s*[/-]\s*\d{2,4})?)\s+(\S.*?)\s*$", l)
        if m:
            y = season_years(m.group(1).replace("-", "/"))
            name = re.split(r"\s{2,}|\s*\[", m.group(2))[0].strip()
            ok = name and not re.match(r"(not |no |abandon|cancel|void|unknown|\?|-)", name, re.I)
            out.setdefault(y, []).extend([name] if ok else [])
            started = True
        elif started and l.strip():
            break
    return out


def variant(x, y):
    """one name spelled two ways («Al-Jazeera» / «Al-Jazira»)"""
    return difflib.SequenceMatcher(None, nk(x), nk(y)).ratio() >= 0.75 and initials(nk(x), nk(y))


def choose(tables, champs, same):
    """(rows, how): the table of a season's final standing, or ([], why) when no table has the champion first.
    champs: the names the champions page gives that season (none: the first table, as the page shows it)"""
    if not tables:
        return [], "no table"
    finals = [b for b in tables if FINAL.search(b["label"]) and not NOTFINAL.search(b["label"])]
    # the champion is first, or level with the first (a title play-off between clubs level on points)
    top = lambda b: next((r for r in b["rows"] if r[0] == b["rows"][0][0] and any(same(r[1], c) for c in champs)), None)
    if champs:
        pick = [b for b in finals if top(b)]
        how = "final stage"
        if not pick:
            pick = [b for b in tables if top(b)]
            pick, how = ([max(pick, key=lambda b: len(b["rows"]))], "table") if pick else ([], "")
        if not pick:
            return [], "the champion is first in no table"
        b = pick[-1]
    else:
        b, how = tables[0], "first table, no champion listed"
    rows = [list(r) for r in b["rows"]]
    if champs:                                           # the champion ahead of the clubs it was level with
        c = top(b)
        rows = [list(c)] + [r for r in rows if r[1] != c[1]]
    # a championship round of the top clubs: the others follow in the order of the whole league's first-stage table
    big = max(tables, key=lambda x: len(x["rows"]))
    keys = {nk(r[1]) for r in rows}
    if big is not b and len(big["rows"]) > len(rows) and keys <= {nk(r[1]) for r in big["rows"]}:
        rest = [list(r) for r in big["rows"] if nk(r[1]) not in keys]
        for i, r in enumerate(rest):
            r[0] = len(rows) + i + 1
        rows += rest; how += " + first stage below it"
    return rows, how


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); ap.add_argument("--country"); a = ap.parse_args(argv)
    store = Store(S3Backend(BUCKET))
    teams = (store.get_json("teams.json") or {}).get("teams") or {}
    from history.transfermarkt import national_ids
    national = national_ids(store)
    clubs_out = defaultdict(lambda: {"positions": [], "matches": []})
    for code, (letter, iso, lid, old) in COUNTRIES.items():
        if a.country and code != a.country:
            continue
        champ = get(f"tables{letter}/{code}champ.html")
        if not champ:
            print(code, "no champions page"); continue
        winners = champions(text(champ))
        pool = [(int(k), canon(fold(t.get("name")))) for k, t in teams.items()
                if int(k) not in national and ((t.get("country") or {}).get("iso2") == iso or (lid and lid in (t.get("comps") or [])))]

        def link_one(f, spelling=True):
            f = old.get(f, f)
            if f == "":
                return None, "no club"
            if RESERVE.search(f):
                return None, "second team"
            ws = set(f.split()) - {"al"}
            ex = [k for k, n in pool if n == f]
            if ex:
                return (ex[0], "exact") if len(ex) == 1 else (None, "ambiguous")
            sub = [k for k, n in pool if ws and ws <= set(n.split())]
            if sub:
                return (sub[0], "words") if len(sub) == 1 else (None, "ambiguous")
            rev = [k for k, n in pool if (lambda nw: bool(nw) and nw <= ws and (ws - nw) <= ABBR and not nw & ABBR)(set(n.split()) - {"al"})]
            if rev:
                return (rev[0], "words") if len(rev) == 1 else (None, "ambiguous")
            if not spelling:
                return None, None
            sc = sorted(((difflib.SequenceMatcher(None, f, n).ratio(), k, n) for k, n in pool), reverse=True)
            if sc and sc[0][0] >= 0.84 and (len(sc) == 1 or sc[0][0] - sc[1][0] >= 0.08) and initials(f, sc[0][2]):
                return sc[0][1], "spelling"
            return None, None

        L = {}

        def link(name):
            """(FotMob id or None, how): the name plus its bracketed city first («Al-Ittihad (Kalba)»), then the name alone. The
            city only ever adds words: «Sporting (Alexandria)» is not «Al Ittihad Alexandria»"""
            if name not in L:
                base = canon(fold(name))
                city = canon(fold(" ".join(re.findall(r"\((.*?)\)", name))))
                got = (None, None)
                for f, spelling in ([((base + " " + city).strip(), False)] if city else []) + [(base, True)]:
                    k, how = link_one(f, spelling)
                    if how in ("exact", "no club", "second team"):
                        got = (k, how); break
                    if k and got[0] is None:
                        got = (k, how)
                L[name] = got
            return L[name][0]

        def same(x, y):
            """one club: the same name, or linked to the same club of ours, or (neither ours) one name spelled two ways —
            never a name inside a longer one («Ahli Fujeira» is not «Al-Ahli»)"""
            if nk(x) == nk(y):
                return True
            a, b = link(x), link(y)
            return a == b if (a is not None or b is not None) else variant(x, y)
        parsed = []
        for pg in sorted(set(re.findall(r'href="(%s\d{2,4}\.html)"' % code, champ))):
            h = get(f"tables{letter}/{pg}")
            if not h:
                continue
            t = text(h)
            label = (re.search(r"\n\s*([^\n]*\d{4}[^\n]*)\n", t) or [None, pg])[1].strip()
            tables, results, scorers = parse_season(t, label)
            y1, y2 = season_years(label)
            season = f"{y1}/{y2}" if y1 and y2 and y1 != y2 else str(y1 or pg)
            w = winners.get((y1, y2)) if (y1, y2) in winners else winners.get((y1, y1 + 1) if y1 and y1 == y2 else (y1, y2)) or []
            for b in tables:
                for r in b["rows"]:
                    link(r[1])
            parsed.append({"pg": pg, "season": season, "tables": tables, "results": results, "scorers": scorers, "champion": w,
                           "rounds": league_rounds(t, label)})
        # two names in one table are two clubs, and so are two names in one season's tables unless they are one name spelled
        # two ways («Al-Jazeera» in the first stage, «Al-Jazira» in the second): they can't both be one of ours
        cooc = defaultdict(set)
        for s in parsed:
            for b in s["tables"]:
                ns = {r[1] for r in b["rows"]}
                for n in ns:
                    cooc[n] |= ns - {n}
            ns = {r[1] for b in s["tables"] for r in b["rows"]}
            for n in ns:
                cooc[n] |= {o for o in ns - {n} if not variant(n, o)}
        by_fid = defaultdict(set)
        for n, (k, how) in L.items():
            if k:
                by_fid[k].add(n)
        dropped = []
        for k, ns in by_fid.items():
            groups = defaultdict(set)                   # one club's spellings: «Olympic» and «Olympic (Alexandria)»
            for n in ns:
                groups[nk(n)].add(n)
            clash = {g for g, mem in groups.items() if any(cooc[n] & (ns - mem) for n in mem)}
            if not clash:
                continue
            exact = {g for g in clash if any(L[n][1] == "exact" for n in groups[g])}
            keep = exact if len(exact) == 1 else set()
            for g in clash - keep:
                for n in groups[g]:
                    L[n] = (None, "shares a season with another name of this club"); dropped.append(f"{n} (vs {sorted(cooc[n] & ns)[:2]})")
        seasons, linked, unl, notab = [], set(), set(), []
        for s in parsed:
            rows, how = choose(s["tables"], s["champion"], same)
            fids = [link(r[1]) for r in rows]
            twice = {f for f in fids if f and fids.count(f) > 1}           # two rows of one season on one club: neither
            fids = [None if f in twice else f for f in fids]
            for r, fid in zip(rows, fids):
                (linked if fid else unl).add(r[1])
                if fid:
                    clubs_out[fid]["positions"].append([s["season"], r[0], len(rows), r[8], r[2], r[3], r[4], r[5], r[6], r[7], "rsssf"])
            if s["tables"] and not rows:
                notab.append(s["season"])
            for d, hn, an, hg, ag, sec in s["results"]:
                hi, ai = link(hn), link(an)
                if hi and hi == ai:
                    hi = ai = None
                for me, opp, oname, home, gf, ga in ((hi, ai, an, 1, hg, ag), (ai, hi, hn, 0, ag, hg)):
                    if me:
                        clubs_out[me]["matches"].append([d, opp if opp else "r:" + oname, home, gf, ga, f"rsssf:{code}:{sec}"])
            ch = next((c for c in s["champion"] if rows and same(rows[0][1], c)), (s["champion"] or [None])[0])
            # the season's table names, the published table's first: a match line's short names mean these
            tn = list(dict.fromkeys([r[1] for r in rows] + sorted({r[1] for b in s["tables"] for r in b["rows"]})))
            seasons.append({"season": s["season"], "page": s["pg"], "champion": ch, "stage": how,
                            "table": [[r[0], r[1], fid] + r[2:] for r, fid in zip(rows, fids)],
                            "scorers": [[x[0], x[1], link(x[1]), x[2]] for x in s["scorers"]], "matches": len(s["results"]),
                            # the league round by round: [date, home, its FotMob id, away, its id, hs, as, [[side, scorer, minute, kind]]]
                            "league_matches": [[d, h, *(lambda hi, ai: (hi, a, ai) if hi is None or hi != ai else (None, a, None))(link(h), link(a)), hs, as_, sc]
                                               for d, h, a, hs, as_, sc in ([d0, table_name(h0, tn), table_name(a0, tn), x, y, z]
                                                                            for d0, h0, a0, x, y, z in s["rounds"])]})
        seasons.sort(key=lambda s: s["season"])
        print(code, len(parsed), "season pages;", sum(1 for s in seasons if s["table"]), "with a table;", sum(s["matches"] for s in seasons), "matches;",
              sum(1 for s in seasons if s["scorers"]), "with scorers; clubs linked", len(linked), "not", len(unl), sorted(unl)[:8])
        if notab:
            print("  ", code, "no table has the champion first (left without one):", notab)
        if dropped:
            print("  ", code, "names left unlinked, they share a season with another name of the same club:", sorted(set(dropped)))
        if a.upload:
            store.put_json(f"history/arab/{code}.json", {"country": code, "league": lid, "seasons": seasons, "source": "RSSSF (rsssf.org)"}, cache="warm")
    json.dump(clubs_out, open(os.path.join(HERE, ".cache", "rsssf_clubs.json"), "w", encoding="utf-8", newline="\n"), ensure_ascii=False)
    print(len(clubs_out), "of our clubs get RSSSF seasons/matches")
    return 0


if __name__ == "__main__":
    sys.exit(main())

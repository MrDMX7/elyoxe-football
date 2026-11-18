"""Article checks (spec, «Checks»): every number in the article is in the fact sheet; Latin letters fail (xG and VAR are
words of the trade); match reports also go through site/ai/checks.py (goal order, red cards, halves). Dates, 12-hour times,
numbers written as words and thousands separators are read the way the sheet stores them, so a right text is not flagged
(the blind tests flagged correct articles in every round without this)."""
import os, re, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "site", "ai"))
import checks as AI   # noqa: E402

MONTHS = {"يناير": 1, "فبراير": 2, "مارس": 3, "أبريل": 4, "ابريل": 4, "مايو": 5, "يونيو": 6, "يوليو": 7, "أغسطس": 8, "اغسطس": 8,
          "سبتمبر": 9, "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12}
WORDS = {"ثنائية": 2, "ثلاثية": 3, "رباعية": 4, "خماسية": 5, "سداسية": 6, "سباعية": 7, "ثمانية": 8, "هدفين": 2, "هدفان": 2}
LATIN_OK = {"xG", "VAR"}


def article_text(a):
    lines = [a.get("headline") or "", a.get("standfirst") or ""]
    for s in a.get("sections") or []:
        lines.append(s.get("subhead") or "")
        lines += s.get("paragraphs") or []
    return "\n".join(lines + list(a.get("facts_box") or []))


def _sheet_dates(sheet):
    days, times = set(), set()
    def walk(o):
        if isinstance(o, dict):
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
        elif isinstance(o, str) and re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", o):
            d = datetime.fromisoformat(o)
            days.add((d.month, d.day)); times.add((d.hour, d.minute))
    walk(sheet)
    return days, times


def check_article(article, sheet, md=None, words=None):
    """words: the type's (min, max); a text under half the min or over 130% of the max fails (spec: a report is 300-400; a thin
    match makes a shorter report rather than a padded one, the 2026-11-18 dry run)."""
    text = article_text(article)
    fails = []
    if words:
        n = len(text.split())
        if n < words[0] * 0.5 or n > words[1] * 1.3:
            fails.append(f"{n} words, the type is {words[0]}-{words[1]}")
    if re.search(r"[٠-٩]", text):                              # the owner's rule: Western digits, always
        fails.append("Eastern Arabic digits («٠-٩») in the text")
    # «الدقيقة N» / «الدقيقتين N و M»: N must be the minute of an event in the sheet (final review, finding 9)
    mins = {str(e.get("دقيقة")) for e in sheet.get("الأحداث بالترتيب") or []}
    mins |= {m.split("+")[0] for m in mins}
    for m in re.finditer(r"الدقيق(?:ة|تين)\s+(\d+(?:\+\d+)?)(?:\s+و\s*(\d+(?:\+\d+)?))?", text):
        for n in filter(None, m.groups()):
            if n not in mins:
                fails.append(f"minute {n} is not an event minute in the sheet")
    days, times = _sheet_dates(sheet)
    # dates «8 نوفمبر»: the day and month must be a date in the sheet; then they are not numbers to check
    for m in re.finditer(r"(\d{1,2})\s+(" + "|".join(MONTHS) + r")", text):
        if (MONTHS[m.group(2)], int(m.group(1))) not in days:
            fails.append(f"date «{m.group(0)}» is not in the sheet")
    text = re.sub(r"\d{1,2}\s+(?:" + "|".join(MONTHS) + r")(?:\s+\d{4})?", " ", text)
    # times «10:00 مساءً» / «22:00»
    for m in re.finditer(r"(\d{1,2}):(\d{2})\s*(مساءً|مساء|صباحاً|صباحا|ص|م)?", text):
        h, mi, half = int(m.group(1)), int(m.group(2)), m.group(3) or ""
        if half.startswith("م") and h < 12: h += 12
        if half.startswith("ص") and h == 12: h = 0
        if (h, mi) not in times:
            fails.append(f"time «{m.group(0)}» is not in the sheet")
    text = re.sub(r"\d{1,2}:\d{2}\s*(?:مساءً|مساء|صباحاً|صباحا|ص|م)?", " ", text)
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)            # 69,788 -> 69788
    have = AI.input_numbers(sheet)
    for w, n in WORDS.items():                                  # «بثلاثية نظيفة»: the number the word stands for
        if w in text and float(n) not in have:
            fails.append(f"«{w}» ({n}) is not in the sheet")
    for m in re.finditer(r"(?<![\d.])(\d+(?:\.\d+)?)(?![\d])", text):
        v = round(float(m.group(1)), 1)
        if v not in have and float(round(v)) not in have:
            fails.append(f"number {m.group(1)} is not in the sheet")
    latin = [w for w in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'\-]+", article_text(article)) if w not in LATIN_OK]
    if latin:
        fails.append("Latin words left: " + ", ".join(sorted(set(latin))[:8]))
    r = AI.check_history(article_text(article), sheet)          # «أول فوز», «سلسلة N», runs and counts need their evidence
    if r:
        fails.append(r)
    if md is not None:
        full = article_text(article)
        r = AI.check_events(full, md)
        if r: fails.append(r)
        r, _ = AI.check_halves(full, md)
        if r: fails.append(r)
    return fails


ATTRIB = re.compile(r"(?:بحسب|وفقاً ل|وفقا ل|نقلاً عن|نقلا عن|حسب ما|ذكرت|أفادت)")


def check_news(article, sheet, words):
    """A news article: the Phase 1 checks without a match, and the source named once (spec, «News rules»). Two are allowed:
    a news piece may credit a second outlet for a second fact."""
    fails = check_article(article, sheet, None, words=words)
    n = len(ATTRIB.findall(article_text(article)))
    if n > 2:
        fails.append(f"attribution {n} times; name the source once")
    return fails

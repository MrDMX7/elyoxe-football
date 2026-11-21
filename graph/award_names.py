"""One Arabic name per award (spec §7.6). The Arabic of an award table is often its section's term alone («Player of the Year»
-> «لاعب العام»), so sixty awards of sixty bodies shared one name, and one <title> on the site. An Arabic name shared by
several awards is told apart, in this order, by:
  1. the league, federation, club or country of its page («Canadian Premier League Awards» -> «في الدوري الكندي الممتاز»),
     from awards.yaml `places` (English words of the page -> Arabic, written by hand, the longest match wins);
  2. what the English name says of who it is for (women, youth, under-21, foreign, coach, fans' vote...);
and what is still shared after both keeps no Arabic name (the site shows the English one) rather than a made-up one."""
import os, re
from collections import defaultdict
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))

QUAL = [(re.compile(r"\bunder[- ]?(\d+)", re.I), lambda m: f"تحت {m.group(1)} سنة", re.compile("تحت")),
        (re.compile(r"women|female|girls|vrouwen", re.I), "للسيدات", re.compile("سيدات|نساء|نسائ")),
        (re.compile(r"\b(men|male)\b|\bmen's", re.I), "للرجال", re.compile("رجال")),
        (re.compile(r"youth|young|junior|talent|breakthrough|revela", re.I), "للشباب", re.compile("شاب|شباب|ناشئ")),
        (re.compile(r"foreign", re.I), "للأجانب", re.compile("أجنب")),
        (re.compile(r"goalkeeper", re.I), "لحراسة المرمى", re.compile("حارس|حراسة")),
        (re.compile(r"manager|coach", re.I), "للمدربين", re.compile("مدرب")),
        (re.compile(r"referee", re.I), "للحكام", re.compile("حكم|حكام")),
        (re.compile(r"fans'?|supporters", re.I), "باختيار الجماهير", re.compile("جماهير|مشجع")),
        (re.compile(r"players'? player", re.I), "باختيار اللاعبين", re.compile("اختيار اللاعبين")),
        (re.compile(r"\bmedia\b", re.I), "باختيار الإعلام", re.compile("إعلام")),
        (re.compile(r"amateur|ameteur", re.I), "للهواة", re.compile("هواة")),
        (re.compile(r"schools?|colleges?|universit", re.I), "للمدارس والجامعات", re.compile("مدارس|جامع")),
        (re.compile(r"disabilit", re.I), "لذوي الإعاقة", re.compile("إعاقة"))]


def places():
    try:
        conf = yaml.safe_load(open(os.path.join(HERE, "awards.yaml"), encoding="utf-8")) or {}
    except OSError:
        return {}
    return {str(k): str(v) for k, v in (conf.get("places") or {}).items()}


def _place(name, table):
    base = (name or "").split(" — ")[0].lower()
    for k in sorted(table, key=len, reverse=True):
        if k.lower() in base:
            return table[k]
    return None


def _shared(names):
    by = defaultdict(list)
    for cid, n in names.items():
        if n:
            by[n].append(cid)
    return [cids for cids in by.values() if len(cids) > 1]


def distinct(rows, table=None):
    """rows: (cid, English name, Arabic name or None). Returns {cid: Arabic name or None}, an Arabic name held twice only where no rule parts them."""
    table = places() if table is None else table
    en = {cid: name for cid, name, _ in rows}
    out = {cid: ar for cid, _, ar in rows}
    for cids in _shared(out):
        for cid in cids:
            p = _place(en[cid], table)
            if p and p.split(" ", 1)[-1] not in out[cid]:
                out[cid] = f"{out[cid]} {p}"
    for cids in _shared(out):
        for cid in cids:
            n, q = out[cid], []
            for rx, ar, has in QUAL:
                m = rx.search(en[cid] or "")
                if not m or has.search(n):
                    continue
                t = ar(m) if callable(ar) else ar
                if t not in q:
                    q.append(t)
            if q:
                out[cid] = f"{n} {' '.join(q)}"
    return out                                     # what no rule parts keeps its Arabic name shared: an English page is worse

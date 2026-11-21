"""The official man of the match (owner 2026-11-21: «MOTM على مر السنين», FotMob rates no match before its own ratings):
Wikipedia's tournament pages print the organiser's award under each match box («Man of the Match:» at the World Cup,
«Player of the Match:» at the Euros and the Asian Cup). The pages are listed in graph/motm_wiki.yaml and fetched with the
awards pages (graph/awards_fetch.py); graph/load/official_motm.py ties each award to its match and player."""
import os
import re
import urllib.parse
from datetime import datetime
from lxml import html as LH
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL = re.compile(r"^\s*(?:man|player) of the match\s*:?\s*$", re.I)
SCORE = re.compile(r"(\d+)\s*[–\-−]\s*(\d+)")


def pages():
    """Every page title graph/motm_wiki.yaml spells out, sorted."""
    conf = yaml.safe_load(open(os.path.join(HERE, "motm_wiki.yaml"), encoding="utf-8")) or {}
    out = set()
    for t in conf.get("tournaments") or []:
        for y in t.get("years") or []:
            out.update(t["groups"].format(y=y, g=g) for g in t.get("letters") or "" if t.get("groups"))
            out.update(s.format(y=y) for s in t.get("stages") or [])
    return sorted(out)


def _title(a):
    t = a.get("title")
    if t:
        return t
    href = a.get("href") or ""
    return urllib.parse.unquote(href[2:]).replace("_", " ") if href.startswith("./") else None


def _team(box, cls):
    th = box.xpath(f".//*[contains(concat(' ', normalize-space(@class), ' '), ' {cls} ')]")
    if not th:
        return None
    a = th[0].xpath(".//a[not(ancestor::*[contains(@class,'flagicon')])]")
    return (a[0].text_content().strip() if a else th[0].text_content().strip()) or None


def _date(text):
    """«9 January 2015» or «June 3, 2002» (a box without the dtstart tag) -> ISO, else None"""
    t = " ".join((text or "").replace(",", " ").split()[:3])
    for f in ("%d %B %Y", "%B %d %Y"):
        try:
            return datetime.strptime(t, f).date().isoformat()
        except ValueError:
            pass
    return None


def _box(box):
    d = box.xpath(".//*[contains(@class,'dtstart')]")
    if not d:
        fd = box.xpath(".//*[contains(concat(' ', normalize-space(@class), ' '), ' fdate ')]")
        day = _date(fd[0].text_content()) if fd else None
        d = [LH.fromstring(f"<span>{day}</span>")] if day else []
    sc = box.xpath(".//*[contains(concat(' ', normalize-space(@class), ' '), ' fscore ')]")
    m = SCORE.search(sc[0].text_content()) if sc else None
    return {"date": d[0].text_content().strip()[:10] if d else None, "home": _team(box, "fhome"), "away": _team(box, "faway"),
            "score": (int(m.group(1)), int(m.group(2))) if m else None}


def official_motm(html):
    """[{date, home, away, score, person (the linked article's title), name}] in page order: the award printed after a match
    box and before the next one belongs to it; a box with none gives no row."""
    doc = LH.fromstring(html.decode("utf-8", "replace") if isinstance(html, bytes) else html)   # bytes alone read as Latin-1: «0â€“2»
    out, cur = [], None
    for el in doc.iter():
        if not isinstance(el.tag, str):
            continue
        cls = " " + (el.get("class") or "") + " "
        if " footballbox " in cls:
            cur = _box(el)
        elif el.tag == "b" and cur and LABEL.match(el.text_content() or ""):
            p = el.getparent()
            links = [a for a in p.iter("a") if a is not el and not a.xpath("ancestor::sup")] if p is not None else []
            if links:
                side = re.match(r"\s*\(([^)]+)\)", links[0].tail or "")             # «Enner Valencia (Ecuador)»
                out.append({**cur, "person": _title(links[0]), "name": links[0].text_content().strip(), "team": side.group(1).strip() if side else None})
            cur = None
    return out

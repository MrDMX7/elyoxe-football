"""The organiser's man of the match (graph/motm_wiki.py) on our matches: before the FotMob rating pick (graph/load/motm.py,
INSERT OR IGNORE), so the official award wins where both exist and fills the years FotMob never rated (World Cups since 2002,
Euros, Asian Cups, Africa Cups, Copa América, Club World Cups). The match is ours on the same date ±1 day with both teams'
names alike and the same score; the man is the one of that name in its lineup, else his Wikidata item's player."""
import os
import unicodedata
from difflib import SequenceMatcher
from graph import awards_fetch as AF
from graph.link import _days
from graph.load.awards import alike
from graph.motm_wiki import official_motm, pages


SAME = [{"united states", "usa"}, {"czech republic", "czechia"}, {"turkey", "turkiye"}, {"united arab emirates", "uae"},
        {"ivory coast", "cote d'ivoire"}, {"south korea", "korea republic"}, {"north korea", "korea dpr"}, {"iran", "ir iran"},
        {"china", "china pr"}, {"republic of ireland", "ireland"}, {"dr congo", "congo dr"}, {"cape verde", "cabo verde"},
        {"bosnia and herzegovina", "bosnia herzegovina"}, {"trinidad and tobago", "trinidad & tobago"}]


def same_team(a, b):
    """Wikipedia's name and ours for one team: alike, or two spellings of one country (Turkey/Türkiye, United States/USA)"""
    fa, fb = _fold(a), _fold(b)
    return bool(fa and fb) and (fa == fb or any(fa in g and fb in g for g in SAME) or alike(a, b))


def load(G, reg, S, titles=None):
    d = os.path.join(S.root, "graph", ".cache", "awards")
    if not os.path.exists(os.path.join(d, "pages.json")) and S.s3:
        AF.restore(S, d)
    items = AF._jload(os.path.join(d, "items.json"), {})
    name = dict(G.c.execute("SELECT tid, name FROM team"))
    by_day = {}
    apps = dict(G.c.execute("SELECT mid, count(*) FROM appearance GROUP BY mid"))
    for mid, day, h, a, hs, as_ in G.c.execute("SELECT mid, substr(date,1,10), home, away, hs, as_ FROM match WHERE date IS NOT NULL"):
        by_day.setdefault(day, []).append((mid, h, a, hs, as_))
    for v in by_day.values():                  # one game held twice (Transfermarkt's and the World Cup set's): the lineup's first
        v.sort(key=lambda m: -apps.get(m[0], 0))
    n = {"pages": 0, "awards": 0, "linked": 0, "no_match": 0, "no_player": 0}
    rows = []
    for t in titles if titles is not None else sorted(pages()):
        h = AF.read_page(d, t)
        if not h:
            continue
        n["pages"] += 1
        for r in official_motm(h):
            n["awards"] += 1
            hit = _match(by_day, name, r)
            if not hit:
                n["no_match"] += 1
                continue
            mid, home, away = hit
            pid, tid = _player(G, reg, items, mid, r)
            if pid is None:
                n["no_player"] += 1
                continue
            if tid is None and r.get("team"):
                tid = home if same_team(r["team"], name.get(home) or "") else away if same_team(r["team"], name.get(away) or "") else None
            rows.append((mid, pid, tid))
            n["linked"] += 1
    G.c.executemany("INSERT OR REPLACE INTO match_award(mid, kind, pid, tid, value, src) VALUES(?, 'motm', ?, ?, NULL, 'official')", rows)
    return n


def _match(by_day, name, r):
    """(mid, home, away) of our match for the page's box: same day ±1, both names alike either way round, the same score"""
    if not (r.get("date") and r.get("home") and r.get("away")):
        return None
    for day in _days(r["date"]):
        for mid, h, a, hs, as_ in by_day.get(day, ()):
            nh, na = name.get(h) or "", name.get(a) or ""
            if same_team(r["home"], nh) and same_team(r["away"], na):
                sc = (hs, as_)
            elif same_team(r["home"], na) and same_team(r["away"], nh):
                sc = (as_, hs)
            else:
                continue
            if r.get("score") and None not in sc and tuple(sc) != tuple(r["score"]):
                continue
            return mid, h, a
    return None


def _player(G, reg, items, mid, r):
    """(pid, tid): the man of that name in the match's lineup, else his Wikidata item's player (minted if new)"""
    for pid, tid, nm in G.c.execute("SELECT a.pid, a.tid, p.name FROM appearance a JOIN player p ON p.pid=a.pid WHERE a.mid=?", (mid,)):
        if nm and (same_man(nm, r["name"]) or (r.get("person") and same_man(nm, r["person"].split(" (")[0]))):
            return pid, tid
    f = items.get(r.get("person") or "") or items.get((r.get("person") or "").replace(" ", "_")) or {}
    if not (f.get("qid") and f.get("human")):
        return None, None
    pid = reg.get("player", "wikidata", f["qid"])
    if pid is None and f.get("tm_player"):
        pid = reg.get("player", "tm", str(f["tm_player"]))
        if pid is not None:
            reg.link("player", "wikidata", f["qid"], pid)
    if pid is None:
        pid = reg.mint("player", "wikidata", f["qid"])
    G.put("player", {"pid": pid, "name": f.get("en") or r["name"], "name_ar": f.get("ar"), "born": f.get("born")}, "wikidata")
    G.xref("player", pid, "wikidata", f["qid"], "wiki-link")
    return pid, None


def _fold(s):
    return " ".join(unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().replace("-", " ").split())


def same_man(a, b):
    """Two spellings of one player's name, stricter than the clubs' alike (Enner and Antonio Valencia shared Ecuador's
    lineup): the same after folding, 90% alike letter by letter, or every word of the shorter name (2+ words) in the longer"""
    a, b = _fold(a), _fold(b)
    if not a or not b:
        return False
    if a == b or SequenceMatcher(None, a, b).ratio() >= 0.9:
        return True
    s, l = sorted((a.split(), b.split()), key=len)
    return len(s) >= 2 and set(s) <= set(l)

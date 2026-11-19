"""Every Arabic form of each player's name, for the goal-clip matcher (docs/2026-11-19-player-aliases.md): broadcasters and
clubs write «سيرجيو بيريرا» for our «سيرجينيو» and «ماركوس مايا» for «ماركوس أندريه», and those goals got no clip.

    state/graph/player_aliases_ar.json.gz   {"generated", "players": {FotMob player id: [Arabic form, ...]}}

Built with the nightly graph from: the graph's Arabic name; names/players_ar.json; Arabic Wikipedia's redirect spellings
(names/players_ar_aka.json); Wikidata's Arabic label and aliases (db/.cache/wd_ar.json, graph/fetch.py); the Arabic keys of
news/aliases.yaml `people:`; 365Scores' Arabic name when the 365 player's club is his FotMob club and the Latin names agree;
and the forms the matcher learned (state/news/media-learned-aliases.json). A one-word form is kept only when it is the
player's own name (هوغو): a first name alone names too many players."""
import json, os, re, unicodedata
from collections import defaultdict
from datetime import datetime, timezone

AR = re.compile(r"[؀-ۿ]")
MARKS = re.compile(r"[ً-ْـ]")


def clean(s):
    return re.sub(r"\s+", " ", MARKS.sub("", s or "")).strip()


def fold(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _read(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def qids(G, S):
    """The Wikidata items of FotMob players (for graph/fetch.py's Arabic labels and aliases)."""
    out = set()
    for f in ("players_ar.json", "players_ar_aka.json"):
        out.update(v.get("qid") for v in _read(os.path.join(S.names, f)).values() if isinstance(v, dict) and v.get("qid"))
    out.update(q for (q,) in G.c.execute("""SELECT w.source_id FROM xref w JOIN xref f ON f.type='player' AND f.source='fotmob' AND f.tifo_id=w.tifo_id
                                            WHERE w.type='player' AND w.source='wikidata'"""))
    return sorted(out)


def build(G, S, learned=None, wd=None):
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    fm = {pid: sid for pid, sid in q("SELECT tifo_id, source_id FROM xref WHERE type='player' AND source='fotmob'") if str(sid).isdigit()}
    by_fid = {sid: pid for pid, sid in fm.items()}
    own, latin = {}, defaultdict(list)
    for pid, name, ar in q("SELECT pid, name, name_ar FROM player"):
        if pid in fm:
            if ar:
                own[fm[pid]] = clean(ar)
            if name:
                latin[fold(name)].append(fm[pid])
    forms = defaultdict(set)

    def add(fid, form):
        f = clean(form)
        if fid and f and AR.search(f):
            forms[str(fid)].add(f)

    for fid, ar in own.items():
        add(fid, ar)
    names = _read(os.path.join(S.names, "players_ar.json"))
    for fid, v in names.items():
        if isinstance(v, dict):
            add(fid, v.get("ar"))
            if v.get("latin") and fid not in latin.get(fold(v["latin"]), []):
                latin[fold(v["latin"])].append(fid)
    aka = _read(os.path.join(S.names, "players_ar_aka.json"))
    for fid, v in aka.items():
        for f in (v.get("aka") or []) if isinstance(v, dict) else []:
            add(fid, f)
    # news/aliases.yaml people: an Arabic form -> the player's Latin name (one FotMob player by that name only)
    try:
        import yaml
        people = (yaml.safe_load(open(os.path.join(S.root, "news", "aliases.yaml"), encoding="utf-8")) or {}).get("people") or {}
    except (OSError, ImportError):
        people = {}
    for form, target in people.items():
        hit = set(latin.get(fold(str(target)), []))
        if AR.search(str(form)) and len(hit) == 1:
            add(next(iter(hit)), form)
    # Wikidata: label and aliases of each player's item
    wd = wd if wd is not None else _read(os.path.join(S.db, "wd_ar.json"))
    qid_of = defaultdict(set)
    for src in (names, aka):
        for fid, v in src.items():
            if isinstance(v, dict) and v.get("qid"):
                qid_of[v["qid"]].add(fid)
    for pid, qq in q("SELECT tifo_id, source_id FROM xref WHERE type='player' AND source='wikidata'"):
        if pid in fm:
            qid_of[qq].add(fm[pid])
    for qq, fids in qid_of.items():
        e = wd.get(qq) or {}
        for fid in fids:
            for f in [e.get("label")] + list(e.get("aliases") or []):
                add(fid, f)
    # 365Scores: its Arabic name when its club is his latest FotMob club and the Latin names agree
    ix = S.published("s365/index.json") or {}
    t365 = {r[0]: r[4] for r in ix.get("teams") or [] if len(r) > 4 and r[4]}
    team_fid = {tid: sid for tid, sid in q("SELECT tifo_id, source_id FROM xref WHERE type='team' AND source='fotmob'")}
    club = {}
    for pid, tid, _ in q("SELECT a.pid, a.tid, max(m.date) FROM appearance a JOIN match m ON m.mid=a.mid WHERE a.played=1 GROUP BY a.pid"):
        if pid in fm and tid in team_fid:
            club[fm[pid]] = str(team_fid[tid])
    for row in ix.get("players") or []:
        if len(row) < 4:
            continue
        _, ar, en, team = row[:4]
        fteam = t365.get(team)
        hits = [fid for fid in latin.get(fold(en), []) if fteam and club.get(fid) == str(fteam)]
        if len(hits) == 1:
            add(hits[0], ar)
    for fid, d in (learned or {}).items():
        for f in d or {}:
            add(fid, f)
    out = {}
    for fid, fs in forms.items():
        mine = own.get(fid) or clean((names.get(fid) or {}).get("ar") if isinstance(names.get(fid), dict) else "")
        keep = sorted(f for f in fs if " " in f or f == mine)
        if keep:
            out[fid] = keep
    return {"generated": datetime.now(timezone.utc).isoformat()[:19] + "Z", "players": dict(sorted(out.items()))}

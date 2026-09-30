"""Every match of a UAE calendar day, compact: v1/all/<yyyymmdd>.json (owner 2026-09-30: «اريد الموقع شامل اي مباراة او
احصائية او شي يصير علطول ينلقى في موقعنا»).

Input: FotMob's day list (api/data/matches?date=…&timezone=Asia/Dubai, the one request the poller already makes for
day/<ymd>.json: ~180 leagues and 600-700 matches on a normal weekend) and, as extra leagues, the Arab leagues FotMob has
no page for, from 365Scores (sources/s365.py, ids prefixed "365:" so they cannot collide with FotMob's).

Document:
  {"date": "20260930", "tz": "Asia/Dubai", "generated", "n": matches, "live": live now, "leagues": [
     {"id": 47, "name": "Premier League", "name_ar": "الدوري الإنجليزي الممتاز", "cc": "ENG", "country_ar": "إنجلترا",
      "ours": true, "src": "365" (365Scores leagues only),
      "matches": [{"id", "utc", "status", "minute" (live), "home": [id, Arabic or English name, score, red cards],
                   "away": [...], "ours": true (a page on the site), "g": "Grp. A" (group), "pen": [h, a], "agg": "3 - 2",
                   "sd": "AET" | "Pen" | "PP" … (status detail)}]}]}
Keys that would be null are left out. Leagues: ours first (competitions.yaml order: UAE first), then the Arab
countries, the big European leagues, the international competitions, then the rest by Arabic country name; inside a
country senior men's leagues before women's, youth and reserve leagues, then FotMob's league id (older = bigger).
"""
import re

from sources import schema as S
from sources.fotmob import status_of
from timeutil import parse_utc, iso

ARAB_CC = ["UAE", "KSA", "QAT", "KUW", "BHR", "OMA", "IRQ", "JOR", "SYR", "LBN", "LIB", "PLE", "YEM", "EGY", "SUD", "LBY",
           "TUN", "ALG", "MAR", "MTN", "SOM", "DJI", "COM"]
BIG_EU = ["ENG", "ESP", "ITA", "GER", "FRA", "POR", "NED"]
CC_SHORT = {"UAE": "الإمارات"}                                           # over FotMob's «الإمارات العربية المتحدة»
CC_AR = {"LBN": "لبنان", "LIB": "لبنان", "INT": "دولي", "KSA": "السعودية"}   # when FotMob's map has none (no LBN in it)
LOWER = re.compile(r"women|kvinner|damallsvenskan|frauen|femenin|f[eé]minine|ladies|\bw\)|u-?1\d\b|u-?2[0-3]\b|under[- ]?\d\d|"
                   r"youth|junior|reserve|primavera|juvenil|\bii\b|development|academy|amateur|regionalliga|oberliga", re.I)
LIVE = S.LIVE_STATUSES
KEEP_LIVE_ROWS_H = 3          # all/live.json keeps a finished match this long after kickoff + 2 h (so pages see it end)


def _group_label(lg):
    g = lg.get("groupName")
    if g:
        return g
    parent = lg.get("parentLeagueName")
    name = lg.get("name") or ""
    if parent and name.startswith(parent):
        return name[len(parent):].strip(" -") or None
    m = re.search(r"\b(Gr(?:ou)?p\.?\s*[A-Z0-9]{1,2})\s*$", name)
    return m.group(1) if m else None


def _base_name(lg):
    name = lg.get("parentLeagueName") or lg.get("name") or ""
    return re.sub(r"\s*Gr(?:ou)?p\.?\s*[A-Z0-9]{1,2}\s*$", "", name).strip() or name


def _team(t, names, ms):
    tid = S._int(t.get("id"))
    nm = (names.get("teams") or {}).get(str(tid)) or t.get("name") or t.get("longName")
    row = [tid, nm, None, None]
    if ms not in (S.SCHEDULED, S.POSTPONED, S.CANCELLED) and isinstance(t.get("score"), int):
        row[2] = t["score"]
    if t.get("redCards"):
        row[3] = t["redCards"]
    while row and row[-1] is None:
        row.pop()
    return row


def match_row(m, names, ours_match):
    st = m.get("status") or {}
    status, detail, minute = status_of(st)
    ko = parse_utc(st.get("utcTime"))
    h, a = m.get("home") or {}, m.get("away") or {}
    row = {"id": S._int(m.get("id")), "utc": iso(ko), "status": status}
    if status in LIVE and minute:
        row["minute"] = minute
    row["home"], row["away"] = _team(h, names, status), _team(a, names, status)
    if ours_match:
        row["ours"] = True
    if h.get("penScore") is not None and a.get("penScore") is not None:
        row["pen"] = [h["penScore"], a["penScore"]]
    if st.get("aggregatedStr"):
        row["agg"] = st["aggregatedStr"]
    if detail and detail not in ("FT", "HT"):
        row["sd"] = detail
    if st.get("matchTimeTbd"):
        row["tbd"] = True
    return row


def fotmob_leagues(raw, names, ours, arab_nat=()):
    """FotMob's day list -> leagues (groups of one competition merged, each match keeping its group label)."""
    by = {}
    arab_nat = set(arab_nat or ())
    for lg in (raw or {}).get("leagues") or []:
        cid = S._int(lg.get("primaryId") or lg.get("parentLeagueId") or lg.get("id"))
        if cid is None:
            continue
        d = by.get(cid)
        if d is None:
            cc = lg.get("ccode") or ""
            d = by[cid] = {"id": cid, "name": _base_name(lg), "name_ar": (names.get("competitions") or {}).get(str(cid)),
                           "cc": cc, "country_ar": CC_SHORT.get(cc) or (names.get("countries") or {}).get(cc) or CC_AR.get(cc),
                           "ours": cid in ours, "matches": [], "_lower": bool(LOWER.search(lg.get("name") or ""))}
        is_group = bool(lg.get("isGroup")) or (S._int(lg.get("id")) != cid)
        g = _group_label(lg) if is_group else None
        for m in lg.get("matches") or []:
            tids = {S._int((m.get("home") or {}).get("id")), S._int((m.get("away") or {}).get("id"))}
            row = match_row(m, names, cid in ours or bool(arab_nat & tids))
            if row["id"] is None:
                continue
            if g:
                row["g"] = g
            d["matches"].append(row)
    return [d for d in by.values() if d["matches"]]


def _rank(lg, order):
    if lg.get("ours"):
        return (0, order.get(lg["id"], 999), 0, "", 0)
    cc = lg.get("cc") or ""
    low = 1 if lg.get("_lower") else 0
    lid = lg["id"] if isinstance(lg["id"], int) else 10 ** 9
    if cc in ARAB_CC:
        return (1, ARAB_CC.index(cc), low, "", lid)
    if cc in BIG_EU:
        return (2, BIG_EU.index(cc), low, "", lid)
    if cc == "INT":
        return (3, 0, low, "", lid)
    return (4, 0, low, lg.get("country_ar") or cc, lid)


def build(ymd, raw, names, ours, order, arab_nat=(), extra=None, now=None):
    """-> the v1/all/<ymd>.json document. ours: competition ids of competitions.yaml; order: {id: position in that file};
    arab_nat: FotMob ids of the Arab national teams; extra: 365Scores leagues already in this shape."""
    leagues = fotmob_leagues(raw, names, ours, arab_nat) + list(extra or [])
    leagues.sort(key=lambda lg: _rank(lg, order))
    n = live = 0
    for lg in leagues:
        lg["matches"].sort(key=lambda m: (m.get("utc") or "9", str(m["id"])))
        lg.pop("_lower", None)
        n += len(lg["matches"])
        live += sum(1 for m in lg["matches"] if m["status"] in LIVE)
        for k in ("name_ar", "country_ar"):
            if not lg.get(k):
                lg.pop(k, None)
        if not lg.get("ours"):
            lg.pop("ours", None)
    return {"date": ymd, "tz": "Asia/Dubai", "generated": iso(now) if now else None, "n": n, "live": live,
            "leagues": leagues, "sources": ["fotmob"] + (["365scores"] if extra else [])}


def live_rows(doc, now):
    """The rows all/live.json carries for one day: live matches, and finished ones for KEEP_LIVE_ROWS_H hours after
    kickoff + 2 h (a page that saw them live sees them end), each with its league id."""
    out = []
    for lg in (doc or {}).get("leagues") or []:
        for m in lg["matches"]:
            ko = parse_utc(m.get("utc"))
            if m["status"] in LIVE or (m["status"] == S.FINISHED and ko and 0 <= (now - ko).total_seconds() <= (2 + KEEP_LIVE_ROWS_H) * 3600):
                r = {k: m[k] for k in ("id", "status", "minute", "home", "away", "pen", "sd") if k in m}
                r["lg"] = lg["id"]
                out.append(r)
    return out


def hot(doc, now, ahead_min=5, behind_min=3):
    """Whether today's list should be refreshed every minute: a match is live, or one kicks off within the next few
    minutes (or should have kicked off moments ago and still shows as scheduled)."""
    for lg in (doc or {}).get("leagues") or []:
        for m in lg["matches"]:
            if m["status"] in LIVE:
                return True
            if m["status"] == S.SCHEDULED:
                ko = parse_utc(m.get("utc"))
                if ko and -behind_min * 60 <= (ko - now).total_seconds() <= ahead_min * 60:
                    return True
                if ko and -20 * 60 <= (ko - now).total_seconds() < -behind_min * 60:
                    return True          # kicked off by the clock but not marked live yet (a delay, a slow feed)
    return False

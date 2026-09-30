"""365Scores (webws.365scores.com, open JSON, Arabic with langId=27): one UAE day of the Arab leagues FotMob has no
page for (Jordan, Lebanon, Syria, Libya, Sudan, Palestine, Yemen, Bahrain, Oman and their cups; db/scores365.py LIVE_CC),
in the all-matches feed's league shape (compute/allday.py). One request per call:

  /web/games/?…&competitions=<ids>&startDate=dd/mm/yyyy&endDate=dd/mm/yyyy     (past and future dates both work)

Ids are prefixed "365:" (league "365:5479", match "365:4789179") so they never collide with FotMob's. statusGroup:
2 = not started, 3 = live, 4 = over (finished, but also «تأجلت» postponed and «ألغيت» cancelled: read statusText).
A score of -1 means none.
"""
from datetime import datetime

from timeutil import parse_utc, iso

BASE = "https://webws.365scores.com"
Q = "appTypeId=5&langId=27&timezoneName=Asia/Dubai&userCountryId=-1"
HEADERS = {"Origin": "https://www.365scores.com", "Referer": "https://www.365scores.com/"}
# 365Scores country id -> FotMob-style code (the all feed sorts Arab countries by it)
LIVE_CC = {161: "LBY", 119: "JOR", 123: "LBN", 125: "SYR", 130: "SUD", 116: "BHR", 117: "OMA", 226: "PLE", 170: "YEM"}
# the live competitions of v1/s365/index.json on 2026-09-30 (used when that file cannot be read)
DEFAULT_COMPS = (559, 565, 566, 564, 5481, 6143, 7600, 7162, 7184, 6904, 7252, 7227, 6166, 6079, 6798, 5524, 5505, 5478,
                 5479, 5480, 5599, 5828, 5836, 5635)
PREFIX = "365:"


def comps_from_index(idx):
    """v1/s365/index.json comps rows [id, ar, en, country id, ko, titles, first, last, women, tables, live, youth] ->
    the live competitions' ids (not women's, not youth)."""
    out = [r[0] for r in (idx or {}).get("comps") or [] if len(r) > 10 and r[10] and not r[8] and not (len(r) > 11 and r[11])]
    return out or list(DEFAULT_COMPS)


def day_url(comp_ids, ymd):
    d = datetime.strptime(ymd, "%Y%m%d").strftime("%d/%m/%Y")
    return f"{BASE}/web/games/?{Q}&competitions={','.join(str(c) for c in comp_ids)}&startDate={d}&endDate={d}"


def fetch_day(http, comp_ids, ymd):
    return http.get_json(day_url(comp_ids, ymd), headers=HEADERS, min_ttl=60)


def status(g):
    """-> (status, minute) in our schema's words."""
    grp, txt = g.get("statusGroup"), g.get("statusText") or ""
    if "تأجل" in txt or "مؤجل" in txt:
        return "postponed", None
    if "ألغي" in txt or "ملغا" in txt or "ملغي" in txt:
        return "cancelled", None
    if "توقف" in txt:
        return "abandoned", None
    if grp == 3:
        if (g.get("shortStatusText") or "") == "شوط" or "استراحة" in txt:
            return "ht", "HT"
        m = (g.get("gameTimeDisplay") or "").replace("'", "").replace("’", "").strip()
        return "live", m or None
    if grp == 4:
        return "finished", None
    return "scheduled", None


def _score(t):
    s = t.get("score")
    return int(s) if isinstance(s, (int, float)) and s >= 0 else None


def leagues(raw, only_cc=LIVE_CC):
    """365Scores games payload -> [league] in compute/allday.py's shape (src "365")."""
    raw = raw or {}
    comps = {c.get("id"): c for c in raw.get("competitions") or []}
    countries = {c.get("id"): c.get("name") for c in raw.get("countries") or []}
    by = {}
    for g in raw.get("games") or []:
        c = comps.get(g.get("competitionId")) or {}
        cc_id = c.get("countryId")
        if only_cc is not None and cc_id not in only_cc:
            continue
        lid = PREFIX + str(g.get("competitionId"))
        lg = by.get(lid)
        if lg is None:
            lg = by[lid] = {"id": lid, "name": c.get("name") or g.get("competitionDisplayName") or "", "name_ar": c.get("name"),
                            "cc": (only_cc or {}).get(cc_id, ""), "country_ar": countries.get(cc_id), "src": "365", "matches": []}
        st, minute = status(g)
        h, a = g.get("homeCompetitor") or {}, g.get("awayCompetitor") or {}
        ko = parse_utc(g.get("startTime"))
        row = {"id": PREFIX + str(g.get("id")), "utc": iso(ko), "status": st}
        if minute and st in ("live", "ht"):
            row["minute"] = minute
        for side, t in (("home", h), ("away", a)):
            r = [PREFIX + str(t.get("id")) if t.get("id") else None, t.get("name"), _score(t) if st not in ("scheduled", "postponed", "cancelled") else None]
            if t.get("redCards"):
                r.append(t["redCards"])
            while r and r[-1] is None:
                r.pop()
            row[side] = r
        if g.get("groupName") and not g.get("groupName", "").startswith(lg["name"]):
            row["g"] = g["groupName"]
        lg["matches"].append(row)
    return [lg for lg in by.values() if lg["matches"]]

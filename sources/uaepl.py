"""uaepl.ae (official ADNOC Pro League site, Laravel) -> normalized schema. Fallback for the UAE
Pro League / League Cup table and fixtures, and the source of official Arabic stadium names and the
full-season pairings (FotMob publishes only the rounds already dated).

XHR endpoints (plain GET + `X-Requested-With: XMLHttpRequest`, answer {"html": "<fragment>"}):
  /{en|ar}/standings/list?seasonCompetitionId=<uuid>&teamId=
  /{en|ar}/fixtures/matches?seasonCompetitionId=<uuid>&weekNumber=     (empty = every week, 182 matches)

Parsing traps (research/league-2026-09-26.md, re-checked 2026-09-26):
  * SCORE ORDER. The Arabic fragment prints «عجمان 3:2 كلباء» for Ajman 2-3 Kalba: in /ar/ the
    "a:b" string is AWAY:HOME (RTL). /en/ prints HOME:AWAY. We read numbers from /en/ and names from
    /ar/, joined on the matchList_<id> element id; parse_score_ar() exists for an /ar/-only fallback.
  * STANDINGS COLUMNS. Both languages put "goals against" BEFORE "goals for". Columns are mapped by
    their header label, never by position.
  * Times are UAE local (Asia/Dubai); "TBC" = not scheduled yet.
"""
import re
from datetime import datetime
from html.parser import HTMLParser  # noqa: F401  (bs4 uses it; keeps the bundle free of lxml)

from bs4 import BeautifulSoup

import config
from timeutil import parse_uae_local, kickoff_pair
from . import schema as S
from .base import Source
from .http import Http

BASE = "https://www.uaepl.ae"
XHR = {"X-Requested-With": "XMLHttpRequest"}


def parse_score_en(text):
    """'/en/' score 'h:a' -> {"home": h, "away": a}."""
    m = re.match(r"\s*(\d+)\s*[:\-]\s*(\d+)\s*$", text or "")
    return {"home": int(m.group(1)), "away": int(m.group(2))} if m else None


def parse_score_ar(text):
    """'/ar/' score 'a:h' (reversed by RTL) -> {"home": h, "away": a}."""
    m = re.match(r"\s*(\d+)\s*[:\-]\s*(\d+)\s*$", (text or "").replace("‎", "").replace("‏", ""))
    return {"home": int(m.group(2)), "away": int(m.group(1))} if m else None


def _txt(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def _slug(box_club):
    a = box_club.select_one("a[href*='/clubs/']")
    return a["href"].rstrip("/").rsplit("/", 1)[-1] if a else None


def parse_fixtures(html_en: str, html_ar: str | None = None) -> list[dict]:
    """Both fragments -> raw fixture dicts keyed by uaepl match id (not yet normalized)."""
    ar_by_id = {}
    if html_ar:
        for b in BeautifulSoup(html_ar, "html.parser").select("div.upcomingMatches__box"):
            clubs = b.select(".upcomingMatches__club")
            ar_by_id[b.get("id")] = {
                "names": [_txt(c.select_one(".upcomingMatches__club-name")) for c in clubs],
                "score_ar": _txt(b.select_one(".upcomingMatches__score")) or None,
                "stadium": _txt(b.select_one(".upcomingMatches__stadium-name")).lstrip("‎") or None,
            }
    out = []
    for b in BeautifulSoup(html_en, "html.parser").select("div.upcomingMatches__box"):
        bid = b.get("id") or ""
        clubs = b.select(".upcomingMatches__club")
        if len(clubs) != 2:
            continue
        dates = [_txt(x) for x in b.select(".upcomingMatches__time-info-date")]
        week = next((int(m.group(1)) for d in dates for m in [re.search(r"GW\s*(\d+)", d)] if m), None)
        day = next((d for d in dates if re.search(r"\d{4}", d)), None)
        tm = _txt(b.select_one(".upcomingMatches__time-info-num")) or None
        link = b.select_one("a[href*='/fixtures/']")
        ar = ar_by_id.get(bid, {})
        out.append({
            "uaepl_id": (link["href"].rstrip("/").rsplit("/", 1)[-1] if link else bid.replace("matchList_", "")),
            "box_id": bid, "week": week, "date_en": day, "time": tm if tm and re.match(r"\d{1,2}:\d{2}$", tm) else None,
            "home_slug": _slug(clubs[0]), "away_slug": _slug(clubs[1]),
            "home_en": _txt(clubs[0].select_one(".upcomingMatches__club-name")),
            "away_en": _txt(clubs[1].select_one(".upcomingMatches__club-name")),
            "home_ar": (ar.get("names") or [None, None])[0], "away_ar": (ar.get("names") or [None, None])[1],
            "status_text": _txt(b.select_one(".upcomingMatches__time-top")) or None,
            "score_en": _txt(b.select_one(".upcomingMatches__score")) or None,
            "score_ar": ar.get("score_ar"),
            "stadium_en": _txt(b.select_one(".upcomingMatches__stadium-name")).lstrip("‎") or None,
            "stadium_ar": ar.get("stadium"),
        })
    return out


def _date(date_en):
    if not date_en:
        return None
    s = re.sub(r"\s+", " ", date_en).strip()
    for fmt in ("%a %d %b %Y", "%d %b %Y", "%A %d %B %Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    m = re.search(r"(\d{1,2}) (\w{3})\w* (\d{4})", s)
    if m:
        try:
            return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %b %Y").strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def parse_standings(html_en: str, html_ar: str | None = None) -> list[dict]:
    """-> [{"rank", "name_en", "name_ar", "uuid", "played", "won", "drawn", "lost", "gf", "ga", "gd", "pts"}]"""
    label_map = {"position": "rank", "played": "played", "wins": "won", "draws": "drawn", "losses": "lost",
                 "goal against": "ga", "goals against": "ga", "goal for": "gf", "goals for": "gf",
                 "goals difference": "gd", "goal difference": "gd", "points": "pts", "club name": "name"}
    s_en = BeautifulSoup(html_en, "html.parser")
    header = [re.sub(r"\s+", " ", _txt(c)).lower() for c in s_en.select(".section-standing__table-title-tab .section-standing__cell")]
    cols = [label_map.get(h) for h in header]
    if "gf" not in cols or "ga" not in cols or "pts" not in cols:
        raise S.Invalid(f"uaepl standings header changed: {header}")
    ar_names = {}
    if html_ar:
        for it in BeautifulSoup(html_ar, "html.parser").select(".accordion-item .section-standing__item"):
            name = it.select_one(".section-standing__name span")
            ar_names[it.get("data-tab")] = _txt(name)
    rows = []
    for it in s_en.select(".accordion-item .section-standing__item"):
        cells = it.find_all("div", class_="section-standing__cell", recursive=False)
        vals = {}
        for col, cell in zip(cols, cells):
            if not col:
                continue
            t = _txt(cell)
            if col == "name":
                vals[col] = t
            else:
                m = re.match(r"^[+\-]?\d+$", t.replace(" ", ""))
                vals[col] = int(t.replace(" ", "")) if m else None
        vals["uuid"] = it.get("data-tab")
        vals["name_ar"] = ar_names.get(it.get("data-tab"))
        rows.append(vals)
    return rows


class UaePL(Source):
    name = "uaepl"

    def __init__(self, http: Http | None = None, names: dict | None = None):
        self.http = http or Http()
        self.names = names or {"teams": {}}
        self.slug_to_id = config.uaepl_teams()
        self.en_to_slug = config.uaepl_en_names()

    def _get_html(self, lang, path, params):
        q = "&".join(f"{k}={v}" for k, v in params.items())
        return self.http.get_json(f"{BASE}/{lang}/{path}?{q}", headers=XHR, min_ttl=30).get("html") or ""

    def _team(self, slug, name_en, name_ar):
        tid = self.slug_to_id.get(slug or "")
        return S.team_ref(tid, name_en, self.names.get("teams", {}).get(str(tid)) or name_ar)

    def fixtures(self, comp: dict, week: str = "") -> list[dict]:
        sid = comp["uaepl"]
        en = self._get_html("en", "fixtures/matches", {"seasonCompetitionId": sid, "weekNumber": week})
        ar = self._get_html("ar", "fixtures/matches", {"seasonCompetitionId": sid, "weekNumber": week})
        return [self.normalize_fixture(comp["id"], f) for f in parse_fixtures(en, ar)]

    def normalize_fixture(self, comp_id, f):
        date = _date(f["date_en"])
        ko = parse_uae_local(date, f["time"]) if date and f["time"] else None
        score = parse_score_en(f["score_en"]) if f["score_en"] else parse_score_ar(f["score_ar"])
        st = (f["status_text"] or "").strip().upper()
        if "POSTPON" in st:
            status, minute = S.POSTPONED, None
        elif st in ("FT", "FULL TIME") or "نهاية" in st:
            status, minute = S.FINISHED, None
        elif score is not None:
            status, minute = S.LIVE, (re.sub(r"[^0-9+]", "", st) or None)
        else:
            status, minute = S.SCHEDULED, None
        return {
            "id": None, "ext_id": f"uaepl:{f['uaepl_id']}", "comp": comp_id, "season": None,
            "round": str(f["week"]) if f["week"] else None, "stage": None,
            **kickoff_pair(ko), "date_uae": date, "time_tbd": ko is None, "date_tbd": date is None,
            "status": status, "status_detail": "FT" if status == S.FINISHED else None, "minute": minute,
            "score": score if status != S.SCHEDULED else None, "penalties": None,
            "home": self._team(f["home_slug"], f["home_en"], f["home_ar"]),
            "away": self._team(f["away_slug"], f["away_en"], f["away_ar"]),
            "venue_name": f["stadium_en"], "venue_name_ar": f["stadium_ar"], "source": self.name,
        }

    def standings(self, comp: dict) -> dict:
        sid = comp["uaepl"]
        en = self._get_html("en", "standings/list", {"seasonCompetitionId": sid, "teamId": ""})
        ar = self._get_html("ar", "standings/list", {"seasonCompetitionId": sid, "teamId": ""})
        rows = []
        for r in parse_standings(en, ar):
            slug = self.en_to_slug.get(r.get("name"))
            rows.append({"rank": r.get("rank"), "team": self._team(slug, r.get("name"), r.get("name_ar")),
                         "played": r.get("played"), "won": r.get("won"), "drawn": r.get("drawn"), "lost": r.get("lost"),
                         "gf": r.get("gf"), "ga": r.get("ga"), "gd": r.get("gd"), "pts": r.get("pts"),
                         "deduction": None, "form": None, "zone": None, "live": False})
        return {"comp": comp["id"], "season": None, "composite": False,
                "groups": [{"id": comp["id"], "name": None, "rows": rows}], "legend": [], "bracket": None,
                "order": "source", "source": self.name}

    # --- Source interface ---
    def competition(self, comp: dict) -> dict:
        matches = self.fixtures(comp)
        st = self.standings(comp)
        teams = {}
        for m in matches:
            for side in ("home", "away"):
                if m[side]["id"]:
                    teams[m[side]["id"]] = m[side]
        return {"competition": {"id": comp["id"], "name": comp.get("name_en"), "name_ar": comp.get("name_ar"),
                                "season": None, "source": self.name, "has_table": True},
                "matches": matches, "standings": st, "leaders": None, "teams": list(teams.values())}

    def day(self, yyyymmdd, comp_filter=lambda m: True):
        raise NotImplementedError("uaepl.ae has no per-day scoreboard")

    def match(self, match_id):
        raise NotImplementedError("uaepl.ae has no match-detail XHR")

    def team(self, team_id):
        raise NotImplementedError("uaepl.ae team pages are not parsed")

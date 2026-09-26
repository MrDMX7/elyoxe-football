"""Match history of the UAE club competitions, slim, one list per season (state/history/{comp}.json).
Past seasons never change: each is fetched once (1 request). The current season comes from the live
fixtures. Feeds the Tifo rating, facts, bump charts, coach tables and the archive."""
from sources import schema as S


def slim(m, season):
    """Normalized match -> compact history row (finished or not)."""
    return {"id": m["id"], "ko": m.get("kickoff_utc"), "comp": m["comp"], "season": season, "round": m.get("round"),
            "h": m["home"]["id"], "a": m["away"]["id"],
            "hs": (m.get("score") or {}).get("home"), "as": (m.get("score") or {}).get("away"),
            "st": m["status"]}


def finished(rows):
    return [r for r in rows if r["st"] == S.FINISHED and r["hs"] is not None and r["h"] and r["a"]]


def season_rows(fm, comp_id, season):
    raw = fm.league_raw(comp_id, season)
    data = fm.competition_from_raw({"id": comp_id}, raw, with_leaders=False)
    s = data["competition"].get("season") or season
    return s, [slim(m, s) for m in data["matches"] if m.get("id")], raw.get("allAvailableSeasons") or []


def all_rows(hist: dict) -> list:
    """hist {comp: {season: [rows]}} -> flat list."""
    return [r for seasons in hist.values() for rows in seasons.values() for r in rows]

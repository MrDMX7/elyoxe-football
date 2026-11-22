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


def with_archive(rows, older):
    """FotMob's finished rows plus every season of the league the archive holds and FotMob does not (v1/league-history/<id>.json,
    graph/publish.league_history: [kickoff, home, away, home goals, away goals]), oldest first. The pre-match facts then read
    «since 1888/1889», not «since 2010/2011» (22 Nov 2026)."""
    if not older:
        return rows
    have = {r["season"] for r in rows}
    old = [{"id": None, "ko": ko, "comp": older.get("comp"), "season": season, "round": None, "h": h, "a": a, "hs": hs, "as": as_,
            "st": S.FINISHED} for season, ms in (older.get("seasons") or {}).items() if season not in have for ko, h, a, hs, as_ in ms]
    return sorted(old, key=lambda r: r["ko"] or "") + rows

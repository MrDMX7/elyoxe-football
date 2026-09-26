"""Club-level indicators: coach pressure, fatigue and AFC travel, coach history.

COACH PRESSURE (comp/{id}/pressure.json), per team, over the current coach's league games this
season (FotMob coachHistory gives the current coach's W/D/L for the season; the window is his last
N <= 6 league games) :
  xppg  = mean expected points from the Tifo-rating probabilities before each game
  ppg   = mean points actually won
  index = clamp(50 + 40 * (xppg - ppg) + 8 * losing_streak + 4 * winless_streak, 0, 100)
  50 = performing as expected, higher = more pressure. FotMob gives season granularity only, so a
  mid-season appointment is counted from his first game this season in coachHistory's count.
FATIGUE (comp/{id}/fatigue.json): matches in the last 14 days (all competitions, from the team
page), days since the last and until the next match, and AFC away trips in the last 30 days with
the straight-line distance from the club's home stadium to the venue.
"""
from datetime import timedelta

from compute.venues import haversine_km
from timeutil import parse_utc


def pressure(team_rows, preds_by_match, coach, coach_history, season):
    """team_rows: [(ko, f, a, home, opp, season, match_id)] league games, chronological."""
    cur = [r for r in team_rows if r[5] == season]
    games_under = None
    if coach and coach_history:
        mine = [c for c in coach_history if c.get("id") == coach.get("id") and c.get("season") == season]
        if mine:
            games_under = sum((c.get("won") or 0) + (c.get("drawn") or 0) + (c.get("lost") or 0) for c in mine)
    n = min(6, len(cur) if games_under is None else min(games_under, len(cur)))
    window = cur[-n:] if n else []
    pts = [3 if f > a else 1 if f == a else 0 for _, f, a, *_ in window]
    xp = []
    for ko, f, a, home, opp, s, mid in window:
        p = preds_by_match.get(mid)
        if p:
            xp.append(3 * (p[0] if home else p[2]) + p[1])
    lose = winless = 0
    for _, f, a, *_ in reversed(cur):
        if f < a:
            lose += 1
        else:
            break
    for _, f, a, *_ in reversed(cur):
        if f <= a:
            winless += 1
        else:
            break
    if not window or len(xp) != len(window):
        return {"coach": coach, "games": len(window), "index": None, "losing_streak": lose, "winless_streak": winless}
    ppg, xppg = sum(pts) / len(pts), sum(xp) / len(xp)
    idx = max(0, min(100, round(50 + 40 * (xppg - ppg) + 8 * lose + 4 * winless)))
    return {"coach": coach, "games": len(window), "ppg": round(ppg, 2), "xppg": round(xppg, 2),
            "losing_streak": lose, "winless_streak": winless, "index": idx,
            "coach_games_this_season": games_under}


def fatigue(fixtures, now, home_stadium, venues_by_match, afc_comps=(525, 9469, 10622), team_id=None):
    past = [m for m in fixtures if m["status"] == "finished" and parse_utc(m.get("kickoff_utc"))]
    last14 = [m for m in past if now - parse_utc(m["kickoff_utc"]) <= timedelta(days=14)]
    last = max((parse_utc(m["kickoff_utc"]) for m in past), default=None)
    nxt = min((parse_utc(m["kickoff_utc"]) for m in fixtures if m["status"] == "scheduled" and parse_utc(m.get("kickoff_utc"))
               and parse_utc(m["kickoff_utc"]) > now), default=None)
    trips = []
    for m in fixtures:
        ko = parse_utc(m.get("kickoff_utc"))
        if m.get("comp") not in afc_comps or not ko or m["away"]["id"] != team_id or abs((now - ko).days) > 30:
            continue
        v = venues_by_match.get(str(m["id"]))
        km = (round(haversine_km(home_stadium["lat"], home_stadium["lon"], v["lat"], v["lon"]))
              if v and v.get("lat") is not None and home_stadium else None)
        trips.append({"match": m["id"], "kickoff_utc": m["kickoff_utc"], "venue": (v or {}).get("name"),
                      "city": (v or {}).get("city"), "km": km, "played": m["status"] == "finished"})
    return {"matches_14d": len(last14), "days_since_last": (now - last).days if last else None,
            "days_to_next": (nxt - now).days if nxt else None, "afc_away_trips_30d": trips,
            "afc_km_30d": sum(t["km"] or 0 for t in trips if t["played"])}

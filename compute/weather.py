"""Kickoff weather from Open-Meteo (free, no key; https://open-meteo.com/en/docs), heat index included.

One batched request covers every stadium in play (comma-separated latitude/longitude lists), hourly
for 16 days, cached in state for weather_minutes (3 h). A match beyond the 16-day horizon gets
weather=null with reason "beyond forecast horizon".

Heat index: NOAA/NWS (Rothfusz regression with the Steadman simple formula below 80 F and NWS
adjustments), from 2 m air temperature and relative humidity at the kickoff hour. Categories are the
NWS bands: caution 27-32 C, extreme caution 32-41 C, danger 41-54 C, extreme danger > 54 C.
Open-Meteo's own "apparent_temperature" (which also uses wind and radiation) is carried alongside.
"""
from datetime import timedelta

from timeutil import parse_utc, iso, now_utc

URL = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
       "&hourly=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation_probability,"
       "wind_speed_10m,weather_code&timezone=GMT&forecast_days=16")
HORIZON = timedelta(days=15, hours=20)


def heat_index_c(temp_c, rh):
    if temp_c is None or rh is None:
        return None
    T = temp_c * 9 / 5 + 32
    simple = 0.5 * (T + 61.0 + (T - 68.0) * 1.2 + rh * 0.094)
    if (simple + T) / 2 < 80:
        hi = simple
    else:
        hi = (-42.379 + 2.04901523 * T + 10.14333127 * rh - 0.22475541 * T * rh - 0.00683783 * T * T
              - 0.05481717 * rh * rh + 0.00122874 * T * T * rh + 0.00085282 * T * rh * rh - 0.00000199 * T * T * rh * rh)
        if rh < 13 and 80 <= T <= 112:
            hi -= ((13 - rh) / 4) * ((17 - abs(T - 95)) / 17) ** 0.5
        elif rh > 85 and 80 <= T <= 87:
            hi += ((rh - 85) / 10) * ((87 - T) / 5)
    return round((hi - 32) * 5 / 9, 1)


def heat_category(hi_c):
    if hi_c is None:
        return None
    if hi_c > 54:
        return "extreme_danger"
    if hi_c > 41:
        return "danger"
    if hi_c > 32:
        return "extreme_caution"
    if hi_c >= 27:
        return "caution"
    return "none"


def fetch(http, points: list[tuple[str, float, float]]) -> dict:
    """points [(stadium_id, lat, lon)] -> {stadium_id: {"time": [...], field: [...]}} (one request)."""
    if not points:
        return {}
    lat = ",".join(f"{p[1]:.4f}" for p in points)
    lon = ",".join(f"{p[2]:.4f}" for p in points)
    raw = http.get_json(URL.format(lat=lat, lon=lon), min_ttl=1800)
    items = raw if isinstance(raw, list) else [raw]
    out = {}
    for (sid, _, _), it in zip(points, items):
        h = it.get("hourly") or {}
        if h.get("time"):
            out[sid] = h
    return out


def at_kickoff(hourly: dict | None, kickoff_utc: str | None, fetched_at: str | None = None):
    ko = parse_utc(kickoff_utc)
    if not ko:
        return None
    if ko - now_utc() > HORIZON:
        return {"available": False, "reason": "beyond forecast horizon (16 days)"}
    if not hourly:
        return {"available": False, "reason": "no forecast for this stadium yet"}
    key = ko.replace(minute=0, second=0, microsecond=0)
    if ko.minute >= 30:
        key += timedelta(hours=1)
    stamp = key.strftime("%Y-%m-%dT%H:%M")
    try:
        i = hourly["time"].index(stamp)
    except ValueError:
        return {"available": False, "reason": "kickoff hour not in forecast"}
    g = lambda f: (hourly.get(f) or [None] * (i + 1))[i]  # noqa: E731
    t, rh = g("temperature_2m"), g("relative_humidity_2m")
    hi = heat_index_c(t, rh)
    return {"available": True, "hour_utc": stamp + "Z", "temp_c": t, "humidity": rh,
            "apparent_c": g("apparent_temperature"), "heat_index_c": hi, "heat_category": heat_category(hi),
            "precip_prob": g("precipitation_probability"), "wind_kmh": g("wind_speed_10m"),
            "weather_code": g("weather_code"), "source": "open-meteo", "fetched": fetched_at}

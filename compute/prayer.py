"""Prayer times at a UAE stadium and "prayer during play" flags.

METHOD. The UAE's official timetable comes from the General Authority of Islamic Affairs, Endowments
and Zakat (Awqaf, formerly GAIWE). Umm al-Qura is Saudi Arabia's and is wrong here. We use exactly
what elyoxe.com/tools already publishes (saas/tools/src/assets/prayer.js), so the two never disagree:
  adhan "Dubai" method = Fajr 18.2 deg, Isha 18.2 deg, Asr Shafi'i (shadow factor 1), sunrise/sunset at
  -0.833 deg, built-in offsets sunrise -3, dhuhr +3, asr +3, maghrib +3 min,
  plus the site's measured offsets asr -1, maghrib +1, isha +1 (checked against the published UAE
  timetable on 2026-09-24: 25 of 30 cells exact, the rest within one minute).
This file is a line-by-line port of adhan-js (MIT) SolarTime/PrayerTimes (Meeus, "Astronomical
Algorithms", ch. 15 rising/transit/setting with interpolation). tests/test_prayer.py checks it
against the vendored adhan.umd.min.js output (tools/adhan_reference.js) to within one minute.

PLAY WINDOW. A prayer "clashes" when it falls inside [kickoff, kickoff + 115 min]: 45 + 15 (half-time)
+ 45 + 10 stoppage. When the real period times are known (FotMob halfs) they replace the estimate.
"""
import math
from datetime import date as Date, datetime, timedelta, timezone

UTC = timezone.utc
FAJR_ANGLE = ISHA_ANGLE = 18.2
ADJUST = {"fajr": 0, "sunrise": -3, "dhuhr": 3, "asr": 3 - 1, "maghrib": 3 + 1, "isha": 0 + 1}
METHOD = ("UAE Awqaf (adhan 'Dubai': Fajr/Isha 18.2 deg, Asr Shafi'i) with the offsets used on "
          "elyoxe.com/tools: sunrise -3, dhuhr +3, asr +2, maghrib +4, isha +1 min")
PRAYERS = ("fajr", "dhuhr", "asr", "maghrib", "isha")
PLAY_MINUTES = 115
FIRST_HALF_END, SECOND_HALF_START = 48, 63


def _r(d): return math.radians(d)
def _d(r): return math.degrees(r)
def _unwind(a): return a - 360 * math.floor(a / 360)
def _norm(n, mx): return n - mx * math.floor(n / mx)


def _quadrant_shift(a):
    if -180 <= a <= 180:
        return a
    return a - 360 * round(a / 360)


def _julian_day(y, m, d, hours=0.0):
    Y = y if m > 2 else y - 1
    M = m if m > 2 else m + 12
    D = d + hours / 24
    A = math.trunc(Y / 100)
    B = math.trunc(2 - A + math.trunc(A / 4))
    return math.trunc(365.25 * (Y + 4716)) + math.trunc(30.6001 * (M + 1)) + D + B - 1524.5


class _Solar:
    def __init__(self, jd):
        T = (jd - 2451545.0) / 36525
        L0 = _unwind(280.4664567 + 36000.76983 * T + 0.0003032 * T * T)
        Lp = _unwind(218.3165 + 481267.8813 * T)
        Om = _unwind(125.04452 - 1934.136261 * T + 0.0020708 * T * T + T ** 3 / 450000)
        M = _unwind(357.52911 + 35999.05029 * T - 0.0001537 * T * T)
        Mr = _r(M)
        C = ((1.914602 - 0.004817 * T - 0.000014 * T * T) * math.sin(Mr)
             + (0.019993 - 0.000101 * T) * math.sin(2 * Mr) + 0.000289 * math.sin(3 * Mr))
        O = 125.04 - 1934.136 * T
        lam = _r(_unwind(L0 + C - 0.00569 - 0.00478 * math.sin(_r(O))))
        JD = T * 36525 + 2451545
        theta0 = _unwind(280.46061837 + 360.98564736629 * (JD - 2451545) + 0.000387933 * T * T - T ** 3 / 38710000)
        dpsi = ((-17.2 / 3600) * math.sin(_r(Om)) - (1.32 / 3600) * math.sin(2 * _r(L0))
                - (0.23 / 3600) * math.sin(2 * _r(Lp)) + (0.21 / 3600) * math.sin(2 * _r(Om)))
        deps = ((9.2 / 3600) * math.cos(_r(Om)) + (0.57 / 3600) * math.cos(2 * _r(L0))
                + (0.1 / 3600) * math.cos(2 * _r(Lp)) - (0.09 / 3600) * math.cos(2 * _r(Om)))
        eps0 = 23.439291 - 0.013004167 * T - 0.0000001639 * T * T + 0.0000005036 * T ** 3
        eps_app = _r(eps0 + 0.00256 * math.cos(_r(O)))
        self.declination = _d(math.asin(math.sin(eps_app) * math.sin(lam)))
        self.right_ascension = _unwind(_d(math.atan2(math.cos(eps_app) * math.sin(lam), math.cos(lam))))
        self.sidereal = theta0 + (dpsi * 3600 * math.cos(_r(eps0 + deps))) / 3600


def _interp(y2, y1, y3, n):
    a, b = y2 - y1, y3 - y2
    return y2 + (n / 2) * (a + b + n * (b - a))


def _interp_angles(y2, y1, y3, n):
    a, b = _unwind(y2 - y1), _unwind(y3 - y2)
    return y2 + (n / 2) * (a + b + n * (b - a))


class _SolarTime:
    def __init__(self, day: Date, lat, lon):
        jd = _julian_day(day.year, day.month, day.day)
        self.lat, self.lon = lat, lon
        self.s, self.p, self.n = _Solar(jd), _Solar(jd - 1), _Solar(jd + 1)
        Lw = -lon
        self.m0 = _norm((self.s.right_ascension + Lw - self.s.sidereal) / 360, 1)
        theta = _unwind(self.s.sidereal + 360.985647 * self.m0)
        alpha = _unwind(_interp_angles(self.s.right_ascension, self.p.right_ascension, self.n.right_ascension, self.m0))
        H = _quadrant_shift(theta - Lw - alpha)
        self.transit = (self.m0 + H / -360) * 24

    def hour_angle(self, h0, after):
        s, p, n, lat, Lw = self.s, self.p, self.n, self.lat, -self.lon
        t1 = math.sin(_r(h0)) - math.sin(_r(lat)) * math.sin(_r(s.declination))
        t2 = math.cos(_r(lat)) * math.cos(_r(s.declination))
        H0 = _d(math.acos(t1 / t2))
        m = self.m0 + H0 / 360 if after else self.m0 - H0 / 360
        theta = _unwind(s.sidereal + 360.985647 * m)
        alpha = _unwind(_interp_angles(s.right_ascension, p.right_ascension, n.right_ascension, m))
        delta = _interp(s.declination, p.declination, n.declination, m)
        H = theta - Lw - alpha
        h = _d(math.asin(math.sin(_r(lat)) * math.sin(_r(delta)) + math.cos(_r(lat)) * math.cos(_r(delta)) * math.cos(_r(H))))
        dm = (h - h0) / (360 * math.cos(_r(delta)) * math.cos(_r(lat)) * math.sin(_r(H)))
        return (m + dm) * 24

    def afternoon(self, shadow=1.0):
        tangent = abs(self.lat - self.s.declination)
        angle = _d(math.atan(1 / (shadow + math.tan(_r(tangent)))))
        return self.hour_angle(angle, True)


def _at(day: Date, hours: float) -> datetime:
    """adhan TimeComponents: floor h, m, s of the fractional hour, as UTC on that calendar day."""
    h = math.floor(hours)
    m = math.floor((hours - h) * 60)
    s = math.floor((hours - (h + m / 60)) * 3600)
    return datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(hours=h, minutes=m, seconds=s)


def _round_minute(dt: datetime) -> datetime:
    s = dt.second
    return (dt + timedelta(seconds=(60 - s) if s >= 30 else -s)).replace(microsecond=0)


def prayer_times(lat: float, lon: float, day: Date) -> dict:
    """{prayer: aware UTC datetime} for the UAE calendar day `day` at (lat, lon)."""
    st = _SolarTime(day, lat, lon)
    raw = {
        "fajr": _at(day, st.hour_angle(-FAJR_ANGLE, False)),
        "sunrise": _at(day, st.hour_angle(-50 / 60, False)),
        "dhuhr": _at(day, st.transit),
        "asr": _at(day, st.afternoon(1.0)),
        "maghrib": _at(day, st.hour_angle(-50 / 60, True)),
        "isha": _at(day, st.hour_angle(-ISHA_ANGLE, True)),
    }
    return {k: _round_minute(v + timedelta(minutes=ADJUST[k])) for k, v in raw.items()}


def clashes(kickoff: datetime, lat: float, lon: float, periods: dict | None = None) -> dict:
    """Prayer times for the kickoff's UAE day (and the next, for late matches) and the prayers that
    fall while the ball is in play or at half-time."""
    from timeutil import UAE, parse_utc
    ko = kickoff.astimezone(UTC)
    end = ko + timedelta(minutes=PLAY_MINUTES)
    fh_end, sh_start = ko + timedelta(minutes=FIRST_HALF_END), ko + timedelta(minutes=SECOND_HALF_START)
    estimated = True
    if periods:
        a = parse_utc(periods.get("firstHalfStarted"))
        b = parse_utc(periods.get("firstHalfEnded"))
        c = parse_utc(periods.get("secondHalfStarted"))
        z = parse_utc(periods.get("gameEnded") or periods.get("secondHalfEnded"))
        if a:
            ko, estimated = a, False
            fh_end = b or fh_end
            sh_start = c or sh_start
            end = z or max(end, sh_start + timedelta(minutes=52))
    local_day = ko.astimezone(UAE).date()
    times = prayer_times(lat, lon, local_day)
    nxt = prayer_times(lat, lon, local_day + timedelta(days=1))
    out = []
    for name in PRAYERS:
        for t in (times[name], nxt[name]):
            if ko <= t <= end:
                seg = "first_half" if t < fh_end else "halftime" if t < sh_start else "second_half"
                out.append({"prayer": name, "at_utc": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "at_uae": t.astimezone(UAE).strftime("%H:%M"),
                            "minute_of_play": int((t - ko).total_seconds() // 60), "segment": seg})
    return {"method": "uae-awqaf-18.2", "estimated_window": estimated,
            "times_uae": {k: v.astimezone(UAE).strftime("%H:%M") for k, v in times.items()},
            "clashes": out}

"""Time handling for every source. Everything we store is ISO-8601 UTC ("...Z") plus a UAE copy.

FotMob has two clocks:
  * status.utcTime / matchTimeUTCDate: real UTC ("2026-09-26T15:55:00.000Z"). Always use this for kickoff.
  * the dd.mm.yyyy HH:MM[:SS] strings (day scoreboard "time", header.status.halfs.*): Europe/Oslo
    wall-clock time WITH daylight saving: UTC+2 in summer (26.09.2026 17:57:03 = 15:57:03Z) and
    UTC+1 in winter (10.01.2027 15:00 = 14:00Z). The research note called it "UTC+2"; that only holds
    from late March to late October. Parse with zoneinfo, never a fixed offset.
uaepl.ae prints UAE local time (Asia/Dubai, UTC+4, no DST).
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
UAE = ZoneInfo("Asia/Dubai")
FOTMOB_LOCAL = ZoneInfo("Europe/Oslo")


def now_utc() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime | None) -> str | None:
    """UTC ISO string with Z, seconds precision."""
    if dt is None:
        return None
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_uae(dt: datetime | None) -> str | None:
    """UAE wall-clock ISO string with its +04:00 offset."""
    if dt is None:
        return None
    return dt.astimezone(UAE).strftime("%Y-%m-%dT%H:%M:%S+04:00")


def parse_utc(s: str | None) -> datetime | None:
    """'2026-09-26T15:55:00.000Z' / '2026-08-14T14:10:00Z' -> aware UTC datetime."""
    if not s:
        return None
    s = s.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def parse_fotmob_local(s: str | None) -> datetime | None:
    """'26.09.2026 17:57:03' or '26.09.2026 20:45' (Europe/Oslo wall clock) -> aware UTC datetime."""
    if not s or not s.strip():
        return None
    s = s.strip()
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M"):
        try:
            naive = datetime.strptime(s, fmt)
            return naive.replace(tzinfo=FOTMOB_LOCAL).astimezone(UTC)
        except ValueError:
            continue
    return None


def parse_uae_local(date_s: str, time_s: str) -> datetime | None:
    """uaepl.ae 'YYYY-MM-DD' + 'HH:MM' in UAE time -> aware UTC datetime."""
    try:
        naive = datetime.strptime(f"{date_s} {time_s}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return naive.replace(tzinfo=UAE).astimezone(UTC)


def uae_date(dt: datetime) -> str:
    """YYYYMMDD of the UAE calendar day the instant falls on."""
    return dt.astimezone(UAE).strftime("%Y%m%d")


def kickoff_pair(dt: datetime | None) -> dict:
    return {"kickoff_utc": iso(dt), "kickoff_uae": iso_uae(dt)}


def minutes_between(a: datetime, b: datetime) -> float:
    return (b - a) / timedelta(minutes=1)

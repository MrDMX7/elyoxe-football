"""FotMob's dd.mm.yyyy strings are Europe/Oslo wall clock (UTC+2 in summer, UTC+1 in winter),
not a fixed UTC+2; kickoffs come from utcTime; UAE is UTC+4 all year."""
from datetime import datetime, timezone

from timeutil import parse_fotmob_local, parse_utc, iso, iso_uae, uae_date, kickoff_pair, parse_uae_local


def test_fotmob_local_summer_is_utc_plus_2():
    # Kuwait v Iraq, Gulf Cup 2026-09-26: firstHalfStarted "26.09.2026 17:57:03" = 15:57:03 UTC
    dt = parse_fotmob_local("26.09.2026 17:57:03")
    assert iso(dt) == "2026-09-26T15:57:03Z"
    assert iso_uae(dt) == "2026-09-26T19:57:03+04:00"


def test_fotmob_local_winter_is_utc_plus_1():
    # UAE v Vietnam, Asian Cup: day feed "time" "10.01.2027 15:00" with utcTime 2027-01-10T14:00Z
    dt = parse_fotmob_local("10.01.2027 15:00")
    assert iso(dt) == "2027-01-10T14:00:00Z"
    assert iso_uae(dt) == "2027-01-10T18:00:00+04:00"


def test_fotmob_local_empty_and_garbage():
    assert parse_fotmob_local("") is None and parse_fotmob_local(None) is None
    assert parse_fotmob_local("not a date") is None


def test_utc_kickoff_to_uae():
    ko = parse_utc("2026-10-16T13:05:00.000Z")
    assert kickoff_pair(ko) == {"kickoff_utc": "2026-10-16T13:05:00Z", "kickoff_uae": "2026-10-16T17:05:00+04:00"}


def test_uae_calendar_day_crosses_utc_midnight():
    # 21:30 UTC is already the next day in the UAE
    assert uae_date(datetime(2026, 9, 26, 21, 30, tzinfo=timezone.utc)) == "20260927"
    assert uae_date(datetime(2026, 9, 26, 19, 59, tzinfo=timezone.utc)) == "20260926"


def test_uaepl_local_to_utc():
    assert iso(parse_uae_local("2026-10-18", "19:45")) == "2026-10-18T15:45:00Z"

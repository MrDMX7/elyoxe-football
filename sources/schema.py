"""The normalized schema (v1): the only shapes the poller, the computed extras and the future site see.
Full field-by-field description in docs/SCHEMA.md. Every adapter (fotmob, uaepl, apifootball) returns
these dicts; helpers here build the shared pieces and validate what an adapter produced, so a broken
or empty fetch is caught before it can overwrite a good snapshot.

Ids: competitions, teams, players and matches use FotMob's numeric ids (as int) — the canonical id
space. A different provider maps its own ids onto them (competitions.yaml `ids:`, teams map).
"""
SCHEMA_VERSION = 1

# match.status
SCHEDULED, LIVE, HALFTIME, FINISHED = "scheduled", "live", "ht", "finished"
POSTPONED, CANCELLED, ABANDONED, AWARDED, UNKNOWN = "postponed", "cancelled", "abandoned", "awarded", "unknown"
STATUSES = {SCHEDULED, LIVE, HALFTIME, FINISHED, POSTPONED, CANCELLED, ABANDONED, AWARDED, UNKNOWN}
LIVE_STATUSES = {LIVE, HALFTIME}

# event.type
EVENT_TYPES = {"goal", "own_goal", "penalty_goal", "missed_penalty", "yellow", "second_yellow", "red",
               "sub", "var", "half", "added_time", "shootout_goal", "shootout_miss"}

LOGO = "https://images.fotmob.com/image_resources/logo/teamlogo/{id}.png"


def team_ref(tid, name, name_ar=None, logo=None) -> dict:
    tid = _int(tid) or None     # FotMob occasionally sends id 0 for a known team (AFC U23 table, 2026-09-26)
    return {"id": tid, "name": name, "name_ar": name_ar,
            "logo": logo or (LOGO.format(id=tid) if tid else None)}


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


class Invalid(ValueError):
    """The fetched object is empty or malformed — keep the last good copy."""


def _need(cond, msg):
    if not cond:
        raise Invalid(msg)


def validate_match(m: dict):
    _need(isinstance(m, dict), "match not a dict")
    _need(isinstance(m.get("id"), int), f"match id {m.get('id')!r}")
    _need(m.get("status") in STATUSES, f"match {m.get('id')} status {m.get('status')!r}")
    for side in ("home", "away"):
        t = m.get(side) or {}
        _need(t.get("name"), f"match {m['id']} {side} team has no name")
    _need(m.get("kickoff_utc") or m.get("status") in (POSTPONED, CANCELLED), f"match {m['id']} has no kickoff")


def validate_matches(ms: list, min_count=1):
    _need(isinstance(ms, list) and len(ms) >= min_count, f"expected >= {min_count} matches, got {len(ms) if isinstance(ms, list) else ms!r}")
    for m in ms:
        validate_match(m)


def validate_standings(s: dict):
    _need(isinstance(s, dict) and s.get("groups"), "standings has no groups")
    for g in s["groups"]:
        rows = g.get("rows") or []
        _need(len(rows) >= 2, f"group {g.get('name')!r} has {len(rows)} rows")
        for r in rows:
            _need(isinstance(r.get("rank"), int) and (r.get("team") or {}).get("name"), f"bad row {r!r:.120}")
            _need(isinstance(r.get("pts"), int), f"row without points {r!r:.120}")


def validate_detail(d: dict):
    validate_match(d)
    _need("events" in d and "lineups" in d, f"detail {d.get('id')} lacks events/lineups keys")


def validate_team(t: dict):
    _need(isinstance(t, dict) and isinstance(t.get("id"), int) and t.get("name"), "team without id/name")


def validate_leaders(s: dict):
    _need(isinstance(s, dict) and isinstance(s.get("lists"), dict), "leaders without lists")
    _need(any(s["lists"].values()), "all leader lists empty")

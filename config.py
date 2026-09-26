"""Loads the YAML configuration once: competitions, stadiums, Arabic name overrides."""
import functools
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent


@functools.lru_cache(maxsize=None)
def _load(name):
    with open(ROOT / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def competitions() -> list[dict]:
    """Active entries of competitions.yaml, in file order (priority order for the heavy cursor)."""
    return [c for c in _load("competitions.yaml")["competitions"] if c.get("active", True)]


def competition(cid) -> dict | None:
    return next((c for c in competitions() if c["id"] == int(cid)), None)


def focus_teams() -> list[int]:
    """Teams whose full page (squad, all fixtures, .ics) is refreshed daily: UAE national team first."""
    return [int(t) for t in _load("competitions.yaml").get("focus_teams", [])]


def focus_comps() -> list[int]:
    """Competitions whose every team gets a team file (UAE club competitions)."""
    return [int(c) for c in _load("competitions.yaml").get("focus_comps", [])]


def settings() -> dict:
    return _load("competitions.yaml").get("settings", {})


def stadiums() -> list[dict]:
    return _load("stadiums.yaml").get("stadiums", [])


def team_overrides() -> dict:
    """teams_ar.yaml: {team_id: Arabic house-style name} applied on top of FotMob's map."""
    d = _load("teams_ar.yaml")
    return {str(k): v for k, v in (d.get("teams") or {}).items()}


def uaepl_teams() -> dict:
    """uaepl.ae club slug -> FotMob team id (teams_ar.yaml `uaepl:`)."""
    d = _load("teams_ar.yaml")
    return {k: int(v) for k, v in (d.get("uaepl") or {}).items()}


def uaepl_en_names() -> dict:
    """uaepl.ae English club name -> slug."""
    return dict(_load("teams_ar.yaml").get("uaepl_en") or {})

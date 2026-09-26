"""API-Football (api-sports.io, paid) — INTERFACE ONLY, not implemented.

Switching later: implement these methods to return the same normalized dicts as sources/fotmob.py
(docs/SCHEMA.md), map ids onto the canonical (FotMob) ids, and construct this class instead of
FotMob in poller.Poller.load(). Nothing else changes: the poller, compute/ and the files it writes
only see the normalized schema.

Endpoint map (v3, https://v3.football.api-sports.io, header x-apisports-key) — from the public docs,
NOT verified against a key (research/league-2026-09-26.md: no key, plan limits unverified):
  day(yyyymmdd)       GET /fixtures?date=YYYY-MM-DD&timezone=Asia/Dubai        (filter league ids)
  competition(comp)   GET /standings?league=L&season=Y  +  /fixtures?league=L&season=Y
                      + /players/topscorers|topassists?league=L&season=Y
  match(id)           GET /fixtures?id=F (events, lineups, statistics, players in one call)
                      + /fixtures/headtohead?h2h=A-B  + /injuries?fixture=F
  team(id)            GET /players/squads?team=T  +  /fixtures?team=T&season=Y  + /transfers?team=T
  arabic_names()      not offered: keep FotMob's map (state/names_ar.json) or teams_ar.yaml
Id mapping: competitions.yaml `ids: {apifootball: <league id>}` per competition; teams need a map
(API-Football team id -> FotMob team id), built once by name + country and reviewed by hand.
Status codes: NS->scheduled, 1H/2H/ET/P/LIVE->live, HT/BT->ht, FT/AET/PEN->finished, PST->postponed,
CANC->cancelled, ABD->abandoned, AWD/WO->awarded. `fixture.date` is ISO with offset (no Oslo trap).
"""
from .base import Source


class ApiFootball(Source):
    name = "apifootball"

    def __init__(self, http=None, key=None, names=None):
        self.http, self.key, self.names = http, key, names or {"teams": {}}

    def day(self, yyyymmdd, comp_filter=lambda m: True):
        raise NotImplementedError("API-Football adapter is a stub; see module docstring")

    def competition(self, comp):
        raise NotImplementedError("API-Football adapter is a stub; see module docstring")

    def match(self, match_id):
        raise NotImplementedError("API-Football adapter is a stub; see module docstring")

    def team(self, team_id):
        raise NotImplementedError("API-Football adapter is a stub; see module docstring")

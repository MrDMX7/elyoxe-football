"""The adapter interface. Swapping FotMob for the paid API-Football means writing one class with
these methods (sources/apifootball.py is the stub) and changing SOURCE in the poller config.

Every method returns normalized dicts (sources/schema.py, docs/SCHEMA.md) or raises
sources.http.FetchError / sources.schema.Invalid. Methods an adapter cannot serve raise
NotImplementedError, and the poller then falls back or skips that file.
"""
from abc import ABC, abstractmethod


class Source(ABC):
    name = "base"

    @abstractmethod
    def day(self, yyyymmdd: str, comp_filter) -> list[dict]:
        """All matches on a UAE calendar day, kept only when comp_filter(match) is true.
        Returns match summaries (schema: Match)."""

    @abstractmethod
    def competition(self, comp: dict) -> dict:
        """One competition's current season. `comp` is its competitions.yaml entry.
        Returns {"competition": Competition, "matches": [Match], "standings": Standings|None,
                 "leaders": Leaders|None, "teams": [TeamRef]}."""

    @abstractmethod
    def match(self, match_id: int) -> dict:
        """Match detail (schema: MatchDetail)."""

    @abstractmethod
    def team(self, team_id: int) -> dict:
        """Team with squad and fixtures across competitions (schema: Team)."""

    def arabic_names(self) -> dict:
        """{"teams": {id: ar}, "competitions": {id: ar}, "countries": {code: ar}} — optional."""
        raise NotImplementedError

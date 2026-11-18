"""Which matches get articles: the competitions in competitions.yaml settings.articles_priority, and every match of an Arab
national team (countries.yaml arab: true) in any competition, friendlies included. Ids from another source («365:5635», the
365Scores leagues and teams in v1/all/) are no FotMob id: they never match a priority competition or an Arab team."""
import config


def priority_comps() -> set[int]:
    return {int(c) for c in config.settings().get("articles_priority", [])}


def arab_teams() -> set[int]:
    return {int(c["fotmob_team"]) for c in config.countries() if c.get("arab") and c.get("fotmob_team")}


def _id(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def is_priority(comp_id, home_id, away_id) -> bool:
    return _id(comp_id) in priority_comps() or bool({_id(home_id), _id(away_id)} & arab_teams())

"""Which matches get articles: the competitions in competitions.yaml settings.articles_priority, and every match of an Arab
national team (countries.yaml arab: true) in any competition, friendlies included."""
import config


def priority_comps() -> set[int]:
    return {int(c) for c in config.settings().get("articles_priority", [])}


def arab_teams() -> set[int]:
    return {int(c["fotmob_team"]) for c in config.countries() if c.get("arab") and c.get("fotmob_team")}


def is_priority(comp_id, home_id, away_id) -> bool:
    return int(comp_id) in priority_comps() or bool({int(home_id), int(away_id)} & arab_teams())

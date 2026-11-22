"""analytics.leagues_step: a league that failed once and succeeds again is ok in health-analytics.json — its failure entry
lived on in the merged file (22 Nov 2026: nine «league-analytics:<id>» stayed failing after the fix)."""
import analytics as AN


class Store:
    def __init__(self):
        self.health = {}

    def ok(self, name, **extra):
        self.health[name] = {"ok": True}

    def fail(self, name, err, **extra):
        self.health[name] = {"ok": False, "error": err}


class P:
    def __init__(self):
        self.store = Store()
        self.prev_health = {"items": {"league-analytics:538": {"ok": False, "error": "TypeError"}}}

    def has_time(self, s):
        return True

    def due(self, key, every, cid=None):
        return True

    def mark(self, key, cid=None):
        pass


def test_a_league_that_succeeds_again_is_ok(monkeypatch):
    monkeypatch.setattr(AN, "analytics_leagues", lambda: [538])
    monkeypatch.setattr(AN, "history_complete", lambda p, comps: True)
    monkeypatch.setattr(AN, "league", lambda p, cid: None)
    p = P()
    AN.leagues_step(p)
    assert p.store.health == {"league-analytics:538": {"ok": True}}

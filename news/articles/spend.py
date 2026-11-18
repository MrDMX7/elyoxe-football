"""What the articles cost (spec, «Guards»): every call's tokens at list price into state/articles/spend.json by calendar month
(UTC); at $180 in a month writing stops until the month ends. Prices from the claude-api skill's models table, 2026-11-18:
Sonnet 5.5 $2 / $10, cache reads $0.10, cache writes 1.25x input; Haiku 5.5 $0.10 / $0.50."""
import usage_log

NAME = "articles/spend.json"
CAP = 180.0
PRICES = {"claude-sonnet-5-5": (2.0, 10.0, 0.10, 2.50), "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125)}


def cost(model, u):
    pin, pout, pread, pwrite = PRICES[model]
    return round((u.get("in", 0) * pin + u.get("out", 0) * pout + u.get("cache_read", 0) * pread
                  + u.get("cache_write", 0) * pwrite) / 1e6, 6)


class Spend:
    def __init__(self, store, now):
        self.store, self.month = store, now.strftime("%Y-%m")
        self.doc = store.get_state(NAME) or {}
        self.doc.setdefault(self.month, {"usd": 0.0, "calls": 0, "by_type": {}, "capped": False})
        self._was_capped = self.doc[self.month]["capped"]

    def month_total(self):
        return self.doc[self.month]["usd"]

    def allowed(self):
        return self.month_total() < CAP

    def add(self, model, usage, job):
        usd = cost(model, usage)
        m = self.doc[self.month]
        m["usd"] = round(m["usd"] + usd, 6); m["calls"] += 1
        m["by_type"][job] = round(m["by_type"].get(job, 0.0) + usd, 6)
        if m["usd"] >= CAP:
            m["capped"] = True
        usage_log.record_api(f"articles-{job}", model, usage, usd)
        return usd

    def capped_now(self):
        """True once, in the run that crossed the cap (the caller sends the one email)."""
        return self.doc[self.month]["capped"] and not self._was_capped

    def save(self):
        self.store.put_state(NAME, self.doc)

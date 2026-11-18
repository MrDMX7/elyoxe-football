"""The news queue (spec, «The desk»: automatic, the owner vetoes).

A story waits wait_minutes after it is first offered. The desk file (state/articles/desk.json, written by the desk page in
Phase 2b) can «reject» it, or «write» it at once. At most `daily` new articles a UAE day, and «write» does not lift that.

A written story is updated at most once an hour, and only for 2 or more new items or a higher stage. A queued story that
leaves the journal's window is dropped."""
from datetime import datetime, timedelta, timezone

UAE = timezone(timedelta(hours=4))
MAX_UPDATES = 3            # a saga gaining 2 items an hour would be rewritten ~24 times a day (final review, finding 11)
STAGE_RANK = {None: -1, "rumour": 0, "talks": 1, "agreed": 2, "here_we_go": 3, "official": 4}


class Queue:
    def __init__(self, state, desk, now, cfg):
        self.now, self.cfg, self.desk = now, cfg, desk or {}
        n = state.setdefault("news", {})
        n.setdefault("queue", {}); n.setdefault("done", {}); n.setdefault("failed", {})
        day = now.astimezone(UAE).date().isoformat()
        if n.get("day") != day:
            n["day"], n["count"] = day, 0
        for book in (n["done"], n["failed"]):
            for sid in [s for s, d in book.items() if datetime.fromisoformat(d["at"]) < now - timedelta(days=3)]:
                del book[sid]
        self.n = n

    def offer(self, sid, rank, items=0):
        """A story that failed comes back only after 2 or more new items, and is tried twice at most (final review, finding 1:
        a failing story was re-offered and due again every 20 minutes, 64 Sonnet calls a day)."""
        f = self.n["failed"].get(sid)
        if sid in self.n["done"] or (f and (f["tries"] >= 2 or items - f["items"] < 2)):
            return
        self.n["queue"].setdefault(sid, {"first": self.now.isoformat()})["rank"] = list(rank)

    def mark_failed(self, sid, items):
        f = self.n["failed"].setdefault(sid, {"tries": 0})
        f.update({"at": self.now.isoformat(), "items": items, "tries": f["tries"] + 1})
        self.n["queue"].pop(sid, None)

    def prune(self, alive):
        for sid in [s for s in self.n["queue"] if s not in alive]:
            del self.n["queue"][sid]

    def ready(self):
        left = self.cfg["daily"] - self.n["count"]
        if left <= 0:
            return []
        wait = timedelta(minutes=self.cfg["wait_minutes"])
        rej, now_ = set(self.desk.get("reject") or {}), set(self.desk.get("write") or {})
        due = [(sid not in now_, [-x for x in q["rank"]], sid) for sid, q in self.n["queue"].items()
               if sid not in rej and (sid in now_ or datetime.fromisoformat(q["first"]) + wait <= self.now)]
        return [sid for _, _, sid in sorted(due)][:left]

    def mark_written(self, sid, items, stage):
        prev = self.n["done"].get(sid)
        if prev is None:
            self.n["count"] += 1
        self.n["done"][sid] = {"at": self.now.isoformat(), "items": items, "stage": stage,
                               "updates": prev.get("updates", 0) + 1 if prev else 0}
        self.n["queue"].pop(sid, None)

    def wants_update(self, sid, items, stage):
        d = self.n["done"].get(sid)
        if not d or d.get("updates", 0) >= MAX_UPDATES or datetime.fromisoformat(d["at"]) + timedelta(hours=1) > self.now:
            return False
        return items - (d.get("items") or 0) >= 2 or STAGE_RANK.get(stage, -1) > STAGE_RANK.get(d.get("stage"), -1)

    def written_today(self):
        return self.n["count"]

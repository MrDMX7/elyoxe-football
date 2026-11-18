"""The news queue (spec, «The desk»: automatic, the owner vetoes).

A story waits wait_minutes after it is first offered. The desk file (state/articles/desk.json, written by the desk page in
Phase 2b) can «reject» it, or «write» it at once. At most `daily` new articles a UAE day, and «write» does not lift that.

A written story is updated at most once an hour, and only for 2 or more new items or a higher stage. A queued story that
leaves the journal's window is dropped."""
from datetime import datetime, timedelta, timezone

UAE = timezone(timedelta(hours=4))
STAGE_RANK = {None: -1, "rumour": 0, "talks": 1, "agreed": 2, "here_we_go": 3, "official": 4}


class Queue:
    def __init__(self, state, desk, now, cfg):
        self.now, self.cfg, self.desk = now, cfg, desk or {}
        n = state.setdefault("news", {})
        n.setdefault("queue", {}); n.setdefault("done", {})
        day = now.astimezone(UAE).date().isoformat()
        if n.get("day") != day:
            n["day"], n["count"] = day, 0
        for sid in [s for s, d in n["done"].items() if datetime.fromisoformat(d["at"]) < now - timedelta(days=3)]:
            del n["done"][sid]
        self.n = n

    def offer(self, sid, rank):
        if sid not in self.n["done"]:
            self.n["queue"].setdefault(sid, {"first": self.now.isoformat()})["rank"] = list(rank)

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
        if sid not in self.n["done"]:
            self.n["count"] += 1
        self.n["done"][sid] = {"at": self.now.isoformat(), "items": items, "stage": stage}
        self.n["queue"].pop(sid, None)

    def wants_update(self, sid, items, stage):
        d = self.n["done"].get(sid)
        if not d or datetime.fromisoformat(d["at"]) + timedelta(hours=1) > self.now:
            return False
        return items - (d.get("items") or 0) >= 2 or STAGE_RANK.get(stage, -1) > STAGE_RANK.get(d.get("stage"), -1)

    def written_today(self):
        return self.n["count"]

"""The poller: one EventBridge invocation per minute (Lambda handler `poller.handler`), or one local run
(`python poller.py --local out/`).

Each invocation has a ~50 s budget (settings.budget_seconds):
  * LIVE mode (a tracked match is live, or kicks off within prematch_minutes, or kicked off < 3 h ago
    and is not finished): three passes at 0 s, 20 s, 40 s. Each pass fetches the UAE-day scoreboard
    (one request, every competition) and the detail of each tracked live match, then writes live.json,
    day/<today>.json and match/<id>.json. Time left between passes goes to the chore queue.
  * IDLE mode: the chore queue only.
Chores (each has its own cadence, stored in state/poller.json): Arabic names (daily), day files,
competition pages (hourly; daily when dormant; every 2 min while that competition is live), team pages
for focus teams (daily), pre-match details (lineups), weather (3 h), last season (daily), player stat
lists (daily), derby head-to-heads (weekly), UAE players abroad (daily), ledger backfill, aggregates.

"Tracked" = the match's competition is in competitions.yaml, or the UAE national team plays.
Nothing is written when a fetch fails or its result does not validate (store.py keeps the last good
copy and health.json says what failed and since when).
"""
import json, os, sys, time, traceback
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import analytics as AN  # noqa: E402
import arabs as AR  # noqa: E402
import more as MO  # noqa: E402
import extra2 as X2  # noqa: E402
from compute import insights as IN  # noqa: E402
import config  # noqa: E402
from compute import winprob as WP  # noqa: E402
from compute import ics as ICS, magic as MAGIC, prayer as PRAYER, season as SEASON, weather as WEATHER  # noqa: E402
from compute.venues import Venues  # noqa: E402
from sources import schema as S  # noqa: E402
from sources.fotmob import FotMob  # noqa: E402
from sources.http import Http, FetchError  # noqa: E402
from sources.uaepl import UaePL  # noqa: E402
from store import Store, S3Backend, LocalBackend  # noqa: E402
from timeutil import now_utc, parse_utc, iso, uae_date, UAE  # noqa: E402

HTTP = Http()                     # module level: a warm Lambda container keeps the source cache
_NAMES = {"stamp": None, "data": None}
NATIONAL = 5789
NOT_READY_RETRY = 30             # minutes: an analytics step whose inputs were not ready runs again this soon
CONVERT_ERRORS = (FetchError, S.Invalid, KeyError, TypeError, ValueError, IndexError, AttributeError)


def _age_min(ts, now):
    t = parse_utc(ts) if isinstance(ts, str) else None
    return 1e9 if t is None else (now - t).total_seconds() / 60


class Poller:
    def __init__(self, store: Store, clock=time.monotonic, sleep=time.sleep, budget=None, now_fn=now_utc, role="poller"):
        """role "poller": the per-minute function (live passes + cadenced chores).
        role "analytics": the slower function (every 10 min): history, ratings, simulations, player
        tables and every other heavy computation. It reads the poller's state and never writes it:
        its own due marks, hashes and health live in state/analytics.json, state/hashes-analytics.json
        and v1/health-analytics.json, so the two functions cannot overwrite each other."""
        self.store, self.clock, self.sleep, self.now_fn, self.role = store, clock, sleep, now_fn, role
        self.cfg = config.settings()
        self.budget = budget if budget is not None else self.cfg.get("budget_seconds", 50)
        self.t0 = clock()
        self.deadline = None          # seconds since t0: chores between live passes must stop here
        self.comps = config.competitions()
        self.comp_ids = {c["id"] for c in self.comps}
        self.comp_by_id = {c["id"]: c for c in self.comps}
        self.venues = Venues()
        self.probs_comps = set(self.cfg.get("history_comps", [])) | set(AN.R.UAE_CLUB_COMPS)
        self.log = []
        self.requests_before = HTTP.network_calls
        self.calls_before = dict(HTTP.calls)
        self.ok_before, self.failed_before = dict(HTTP.ok), dict(HTTP.failed)
        self.mailer = None            # tests inject a fake; None = SES (_ses_send)

    # ------------------------------------------------------------------ helpers
    def now(self):
        return self.now_fn()

    def left(self):
        limit = self.budget if self.deadline is None else min(self.budget, self.deadline)
        return limit - (self.clock() - self.t0)

    def has_time(self, need=6):
        return self.left() > need

    def dues(self):
        return self.an_state.setdefault("due", {}) if self.role == "analytics" else self.st.setdefault("due", {})

    def due(self, key, minutes, sub=None):
        d = self.dues()
        k = f"{key}:{sub}" if sub is not None else key
        return _age_min(d.get(k), self.now()) >= minutes

    def mark(self, key, sub=None):
        k = f"{key}:{sub}" if sub is not None else key
        self.dues()[k] = iso(self.now())

    def note(self, msg):
        self.log.append(msg)
        print(msg)

    def tracked(self, m):
        return m.get("comp") in self.comp_ids or NATIONAL in ((m.get("home") or {}).get("id"), (m.get("away") or {}).get("id"))

    def fixtures(self, cid):
        """The competition's current normalized fixtures (this run's refresh, else the published file)."""
        if cid not in self.fixture_cache:
            self.fixture_cache[cid] = (self.store.get_json(f"comp/{cid}/fixtures.json") or {}).get("matches") or []
        return self.fixture_cache[cid]

    def cc_of(self, cid):
        return (self.st.get("comp_meta", {}).get(str(cid)) or {}).get("country")

    def comp_name_ar(self, cid):
        c = self.comp_by_id.get(cid)
        return c["name_ar"] if c else self.names["competitions"].get(str(cid))

    # ------------------------------------------------------------------ state
    def load(self):
        self.st = self.store.get_state("poller.json", {}) or {}
        self.an_state = self.store.get_state("analytics.json", {}) or {} if self.role == "analytics" else {}
        self.hashes_name = "hashes-analytics.json" if self.role == "analytics" else "hashes.json"
        self.health_name = "health-analytics.json" if self.role == "analytics" else "health.json"
        self.store.hashes.update(self.store.get_state(self.hashes_name, {}) or {})
        self.prev_health = self.store.get_json(self.health_name) or {}
        stamp = self.st.get("names_stamp")
        if _NAMES["data"] is None or _NAMES["stamp"] != stamp:
            _NAMES["data"] = self.store.get_state("names_ar.json", None) or {"teams": {}, "competitions": {}, "countries": {}}
            _NAMES["stamp"] = stamp
        self.names = _NAMES["data"]
        self.names["teams"].update(config.team_overrides())
        self.fm = FotMob(HTTP, self.names)
        self.up = UaePL(HTTP, self.names)
        self.ledgers = {}
        self.dirty_ledgers = set()
        self._aux, self._aux_sig = {}, {}
        for k in ("prev_season", "uaepl_fx", "squads"):      # moved out of poller.json (read every minute)
            if k in self.st and self.role == "poller":
                self.aux(k).update(self.st.pop(k))
        self.fixture_cache = {}

    def aux(self, name):
        """A side state file (state/<name>.json) loaded only by the chores that need it, saved if changed."""
        if name not in self._aux:
            self._aux[name] = self.store.get_state(f"{name}.json", {}) or {}
            self._aux_sig[name] = json.dumps(self._aux[name], sort_keys=True)
        return self._aux[name]

    def save(self):
        for name, obj in self._aux.items():
            if json.dumps(obj, sort_keys=True) != self._aux_sig.get(name):
                self.store.put_state(f"{name}.json", obj)
        if self.role == "analytics":
            self.store.put_state("analytics.json", self.an_state)
        else:
            for cid in self.dirty_ledgers:
                self.store.put_state(f"ledger/{cid}.json", self.ledgers[cid])
        sched = self.st.get("schedule", {})
        cutoff = self.now() - timedelta(days=3)
        for k in [k for k, v in sched.items() if (parse_utc(v.get("ko")) or self.now()) < cutoff]:
            del sched[k]
        det = self.st.get("detail_at", {})
        for k in [k for k, v in det.items() if _age_min(v, self.now()) > 60 * 24 * 10]:
            del det[k]
        if self.role == "poller":
            self.store.put_state("poller.json", self.st)
        self.store.put_state(self.hashes_name, self.store.hashes)
        health = dict(self.prev_health.get("items") or {})
        for k, v in self.store.health.items():
            prev = health.get(k) or {}
            if v["ok"]:
                v["last_ok"] = v["at"]
            else:
                v["last_ok"] = prev.get("last_ok") if prev.get("ok") is False else prev.get("at") if prev.get("ok") else prev.get("last_ok")
            health[k] = v
        bad = sorted(k for k, v in health.items() if not v.get("ok"))
        self.store.put_json(self.health_name, {
            "generated": iso(self.now()), "ok": not bad, "failing": bad, "items": health,
            "last_run": {"mode": self.mode, "seconds": round(self.clock() - self.t0, 1),
                         "requests": HTTP.network_calls - self.requests_before, "by_host": {h: n - self.calls_before.get(h, 0) for h, n in HTTP.calls.items() if n - self.calls_before.get(h, 0)},
                         "written": len(self.store.written), "unchanged": self.store.skipped_same,
                         "refused": self.store.refused[:20], "log": self.log[-30:]},
        }, cache="hot", heartbeat=True)

    # ------------------------------------------------------------------ enrichment
    def venue_for(self, m):
        key = str(m.get("id") or m.get("ext_id"))
        fv = self.st.get("venue_fm", {}).get(key)
        un = self.st.get("venue_up", {}).get(key)
        if not (m.get("comp") in config.focus_comps() or m.get("comp") in (9943, 11026)
                or NATIONAL in (m["home"]["id"], m["away"]["id"]) or fv or un):
            return None
        return self.venues.resolve(m, fv, un)

    def enrich(self, m, full=False):
        m = dict(m)
        m["comp_name_ar"] = self.comp_name_ar(m.get("comp"))
        if m.get("status") == S.SCHEDULED and m.get("comp") in self.probs_comps:
            pr = AN.probs_for(self, m)
            if pr:
                m["probs"] = pr
        v = self.venue_for(m)
        if v:
            vv = {k: v[k] for k in ("id", "name_ar", "name_en", "city", "emirate", "lat", "lon", "in_uae")}
            if full:
                vv["distance_km"] = self.venues.distances(v)
            m["venue"] = vv
            ko = parse_utc(m.get("kickoff_utc"))
            if v.get("in_uae") and ko and not m.get("time_tbd"):
                w = self.st.get("wx", {})
                sid = v.get("id") or f"{v['lat']:.3f},{v['lon']:.3f}"
                m["weather"] = WEATHER.at_kickoff(w.get("data", {}).get(sid), m["kickoff_utc"], w.get("at"))
                m["prayer"] = PRAYER.clashes(ko, v["lat"], v["lon"], m.get("periods"))
        return m

    def remember_schedule(self, matches):
        sched = self.st.setdefault("schedule", {})
        now = self.now()
        for m in matches:
            if not m.get("id") or not self.tracked(m):
                continue
            ko = parse_utc(m.get("kickoff_utc"))
            if not ko or ko < now - timedelta(days=2) or ko > now + timedelta(days=30):
                continue
            sched[str(m["id"])] = {"ko": m["kickoff_utc"], "comp": m["comp"], "status": m["status"],
                                   "h": m["home"]["id"], "a": m["away"]["id"]}

    # ------------------------------------------------------------------ live
    def live_window(self):
        now = self.now()
        pre = timedelta(minutes=self.cfg.get("prematch_minutes", 75))
        ids = []
        for mid, s in self.st.get("schedule", {}).items():
            ko = parse_utc(s.get("ko"))
            if not ko:
                continue
            if s["status"] in S.LIVE_STATUSES:
                if now - ko < timedelta(hours=4):
                    ids.append(mid)
            elif s["status"] == S.SCHEDULED and ko - pre <= now <= ko + timedelta(hours=3):
                ids.append(mid)
        return ids

    def day_file(self, ymd, kind="hot"):
        raw = self.fm.day_raw(ymd)
        if not raw.get("leagues"):
            raise S.Invalid(f"scoreboard {ymd} is empty")
        matches = [m for m in self.fm.day_from_raw(raw) if self.tracked(m)]
        self.remember_schedule(matches)
        for m in matches:   # periods for prayer windows come from the detail we already hold
            p = self.st.get("periods", {}).get(str(m["id"]))
            if p:
                m["periods"] = p
        out = [self.enrich(m) for m in sorted(matches, key=lambda m: (m["kickoff_utc"] or "", m["comp"]))]
        self.store.put_json(f"day/{ymd}.json", {"date": ymd, "tz": "Asia/Dubai", "generated": iso(self.now()),
                                                  "matches": out, "source": self.fm.name}, cache=kind)
        self.store.ok(f"day:{'today' if kind == 'hot' else 'other'}")
        return out

    def write_live(self, today):
        now = self.now()
        keep = []
        for m in today:
            ko = parse_utc(m.get("kickoff_utc"))
            if m["status"] in S.LIVE_STATUSES or (
                    ko and m["status"] == S.SCHEDULED and ko - now <= timedelta(hours=6)) or (
                    ko and m["status"] == S.FINISHED and now - ko <= timedelta(hours=4)):
                keep.append(m)
        self.store.put_json("live.json", {"generated": iso(now), "live": sum(m["status"] in S.LIVE_STATUSES for m in keep),
                                          "matches": keep}, cache="live", heartbeat=True)
        self.st["live_written_at"] = iso(now)

    def fetch_detail(self, mid, why):
        try:
            d = self.fm.match(mid)
            S.validate_detail(d)
        except CONVERT_ERRORS as e:
            self.store.fail(f"match:{why}", f"{mid}: {e}")
            return None
        mid = d["id"]
        self.st.setdefault("detail_at", {})[str(mid)] = iso(self.now())
        if d.get("venue"):
            self.st.setdefault("venue_fm", {})[str(mid)] = {k: d["venue"].get(k) for k in ("name", "city", "lat", "lon")}
        if d.get("periods"):
            self.st.setdefault("periods", {})[str(mid)] = d["periods"]
        full = self.enrich(d, full=True)
        if d.get("referee") and d["status"] == S.SCHEDULED and d.get("comp") in self.comp_ids:
            try:
                refs = self.store.get_json(f"comp/{d['comp']}/referees.json")
                full["referee_profile"] = IN.referee_profile(d["referee"].get("id"), d["referee"].get("name"), refs,
                                                             self.ledger(d["comp"])["matches"], d["home"]["id"], d["away"]["id"])
            except Exception as e:
                self.store.fail("referee-profile", f"{mid}: {e}")
        if d.get("comp") in self.comp_ids:
            try:
                hrows = [r for rs in self.aux(f"history/{d['comp']}").values() for r in rs]
                full["firsts"] = IN.firsts(d, self.ledger(d["comp"])["matches"], hrows)
            except Exception as e:
                self.store.fail("firsts", f"{mid}: {e}")
        if d["status"] in S.LIVE_STATUSES or str(mid) in self.st.get("ev_seen", {}):
            seen = self.st.setdefault("ev_seen", {}).setdefault(str(mid), {})
            stamp = iso(self.now())
            for e in full["events"]:
                e["first_seen"] = seen.setdefault(e["event_id"], stamp)
            if d["status"] == S.FINISHED:
                self.st["ev_seen"].pop(str(mid), None)     # the finished file keeps the stamps
        if d["status"] in S.LIVE_STATUSES or d["status"] == S.FINISHED:
            try:
                pm = AN.prematch(self, d)
                upto = None if d["status"] == S.FINISHED else _minute_num(d.get("minute"), d["status"])
                full["winprob"] = WP.curve(d["events"], pm[:3] if pm else None, upto)
                full["winprob_prematch"] = {"p": [round(x, 3) for x in pm[:3]], "source": pm[3]} if pm else {"p": list(WP.PRIOR), "source": "base-rates"}
            except Exception as e:
                self.store.fail("winprob", f"{mid}: {e}")
        full["coverage_events"] = coverage_events(d)
        if d["status"] == S.FINISHED:
            self.plan_repoll(d, full, why)
        cache = "hot" if d["status"] in S.LIVE_STATUSES or self._near_kickoff(d) else "static" if d["status"] == S.FINISHED else "warm"
        self.store.put_json(f"match/{mid}.json", full, cache=cache, validate=S.validate_detail, health_key=f"match:{why}")
        self.store.ok(f"match:{why}")
        s = self.st.setdefault("schedule", {}).get(str(mid))
        if s:
            s["status"] = d["status"]
        if d["status"] == S.FINISHED and d.get("comp") in self.comp_ids:
            self.add_ledger(d)
        return d

    def _near_kickoff(self, d):
        """Scheduled but within kickoff - prematch_minutes .. kickoff + 15 min: cache like a live file (20 s), so the
        switch to live is not hidden behind a 5-minute 'warm' copy (audit W1.1b)."""
        ko = parse_utc(d.get("kickoff_utc"))
        if d.get("status") != S.SCHEDULED or not ko:
            return False
        return ko - timedelta(minutes=self.cfg.get("prematch_minutes", 75)) <= self.now() <= ko + timedelta(minutes=15)

    # ------------------------------------------------------------------ thin-coverage re-polls after full time
    def plan_repoll(self, d, full, why):
        """Finished match whose feed lacks subs or cards: fetch it again REPOLL_MINUTES after full time (FotMob
        sometimes fills events in later), and keep any event an earlier copy had that the new one lacks."""
        mid = str(d["id"])
        rp = self.st.setdefault("repoll", {})
        cov = full["coverage_events"]
        if why == "repoll":
            prev = self.store.get_json(f"match/{mid}.json") or {}
            seen = {e.get("event_id"): e.get("first_seen") for e in prev.get("events") or [] if e.get("first_seen")}
            for e in full.get("events") or []:
                if e.get("event_id") in seen:
                    e["first_seen"] = seen[e["event_id"]]       # keep the live stamps of events we already had
            have = {e.get("event_id") for e in full.get("events") or []}
            kept = [e for e in prev.get("events") or [] if e.get("event_id") and e["event_id"] not in have]
            if kept:
                full["events"] = sorted(full["events"] + kept, key=lambda e: (e.get("minute") or 0, e.get("added") or 0))
            new = len(have - {e.get("event_id") for e in prev.get("events") or []})
            if new:
                self.note(f"repoll {mid}: {new} new events from the source")
            if cov["subs"] and cov["cards"]:
                rp.pop(mid, None)           # the feed is complete now
            return
        if mid in rp or cov["subs"] and cov["cards"]:
            return
        ended = ((d.get("periods") or {}).get("gameEnded")) or iso(self.now())
        if _age_min(ended, self.now()) <= 6 * 60:          # only matches that just ended, not the backfill
            rp[mid] = {"ft": ended, "done": []}

    def repolls(self):
        rp = self.st.get("repoll") or {}
        for mid, r in list(rp.items()):
            if not self.has_time(8):
                return
            age = _age_min(r["ft"], self.now())
            todo = [x for x in REPOLL_MINUTES if x <= age and x not in r["done"]]
            if todo:
                r["done"] += todo
                self.fetch_detail(int(mid), "repoll")
            if len(r["done"]) >= len(REPOLL_MINUTES) or age > REPOLL_MINUTES[-1] + 120:
                rp.pop(mid, None)

    def live_pass(self, n):
        now = self.now()
        today = uae_date(now)
        days = [today]
        if now.astimezone(UAE).hour < 4:
            days.insert(0, uae_date(now - timedelta(hours=6)))
        matches = []
        for ymd in days:
            try:
                matches += self.day_file(ymd, "hot")
            except CONVERT_ERRORS as e:
                self.store.fail("day:today", e)
        if not matches:
            return
        self.write_live([m for m in matches])
        prev_live = set(self.st.get("live_ids", []))
        pre = timedelta(minutes=self.cfg.get("prematch_minutes", 75))
        now_live = set()
        for m in matches:
            mid = str(m["id"])
            ko = parse_utc(m.get("kickoff_utc"))
            if m["status"] in S.LIVE_STATUSES:
                now_live.add(mid)
                self.fetch_detail(m["id"], "live")
            elif m["status"] == S.FINISHED and mid in prev_live:
                self.fetch_detail(m["id"], "final")
                self.st.setdefault("due", {})[f"comp:{m['comp']}"] = None     # refresh its table next
            elif m["status"] == S.SCHEDULED and ko and ko - pre <= now <= ko and _age_min(self.st.get("detail_at", {}).get(mid), now) >= 2:
                self.fetch_detail(m["id"], "prematch")
            if not self.has_time(3):
                break
        for cid in {m["comp"] for m in matches if m["status"] in S.LIVE_STATUSES and m["comp"] in self.comp_ids}:
            if self.has_time(3):
                try:
                    AN.live_table(self, cid, [m for m in matches if m["comp"] == cid and m["status"] in S.LIVE_STATUSES])
                except Exception as e:
                    self.store.fail(f"live-table:{cid}", e)
        self.st["live_ids"] = sorted(now_live | (prev_live & {str(m["id"]) for m in matches if m["status"] in S.LIVE_STATUSES}))
        self.mark("day_today")

    # ------------------------------------------------------------------ competitions
    def comp_due_minutes(self, cid):
        s = self.st.get("comp_live", {})
        if cid in {v["comp"] for v in self.st.get("schedule", {}).values() if v["status"] in S.LIVE_STATUSES}:
            return 2
        dormant = self.st.get("dormant", {}).get(str(cid))
        return self.cfg.get("heavy_dormant_minutes", 1440) if dormant else self.cfg.get("heavy_minutes", 60)

    def refresh_comp(self, comp):
        cid = comp["id"]
        live_now = self.comp_due_minutes(cid) == 2
        raw, source, data = None, "fotmob", None
        try:
            raw = self.fm.league_raw(cid, comp.get("season"))
            data = self.fm.competition_from_raw(comp, raw, with_leaders=not live_now)
            if not data["matches"] and not data["standings"]:
                raise S.Invalid(f"competition {cid} returned no matches and no table")
            self.store.ok(f"comp:{cid}:fotmob")
        except CONVERT_ERRORS as e:
            self.store.fail(f"comp:{cid}:fotmob", e)
            if comp.get("uaepl"):
                try:
                    data = self.up.competition(comp)
                    source = "uaepl"
                    self.store.ok(f"comp:{cid}:uaepl-fallback")
                    self.note(f"comp {cid}: FotMob failed, used uaepl.ae")
                except CONVERT_ERRORS as e2:
                    self.store.fail(f"comp:{cid}:uaepl-fallback", e2)
        if data is None:
            return
        season = data["competition"].get("season")
        matches = data["matches"]
        if comp.get("uaepl") and source == "fotmob":
            matches = self.merge_uaepl(comp, matches)
        self.remember_schedule(matches)
        now = self.now()
        kos = [parse_utc(m["kickoff_utc"]) for m in matches if m.get("kickoff_utc")]
        dormant = not any(now - timedelta(days=3) <= k <= now + timedelta(days=30) for k in kos if k)
        self.st.setdefault("dormant", {})[str(cid)] = dormant
        for t in data["teams"]:
            self.st.setdefault("team_comps", {}).setdefault(str(t["id"]), [])
            if cid not in self.st["team_comps"][str(t["id"])]:
                self.st["team_comps"][str(t["id"])].append(cid)
            self.st.setdefault("teams", {})[str(t["id"])] = [t["name"], t.get("name_ar")]
        # fixtures
        enriched = [self.enrich(m) for m in matches]
        fx = {"comp": cid, "season": season, "generated": iso(now), "source": source,
              "next_round": data["competition"].get("next_round"), "matches": enriched,
              "note": "FotMob fixtures; entries with id=null and ext_id uaepl:* are official uaepl.ae fixtures FotMob has not published yet"
              if comp.get("uaepl") else None}
        self.fixture_cache[cid] = enriched
        self.store.put_json(f"comp/{cid}/fixtures.json", fx, cache="warm",
                            validate=lambda o: S.validate_matches([m for m in o["matches"] if m.get("id")] or o["matches"], 1),
                            health_key=f"file:comp/{cid}/fixtures")
        # standings (+ magic numbers, last season at the same point)
        st = data["standings"]
        if st:
            if comp.get("kind") == "league" and comp.get("magic", True):
                st["magic"] = MAGIC.magic_numbers(st, comp.get("matches_per_team"))
                prev = self.aux("prev_season").get(str(cid))
                if prev and not st.get("composite"):
                    played = {r["team"]["id"]: r["played"] or 0 for r in st["groups"][0]["rows"]}
                    ls = SEASON.last_season_same_round(prev["matches"], played)
                    for r in st["groups"][0]["rows"]:
                        r["last_season_same_round"] = ls.get(str(r["team"]["id"]))
                    st["last_season"] = prev.get("season")
            st["generated"] = iso(now)
            self.store.put_json(f"comp/{cid}/standings.json", st, cache="warm", validate=S.validate_standings,
                                health_key=f"file:comp/{cid}/standings")
            if cid in (10197, 10609, 290, 329):
                self.qualifying_section(comp, st, matches)
            self.detect_draw(cid, st)
            try:
                AN.comp_tables(self, cid, st, matches, comp.get("kind"))
            except Exception as e:
                self.store.fail(f"tables:{cid}", e)
        if data.get("leaders"):
            self.store.put_json(f"comp/{cid}/stats.json", {**data["leaders"], "generated": iso(now)}, cache="warm",
                                validate=S.validate_leaders, health_key=f"file:comp/{cid}/stats")
        if raw is not None and not live_now:
            tr = self.fm.league_transfers_from_raw(cid, raw)
            if tr:
                self.store.put_json(f"comp/{cid}/transfers.json", {**tr, "generated": iso(now)}, cache="static")
        self.comp_meta(comp, data, matches, source)
        self.write_team_calendars(cid)
        self.mark("comp", cid)

    def detect_draw(self, cid, st):
        """Item 321: record when a competition's groups or knockout pairings first appear or change."""
        groups = sorted([g.get("name") or "", sorted(r["team"]["id"] for r in g["rows"] if r["team"]["id"])] for g in st.get("groups") or [])
        ties = sorted(sorted(x for x in (t["home"]["id"], t["away"]["id"]) if x)
                      for rd in st.get("bracket") or [] for t in rd["ties"] if not t.get("tbd"))
        sig = json.dumps([groups, ties], sort_keys=True)
        prev = self.st.setdefault("draw_sig", {}).get(str(cid))
        base = self.st.setdefault("draw_base", {})
        if prev == sig and str(cid) in base:
            return
        self.st["draw_sig"][str(cid)] = sig
        log = self.st.setdefault("draws", {}).setdefault(str(cid), [])
        if prev is None or str(cid) not in base:
            base[str(cid)] = iso(self.now())      # first sight: the baseline, not a draw (its date is unknown)
        if prev is not None and prev != sig:
            log.append({"at": iso(self.now()), "groups": [{"name": n, "teams": t} for n, t in groups], "ties": ties})
            del log[:-10]
            self.st.setdefault("draw_trigger", {})[str(cid)] = iso(self.now())
        if not log and (not (groups or ties) or (self.comp_by_id.get(cid) or {}).get("kind") == "league"):
            return                      # no draw events: a baseline file only for cups and group tournaments
        self.store.put_json(f"draws/{cid}.json", {"comp": cid, "events": log, "baseline_at": base[str(cid)],
                                                  "current": {"groups": [{"name": n, "teams": t} for n, t in groups], "ties": ties},
                                                  "note": "each event = the groups/pairings as they appeared when they changed; "
                                                          "current = what the source shows now; baseline_at = when we first saw it "
                                                          "(a draw made before that is not an event)"},
                            cache="warm")

    def merge_uaepl(self, comp, matches):
        """Add official stadium names and the not-yet-dated rounds from uaepl.ae (cached daily)."""
        cid = comp["id"]
        cache = self.aux("uaepl_fx")
        if self.due("uaepl", 1440, cid) and self.has_time(12):
            try:
                ul = self.up.fixtures(comp)
                if len(ul) < 2:
                    raise S.Invalid("uaepl fixtures empty")
                cache[str(cid)] = ul
                self.mark("uaepl", cid)
                self.store.ok(f"uaepl:{cid}")
            except CONVERT_ERRORS as e:
                self.store.fail(f"uaepl:{cid}", e)
        ul = cache.get(str(cid)) or []
        if not ul:
            return matches
        by_pair = {(m["home"]["id"], m["away"]["id"]): m for m in matches}
        vu = self.st.setdefault("venue_up", {})
        extra = []
        for u in ul:
            key = (u["home"]["id"], u["away"]["id"])
            fm = by_pair.get(key)
            if fm:
                if u.get("venue_name"):
                    vu[str(fm["id"])] = u["venue_name"]
                if fm.get("kickoff_utc") and u.get("kickoff_utc") and fm["kickoff_utc"] != u["kickoff_utc"]:
                    fm["kickoff_official_uaepl"] = u["kickoff_utc"]
            elif u["home"]["id"] and u["away"]["id"]:
                if u.get("venue_name"):
                    vu[u["ext_id"]] = u["venue_name"]
                extra.append(u)
        return matches + extra

    def comp_meta(self, comp, data, matches, source):
        now = self.now()
        nxt = min((m["kickoff_utc"] for m in matches if m["status"] == S.SCHEDULED and m.get("kickoff_utc")
                   and parse_utc(m["kickoff_utc"]) > now), default=None)
        self.st.setdefault("comp_meta", {})[str(comp["id"])] = {
            "season": data["competition"].get("season"), "name": data["competition"].get("name"),
            "has_table": bool(data.get("standings")), "matches": len(matches),
            "finished": sum(m["status"] == S.FINISHED for m in matches), "next_kickoff": nxt,
            "source": source, "updated": iso(now), "country": data["competition"].get("country")}

    def qualifying_section(self, comp, st, matches):
        """National-team scenario inputs: the UAE's group table and that group's remaining fixtures."""
        grp = next((g for g in st["groups"] if any(r["team"]["id"] == NATIONAL for r in g["rows"])), None)
        q = self.st.setdefault("qualifying", {})
        if not grp:
            q[str(comp["id"])] = {"comp": comp["id"], "name_ar": comp["name_ar"], "season": st.get("season"), "uae_in_group": False}
        else:
            ids = {r["team"]["id"] for r in grp["rows"]}
            rem = [m for m in matches if m["status"] in (S.SCHEDULED, S.POSTPONED) and m["home"]["id"] in ids and m["away"]["id"] in ids]
            played = [m for m in matches if m["status"] == S.FINISHED and m["home"]["id"] in ids and m["away"]["id"] in ids]
            q[str(comp["id"])] = {"comp": comp["id"], "name_ar": comp["name_ar"], "season": st.get("season"),
                                  "uae_in_group": True, "group": grp["name"], "table": grp["rows"],
                                  "legend": st.get("legend"), "remaining": rem, "played": played,
                                  "finished": not rem}
        self.store.put_json(f"national/{NATIONAL}/qualifying.json", {
            "team": NATIONAL, "generated": iso(self.now()), "competitions": list(q.values()),
            "note": "inputs for qualification scenarios: group table in source order + the group's remaining fixtures. "
                    "World Cup qualifying (AFC) 2023/25 is finished and the next cycle is not published yet."}, cache="warm")

    # ------------------------------------------------------------------ teams
    def team_matches(self, tid):
        out = []
        for cid in self.st.get("team_comps", {}).get(str(tid), []):
            fx = self.fixture_cache.get(cid)
            if fx is None:
                doc = self.store.get_json(f"comp/{cid}/fixtures.json") or {}
                fx = self.fixture_cache[cid] = doc.get("matches") or []
            out += [m for m in fx if tid in (m["home"]["id"], m["away"]["id"])]
        return out

    def write_team_calendars(self, cid):
        seq = self.st.setdefault("ics_seq", {})
        focus = set(config.focus_teams())
        for tid_s, comps in self.st.get("team_comps", {}).items():
            if cid not in comps or int(tid_s) in focus or not self.has_time(4):
                continue
            tid = int(tid_s)
            ms = self.team_matches(tid)
            if not ms:
                continue
            self.write_ics(tid, ms, seq)

    def write_ics(self, tid, matches, seq):
        name, name_ar = (self.st.get("teams", {}).get(str(tid)) or [str(tid), None])
        seqs = ICS.bump_sequences(matches, seq)
        venues = {str(m.get("id") or m.get("ext_id")): (m.get("venue") or {}).get("name_ar") or (m.get("venue") or {}).get("name_en")
                  for m in matches if m.get("venue")}
        names = {c["id"]: c["name_ar"] for c in self.comps}
        text = ICS.team_calendar({"id": tid, "name": name, "name_ar": name_ar or self.names["teams"].get(str(tid))},
                                 matches, names, seqs, venues)
        self.store.put_text(f"team/{tid}.ics", text, "text/calendar; charset=utf-8", cache="static")

    def refresh_team(self, tid):
        try:
            t = self.fm.team(tid)
            S.validate_team(t)
        except CONVERT_ERRORS as e:
            self.store.fail(f"team:{tid}", e)
            return
        t["fixtures"] = [self.enrich(m) for m in t["fixtures"]]
        if t.get("national"):
            uae_clubs = {int(k) for k, v in self.st.get("team_comps", {}).items() if 538 in v or 11027 in v}
            for g in t["squad"]:
                for p in g["players"]:
                    p["abroad"] = bool(p.get("club_id")) and p["club_id"] not in uae_clubs
        t["country_info"] = self.team_country(tid)
        self.store.put_json(f"team/{tid}.json", {**t, "generated": iso(self.now())}, cache="static",
                            validate=S.validate_team, health_key=f"team:{tid}")
        self.store.ok(f"team:{tid}")
        self.aux("squads")[str(tid)] = t["squad"]
        loans = [x for x in ((t.get("transfers") or {}).get("out") or []) if x.get("loan")]
        if loans:
            self.aux("loans_out")[str(tid)] = loans

        self.st.setdefault("teams", {})[str(tid)] = [t["name"], t.get("name_ar")]
        self.write_ics(tid, t["fixtures"], self.st.setdefault("ics_seq", {}))
        self.mark("team", tid)

    # ------------------------------------------------------------------ ledger and aggregates
    def ledger(self, cid):
        if cid not in self.ledgers:
            self.ledgers[cid] = self.store.get_state(f"ledger/{cid}.json", None) or {"season": None, "matches": {}}
        return self.ledgers[cid]

    def add_ledger(self, d):
        cid = d["comp"]
        L = self.ledger(cid)
        season = (self.st.get("comp_meta", {}).get(str(cid)) or {}).get("season")
        if season and L.get("season") and L["season"] != season:
            L.update({"season": season, "matches": {}})
        L["season"] = L.get("season") or season
        L["matches"][str(d["id"])] = SEASON.ledger_entry(d)
        self.dirty_ledgers.add(cid)
        self.st.setdefault("ledger_changed", {})[str(cid)] = iso(self.now())

    def backfill(self, limit):
        """Fetch final details of finished matches not yet in the ledger, focus competitions first."""
        n = 0
        order = config.focus_comps() + [c["id"] for c in self.comps if c["id"] not in config.focus_comps()]
        for cid in order:
            if self.st.get("dormant", {}).get(str(cid)) is not False:
                continue            # only competitions with a current season in play (and seen at least once)
            fx = self.fixture_cache.get(cid)
            if fx is None:
                fx = self.fixture_cache[cid] = (self.store.get_json(f"comp/{cid}/fixtures.json") or {}).get("matches") or []
            have = self.ledger(cid)["matches"]
            for m in sorted(fx, key=lambda m: m.get("kickoff_utc") or "", reverse=True):
                if m.get("id") and m["status"] == S.FINISHED and (have.get(str(m["id"])) or {}).get("v", 1) < SEASON.LEDGER_VERSION:
                    if n >= limit or not self.has_time(5):
                        return n
                    self.fetch_detail(m["id"], "backfill")
                    n += 1
        return n

    def aggregates(self, cid):
        L = self.ledger(cid)["matches"]
        if not L:
            return
        now = iso(self.now())
        base = {"comp": cid, "season": self.ledger(cid).get("season"), "generated": now, "matches_counted": len(L)}
        refs = SEASON.referees(L, self.cc_of(cid))
        self.store.put_json(f"comp/{cid}/referees.json", {**base, **refs, "available": bool(refs.get("referees")),
                                                          **({} if refs.get("referees") else
                                                             {"reason": "FotMob names no referee for this competition's matches"})},
                            cache="static")
        self.store.put_json(f"comp/{cid}/halftime.json", {**base, **SEASON.ht_table(L)}, cache="static")
        self.store.put_json(f"comp/{cid}/goal-bands.json", {**base, **SEASON.goal_bands(L)}, cache="static")
        xt = SEASON.xg_table(L)
        if xt.get("available"):        # no source xG: the analytics function writes the danger-index proxy table
            self.store.put_json(f"comp/{cid}/xg.json", {**base, **xt, "proxy": False}, cache="static")
        sh = SEASON.shots(L)
        self.store.put_json(f"comp/{cid}/shots.json", {**base, **sh}, cache="static")
        try:
            AN.ledger_extras(self, cid)
        except Exception as e:
            self.store.fail(f"ledger-extras:{cid}", e)
        self.mark("agg", cid)

    def player_tables(self, cid):
        comp = self.comp_by_id[cid]
        try:
            raw = self.fm.league_raw(cid, comp.get("season"))
            lists = self.fm.player_stat_lists(raw)
            if not lists:
                self.store.ok(f"players:{cid}", note="FotMob publishes no per-player season lists for this league")
                self.mark("players", cid)
                return
        except CONVERT_ERRORS as e:
            self.store.fail(f"players:{cid}", e)
            return
        table = SEASON.player_table(lists)
        country = (raw.get("details") or {}).get("country")
        self.store.put_json(f"comp/{cid}/players.json", {"comp": cid, "generated": iso(self.now()), **table}, cache="static")
        table["_lists"] = {"rating": (lists.get("rating") or {}).get("entries") or []}
        try:
            AN.player_extras(self, cid, table, raw)
        except Exception as e:
            self.store.fail(f"player-extras:{cid}", e)
        squads = [{"national": False, "squad": sq} for tid, sq in self.aux("squads").items() if int(tid) != NATIONAL]
        nat = SEASON.nationality_map([self.ledger(cid)["matches"]], squads)
        if country and country != "INT":
            self.store.put_json(f"comp/{cid}/foreigners.json", {"comp": cid, "generated": iso(self.now()),
                                                                **SEASON.foreigners(table, nat, country)}, cache="static")
        self.store.ok(f"players:{cid}")
        self.mark("players", cid)

    def prev_season(self, comp):
        cid = comp["id"]
        try:
            raw = self.fm.league_raw(cid)
            seasons = raw.get("allAvailableSeasons") or []
            cur = (raw.get("details") or {}).get("selectedSeason")
            prev = seasons[seasons.index(cur) + 1] if cur in seasons and seasons.index(cur) + 1 < len(seasons) else None
            if not prev:
                raise S.Invalid("no previous season")
            praw = self.fm.league_raw(cid, prev)
            pdata = self.fm.competition_from_raw({"id": cid}, praw, with_leaders=False)
            if not pdata["matches"]:
                raise S.Invalid("previous season has no matches")
        except CONVERT_ERRORS as e:
            self.store.fail(f"prev-season:{cid}", e)
            self.mark("prev", cid)
            return
        slim = [{"id": m["id"], "kickoff_utc": m["kickoff_utc"], "status": m["status"], "score": m["score"],
                 "home": {"id": m["home"]["id"]}, "away": {"id": m["away"]["id"]}} for m in pdata["matches"]]
        self.aux("prev_season")[str(cid)] = {"season": prev, "matches": slim}
        self.store.ok(f"prev-season:{cid}")
        self.mark("prev", cid)

    def derbies(self, limit):
        """Head-to-head history for every pair of current UAE Pro League clubs, via any match between them."""
        clubs = sorted(int(k) for k, v in self.st.get("team_comps", {}).items() if 538 in v)
        if len(clubs) < 2:
            return
        pairs = [(a, b) for i, a in enumerate(clubs) for b in clubs[i + 1:]]
        known = {}
        for m in (self.fixture_cache.get(538) or []) + (self.aux("prev_season").get("538") or {}).get("matches", []):
            if m.get("id"):
                known.setdefault(tuple(sorted((m["home"]["id"], m["away"]["id"]))), m["id"])
        n = 0
        for a, b in pairs:
            if n >= limit or not self.has_time(5):
                break
            if not self.due("h2h", 7 * 1440, f"{a}-{b}"):
                continue
            mid = known.get((a, b))
            if not mid:
                continue
            try:
                d = self.fm.match(mid)
            except CONVERT_ERRORS as e:
                self.store.fail("h2h", e)
                continue
            h = d.get("h2h")
            n += 1
            self.mark("h2h", f"{a}-{b}")
            if not h:
                continue
            per = {str(a): 0, str(b): 0, "draws": 0}
            for x in h["matches"]:
                sc = x.get("score")
                if not sc:
                    continue
                if sc["home"] == sc["away"]:
                    per["draws"] += 1
                else:
                    w = x["home"]["id"] if sc["home"] > sc["away"] else x["away"]["id"]
                    if str(w) in per:
                        per[str(w)] += 1
            self.store.put_json(f"h2h/{a}-{b}.json", {"teams": [a, b], "generated": iso(self.now()),
                                                     "wins": per, "matches": h["matches"], "via_match": mid,
                                                     "note": "all meetings FotMob lists for this pair (its depth, all competitions)"},
                                cache="static")
            self.st.setdefault("h2h_index", {})[f"{a}-{b}"] = len(h["matches"])
        if self.st.get("h2h_index"):
            self.store.put_json("h2h/index.json", {"generated": iso(self.now()), "pairs": self.st["h2h_index"]}, cache="static")

    def uae_abroad(self, limit=12):
        """UAE nationals at clubs outside the UAE: national squad + UAE-coded players in other leagues' lineups."""
        uae_clubs = {int(k) for k, v in self.st.get("team_comps", {}).items() if 538 in v or 11027 in v}
        cands = {}
        for g in self.aux("squads").get(str(NATIONAL)) or []:
            for p in g["players"]:
                if p.get("club_id") and p["club_id"] not in uae_clubs:
                    cands[str(p["id"])] = p["name"]
        for cid in self.comp_ids - set(config.focus_comps()):
            if self.st.get("dormant", {}).get(str(cid)) is not False:
                continue
            for e in self.ledger(cid)["matches"].values():
                for pid, pl in (e.get("players") or {}).items():
                    name, cc, tid = pl[:3]
                    if cc == "UAE" and tid not in uae_clubs and tid != NATIONAL:
                        cands[pid] = name
        known = self.st.setdefault("abroad", {})
        n = 0
        for pid in sorted(cands):
            if n >= limit or not self.has_time(4):
                break
            if not self.due("abroad", 1440, pid):
                continue
            try:
                p = self.fm.player(int(pid))
                n += 1
                self.mark("abroad", pid)
                if p.get("country") == "UAE" and p.get("team") and p["team"]["id"] not in uae_clubs:
                    known[pid] = p
                else:
                    known.pop(pid, None)
            except CONVERT_ERRORS as e:
                self.store.fail("abroad", e)
        self.store.put_json("national/uae-abroad.json", {
            "generated": iso(self.now()), "players": sorted(known.values(), key=lambda p: p["name"] or ""),
            "note": "UAE nationals whose club is outside the UAE Pro League: from the national-team squad and every "
                    "lineup we store; season stats are the player's main league on FotMob"}, cache="static")
        self.store.ok("abroad")

    # ------------------------------------------------------------------ weather, names, index
    def refresh_weather(self):
        pts = {}
        now = self.now()
        horizon = now + timedelta(days=16)
        for mid, s in self.st.get("schedule", {}).items():
            ko = parse_utc(s.get("ko"))
            if not ko or not (now - timedelta(hours=3) <= ko <= horizon):
                continue
            m = {"id": int(mid), "comp": s["comp"], "home": {"id": s["h"]}, "away": {"id": s["a"]}}
            v = self.venue_for(m)
            if v and v.get("in_uae"):
                sid = v.get("id") or f"{v['lat']:.3f},{v['lon']:.3f}"
                pts[sid] = (sid, v["lat"], v["lon"])
        try:
            data = WEATHER.fetch(HTTP, list(pts.values()))
            if pts and not data:
                raise S.Invalid("open-meteo returned nothing")
            self.st["wx"] = {"at": iso(now), "data": data}
            self.store.ok("weather:open-meteo", stadiums=len(data))
        except CONVERT_ERRORS as e:
            self.store.fail("weather:open-meteo", e)
        self.mark("weather")

    def refresh_names(self):
        try:
            nm = self.fm.arabic_names()
        except CONVERT_ERRORS as e:
            self.store.fail("names:fotmob", e)
            self.mark("names")
            return
        slim = {"teams": nm["teams"], "competitions": nm["competitions"], "countries": nm["countries"]}
        self.store.put_state("names_ar.json", slim)
        stamp = iso(self.now())
        self.st["names_stamp"] = stamp
        _NAMES.update(stamp=stamp, data=slim)
        self.names = slim
        self.names["teams"].update(config.team_overrides())
        self.fm.names = self.up.names = self.names
        self.store.ok("names:fotmob", teams=len(nm["teams"]))
        self.mark("names")

    def write_index(self):
        meta = self.st.get("comp_meta", {})
        comps = []
        for c in self.comps:
            m = meta.get(str(c["id"])) or {}
            base = f"comp/{c['id']}/"
            files = {"fixtures": base + "fixtures.json"}
            if m.get("has_table"):
                files["standings"] = base + "standings.json"
            comps.append({"id": c["id"], "key": c["key"], "name_ar": c["name_ar"], "name_en": c["name_en"],
                          "country": c.get("country"), "region": c.get("region"),
                          "name_ar_source": self.names["competitions"].get(str(c["id"])), "kind": c["kind"],
                          "scope": c["scope"], "season": m.get("season"), "matches": m.get("matches"),
                          "finished": m.get("finished"), "next_kickoff": m.get("next_kickoff"),
                          "dormant": self.st.get("dormant", {}).get(str(c["id"])), "source": m.get("source"),
                          "updated": m.get("updated"), "files": files})
        self.store.put_json("index.json", {
            "schema": S.SCHEMA_VERSION, "generated": iso(self.now()), "competitions": comps,
            "focus_teams": config.focus_teams(), "live_now": len(self.st.get("live_ids", [])),
            "files": {"live": "live.json", "day": "day/YYYYMMDD.json (UAE date)", "match": "match/{id}.json",
                      "team": "team/{id}.json, team/{id}.ics", "teams": "teams.json", "health": "health.json",
                      "national": ["national/5789/qualifying.json", "national/uae-abroad.json", "national/5789/fifa.json"],
                      "h2h": "h2h/index.json", "health_analytics": "health-analytics.json",
                      "ratings": ["ratings/uae-clubs.json", "ratings/team/{id}.json", "ratings/national.json"],
                      "archive": "archive/index.json", "leagues": "leagues/compare.json", "player": "player/{id}.json",
                      "comp_extras": ["sim", "scenarios", "live-table", "bump", "tournament-sim", "facts", "watch", "pressure",
                                      "fatigue", "coaches", "fortress", "clutch", "minute-clock", "lineup-ages", "rotation",
                                      "team-of-round", "style", "cards", "improved", "young-uae", "similar", "records",
                                      "alltime", "loans", "referees", "halftime", "goal-bands", "xg", "shots", "players",
                                      "foreigners", "transfers"]},
        }, cache="hot")
        teams = {k: {"name": v[0], "name_ar": v[1] or self.names["teams"].get(k), "logo": S.LOGO.format(id=k),
                     "comps": self.st.get("team_comps", {}).get(k, []), "country": self.team_country(k)}
                 for k, v in self.st.get("teams", {}).items()}
        self.store.put_json("national/countries.json", {
            "countries": [{**{k: c.get(k) for k in ("iso2", "name_ar", "name_en", "arab")},
                           "team": c.get("fotmob_team"), "competitions": [x["id"] for x in self.comps
                                                                           if (x.get("country") or {}).get("iso2") == c["iso2"]]}
                          for c in config.countries()],
            "note": "ISO 3166-1 alpha-2 (England GB-ENG); team = FotMob national-team id"}, cache="static")
        if teams:
            self.store.put_json("teams.json", {"generated": iso(self.now()), "teams": teams}, cache="static")

    # ------------------------------------------------------------------ main
    def chores(self, live):
        """Cadenced work in priority order; each step checks the remaining budget."""
        c = self.cfg
        if self.due("names", c.get("names_minutes", 1440)) and self.has_time(15):
            self.refresh_names()
        now = self.now()
        if not live and self.due("day_today", c.get("day_idle_minutes", 10)) and self.has_time(8):
            try:
                self.write_live(self.day_file(uae_date(now), "hot"))
                self.mark("day_today")
            except CONVERT_ERRORS as e:
                self.store.fail("day:today", e)
        for off, key in ((1, "day_tomorrow"), (-1, "day_yesterday")):
            if self.due(key, 60) and self.has_time(8):
                try:
                    self.day_file(uae_date(now + timedelta(days=off)), "warm")
                except CONVERT_ERRORS as e:
                    self.store.fail("day:other", e)
                self.mark(key)
        for comp in self.comps:
            if not self.has_time(10):
                break
            if self.due("comp", self.comp_due_minutes(comp["id"]), comp["id"]):
                self.refresh_comp(comp)
        for tid in self.focus_team_ids():
            if not self.has_time(10):
                break
            if self.due("team", c.get("squads_minutes", 1440), tid):
                self.refresh_team(tid)
        # upcoming UAE-relevant details (injuries, venue) once an hour for the next 48 h
        for mid, s in sorted(self.st.get("schedule", {}).items(), key=lambda kv: kv[1]["ko"] or ""):
            if not self.has_time(10):
                break
            ko = parse_utc(s["ko"])
            if s["status"] != S.SCHEDULED or not ko or ko - now > timedelta(hours=48) or ko < now:
                continue
            if (s["comp"] in config.focus_comps() or NATIONAL in (s["h"], s["a"])) and \
                    _age_min(self.st.get("detail_at", {}).get(mid), now) >= 60:
                self.fetch_detail(int(mid), "upcoming")
        if self.due("weather", c.get("weather_minutes", 180)) and self.has_time(8):
            self.refresh_weather()
        for comp in self.comps:
            if not self.has_time(12):
                break
            if comp.get("kind") == "league" and self.due("prev", 1440, comp["id"]):
                self.prev_season(comp)
        self.repolls()
        if self.has_time(8):
            self.backfill(2 if live else c.get("backfill_per_run", 6))
        if not live and self.has_time(8):
            self.derbies(2)
        if not live and self.due("abroad_run", 1440) and self.has_time(10):
            self.uae_abroad()
            self.mark("abroad_run")
        for cid_s, changed in list(self.st.get("ledger_changed", {}).items()):
            if not self.has_time(5):
                break
            if _age_min(self.st.get("due", {}).get(f"agg:{cid_s}"), now) >= 30 and \
                    (self.st.get("due", {}).get(f"agg:{cid_s}") or "") < changed:
                self.aggregates(int(cid_s))

    def insights_due(self):
        for cid in AN.analytics_leagues() + [c for c in MO.CUPS if c in self.comp_ids]:
            if self.has_time(15) and self.due("insights", 120, cid):
                try:
                    MO.comp_insights(self, cid)
                except Exception as e:
                    self.store.fail(f"insights:{cid}", f"{type(e).__name__}: {e}")
                    self.mark("insights", cid)

    def draw_triggers(self):
        done = self.an_state.setdefault("draw_done", {})
        for cid, at in (self.st.get("draw_trigger") or {}).items():
            if done.get(cid, "") < at and self.has_time(30):
                MO.cups(self)
                X2.continental_odds(self)
                done[cid] = at

    def records_books(self):
        for cid in self.cfg.get("records_comps", []):
            if self.has_time(10) and AN.history_complete(self, (cid,)):
                AN.records_book(self, cid)

    def player_tables_due(self):
        for cid in self.cfg.get("player_stats_comps", []):
            if self.has_time(40) and self.due("players", 1440, cid):
                self.player_tables(cid)

    def analytics_chores(self, only=None):
        """`only`: a replacement step list (tests)."""
        steps = [
            ("live_watchdog", 0, lambda: self.live_watchdog(self.store.get_json("live.json") or {})),
            ("history", 0, lambda: AN.history_step(self, limit=20)),
            ("records_book", 1440, self.records_books),
            ("danger", 1440, lambda: AN.danger(self)),
            ("arab_ratings", 360, lambda: AN.arab_ratings(self)),
            ("insights", 0, self.insights_due),
            ("players_step", 180, lambda: MO.players_step(self)),
            ("team_histories", 60, lambda: MO.team_histories(self)),
            ("cups", 60, lambda: MO.cups(self)),
            ("callups", 180, lambda: MO.callups(self)),
            ("careers", 30, lambda: MO.careers(self)),
            ("birthdays", 1440, lambda: MO.birthdays(self)),
            ("transfers_feed", 60, lambda: MO.transfers_feed(self)),
            ("arabs_abroad", 60, lambda: AR.abroad(self)),
            ("arabs_tonight", 30, lambda: AR.tonight(self)),
            ("coefficients", 1440, lambda: AR.coefficients(self)),
            ("calendars", 1440, lambda: AR.calendars(self)),
            ("archive_index", 1440, lambda: AR.archive_index(self)),
            ("arab_streaks", 60, lambda: AR.streaks(self)),
            ("tv_guide", 60, lambda: AR.guide(self)),
            ("draw_triggers", 0, self.draw_triggers),
            ("national_teams", 0, lambda: AR.national_teams(self)),
            ("abroad_per90", 60, lambda: X2.abroad_per90(self)),
            ("match_of_week", 720, lambda: X2.match_of_week(self)),
            ("golden_boot", 360, lambda: X2.golden_boot_and_poty(self)),
            ("continental_odds", 360, lambda: X2.continental_odds(self)),
            ("champion_path", 1440, lambda: X2.champion_path(self)),
            ("coaches_all", 720, lambda: X2.coaches(self)),
            ("happiness", 60, lambda: X2.happiness(self)),
            ("twins", 1440, lambda: X2.twins(self)),
            ("finishing", 720, lambda: X2.finishing(self)),
            ("anniversaries", 360, lambda: X2.anniversaries(self)),
            ("year_calendar", 1440, lambda: X2.year_calendar(self)),
            ("suspensions", 60, lambda: X2.suspensions_and_absences(self)),
            ("league_books", 720, lambda: X2.league_books(self)),
            ("club_records", 360, lambda: X2.club_records_step(self)),
            ("transitions", 1440, lambda: MO.transitions(self)),
            ("continental_history", 1440, lambda: AR.continental_history(self)),
            ("arab_coaches", 60, lambda: AR.coaches(self)),
            ("arab_referees", 360, lambda: AR.referees(self)),
            ("friendlies", 360, lambda: AR.friendlies(self)),
            ("monthly", 720, lambda: AR.monthly(self)),
            ("arab_clashes", 60, lambda: AR.clashes(self)),
            ("arab_national", 60, lambda: AR.national_hub(self)),
            ("arab_derbies", 60, lambda: AR.derbies(self)),
            ("players", 0, self.player_tables_due),
            ("club_pages", 0, lambda: AN.club_pages(self)),
            ("coaches_fatigue", 0, lambda: AN.coaches_and_fatigue(self)),
            ("ratings", 60, lambda: AN.ratings(self)),
            ("league_analytics", 0, lambda: AN.leagues_step(self)),
            ("style", 1440, lambda: AN.style(self)),
            ("national", 1440, lambda: AN.national(self)),
            ("fifa", 1440, lambda: AN.fifa(self)),
            ("alltime", 1440, lambda: AN.publish_alltime(self)),
            ("loans", 60, lambda: AN.loans(self)),
            ("league_squads", 0, lambda: AN.league_squads_step(self)),
            ("compare", 1440, lambda: AN.league_compare(self)),
            ("archive", 0, lambda: AN.archive_step(self)),
        ] if only is None else only
        for key, every, fn in steps:
            if not self.has_time(12):
                return
            if key == "history" and AN.history_complete(self, AN.history_comps()) and not self.due("history_recheck", 1440):
                continue
            if key in ("ratings", "archive") and not AN.history_complete(self):
                continue
            if every and not self.due(key, every):
                continue
            try:
                done = fn()
                if every and done is False and every > NOT_READY_RETRY:
                    # inputs not there yet (history, ratings, careers ... fill in over several runs): try again in
                    # NOT_READY_RETRY minutes instead of publishing nothing, or an empty file, for a whole cadence
                    self.dues()[key] = iso(self.now() - timedelta(minutes=every - NOT_READY_RETRY))
                elif every:
                    self.mark(key)
                if key == "history" and AN.history_complete(self, AN.history_comps()):
                    self.mark("history_recheck")
            except Exception as e:
                self.store.fail(f"analytics:{key}", f"{type(e).__name__}: {e}")
                self.mark(key)

    # ------------------------------------------------------------------ source outage alert (343)
    SOURCE_KEYS = ("day:", "match:", "team:", "names:fotmob", "prev-season:", "players:")

    def _source_key(self, k):
        return k.startswith(self.SOURCE_KEYS) or (k.startswith("comp:") and k.endswith(":fotmob"))

    def source_watch(self):
        """One e-mail when FotMob has failed (errors, or empty/malformed data the validators refused) for
        source_alert_minutes, one when it answers again. A run is good if any FotMob-fed item succeeded, bad if
        FotMob items failed and none succeeded, neutral if it touched none (idle minutes): neutral runs never
        start or end an outage. State in poller.json (source_watch)."""
        now = self.now()
        w = self.st.setdefault("source_watch", {"first_bad_at": None, "alerted_at": None, "last_error": None, "send_failures": 0})
        mine = {k: v for k, v in self.store.health.items() if self._source_key(k)}
        fm_ok = sum(n - self.ok_before.get(h, 0) for h, n in HTTP.ok.items() if "fotmob.com" in h)
        fm_bad = sum(n - self.failed_before.get(h, 0) for h, n in HTTP.failed.items() if "fotmob.com" in h)
        good = any(v["ok"] for v in mine.values()) or (not mine and fm_ok > 0 and not fm_bad)
        bad = not good and (any(not v["ok"] for v in mine.values()) or fm_bad > 0)
        limit = self.cfg.get("source_alert_minutes", 15)
        if bad:
            err = next((f"{k}: {v['error']}" for k, v in mine.items() if not v["ok"]), f"{fm_bad} FotMob requests failed")
            w["last_error"] = err[:300]
            w["first_bad_at"] = w.get("first_bad_at") or iso(now)
            down = _age_min(w["first_bad_at"], now)
            self.store.fail("source:fotmob", f"failing for {down:.0f} min: {err}")
            if down >= limit and not w.get("alerted_at") and w.get("send_failures", 0) < 5:
                self._alert("outage", w, down)
        elif good:
            if w.get("alerted_at"):
                self._alert("recovery", w, _age_min(w["first_bad_at"], now) if w.get("first_bad_at") else None)
            if not w.get("alerted_at") or w.get("send_failures", 0) >= 5:
                if w.get("send_failures", 0) >= 5:
                    self.store.ok("source-alert", note="gave up sending after 5 failures; outage over")   # health.ok again
                w.update({"first_bad_at": None, "alerted_at": None, "send_failures": 0})
            self.store.ok("source:fotmob")

    def _alert(self, kind, w, minutes):
        mins = f"{minutes:.0f}" if minutes is not None else "?"
        if kind == "outage":
            subj = f"Tifo: FotMob down for {mins} min"
            body = (f"مصدر البيانات FotMob متعطل من {w['first_bad_at']} (UTC)، يعني {mins} دقيقة.\n"
                    f"آخر خطأ: {w['last_error']}\n\n"
                    "الموقع يعرض آخر نسخة سليمة من كل ملف (keep-last-good)، والنتائج الحية واقفة لين يرجع المصدر.\n"
                    "بيوصلك إيميل ثاني واحد بس لما يرجع. الحالة: https://tifo.elyoxe.com/v1/health.json\n"
                    "خطة البديل: docs/SOURCE-MIGRATION.md")
        else:
            subj = f"Tifo: FotMob back after {mins} min"
            body = (f"رجع FotMob يرد بشكل سليم. بدأ العطل {w['first_bad_at']} (UTC) واستمر حوالي {mins} دقيقة.\n"
                    f"آخر خطأ كان: {w['last_error']}\n"
                    "الملفات تتحدث من جديد في الدورات الياية.")
        try:
            (self.mailer or _ses_send)(subj, body)
        except Exception as e:
            w["send_failures"] = w.get("send_failures", 0) + 1
            self.store.fail("source-alert", f"{kind} mail not sent ({w['send_failures']}/5): {type(e).__name__}: {e}")
            return
        w["send_failures"] = 0
        if kind == "outage":
            w["alerted_at"] = iso(self.now())
        else:
            w.update({"first_bad_at": None, "alerted_at": None})
        self.store.ok("source-alert", note=f"{kind} mail sent")
        self.note(f"source alert: {kind} mail sent")

    # ------------------------------------------------------------------ live-feed watchdog (audit W1.12)
    def live_watchdog(self, live_json=None):
        """While a match is live, live.json must move every 20 s. If its last write is more than live_stall_seconds
        old, mail the owner once per match (poller: a gap between runs; analytics: a poller that stopped running)."""
        now = self.now()
        limit = self.cfg.get("live_stall_seconds", 90)
        if live_json is None:
            live = set(self.st.get("live_ids") or [])
            last = self.st.get("live_written_at")
        else:
            live = {str(m["id"]) for m in live_json.get("matches") or [] if m.get("status") in S.LIVE_STATUSES}
            last = live_json.get("generated")
        state = (self.an_state if self.role == "analytics" else self.st).setdefault("stall_alerted", {})
        for k in [k for k in state if k not in live]:
            del state[k]                        # match over: a new stall of another match alerts again
        if not live or not last:
            return
        gap = (now - parse_utc(last)).total_seconds()
        if gap <= limit:
            self.store.ok("live-watchdog", note=f"live.json {gap:.0f} s old")
            return
        todo = sorted(m for m in live if m not in state)
        if not todo:
            return
        who = "the poller has not run" if self.role == "analytics" else "the previous runs did not write it"
        body = (f"live.json توقف: آخر تحديث قبل {gap:.0f} ثانية ({last} UTC) والمباريات {', '.join(todo)} شغالة.\n"
                f"السبب المرجّح: {who}. الموقع يعرض آخر نسخة سليمة.\n"
                "الحالة: https://tifo.elyoxe.com/v1/health.json · السجل: bash run.sh logs")
        try:
            (self.mailer or _ses_send)(f"Tifo: live feed stalled {gap:.0f} s", body)
        except Exception as e:
            self.store.fail("live-watchdog", f"mail not sent: {type(e).__name__}: {e}")
            return
        for m in todo:
            state[m] = iso(now)
        self.store.fail("live-watchdog", f"live.json {gap:.0f} s old while live (alerted: {', '.join(todo)})")
        self.note(f"live watchdog: stall of {gap:.0f} s mailed")

    def team_country(self, tid):
        """National team -> its country; club -> the country of its first domestic competition."""
        c = config.country_of_team(tid)
        if c:
            return {**c, "national": True}
        for cid in self.st.get("team_comps", {}).get(str(tid), []):
            cc = (self.comp_by_id.get(cid) or {}).get("country")
            if cc:
                return cc
        return None

    def focus_team_ids(self):
        ids = list(config.focus_teams())
        for k, v in self.st.get("team_comps", {}).items():
            if any(c in v for c in config.focus_comps()) and int(k) not in ids:
                ids.append(int(k))
        return ids

    def run(self):
        self.load()
        if self.role == "analytics":
            self.mode = "analytics"
            try:
                self.analytics_chores()
            except Exception as e:
                self.store.fail("analytics", f"{type(e).__name__}: {e}")
                traceback.print_exc()
            self.save()
            return {"mode": self.mode, "written": len(self.store.written), "unchanged": self.store.skipped_same,
                    "requests": HTTP.network_calls - self.requests_before, "seconds": round(self.clock() - self.t0, 1),
                    "refused": self.store.refused}
        live_ids = self.live_window()
        self.mode = "live" if live_ids else "idle"
        try:
            if live_ids:
                self.live_watchdog()
        except Exception as e:
            self.store.fail("live-watchdog", f"{type(e).__name__}: {e}")
        try:
            if live_ids:
                step = self.cfg.get("live_pass_seconds", 20)
                for n in range(3):
                    start = n * step
                    if n > 0:
                        self.deadline = start - 0.5          # fill the gap with chores, stop before the slot
                        self.chores(live=True)
                        self.deadline = None
                        wait = start - (self.clock() - self.t0)
                        if wait > 0:
                            self.sleep(wait)
                    if not self.has_time(4):
                        break
                    self.live_pass(n)
                if self.has_time(8):
                    self.chores(live=True)
            else:
                self.chores(live=False)
        except Exception as e:   # never lose the state because one chore blew up
            self.store.fail("poller", f"{type(e).__name__}: {e}")
            traceback.print_exc()
        try:
            self.source_watch()
        except Exception as e:
            self.store.fail("source-watch", f"{type(e).__name__}: {e}")
        self.write_index()
        self.save()
        return {"mode": self.mode, "written": len(self.store.written), "unchanged": self.store.skipped_same,
                "requests": HTTP.network_calls - self.requests_before, "seconds": round(self.clock() - self.t0, 1),
                "refused": self.store.refused}


REPOLL_MINUTES = (30, 60, 180, 1440)   # after full time, for matches whose feed lacks subs or cards (1440: FotMob
                                       # added Gulf Cup cards a day later, 2026-09-27)


def coverage_events(d):
    """What the source's event feed covers for this match. subs = false when the match is past 60' (or finished)
    and has lineups but not one substitution event: the source did not report them (a real match always has some).
    cards = false in the same case when there is no card either; with subs reported, zero cards is a real zero."""
    ev = d.get("events") or []
    lu = d.get("lineups") or {}
    has_lineups = any((lu.get(s) or {}).get("starters") for s in ("home", "away"))
    past60 = d.get("status") == S.FINISHED or (d.get("status") in S.LIVE_STATUSES and _minute_num(d.get("minute"), d["status"]) >= 60)
    subs = any(e["type"] == "sub" for e in ev)
    cards = any(e["type"] in ("yellow", "second_yellow", "red") for e in ev)
    thin = past60 and has_lineups
    return {"subs": subs or not thin, "cards": cards or subs or not thin}


def _ses_send(subject, body):
    """Plain-text mail to the owner through SES ap-south-1 (elyoxe.com is a verified domain)."""
    import boto3
    boto3.client("ses", region_name=os.environ.get("ALERT_REGION", "ap-south-1")).send_email(
        Source=f"Tifo <{os.environ.get('ALERT_FROM', 'tifo@elyoxe.com')}>",
        Destination={"ToAddresses": [os.environ.get("ALERT_TO", "hello@elyoxe.com")]},
        Message={"Subject": {"Data": subject, "Charset": "UTF-8"}, "Body": {"Text": {"Data": body, "Charset": "UTF-8"}}})


def _minute_num(minute, status):
    if status == S.HALFTIME or minute == "HT":
        return 45
    try:
        return int(str(minute).split("+")[0])
    except (TypeError, ValueError):
        return 0


def analytics_handler(event, context):
    """The slow schedule (every 10 min, own function): heavy computation only, never the live loop."""
    budget = float(os.environ.get("ANALYTICS_BUDGET", 280))
    if context is not None and hasattr(context, "get_remaining_time_in_millis"):
        budget = min(budget, context.get_remaining_time_in_millis() / 1000 - 15)
    res = Poller(Store(S3Backend(os.environ["BUCKET"])), budget=budget, role="analytics").run()
    print(json.dumps(res))
    return res


def handler(event, context):
    budget = config.settings().get("budget_seconds", 50)
    if context is not None and hasattr(context, "get_remaining_time_in_millis"):
        budget = min(budget, context.get_remaining_time_in_millis() / 1000 - 6)
    store = Store(S3Backend(os.environ["BUCKET"]))
    res = Poller(store, budget=budget).run()
    print(json.dumps(res))
    return res


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="one poller invocation")
    ap.add_argument("--local", help="write to this directory instead of S3")
    ap.add_argument("--bucket", help="S3 bucket (default $BUCKET)")
    ap.add_argument("--budget", type=float, default=None)
    ap.add_argument("--analytics", action="store_true", help="run the slow analytics role instead of the poller")
    a = ap.parse_args()
    st = Store(LocalBackend(a.local)) if a.local else Store(S3Backend(a.bucket or os.environ["BUCKET"]))
    role = "analytics" if a.analytics else "poller"
    print(json.dumps(Poller(st, budget=a.budget, role=role).run(), ensure_ascii=False))

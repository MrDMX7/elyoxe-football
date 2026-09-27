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
        self.log = []
        self.requests_before = HTTP.network_calls
        self.calls_before = dict(HTTP.calls)

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
        if m.get("comp") in AN.R.UAE_CLUB_COMPS and m.get("status") == S.SCHEDULED:
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
        if d["status"] in S.LIVE_STATUSES or d["status"] == S.FINISHED:
            try:
                pm = AN.prematch(self, d)
                upto = None if d["status"] == S.FINISHED else _minute_num(d.get("minute"), d["status"])
                full["winprob"] = WP.curve(d["events"], pm[:3] if pm else None, upto)
                full["winprob_prematch"] = {"p": [round(x, 3) for x in pm[:3]], "source": pm[3]} if pm else {"p": list(WP.PRIOR), "source": "base-rates"}
            except Exception as e:
                self.store.fail("winprob", f"{mid}: {e}")
        cache = "hot" if d["status"] in S.LIVE_STATUSES else "static" if d["status"] == S.FINISHED else "warm"
        self.store.put_json(f"match/{mid}.json", full, cache=cache, validate=S.validate_detail, health_key=f"match:{why}")
        self.store.ok(f"match:{why}")
        s = self.st.setdefault("schedule", {}).get(str(mid))
        if s:
            s["status"] = d["status"]
        if d["status"] == S.FINISHED and d.get("comp") in self.comp_ids:
            self.add_ledger(d)
        return d

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
        self.store.put_json(f"comp/{cid}/referees.json", {**base, **SEASON.referees(L)}, cache="static")
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
                raise S.Invalid("no player stat lists")
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

    def records_books(self):
        for cid in self.cfg.get("records_comps", []):
            if self.has_time(10) and AN.history_complete(self, (cid,)):
                AN.records_book(self, cid)

    def player_tables_due(self):
        for cid in self.cfg.get("player_stats_comps", []):
            if self.has_time(40) and self.due("players", 1440, cid):
                self.player_tables(cid)

    def analytics_chores(self):
        steps = [
            ("history", 0, lambda: AN.history_step(self, limit=20)),
            ("records_book", 1440, self.records_books),
            ("danger", 1440, lambda: AN.danger(self)),
            ("players", 0, self.player_tables_due),
            ("club_pages", 0, lambda: AN.club_pages(self)),
            ("coaches_fatigue", 0, lambda: AN.coaches_and_fatigue(self)),
            ("ratings", 60, lambda: AN.ratings(self)),
            ("league_analytics", 60, lambda: AN.league(self)),
            ("style", 1440, lambda: AN.style(self)),
            ("national", 1440, lambda: AN.national(self)),
            ("fifa", 1440, lambda: AN.fifa(self)),
            ("alltime", 1440, lambda: AN.publish_alltime(self)),
            ("loans", 60, lambda: AN.loans(self)),
            ("league_squads", 0, lambda: AN.league_squads_step(self)),
            ("compare", 1440, lambda: AN.league_compare(self)),
            ("archive", 0, lambda: AN.archive_step(self)),
        ]
        for key, every, fn in steps:
            if not self.has_time(12):
                return
            if key == "history" and AN.history_complete(self, AN.history_comps()) and not self.due("history_recheck", 1440):
                continue
            if key in ("ratings", "league_analytics", "archive") and not AN.history_complete(self):
                continue
            if every and not self.due(key, every):
                continue
            try:
                fn()
                if every:
                    self.mark(key)
                if key == "history" and AN.history_complete(self, AN.history_comps()):
                    self.mark("history_recheck")
            except Exception as e:
                self.store.fail(f"analytics:{key}", f"{type(e).__name__}: {e}")
                self.mark(key)

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
        self.write_index()
        self.save()
        return {"mode": self.mode, "written": len(self.store.written), "unchanged": self.store.skipped_same,
                "requests": HTTP.network_calls - self.requests_before, "seconds": round(self.clock() - self.t0, 1),
                "refused": self.store.refused}


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

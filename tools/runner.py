"""Tifo's scheduled jobs. Since 2026-10-23 GitHub Actions runs site, journal, names and newsletter (.github/workflows/tifo-*.yml;
the repo is public so the runners are free); the laptop (Windows Task Scheduler, tools/runner-task.vbs) keeps streams, and
any job still runs here by hand. Owner 2026-10-01 moved them off the Fold; the Fold's watchdog (`watch`) went on 2026-10-23.

    python -m tools.runner site        hourly: AI content (site/ai/gen.py), build, guard, publish, health
    python -m tools.runner journal     every 15 min: news, videos, commentators (python -m news.run)
    python -m tools.runner streams     every 5 min: «شوفها مباشر ببلاش», the free official live streams (python -m news.streams)
    python -m tools.runner names       weekly: Arabic names for new players (names/build_names.py), committed
    python -m tools.runner week        Thursday 15:00: «تيفو الأسبوع» images (site/weekly.py)
    python -m tools.runner newsletter  Thursday 18:00: the weekly newsletter (newsletter/send.py)

Each job runs one at a time (a lock under site/cache/), logs to site/cache/runner/<job>.log, and writes a heartbeat to
S3 state/runner/<job>.json {host, ok, at, seconds, note}; host is github, laptop or fold. A job that fails twice in a row
mails hello@elyoxe.com (SES, at most once every 6 hours per job). On the laptop every job ends with tools/ci_bridge.py
push: the workspace files and ~/.elyoxe switches the GitHub runs read. Same steps as site/deploy.sh (manual runs).
"""
import argparse, json, os, shutil, subprocess, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
CACHE = SITE / "cache"
LOGS = CACHE / "runner"
sys.path.insert(0, str(ROOT))
from store import Store, S3Backend  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
REGION, STACK = "ap-south-1", "elyoxe-tifo-site"
HOST = "github" if os.environ.get("GITHUB_ACTIONS") == "true" else "laptop" if os.name == "nt" else "fold"
PY, NODE, AWS = sys.executable, shutil.which("node") or "node", shutil.which("aws") or "aws"
INDEXNOW_KEY = "8a5d11d3194545d5a4750dc4ede4a7ad"
STORE = Store(S3Backend(BUCKET))


class Lock:
    """One run per job on this machine; a second start while the first runs exits quietly."""
    def __init__(self, name):
        self.p = CACHE / f"runner-{name}.lock"

    def __enter__(self):
        CACHE.mkdir(parents=True, exist_ok=True)
        self.f = open(self.p, "a+")
        try:
            self.f.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            self.f.close()
            return False

    def __exit__(self, *a):
        try:
            if os.name == "nt":
                import msvcrt
                self.f.seek(0); msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
            self.f.close()
        except Exception:
            pass


class Log:
    def __init__(self, job):
        LOGS.mkdir(parents=True, exist_ok=True)
        self.p = LOGS / f"{job}.log"
        if self.p.exists() and self.p.stat().st_size > 2_000_000:
            self.p.write_text(self.p.read_text(encoding="utf-8", errors="replace")[-500_000:], encoding="utf-8")
        self.f = open(self.p, "a", encoding="utf-8", newline="\n")
        self.w(f"==== {job} on {HOST} at {datetime.now(timezone.utc).isoformat(timespec='seconds')}")

    def w(self, s):
        self.f.write(str(s).rstrip() + "\n"); self.f.flush()


def run(log, cmd, cwd=ROOT, timeout=None):
    """Run a command, its output into the log; (return code, the output's tail). On a timeout the whole process tree goes and
    what it printed so far is logged: the 19:49 build of 2026-10-06 hung 4 h with nothing in the log to say where, and a child
    of node's still holding the pipe kept the runner waiting 10 more minutes after node was killed."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONWARNINGS="ignore")
    env.setdefault("HOME", str(Path.home()))          # Task Scheduler gives no HOME; scripts join paths onto it
    # IPv4 first: this laptop's IPv6 path is slower and once left a build waiting on a dead connection for 4 hours (2026-10-06)
    env["NODE_OPTIONS"] = (env.get("NODE_OPTIONS", "") + " --dns-result-order=ipv4first").strip()
    log.w("$ " + " ".join(str(c) for c in cmd))
    t0 = time.time()                                   # every step's time in the log (2026-10-07: where a 45-min site job goes)
    p = subprocess.Popen([str(c) for c in cmd], cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                         errors="replace", env=env)
    try:
        out, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
        else:
            p.kill()
        try:
            out, _ = p.communicate(timeout=120)   # a retried communicate() keeps what was read before the timeout
        except subprocess.TimeoutExpired:
            out = "(its output was not readable after the kill)"
        log.w((out or "")[-6000:])
        log.w(f"timed out after {timeout}s"); return 124, "timeout"
    out = out or ""
    log.w(out[-12000:])
    log.w(f"[{time.time() - t0:.0f} s, exit {p.returncode}]")
    return p.returncode, "\n".join(out.strip().splitlines()[-4:])


S3FAST = Path.home() / "workspace" / "tools" / "s3fast.py"


def s3(log, args):
    """`aws s3 sync|cp …` (args from "s3" on) through ~/workspace/tools/s3fast.py, boto3 many at a time (owner 2026-10-08: the
    fast upload for everything); the CLI, with one retry for S3 stream blips, only when it fails or is missing."""
    if S3FAST.exists():
        rc, tail = run(log, [PY, S3FAST] + args[1:], cwd=SITE, timeout=3 * 3600)
        if not rc:
            return rc, tail
        log.w("s3fast failed; the CLI does it")
    rc, tail = run(log, [AWS] + args, cwd=SITE, timeout=3 * 3600)
    if rc:
        time.sleep(5)
        rc, tail = run(log, [AWS] + args, cwd=SITE, timeout=3 * 3600)
    return rc, tail


def http_ok(url):
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "tifo-runner", "Accept-Encoding": "gzip"}), timeout=30).status
    except Exception as e:
        return getattr(e, "code", 0)


# ------------------------------------------------------------------ the jobs
def job_site(log):
    rc, tail = run(log, [PY, SITE / "ai" / "gen.py", "--limit", "10"], timeout=1500)   # cached by data signature; never fatal
    if rc:
        log.w(f"ai/gen.py exit {rc} (not fatal)")
    rc, tail = run(log, [NODE, "build.cjs"], cwd=SITE, timeout=4 * 3600)
    if rc:
        return False, f"build failed ({rc}): {tail}"
    out = SITE / "out"
    now = sum(1 for _ in out.rglob("index.html"))
    lastf = CACHE / "last_pages"
    last = int(lastf.read_text().strip() or 0) if lastf.exists() else 0
    # 2026-10-23: the count also lives in S3 (state/runner/site-pages.json), so a run that starts from a cold or stale cache
    # (GitHub's runners keep nothing) still holds the build against the last published count; the larger of the two wins
    try:
        last = max(last, int((STORE.get_state("runner/site-pages.json") or {}).get("pages") or 0))
    except Exception as e:
        log.w(f"site-pages state unreadable ({e}); the local count only")
    if not last and os.environ.get("TIFO_FIRST_PUBLISH") != "1":
        return False, f"{now} pages built and no published count to hold them against; not publishing (TIFO_FIRST_PUBLISH=1 overrides)"
    if last and now < last * 95 // 100:             # a flaky fetch (or a missing input) can yield a partial build, and
        return False, f"partial build: {now} pages vs {last} last time; not publishing"   # `sync --delete` would wipe pages
    q = lambda k: subprocess.run([AWS, "cloudformation", "describe-stacks", "--region", REGION, "--stack-name", STACK, "--query",
                                  f"Stacks[0].Outputs[?OutputKey=='{k}'].OutputValue", "--output", "text"], capture_output=True, text=True).stdout.strip()
    bucket, dist, dom = q("Bucket"), q("DistributionId"), q("DistributionDomain")
    if not bucket:
        return False, "can't read the site stack's outputs"
    syncs = [
        (["s3", "sync", "out/assets", f"s3://{bucket}/assets", "--region", REGION, "--only-show-errors", "--cache-control", "public,max-age=31536000,immutable"], "assets"),
        (["s3", "sync", "out/logo", f"s3://{bucket}/logo", "--region", REGION, "--only-show-errors", "--cache-control", "public,max-age=604800"], "logos"),
        # the stages' files (below) live outside out/: the encyclopedia's db/player/<id>/, the share cards og/s/ and the goal pages
        # m/<id>/g/<n>/; the --delete must not take them
        (["s3", "sync", "out", f"s3://{bucket}", "--region", REGION, "--only-show-errors", "--delete", "--exclude", "assets/*", "--exclude", "logo/*",
          "--exclude", "next/*", "--exclude", "google*.html", "--exclude", "db/player/[0-9]*", "--exclude", "og/s/*", "--exclude", "m/*/g/*",
          "--cache-control", "public,max-age=60"], "pages"),
    ]
    for args, what in syncs:
        if what == "pages":                            # 2026-10-08: boto3, 32 at a time (tools/s3push.py); the CLI sync is the fallback
            t0 = time.time()
            try:
                from tools.s3push import push
                ok, note = push(str(SITE / "out"), bucket, REGION, excludes=[a for i, a in enumerate(args) if i and args[i - 1] == "--exclude"],
                                cache_control="public,max-age=60", say=log.w, manifest=str(SITE / "cache" / "out_manifest.json"))
            except Exception as e:
                ok, note = False, f"{type(e).__name__}: {e}"
            log.w(f"s3push: {note} [{time.time() - t0:.0f} s, {'ok' if ok else 'falling back to the CLI sync'}]")
            if ok:
                continue
        rc, tail = s3(log, args)
        if rc:
            return False, f"{what} sync failed: {tail}"
    world = publish_stage(log, bucket, "world") + publish_stage(log, bucket, "share")
    lastf.write_text(str(now))
    try:
        STORE.put_state("runner/site-pages.json", {"pages": now, "host": HOST, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    except Exception as e:
        log.w(f"site-pages state not written: {e}")
    run(log, [AWS, "cloudfront", "create-invalidation", "--distribution-id", dist, "--paths", "/sw.js", "/", "--query", "Invalidation.Id", "--output", "text"], timeout=120)
    ix = CACHE / "indexnow.txt"
    if ix.exists() and ix.stat().st_size:
        try:
            urls = [u for u in ix.read_text(encoding="utf-8").splitlines() if u][:10000]
            body = json.dumps({"host": "tifo.elyoxe.com", "key": INDEXNOW_KEY, "keyLocation": f"https://tifo.elyoxe.com/{INDEXNOW_KEY}.txt", "urlList": urls}).encode()
            st = urllib.request.urlopen(urllib.request.Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8"}), timeout=30).status
            log.w(f"indexnow: {len(urls)} urls -> {st}")
        except Exception as e:
            log.w(f"indexnow: submit failed (not fatal): {e}")
    codes = {p: http_ok(f"https://{dom}{p}") for p in ("/", "/c/uae-pro-league/", "/v1/index.json")}
    log.w(f"live: {codes}")
    # the outage alert (202): the data feed must be fresh
    try:
        h = STORE.get_json("health.json") or {}
        age = time.time() - datetime.strptime(h["generated"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
        feed = "ok" if h.get("ok") and age < 3600 else f"FAILING {','.join(h.get('failing', []))} age {age / 60:.0f} min"
    except Exception as e:
        feed = f"health unreadable: {e}"
    note = f"{now} pages published{world}; feed {feed}"
    # «ok» = the pages are published and answer. The feed's own health (the poller) is reported here but alerts on its own:
    # counting it as a site failure marked 62 published builds «failed» (2026-10-02..05) and set off the Fold's old watchdog
    return all(c == 200 for c in codes.values()), note


def publish_stage(log, bucket, name):
    """A build stage that lives outside out/ (owner items 10-11, 2026-10-06): site/cache/world/ (the encyclopedia's /db/player/<id>/,
    site/lib/world_stage.cjs) and site/cache/share/ (share cards og/s/ and goal pages /m/<id>/g/<n>/, site/lib/share_stage.cjs).
    Uploads only this run's new or changed files (<stage>/delta/, `s3 cp`: nothing already up is listed or compared), deletes what
    left the stage (delete.txt, guarded at 5 % by the stage), then promotes manifest.next.json. A failed upload keeps the old
    manifest, so the next build writes the same files again. Never fails the site job; the note says what happened."""
    wd = CACHE / name
    delta, nxt = wd / "delta", wd / "manifest.next.json"
    if not nxt.exists():
        return ""
    n = sum(1 for p in delta.rglob("*") if p.is_file()) if delta.is_dir() else 0
    t0 = time.time()
    if n:
        rc, tail = s3(log, ["s3", "cp", str(delta), f"s3://{bucket}", "--recursive", "--region", REGION, "--only-show-errors", "--cache-control", "public,max-age=60"])
        if rc:
            return f"; {name} upload failed ({tail.splitlines()[-1] if tail else rc}), redone next run"
    dl = wd / "delete.txt"
    keys = [k.strip() for k in dl.read_text(encoding="utf-8").splitlines() if k.strip()] if dl.exists() else []
    for i in range(0, len(keys), 1000):
        jf = wd / "delete.json"
        jf.write_text(json.dumps({"Objects": [{"Key": k} for k in keys[i:i + 1000]], "Quiet": True}), encoding="utf-8")
        run(log, [AWS, "s3api", "delete-objects", "--bucket", bucket, "--region", REGION, "--delete", "file://" + str(jf).replace("\\", "/")], cwd=SITE, timeout=600)
    nxt.replace(wd / "manifest.json")
    log.w(f"{name}: {n} files uploaded, {len(keys)} deleted in {time.time() - t0:.0f}s")
    return f"; {name}: {n} up, {len(keys)} removed"


def job_journal(log):
    # 30 min: a run killed at the limit loses all its work, and while the site job uploads a whole new site (every page changed:
    # the SEO footer and the v5 shell on 2026-10-06) the journal's S3 writes share the uplink and a run took 16 min (954 s)
    rc, tail = run(log, [PY, "-m", "news.run"], timeout=30 * 60)
    # «تابع اللاعب»: the followed players' club and national team for the poller (never fatal: the last map stays)
    rc2, _ = run(log, [PY, "-m", "pushplayers"], timeout=5 * 60)
    if rc2:
        log.w(f"pushplayers exit {rc2} (not fatal)")
    # «انتقالات النادي» (owner 2026-10-10 item 12): the ledger's new moves to both clubs' subscribers, in the UAE day (never fatal)
    rc4, _ = run(log, [PY, "-m", "pushtransfers"], timeout=5 * 60)
    if rc4:
        log.w(f"pushtransfers exit {rc4} (not fatal)")
    # Bing: the day's 100 URLs (a new site's quota), once a day; the tool skips a day already sent (never fatal)
    rc3, _ = run(log, [PY, "-m", "tools.bing_submit"], timeout=5 * 60)
    if rc3:
        log.w(f"bing_submit exit {rc3} (not fatal)")
    return rc == 0, tail


def job_streams(log):
    # a stream is looked for while its match is near (75 min before kickoff to 3.5 h after): ~10-20 YouTube Live tabs a run
    rc, tail = run(log, [PY, "-m", "news.streams"], timeout=5 * 60)
    return rc == 0, tail


def job_names(log):
    rc, tail = run(log, [PY, "build_names.py"], cwd=ROOT / "names", timeout=3 * 3600)
    if rc == 0:   # «يُكتب أيضاً»: other Arabic spellings from Arabic Wikipedia redirects (never fatal; committed with names/)
        run(log, [PY, "aka.py"], cwd=ROOT / "names", timeout=30 * 60)
    if rc == 0 and subprocess.run(["git", "status", "--porcelain", "--", "names/"], cwd=ROOT, capture_output=True, text=True).stdout.strip():
        run(log, ["git", "add", "names/"])
        run(log, ["git", "commit", "-q", "-m", f"names: weekly Arabic names for new players ({datetime.now().date()})"])
        if run(log, ["git", "pull", "-q", "--rebase"])[0] == 0:
            run(log, ["git", "push", "-q"])
    return rc == 0, tail


def job_week(log):
    rc, tail = run(log, [PY, SITE / "weekly.py"], timeout=1800)
    return rc == 0, tail


def job_newsletter(log):
    rc, tail = run(log, [PY, ROOT / "newsletter" / "send.py"], timeout=1800)
    return rc == 0, tail


JOBS = {"site": job_site, "journal": job_journal, "streams": job_streams, "names": job_names, "week": job_week, "newsletter": job_newsletter}


# ------------------------------------------------------------------ heartbeat, alerts
def where_log(job):
    if HOST == "github":
        return f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/{os.environ.get('GITHUB_RUN_ID')}"
    return f"site/cache/runner/{job}.log على {HOST}"


def beat(job, ok, secs, note):
    prev = STORE.get_state(f"runner/{job}.json") or {}
    fails = 0 if ok else int(prev.get("fails") or 0) + 1
    doc = {"host": HOST, "ok": ok, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "seconds": round(secs), "note": str(note)[:600],
           "fails": fails, "last_ok": prev.get("last_ok") if not ok else datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "last_ok_host": prev.get("last_ok_host") if not ok else HOST, "alerted_at": prev.get("alerted_at"), "running": False}
    alerts_off = os.path.exists(os.path.expanduser("~/.elyoxe/tifo-alerts-off"))   # owner's pause, 2026-10-02
    if fails >= 2 and not alerts_off and time.time() - float(prev.get("alerted_ts") or 0) > 6 * 3600:
        try:
            import boto3
            boto3.client("ses", region_name=REGION).send_email(
                Source="Tifo <tifo@elyoxe.com>", Destination={"ToAddresses": ["hello@elyoxe.com"]},
                Message={"Subject": {"Data": f"تيفو: مهمة «{job}» فشلت {fails} مرات على {HOST}", "Charset": "UTF-8"},
                         "Body": {"Text": {"Data": f"{note}\n\nالسجل: {where_log(job)}.", "Charset": "UTF-8"}}})
            doc["alerted_ts"], doc["alerted_at"] = time.time(), doc["at"]
        except Exception as e:
            doc["alert_error"] = str(e)[:200]
    else:
        doc["alerted_ts"] = prev.get("alerted_ts")
    STORE.put_state(f"runner/{job}.json", doc)


# Weekly jobs, done once a week whichever host gets there first (2026-10-23: GitHub Actions and the laptop both had them
# scheduled while the jobs moved; a second newsletter would mail every subscriber twice, a second names run would race
# the first one's push). TIFO_FORCE=1 runs anyway (a run by hand).
ONCE = {"names": 5 * 86400, "newsletter": 5 * 86400}


def done_elsewhere(job):
    """A note when `job` needs no run now: it succeeded within ONCE[job] on any host, or another host is running it."""
    gap = ONCE.get(job)
    if not gap or os.environ.get("TIFO_FORCE") == "1":
        return None
    try:
        st = STORE.get_state(f"runner/{job}.json") or {}
    except Exception:
        return None
    age = lambda t: time.time() - datetime.fromisoformat(t).timestamp() if t else 1e12
    if age(st.get("last_ok")) < gap:
        return f"done {age(st.get('last_ok')) / 3600:.0f} h ago on {st.get('last_ok_host')}"
    if st.get("running") and st.get("running_host") != HOST and age(st.get("started_at")) < 2 * 3600:
        return f"running on {st.get('running_host')} since {st.get('started_at')}"
    return None


def do(job):
    with Lock(job) as got:
        if not got:
            print(f"{job}: a previous run is still going; skip")
            return 0
        why = done_elsewhere(job)
        if why:
            print(f"{job}: {why}; skip")
            return 0
        log, t0 = Log(job), time.time()
        try:   # «running»: the job is under way, and where
            prev = STORE.get_state(f"runner/{job}.json") or {}
            STORE.put_state(f"runner/{job}.json", dict(prev, running=True, running_host=HOST, started_at=datetime.now(timezone.utc).isoformat(timespec="seconds")))
        except Exception as e:
            log.w(f"start beat failed: {e}")
        try:
            ok, note = JOBS[job](log)
        except Exception as e:
            ok, note = False, f"{type(e).__name__}: {e}"
        log.w(f"==== {'ok' if ok else 'FAILED'} in {time.time() - t0:.0f}s: {note}")
        try:
            beat(job, ok, time.time() - t0, note)
        except Exception as e:
            log.w(f"heartbeat failed: {e}")
        print(f"{job}: {'ok' if ok else 'FAILED'} ({note})")
        bridge(log)
        return 0 if ok else 1


def bridge(log=None):
    """The laptop, after each job: tools/ci_bridge.py push (at most every 10 min; never fails the job)."""
    if HOST != "laptop":
        return
    try:
        from tools import ci_bridge
        r = ci_bridge.push()
        if log and not r.get("skipped"):
            log.w(f"ci_bridge: {r}")
    except Exception as e:
        if log:
            log.w(f"ci_bridge push failed (not fatal): {type(e).__name__}: {e}")


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("job", choices=sorted(JOBS)); a = ap.parse_args(argv)
    return do(a.job)


if __name__ == "__main__":
    sys.exit(main())

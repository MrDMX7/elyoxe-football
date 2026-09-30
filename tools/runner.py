"""Tifo's scheduled jobs, for the laptop (Windows Task Scheduler) and the Fold (cron) alike. Owner 2026-10-01: «ليش ما
تخلي كل شي يشتغل من اللابتوب عشان ما يخلص جرج الفولد». The laptop runs them all; the Fold keeps only `watch`, a light
hourly check that runs a job itself when the laptop's heartbeat for it has gone stale (laptop off or asleep).

    python -m tools.runner site        hourly: AI content (site/ai/gen.py), build, guard, publish, health
    python -m tools.runner journal     every 15 min: news, videos, commentators (python -m news.run)
    python -m tools.runner names       weekly: Arabic names for new players (names/build_names.py), committed
    python -m tools.runner week        Thursday 15:00: «تيفو الأسبوع» images (site/weekly.py)
    python -m tools.runner newsletter  Thursday 18:00: the weekly newsletter (newsletter/send.py)
    python -m tools.runner watch       (the Fold) runs site/journal here when the laptop has gone quiet

Each job runs one at a time (a lock under site/cache/), logs to site/cache/runner/<job>.log, and writes a heartbeat to
S3 state/runner/<job>.json {host, ok, at, seconds, note}. A job that fails twice in a row mails hello@elyoxe.com (SES,
at most once every 6 hours per job). Same steps as site/deploy.sh (which stays for manual runs on the Fold).
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
HOST = "laptop" if os.name == "nt" else "fold"
PY, NODE, AWS = sys.executable, shutil.which("node") or "node", shutil.which("aws") or "aws"
STALE = {"site": 3 * 3600, "journal": 3600}          # watch: the Fold takes a job over after this much silence
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
    """Run a command, its output into the log; (return code, the output's tail)."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONWARNINGS="ignore")
    log.w("$ " + " ".join(str(c) for c in cmd))
    try:
        p = subprocess.run([str(c) for c in cmd], cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        log.w(f"timed out after {timeout}s"); return 124, "timeout"
    out = p.stdout or ""
    log.w(out[-12000:])
    return p.returncode, "\n".join(out.strip().splitlines()[-4:])


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
    if last and now < last * 85 // 100:             # a flaky fetch can yield a partial build; `sync --delete` would wipe pages
        return False, f"partial build: {now} pages vs {last} last time; not publishing"
    q = lambda k: subprocess.run([AWS, "cloudformation", "describe-stacks", "--region", REGION, "--stack-name", STACK, "--query",
                                  f"Stacks[0].Outputs[?OutputKey=='{k}'].OutputValue", "--output", "text"], capture_output=True, text=True).stdout.strip()
    bucket, dist, dom = q("Bucket"), q("DistributionId"), q("DistributionDomain")
    if not bucket:
        return False, "can't read the site stack's outputs"
    syncs = [
        (["s3", "sync", "out/assets", f"s3://{bucket}/assets", "--region", REGION, "--only-show-errors", "--cache-control", "public,max-age=31536000,immutable"], "assets"),
        (["s3", "sync", "out/logo", f"s3://{bucket}/logo", "--region", REGION, "--only-show-errors", "--cache-control", "public,max-age=604800"], "logos"),
        (["s3", "sync", "out", f"s3://{bucket}", "--region", REGION, "--only-show-errors", "--delete", "--exclude", "assets/*", "--exclude", "logo/*",
          "--exclude", "next/*", "--exclude", "google*.html", "--cache-control", "public,max-age=60"], "pages"),
    ]
    for args, what in syncs:
        rc, tail = run(log, [AWS] + args, cwd=SITE, timeout=3 * 3600)
        if rc:
            time.sleep(5)
            rc, tail = run(log, [AWS] + args, cwd=SITE, timeout=3 * 3600)   # one retry: S3 stream blips on thousands of files
        if rc:
            return False, f"{what} sync failed: {tail}"
    lastf.write_text(str(now))
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
    note = f"{now} pages published; feed {feed}"
    return feed == "ok" and all(c == 200 for c in codes.values()), note


def job_journal(log):
    rc, tail = run(log, [PY, "-m", "news.run"], timeout=20 * 60)
    return rc == 0, tail


def job_names(log):
    rc, tail = run(log, [PY, "build_names.py"], cwd=ROOT / "names", timeout=3 * 3600)
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


JOBS = {"site": job_site, "journal": job_journal, "names": job_names, "week": job_week, "newsletter": job_newsletter}


# ------------------------------------------------------------------ heartbeat, alerts, the Fold's watchdog
def beat(job, ok, secs, note):
    prev = STORE.get_state(f"runner/{job}.json") or {}
    fails = 0 if ok else int(prev.get("fails") or 0) + 1
    doc = {"host": HOST, "ok": ok, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "seconds": round(secs), "note": str(note)[:600],
           "fails": fails, "last_ok": prev.get("last_ok") if not ok else datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "last_ok_host": prev.get("last_ok_host") if not ok else HOST, "alerted_at": prev.get("alerted_at")}
    if fails >= 2 and time.time() - float(prev.get("alerted_ts") or 0) > 6 * 3600:
        try:
            import boto3
            boto3.client("ses", region_name=REGION).send_email(
                Source="Tifo <tifo@elyoxe.com>", Destination={"ToAddresses": ["hello@elyoxe.com"]},
                Message={"Subject": {"Data": f"تيفو: مهمة «{job}» فشلت {fails} مرات على {HOST}", "Charset": "UTF-8"},
                         "Body": {"Text": {"Data": f"{note}\n\nالسجل: site/cache/runner/{job}.log على {HOST}.", "Charset": "UTF-8"}}})
            doc["alerted_ts"], doc["alerted_at"] = time.time(), doc["at"]
        except Exception as e:
            doc["alert_error"] = str(e)[:200]
    else:
        doc["alerted_ts"] = prev.get("alerted_ts")
    STORE.put_state(f"runner/{job}.json", doc)


def do(job):
    with Lock(job) as got:
        if not got:
            print(f"{job}: a previous run is still going; skip")
            return 0
        log, t0 = Log(job), time.time()
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
        return 0 if ok else 1


def watch():
    """The Fold, hourly: a job whose last good run (any host) is older than STALE runs here, until the laptop is back."""
    rc = 0
    for job, limit in STALE.items():
        st = STORE.get_state(f"runner/{job}.json") or {}
        last = st.get("last_ok")
        age = time.time() - datetime.fromisoformat(last).timestamp() if last else 1e9
        if age > limit:
            print(f"watch: {job} quiet for {age / 60:.0f} min (last good on {st.get('last_ok_host')}); running it here")
            rc |= do(job)
        else:
            print(f"watch: {job} fine ({age / 60:.0f} min ago on {st.get('last_ok_host')})")
    return rc


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("job", choices=sorted(JOBS) + ["watch"]); a = ap.parse_args(argv)
    return watch() if a.job == "watch" else do(a.job)


if __name__ == "__main__":
    sys.exit(main())

"""Billed duration of elyoxe-football-poller from its CloudWatch REPORT lines (player-follow plan, Task 1 and Task 7).
  python -m tools.poller_time --hours 24 [--out FILE]
In Git Bash prefix MSYS_NO_PATHCONV=1: the log group is a path and would be turned into a Windows one."""
import argparse, json, re, statistics, time

GROUP = "/aws/lambda/elyoxe-football-poller"
BILLED = re.compile(r"Billed Duration: (\d+) ms")


def durations(hours, client=None):
    if client is None:
        import boto3
        client = boto3.client("logs", region_name="ap-south-1")
    kw = {"logGroupName": GROUP, "startTime": int((time.time() - hours * 3600) * 1000), "filterPattern": "REPORT"}
    out = []
    while True:
        r = client.filter_log_events(**kw)
        out += [int(m.group(1)) for e in r.get("events", []) for m in [BILLED.search(e["message"])] if m]
        if not r.get("nextToken"):
            return out
        kw["nextToken"] = r["nextToken"]


def summary(xs):
    if not xs:
        return {"n": 0}
    xs = sorted(xs)
    return {"n": len(xs), "p50": int(statistics.median(xs)), "p95": xs[int(len(xs) * 0.95) - 1], "max": xs[-1]}


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--hours", type=float, default=24); ap.add_argument("--out")
    a = ap.parse_args(argv)
    s = summary(durations(a.hours)); s["hours"] = a.hours; s["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print(json.dumps(s))
    if a.out:
        with open(a.out, "w") as f:
            f.write(json.dumps(s, indent=1))


if __name__ == "__main__":
    main()

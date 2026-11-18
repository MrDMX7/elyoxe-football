"""Throwaway spike (2026-11-18): can GitHub's runners download Tifo's goal clips? Same yt-dlp arguments as the laptop's
goal_watch.fetch(); YouTube failures get a second try with other player clients and node as the JS runtime."""
import json, os, subprocess, time
from pathlib import Path

CLIPS = [
    ("x", "thmanyahsports", "https://x.com/thmanyahsports/status/2123080008675508376"),
    ("x", "dubaisportstv", "https://x.com/dubaisportstv/status/2122010400292024325"),
    ("x", "ADSportsTV", "https://x.com/ADSportsTV/status/2122007645586383335"),
    ("x", "SharjahSportsTV", "https://x.com/SharjahSportsTV/status/2122007551982330180"),
    ("x", "thmanyahsports", "https://x.com/thmanyahsports/status/2123074602603585711"),
    ("youtube", "TUDN", "https://www.youtube.com/watch?v=QjhN0ZseUxs"),
    ("youtube", "TUDN", "https://www.youtube.com/watch?v=r8VRjWtUQBI"),
    ("youtube", "TUDN", "https://www.youtube.com/watch?v=6whcHTXwMA8"),
    ("youtube", "TNT Sports Brasil", "https://www.youtube.com/watch?v=BXjp54-3tgE"),
    ("youtube", "AUFTV", "https://www.youtube.com/watch?v=AMbC-2P9q9w"),
]
OUT = Path("dl"); OUT.mkdir(exist_ok=True)


def run(url, dst, extra=()):
    fmt = ["-f", "bv*[height<=720]+ba/b[height<=720]/b", "--merge-output-format", "mp4"] if "youtube" in url else ["-f", "best[ext=mp4]/best"]
    t0 = time.time()
    r = subprocess.run(["yt-dlp", "--no-warnings", "--no-progress", *fmt, *extra, "-o", str(dst), url], capture_output=True, text=True, timeout=600)
    return time.time() - t0, r.returncode, (r.stderr or r.stdout).strip().splitlines()[-3:]


def probe(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=height,codec_name", "-of", "json", str(f)], capture_output=True, text=True)
    d = json.loads(r.stdout or "{}")
    h = max([s.get("height") or 0 for s in d.get("streams") or []] or [0])
    return round(float((d.get("format") or {}).get("duration") or 0), 1), h


rows = []
for i, (kind, ch, url) in enumerate(CLIPS):
    dst = OUT / f"{i}.mp4"
    tries = [("laptop args", ())]
    if kind == "youtube":
        tries += [("node runtime", ("--js-runtimes", "node")),
                  ("tv/mweb clients + node", ("--js-runtimes", "node", "--extractor-args", "youtube:player_client=tv_simply,mweb,web_safari"))]
    for label, extra in tries:
        secs, rc, tail = run(url, dst, extra)
        ok = dst.exists() and dst.stat().st_size > 50_000
        row = {"i": i, "kind": kind, "channel": ch, "url": url, "try": label, "ok": ok, "secs": round(secs, 1), "rc": rc,
               "mb": round(dst.stat().st_size / 1e6, 1) if ok else 0, "dur_h": probe(dst) if ok else None, "err": "" if ok else " | ".join(tail)[-300:]}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        if ok:
            break

Path("fetch.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
md = ["| # | kind | channel | try | ok | s | MB | dur s / h | error |", "|---|---|---|---|---|---|---|---|---|"]
for r in rows:
    md.append(f"| {r['i']} | {r['kind']} | {r['channel']} | {r['try']} | {'yes' if r['ok'] else 'NO'} | {r['secs']} | {r['mb']} | {r['dur_h']} | {r['err'].replace('|', '/')[:160]} |")
with open(os.environ.get("GITHUB_STEP_SUMMARY", "summary.md"), "a", encoding="utf-8") as f:
    f.write("## yt-dlp from the runner\n\n" + "\n".join(md) + "\n\n")

"""Keeps the owner's football database current (2026-09-30 «الداتا بيس… يكونون محدثين فالموقع»): runs each stage when its
turn comes, in dependency order, and records when each last ran. The laptop runs it (Task Scheduler «Tifo database»,
daily 04:30; StartWhenAvailable catches up after the laptop was off); each stage is a module you can run alone.

    python -m db.refresh [--force stage,stage] [--list]

Stages and cadence (days): Transfermarkt transfers + maps 7 · club histories 7 · club cards 7 · champions (Wikidata, then
Wikipedia) 7 · season scorers 7 · Understat 7 · national Elo 1 · FIFA ranking 30 · UEFA coefficients 30 · photos 30 ·
Messi museum data 7 · FotMob club and player profiles 7 · FotMob season leaders 7 · world encyclopedia 14 · every match since 2010 1 ·
365Scores (champions of ~640 competitions, Arab final tables, the Arab leagues FotMob lacks) 1 · EA FC ratings 7 · Transfermarkt records 7 · Arabic Wikipedia leads 30.
"""
import argparse, json, os, subprocess, sys, time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATE = os.path.join(HERE, ".cache", "refresh.json")
STAGES = [   # name, module, args, every (days)
    ("rsssf", "db.rsssf", ["--upload"], 30),                       # Arab leagues' old seasons (before db.history, which merges them)
    ("transfers", "history.transfermarkt", ["--upload"], 7),
    ("history", "db.history", ["--upload"], 7),
    ("clubs", "db.clubs", ["--upload"], 7),
    ("champions", "db.champions", ["--upload"], 7),
    ("champions_wiki", "db.champions_wiki", ["--upload"], 7),
    ("scorers", "db.scorers", ["--upload"], 7),
    ("understat", "db.understat", ["--upload"], 7),
    ("elo", "db.elo_nations", ["--upload"], 1),
    ("fifa", "db.fifa_rank", ["--upload"], 30),
    ("uefa", "db.uefa", ["--upload"], 30),
    ("photos", "photos.build", [], 30),
    ("messi_play", "history.statsbomb_messi", ["--upload"], 30),
    ("messi_extra", "history.messi_extra", ["--upload"], 7),
    ("fotmob_profiles", "db.fotmob_profiles", ["--upload"], 7),     # every site club and squad player complete (FotMob)
    ("fm_scorers", "db.fm_scorers", ["--upload"], 7),               # season leaders for every competition (after scorers)
    ("world", "db.world", ["--upload", "--players"], 14),           # the world encyclopedia: ~300 leagues, their clubs and players
    ("matches", "db.matches", ["--upload"], 1),                     # new finished matches in detail, then every player's log
    ("s365", "db.scores365", ["--upload"], 1),
    ("eafc", "db.eafc", ["--upload"], 7),
    ("tmdata", "db.tmdata", ["--upload"], 7),                        # Transfermarkt careers by competition, injuries, bio fill (salimt datasets)
    ("wiki_ar", "db.wiki_ar", ["--upload"], 30),                     # Arabic Wikipedia's lead for players and clubs                            # EA SPORTS FC ratings on the player pages (the feed is refetched every 30 days)                      # 365Scores: champions of ~640 competitions, Arab tables, the Arab leagues FotMob lacks
]


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--force", default=""); ap.add_argument("--list", action="store_true"); a = ap.parse_args(argv)
    st = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}
    force = set(filter(None, a.force.split(",")))
    now = time.time()
    for name, mod, args, every in STAGES:
        last = st.get(name, {}).get("ok_at", 0)
        due = name in force or now - last > every * 86400 - 3600
        if a.list:
            print(f"{name:15} every {every:>2}d  last {datetime.fromtimestamp(last, timezone.utc).isoformat()[:16] if last else 'never':16}  {'DUE' if due else ''}"); continue
        if not due:
            continue
        t0 = time.time()
        r = subprocess.run([sys.executable, "-m", mod] + args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        tail = (r.stdout or "").strip().splitlines()[-1:] or (r.stderr or "").strip().splitlines()[-1:]
        st[name] = dict(st.get(name, {}), last_at=now, secs=round(time.time() - t0), rc=r.returncode, tail=(tail[0] if tail else "")[:200])
        if r.returncode == 0:
            st[name]["ok_at"] = now
        print(f"{name}: rc={r.returncode} {st[name]['secs']}s {st[name]['tail']}")
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        json.dump(st, open(STATE, "w", encoding="utf-8", newline="\n"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())

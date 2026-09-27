#!/usr/bin/env bash
# Lighthouse mobile gate: the same pages from two local builds (old = out_base, new = out), one run at a time.
# ./redesign/lh.sh [old_dir] [new_dir]  -> redesign/lh.json {page: {old:{perf,lcp,cls,tbt,fcp}, new:{…}}}
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"; OLD="${1:-out_base}"; NEW="${2:-out}"; LH=/root/.cache/lh/node_modules/.bin/lighthouse
export CHROME_PATH=/usr/bin/chromium
python3 -m http.server 8801 -d "$HERE/$OLD" >/dev/null 2>&1 & P1=$!
python3 -m http.server 8802 -d "$HERE/$NEW" >/dev/null 2>&1 & P2=$!
sleep 1; echo "{" > /tmp/lh.json; first=1
for pg in ${PAGES:-/ /m/6052085/ /m/1000020522/ /c/uae-pro-league/}; do
  for side in old:8801 new:8802; do
    n=${side%%:*}; port=${side##*:}
    timeout 180 "$LH" "http://127.0.0.1:$port$pg" --quiet --only-categories=performance --form-factor=mobile --chrome-flags="--headless=new --no-sandbox --disable-dev-shm-usage" --output=json --output-path=/tmp/lh_$n.json >/dev/null 2>&1
    python3 - "$pg" "$n" <<'PY'
import json,sys
pg,n=sys.argv[1],sys.argv[2]
try:
  d=json.load(open(f"/tmp/lh_{n}.json")); a=d["audits"]
  r=dict(perf=round(d["categories"]["performance"]["score"]*100), fcp=round(a["first-contentful-paint"]["numericValue"]), lcp=round(a["largest-contentful-paint"]["numericValue"]), tbt=round(a["total-blocking-time"]["numericValue"]), cls=round(a["cumulative-layout-shift"]["numericValue"],3))
except Exception as e: r=dict(error=str(e)[:80])
print(pg, n, r)
PY
  done
done
kill $P1 $P2

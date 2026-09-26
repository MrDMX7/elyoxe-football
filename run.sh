#!/usr/bin/env bash
# run.sh — one poller pass by hand. Production runs itself (Lambda, every minute); this is for checks.
#   bash run.sh              tests, then one poll into ./out/ (no AWS; out/v1 mirrors the public files)
#   bash run.sh --s3         tests, then one poll against the deployed bucket (exactly what the Lambda does;
#                            the Lambda may run at the same minute: it is safe, both keep last good)
#   bash run.sh status       health.json from the live distribution (what failed, since when)
#   bash run.sh logs         last 15 minutes of the Lambda's log
# Exit: 0 ok · 6 tests failed (nothing ran) · other = the poll crashed
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
REGION="${FOOTBALL_REGION:-ap-south-1}"; STACK="${FOOTBALL_STACK:-elyoxe-football}"
PY="$HERE/.venv/bin/python"; [ -x "$PY" ] || PY=python3
export PYTHONUNBUFFERED=1 PYTHONWARNINGS=ignore

out() { aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }

case "${1:-}" in
  status)
    dom=$(out DistributionDomain)
    body=$(curl -sS --compressed -m 20 "https://$dom/health.json") || exit 1
    "$PY" -c 'import json,sys; h=json.loads(sys.argv[1]); print("ok" if h["ok"] else "FAILING: "+", ".join(h["failing"]));
r=h["last_run"]; print(f"last run {h[\"generated\"]}: {r[\"mode\"]}, {r[\"seconds\"]} s, {r[\"requests\"]} requests, {r[\"written\"]} written")
[print(f"  {k}: {v[\"error\"]} (last ok {v.get(\"last_ok\")})") for k,v in h["items"].items() if not v["ok"]]' "$body"
    exit 0 ;;
  logs)
    aws logs tail /aws/lambda/elyoxe-football-poller --region "$REGION" --since 15m; exit 0 ;;
esac

"$PY" -m pytest -q -x -p no:cacheprovider || { echo "tests failed — not polling"; exit 6; }
if [ "${1:-}" = "--s3" ]; then
  BUCKET=$(out Bucket)
  "$PY" poller.py --bucket "$BUCKET"
else
  mkdir -p out
  "$PY" poller.py --local out
fi

#!/usr/bin/env bash
# deploy.sh — test, bundle and deploy the football data pipeline (stack elyoxe-football, ap-south-1):
# private S3 bucket + CloudFront (default *.cloudfront.net, no custom domain until the name is chosen)
# + the poller Lambda (arm64) on a 1-minute EventBridge schedule. Then checks the live files.
#   ./deploy.sh              full deploy
#   ./deploy.sh --check      only the live checks against the deployed distribution
# Same shape as saas/cards/deploy.sh: native `sam deploy` of a prebuilt code dir (no docker, no sam build).
set -euo pipefail
export PYTHONWARNINGS=ignore
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="${FOOTBALL_REGION:-ap-south-1}"
STACK="${FOOTBALL_STACK:-elyoxe-football}"
SAM="${SAM_BIN:-$HERE/../whatsapp-agent/.venv-sam/bin/sam}"
[[ -x "$SAM" ]] || SAM="$(command -v sam || true)"
cd "$HERE"
if [ -z "${PY:-}" ]; then
  if [ -x .venv/bin/python ]; then PY=.venv/bin/python; elif python3 -c "" >/dev/null 2>&1; then PY=python3; else PY=python; fi
fi

out() { aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }

# live check: body in a variable, no pipes (CLAUDE.md traps); CloudFront objects are gzip -> --compressed
check() {
  local url="$1" want="$2" code body i
  for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
    body=$(curl -sS --compressed -m 20 -w $'\n%{http_code}' "$url" || true)
    code="${body##*$'\n'}"; body="${body%$'\n'*}"
    if [ "$code" = "200" ] && [[ "$body" == *"$want"* ]]; then echo "live ok  $code $url"; return 0; fi
    sleep 10
  done
  echo "live FAIL $code $url" >&2; return 1
}

live_checks() {
  local dom; dom=$(out DistributionDomain)
  [ -n "$dom" ] && [ "$dom" != "None" ] || { echo "no distribution domain in stack $STACK" >&2; exit 4; }
  check "https://$dom/index.json" '"competitions"'
  check "https://$dom/health.json" '"last_run"'
  check "https://$dom/live.json" '"matches"'
  check "https://$dom/comp/538/standings.json" '"groups"'
  echo "base url: https://$dom/"
}

if [ "${1:-}" = "--check" ]; then live_checks; exit 0; fi
[[ -n "$SAM" ]] || { echo "sam not found (set SAM_BIN)" >&2; exit 1; }

# 1. tests gate: nothing ships red
"$PY" -m pytest -q -x -p no:cacheprovider || { echo "tests failed — not deploying" >&2; exit 6; }

# 2. bundle: our modules + aarch64 wheels for the arm64 runtime (boto3 comes with the runtime)
rm -rf build/lambda && mkdir -p build/lambda
cp -r sources compute build/lambda/
cp poller.py analytics.py arabs.py more.py store.py config.py timeutil.py competitions.yaml stadiums.yaml teams_ar.yaml countries.yaml derbies.yaml alltime.yaml fifa_history.json coefficients.json build/lambda/
B=/root/workspace/research/tifo-2026-09-27/broadcast_by_country.json; [ -f "$B" ] && cp "$B" build/lambda/   # another agent's broadcast research (read only)
if [ -f names/players_ar.json ]; then mkdir -p build/lambda/names && cp names/players_ar.json build/lambda/names/; fi   # another agent's Arabic names (read only)
find build/lambda -name "__pycache__" -type d -prune -exec rm -rf {} +
"$PY" -m pip install -q --disable-pip-version-check --target build/lambda \
  --platform manylinux2014_aarch64 --implementation cp --python-version 3.13 --only-binary=:all: \
  -r requirements.txt
"$PY" - <<'EOF'
import sys; sys.path.insert(0, "build/lambda")
import poller, yaml, bs4, tzdata  # noqa: F401  (import check of the bundle itself)
print("bundle imports ok")
EOF

# 3. stack
"$SAM" deploy --template-file template.yaml --stack-name "$STACK" --region "$REGION" \
  --capabilities CAPABILITY_IAM --resolve-s3 --no-confirm-changeset --no-fail-on-empty-changeset \
  --tags product=elyoxe-football

FN=$(out FunctionName)
echo "stack $STACK: bucket $(out Bucket), distribution $(out DistributionId), function $FN"

# 4. one immediate run (async: the schedule may be running it already; reserved concurrency is 1)
aws lambda invoke --region "$REGION" --function-name "$FN" --invocation-type Event /dev/null >/dev/null || true
sleep 55
live_checks

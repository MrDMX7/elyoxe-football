#!/usr/bin/env bash
# deploy.sh — build تيفو and publish it: stack elyoxe-tifo-site (ap-south-1) = site bucket + CloudFront (+ /v1 -> data).
#   ./deploy.sh            build (--preview while there is no custom domain) + sync + invalidate + live check
#   ./deploy.sh --stack    also (re)deploy the CloudFormation stack first
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$HERE"
mkdir -p cache; exec 9>cache/deploy.lock
flock -n 9 || { echo "another tifo build/deploy is running; skipping" >&2; exit 0; }   # the hourly job and a manual run share out/
REGION=ap-south-1 STACK=elyoxe-tifo-site
out() { aws cloudformation describe-stacks --region $REGION --stack-name $STACK --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
if [ "${1:-}" = "--stack" ] || ! aws cloudformation describe-stacks --region $REGION --stack-name $STACK >/dev/null 2>&1; then
  aws cloudformation deploy --region $REGION --stack-name $STACK --template-file template.yaml --no-fail-on-empty-changeset
fi
BUCKET=$(out Bucket); DIST=$(out DistributionId); DOM=$(out DistributionDomain)
ALIASES=$(aws cloudfront get-distribution-config --id "$DIST" --query "DistributionConfig.Aliases.Quantity" --output text)
FLAG=--preview; [ "$ALIASES" != "0" ] && FLAG=""
node build.cjs $FLAG
# guard: a flaky fetch can yield a partial build, and `sync --delete` would then wipe live pages. Refuse a build that
# lost more than 15% of the last published page count.
NOW=$(find out -name index.html | wc -l); LAST=$(cat cache/last_pages 2>/dev/null || echo 0)
if [ "$LAST" -gt 0 ] && [ "$NOW" -lt $((LAST * 85 / 100)) ]; then echo "partial build: $NOW pages vs $LAST last time; not publishing" >&2; exit 7; fi
# assets are content-hashed -> 1 year; logos 7 days; pages 60 s (live data comes from /v1 anyway)
sync_assets(){ aws s3 sync out/assets "s3://$BUCKET/assets" --region $REGION --only-show-errors --cache-control "public,max-age=31536000,immutable"; }
sync_logos(){ aws s3 sync out/logo "s3://$BUCKET/logo" --region $REGION --only-show-errors --cache-control "public,max-age=604800"; }
sync_assets || { echo "assets sync hiccup; retrying" >&2; sleep 5; sync_assets; }   # one retry, as for the pages: a single S3 blip failed the 23:25 run
sync_logos || { echo "logo sync hiccup; retrying" >&2; sleep 5; sync_logos; }
sync_pages(){ aws s3 sync out "s3://$BUCKET" --region $REGION --only-show-errors --delete --exclude "assets/*" --exclude "logo/*" --exclude "next/*" --exclude "google*.html" --cache-control "public,max-age=60"; }
sync_pages || { echo "sync hiccup; retrying" >&2; sleep 5; sync_pages; }   # transient S3 stream errors on a few thousand small files
echo "$NOW" > cache/last_pages
# W4.7: pages, /og/, /tn/ and sw.js are served with max-age=60 (CachingOptimized honours it) and /assets/ is content-hashed, so the cache
# refreshes on its own; only the worker and the home page are purged, instead of evicting every crest and card each hour
aws cloudfront create-invalidation --distribution-id "$DIST" --paths "/sw.js" "/" --query Invalidation.Id --output text >/dev/null
# 445: IndexNow (Bing, Yandex, Seznam, Naver): the pages whose bytes changed in this build (build.cjs writes cache/indexnow.txt).
# The key file ships from static/; a refused or failed submit never fails the deploy.
INDEXNOW_KEY=8a5d11d3194545d5a4750dc4ede4a7ad
if [ -z "$FLAG" ] && [ -s cache/indexnow.txt ]; then
  python3 - "$INDEXNOW_KEY" <<'PY' || echo "indexnow: submit failed (not fatal)" >&2
import json, sys, urllib.request
key = sys.argv[1]; urls = [u for u in open("cache/indexnow.txt", encoding="utf-8").read().splitlines() if u][:10000]
body = json.dumps({"host": "tifo.elyoxe.com", "key": key, "keyLocation": f"https://tifo.elyoxe.com/{key}.txt", "urlList": urls}).encode()
req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8"})
print("indexnow:", len(urls), "urls ->", urllib.request.urlopen(req, timeout=30).status)
PY
fi
for p in / /c/uae-pro-league/ /v1/index.json; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --compressed "https://$DOM$p"); echo "$code https://$DOM$p"
done

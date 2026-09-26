#!/usr/bin/env bash
# deploy.sh — build تيفو and publish it: stack elyoxe-tifo-site (ap-south-1) = site bucket + CloudFront (+ /v1 -> data).
#   ./deploy.sh            build (--preview while there is no custom domain) + sync + invalidate + live check
#   ./deploy.sh --stack    also (re)deploy the CloudFormation stack first
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$HERE"
REGION=ap-south-1 STACK=elyoxe-tifo-site
out() { aws cloudformation describe-stacks --region $REGION --stack-name $STACK --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
if [ "${1:-}" = "--stack" ] || ! aws cloudformation describe-stacks --region $REGION --stack-name $STACK >/dev/null 2>&1; then
  aws cloudformation deploy --region $REGION --stack-name $STACK --template-file template.yaml --no-fail-on-empty-changeset
fi
BUCKET=$(out Bucket); DIST=$(out DistributionId); DOM=$(out DistributionDomain)
ALIASES=$(aws cloudfront get-distribution-config --id "$DIST" --query "DistributionConfig.Aliases.Quantity" --output text)
FLAG=--preview; [ "$ALIASES" != "0" ] && FLAG=""
node build.cjs $FLAG
# assets are content-hashed -> 1 year; logos 7 days; pages 60 s (live data comes from /v1 anyway)
aws s3 sync out/assets "s3://$BUCKET/assets" --region $REGION --only-show-errors --cache-control "public,max-age=31536000,immutable"
aws s3 sync out/logo "s3://$BUCKET/logo" --region $REGION --only-show-errors --cache-control "public,max-age=604800"
aws s3 sync out "s3://$BUCKET" --region $REGION --only-show-errors --delete --exclude "assets/*" --exclude "logo/*" --cache-control "public,max-age=60"
aws cloudfront create-invalidation --distribution-id "$DIST" --paths "/*" --query Invalidation.Id --output text >/dev/null
for p in / /c/uae-pro-league/ /v1/index.json; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --compressed "https://$DOM$p"); echo "$code https://$DOM$p"
done

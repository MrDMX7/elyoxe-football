#!/usr/bin/env bash
# Tifo's ticker: Lambda tifo-ticker + one EventBridge Scheduler schedule per job (UTC), each starting its GitHub workflow
# by workflow_dispatch (ticker.py). Idempotent: run again after editing the code or the times. All within AWS's free tiers.
#   bash infra/ticker/deploy.sh
# Also «سينما»'s refresh (MrDMX7/elyoxe-cinema, 7 times a day at :10 UAE; names carry the UAE time, the cron is UTC).
# Then, once: a fine-grained PAT (github.com/settings/personal-access-tokens: MrDMX7/elyoxe-football and
# MrDMX7/elyoxe-cinema, Actions read and write), stored with
#   aws ssm put-parameter --region ap-south-1 --name /elyoxe/tifo/github-dispatch-token --type SecureString --value <token>
set -euo pipefail
export MSYS_NO_PATHCONV=1      # Git Bash: keep /aws/lambda/… and /elyoxe/… as they are
R=ap-south-1; ACCT=574771023173; FN=tifo-ticker
HERE="$(cd "$(dirname "$0")" && pwd)"; command -v cygpath >/dev/null && HERE="$(cygpath -m "$HERE")"
TMP="$(mktemp -d)"; command -v cygpath >/dev/null && TMP="$(cygpath -m "$TMP")"   # Windows: aws.exe reads C:/… paths
cat > "$TMP/lambda-trust.json" <<'EOF'
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}
EOF
cat > "$TMP/lambda-policy.json" <<EOF
{"Version":"2012-10-17","Statement":[
 {"Effect":"Allow","Action":"ssm:GetParameter","Resource":"arn:aws:ssm:$R:$ACCT:parameter/elyoxe/tifo/github-dispatch-token"},
 {"Effect":"Allow","Action":["logs:CreateLogStream","logs:PutLogEvents"],"Resource":"arn:aws:logs:$R:$ACCT:log-group:/aws/lambda/$FN:*"}]}
EOF
cat > "$TMP/sched-trust.json" <<'EOF'
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"scheduler.amazonaws.com"},"Action":"sts:AssumeRole"}]}
EOF
cat > "$TMP/sched-policy.json" <<EOF
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"lambda:InvokeFunction","Resource":"arn:aws:lambda:$R:$ACCT:function:$FN"}]}
EOF
role(){ aws iam get-role --role-name "$1" >/dev/null 2>&1 || { aws iam create-role --role-name "$1" --assume-role-policy-document "file://$2" >/dev/null; sleep 10; }
        aws iam put-role-policy --role-name "$1" --policy-name "$1" --policy-document "file://$3"; }
role tifo-ticker-lambda "$TMP/lambda-trust.json" "$TMP/lambda-policy.json"
role tifo-ticker-scheduler "$TMP/sched-trust.json" "$TMP/sched-policy.json"

aws logs create-log-group --region $R --log-group-name /aws/lambda/$FN 2>/dev/null || true
aws logs put-retention-policy --region $R --log-group-name /aws/lambda/$FN --retention-in-days 7
python -c "import zipfile,sys; z=zipfile.ZipFile(sys.argv[1],'w'); z.write(sys.argv[2],'ticker.py'); z.close()" "$TMP/fn.zip" "$HERE/ticker.py"
if aws lambda get-function --region $R --function-name $FN >/dev/null 2>&1; then
  aws lambda update-function-code --region $R --function-name $FN --zip-file "fileb://$TMP/fn.zip" >/dev/null
else
  aws lambda create-function --region $R --function-name $FN --runtime python3.13 --architectures arm64 --handler ticker.handler \
    --role arn:aws:iam::$ACCT:role/tifo-ticker-lambda --timeout 30 --memory-size 128 --zip-file "fileb://$TMP/fn.zip" >/dev/null
fi

# job = workflow file = schedule (UTC; UAE is UTC+4) [= repo, when not elyoxe-football; the token must cover it]
while read -r name wf expr repo; do
  [ -n "$name" ] || continue
  IN="{\\\"workflow\\\":\\\"$wf\\\"}"
  [ -n "${repo:-}" ] && IN="{\\\"repo\\\":\\\"$repo\\\",\\\"workflow\\\":\\\"$wf\\\"}"
  T="{\"Arn\":\"arn:aws:lambda:$R:$ACCT:function:$FN\",\"RoleArn\":\"arn:aws:iam::$ACCT:role/tifo-ticker-scheduler\",\"Input\":\"$IN\",\"RetryPolicy\":{\"MaximumRetryAttempts\":3,\"MaximumEventAgeInSeconds\":600}}"
  op=create-schedule; aws scheduler get-schedule --region $R --name "$name" >/dev/null 2>&1 && op=update-schedule
  aws scheduler $op --region $R --name "$name" --schedule-expression "$expr" --flexible-time-window Mode=OFF --target "$T" >/dev/null
  echo "$name  $expr  -> ${repo:-MrDMX7/elyoxe-football} $wf"
done <<'EOF'
tifo-site tifo-site.yml cron(25 * * * ? *)
tifo-journal tifo-journal.yml cron(5/15 * * * ? *)
tifo-names tifo-names.yml cron(40 22 ? * SAT *)
tifo-newsletter tifo-newsletter.yml cron(0 14 ? * THU *)
tifo-database tifo-database.yml cron(10 0 * * ? *)
tifo-streams tifo-streams.yml cron(0/5 * * * ? *)
cinema-refresh-0010 cinema-refresh.yml cron(10 20 * * ? *) MrDMX7/elyoxe-cinema
cinema-refresh-0610 cinema-refresh.yml cron(10 2 * * ? *) MrDMX7/elyoxe-cinema
cinema-refresh-0910 cinema-refresh.yml cron(10 5 * * ? *) MrDMX7/elyoxe-cinema
cinema-refresh-1210 cinema-refresh.yml cron(10 8 * * ? *) MrDMX7/elyoxe-cinema
cinema-refresh-1510 cinema-refresh.yml cron(10 11 * * ? *) MrDMX7/elyoxe-cinema
cinema-refresh-1810 cinema-refresh.yml cron(10 14 * * ? *) MrDMX7/elyoxe-cinema
cinema-refresh-2110 cinema-refresh.yml cron(10 17 * * ? *) MrDMX7/elyoxe-cinema
EOF
rm -rf "$TMP"

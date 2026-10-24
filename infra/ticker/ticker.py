"""Tifo's ticker (2026-10-24): GitHub's own cron is best-effort and, for this repo, did not fire once in its first hours
public, so EventBridge Scheduler calls this Lambda on the jobs' times and it starts the workflow by workflow_dispatch.

The token is a fine-grained GitHub PAT with «Actions: read and write» on MrDMX7/elyoxe-football and (since 2026-10-24)
MrDMX7/elyoxe-cinema, in SSM SecureString /elyoxe/tifo/github-dispatch-token. No parameter = nothing happens (logged).
Event: {"workflow": "tifo-site.yml"} for Tifo, or {"repo": "MrDMX7/elyoxe-cinema", "workflow": "cinema-refresh.yml"} for
another repo the token covers (the repo defaults to the football one; "ref" defaults to main).
Deployed by infra/ticker/deploy.sh."""
import json, os, urllib.request

import boto3

REPO = os.environ.get("REPO", "MrDMX7/elyoxe-football")
PARAM = os.environ.get("TOKEN_PARAM", "/elyoxe/tifo/github-dispatch-token")


def handler(event, context):
    wf = event.get("workflow")
    repo = event.get("repo") or REPO
    ref = event.get("ref") or "main"
    try:
        token = boto3.client("ssm").get_parameter(Name=PARAM, WithDecryption=True)["Parameter"]["Value"]
    except Exception as e:
        print(json.dumps({"repo": repo, "workflow": wf, "skipped": f"no token: {type(e).__name__}"}))
        return {"ok": False}
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/workflows/{wf}/dispatches", method="POST",
                                 data=json.dumps({"ref": ref}).encode(),
                                 headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                                          "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "tifo-ticker"})
    try:
        st = urllib.request.urlopen(req, timeout=20).status
    except urllib.error.HTTPError as e:
        st = e.code
    print(json.dumps({"repo": repo, "workflow": wf, "status": st}))
    if st != 204:
        raise RuntimeError(f"dispatch {repo} {wf}: HTTP {st}")   # EventBridge Scheduler retries
    return {"ok": True}

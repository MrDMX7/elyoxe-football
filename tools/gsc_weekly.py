"""Every week, what each article type brought from Google (spec, «Trust and measurement»): Search Console clicks and impressions
of /news/<id>/ pages, grouped by type, for the 7 days that ended 3 days ago (Search Console's delay). One email to hello@, once
a week (state/articles/weekly.json). Needs GSC_SA_JSON (a service account the owner added as a user of the property) and
GSC_SITE (the property, e.g. "sc-domain:elyoxe.com"); without them it says so and exits 0."""
import json, os, re, sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
PREFIX = [("fpl-", "fantasy"), ("r-", "report"), ("n-", "news"), ("m-", "before the match"), ("l-", "live"), ("t-", "ratings"),
          ("s-", "table"), ("a-", "arab players"), ("f-", "evergreen")]


def by_type(rows):
    out = {}
    for r in rows:
        m = re.search(r"/news/([^/]+)/", r["keys"][0])
        if not m:
            continue
        kind = next((k for p, k in PREFIX if m.group(1).startswith(p)), None)
        if not kind:
            continue
        o = out.setdefault(kind, {"clicks": 0, "impressions": 0, "pages": 0})
        o["clicks"] += r.get("clicks", 0); o["impressions"] += r.get("impressions", 0); o["pages"] += 1
    return out


def query(site, start, end):
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    creds = service_account.Credentials.from_service_account_info(json.loads(os.environ["GSC_SA_JSON"]),
                                                                  scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    s = AuthorizedSession(creds)
    url = f"https://searchconsole.googleapis.com/webmasters/v3/sites/{site.replace(':', '%3A').replace('/', '%2F')}/searchAnalytics/query"
    body = {"startDate": start.isoformat(), "endDate": end.isoformat(), "dimensions": ["page"], "rowLimit": 25000,
            "dimensionFilterGroups": [{"filters": [{"dimension": "page", "operator": "contains", "expression": "/news/"}]}]}
    r = s.post(url, json=body, timeout=60); r.raise_for_status()
    return r.json().get("rows") or []


def main():
    if not os.environ.get("GSC_SA_JSON") or not os.environ.get("GSC_SITE"):
        print(json.dumps({"gsc_weekly": "no GSC_SA_JSON / GSC_SITE, skipped"})); return 0
    from store import Store, S3Backend
    store = Store(S3Backend(os.environ.get("BUCKET", "elyoxe-football-574771023173-ap-south-1")))
    end = date.today() - timedelta(days=3); start = end - timedelta(days=6)
    st = store.get_state("articles/weekly.json") or {}
    if st.get("last_end") and date.fromisoformat(st["last_end"]) > end - timedelta(days=7):
        return 0
    got = by_type(query(os.environ["GSC_SITE"], start, end))
    lines = [f"{k}: {v['clicks']} نقرة، {v['impressions']} ظهور، {v['pages']} صفحة" for k, v in sorted(got.items(), key=lambda x: -x[1]["clicks"])]
    import boto3
    boto3.client("ses", region_name="ap-south-1").send_email(
        Source="تيفو <hello@elyoxe.com>", Destination={"ToAddresses": ["hello@elyoxe.com"]},
        Message={"Subject": {"Data": f"مقالات تيفو في قوقل: {start} إلى {end}"},
                 "Body": {"Text": {"Data": "\n".join(lines) or "ولا مقال جاب ظهور في قوقل هالأسبوع."}}})
    store.put_state("articles/weekly.json", {"last_end": end.isoformat(), "by_type": got})
    print(json.dumps({"gsc_weekly": got}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

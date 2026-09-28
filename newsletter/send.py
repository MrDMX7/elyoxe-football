"""تيفو weekly newsletter (feature 184) — every Thursday 18:00 UAE from the phone's scheduler (run-job.sh tifo-news).

Content is numbers only (no generated prose, so no approval gate): last 7 days' results and the top of the table for the
Arab top leagues, the Arab match of the week and the week's biggest matches, plus a link to Tifo Cast if the owner has
approved it (site/ai/approved.json). Personalised by the subscriber's country (their league first).
Subscribers: DynamoDB table "cards", pk TIFONEWS#<email>, status active (double opt-in via /api/tifo/subscribe).
  python3 newsletter/send.py [--dry-run you@x] [--limit N]
Sends at most 12/s (SES MaxSendRate 14) and stops on any SES throttle; every mail has a one-click unsubscribe link.
"""
import argparse, datetime as dt, gzip, html, json, os, sys, time, urllib.parse, urllib.request
import boto3

DATA, SITE = "https://tifo.elyoxe.com/v1", "https://tifo.elyoxe.com"
HERE = os.path.dirname(os.path.abspath(__file__))
ARAB = {"AE": 538, "SA": 536, "QA": 535, "EG": 519, "MA": 530, "DZ": 516, "TN": 544, "IQ": 524, "KW": 529}

def get(p):
    try:
        raw = urllib.request.urlopen(f"{DATA}/{p}", timeout=30).read()
        return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    except Exception:
        return None

def e(s): return html.escape(str(s or ""))
def tn(t): return (t or {}).get("name_ar") or (t or {}).get("name") or ""

def league_block(cid, index):
    c = next((x for x in index["competitions"] if x["id"] == cid), None); fx = get(f"comp/{cid}/fixtures.json"); st = get(f"comp/{cid}/standings.json")
    if not c or not fx: return ""
    now = dt.datetime.utcnow(); wk = now - dt.timedelta(days=7)
    res = [m for m in fx["matches"] if m.get("status") == "finished" and m.get("kickoff_utc") and dt.datetime.fromisoformat(m["kickoff_utc"][:19]) > wk]
    rows = ((st or {}).get("groups") or [{}])[0].get("rows", [])[:4]
    out = f'<h3 style="margin:18px 0 6px;font-size:17px"><a href="{SITE}/c/{c["key"]}/" style="color:#0A2620">{e(c["name_ar"])}</a></h3>'
    if res:
        out += "".join(f'<div style="padding:3px 0;border-bottom:1px dashed #CDD3CC">{e(tn(m["home"]))} <b>{m["score"]["home"]} - {m["score"]["away"]}</b> {e(tn(m["away"]))}</div>' for m in res[:10])
    if rows:
        out += '<p style="margin:8px 0 0;color:#5C6660;font-size:14px">الصدارة: ' + "، ".join(f'{r["rank"]}. {e(tn(r["team"]))} ({r["pts"]})' for r in rows) + "</p>"
    return out

def issue(country, index, week_html, cast):
    order = [ARAB[country]] if country in ARAB else []
    order += [c for c in (538, 536, 519, 530, 535) if c not in order]
    blocks = "".join(league_block(c, index) for c in order[:4])
    return f"""<div dir="rtl" style="font-family:Tahoma,Arial,sans-serif;font-size:15px;line-height:1.8;color:#0E1512;max-width:640px;margin:auto">
<div style="background:#0A2620;color:#F6F7F2;padding:16px 20px"><b style="font-size:22px">تيفو</b> <span style="color:#B9C7C0">نشرة الأسبوع</span></div>
<div style="padding:8px 20px">{week_html}{blocks}{cast}
<p style="margin-top:22px"><a href="{SITE}/" style="display:inline-block;background:#0A2620;color:#F6F7F2;text-decoration:none;padding:10px 22px">افتح تيفو</a></p></div></div>"""

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run"); ap.add_argument("--limit", type=int, default=5000); a = ap.parse_args()
    index = get("index.json") or {"competitions": []}
    mw = get("arabs/match-of-week.json"); week_html = ""
    if mw and mw.get("match"):
        m = mw["match"]; week_html = f'<h3 style="margin:14px 0 6px">مباراة الأسبوع العربية</h3><p><a href="{SITE}/m/{m["id"]}/" style="color:#0A2620"><b>{e(tn(m["home"]))} و{e(tn(m["away"]))}</b></a></p>'
    # «تيفو الأسبوع» (417): the feed image weekly.py made this week (Thursday 15:00), linked to /week/
    iso = dt.date.today().isocalendar(); wkf = os.path.join(HERE, "..", "site", "cache", "week", f"week-{iso[0]}-{iso[1]:02d}.json")
    if os.path.exists(wkf):
        wk = json.load(open(wkf))["week"]
        week_html = (f'<p style="margin:14px 0"><a href="{SITE}/week/"><img src="{SITE}/og/week-{wk}-feed.png" width="600" alt="تيفو الأسبوع: أرقام الأسبوع في الكورة العربية" '
                     f'style="display:block;width:100%;max-width:600px;height:auto;border:0"></a></p>') + week_html
    appr = json.load(open(os.path.join(HERE, "..", "site", "ai", "approved.json")))
    cast = f'<p><a href="{SITE}/cast/">اسمع حلقة تيفو كاست هالأسبوع</a></p>' if appr.get("podcast") else ""
    ses = boto3.client("sesv2", region_name="ap-south-1"); subs = []
    if a.dry_run: subs = [{"email": a.dry_run, "country": "AE", "token": "dry"}]
    else:
        tbl = boto3.resource("dynamodb", region_name="ap-south-1").Table("cards"); kw = {"FilterExpression": "begins_with(pk, :p) AND #s = :a", "ExpressionAttributeValues": {":p": "TIFONEWS#", ":a": "active"}, "ExpressionAttributeNames": {"#s": "status"}}
        while True:
            r = tbl.scan(**kw); subs += r.get("Items", [])
            if "LastEvaluatedKey" not in r: break
            kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]
    cache, sent = {}, 0
    for sbs in subs[:a.limit]:
        c = sbs.get("country") or "AE"
        if c not in cache: cache[c] = issue(c, index, week_html, cast)
        unsub = f"{SITE}/api/tifo/unsub?t={urllib.parse.quote(sbs.get('token', ''))}&e={urllib.parse.quote(sbs['email'])}"
        body = cache[c] + f'<p dir="rtl" style="font-family:Tahoma,Arial,sans-serif;color:#5C6660;font-size:12px;text-align:center"><a href="{unsub}" style="color:#5C6660">إلغاء الاشتراك</a></p>'
        try:
            ses.send_email(FromEmailAddress="تيفو <tifo@elyoxe.com>", ReplyToAddresses=["hello@elyoxe.com"], Destination={"ToAddresses": [sbs["email"]]},
                           Content={"Simple": {"Subject": {"Data": "نشرة تيفو: أسبوع الكورة العربية", "Charset": "UTF-8"}, "Body": {"Html": {"Data": body, "Charset": "UTF-8"}},
                                               "Headers": [{"Name": "List-Unsubscribe", "Value": f"<{unsub}>"}]}})
            sent += 1; time.sleep(1 / 12)
        except Exception as ex:
            print("stop:", repr(ex)[:200]); break
    print(f"newsletter: {sent}/{len(subs)} sent")

if __name__ == "__main__":
    main()

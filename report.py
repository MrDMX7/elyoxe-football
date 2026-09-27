"""Private weekly Tifo accuracy report (item 290): e-mailed to the owner, never published to v1/.

Reads state/arab_ratings.json `season_preds` (every pre-match prediction of the current season, made by
the sequential rating before it saw the match) and reports, per competition and overall, for the past 7
days and season to date: top-pick hit rate, Brier (3-class sum) against league base rates, calibration
buckets of the top-pick probability, and the biggest misses. Arabic, simple HTML, sent through SES
(ap-south-1) from contact@elyoxe.com, the verified sender automation/contact-form uses.
Lambda `elyoxe-football-report`, EventBridge cron(0 4 ? * MON *) = Monday 08:00 UAE.
"""
import html, json, os
from datetime import timedelta

import config
from compute import rating as R
from store import Store, S3Backend
from timeutil import now_utc, parse_utc

TO = os.environ.get("REPORT_TO", "dmxalkaabi@gmail.com")
FROM = os.environ.get("REPORT_FROM", "contact@elyoxe.com")
BASE = (0.44, 0.284, 0.276)          # Arab-clubs training base rates (docs/TIFO-RATING.md)


def stats(preds):
    n = len(preds)
    if not n:
        return None
    hits = sum(1 for x in preds if max(range(3), key=lambda i: x["p"][i]) == x["outcome"])
    b = R.brier(preds)
    bb = R.brier([{"p": BASE, "outcome": x["outcome"]} for x in preds])
    buckets = {}
    for x in preds:
        top = max(x["p"])
        k = f"{int(top * 10) / 10:.1f}"
        c = buckets.setdefault(k, [0, 0])
        c[0] += 1
        c[1] += 1 if max(range(3), key=lambda i: x["p"][i]) == x["outcome"] else 0
    return {"n": n, "hit": round(100 * hits / n, 1), "brier": round(b, 4), "brier_base": round(bb, 4),
            "skill": round(100 * (1 - b / bb), 1) if bb else None,
            "buckets": {k: [v[0], round(100 * v[1] / v[0])] for k, v in sorted(buckets.items())}}


def build(sp, names, now):
    preds = [{"id": r[0], "ko": r[1], "comp": r[2], "h": r[3], "a": r[4], "p": r[5], "outcome": r[6]} for r in sp]
    week = [x for x in preds if x["ko"] and now - parse_utc(x["ko"]) <= timedelta(days=7)]
    comps = {c["id"]: c["name_ar"] for c in config.competitions()}
    lab = ["فوز صاحب الأرض", "تعادل", "فوز الضيف"]

    def table(rows):
        out = ["<table border=1 cellpadding=4 style='border-collapse:collapse'><tr><th>البطولة</th><th>مباريات</th>"
               "<th>الاختيار الأول صحيح</th><th>Brier</th><th>Brier المعدلات الأساسية</th><th>المهارة</th></tr>"]
        for name, st in rows:
            if st:
                out.append(f"<tr><td>{html.escape(name)}</td><td>{st['n']}</td><td>{st['hit']}%</td><td>{st['brier']}</td>"
                           f"<td>{st['brier_base']}</td><td>{st['skill']}%</td></tr>")
        out.append("</table>")
        return "".join(out)

    def section(title, xs):
        by = {}
        for x in xs:
            by.setdefault(x["comp"], []).append(x)
        rows = [("الكل", stats(xs))] + [(comps.get(c, str(c)), stats(v)) for c, v in sorted(by.items(), key=lambda kv: -len(kv[1]))]
        allst = stats(xs)
        cal = ""
        if allst:
            cal = "<p>المعايرة (احتمال الاختيار الأول ← نسبة الإصابة الفعلية):</p><ul>" + "".join(
                f"<li>{k}–{float(k) + 0.1:.1f}: {v[0]} مباراة، أصاب {v[1]}%</li>" for k, v in allst["buckets"].items()) + "</ul>"
        miss = sorted(xs, key=lambda x: x["p"][x["outcome"]])[:8]
        mtxt = "<p>أكبر المفاجآت:</p><ol>" + "".join(
            f"<li>{html.escape(names.get(str(x['h']), str(x['h'])))} × {html.escape(names.get(str(x['a']), str(x['a'])))} "
            f"({(x['ko'] or '')[:10]}، {html.escape(comps.get(x['comp'], ''))}): النتيجة {lab[x['outcome']]} "
            f"وكان احتمالها {round(100 * x['p'][x['outcome']])}%</li>" for x in miss) + "</ol>"
        return f"<h2>{title}</h2>{table(rows)}{cal}{mtxt}"

    body = (f"<div dir='rtl' style='font-family:Arial,sans-serif'><h1>تقرير دقة توقعات Tifo</h1>"
            f"<p>أسبوع ينتهي {now:%Y-%m-%d}. Brier: الأقل أفضل (0 مثالي، 0.667 لتوقع الثلث لكل نتيجة). "
            f"المهارة = نسبة التحسن عن المعدلات الأساسية.</p>"
            f"{section('الأسبوع الماضي', week)}{section('الموسم حتى الآن', preds)}"
            f"<p style='color:#666'>خاص للمالك، غير منشور. المصدر: state/arab_ratings.json.</p></div>")
    return body, stats(week), stats(preds)


def handler(event, context):
    store = Store(S3Backend(os.environ["BUCKET"]))
    ar = store.get_state("arab_ratings.json", {}) or {}
    names = (store.get_state("names_ar.json", {}) or {}).get("teams", {})
    names.update(config.team_overrides())
    now = now_utc()
    body, wk, season = build(ar.get("season_preds") or [], names, now)
    import boto3
    subj = f"Tifo: دقة التوقعات حتى {now:%Y-%m-%d}" + (f" (الأسبوع {wk['hit']}% · Brier {wk['brier']})" if wk else "")
    if event and event.get("dry_run"):
        return {"subject": subj, "week": wk, "season": season, "html_len": len(body)}
    boto3.client("ses", region_name="ap-south-1").send_email(
        Source=f"Tifo <{FROM}>", Destination={"ToAddresses": [TO]},
        Message={"Subject": {"Data": subj, "Charset": "UTF-8"}, "Body": {"Html": {"Data": body, "Charset": "UTF-8"}}})
    return {"sent": True, "week": wk, "season": season}

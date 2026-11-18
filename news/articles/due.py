"""Finished priority matches from the all-day files (v1/all/<yyyymmdd>.json: leagues[].matches[] with id, utc, status,
home/away = [team id, Arabic name, score]). The caller passes today's and yesterday's UAE days and drops what it has written."""
from . import priority


def finished_priority(day_docs, awarded):
    seen, out = set(), []
    for doc in day_docs:
        for lg in (doc or {}).get("leagues") or []:
            for m in lg.get("matches") or []:
                mid = m.get("id")
                if mid in seen or m.get("status") != "finished" or mid in awarded:
                    continue
                if priority.is_priority(lg["id"], m["home"][0], m["away"][0]):
                    seen.add(mid)
                    out.append((m.get("utc") or "", mid))
    return [mid for _, mid in sorted(out)]

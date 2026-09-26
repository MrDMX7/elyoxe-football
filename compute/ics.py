"""Per-team iCalendar feeds (RFC 5545) that follow fixture changes.

Subscribing clients re-download the whole feed (REFRESH-INTERVAL / X-PUBLISHED-TTL: 6 h). Each match
keeps one UID (<matchId>@football.elyoxe) for life, so a moved kickoff updates the existing event
instead of duplicating it; SEQUENCE goes up by one each time the kickoff changes (tracked in state).
DTSTART/DTEND are UTC ("Z"). Matches without a fixed time (TBC) are all-day events on their date;
matches without a date are left out. Summaries are Arabic ("الجزيرة × العين").
"""
from datetime import datetime, timedelta

from timeutil import parse_utc, UAE, now_utc

PRODID = "-//elyoxe//football//AR"
DURATION = timedelta(minutes=115)


def _esc(s):
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line):
    """75-octet line folding."""
    b = line.encode("utf-8")
    if len(b) <= 75:
        return line
    out, cur = [], b""
    for ch in line:
        e = ch.encode("utf-8")
        if len(cur) + len(e) > (75 if not out else 74):
            out.append(cur.decode("utf-8"))
            cur = b""
        cur += e
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def _dt(d: datetime):
    return d.strftime("%Y%m%dT%H%M%SZ")


def bump_sequences(matches, seq_state: dict) -> dict:
    """seq_state {match_id: [kickoff_utc, seq]} updated in place; returns {match_id: seq}."""
    out = {}
    for m in matches:
        key = str(m.get("id") or m.get("ext_id"))
        ko = m.get("kickoff_utc") or m.get("date_uae")
        prev = seq_state.get(key)
        if prev is None:
            seq_state[key] = [ko, 0]
        elif prev[0] != ko:
            seq_state[key] = [ko, prev[1] + 1]
        out[key] = seq_state[key][1]
    return out


def team_calendar(team: dict, matches: list[dict], comp_names: dict, seqs: dict, venues: dict | None = None) -> str:
    name = team.get("name_ar") or team.get("name")
    stamp = _dt(now_utc())
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             f"X-WR-CALNAME:{_esc('مباريات ' + name)}", "X-WR-TIMEZONE:Asia/Dubai",
             "REFRESH-INTERVAL;VALUE=DURATION:PT6H", "X-PUBLISHED-TTL:PT6H"]
    for m in sorted(matches, key=lambda m: m.get("kickoff_utc") or m.get("date_uae") or "9999"):
        key = str(m.get("id") or m.get("ext_id"))
        ko = parse_utc(m.get("kickoff_utc"))
        if not ko and not m.get("date_uae"):
            continue
        h = m["home"].get("name_ar") or m["home"]["name"]
        a = m["away"].get("name_ar") or m["away"]["name"]
        summary = f"{h} × {a}"
        if m.get("score") and m.get("status") == "finished":
            summary = f"{h} {m['score']['home']}-{m['score']['away']} {a}"
        comp = comp_names.get(m.get("comp")) or m.get("comp_name") or ""
        desc = comp + (f" · الجولة {m['round']}" if m.get("round") and str(m["round"]).isdigit() else "")
        lines += ["BEGIN:VEVENT", f"UID:{key}@football.elyoxe", f"DTSTAMP:{stamp}", f"SEQUENCE:{seqs.get(key, 0)}"]
        if ko and not m.get("time_tbd"):
            lines += [f"DTSTART:{_dt(ko)}", f"DTEND:{_dt(ko + DURATION)}"]
        else:
            d = (ko.astimezone(UAE).strftime("%Y%m%d") if ko else m["date_uae"].replace("-", ""))
            nd = (datetime.strptime(d, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")
            lines += [f"DTSTART;VALUE=DATE:{d}", f"DTEND;VALUE=DATE:{nd}"]
            desc += " · الموعد لم يُحدَّد بعد"
        lines += [f"SUMMARY:{_esc(summary)}", f"DESCRIPTION:{_esc(desc)}"]
        v = (venues or {}).get(key)
        if v:
            lines.append(f"LOCATION:{_esc(v)}")
        if m.get("status") in ("postponed", "cancelled"):
            lines.append("STATUS:CANCELLED")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(x) for x in lines) + "\r\n"

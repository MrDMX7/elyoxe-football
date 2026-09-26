"""Records at stake and fun facts before a match (comp/{id}/facts.json).

Input: the league's match history (FotMob, 2010/11 onward) plus the current season. Every "record" is
qualified with that window (FotMob's data is not the club's full history). Arabic text uses Western
digits. Items are short and factual: a kind, the numbers, and a sentence.
Streaks: unbeaten, winning, winless, losing, scoring, clean sheets (all league games), home unbeaten
(if the team is at home next) or away unbeaten (if away), plus the team's league record on the
match's weekday (UAE time) and the head-to-head record in the league.
"""
from datetime import datetime

from timeutil import UAE, parse_utc

WEEKDAYS_AR = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
KINDS = {  # key: (label_ar, test on (goals for, goals against, home?), minimum run worth saying)
    "unbeaten": ("مباريات دون خسارة", lambda f, a, h: f >= a, 4),
    "winning": ("انتصارات متتالية", lambda f, a, h: f > a, 3),
    "winless": ("مباريات دون فوز", lambda f, a, h: f <= a, 4),
    "losing": ("هزائم متتالية", lambda f, a, h: f < a, 3),
    "scoring": ("مباريات متتالية يسجل فيها", lambda f, a, h: f > 0, 6),
    "clean_sheets": ("مباريات متتالية بشباك نظيفة", lambda f, a, h: a == 0, 3),
}


def team_games(rows, tid, venue=None):
    """Chronological [(ko, f, a, home?, opponent, season)] for a team from finished history rows."""
    out = []
    for r in rows:
        if tid not in (r["h"], r["a"]):
            continue
        home = r["h"] == tid
        if venue == "home" and not home or venue == "away" and home:
            continue
        f, a = (r["hs"], r["as"]) if home else (r["as"], r["hs"])
        out.append((r["ko"] or "", f, a, home, r["a"] if home else r["h"], r["season"]))
    return sorted(out)


def runs(games, test):
    """(current run, longest run, season of the longest run's end)."""
    cur = best = 0
    best_season = None
    for ko, f, a, h, opp, season in games:
        cur = cur + 1 if test(f, a, h) else 0
        if cur > best:
            best, best_season = cur, season
    return cur, best, best_season


def since_label(rows):
    first = min((r["season"] for r in rows if r.get("season")), default=None)
    return first


def match_facts(rows, match, names_ar, window):
    """rows: finished league history rows (all seasons incl. current). match: normalized upcoming match."""
    items = []
    hid, aid = match["home"]["id"], match["away"]["id"]
    ko = parse_utc(match.get("kickoff_utc"))
    since = f"منذ {window} (بيانات FotMob)"
    for tid, side in ((hid, "home"), (aid, "away")):
        name = names_ar.get(str(tid)) or (match[side].get("name_ar") or match[side]["name"])
        games = team_games(rows, tid)
        if not games:
            continue
        for key, (label, test, minimum) in KINDS.items():
            cur, best, best_season = runs(games, test)
            if cur >= minimum:
                at_stake = cur + 1 >= best
                txt = f"{name}: {cur} {label}"
                if at_stake and best > 0:
                    txt += (f"، ومباراة أخرى تعادل رقمه الأطول {best} {since}" if cur + 1 == best
                            else f"، وهو أطول رقم له {since}" if cur == best else "")
                else:
                    txt += f"؛ أطول سلسلة له {best} {since}"
                items.append({"team": tid, "kind": key, "current": cur, "record": best, "record_season": best_season,
                              "record_at_stake": at_stake, "text_ar": txt})
        venue = "home" if side == "home" else "away"
        vg = team_games(rows, tid, venue)
        cur, best, best_season = runs(vg, lambda f, a, h: f >= a)
        if cur >= 5:
            where = "على أرضه" if venue == "home" else "خارج أرضه"
            items.append({"team": tid, "kind": f"{venue}_unbeaten", "current": cur, "record": best,
                          "record_season": best_season, "record_at_stake": cur + 1 >= best,
                          "text_ar": f"{name}: {cur} مباريات {where} دون خسارة؛ الأطول {best} {since}"})
        if ko:
            wd = ko.astimezone(UAE).weekday()
            day = [g for g in games if g[0] and parse_utc(g[0]).astimezone(UAE).weekday() == wd]
            if len(day) >= 10:
                w = sum(1 for g in day if g[1] > g[2])
                d = sum(1 for g in day if g[1] == g[2])
                l_ = len(day) - w - d
                items.append({"team": tid, "kind": "weekday", "weekday": wd, "played": len(day), "won": w, "drawn": d, "lost": l_,
                              "win_pct": round(100 * w / len(day)),
                              "text_ar": f"{name} يوم {WEEKDAYS_AR[wd]} في الدوري: {w} فوز و{d} تعادل و{l_} خسارة "
                                         f"({round(100 * w / len(day))}% انتصارات) {since}"})
    h2h = [g for g in team_games(rows, hid) if g[4] == aid]
    if h2h:
        w = sum(1 for g in h2h if g[1] > g[2])
        d = sum(1 for g in h2h if g[1] == g[2])
        l_ = len(h2h) - w - d
        last = h2h[-1]
        hn = names_ar.get(str(hid)) or match["home"]["name"]
        an = names_ar.get(str(aid)) or match["away"]["name"]
        items.append({"team": None, "kind": "h2h", "played": len(h2h), "home_team_won": w, "drawn": d, "away_team_won": l_,
                      "last": {"date": last[0][:10], "for": last[1], "against": last[2], "home": last[3]},
                      "text_ar": f"{hn} و{an} في الدوري {since}: {len(h2h)} مباراة، {w} فوز لـ{hn} و{d} تعادل و{l_} فوز لـ{an}"})
    return items

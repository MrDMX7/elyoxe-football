"""Magic numbers for round-robin leagues: points each team still needs to GUARANTEE a finishing band
(title, each Asian/European place band, avoiding relegation), and whether it is already clinched or
already out of reach.

Guarantee = worst case on points only:
  * every rival wins all its remaining games (maxpts = pts + 3 x remaining), even when two rivals
    still have to play each other (so the number is conservative: an upper bound);
  * a tie on points counts against us (tie-breakers are ignored), so we need strictly more.
Remaining games = matches_per_team (competitions.yaml) - played, because FotMob publishes only the
rounds already dated (UAE Pro League: 42 of 182 matches on 2026-09-26).

For a band "finish in the top k" and team T with final points pts_T + x:
  T is safe when fewer than k rivals can reach >= pts_T + x.
  needed(T, k) = max(0, kth_largest(maxpts of rivals) + 1 - pts_T)
  clinched when needed == 0; "own hands" when needed <= 3 x remaining(T);
  eliminated when at least k rivals already have MORE points than T can ever reach (pts > maxpts_T).
Bands come from the standings legend (FotMob `legend[].indices`): e.g. Pro League 2026/27 =
ranks 1-2 AFC Champions League Elite, 3 ACL Elite qualification, 4 ACL Two, 13-14 relegation.
"""


def _band_targets(n_teams, legend):
    """[(key, label, k)] where k = must finish in the top k. Relegation zone -> stay above it."""
    targets = [("title", "Title", 1)]
    seen = {1}
    for lg in legend or []:
        ranks = sorted(lg.get("ranks") or [])
        if not ranks:
            continue
        label = lg.get("label") or ""
        if "releg" in (lg.get("key") or "").lower() or "releg" in label.lower():
            k = min(ranks) - 1
            if 0 < k < n_teams and k not in seen:
                targets.append(("safety", "Avoid relegation" + (" (play-off)" if "play" in label.lower() else ""), k))
                seen.add(k)
        elif ranks[0] <= n_teams // 2:
            k = max(ranks)
            if k not in seen:
                targets.append((f"top{k}", label, k))
                seen.add(k)
    return targets


def magic_numbers(standings: dict, matches_per_team: int) -> dict | None:
    if not standings or len(standings.get("groups") or []) != 1 or not matches_per_team:
        return None
    rows = standings["groups"][0]["rows"]
    n = len(rows)
    if n < 3:
        return None
    teams = []
    for r in rows:
        played = r.get("played") or 0
        rem = max(0, matches_per_team - played)
        teams.append({"id": r["team"]["id"], "pts": r["pts"], "remaining": rem, "max": r["pts"] + 3 * rem})
    targets = _band_targets(n, standings.get("legend"))
    out = {"method": "points-only guarantee; rivals assumed to win every remaining game; ties count against",
           "matches_per_team": matches_per_team, "bands": [{"key": k, "label": lbl, "top": top} for k, lbl, top in targets],
           "teams": {}}
    for t in teams:
        rivals = [x for x in teams if x["id"] != t["id"]]
        rmax = sorted((x["max"] for x in rivals), reverse=True)
        per = {}
        for key, _lbl, k in targets:
            kth = rmax[k - 1] if k - 1 < len(rmax) else -1
            needed = max(0, kth + 1 - t["pts"])
            above_reach = sum(1 for x in rivals if x["pts"] > t["max"])
            if needed == 0:
                state = "clinched"
            elif above_reach >= k:
                state = "eliminated"
            else:
                state = "open"
            per[key] = {"needed": needed if state == "open" else 0 if state == "clinched" else None,
                        "state": state, "own_hands": state == "open" and needed <= 3 * t["remaining"],
                        "wins_needed": (-(-needed // 3)) if (state == "open" and needed <= 3 * t["remaining"]) else None}
        out["teams"][str(t["id"])] = {"pts": t["pts"], "remaining": t["remaining"], "max": t["max"], **per}
    return out

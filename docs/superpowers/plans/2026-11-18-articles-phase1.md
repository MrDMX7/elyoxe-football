# Tifo articles, Phase 1: match reports — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After the final whistle of every match in a priority competition, Tifo writes a 300-400 word Arabic match report with Claude Sonnet 5.5. The report is checked against Tifo's own data and published at `tifo.elyoxe.com/news/r-<match id>/` with a real photo, `NewsArticle` data and a Google News sitemap. It is then posted to X from the laptop. The spend stops at $180 a month.

**Architecture:** A new package `news/articles/` runs as a step of the 15-minute journal job on GitHub Actions. The steps are:
- Find the finished priority matches (`due.py`).
- Build each match's fact sheet from the public `v1/` files (`facts.py`).
- Call the Claude API (`write.py`), and check the text, rewriting once on failure (`check.py`).
- Pick a photo (`photo.py`).
- Publish `v1/news/a/<id>.json` and the list `v1/news/articles.json` (`publish.py`).

The hourly site build reads those files and writes the article pages, the trust pages and `sitemap-news.xml` (`site/lib/articles.cjs`). A laptop task posts the new reports to X through the logged-in Chrome (`content/social/tifo/article_x.py` in the workspace repo).

**Tech Stack:** Python 3.13 and the `anthropic` SDK (Messages API with structured output). The rest is already used in the repo: boto3, Pillow and pytest. Node 24 for the site build (`node:test`). Playwright-core for the X poster.

**Spec:** the design (`2026-11-18-articles-design.md`) is kept in the owner's private workspace repo, `content/social/tifo/articles-test/2026-11-18/`, because it carries the owner's own words and account details. Phase 1 is the first row of its Phases table. Read its sections «Article types», «The pipeline» and «Cost» before starting.

## Global Constraints

- Language: written Arabic as Kooora writes it (فصحى صحفية), not dialect. Western digits (0-9), always.
- Match report length: 300-400 words (owner, spec review: short, like Kooora).
- Model: `claude-sonnet-5-5` for match reports. It is set per type in `news/articles/types.json`, so a type can move to another model with a one-line change.
- Byline: «تحرير تيفو» on every article, with an «من نحن» page.
- Priority competitions: the UAE league and cups, Saudi, Qatar, Egypt, Morocco, the AFC Champions League (Elite and Two), the UEFA Champions League, the big five, and every match of an Arab national team. The list lives in config, not code.
- Every article has a real photo of its subject, at least 1200 px wide, copied to Tifo's own storage. The pages carry `max-image-preview:large`.
- Spend: the model and the spend of every call go to `state/articles/spend.json`. At **$180 in a calendar month** writing stops until the month ends.
- The key is the repo secret `ANTHROPIC_API_KEY`. The repo is public, so the key never goes in a file.
- The writer may only state what the fact sheet holds. Every score, minute, number and name in the article must be in the fact sheet. Latin letters left in the text fail the check.
- The fact sheet carries every derived number ready-made, and states each team's games played and any postponed round next to the table. On 11-18, ADNOC round 7 had been postponed, so after round 8 every team had played 7.
- Never MBC Action (owner rule 2026-10-09). This does not come up in a match report, but the style guide carries it.
- Existing pages and sitemaps are not changed, beyond the additions listed in Task 10 (owner: option 3).
- Writing a file in Python: `write_text(..., encoding="utf-8", newline="\n")`. On Windows, `write_text` writes CRLF otherwise.

## Review Focus

1. **A finished match with a thin data file** (the Moroccan league or a friendly: no events, no stats): no report is written. The match is marked `thin` in the state rather than retried every 15 minutes. Test in Task 2 and Task 8.
2. **An awarded, abandoned or postponed match** (`config.awarded()`, status `postponed`/`cancelled`): never reported. Test in Task 3.
3. **A cup match decided on penalties:** the shootout score is in the sheet, and «ركلات الترجيح 4-3» passes the number check. Test in Task 2 and Task 4.
4. **The API is down, overloaded (529) or rate-limited (429):** the journal job does not fail. The match stays due for the next run, and is dropped after 3 attempts. Test in Task 8.
5. **The match file changes after the report** (a goal re-credited to another player, a late correction of the score): the report is written again under the same id, with `dateModified`. Test in Task 8.

---

## File structure

saas/football (repo `MrDMX7/elyoxe-football`, public):

| File | Responsibility |
|---|---|
| `news/articles/__init__.py` | package marker |
| `news/articles/types.json` | per type: on/off, model, word range |
| `news/articles/style.md` | the style guide (system prompt), from the blind tests' `style4.md` |
| `news/articles/priority.py` | which matches get articles |
| `news/articles/facts.py` | the match-report fact sheet from `v1/` files |
| `news/articles/due.py` | finished priority matches not written yet |
| `news/articles/check.py` | the article checks |
| `news/articles/spend.py` | cost per call, the month's total, the $180 cap |
| `news/articles/write.py` | the Claude API call |
| `news/articles/photo.py` | the article's photo |
| `news/articles/publish.py` | the article JSON and the list |
| `news/articles/run.py` | the orchestration and CLI (`python -m news.articles.run`) |
| `store.py` | + `Store.put_bytes` |
| `usage_log.py` | + `record_api` |
| `competitions.yaml` | + `settings.articles_priority` |
| `requirements-ci.txt` | + `anthropic`, `google-auth` |
| `tools/runner.py` | journal job: + the articles step, + the weekly measurement |
| `.github/workflows/tifo-journal.yml` | + `ANTHROPIC_API_KEY`, `GSC_SA_JSON` |
| `tools/gsc_weekly.py` | clicks and impressions per article type, a weekly email |
| `site/lib/articles.cjs` | article pages, the /news/ block, the trust pages, `sitemap-news.xml` |
| `site/lib/articles.test.cjs` | its tests |
| `site/build.cjs` | wiring: call the module, `ogUrl`, robots line, match-page link |
| `tests/test_articles_*.py` | Python tests |
| `tests/fixtures/articles/` | recorded `v1/` files for the tests |

workspace (repo `MrDMX7/workspace`, private):

| File | Responsibility |
|---|---|
| `content/social/tifo/article_x.py` | posts new reports to X, one per run |
| `content/social/tifo/article-x-task.vbs` | the Task Scheduler wrapper |
| `content/social/tifo/tests/test_article_x.py` | its tests |

---

### Task 1: The package, its config and the priority list

**Files:**
- Create: `news/articles/__init__.py`, `news/articles/types.json`, `news/articles/style.md`, `news/articles/priority.py`
- Modify: `competitions.yaml` (the `settings:` block), `requirements-ci.txt`
- Test: `tests/test_articles_priority.py`

**Interfaces:**
- Produces:
  - `priority.priority_comps() -> set[int]`
  - `priority.arab_teams() -> set[int]`
  - `priority.is_priority(comp_id: int, home_id: int, away_id: int) -> bool`
  - `types.json` shape `{"report": {"on": bool, "model": str, "words": [int, int]}}`
  - `news/articles/style.md` (plain text)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_articles_priority.py
"""news/articles/priority.py: the spec's priority list (owner, spec review: the full list) and every Arab national team."""
from news.articles import priority as P


def test_the_priority_list_holds_the_spec_competitions():
    comps = P.priority_comps()
    for cid in (538, 11027, 9943, 11026,      # UAE league and cups
                536, 9942, 10074,             # Saudi
                535, 519, 9941, 10314,        # Qatar, Egypt
                530, 11840,                   # Morocco
                525, 10622, 9469,             # AFC Champions League Elite (and its qualification), Two
                42, 47, 87, 55, 54, 53):      # UEFA Champions League, the big five
        assert cid in comps, cid


def test_an_arab_national_team_makes_any_match_a_priority():
    assert 5789 in P.arab_teams() and 7795 in P.arab_teams()      # UAE, Saudi Arabia (countries.yaml arab: true)
    assert P.is_priority(114, 5789, 9999)                          # a friendly of the UAE
    assert not P.is_priority(114, 9998, 9999)                      # a friendly of two non-Arab sides
    assert P.is_priority(47, 1, 2)                                 # any Premier League match
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_articles_priority.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'news.articles'`

- [ ] **Step 3: Write the config and the module**

In `competitions.yaml`, inside `settings:` (after `analytics_leagues`), add:

```yaml
  # Tifo articles (docs/superpowers/specs/2026-11-18-articles-design.md): match reports and previews for these, and for every
  # match of an Arab national team whatever the competition (news/articles/priority.py). Owner, spec review: the full list.
  articles_priority: [538, 11027, 9943, 11026, 536, 9942, 10074, 535, 11018, 519, 9941, 10314, 530, 11840,
                      525, 10622, 9469, 42, 47, 87, 55, 54, 53]
```

`news/articles/__init__.py`:

```python
"""Tifo articles (docs/superpowers/specs/2026-11-18-articles-design.md): fact sheet -> Claude API -> checks -> v1/news/a/."""
```

`news/articles/priority.py`:

```python
"""Which matches get articles: the competitions in competitions.yaml settings.articles_priority, and every match of an Arab
national team (countries.yaml arab: true) in any competition, friendlies included."""
import config


def priority_comps() -> set[int]:
    return {int(c) for c in config.settings().get("articles_priority", [])}


def arab_teams() -> set[int]:
    return {int(c["fotmob_team"]) for c in config.countries() if c.get("arab") and c.get("fotmob_team")}


def is_priority(comp_id, home_id, away_id) -> bool:
    return int(comp_id) in priority_comps() or bool({int(home_id), int(away_id)} & arab_teams())
```

`news/articles/types.json` (`on` stays false until Task 13 goes live):

```json
{
  "report": {"on": false, "model": "claude-sonnet-5-5", "words": [300, 400]}
}
```

`news/articles/style.md`:
- Copy `content/social/tifo/articles-test/2026-11-18/style4.md` from the workspace repo.
- Replace its rule 6 (tactics) with the match-report rule below.
- Delete rules 7-10 and 13, which belong to other types and come back in their own phases.
- Renumber the rules.
- Add the two rules at the end.

```text
6. تقرير المباراة: ابدأ بالنتيجة وما تعنيه في الترتيب. ثم مجرى المباراة بترتيب الأحداث المهمة (الأهداف، والطرد، والتبديلات التي غيّرت شيئاً إن ظهر ذلك من الورقة). ثم الأرقام التي تشرح النتيجة (الاستحواذ، والتسديدات، والفرص). لا تصف لقطة لم تذكر الورقة طريقتها. عدد المباريات التي لعبها كل فريق مذكور في الورقة بجانب الترتيب، فلا تستنتجه من رقم الجولة. الطول من 300 إلى 400 كلمة.
```

```text
- لا تذكر قناة MBC Action أبداً.
- sources_cited: «بيانات تيفو».
```

`requirements-ci.txt`, add at the end:

```text
anthropic
google-auth
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pip install anthropic google-auth && python -m pytest tests/test_articles_priority.py -q`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add news/articles/ competitions.yaml requirements-ci.txt tests/test_articles_priority.py
git commit -m "articles: package, types.json, the style guide and the priority list"
```

---

### Task 2: The match-report fact sheet

**Files:**
- Create: `news/articles/facts.py`
- Create: `tests/fixtures/articles/` (recorded files, step 1)
- Test: `tests/test_articles_facts.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - `facts.load_names(root: Path | None = None) -> dict` (`{"players": {...}, "coaches": {...}, "referees": {...}}`)
  - `facts.report_sheet(md: dict, standings: dict | None, fixtures: dict | None, names: dict) -> tuple[dict, dict]`, returning `(sheet, meta)`
  - `meta = {"match": int, "comp": int, "teams": [home_id, away_id], "players": [ids], "thin": bool, "fingerprint": str}`
  - `fingerprint` changes when the score, a goal's minute or scorer, or a red card changes. It is used in Task 8.

- [ ] **Step 1: Record the fixtures**

```bash
mkdir -p tests/fixtures/articles
python - <<'EOF'
import gzip, json, urllib.request
def get(p):
    raw = urllib.request.urlopen(urllib.request.Request("https://tifo.elyoxe.com/v1/" + p, headers={"Accept-Encoding": "gzip", "User-Agent": "tifo-tests"}), timeout=60).read()
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
for name, path in [("match_1000022237.json", "match/1000022237.json"),    # Al Jazira 2-1 Al Wasl, ADNOC (round 7 postponed)
                   ("standings_538.json", "comp/538/standings.json"),
                   ("fixtures_538.json", "comp/538/fixtures.json"),
                   ("match_5181860.json", "match/5181860.json"),          # Spain 2-3 England, Nations League
                   ("all_20261117.json", "all/20261117.json")]:
    open(f"tests/fixtures/articles/{name}", "w", encoding="utf-8", newline="\n").write(json.dumps(get(path), ensure_ascii=False))
    print("saved", name)
EOF
```

Expected: five `saved …` lines.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_articles_facts.py
"""news/articles/facts.py on real recorded matches (tests/fixtures/articles/)."""
import copy, json
from pathlib import Path
from news.articles import facts as F

FX = Path(__file__).parent / "fixtures" / "articles"
J = lambda n: json.loads((FX / n).read_text(encoding="utf-8"))
NAMES = {"players": {}, "coaches": {}, "referees": {}}


def test_the_sheet_carries_the_result_the_goals_in_order_and_the_table_with_games_played():
    md = J("match_1000022237.json")
    sheet, meta = F.report_sheet(md, J("standings_538.json"), J("fixtures_538.json"), NAMES)
    h, a = md["home"]["name_ar"], md["away"]["name_ar"]
    assert sheet["النتيجة النهائية"] == f"{h} {md['score']['home']} - {md['score']['away']} {a}"
    goals = [e for e in sheet["الأحداث بالترتيب"] if e["حدث"].startswith("هدف")]
    assert len(goals) == md["score"]["home"] + md["score"]["away"]
    rows = sheet["الترتيب الحالي في البطولة"]
    assert {r["الفريق"] for r in rows} == {h, a} and all("لعب" in r and "النقاط" in r for r in rows)
    assert meta["match"] == md["id"] and meta["comp"] == md["comp"] and not meta["thin"]


def test_a_postponed_round_is_stated_next_to_the_table():
    sheet, _ = F.report_sheet(J("match_1000022237.json"), J("standings_538.json"), J("fixtures_538.json"), NAMES)
    post = sheet.get("جولات مؤجلة") or []
    assert any(p["الجولة"] == "الجولة 7" for p in post)                      # ADNOC round 7, moved to 29-30 December


def test_derived_numbers_are_ready_made():
    md = J("match_5181860.json")                                            # Spain 2-3 England
    sheet, _ = F.report_sheet(md, None, None, NAMES)
    d = sheet["أرقام محسوبة"]
    assert d["مجموع الأهداف"] == 5 and d["فارق الأهداف"] == 1
    assert d["الفائز"] == md["away"]["name_ar"]


def test_a_shootout_is_in_the_sheet():
    md = copy.deepcopy(J("match_5181860.json"))
    md["score"] = {"home": 1, "away": 1}; md["penalties"] = {"home": 4, "away": 3}
    sheet, _ = F.report_sheet(md, None, None, NAMES)
    assert sheet["ركلات الترجيح"] == f"{md['home']['name_ar']} 4 - 3 {md['away']['name_ar']}"
    assert sheet["أرقام محسوبة"]["الفائز"] == md["home"]["name_ar"]


def test_a_match_without_events_or_stats_is_thin():
    md = copy.deepcopy(J("match_5181860.json")); md["events"] = []; md["stats"] = []; md["lineups"] = {}
    _, meta = F.report_sheet(md, None, None, NAMES)
    assert meta["thin"]


def test_the_fingerprint_moves_when_a_goal_changes_scorer():
    md = J("match_5181860.json")
    _, m1 = F.report_sheet(md, None, None, NAMES)
    md2 = copy.deepcopy(md)
    g = next(e for e in md2["events"] if e["type"] in ("goal", "penalty_goal", "own_goal"))
    g["player"] = {"id": 1, "name": "Someone Else"}
    _, m2 = F.report_sheet(md2, None, None, NAMES)
    assert m1["fingerprint"] != m2["fingerprint"]
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `python -m pytest tests/test_articles_facts.py -q`
Expected: FAIL with `ImportError: cannot import name 'facts'`

- [ ] **Step 4: Write `news/articles/facts.py`**

```python
"""The match-report fact sheet (spec: «Every article is written from one fact sheet»). Built from the public v1/ files only:
match/<id>.json, comp/<id>/standings.json, comp/<id>/fixtures.json. Keys are Arabic, as in the blind tests the owner judged
(content/social/tifo/articles-test/2026-11-18/build.py). The writer never does arithmetic: totals, differences, the winner
and each team's games played are in the sheet. A round played after a postponed one is stated (ADNOC 11-18: round 7 was
moved to 29-30 December, so after round 8 every team had played 7)."""
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAT_AR = {"BallPossesion": "الاستحواذ (%)", "total_shots": "التسديدات", "ShotsOnTarget": "على المرمى", "big_chance": "الفرص الكبيرة",
           "big_chance_missed_title": "فرص كبيرة ضائعة", "accurate_passes": "تمريرات صحيحة", "corners": "الركنيات",
           "yellow_cards": "البطاقات الصفراء", "expected_goals": "الأهداف المتوقعة xG", "fouls": "الأخطاء", "Offsides": "التسلل"}
GOALS = ("goal", "penalty_goal", "own_goal")
GOAL_AR = {"goal": "هدف", "penalty_goal": "هدف من ركلة جزاء", "own_goal": "هدف عكسي"}
CARD_AR = {"red": "بطاقة حمراء مباشرة", "second_yellow": "بطاقة صفراء ثانية وطرد", "yellow": "بطاقة صفراء"}


def load_names(root: Path | None = None) -> dict:
    nd = (root or ROOT) / "names"
    def rd(f):
        try:
            return json.loads((nd / f).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    return {"players": rd("players_ar.json"), "coaches": rd("coaches_ar.json"), "referees": rd("referees_ar.json")}


def _ar(table, pid, latin):
    e = table.get(str(pid)) if pid else None
    v = (e or {}).get("ar") if isinstance(e, dict) else e
    return v or latin


def _minute(e):
    return f"{e['minute']}" + (f"+{e['added']}" if e.get("added") else "")


def _lineup_index(md):
    idx = {}
    for side in ("home", "away"):
        for k, v in ((md.get("lineups") or {}).get(side) or {}).items():
            if isinstance(v, list):
                for p in v:
                    if isinstance(p, dict) and p.get("id"):
                        idx[p["id"]] = (side, p)
    return idx


def _postponed(fixtures, md):
    """Rounds with a match not played while a later round of the same competition is finished."""
    ms = (fixtures or {}).get("matches") or []
    num = lambda r: int(r) if str(r).isdigit() else None
    done = [num(m.get("round")) for m in ms if m.get("status") == "finished" and num(m.get("round")) is not None]
    if not done:
        return []
    last = max(done)
    out = []
    for m in ms:
        r = num(m.get("round"))
        if r is not None and r < last and m.get("status") in ("scheduled", "postponed"):
            out.append({"الجولة": m.get("round_ar") or f"الجولة {r}", "المباراة": f"{m['home'].get('name_ar')} - {m['away'].get('name_ar')}",
                        "الموعد الجديد بتوقيت الإمارات": m.get("kickoff_uae")})
    return out


def report_sheet(md, standings, fixtures, names):
    PL, CO, RE = names.get("players", {}), names.get("coaches", {}), names.get("referees", {})
    person = lambda p: _ar(PL, p.get("id"), p.get("name")) if p else None
    idx = _lineup_index(md)
    team = {"home": md["home"]["name_ar"], "away": md["away"]["name_ar"]}
    ev, fp = [], []
    for e in md.get("events") or []:
        t = e.get("type")
        if t in GOALS:
            pid = (e.get("player") or {}).get("id")
            side = idx.get(pid, (None,))[0]
            ev.append({"دقيقة": _minute(e), "حدث": GOAL_AR[t], "اللاعب": person(e.get("player")), "فريق اللاعب": team.get(side) if side else None,
                       "الصناعة": person(e.get("assist")),
                       "النتيجة بعده": f"{team['home']} {e['score']['home']} - {e['score']['away']} {team['away']}"})
            fp.append(f"g{_minute(e)}:{pid}")
        elif t in CARD_AR:
            ev.append({"دقيقة": _minute(e), "حدث": CARD_AR[t], "اللاعب": person(e.get("player")), "الفريق": team.get(e.get("team"))})
            if t != "yellow":
                fp.append(f"r{_minute(e)}:{(e.get('player') or {}).get('id')}")
        elif t == "sub":
            ev.append({"دقيقة": _minute(e), "حدث": "تبديل", "الفريق": team.get(e.get("team")),
                       "دخل": person(e.get("player")), "خرج": person(e.get("player_out"))})
    stats = {}
    for grp in md.get("stats") or []:
        for it in grp.get("items") or []:
            k = STAT_AR.get(it.get("key"))
            if k and k not in stats:
                stats[k] = {team["home"]: it.get("home"), team["away"]: it.get("away")}
    if md.get("xg"):
        stats["الأهداف المتوقعة xG"] = {team["home"]: md["xg"].get("home"), team["away"]: md["xg"].get("away")}
    sh, sa = md["score"]["home"], md["score"]["away"]
    pens = md.get("penalties") or None
    if sh != sa:
        winner = team["home"] if sh > sa else team["away"]
    elif pens and pens.get("home") is not None and pens.get("home") != pens.get("away"):
        winner = team["home"] if pens["home"] > pens["away"] else team["away"]
    else:
        winner = "تعادل"
    rated = sorted([(p.get("rating") or 0, side, p) for _, (side, p) in idx.items() if p.get("rating")], key=lambda x: -x[0])[:3]
    lu = md.get("lineups") or {}
    coach = {team[s]: _ar(CO, ((lu.get(s) or {}).get("coach") or {}).get("id"), ((lu.get(s) or {}).get("coach") or {}).get("name"))
             for s in ("home", "away")}
    wp = (md.get("winprob_prematch") or {}).get("p")
    table = None
    if standings:
        rows = [r for g in standings.get("groups") or [] for r in g.get("rows") or []]
        table = [{"الفريق": r["team"]["name_ar"], "المركز": r["rank"], "لعب": r["played"], "النقاط": r.get("pts", r.get("points")),
                  "فوز": r.get("won"), "تعادل": r.get("drawn"), "خسارة": r.get("lost"), "له": r.get("gf"), "عليه": r.get("ga")}
                 for r in rows if r["team"]["id"] in (md["home"]["id"], md["away"]["id"])] or None
    ref = md.get("referee") or {}
    sheet = {
        "النوع": "تقرير مباراة", "البطولة": md.get("comp_name_ar"), "الجولة": md.get("round_ar"), "الموسم": md.get("season"),
        "الموعد بتوقيت الإمارات": md.get("kickoff_uae"),
        "الملعب": (md.get("venue") or {}).get("name_ar") or (md.get("venue") or {}).get("name_en"),
        "الحكم": _ar(RE, ref.get("id"), ref.get("name")), "الحضور": md.get("attendance"),
        "صاحب الأرض": team["home"], "الضيف": team["away"],
        "النتيجة النهائية": f"{team['home']} {sh} - {sa} {team['away']}",
        "نتيجة الشوط الأول": (f"{team['home']} {md['halftime_score']['home']} - {md['halftime_score']['away']} {team['away']}"
                              if md.get("halftime_score") else None),
        "ركلات الترجيح": f"{team['home']} {pens['home']} - {pens['away']} {team['away']}" if pens and pens.get("home") is not None else None,
        "أرقام محسوبة": {"مجموع الأهداف": sh + sa, "فارق الأهداف": abs(sh - sa), "الفائز": winner},
        "المدربان": coach, "الخطتان": {team[s]: (lu.get(s) or {}).get("formation") for s in ("home", "away")},
        "الأحداث بالترتيب": ev, "الإحصائيات": stats,
        "الأعلى تقييماً": [{"اللاعب": person(p), "الفريق": team[s], "التقييم": r} for r, s, p in rated],
        "احتمالات نموذج تيفو قبل المباراة (%)": ({"فوز " + team["home"]: round(wp[0] * 100), "تعادل": round(wp[1] * 100),
                                                 "فوز " + team["away"]: round(wp[2] * 100)} if wp else None),
        "الترتيب الحالي في البطولة": table,
        "جولات مؤجلة": _postponed(fixtures, md) or None,
    }
    sheet = {k: v for k, v in sheet.items() if v not in (None, [], {})}
    fp.append(f"s{sh}-{sa}" + (f"p{pens.get('home')}-{pens.get('away')}" if pens else ""))
    meta = {"match": md["id"], "comp": md.get("comp"), "teams": [md["home"]["id"], md["away"]["id"]],
            "players": sorted({pid for pid in idx} | {(e.get("player") or {}).get("id") for e in md.get("events") or []} - {None}),
            "thin": not (md.get("events") or md.get("stats")),
            "fingerprint": hashlib.sha1("|".join(sorted(fp)).encode()).hexdigest()[:12]}
    return sheet, meta
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest tests/test_articles_facts.py -q`
Expected: PASS (6 tests)

If `test_a_postponed_round_is_stated_next_to_the_table` fails because round 7 has been played by the time you record the fixtures: edit `fixtures_538.json` so one round-7 match has `"status": "scheduled"` and a December `kickoff_uae`. Add a comment in the test saying the fixture was edited and why.

- [ ] **Step 6: Commit**

```bash
git add news/articles/facts.py tests/test_articles_facts.py tests/fixtures/articles/
git commit -m "articles: the match-report fact sheet (games played, postponed rounds, derived numbers, shootouts)"
```

---

### Task 3: Which matches are due

**Files:**
- Create: `news/articles/due.py`
- Test: `tests/test_articles_due.py`

**Interfaces:**
- Consumes: `priority.is_priority(comp, home, away)` (Task 1)
- Produces: `due.finished_priority(day_docs: list[dict], awarded: set[int]) -> list[int]` (match ids, oldest kickoff first)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_articles_due.py
"""news/articles/due.py on a recorded all-day file (tests/fixtures/articles/all_20261117.json)."""
import json
from pathlib import Path
from news.articles import due as D, priority as P

DAY = json.loads((Path(__file__).parent / "fixtures" / "articles" / "all_20261117.json").read_text(encoding="utf-8"))


def _matches():
    return [(lg["id"], m) for lg in DAY["leagues"] for m in lg.get("matches") or []]


def test_only_finished_priority_matches_are_due():
    ids = D.finished_priority([DAY], awarded=set())
    assert ids
    by = {m["id"]: (cid, m) for cid, m in _matches()}
    for mid in ids:
        cid, m = by[mid]
        assert m["status"] == "finished"
        assert P.is_priority(cid, m["home"][0], m["away"][0])


def test_awarded_and_postponed_matches_are_never_due():
    ids = D.finished_priority([DAY], awarded=set())
    first = ids[0]
    assert first not in D.finished_priority([DAY], awarded={first})
    post = [m["id"] for _, m in _matches() if m["status"] == "postponed"]
    assert not set(post) & set(D.finished_priority([DAY], awarded=set()))


def test_oldest_first_and_no_duplicates():
    ids = D.finished_priority([DAY, DAY], awarded=set())
    assert len(ids) == len(set(ids))
    utc = {m["id"]: m["utc"] for _, m in _matches()}
    assert [utc[i] for i in ids] == sorted(utc[i] for i in ids)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_articles_due.py -q`
Expected: FAIL with `ImportError: cannot import name 'due'`

- [ ] **Step 3: Write `news/articles/due.py`**

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_articles_due.py -q`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add news/articles/due.py tests/test_articles_due.py
git commit -m "articles: finished priority matches from the all-day files"
```

---

### Task 4: The article checks

**Files:**
- Create: `news/articles/check.py`
- Test: `tests/test_articles_check.py`

**Interfaces:**
- Consumes: `site/ai/checks.py`: `check_events(text, md, players=None) -> str | None`, `check_halves(text, md) -> (str | None, str)`, `input_numbers(evidence) -> set[float]`, `match_players(md)`. It is imported with `sys.path.insert(0, ROOT/"site"/"ai")` and `import checks`, as `tests/test_ai_checks.py` does.
- Produces:
  - `check.article_text(article: dict) -> str` (headline, standfirst, every paragraph and the facts box, one line each)
  - `check.check_article(article: dict, sheet: dict, md: dict | None = None) -> list[str]` (an empty list means it passes)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_articles_check.py
"""news/articles/check.py: the failures the blind tests showed (spec, «Checks»), and the right texts that must pass."""
import json
from pathlib import Path
from news.articles import check as C, facts as F

FX = Path(__file__).parent / "fixtures" / "articles"
MD = json.loads((FX / "match_5181860.json").read_text(encoding="utf-8"))
SHEET, _ = F.report_sheet(MD, None, None, {"players": {}, "coaches": {}, "referees": {}})
H, A = MD["home"]["name_ar"], MD["away"]["name_ar"]


def art(*paras, headline="عنوان", standfirst="مقدمة"):
    return {"headline": headline, "standfirst": standfirst, "sections": [{"subhead": "قسم", "paragraphs": list(paras)}], "facts_box": []}


def test_a_correct_line_passes():
    line = f"فاز {A} على {H} بنتيجة {MD['score']['away']}-{MD['score']['home']}."
    assert C.check_article(art(line), SHEET, MD) == []


def test_a_number_not_in_the_sheet_fails():
    assert C.check_article(art(f"سجل {A} 7 أهداف."), SHEET, MD)


def test_latin_letters_fail_but_xg_and_var_pass():
    assert C.check_article(art("سجل Kane الهدف."), SHEET, MD)
    assert not [f for f in C.check_article(art("بلغت الأهداف المتوقعة xG للفريق رقماً، وتدخل VAR."), SHEET, MD) if "Latin" in f]


def test_dates_times_word_numbers_and_thousands_are_read_as_the_sheet_has_them():
    sheet = dict(SHEET, **{"الموعد بتوقيت الإمارات": "2026-11-08T22:00:00+04:00", "الحضور": 69788,
                           "النتيجة النهائية": f"{H} 3 - 0 {A}"})
    line = "أقيمت المباراة في 8 نوفمبر عند 10:00 مساءً أمام 69,788 متفرج، وانتهت بثلاثية نظيفة."
    assert C.check_article(art(line), sheet, None) == []


def test_a_shootout_line_passes():
    sheet = dict(SHEET, **{"ركلات الترجيح": f"{H} 4 - 3 {A}"})
    assert C.check_article(art(f"حسم {H} التأهل بركلات الترجيح 4-3."), sheet, None) == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_articles_check.py -q`
Expected: FAIL with `ImportError: cannot import name 'check'`

- [ ] **Step 3: Write `news/articles/check.py`**

```python
"""Article checks (spec, «Checks»): every number in the article is in the fact sheet; Latin letters fail (xG and VAR are
words of the trade); match reports also go through site/ai/checks.py (goal order, red cards, halves). Dates, 12-hour times,
numbers written as words and thousands separators are read the way the sheet stores them, so a right text is not flagged
(the blind tests flagged correct articles in every round without this)."""
import os, re, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "site", "ai"))
import checks as AI   # noqa: E402

MONTHS = {"يناير": 1, "فبراير": 2, "مارس": 3, "أبريل": 4, "ابريل": 4, "مايو": 5, "يونيو": 6, "يوليو": 7, "أغسطس": 8, "اغسطس": 8,
          "سبتمبر": 9, "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12}
WORDS = {"ثنائية": 2, "ثلاثية": 3, "رباعية": 4, "خماسية": 5, "سداسية": 6, "سباعية": 7, "ثمانية": 8, "هدفين": 2, "هدفان": 2}
LATIN_OK = {"xG", "VAR"}


def article_text(a):
    lines = [a.get("headline") or "", a.get("standfirst") or ""]
    for s in a.get("sections") or []:
        lines.append(s.get("subhead") or "")
        lines += s.get("paragraphs") or []
    return "\n".join(lines + list(a.get("facts_box") or []))


def _sheet_dates(sheet):
    days, times = set(), set()
    def walk(o):
        if isinstance(o, dict):
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
        elif isinstance(o, str) and re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", o):
            d = datetime.fromisoformat(o)
            days.add((d.month, d.day)); times.add((d.hour, d.minute))
    walk(sheet)
    return days, times


def check_article(article, sheet, md=None):
    text = article_text(article)
    fails = []
    days, times = _sheet_dates(sheet)
    # dates «8 نوفمبر»: the day and month must be a date in the sheet; then they are not numbers to check
    for m in re.finditer(r"(\d{1,2})\s+(" + "|".join(MONTHS) + r")", text):
        if (MONTHS[m.group(2)], int(m.group(1))) not in days:
            fails.append(f"date «{m.group(0)}» is not in the sheet")
    text = re.sub(r"\d{1,2}\s+(?:" + "|".join(MONTHS) + r")(?:\s+\d{4})?", " ", text)
    # times «10:00 مساءً» / «22:00»
    for m in re.finditer(r"(\d{1,2}):(\d{2})\s*(مساءً|مساء|صباحاً|صباحا|ص|م)?", text):
        h, mi, half = int(m.group(1)), int(m.group(2)), m.group(3) or ""
        if half.startswith("م") and h < 12: h += 12
        if half.startswith("ص") and h == 12: h = 0
        if (h, mi) not in times:
            fails.append(f"time «{m.group(0)}» is not in the sheet")
    text = re.sub(r"\d{1,2}:\d{2}\s*(?:مساءً|مساء|صباحاً|صباحا|ص|م)?", " ", text)
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)            # 69,788 -> 69788
    have = AI.input_numbers(sheet)
    for w, n in WORDS.items():                                  # «بثلاثية نظيفة»: the number the word stands for
        if w in text and float(n) not in have:
            fails.append(f"«{w}» ({n}) is not in the sheet")
    for m in re.finditer(r"(?<![\d.])(\d+(?:\.\d+)?)(?![\d])", text):
        v = round(float(m.group(1)), 1)
        if v not in have and float(round(v)) not in have:
            fails.append(f"number {m.group(1)} is not in the sheet")
    latin = [w for w in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'\-]+", article_text(article)) if w not in LATIN_OK]
    if latin:
        fails.append("Latin words left: " + ", ".join(sorted(set(latin))[:8]))
    if md is not None:
        full = article_text(article)
        r = AI.check_events(full, md)
        if r: fails.append(r)
        r, _ = AI.check_halves(full, md)
        if r: fails.append(r)
    return fails
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_articles_check.py -q`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add news/articles/check.py tests/test_articles_check.py
git commit -m "articles: the number, date, time, Latin and event checks"
```

---

### Task 5: Spend, the $180 cap and the usage log

**Files:**
- Create: `news/articles/spend.py`
- Modify: `usage_log.py` (add `record_api` after `record_cli`)
- Test: `tests/test_articles_spend.py`

**Interfaces:**
- Produces:
  - `spend.PRICES: dict[str, tuple[float, float, float, float]]` ($ per million: in, out, cache read, cache write)
  - `spend.cost(model: str, usage: dict) -> float`, where usage is `{"in", "out", "cache_read", "cache_write"}`
  - `spend.Spend(store, now: datetime)` with `.month_total() -> float`, `.allowed() -> bool`, `.add(model, usage, job) -> float`, `.save()`, `.capped_now() -> bool`
  - `spend.CAP = 180.0`
  - `usage_log.record_api(job, model, usage, usd)`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_articles_spend.py
"""news/articles/spend.py: the month's total and the $180 stop (spec, «Guards»)."""
from datetime import datetime, timezone
from store import Store, LocalBackend
from news.articles import spend as S


def test_cost_counts_cache_reads_and_writes():
    u = {"in": 1_000_000, "out": 1_000_000, "cache_read": 1_000_000, "cache_write": 1_000_000}
    assert S.cost("claude-sonnet-5-5", u) == round(2.0 + 10.0 + 0.10 + 2.50, 6)


def test_the_cap_stops_at_180_and_a_new_month_starts_at_zero(tmp_path):
    st = Store(LocalBackend(tmp_path))
    nov = datetime(2026, 11, 20, tzinfo=timezone.utc)
    sp = S.Spend(st, nov)
    sp.add("claude-sonnet-5-5", {"in": 0, "out": 17_999_000, "cache_read": 0, "cache_write": 0}, "report")   # $179.99
    assert sp.allowed()
    sp.add("claude-sonnet-5-5", {"in": 0, "out": 10_000, "cache_read": 0, "cache_write": 0}, "report")
    assert not sp.allowed() and sp.capped_now()
    sp.save()
    assert not S.Spend(st, nov).allowed()
    assert S.Spend(st, datetime(2026, 12, 1, tzinfo=timezone.utc)).allowed()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_articles_spend.py -q`
Expected: FAIL with `ImportError: cannot import name 'spend'`

- [ ] **Step 3: Write `news/articles/spend.py` and `usage_log.record_api`**

```python
"""What the articles cost (spec, «Guards»): every call's tokens at list price into state/articles/spend.json by calendar month
(UTC); at $180 in a month writing stops until the month ends. Prices from the claude-api skill's models table, 2026-11-18:
Sonnet 5.5 $2 / $10, cache reads $0.10, cache writes 1.25x input; Haiku 5.5 $0.10 / $0.50."""
import usage_log

NAME = "articles/spend.json"
CAP = 180.0
PRICES = {"claude-sonnet-5-5": (2.0, 10.0, 0.10, 2.50), "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125)}


def cost(model, u):
    pin, pout, pread, pwrite = PRICES[model]
    return round((u.get("in", 0) * pin + u.get("out", 0) * pout + u.get("cache_read", 0) * pread
                  + u.get("cache_write", 0) * pwrite) / 1e6, 6)


class Spend:
    def __init__(self, store, now):
        self.store, self.month = store, now.strftime("%Y-%m")
        self.doc = store.get_state(NAME) or {}
        self.doc.setdefault(self.month, {"usd": 0.0, "calls": 0, "by_type": {}, "capped": False})
        self._was_capped = self.doc[self.month]["capped"]

    def month_total(self):
        return self.doc[self.month]["usd"]

    def allowed(self):
        return self.month_total() < CAP

    def add(self, model, usage, job):
        usd = cost(model, usage)
        m = self.doc[self.month]
        m["usd"] = round(m["usd"] + usd, 6); m["calls"] += 1
        m["by_type"][job] = round(m["by_type"].get(job, 0.0) + usd, 6)
        if m["usd"] >= CAP:
            m["capped"] = True
        usage_log.record_api(f"articles-{job}", model, usage, usd)
        return usd

    def capped_now(self):
        """True once, in the run that crossed the cap (the caller sends the one email)."""
        return self.doc[self.month]["capped"] and not self._was_capped

    def save(self):
        self.store.put_state(NAME, self.doc)
```

In `usage_log.py`, after `record_cli`:

```python
def record_api(job, model, usage, usd):
    """A Claude API call (Tifo articles, paid from the owner's API credit): via=api, a real bill."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    try:
        line = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "project": "tifo", "job": job, "via": "api",
                "model": model, "in": usage.get("in", 0), "out": usage.get("out", 0), "cache_read": usage.get("cache_read", 0),
                "cache_write": usage.get("cache_write", 0), "usd": usd, "ok": True, "secs": None}
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        with open(PATH, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(line) + "\n")
    except Exception:
        pass
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_articles_spend.py -q`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add news/articles/spend.py usage_log.py tests/test_articles_spend.py
git commit -m "articles: spend by month, the \$180 stop, API calls in the usage log"
```

---

### Task 6: The writer (Claude API)

**Files:**
- Create: `news/articles/write.py`
- Test: `tests/test_articles_write.py`

**Interfaces:**
- Consumes: `news/articles/style.md` (Task 1)
- Produces:
  - `write.SCHEMA` (the article JSON schema)
  - `write.Writer(client=None)`
  - `.write(kind: str, sheet: dict, model: str, notes: list[str] | None = None) -> tuple[dict, dict]`, returning `(article, usage)`
  - `article = {"headline", "standfirst", "sections": [{"subhead", "paragraphs": [str]}], "facts_box": [str], "sources_cited": [str]}`
  - `write.WriteError(Exception)` (refusal, max_tokens, no JSON)
  - API errors from the SDK propagate. Task 8 catches them.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_articles_write.py
"""news/articles/write.py with a fake client (no network): the request carries the style guide as a cached system block, the
sheet, the schema, and on a rewrite the failures; a refusal or a cut-off answer is an error."""
import json, types
import pytest
from news.articles import write as W

ART = {"headline": "ع", "standfirst": "م", "sections": [{"subhead": "ق", "paragraphs": ["ف"]}], "facts_box": ["ح"], "sources_cited": ["بيانات تيفو"]}


class FakeStream:
    def __init__(self, msg): self.msg = msg
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def get_final_message(self): return self.msg


class FakeClient:
    def __init__(self, stop="end_turn", text=json.dumps(ART, ensure_ascii=False)):
        self.calls = []
        usage = types.SimpleNamespace(input_tokens=5000, output_tokens=2000, cache_read_input_tokens=3000, cache_creation_input_tokens=0)
        self.msg = types.SimpleNamespace(stop_reason=stop, usage=usage, content=[types.SimpleNamespace(type="text", text=text)])
        self.messages = types.SimpleNamespace(stream=self._stream)
    def _stream(self, **kw):
        self.calls.append(kw); return FakeStream(self.msg)


def test_the_request_and_the_parsed_answer():
    c = FakeClient()
    art, u = W.Writer(c).write("report", {"النوع": "تقرير مباراة"}, "claude-sonnet-5-5")
    assert art == ART and u == {"in": 5000, "out": 2000, "cache_read": 3000, "cache_write": 0}
    kw = c.calls[0]
    assert kw["model"] == "claude-sonnet-5-5"
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"} and "تيفو" in kw["system"][0]["text"]
    assert kw["output_config"]["format"]["schema"] == W.SCHEMA
    assert "تقرير مباراة" in kw["messages"][0]["content"]


def test_a_rewrite_carries_the_failures():
    c = FakeClient()
    W.Writer(c).write("report", {}, "claude-sonnet-5-5", notes=["number 7 is not in the sheet"])
    assert "number 7 is not in the sheet" in c.calls[0]["messages"][0]["content"]


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_a_refusal_or_a_cut_answer_is_an_error(stop):
    with pytest.raises(W.WriteError):
        W.Writer(FakeClient(stop=stop)).write("report", {}, "claude-sonnet-5-5")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_articles_write.py -q`
Expected: FAIL with `ImportError: cannot import name 'write'`

- [ ] **Step 3: Write `news/articles/write.py`**

```python
"""One Claude API call per article (spec, «Writer»): the style guide is the system prompt, as a cached block (it is the same
for every article, so later calls read it from the prompt cache); the fact sheet is the user message; the answer is JSON in
the schema (structured output, output_config.format). Streamed and read with get_final_message() so a long answer never hits
the request timeout. The key is ANTHROPIC_API_KEY from the environment (the repo secret on GitHub)."""
import json
from pathlib import Path

STYLE = Path(__file__).with_name("style.md")
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["headline", "standfirst", "sections", "facts_box", "sources_cited"],
          "properties": {"headline": {"type": "string"}, "standfirst": {"type": "string"},
                         "sections": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["subhead", "paragraphs"],
                                                                  "properties": {"subhead": {"type": "string"}, "paragraphs": {"type": "array", "items": {"type": "string"}}}}},
                         "facts_box": {"type": "array", "items": {"type": "string"}}, "sources_cited": {"type": "array", "items": {"type": "string"}}}}


class WriteError(Exception):
    pass


class Writer:
    def __init__(self, client=None):
        self.client = client

    def _c(self):
        if self.client is None:
            import anthropic
            self.client = anthropic.Anthropic()
        return self.client

    def write(self, kind, sheet, model, notes=None):
        user = "جاوب بـ JSON فقط مطابق للـ schema.\n\nورقة الحقائق:\n" + json.dumps(sheet, ensure_ascii=False, indent=1)
        if notes:
            user += "\n\nالنسخة السابقة لم تجتز الفحص لهذه الأسباب. اكتب المقال من جديد وصحّحها:\n- " + "\n- ".join(notes)
        with self._c().messages.stream(
                model=model, max_tokens=16000,
                system=[{"type": "text", "text": STYLE.read_text(encoding="utf-8"), "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}],
                output_config={"format": {"type": "json_schema", "schema": SCHEMA}}) as s:
            msg = s.get_final_message()
        if msg.stop_reason in ("refusal", "max_tokens"):
            raise WriteError(f"stop_reason {msg.stop_reason}")
        text = next((b.text for b in msg.content if b.type == "text"), "")
        try:
            art = json.loads(text)
        except ValueError as e:
            raise WriteError(f"no JSON: {e}") from e
        u = msg.usage
        usage = {"in": u.input_tokens or 0, "out": u.output_tokens or 0,
                 "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0, "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0}
        return art, usage
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_articles_write.py -q`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add news/articles/write.py tests/test_articles_write.py
git commit -m "articles: the Claude API writer (cached style guide, structured output, rewrite notes)"
```

---

### Task 7: The photo

**Files:**
- Create: `news/articles/photo.py`
- Modify: `store.py` (add `Store.put_bytes` after `put_text`)
- Test: `tests/test_articles_photo.py`

**Interfaces:**
- Consumes: `v1/media/<id>.json` (news/media.py):
  - The shape is `{"highlights": [video], "goals": {"<minute>-<pid>": [video]}}`.
  - Each video has `id`, `source` (`youtube` or `x`), `channel`, `image`.
- Produces:
  - `photo.candidates(md: dict, media: dict | None) -> list[dict]`. Each item is `{"url", "caption", "source"}`, best first, and the match card is always last.
  - `photo.pick(aid: str, md: dict, media: dict | None, fetch, store) -> dict`, returning `{"url", "w", "h", "caption", "source", "card": bool}`.
  - `fetch(url) -> bytes | None`.
  - `Store.put_bytes(path, body, content_type, cache="static") -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_articles_photo.py
"""news/articles/photo.py: a frame of the match first (the highlights video's YouTube thumbnail, 1280x720), then a goal clip's,
then Tifo's match card; a picture under 1200 px wide is skipped; the chosen one is copied to v1/news/img/<id>.jpg."""
import io
from PIL import Image
from store import Store, LocalBackend
from news.articles import photo as P

MD = {"id": 77, "home": {"name_ar": "أ"}, "away": {"name_ar": "ب"}}
MEDIA = {"highlights": [{"id": "abc", "source": "youtube", "channel": "beIN SPORTS", "image": "https://i.ytimg.com/vi/abc/hqdefault.jpg"}],
         "goals": {"12-5": [{"id": "def", "source": "youtube", "channel": "LaLiga", "image": "https://i.ytimg.com/vi/def/hqdefault.jpg"}]}}


def jpg(w, h):
    b = io.BytesIO(); Image.new("RGB", (w, h), (10, 120, 80)).save(b, "JPEG"); return b.getvalue()


def test_the_order_of_the_candidates():
    c = P.candidates(MD, MEDIA)
    assert c[0]["url"] == "https://i.ytimg.com/vi/abc/maxresdefault.jpg" and "beIN SPORTS" in c[0]["caption"]
    assert c[1]["url"] == "https://i.ytimg.com/vi/def/maxresdefault.jpg"
    assert c[-1]["source"] == "card" and c[-1]["url"].endswith("/og/m-77.png")


def test_a_small_picture_is_skipped_and_the_chosen_one_is_stored(tmp_path):
    st = Store(LocalBackend(tmp_path))
    sizes = {"https://i.ytimg.com/vi/abc/maxresdefault.jpg": jpg(480, 360), "https://i.ytimg.com/vi/def/maxresdefault.jpg": jpg(1280, 720)}
    got = P.pick("r-77", MD, MEDIA, sizes.get, st)
    assert got["url"].endswith("/v1/news/img/r-77.jpg") and got["w"] == 1200 and got["h"] == 675 and not got["card"]
    assert (tmp_path / "v1" / "news" / "img" / "r-77.jpg").exists()


def test_no_frame_means_the_match_card(tmp_path):
    got = P.pick("r-77", MD, None, lambda u: None, Store(LocalBackend(tmp_path)))
    assert got["card"] and got["w"] == 1200 and got["h"] == 630
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_articles_photo.py -q`
Expected: FAIL with `ImportError: cannot import name 'photo'`

- [ ] **Step 3: Write `Store.put_bytes` and `news/articles/photo.py`**

In `store.py`, after `put_text`:

```python
    def put_bytes(self, path, body: bytes, content_type, cache="static") -> bool:
        h = hashlib.md5(body).hexdigest()
        key = PUBLIC + path
        if self.hashes.get(key) == h + "|" + cache:
            self.skipped_same += 1
            return True
        self.b.put(key, body, content_type, CACHE[cache])
        self.hashes[key] = h + "|" + cache
        self.written.append(path)
        return True
```

`news/articles/photo.py`:

```python
"""The article's photo (spec, «Every article has a real photo of its subject»). A match report takes a frame of the match: the
official highlights video's YouTube thumbnail (maxresdefault, 1280x720), else a goal clip's, from v1/media/<id>.json; else
Tifo's match card (/og/m-<id>.png, 1200x630). A frame is cropped to 16:9 and resized to 1200x675, stored at
v1/news/img/<id>.jpg (an outlet's link can break), and captioned. Under 1200 px wide it is skipped."""
import io
from PIL import Image

SITE = "https://tifo.elyoxe.com"


def _yt(v):
    return f"https://i.ytimg.com/vi/{v['id']}/maxresdefault.jpg" if v.get("source") == "youtube" and v.get("id") else v.get("image")


def candidates(md, media):
    out = []
    for v in (media or {}).get("highlights") or []:
        if _yt(v):
            out.append({"url": _yt(v), "caption": f"لقطة من ملخص المباراة على قناة {v.get('channel') or 'رسمية'}", "source": v.get("source")})
    for clips in ((media or {}).get("goals") or {}).values():
        for v in clips:
            if _yt(v):
                out.append({"url": _yt(v), "caption": f"لقطة من هدف في المباراة على قناة {v.get('channel') or 'رسمية'}", "source": v.get("source")})
    out.append({"url": f"{SITE}/og/m-{md['id']}.png", "caption": f"بطاقة مباراة {md['home']['name_ar']} و{md['away']['name_ar']} من تيفو", "source": "card"})
    return out


def pick(aid, md, media, fetch, store):
    for c in candidates(md, media):
        if c["source"] == "card":
            return dict(c, w=1200, h=630, card=True)
        raw = fetch(c["url"])
        if not raw:
            continue
        try:
            im = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception:
            continue
        if im.width < 1200:
            continue
        w, h = im.size
        ch = round(w * 9 / 16)
        if ch <= h:
            top = (h - ch) // 2; im = im.crop((0, top, w, top + ch))
        else:
            cw = round(h * 16 / 9); left = (w - cw) // 2; im = im.crop((left, 0, left + cw, h))
        im = im.resize((1200, 675), Image.LANCZOS)
        b = io.BytesIO(); im.save(b, "JPEG", quality=85, optimize=True)
        store.put_bytes(f"news/img/{aid}.jpg", b.getvalue(), "image/jpeg", cache="static")
        return {"url": f"{SITE}/v1/news/img/{aid}.jpg", "w": 1200, "h": 675, "caption": c["caption"], "source": c["source"], "card": False}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_articles_photo.py tests/test_store.py -q`
Expected: PASS (photo 3 tests, store tests unchanged)

- [ ] **Step 5: Commit**

```bash
git add news/articles/photo.py store.py tests/test_articles_photo.py
git commit -m "articles: a frame of the match as the report's photo, the match card as the fallback"
```

---

### Task 8: Publish and run

**Files:**
- Create: `news/articles/publish.py`, `news/articles/run.py`
- Test: `tests/test_articles_run.py`

**Interfaces:**
- Consumes: Tasks 1-7:
  - `facts.report_sheet`, `facts.load_names`
  - `due.finished_priority`
  - `check.check_article`
  - `spend.Spend`
  - `write.Writer`, `write.WriteError`
  - `photo.pick`
- Produces:
  - `publish.article_doc(aid, kind, art, meta, image, model, now_iso, prev=None) -> dict`
  - `publish.publish(store, doc) -> None` writes `v1/news/a/<id>.json` and updates `v1/news/articles.json` (`{"generated", "articles": [summary]}`, newest first, 500 kept).
  - The summary is `{"id", "kind", "headline", "standfirst", "image", "published", "modified", "match", "entities"}`.
  - `run.run(store, data_get, writer, now, *, dry=False, only=None, limit=None, fetch=None) -> dict` (summary counts)
  - `run.main(argv=None)` (CLI: `python -m news.articles.run [--local DIR] [--dry] [--match ID] [--limit N]`)
  - The state at `state/articles/state.json` is `{"reports": {"<match id>": {"id", "fp", "tries", "status": "done|thin|failed", "at", "card": bool}}}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_articles_run.py
"""news/articles/run.py end to end with a LocalBackend and a fake writer: a due match is written, checked, photographed and
published; a thin match is skipped once; API errors leave the match due and stop after 3 tries; a changed match is written
again under the same id; the $180 cap and types.json «on» stop everything."""
import copy, json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from store import Store, LocalBackend
from news.articles import run as R, write as W

FX = Path(__file__).parent / "fixtures" / "articles"
MD = json.loads((FX / "match_5181860.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
DAY = {"leagues": [{"id": 42, "matches": [{"id": MD["id"], "utc": MD["kickoff_utc"], "status": "finished",
                                           "home": [MD["home"]["id"], MD["home"]["name_ar"], 2], "away": [MD["away"]["id"], MD["away"]["name_ar"], 3]}]}]}


def data(md=MD):
    files = {f"match/{md['id']}.json": md, "all/20261116.json": DAY, "all/20261115.json": {"leagues": []}}
    return lambda p: copy.deepcopy(files.get(p))


class FakeWriter:
    def __init__(self, texts=None, error=None):
        self.texts, self.error, self.calls = list(texts or []), error, []
    def write(self, kind, sheet, model, notes=None):
        self.calls.append(notes)
        if self.error:
            raise self.error
        line = self.texts.pop(0) if self.texts else f"فاز {MD['away']['name_ar']} 3-2."
        return ({"headline": "عنوان", "standfirst": "مقدمة", "sections": [{"subhead": "ق", "paragraphs": [line]}], "facts_box": [], "sources_cited": ["بيانات تيفو"]},
                {"in": 5000, "out": 2000, "cache_read": 0, "cache_write": 0})


@pytest.fixture(autouse=True)
def on(monkeypatch):
    monkeypatch.setattr(R, "TYPES", {"report": {"on": True, "model": "claude-sonnet-5-5", "words": [300, 400]}})


def test_a_due_match_is_published(tmp_path):
    st = Store(LocalBackend(tmp_path))
    out = R.run(st, data(), FakeWriter(), NOW, fetch=lambda u: None)
    assert out["written"] == 1
    doc = st.get_json(f"news/a/r-{MD['id']}.json")
    assert doc["author"] == "تحرير تيفو" and doc["image"]["card"] and doc["match"] == MD["id"]
    lst = st.get_json("news/articles.json")["articles"]
    assert lst[0]["id"] == f"r-{MD['id']}"
    assert R.run(st, data(), FakeWriter(), NOW, fetch=lambda u: None)["written"] == 0       # done: not written twice


def test_a_failed_check_is_rewritten_once_then_dropped(tmp_path):
    st = Store(LocalBackend(tmp_path))
    w = FakeWriter(texts=["سجل 973 هدفاً.", "سجل 973 هدفاً."])
    out = R.run(st, data(), w, NOW, fetch=lambda u: None)
    assert out["written"] == 0 and len(w.calls) == 2 and w.calls[1]                      # the second call carries the failures
    assert st.get_state("articles/state.json")["reports"][str(MD["id"])]["status"] == "failed"


def test_api_errors_keep_the_match_due_three_times(tmp_path):
    st = Store(LocalBackend(tmp_path))
    for i in range(3):
        R.run(st, data(), FakeWriter(error=RuntimeError("529 overloaded")), NOW, fetch=lambda u: None)
    s = st.get_state("articles/state.json")["reports"][str(MD["id"])]
    assert s["tries"] == 3 and s["status"] == "failed"
    assert R.run(st, data(), FakeWriter(), NOW, fetch=lambda u: None)["written"] == 0


def test_a_thin_match_is_skipped_and_remembered(tmp_path):
    st = Store(LocalBackend(tmp_path))
    thin = copy.deepcopy(MD); thin["events"] = []; thin["stats"] = []; thin["lineups"] = {}
    w = FakeWriter()
    R.run(st, data(thin), w, NOW, fetch=lambda u: None)
    assert not w.calls and st.get_state("articles/state.json")["reports"][str(MD["id"])]["status"] == "thin"


def test_a_changed_match_is_written_again_under_the_same_id(tmp_path):
    st = Store(LocalBackend(tmp_path))
    R.run(st, data(), FakeWriter(), NOW, fetch=lambda u: None)
    md2 = copy.deepcopy(MD)
    g = next(e for e in md2["events"] if e["type"] in ("goal", "penalty_goal", "own_goal")); g["player"] = {"id": 1, "name": "X"}
    later = datetime(2026, 11, 16, 13, 0, tzinfo=timezone.utc)
    assert R.run(st, data(md2), FakeWriter(), later, fetch=lambda u: None)["written"] == 1
    doc = st.get_json(f"news/a/r-{MD['id']}.json")
    assert doc["modified"] > doc["published"] and doc["version"] == 2


def test_the_cap_and_the_switch_stop_everything(tmp_path, monkeypatch):
    st = Store(LocalBackend(tmp_path))
    st.put_state("articles/spend.json", {"2026-11": {"usd": 180.0, "calls": 1, "by_type": {}, "capped": True}})
    assert R.run(st, data(), FakeWriter(), NOW, fetch=lambda u: None)["written"] == 0
    monkeypatch.setattr(R, "TYPES", {"report": {"on": False, "model": "claude-sonnet-5-5", "words": [300, 400]}})
    assert R.run(Store(LocalBackend(tmp_path / "b")), data(), FakeWriter(), NOW, fetch=lambda u: None)["written"] == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_articles_run.py -q`
Expected: FAIL with `ImportError: cannot import name 'run'`

- [ ] **Step 3: Write `news/articles/publish.py`**

```python
"""The article as Tifo publishes it: v1/news/a/<id>.json and the list v1/news/articles.json (newest first, 500 kept). The
hourly site build turns both into /news/<id>/ pages (site/lib/articles.cjs)."""
AUTHOR = "تحرير تيفو"
KEEP = 500


def article_doc(aid, kind, art, meta, image, model, now_iso, prev=None):
    ents = [["team", t] for t in meta.get("teams") or []] + [["player", p] for p in (meta.get("players") or [])[:30]]
    return {"id": aid, "kind": kind, "headline": art["headline"], "standfirst": art["standfirst"], "sections": art["sections"],
            "facts_box": art.get("facts_box") or [], "image": image, "author": AUTHOR, "match": meta.get("match"),
            "comp": meta.get("comp"), "entities": ents, "model": model,
            "published": (prev or {}).get("published") or now_iso, "modified": now_iso,
            "version": ((prev or {}).get("version") or 0) + 1}


def summary(doc):
    return {k: doc.get(k) for k in ("id", "kind", "headline", "standfirst", "image", "published", "modified", "match", "comp", "entities")}


def publish(store, doc):
    store.put_json(f"news/a/{doc['id']}.json", doc, cache="warm")
    lst = (store.get_json("news/articles.json") or {}).get("articles") or []
    lst = [a for a in lst if a["id"] != doc["id"]] + [summary(doc)]
    lst.sort(key=lambda a: a["published"], reverse=True)
    store.put_json("news/articles.json", {"generated": doc["modified"], "articles": lst[:KEEP]}, cache="hot")
```

- [ ] **Step 4: Write `news/articles/run.py`**

```python
"""Tifo articles, Phase 1: match reports. A step of the 15-minute journal job (tools/runner.py job_journal):

  python -m news.articles.run                    # S3 (GitHub Actions)
  python -m news.articles.run --local DIR --dry  # read the live site over HTTP, write into DIR, publish nothing

For each finished priority match of today or yesterday (UAE days): fact sheet -> Sonnet 5.5 -> checks (one rewrite with the
failures, then drop) -> photo -> v1/news/a/r-<id>.json. State in state/articles/state.json: a written match is not written
again unless its fingerprint (score, goals, red cards) changes; a thin match (no events, no stats) is skipped once; API errors
leave it due, three tries at most. Spend is checked before every call; at $180 in a month nothing is written and one email
goes out. types.json «on» false: nothing is written (the switch the owner can flip without a deploy)."""
import argparse, gzip, json, os, sys, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import config  # noqa: E402
from store import Store, S3Backend, LocalBackend  # noqa: E402
from . import facts, due, check, spend, write, photo, publish  # noqa: E402

TYPES = json.loads(Path(__file__).with_name("types.json").read_text(encoding="utf-8"))
STATE = "articles/state.json"
BUCKET = os.environ.get("BUCKET", "elyoxe-football-574771023173-ap-south-1")
UAE = timezone(timedelta(hours=4))
MAX_TRIES = 3


def http_get(path):
    try:
        raw = urllib.request.urlopen(urllib.request.Request("https://tifo.elyoxe.com/v1/" + path,
                                     headers={"Accept-Encoding": "gzip", "User-Agent": "tifo-articles"}), timeout=60).read()
        return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    except Exception:
        return None


def http_bytes(url):
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "tifo-articles"}), timeout=30).read()
    except Exception:
        return None


def _mail_cap(total):
    try:
        import boto3
        boto3.client("ses", region_name="ap-south-1").send_email(
            Source="تيفو <hello@elyoxe.com>", Destination={"ToAddresses": ["hello@elyoxe.com"]},
            Message={"Subject": {"Data": f"مقالات تيفو توقفت: الصرف وصل ${total:.2f} هذا الشهر"},
                     "Body": {"Text": {"Data": "وصل صرف المقالات إلى سقف 180 دولار لهذا الشهر، فتوقفت الكتابة حتى بداية الشهر الجاي."}}})
    except Exception as e:
        print(json.dumps({"cap_mail_error": str(e)[:200]}))


def run(store, data_get, writer, now, *, dry=False, only=None, limit=None, fetch=None):
    out = {"due": 0, "written": 0, "failed": 0, "thin": 0, "skipped": None}
    cfg = TYPES.get("report") or {}
    if not cfg.get("on"):
        out["skipped"] = "report is off in types.json"; return out
    sp = spend.Spend(store, now)
    if not sp.allowed():
        out["skipped"] = f"cap: ${sp.month_total():.2f} this month"; return out
    state = store.get_state(STATE) or {}
    reps = state.setdefault("reports", {})
    uae = now.astimezone(UAE)
    days = [data_get(f"all/{(uae - timedelta(days=d)).strftime('%Y%m%d')}.json") for d in (0, 1)]
    ids = [only] if only else due.finished_priority(days, set(config.awarded()))
    names = facts.load_names()
    n = 0
    for mid in ids:
        if limit and n >= limit:
            break
        md = data_get(f"match/{mid}.json")
        if not md or md.get("status") != "finished":
            continue
        rec = reps.get(str(mid)) or {}
        standings = data_get(f"comp/{md['comp']}/standings.json")
        fixtures = data_get(f"comp/{md['comp']}/fixtures.json")
        sheet, meta = facts.report_sheet(md, standings, fixtures, names)
        if rec.get("status") == "done" and rec.get("fp") == meta["fingerprint"]:
            continue
        if rec.get("status") in ("thin", "failed") and rec.get("fp") == meta["fingerprint"]:
            continue
        out["due"] += 1
        if meta["thin"]:
            reps[str(mid)] = {"status": "thin", "fp": meta["fingerprint"], "at": now.isoformat()}; out["thin"] += 1; continue
        if not sp.allowed():
            break
        n += 1
        art, notes, ok = None, None, False
        try:
            for attempt in (1, 2):
                art, usage = writer.write("report", sheet, cfg["model"], notes=notes)
                sp.add(cfg["model"], usage, "report")
                notes = check.check_article(art, sheet, md)
                if not notes:
                    ok = True; break
        except Exception as e:      # API errors, refusals: the match stays due, three tries at most
            tries = (rec.get("tries") or 0) + 1
            reps[str(mid)] = dict(rec, tries=tries, fp=meta["fingerprint"], at=now.isoformat(),
                                  status="failed" if tries >= MAX_TRIES else "retry", error=str(e)[:200])
            out["failed"] += 1
            continue
        if not ok:
            reps[str(mid)] = {"status": "failed", "fp": meta["fingerprint"], "at": now.isoformat(), "fails": notes[:5]}
            out["failed"] += 1; print(json.dumps({"report_failed": mid, "fails": notes[:5]}, ensure_ascii=False)); continue
        aid = f"r-{mid}"
        img = photo.pick(aid, md, data_get(f"media/{mid}.json"), fetch or http_bytes, store)
        prev = store.get_json(f"news/a/{aid}.json")
        doc = publish.article_doc(aid, "report", art, meta, img, cfg["model"], now.isoformat(), prev)
        publish.publish(store, doc)
        reps[str(mid)] = {"id": aid, "status": "done", "fp": meta["fingerprint"], "at": now.isoformat(), "card": img["card"]}
        out["written"] += 1
    # a report published with the match card gets a frame of the match when the highlights come out (48 h)
    for mid, rec in reps.items():
        if rec.get("status") == "done" and rec.get("card") and rec.get("at", "") >= (now - timedelta(hours=48)).isoformat():
            md = data_get(f"match/{mid}.json"); media = data_get(f"media/{mid}.json")
            if md and media:
                img = photo.pick(rec["id"], md, media, fetch or http_bytes, store)
                if not img["card"]:
                    doc = store.get_json(f"news/a/{rec['id']}.json")
                    if doc:
                        doc["image"], doc["modified"] = img, now.isoformat(); publish.publish(store, doc); rec["card"] = False
    store.put_state(STATE, state)
    sp.save()
    if sp.capped_now():
        _mail_cap(sp.month_total())
    out["spend_month"] = round(sp.month_total(), 4)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--local"); ap.add_argument("--dry", action="store_true"); ap.add_argument("--match", type=int); ap.add_argument("--limit", type=int)
    a = ap.parse_args(argv)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(json.dumps({"articles": "no ANTHROPIC_API_KEY, skipped"})); return 0
    if a.local:
        store, get = Store(LocalBackend(a.local)), http_get
    else:
        store = Store(S3Backend(BUCKET)); get = lambda p: store.get_json(p)
    if a.dry:
        TYPES["report"]["on"] = True
    out = run(store, get, write.Writer(), datetime.now(timezone.utc), dry=a.dry, only=a.match, limit=a.limit)
    print(json.dumps({"articles": out}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest tests/test_articles_run.py -q`
Expected: PASS (6 tests)

- [ ] **Step 6: Run every article test and the whole suite**

Run: `python -m pytest -q`
Expected: all pass (the 438 existing tests and the new ones)

- [ ] **Step 7: Commit**

```bash
git add news/articles/publish.py news/articles/run.py tests/test_articles_run.py
git commit -m "articles: run and publish (state, one rewrite, three tries, fingerprint updates, cap mail, frame upgrade)"
```

---

### Task 9: Run it inside the journal job

**Files:**
- Modify: `tools/runner.py` (`job_journal`, after the `news.run` call)
- Modify: `.github/workflows/tifo-journal.yml` (the «Run the journal job» step)

**Interfaces:**
- Consumes: `python -m news.articles.run` (Task 8)
- Produces: the journal log line `{"articles": {...}}` every 15 minutes

- [ ] **Step 1: Add the step to `job_journal`**

In `tools/runner.py`, right after `rc, tail = run(log, [PY, "-m", "news.run"], timeout=30 * 60)`:

```python
    # Tifo articles (docs/superpowers/specs/2026-11-18-articles-design.md): match reports from the finished priority matches;
    # never fatal (no key, the $180 cap or types.json «on» false: it writes nothing and says why)
    rc5, _ = run(log, [PY, "-m", "news.articles.run"], timeout=12 * 60)
    if rc5:
        log.w(f"news.articles.run exit {rc5} (not fatal)")
```

- [ ] **Step 2: Give the step its key**

In `.github/workflows/tifo-journal.yml`, the step `- name: Run the journal job` becomes:

```yaml
      - name: Run the journal job
        run: python -m tools.runner journal
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GSC_SA_JSON: ${{ secrets.GSC_SA_JSON }}
```

- [ ] **Step 3: Check that the runner still imports and the suite passes**

Run: `python -c "import tools.runner" && python -m pytest -q`
Expected: no output from the import, then all tests pass

- [ ] **Step 4: Commit**

```bash
git add tools/runner.py .github/workflows/tifo-journal.yml
git commit -m "journal: the articles step (not fatal) and its API key"
```

---

### Task 10: The pages: articles, trust pages, the news sitemap

**Files:**
- Create: `site/lib/articles.cjs`, `site/lib/articles.test.cjs`
- Modify: `site/build.cjs`:
  - `page()`: `ogUrl`
  - the `/news/` page: the articles block
  - the match page: the report link
  - `robots.txt`
  - the call to the module

**Interfaces:**
- Consumes: `v1/news/articles.json`, `v1/news/a/<id>.json` (Task 8)
- Produces (module exports):
  - `articleHtml(doc, related) -> string` (the page body)
  - `articleLd(doc, SITE) -> object` (`NewsArticle`)
  - `newsSitemap(docs, SITE, now) -> string` (the last 48 h)
  - `listHtml(summaries) -> string`
  - `related(doc, all, n) -> summary[]`
  - `TRUST: [{path, title, desc, body}]`
  - `render(X) -> Promise<{urls, byMatch}>`, where `X = { get, pool, write, page, esc, SITE, OUT, fs, path }` and `byMatch: {matchId: articleId}`

- [ ] **Step 1: Write the failing test**

```javascript
// node --test site/lib/articles.test.cjs — Tifo articles' pages (lib/articles.cjs) on hand-made documents
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), A = require("./articles.cjs");
const SITE = "https://tifo.elyoxe.com";
const doc = (id, o) => Object.assign({ id, kind: "report", headline: "العين يفوز على الوحدة 2-1", standfirst: "فاز العين.", author: "تحرير تيفو",
  sections: [{ subhead: "الأهداف", paragraphs: ["سجل فلان في الدقيقة 10."] }], facts_box: ["حقيقة"],
  image: { url: SITE + "/v1/news/img/" + id + ".jpg", w: 1200, h: 675, caption: "لقطة", card: false },
  match: 9, entities: [["team", 1], ["team", 2]], published: "2026-11-18T20:00:00+00:00", modified: "2026-11-18T20:05:00+00:00" }, o || {});

test("the page body carries the headline, the byline, the photo with its caption and the trust links", () => {
  const h = A.articleHtml(doc("r-9"), []);
  assert.match(h, /<h1[^>]*>العين يفوز على الوحدة 2-1<\/h1>/);
  assert.match(h, /تحرير تيفو/); assert.match(h, /<figure[\s\S]*r-9\.jpg[\s\S]*<figcaption>لقطة<\/figcaption>/);
  assert.match(h, /href="\/how-we-write\/"/); assert.match(h, /href="\/m\/9\/"/);
});

test("NewsArticle data has the author, the dates and the 1200 px image", () => {
  const ld = A.articleLd(doc("r-9"), SITE);
  assert.equal(ld["@type"], "NewsArticle"); assert.equal(ld.author.name, "تحرير تيفو");
  assert.equal(ld.datePublished, "2026-11-18T20:00:00+00:00"); assert.equal(ld.dateModified, "2026-11-18T20:05:00+00:00");
  assert.deepEqual(ld.image, [SITE + "/v1/news/img/r-9.jpg"]); assert.equal(ld.mainEntityOfPage, SITE + "/news/r-9/");
});

test("the news sitemap lists the last 48 hours only, with the Google News fields", () => {
  const now = Date.parse("2026-11-19T12:00:00Z");
  const xml = A.newsSitemap([doc("r-1"), doc("r-2", { published: "2026-11-10T10:00:00+00:00" })], SITE, now);
  assert.match(xml, /xmlns:news="http:\/\/www\.google\.com\/schemas\/sitemap-news\/0\.9"/);
  assert.match(xml, /<loc>https:\/\/tifo\.elyoxe\.com\/news\/r-1\/<\/loc>/); assert.doesNotMatch(xml, /r-2/);
  assert.match(xml, /<news:name>تيفو<\/news:name><news:language>ar<\/news:language>/);
});

test("related articles share a club, newest first, never the article itself", () => {
  const all = [doc("r-1", { entities: [["team", 1]], published: "2026-11-17T00:00:00Z" }), doc("r-2", { entities: [["team", 5]] }),
               doc("r-3", { entities: [["team", 2]], published: "2026-11-18T00:00:00Z" }), doc("r-9")];
  assert.deepEqual(A.related(doc("r-9"), all, 5).map(d => d.id), ["r-3", "r-1"]);
});

test("the three trust pages exist", () => {
  assert.deepEqual(A.TRUST.map(t => t.path), ["/about/", "/how-we-write/", "/corrections/"]);
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --test site/lib/articles.test.cjs`
Expected: FAIL with `Cannot find module './articles.cjs'`

- [ ] **Step 3: Write `site/lib/articles.cjs`**

```javascript
/* Tifo articles (docs/superpowers/specs/2026-11-18-articles-design.md), read from v1/news/articles.json and v1/news/a/<id>.json:
     /news/<id>/                  the article: the text in the HTML, NewsArticle data, the photo (1200 px, max-image-preview:large),
                                  the byline «تحرير تيفو», links to the match and to the related articles
     /about/ /how-we-write/ /corrections/   the trust pages Google News looks for
     sitemap-news.xml             the last 48 hours (Google News sitemap)
   Called by build.cjs with its helpers; returns the URLs for sitemap.xml and {match id: article id} for the match pages. */
"use strict";
const AUTHOR = "تحرير تيفو";
const E = s => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const T = iso => { try { return new Date(iso).toLocaleString("ar-AE-u-nu-latn", { timeZone: "Asia/Dubai", day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" }); } catch (e) { return ""; } };

const TRUST = [
  { path: "/about/", title: "من نحن | تيفو", desc: "تيفو موقع كرة قدم عربي من الإمارات: النتائج والجداول والمقالات من بيانات تيفو.",
    body: "<h1>من نحن</h1><p>تيفو موقع كرة قدم عربي من الإمارات. ينشر النتائج المباشرة والجداول والإحصائيات لأكثر من 40 بطولة، ومقالات تكتبها «تحرير تيفو».</p><p>المقالات تُكتب من بيانات تيفو نفسها: نتائج المباريات وأحداثها دقيقة بدقيقة، والإحصائيات، والجداول. وإذا استند خبر إلى وسيلة إعلام، ذُكرت باسمها في النص.</p><p>للتواصل: <a href=\"mailto:hello@elyoxe.com\">hello@elyoxe.com</a></p>" },
  { path: "/how-we-write/", title: "كيف نكتب | تيفو", desc: "كيف تكتب «تحرير تيفو» مقالاتها: من البيانات، وبفحص كل رقم قبل النشر.",
    body: "<h1>كيف نكتب</h1><p>كل مقال في تيفو يبدأ من ورقة حقائق: نتيجة المباراة وأحداثها وإحصائياتها وترتيب الفريقين، كما يسجلها تيفو. يُكتب المقال بمساعدة الذكاء الاصطناعي من هذه الورقة وحدها.</p><p>قبل النشر يُفحص المقال آلياً: كل نتيجة ودقيقة ورقم واسم يجب أن يكون في الورقة، وترتيب الأهداف والطرد يطابق المباراة. المقال الذي لا يجتاز الفحص لا يُنشر.</p><p>الصور لقطات من المباراة نفسها من القنوات الرسمية، أو بطاقة المباراة من تيفو.</p>" },
  { path: "/corrections/", title: "سياسة التصحيح | تيفو", desc: "كيف تصحح تيفو الخطأ إذا وقع.",
    body: "<h1>سياسة التصحيح</h1><p>إذا وجدت خطأً في مقال، راسلنا على <a href=\"mailto:hello@elyoxe.com\">hello@elyoxe.com</a> مع رابط المقال.</p><p>نصحح الخطأ في المقال نفسه، ويظهر تاريخ آخر تحديث تحت العنوان. وإذا تغيّرت بيانات المباراة بعد النشر، مثل نسب هدف إلى لاعب آخر، يُعاد كتابة التقرير ويُحدّث تلقائياً.</p>" },
];

function related(doc, all, n){
  const mine = new Set((doc.entities || []).map(e => e.join(":")));
  return all.filter(d => d && d.id !== doc.id && (d.entities || []).some(e => mine.has(e.join(":"))))
    .sort((a, b) => String(b.published).localeCompare(String(a.published))).slice(0, n);
}

function articleHtml(doc, rel){
  const img = doc.image || {};
  const secs = (doc.sections || []).map(s => `<h2>${E(s.subhead)}</h2>` + (s.paragraphs || []).map(p => `<p>${E(p)}</p>`).join("")).join("");
  const facts = (doc.facts_box || []).length ? `<aside class="card facts"><h2>حقائق سريعة</h2><ul>${doc.facts_box.map(f => `<li>${E(f)}</li>`).join("")}</ul></aside>` : "";
  const rl = (rel || []).length ? `<section class="grp"><h2>ذات صلة</h2><ul>${rel.map(r => `<li><a href="/news/${E(r.id)}/">${E(r.headline)}</a></li>`).join("")}</ul></section>` : "";
  const mod = doc.modified && doc.modified !== doc.published ? ` · آخر تحديث ${E(T(doc.modified))}` : "";
  return `<article class="art"><p class="crumbs"><a href="/news/">الأخبار</a></p><h1>${E(doc.headline)}</h1><p class="lede">${E(doc.standfirst)}</p>`
    + `<p class="byline muted">${AUTHOR} · ${E(T(doc.published))}${mod}</p>`
    + (img.url ? `<figure><img src="${E(img.url)}" width="${img.w || 1200}" height="${img.h || 675}" alt="${E(img.caption || doc.headline)}" loading="eager"><figcaption>${E(img.caption || "")}</figcaption></figure>` : "")
    + secs + facts
    + (doc.match ? `<p><a href="/m/${E(doc.match)}/">صفحة المباراة: الأحداث والتشكيلة والإحصائيات</a></p>` : "")
    + rl + `<p class="muted small"><a href="/how-we-write/">كيف نكتب</a> · <a href="/corrections/">سياسة التصحيح</a> · <a href="/about/">من نحن</a></p></article>`;
}

function articleLd(doc, SITE){
  return { "@context": "https://schema.org", "@type": "NewsArticle", headline: doc.headline, description: doc.standfirst,
    image: doc.image && doc.image.url ? [doc.image.url] : [], datePublished: doc.published, dateModified: doc.modified || doc.published,
    author: { "@type": "Organization", name: AUTHOR, url: SITE + "/about/" },
    publisher: { "@type": "Organization", name: "تيفو", logo: { "@type": "ImageObject", url: SITE + "/icons/icon-512.png" } },
    mainEntityOfPage: SITE + "/news/" + doc.id + "/", inLanguage: "ar" };
}

function newsSitemap(docs, SITE, now){
  const recent = docs.filter(d => d && now - Date.parse(d.published) <= 48 * 36e5);
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">\n`
    + recent.map(d => `<url><loc>${E(SITE + "/news/" + d.id + "/")}</loc><news:news><news:publication><news:name>تيفو</news:name><news:language>ar</news:language></news:publication><news:publication_date>${E(d.published)}</news:publication_date><news:title>${E(d.headline)}</news:title></news:news></url>`).join("\n")
    + "\n</urlset>\n";
}

function listHtml(list){
  if (!list || !list.length) return "";
  return `<section class="grp" id="articles"><h2>مقالات تيفو</h2><ul class="arts">${list.map(a => `<li><a href="/news/${E(a.id)}/">${a.image && a.image.url ? `<img src="${E(a.image.url)}" width="120" height="68" alt="" loading="lazy">` : ""}<span>${E(a.headline)}</span></a></li>`).join("")}</ul></section>`;
}

async function render(X){
  const { get, pool, write, page, SITE, OUT, fs, path } = X;
  const lst = ((await get("news/articles.json", 2)) || {}).articles || [];
  const docs = (await pool(lst, 8, a => get(`news/a/${a.id}.json`, 2))).filter(Boolean);
  const urls = [], byMatch = {};
  for (const d of docs){
    write(`news/${d.id}/index.html`, page({ path: `/news/${d.id}/`, page: "ref", title: `${d.headline} | تيفو`, desc: d.standfirst,
      ogUrl: d.image && d.image.url, ogW: d.image && d.image.w, ogH: d.image && d.image.h, ld: articleLd(d, SITE),
      head: '<meta name="robots" content="max-image-preview:large">', body: articleHtml(d, related(d, docs, 5)) }));
    urls.push(`/news/${d.id}/`);
    if (d.kind === "report" && d.match) byMatch[d.match] = d.id;
  }
  for (const t of TRUST){ write(t.path.replace(/^\//, "") + "index.html", page({ path: t.path, page: "ref", title: t.title, desc: t.desc, body: t.body })); urls.push(t.path); }
  fs.writeFileSync(path.join(OUT, "sitemap-news.xml"), newsSitemap(docs, SITE, Date.now()));
  return { urls, byMatch, latest: lst.slice(0, 10) };
}

module.exports = { render, articleHtml, articleLd, newsSitemap, listHtml, related, TRUST, AUTHOR };
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `node --test site/lib/articles.test.cjs`
Expected: PASS (5 tests)

- [ ] **Step 5: Wire it into `site/build.cjs`**

Make five edits:

1. **In `page(o)`:** an article's photo is its `og:image`. In the head template, replace this exact text:

```text
og:image" content="${SITE}/og/${og}.png${o.ogv ? "?v=" + o.ogv : ""}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
```

with:

```text
og:image" content="${o.ogUrl || `${SITE}/og/${og}.png${o.ogv ? "?v=" + o.ogv : ""}`}"><meta property="og:image:width" content="${o.ogW || 1200}"><meta property="og:image:height" content="${o.ogH || 630}">
```

2. **Render the articles before the match pages:** the match pages (around line 1055) are written before the `/news/` page (around line 1316), and they need `ART.byMatch`. Find the line `const SHARE = require("./lib/share_stage.cjs")` (around line 907, before the match pages). Immediately before it, add:

```javascript
  // Tifo articles (lib/articles.cjs): the /news/<id>/ pages, the trust pages, sitemap-news.xml; the match pages link the report,
  // the /news/ page lists the newest ten
  const ART = await require("./lib/articles.cjs").render({ get, pool, write, page, esc, SITE, OUT, fs, path });
  urls.push(...ART.urls);
```

Then find the `/news/` block that starts `{ const nj = (await get("news/latest.json", 2))`. Right after `v5 = P5.news(nj)`, add:

```javascript
v5.body = require("./lib/articles.cjs").listHtml(ART.latest) + v5.body;
```

3. **The match page links its report:** find the line that starts `write(\`m/${id}/index.html\`, page({ v5,`. Before that line, add:

```javascript
    if (ART && ART.byMatch[id]) { const link = `<p class="card"><a href="/news/${ART.byMatch[id]}/">تقرير المباراة من تحرير تيفو</a></p>`;
      v5.body = /<footer class="foot"/.test(v5.body) ? v5.body.replace(/<footer class="foot"/, link + '<footer class="foot"') : v5.body + link; }
```

4. **In `robots.txt`:** append `Sitemap: ${SITE}/sitemap-news.xml\n` to the non-preview string, after the `sitemap-players.xml` line.

- [ ] **Step 6: Build the news pages locally**

Run:
```bash
cd site && TIFO_ONLY='^/(news|about|how-we-write|corrections)/' node build.cjs 2>&1 | tail -5
```
Expected:
- The build ends with `built … pages`.
- `site/out/about/index.html`, `site/out/how-we-write/index.html` and `site/out/corrections/index.html` exist.
- `site/out/sitemap-news.xml` exists. Before Task 13 there are no articles, so it holds no `<url>`.
- Task 13, step 5, checks a real article page once one is live.

- [ ] **Step 7: Run all site tests**

Run: `node --test site/lib/*.test.cjs`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add site/lib/articles.cjs site/lib/articles.test.cjs site/build.cjs
git commit -m "site: article pages, trust pages, sitemap-news.xml, the report link on the match page"
```

---

### Task 11: The weekly measurement

**Files:**
- Create: `tools/gsc_weekly.py`
- Modify: `tools/runner.py` (`job_journal`, after the articles step)
- Test: `tests/test_gsc_weekly.py`

**Interfaces:**
- Consumes: Search Console API (`searchanalytics.query`) with a service account (`GSC_SA_JSON` secret). The owner adds the service account to the property (spec, «Needs the owner»).
- Produces:
  - `gsc_weekly.by_type(rows: list[dict]) -> dict`
  - `rows = [{"keys": [page_url], "clicks": int, "impressions": int}]`
  - The result is `{type: {"clicks", "impressions", "pages"}}`. The type comes from the id prefix: `r-` report, `n-` news, `m-` before the match, `l-` live, `t-` ratings, `s-` table, `a-` Arab players, `fpl-` fantasy, `f-` evergreen.
  - `gsc_weekly.main()` sends one email a week and stores `state/articles/weekly.json`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gsc_weekly.py
"""tools/gsc_weekly.py: Search Console rows grouped by article type (the id prefix after /news/)."""
from tools import gsc_weekly as G


def test_rows_are_grouped_by_the_article_type():
    rows = [{"keys": ["https://tifo.elyoxe.com/news/r-1/"], "clicks": 3, "impressions": 40},
            {"keys": ["https://tifo.elyoxe.com/news/r-2/"], "clicks": 1, "impressions": 10},
            {"keys": ["https://tifo.elyoxe.com/news/fpl-12/"], "clicks": 0, "impressions": 5},
            {"keys": ["https://tifo.elyoxe.com/m/9/"], "clicks": 9, "impressions": 90}]
    got = G.by_type(rows)
    assert got == {"report": {"clicks": 4, "impressions": 50, "pages": 2}, "fantasy": {"clicks": 0, "impressions": 5, "pages": 1}}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_gsc_weekly.py -q`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write `tools/gsc_weekly.py`**

```python
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
    if st.get("last_end") == end.isoformat() or (st.get("last_end") and date.fromisoformat(st["last_end"]) > end - timedelta(days=7)):
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
```

In `tools/runner.py` `job_journal`, after the articles step from Task 9:

```python
    # the weekly «what each article type brought from Google» email (never fatal; skips itself between weeks)
    rc6, _ = run(log, [PY, "-m", "tools.gsc_weekly"], timeout=3 * 60)
    if rc6:
        log.w(f"gsc_weekly exit {rc6} (not fatal)")
```

In `.github/workflows/tifo-journal.yml`, add `GSC_SITE` to the same `env:` as Task 9. Get the value from the property name: run the Search Console MCP `list_properties` (or open Search Console) and copy the property that covers `tifo.elyoxe.com`, e.g. `GSC_SITE: sc-domain:elyoxe.com`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_gsc_weekly.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/gsc_weekly.py tools/runner.py .github/workflows/tifo-journal.yml tests/test_gsc_weekly.py
git commit -m "articles: weekly Search Console numbers per type, by email"
```

---

### Task 12: Post the reports to X from the laptop (workspace repo)

**Files (repo `MrDMX7/workspace`):**
- Create: `content/social/tifo/article_x.py`, `content/social/tifo/article-x-task.vbs`
- Modify: `content/social/tifo/.gitignore` (add `articles_x.json`)
- Test: `content/social/tifo/tests/test_article_x.py`

**Interfaces:**
- Consumes:
  - `https://tifo.elyoxe.com/v1/news/articles.json` (Task 8)
  - `daily.node(args, timeout)` and `daily.browser_down()` (`content/social/tifo/daily.py`)
  - `cards/xpost2.js <caption.txt> <img> --go` (prints `SENT` on success, exits 3 on the wrong account)
- Produces:
  - `article_x.next_to_post(articles: list[dict], posted: set[str], now: datetime, kinds: set[str]) -> dict | None`
  - `article_x.caption(a: dict) -> str`

- [ ] **Step 1: Write the failing test**

```python
# content/social/tifo/tests/test_article_x.py
"""article_x.py: one report per run, oldest unposted first, only from the last 12 hours; the caption is the headline and the link."""
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import article_x as AX

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
A = lambda i, at, kind="report": {"id": i, "kind": kind, "headline": "العين يفوز 2-1", "published": at, "image": {"url": "https://x/i.jpg"}}


def test_the_oldest_unposted_report_of_the_last_12_hours():
    arts = [A("r-3", "2026-11-19T11:00:00+00:00"), A("r-2", "2026-11-19T09:00:00+00:00"), A("r-1", "2026-11-18T20:00:00+00:00"),
            A("n-9", "2026-11-19T08:00:00+00:00", "news")]
    assert AX.next_to_post(arts, set(), NOW, {"report"})["id"] == "r-2"           # r-1 is older than 12 h, n-9 is news
    assert AX.next_to_post(arts, {"r-2"}, NOW, {"report"})["id"] == "r-3"
    assert AX.next_to_post(arts, {"r-2", "r-3"}, NOW, {"report"}) is None


def test_the_caption_is_the_headline_and_the_link():
    assert AX.caption(A("r-2", "x")) == "العين يفوز 2-1\n\nhttps://tifo.elyoxe.com/news/r-2/"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd content/social/tifo && python -m pytest tests/test_article_x.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'article_x'`

- [ ] **Step 3: Write `article_x.py` and the task wrapper**

```python
"""Tifo articles to X (spec, «Share»): every 10 minutes (Task Scheduler «Tifo article X»), the oldest report published in the
last 12 hours that is not on X yet goes out from @elyoxe_tifo: the headline, the link, the article's photo. One post per run
spreads them over the day instead of bursts (the spam risk the spec names). Same browser and lock as the goal posts (daily.py):
if a goal post holds the lock, this run waits for the next."""
import json, sys, tempfile, urllib.request, gzip
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / "articles_x.json"
LOCK = HERE / ".post.lock"
KINDS = {"report"}
SITE = "https://tifo.elyoxe.com"


def next_to_post(articles, posted, now, kinds):
    since = now - timedelta(hours=12)
    fresh = [a for a in articles if a.get("kind") in kinds and a["id"] not in posted
             and datetime.fromisoformat(a["published"]) >= since]
    return min(fresh, key=lambda a: a["published"]) if fresh else None


def caption(a):
    return f"{a['headline']}\n\n{SITE}/news/{a['id']}/"


def main():
    if LOCK.exists() and (datetime.now().timestamp() - LOCK.stat().st_mtime) < 20 * 60:
        print("a goal post holds the browser; next run"); return 0
    raw = urllib.request.urlopen(urllib.request.Request(SITE + "/v1/news/articles.json", headers={"Accept-Encoding": "gzip", "User-Agent": "tifo-x"}), timeout=30).read()
    arts = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw).get("articles") or []
    posted = set(json.loads(STATE.read_text(encoding="utf-8"))) if STATE.exists() else set()
    a = next_to_post(arts, posted, datetime.now(timezone.utc), KINDS)
    if not a:
        print("nothing to post"); return 0
    sys.path.insert(0, str(HERE)); import daily as DL
    tmp = Path(tempfile.mkdtemp())
    cap = tmp / "caption-x.txt"; cap.write_text(caption(a), encoding="utf-8", newline="\n")
    img = tmp / "img.jpg"; img.write_bytes(urllib.request.urlopen(a["image"]["url"], timeout=30).read())
    LOCK.write_text(str(tmp), encoding="utf-8")
    try:
        rc, o = DL.node([DL.POSTER / "lapbrowser.js", "up", "tifo"], 120)
        rc, o = DL.node([HERE / "cards" / "xpost2.js", cap, img, "--go"], 240)
        if "SENT" in (o or "") and "NOT_SENT" not in (o or ""):
            posted.add(a["id"]); STATE.write_text(json.dumps(sorted(posted)), encoding="utf-8", newline="\n")
            print("posted", a["id"])
        else:
            print("not sent", a["id"], (o or "")[-300:])
    finally:
        if LOCK.read_text(encoding="utf-8") == str(tmp):
            LOCK.unlink()
        DL.browser_down()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`article-x-task.vbs` (same shape as `goal-watch-task.vbs`):

```vbscript
' Task Scheduler «Tifo article X»: every 10 minutes, one new Tifo report to X (article_x.py). Hidden window.
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "C:\Users\requi\workspace\content\social\tifo"
sh.Run "cmd /c python -X utf8 article_x.py >> goals\article_x.log 2>&1", 0, True
```

Register the task (PowerShell, on the laptop):

```powershell
$a = New-ScheduledTaskAction -Execute "wscript.exe" -Argument '"C:\Users\requi\workspace\content\social\tifo\article-x-task.vbs"'
$t = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 10)
$s = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -Priority 4
Register-ScheduledTask -TaskName "Tifo article X" -Action $a -Trigger $t -Settings $s -Disable
```

The task is registered **disabled**. Task 13 enables it.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd content/social/tifo && python -m pytest tests/test_article_x.py -q`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit (workspace repo)**

```bash
cd ~/workspace
git add content/social/tifo/article_x.py content/social/tifo/article-x-task.vbs content/social/tifo/.gitignore content/social/tifo/tests/test_article_x.py
git commit -m "tifo: post new article reports to X, one per 10 minutes (task registered disabled)"
```

---

### Task 13: Go live

This task needs the owner twice: the API key (step 1) and Google News Publisher Center (step 7).

- [ ] **Step 1: The key (owner)**
  - The owner creates an API key in the Anthropic Console, on the account that carries the monthly API credit.
  - Then run: `gh secret set ANTHROPIC_API_KEY --repo MrDMX7/elyoxe-football`. Paste the key at the prompt. It is never written to a file or a chat.
  - Optional: a monthly spend limit in the Console as a second fence.

- [ ] **Step 2: A dry run on real matches (laptop)**

```bash
cd ~/workspace/saas/football
ANTHROPIC_API_KEY=… python -m news.articles.run --local out-articles --dry --limit 3
```

Expected: `{"articles": {"due": …, "written": 3, …, "spend_month": 0.1…}}`. There are three files in `out-articles/v1/news/a/`.

Read all three. Check:
- 300-400 words.
- فصحى.
- No Latin.
- The score and the scorers are right against the match page.
- The table line uses «لعب».

If one is wrong, fix `style.md` or the sheet, and run again.

- [ ] **Step 3: Switch reports on**

In `news/articles/types.json` set `"on": true`. Then:

```bash
git add news/articles/types.json && git commit -m "articles: match reports on" && git push
```

Pushing `main` deploys; the owner decided that each type goes live without a sample gate.

- [ ] **Step 4: Watch the first journal runs**

```bash
gh run list --repo MrDMX7/elyoxe-football --workflow tifo-journal.yml --limit 3
gh run view <id> --repo MrDMX7/elyoxe-football --log | grep '"articles"'
```

Expected: `"written"` at 1 or more after a matchday, and no `Traceback`.

- [ ] **Step 5: The site after the next hourly build**

Open `https://tifo.elyoxe.com/news/r-<id>/` for one written report. Check:
- The headline, the byline «تحرير تيفو», the photo and the related links.
- The `NewsArticle` JSON-LD in the source.
- `https://tifo.elyoxe.com/sitemap-news.xml` lists it.
- `/about/`, `/how-we-write/` and `/corrections/` open.

- [ ] **Step 6: X**

Enable the task: `Enable-ScheduledTask -TaskName "Tifo article X"`. After 10 minutes, check `goals\article_x.log` for `posted r-…`, and open @elyoxe_tifo.

- [ ] **Step 7: Google (owner)**
  - Add `tifo.elyoxe.com` in Google News Publisher Center.
  - Create a service account in Google Cloud, add it as a user of the Search Console property, then: `gh secret set GSC_SA_JSON --repo MrDMX7/elyoxe-football < key.json`. Delete `key.json` afterwards.
  - Submit `https://tifo.elyoxe.com/sitemap-news.xml` in Search Console.

- [ ] **Step 8: A week later**

Phase 1 is done when it has been live for a week with no failed check reaching the site. Check:
- `state/articles/state.json` for `failed` entries and their reasons.
- The spend in `state/articles/spend.json`.
- The first weekly email.

Then write the Phase 2 plan (news, «عاجل», the desk, fast sources) from the spec.

# Tifo articles, Phase 2a: news articles and «عاجل» — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every journal story that names a club or player of a priority competition becomes an Arabic news article: at most 60 a day, biggest first. Each article:
- waits 20 minutes, during which a desk file can stop it;
- is written by Sonnet 5.5 from the source texts and Tifo's data, then checked;
- is published at `/news/n-<story id>/` with the source's photo;
- is updated in place when its story grows.

An official announcement goes out first as a short «عاجل» by Haiku 5.5, and the full article replaces it at the same address.

**Architecture:** The news pass is `news/articles/news_run.py`. It runs after the match reports, in the same 10-minute step of the journal workflow, and shares the reports' spend cap, state file, writer, checks and publish code. In order:
1. Read the journal's state (`state/news/state.json`: stories, items, and the player-to-team map).
2. Pick and rank the stories (`news_pick.py`).
3. Queue them for 20 minutes (`queue.py`, which reads `state/articles/desk.json` for vetoes; the desk page that writes that file is Phase 2b).
4. Fetch up to 3 source texts (`sources.py`: Google News links decoded, then text and `og:image` extracted).
5. Build the sheet (`facts.news_sheet`), with Tifo's Arabic names from the journal's own dictionary.
6. Write, check and publish.
7. Post to X with the existing laptop poster, «عاجل» first.

On the laptop, the X reader starts the journal at once when an official account posts.

**Tech Stack:** Python 3.13, `anthropic`, `googlenewsdecoder` (Google News links), `trafilatura` (article text and metadata), Pillow; Node 24 for the X reader and the site.

**Spec:** `2026-11-18-articles-design.md`, in the owner's private workspace repo at `content/social/tifo/articles-test/2026-11-18/`. Read these sections:
- «Article types»: rows 2 and 8, and the paragraphs on «عاجل», «big enough» and «News rules»;
- «The desk»;
- «The pipeline»;
- «Cost».

The spec's Phase 2 is split three ways:
- **2a (this plan):** news, «عاجل», the queue and the desk contract.
- **2b:** the desk page and its API, editing, «اسحب» from the page, and the club and player «الأخبار» tabs.
- **2c:** the fast-sources ranking and the new X accounts.

The Phase 1 plan (`docs/superpowers/plans/2026-11-18-articles-phase1.md`) shows the code this one builds on.

## Global Constraints

- **Language:** فصحى صحفية, Western digits (0-9) always. Written fresh: never translated or paraphrased sentence by sentence, and never a copied paragraph.
- **Sources:**
  - The source is named once, in the text («بحسب ماركا»), with no list of sources and no links out.
  - Quotes appear only when a source carries them; a translated quote says it is translated.
  - The news goes in the first sentence, attribution appears once, and the text says nothing about the sources or the editing (the round-4 rule).
- A rumour is called a rumour, with its stage from `classify.py` and Tifo's credibility mark when there is one. Tifo's own data adds context no source has.
- **Big enough:**
  - a story that names a club or player from a priority competition;
  - one source is enough, and «other» is never written;
  - **at most 60 a day**, biggest first: most outlets, then an official source, then the size of the club.
- A story that gains new facts updates its article (`dateModified`), and never becomes a second article.
- **The news queue is automatic, and the owner vetoes.** Each story waits **20 minutes**:
  - «ارفض» stops it;
  - «اكتب» writes it at once, inside the 60;
  - «اسحب» takes an article off the site.
- **«عاجل»:**
  - for an official account announcing a signing, a sacking, an injury or a sanction;
  - about 120 words by Haiku 5.5, under the story's news id `n-<story id>`;
  - it goes out at once (the spec: «To be first»), and the news article replaces it at the same address;
  - an article that grows is not posted to X again.
- **Models:** news on Sonnet 5.5 (`claude-sonnet-5-5`); «عاجل» on Haiku 5.5 (`claude-haiku-5-5`).
- **Length:** news 250-450 words; «عاجل» 80-160.
- **Photo** (owner, plan review: the photo need not be the source's own; a photo from the internet of the same event, or one that fits the news better, may be better):
  - the candidates are:
    - the photo each outlet put on its article (`og:image`);
    - the journal's own image of each item;
    - Wikimedia Commons photos of who the story is about;
  - only photos at least 1200 px wide count;
  - Haiku 5.5 looks at the candidates with the headline and picks the one that fits the news best, or none. A site's logo or a graphic full of text is never chosen. This costs about $0.0005 an article;
  - the chosen photo is copied to Tifo's storage, with a caption that says who it shows and where it is from;
  - if none fits, Tifo's own card.
- **Names:** Arabic names come from Tifo's dictionaries, never from the model. The sheet carries the Arabic name of every club and player the story names.
- **Spend:** the same $180-a-month stop as Phase 1. News is expected to cost about $3 a day.
- **Files:** Python writes text with `encoding="utf-8", newline="\n"`. In shell heredocs a backslash is mangled, so regexes and `\n` go in files written with the editor.

## Review Focus

1. **A story whose every source is a Google News link that cannot be decoded** (Google blocks GitHub's servers, or the link format changes):
   - The article is written from the headlines and descriptions, never from nothing.
   - The run logs how many links decoded.
   - Test in Task 4.
2. **The same news arriving as two stories** (the journal's clusters split a story):
   - Two articles about the same thing would be the cost.
   - A story is not queued when its first headline shares 60% of its words with an article from the last day on the same club or player.
   - The story's own earlier article never counts against it.
   - Test in Task 3.
3. **A story that grows every 15 minutes** (a transfer saga): it is rewritten at most once an hour, and only when it has gained 2 or more items or a higher stage. Test in Task 7.
4. **A birthday greeting from a club's official account:**
   - `classify.py` (line 78) turns every non-match post of an official account into kind `official`.
   - So «عاجل» needs more than the kind: an official-tier item whose headline passes `classify.official()` (a done announcement), or kind `injury`.
   - Test in Task 8.
5. **The 61st story of the day:**
   - It is not written, even with «اكتب» from the desk. «اكتب» moves a story up, but it does not lift the cap.
   - A queued story that leaves the journal's last 24 hours is dropped from the queue, so tomorrow does not start with yesterday's leftovers.
   - Test in Task 7.

---

## File structure

| File | Responsibility |
|---|---|
| `news/articles/types.json` | + `news` and `breaking` entries (off) |
| `news/articles/style.md` | + the news rule and the «عاجل» rule |
| `tools/record_news_fixture.py` | records a slice of the live journal as a test fixture |
| `news/articles/news_pick.py` | which stories are eligible, their rank, near-duplicates |
| `news/articles/sources.py` | the source texts and images of a story's items |
| `news/articles/facts.py` | + `news_sheet` |
| `news/articles/check.py` | + `check_news` (the source named once) |
| `news/articles/photo.py` | + `commons`, `news_candidates`, `news_pick`, `clubs_card` (the best-fitting photo, else a clubs card) |
| `news/articles/write.py` | + `Writer.pick_photo` (Haiku looks at the candidates) |
| `news/articles/queue.py` | the 20-minute queue, the desk file, the daily cap, the update rule |
| `news/articles/news_run.py` | the news pass |
| `news/articles/publish.py` | `summary()` carries `breaking` |
| `news/articles/run.py` | `main` runs reports (6 min), then news (until minute 8) |
| `news/xreader.js` | starts the journal when an official account posts |
| `requirements-ci.txt` | + `googlenewsdecoder`, `trafilatura` |
| `site/lib/articles.cjs` | «عاجل» label |
| workspace `content/social/tifo/article_x.py` | `KINDS` + `news`, «عاجل» first |

---

### Task 1: Config, dependencies and the two writing rules

**Files:**
- Modify: `news/articles/types.json`, `news/articles/style.md`, `requirements-ci.txt`
- Test: `tests/test_articles_types.py`

**Interfaces:**
- Produces: `types.json` gains two entries:
  - `news` = `{"on": false, "model": "claude-sonnet-5-5", "words": [250, 450], "daily": 60, "wait_minutes": 20}`
  - `breaking` = `{"on": false, "model": "claude-haiku-5-5", "words": [80, 160]}`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_articles_types.py
"""news/articles/types.json and style.md carry Phase 2a's decisions (spec: 60 a day, 20 minutes, Sonnet / Haiku)."""
import json
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "news" / "articles"
T = json.loads((D / "types.json").read_text(encoding="utf-8"))


def test_news_and_breaking_are_configured_and_off():
    assert T["news"] == {"on": False, "model": "claude-sonnet-5-5", "words": [250, 450], "daily": 60, "wait_minutes": 20}
    assert T["breaking"] == {"on": False, "model": "claude-haiku-5-5", "words": [80, 160]}


def test_the_style_guide_has_the_news_and_breaking_rules():
    s = (D / "style.md").read_text(encoding="utf-8")
    assert "الطول من 250 إلى 450 كلمة" in s and "«عاجل»: إذا كان «النوع» في الورقة «عاجل»" in s
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_articles_types.py -q`
Expected: FAIL with `KeyError: 'news'`

- [ ] **Step 3: Write the config and the rules**

`news/articles/types.json`:

```json
{
  "report": {"on": true, "model": "claude-sonnet-5-5", "words": [300, 400]},
  "news": {"on": false, "model": "claude-sonnet-5-5", "words": [250, 450], "daily": 60, "wait_minutes": 20},
  "breaking": {"on": false, "model": "claude-haiku-5-5", "words": [80, 160]}
}
```

Edit `news/articles/style.md` with the editor, not a heredoc:
1. Copy rule 13 (the news rule) word for word from the blind tests' `style4.md`, which is at `content/social/tifo/articles-test/2026-11-18/style4.md` in the workspace repo.
2. Insert it before the MBC Action rule, and renumber the rules after it.
3. End it with «الطول من 250 إلى 450 كلمة، وبلا حشو.».
4. If the copied rule says nothing about quotes, append «لا تقتبس إلا ما اقتبسه المصدر، وإذا ترجمت اقتباساً فقل إنه مترجم.».
5. After it, add the «عاجل» rule:

```text
«عاجل»: إذا كان «النوع» في الورقة «عاجل» فاكتب خبراً قصيراً من 80 إلى 160 كلمة: الجملة الأولى هي الخبر كما أعلنه الحساب الرسمي، ثم جملة أو جملتان من بيانات تيفو إن وُجدت. قسم واحد عنوانه «التفاصيل»، و«حقائق سريعة» من نقطتين أو ثلاث.
```

`requirements-ci.txt`, add:

```text
googlenewsdecoder
trafilatura
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pip install googlenewsdecoder trafilatura && python -m pytest tests/test_articles_types.py tests/test_articles_run.py -q`
Expected: PASS. The run tests patch `TYPES`, so the new keys do not touch them.

- [ ] **Step 5: Commit**

```bash
git add news/articles/types.json news/articles/style.md requirements-ci.txt tests/test_articles_types.py
git commit -m "articles: news and «عاجل» in types.json (off) and the style guide"
```

---

### Task 2: Record a slice of the journal as a fixture

**Files:**
- Create: `tools/record_news_fixture.py` (kept, so the fixture can be recorded again)
- Create: `tests/fixtures/articles/news_state.json`

- [ ] **Step 1: Write the recorder**

```python
# tools/record_news_fixture.py
"""Writes tests/fixtures/articles/news_state.json: three stories of the live journal and their items, in this order:
a transfer story carried by 3+ outlets (one with an official item if there is one), an «other» story with 2+ outlets, and
an injury / statement / presser story with one outlet."""
import gzip, json, subprocess, sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "articles" / "news_state.json"
raw = subprocess.run(["aws", "s3", "cp", "s3://elyoxe-football-574771023173-ap-south-1/state/news/state.json", "-",
                      "--region", "ap-south-1"], capture_output=True, check=True).stdout
st = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
items, stories = st["items"], st["stories"]
outlets = lambda s: len({items[i]["source"] for i in s["items"] if i in items})
official = lambda s: any(items.get(i, {}).get("tier") == "official" for i in s["items"])
newest = sorted(stories.values(), key=lambda s: s["last_at"], reverse=True)
transfers = [s for s in newest if s["kind"] == "transfer" and outlets(s) >= 3]
pick = [next((s for s in transfers if official(s)), transfers[0] if transfers else None),
        next((s for s in newest if s["kind"] == "other" and outlets(s) >= 2), None),
        next((s for s in newest if s["kind"] in ("injury", "statement", "presser") and outlets(s) == 1), None)]
if None in pick:
    sys.exit(f"the live journal has no story of every shape: {[bool(p) for p in pick]}")
keep = {i for s in pick for i in s["items"] if i in items}
OUT.write_text(json.dumps({"stories": {s["id"]: s for s in pick}, "items": {i: items[i] for i in keep}, "pteam": st.get("pteam", {})},
                          ensure_ascii=False), encoding="utf-8", newline="\n")
print([(s["id"], s["kind"], outlets(s), official(s)) for s in pick])
```

- [ ] **Step 2: Record**

Run: `python tools/record_news_fixture.py`
Expected: three tuples. Their kinds, in order, are `transfer`, `other`, and one of injury, statement or presser. The first has 3 or more outlets; the last has 1.

- [ ] **Step 3: Commit**

```bash
git add tools/record_news_fixture.py tests/fixtures/articles/news_state.json
git commit -m "tests: a slice of the journal state (three stories) for the news articles"
```

---

### Task 3: Which stories, in which order

**Files:**
- Create: `news/articles/news_pick.py`
- Test: `tests/test_articles_news_pick.py`

**Interfaces:**
- Consumes:
  - `priority.priority_comps() -> set[int]` and `priority.arab_teams() -> set[int]` (Phase 1);
  - `v1/teams.json`'s `teams`: string id → `{"comps": [...]}`;
  - the journal state's `pteam`: string player id → team id.
- Produces:
  - `news_pick.eligible(story, teams, pteam, now) -> bool`
  - `news_pick.rank_key(story, items, teams) -> list[float]`: higher is bigger. It is `[outlets, best tier, club size, last_at as epoch seconds]`.
  - `news_pick.near_duplicate(story, items, recent) -> str | None`, where `recent` is a list of `{"id", "anchor", "words", "at"}`.
  - `news_pick.words(text) -> set[str]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_articles_news_pick.py
"""news/articles/news_pick.py on a real slice of the journal (tests/fixtures/articles/news_state.json)."""
import copy, json
from datetime import datetime, timezone
from pathlib import Path
from news.articles import news_pick as N

S = json.loads((Path(__file__).parent / "fixtures" / "articles" / "news_state.json").read_text(encoding="utf-8"))
ITEMS = S["items"]
TRANSFER, OTHER, SMALL = S["stories"].values()
ANCH = [e for s in S["stories"].values() for e in s["anchor"]]
TEAMS = {"1": {"comps": [47]}, **{str(i): {"comps": [47]} for k, i in ANCH if k == "team"}}     # all: Premier League
PTEAM = {str(i): 1 for k, i in ANCH if k == "player"}
NOW = datetime.fromisoformat(TRANSFER["last_at"].replace("Z", "+00:00"))


def test_other_is_never_written_and_a_story_must_name_a_priority_club():
    assert N.eligible(TRANSFER, TEAMS, PTEAM, NOW)
    assert not N.eligible(OTHER, TEAMS, PTEAM, NOW)
    assert not N.eligible(TRANSFER, {k: {"comps": [999999]} for k in TEAMS}, {}, NOW)


def test_a_story_older_than_a_day_is_not_eligible():
    assert not N.eligible(TRANSFER, TEAMS, PTEAM, datetime(2030, 1, 1, tzinfo=timezone.utc))


def test_more_outlets_rank_first():
    assert N.rank_key(TRANSFER, ITEMS, TEAMS) > N.rank_key(SMALL, ITEMS, TEAMS)


def test_the_same_news_as_a_second_story_is_a_near_duplicate_but_not_of_itself():
    title = ITEMS[TRANSFER["items"][0]]["title"]
    recent = [{"id": "n-old", "anchor": TRANSFER["anchor"], "words": sorted(N.words(title)), "at": TRANSFER["last_at"]}]
    twin = copy.deepcopy(TRANSFER); twin["id"] = "twin"
    assert N.near_duplicate(twin, ITEMS, recent) == "n-old"
    assert N.near_duplicate(twin, ITEMS, [dict(recent[0], anchor=[["team", -1]])]) is None
    assert N.near_duplicate(TRANSFER, ITEMS, [dict(recent[0], id=f"n-{TRANSFER['id']}")]) is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_articles_news_pick.py -q`
Expected: FAIL with `ImportError: cannot import name 'news_pick'`

- [ ] **Step 3: Write `news/articles/news_pick.py`**

```python
"""Which journal stories become news articles (spec, «A news story is big enough»):
- it names a club or player of a priority competition, or an Arab national team;
- it is any kind but «other», seen in the last 24 hours.
Biggest first: most outlets, then an official source, then the size of the club (the big five and the Champions League,
then the Arab leagues), then the newest.
The journal's clusters can split one news item into two stories. The second is caught by its first headline's words,
against the last day's articles on the same club or player."""
from datetime import datetime, timedelta
from . import priority

BIG = {47, 87, 55, 54, 53, 42}
ARAB = {538, 536, 535, 519, 530, 525}
TIER = {"official": 3, "journalist": 2, "paper": 1, "aggregator": 0}


def _at(s):
    return datetime.fromisoformat((s or "1970-01-01T00:00:00+00:00").replace("Z", "+00:00"))


def words(text):
    from news.entities import norm
    return {w for w in norm(text or "").split() if len(w) > 3}


def _teams_of(story, pteam):
    out = {int(e[1]) for e in story.get("anchor") or [] if e[0] == "team"}
    out |= {int(pteam[str(e[1])]) for e in story.get("anchor") or [] if e[0] == "player" and str(e[1]) in pteam}
    return out


def eligible(story, teams, pteam, now):
    if story.get("kind") in (None, "other") or not story.get("anchor"):
        return False
    if _at(story.get("last_at")) < now - timedelta(hours=24):
        return False
    pri, arab = priority.priority_comps(), priority.arab_teams()
    return any(t in arab or set((teams.get(str(t)) or {}).get("comps") or []) & pri for t in _teams_of(story, pteam))


def rank_key(story, items, teams):
    its = [items[i] for i in story.get("items") or [] if i in items]
    comps = set()
    for e in story.get("anchor") or []:
        if e[0] == "team":
            comps |= set((teams.get(str(e[1])) or {}).get("comps") or [])
    return [len({i.get("source") for i in its}), max((TIER.get(i.get("tier"), 0) for i in its), default=0),
            2 if comps & BIG else 1 if comps & ARAB else 0, _at(story.get("last_at")).timestamp()]


def near_duplicate(story, items, recent):
    first = next((items[i] for i in story.get("items") or [] if i in items), None)
    if not first:
        return None
    w, anc, own = words(first.get("title")), {tuple(e) for e in story.get("anchor") or []}, f"n-{story['id']}"
    for r in recent:
        if r["id"] == own or not anc & {tuple(e) for e in r.get("anchor") or []}:
            continue
        rw = set(r.get("words") or [])
        if w and rw and len(w & rw) / min(len(w), len(rw)) >= 0.6:
            return r["id"]
    return None
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_articles_news_pick.py -q`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add news/articles/news_pick.py tests/test_articles_news_pick.py
git commit -m "articles: which journal stories become news, their order, near-duplicates"
```

---

### Task 4: The source texts and images

**Files:**
- Create: `news/articles/sources.py`
- Test: `tests/test_articles_sources.py`

**Interfaces:**
- Produces: `sources.collect(story, items, *, resolve=None, fetch_html=None, limit=3) -> (list[dict], dict)`.
  - The list has one entry per outlet: `{"source", "lang", "url", "text", "image", "tier"}`.
    - Best first: official, then the most text; at most `limit`.
    - An X item is its own text, with no fetch.
    - A link that cannot be read keeps its title plus description as `text`.
    - Each text is cut at 4000 characters.
  - The dict counts what happened: `{"links", "decoded", "texts"}`.
  - `resolve(url) -> str | None` decodes a Google News link. By default it uses `googlenewsdecoder`.
  - `fetch_html(url) -> str | None`. By default it uses `trafilatura.fetch_url`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_articles_sources.py
"""news/articles/sources.py with fake fetchers (no network):
- Google News links are decoded and the texts extracted;
- X posts are read as they are;
- official first, at most 3;
- a story whose links all fail keeps its headlines and descriptions, and the counts say so."""
from news.articles import sources as SRC

HTML = "<html><head><meta property='og:image' content='https://img/x.jpg'></head><body><article><p>" + ("خبر كامل. " * 80) + "</p></article></body></html>"
ITEMS = {"a": {"source": "AS", "lang": "es", "tier": "paper", "url": "https://news.google.com/rss/articles/AAA", "title": "t a", "desc": "d a"},
         "b": {"source": "Club", "lang": "en", "tier": "official", "url": "https://x.com/club/status/1", "title": "Official: X joins", "desc": "Official: X joins the club."},
         "c": {"source": "BBC", "lang": "en", "tier": "paper", "url": "https://www.bbc.co.uk/sport/1", "title": "t c", "desc": ""},
         "d": {"source": "Kooora", "lang": "ar", "tier": "paper", "url": "https://www.kooora.com/1", "title": "t d", "desc": ""}}
STORY = {"items": ["a", "b", "c", "d"]}


def test_official_first_three_at_most_texts_and_images():
    got, n = SRC.collect(STORY, ITEMS, resolve=lambda u: "https://as.com/1", fetch_html=lambda u: HTML)
    assert got[0]["source"] == "Club" and got[0]["text"].startswith("Official: X joins") and len(got) == 3
    assert all("خبر كامل" in g["text"] and g["image"] == "https://img/x.jpg" for g in got[1:])
    assert n == {"links": 3, "decoded": 1, "texts": 3}


def test_links_that_cannot_be_read_keep_the_headline_and_description():
    got, n = SRC.collect(STORY, ITEMS, resolve=lambda u: None, fetch_html=lambda u: None)
    web = [g for g in got if g["source"] != "Club"]
    assert web and all(g["text"].startswith("t ") and g["image"] is None for g in web)
    assert n["decoded"] == 0 and n["texts"] == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_articles_sources.py -q`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write `news/articles/sources.py`**

```python
"""The source texts of a story (spec: «the main text of up to 3 sources»).

Measured 2026-11-19 on the laptop:
- googlenewsdecoder decodes 11 of 12 Google News links;
- trafilatura extracts the text of 8 of 12, and the og:image of most.
Whether GitHub's servers may decode is measured in Task 10, and every run logs its counts.

An X post is its own text. Whatever cannot be read keeps its headline and description, so a story is never written from
nothing. The texts are for facts only (the style guide tells the writer not to copy) and are cut at 4000 characters."""
TIER = {"official": 3, "journalist": 2, "paper": 1, "aggregator": 0}
CAP = 4000


def _resolve(url):
    try:
        from googlenewsdecoder import gnewsdecoder
        r = gnewsdecoder(url, interval=1) or {}
        return r.get("decoded_url") if r.get("status") or r.get("success") else None
    except Exception:
        return None


def _fetch_html(url):
    try:
        import trafilatura
        return trafilatura.fetch_url(url)
    except Exception:
        return None


def _extract(html):
    try:
        import trafilatura
        meta = trafilatura.extract_metadata(html)
        return trafilatura.extract(html, include_comments=False) or "", (getattr(meta, "image", None) if meta else None)
    except Exception:
        return "", None


def collect(story, items, *, resolve=None, fetch_html=None, limit=3):
    resolve, fetch_html = resolve or _resolve, fetch_html or _fetch_html
    its = sorted((items[i] for i in story.get("items") or [] if i in items), key=lambda i: -TIER.get(i.get("tier"), 0))
    seen, cands = set(), []
    for it in its:
        if it.get("source") not in seen:
            seen.add(it.get("source")); cands.append(it)
    out, n = [], {"links": 0, "decoded": 0, "texts": 0}
    for it in cands[: limit + 2]:                 # two spare: an outlet that yields nothing may be beaten by the next
        url, head = it.get("url") or "", "\n".join(x for x in (it.get("title"), it.get("desc")) if x)
        text, image = "", None
        if "x.com/" in url or "twitter.com/" in url:
            text = it.get("desc") or it.get("title") or ""
        else:
            n["links"] += 1
            real = url
            if "news.google.com" in url:
                real = resolve(url)
                n["decoded"] += bool(real)
            html = fetch_html(real) if real else None
            if html:
                text, image = _extract(html)
                n["texts"] += len(text) > len(head)
            url = real or url
        out.append({"source": it.get("source"), "lang": it.get("lang"), "url": url, "tier": it.get("tier"),
                    "text": (text if len(text) > len(head) else head)[:CAP], "image": image})
    out.sort(key=lambda o: (-TIER.get(o["tier"], 0), -len(o["text"])))
    return out[:limit], n
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_articles_sources.py -q`
Expected: PASS (2 tests). In the first test, three links are read:
- `a`: a Google News link, decoded;
- `c` and `d`: direct links.

The three kept are Club and two of the three web outlets, which have equal text.

- [ ] **Step 5: Commit**

```bash
git add news/articles/sources.py tests/test_articles_sources.py
git commit -m "articles: up to three source texts and images per story (Google News decoded, counts logged)"
```

---

### Task 5: The news fact sheet

**Files:**
- Modify: `news/articles/facts.py` (add `news_sheet`)
- Test: `tests/test_articles_news_sheet.py`

**Interfaces:**
- Consumes:
  - the list from `sources.collect`;
  - the journal's own `news.run.credibility(story, srcs)` and `news.cluster.sources_of(story, items)`, the same pair `news.run.display()` uses;
  - `player/<id>.json`: `name`, `team.name_ar`, `minutes`, `goals`, `assists`, `rating`;
  - `comp/<c>/standings.json`: `groups[].rows[]`, with `team.id`, `rank`, `played` and `pts`;
  - `ar`: the journal dictionary's names, `{(kind, id): arabic}`, from `news.entities.load(teams_json).names`.
- Produces: `facts.news_sheet(story, items, texts, data_get, ar, teams, breaking=False) -> (sheet, meta)`, where:
  - `meta = {"story", "teams", "players", "stage", "items", "subject", "query"}`;
  - `subject` is the Arabic name of the first player or club the story names, for the photo caption;
  - `query` is the Latin name of that player or club, for the Commons photo search.
- **Ruling:**
  - The spec's sheet also lists «contract, transfer history».
  - Tifo's data has neither today: `player/<id>.json` holds season stats only. So they are left out until Tifo has them.
  - Cost if wrong: thinner context in transfer news.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_articles_news_sheet.py
"""facts.news_sheet on the recorded transfer story. The sheet carries:
- the kind and stage, and the credibility mark;
- the source texts and the other headlines;
- the Arabic names from Tifo's dictionary;
- Tifo's data on the players and clubs the story names."""
import json
from pathlib import Path
from news.articles import facts as F

S = json.loads((Path(__file__).parent / "fixtures" / "articles" / "news_state.json").read_text(encoding="utf-8"))
TRANSFER = list(S["stories"].values())[0]
TEXTS = [{"source": "Club", "lang": "en", "url": "https://x.com/1", "tier": "official", "text": "Official.", "image": None}]
AR = {tuple(e): f"اسم {i}" for i, e in enumerate(TRANSFER["anchor"])}


def data_get(path):
    if path.startswith("player/"):
        return {"name": "P", "team": {"name_ar": "النادي"}, "minutes": 900, "goals": 4, "assists": 2, "rating": 7.1}
    return None


def test_the_sheet_carries_the_news_and_tifos_context():
    sheet, meta = F.news_sheet(TRANSFER, S["items"], TEXTS, data_get, AR, {})
    assert sheet["النوع"] == "خبر" and sheet["التصنيف"].startswith("انتقالات")
    assert sheet["نصوص المصادر (للحقائق فقط، لا تُنسخ)"][0]["النص"] == "Official."
    assert sheet["مؤشر المصداقية في تيفو (من 100)"] is not None
    assert set(sheet["الأسماء بالعربية (استعملها كما هي)"]) == set(AR.values())
    assert meta["story"] == TRANSFER["id"] and meta["items"] == len(TRANSFER["items"]) and meta["subject"] in AR.values()
    if TRANSFER["anchor"][0][0] == "player":
        assert meta["query"] == "P"                          # the Latin name, for the Commons photo search
    if any(e[0] == "player" for e in TRANSFER["anchor"]):
        assert any(k.endswith("هذا الموسم") for k in sheet["بيانات تيفو"])


def test_breaking_is_its_own_kind():
    sheet, _ = F.news_sheet(TRANSFER, S["items"], TEXTS, data_get, AR, {}, breaking=True)
    assert sheet["النوع"] == "عاجل"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_articles_news_sheet.py -q`
Expected: FAIL with `AttributeError: module 'news.articles.facts' has no attribute 'news_sheet'`

- [ ] **Step 3: Write `news_sheet` at the end of `news/articles/facts.py`**

```python
KIND_AR = {"transfer": "انتقالات", "injury": "إصابات", "presser": "مؤتمر صحفي", "statement": "تصريحات", "official": "إعلان رسمي",
           "match": "مباراة"}
STAGE_AR = {"rumour": "إشاعة", "talks": "مفاوضات", "agreed": "اتفاق", "here_we_go": "اتفاق نهائي «Here we go»", "official": "رسمي"}


def news_sheet(story, items, texts, data_get, ar, teams, breaking=False):
    """The news fact sheet (spec, «News rules»), in the shape the owner judged in the blind tests (articles-test/build_news.py).
    ar: the journal dictionary's Arabic names {(kind, id): name}; the writer must use them as they are."""
    from news.run import credibility
    from news.cluster import sources_of
    anchor = [tuple(e) for e in story.get("anchor") or []]
    players = [int(i) for k, i in anchor if k == "player"]
    clubs = [int(i) for k, i in anchor if k == "team"]
    tifo, latin = {}, {("team", t): (teams.get(str(t)) or {}).get("name") for t in clubs}
    for pid in players[:3]:
        p = data_get(f"player/{pid}.json")
        if p:
            latin[("player", pid)] = p.get("name")
            row = {"الفريق": (p.get("team") or {}).get("name_ar"), "الدقائق": p.get("minutes"), "الأهداف": p.get("goals"),
                   "الصناعة": p.get("assists"), "التقييم": p.get("rating")}
            tifo[f"{ar.get(('player', pid)) or p.get('name')} هذا الموسم"] = {k: v for k, v in row.items() if v is not None}
    for tid in clubs[:2]:
        for cid in ((teams.get(str(tid)) or {}).get("comps") or [])[:1]:
            st = data_get(f"comp/{cid}/standings.json") or {}
            r = next((r for g in st.get("groups") or [] for r in g.get("rows") or [] if r["team"]["id"] == tid), None)
            if r:
                tifo[f"ترتيب {ar.get(('team', tid)) or _club(r['team'])} الآن"] = {"المركز": r["rank"], "لعب": r["played"],
                                                                                  "النقاط": r.get("pts", r.get("points"))}
    its = [items[i] for i in story.get("items") or [] if i in items]
    cred = credibility(story, sources_of(story, items))
    shown = {t["source"] for t in texts}
    names = [ar[e] for e in anchor if ar.get(e)]
    sheet = {
        "النوع": "عاجل" if breaking else "خبر",
        "التصنيف": KIND_AR.get(story.get("kind"), story.get("kind")) + (f" · المرحلة: {STAGE_AR[story['stage']]}" if story.get("stage") in STAGE_AR else ""),
        "عدد المصادر": len({i.get("source") for i in its}),
        "مؤشر المصداقية في تيفو (من 100)": (cred or {}).get("v"),
        "الأسماء بالعربية (استعملها كما هي)": names,
        "نصوص المصادر (للحقائق فقط، لا تُنسخ)": [{"المصدر": t["source"], "اللغة": t["lang"], "النص": t["text"]} for t in texts],
        "عناوين أخرى عن الخبر نفسه": [{"المصدر": i.get("source"), "العنوان": i.get("title")} for i in its if i.get("source") not in shown][:8],
        "بيانات تيفو": tifo,
    }
    sheet = {k: v for k, v in sheet.items() if v not in (None, [], {})}
    first = (anchor[0][0], int(anchor[0][1])) if anchor else None
    meta = {"story": story["id"], "teams": clubs, "players": players, "stage": story.get("stage"), "items": len(story.get("items") or []),
            "subject": names[0] if names else None, "query": latin.get(first) if first else None}
    return sheet, meta
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_articles_news_sheet.py tests/test_articles_facts.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add news/articles/facts.py tests/test_articles_news_sheet.py
git commit -m "articles: the news fact sheet (stage, credibility, source texts, Arabic names, Tifo's data)"
```

---

### Task 6: The news checks and the news photo

**Files:**
- Modify: `news/articles/check.py` (add `check_news`)
- Modify: `news/articles/photo.py` (add `commons`, `news_candidates`, `news_pick`, `clubs_card`)
- Modify: `news/articles/write.py` (add `Writer.pick_photo`)
- Test: `tests/test_articles_news_check_photo.py`

**Interfaces:**
- Produces:
  - `check.check_news(article, sheet, words) -> list[str]`: Phase 1's `check_article(article, sheet, None, words=words)`, plus a failure when the source is named more than twice.
  - `photo.commons(query, get_json=None, n=4) -> list[dict]`: Wikimedia Commons photos for a name, each `{"url", "source": "ويكيميديا كومنز"}`.
  - `photo.news_candidates(texts, story, items, extra) -> list[dict]`: `{"url", "source"}`, deduplicated, at most 10. The order is the fetched sources' `og:image`, then the journal's item images, then `extra` (the Commons photos).
  - `photo.news_pick(aid, cands, team_ids, fetch, store, subject=None, headline="", judge=None) -> dict`, in `photo.pick`'s shape `{url, w, h, caption, source, card}`.
    - `judge(headline, thumbs) -> int` gets JPEG thumbnails of the candidates 1200 px or wider. It returns the index of the best, or -1 for none.
    - With no judge, or a judge that raises, the widest is used.
  - `photo.clubs_card(team_ids, fetch) -> PIL.Image`
  - `write.Writer.pick_photo(headline, thumbs, model="claude-haiku-5-5") -> (int, usage)`

- [ ] **Step 1: Write the failing tests** (with the editor, not a heredoc)

```python
# tests/test_articles_news_check_photo.py
"""check.check_news, the news photo and Writer.pick_photo. The spec and the owner's plan review ask for:
- the source named once;
- the photo that fits the news best, from the outlets that carried it or from the internet, at least 1200 px, with a
  caption that says who it shows and where it is from; else Tifo's card."""
import io, json, types
from PIL import Image
from store import Store, LocalBackend
from news.articles import check as C, photo as P, write as WR

SHEET = {"النوع": "خبر", "نصوص المصادر (للحقائق فقط، لا تُنسخ)": [{"المصدر": "ماركا", "النص": "x"}]}
art = lambda *p: {"headline": "ع", "standfirst": "م", "sections": [{"subhead": "ق", "paragraphs": list(p)}], "facts_box": []}


def jpg(w, h):
    b = io.BytesIO(); Image.new("RGB", (w, h), (1, 2, 3)).save(b, "JPEG"); return b.getvalue()


IMGS = {"https://i/small.jpg": jpg(800, 450), "https://i/big.jpg": jpg(1600, 900), "https://i/wide.jpg": jpg(2000, 1125)}
CANDS = [{"url": "https://i/small.jpg", "source": "A"}, {"url": "https://i/big.jpg", "source": "B"}, {"url": "https://i/wide.jpg", "source": "ويكيميديا كومنز"}]


def test_the_source_named_again_and_again_fails():
    once = art("قال اللاعب بحسب ماركا إنه سعيد. " + "كلمة " * 260)
    thrice = art("بحسب ماركا وصل اللاعب. وبحسب ماركا وقّع. ونقلاً عن ماركا سيُقدَّم غداً. " + "كلمة " * 260)
    assert not [f for f in C.check_news(once, SHEET, (250, 450)) if "attribution" in f]
    assert [f for f in C.check_news(thrice, SHEET, (250, 450)) if "attribution" in f]


def test_candidates_come_from_the_sources_the_items_and_the_internet_once_each():
    texts = [{"source": "AS", "image": "https://i/a.jpg"}, {"source": "BBC", "image": None}]
    story = {"items": ["x", "y"], "image": "https://i/a.jpg"}
    items = {"x": {"source": "Kooora", "image": "https://i/k.jpg"}, "y": {"source": "AS", "image": "https://i/a.jpg"}}
    got = P.news_candidates(texts, story, items, [{"url": "https://c/1.jpg", "source": "ويكيميديا كومنز"}])
    assert [c["url"] for c in got] == ["https://i/a.jpg", "https://i/k.jpg", "https://c/1.jpg"]
    assert [c["source"] for c in got] == ["AS", "Kooora", "ويكيميديا كومنز"]


def test_commons_reads_the_search_api():
    api = {"query": {"pages": {"1": {"index": 2, "imageinfo": [{"thumburl": "https://u/2.jpg", "width": 3000}]},
                               "2": {"index": 1, "imageinfo": [{"thumburl": "https://u/1.jpg", "width": 2000}]}}}}
    got = P.commons("Mohamed Salah", get_json=lambda url: api)
    assert [c["url"] for c in got] == ["https://u/1.jpg", "https://u/2.jpg"] and got[0]["source"] == "ويكيميديا كومنز"
    assert P.commons("x", get_json=lambda url: None) == []


def test_the_judge_picks_among_the_big_ones_and_the_caption_says_who_and_where(tmp_path):
    st, seen = Store(LocalBackend(tmp_path)), []
    def judge(headline, thumbs):
        seen.append((headline, len(thumbs))); return 1
    got = P.news_pick("n-1", CANDS, [10], IMGS.get, st, subject="محمد صلاح", headline="صلاح يجدد", judge=judge)
    assert seen == [("صلاح يجدد", 2)]                        # the 800 px photo never reaches the judge
    assert not got["card"] and got["caption"] == "محمد صلاح — الصورة من ويكيميديا كومنز"
    assert (tmp_path / "v1" / "news" / "img" / "n-1.jpg").exists()


def test_none_fits_means_tifos_card_and_a_failing_judge_means_the_widest(tmp_path):
    st = Store(LocalBackend(tmp_path))
    assert P.news_pick("n-2", CANDS, [10], IMGS.get, st, judge=lambda h, t: -1)["card"]
    def boom(h, t):
        raise RuntimeError("api down")
    got = P.news_pick("n-3", CANDS, [10], IMGS.get, st, subject="صلاح", judge=boom)
    assert got["caption"] == "صلاح — الصورة من ويكيميديا كومنز"
    assert P.news_pick("n-4", [], [10], IMGS.get, st, judge=boom)["card"]


class FakeClient:
    def __init__(self, answer):
        self.calls, self.answer = [], answer
        self.messages = types.SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        u = types.SimpleNamespace(input_tokens=900, output_tokens=10, cache_read_input_tokens=0, cache_creation_input_tokens=0)
        return types.SimpleNamespace(stop_reason="end_turn", usage=u, content=[types.SimpleNamespace(type="text", text=json.dumps(self.answer))])


def test_pick_photo_sends_the_photos_and_the_headline_to_haiku():
    c = FakeClient({"best": 1})
    best, usage = WR.Writer(c).pick_photo("صلاح يجدد", [jpg(400, 225), jpg(400, 225)])
    kw = c.calls[0]
    blocks = kw["messages"][0]["content"]
    assert best == 1 and usage["in"] == 900 and kw["model"] == "claude-haiku-5-5"
    assert [b["type"] for b in blocks].count("image") == 2 and "صلاح يجدد" in blocks[-1]["text"]
    assert WR.Writer(FakeClient({"best": 7})).pick_photo("x", [jpg(400, 225)])[0] == -1     # out of range: none
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_articles_news_check_photo.py -q`
Expected: FAIL with `AttributeError: module 'news.articles.check' has no attribute 'check_news'`

- [ ] **Step 3: Write them**

At the end of `news/articles/check.py`:

```python
ATTRIB = re.compile(r"(?:بحسب|وفقاً ل|وفقا ل|نقلاً عن|نقلا عن|حسب ما|ذكرت|أفادت)")


def check_news(article, sheet, words):
    """A news article: the Phase 1 checks without a match, and the source named once (spec, «News rules»). Two are allowed:
    a news piece may credit a second outlet for a second fact."""
    fails = check_article(article, sheet, None, words=words)
    n = len(ATTRIB.findall(article_text(article)))
    if n > 2:
        fails.append(f"attribution {n} times; name the source once")
    return fails
```

At the end of `news/articles/photo.py` (add `import base64, json, urllib.parse, urllib.request` at the top if they are missing):

```python
LOGO = "https://images.fotmob.com/image_resources/logo/teamlogo/{}.png"
COMMONS = "ويكيميديا كومنز"
UA = {"User-Agent": "tifo-articles/1.0 (https://tifo.elyoxe.com)"}       # Wikimedia asks every client to name itself


def _get_json(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
            return json.loads(r.read())
    except Exception:
        return None


def commons(query, get_json=None, n=4):
    """Photos of a player or club on Wikimedia Commons, best match first, as 1600 px thumbnails."""
    q = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": n,
                                "gsrsearch": f"{query} filetype:bitmap", "prop": "imageinfo", "iiprop": "url|size", "iiurlwidth": 1600})
    pages = ((get_json or _get_json)(f"https://commons.wikimedia.org/w/api.php?{q}") or {}).get("query", {}).get("pages", {})
    out = sorted(pages.values(), key=lambda p: p.get("index", 99))
    return [{"url": p["imageinfo"][0].get("thumburl") or p["imageinfo"][0]["url"], "source": COMMONS} for p in out if p.get("imageinfo")]


def news_candidates(texts, story, items, extra):
    """Every photo the story offers: the outlets' own (og:image), the journal's item images, then `extra` (Commons)."""
    raw = [(t.get("image"), t.get("source")) for t in texts]
    raw += [((items.get(i) or {}).get("image"), (items.get(i) or {}).get("source")) for i in story.get("items") or []]
    raw += [(c["url"], c["source"]) for c in extra]
    seen, out = set(), []
    for url, src in raw:
        if url and url not in seen:
            seen.add(url); out.append({"url": url, "source": src})
    return out[:10]


def clubs_card(team_ids, fetch):
    """Tifo's card for a news article with no fitting photo: the clubs' logos on Tifo's dark ground."""
    im = Image.new("RGB", (1200, 675), (20, 26, 23))
    ids = list(team_ids)[:2]
    for tid, cx in zip(ids, [600] if len(ids) == 1 else [800, 400]):
        try:
            lg = Image.open(io.BytesIO(fetch(LOGO.format(tid)))).convert("RGBA"); lg.thumbnail((320, 320))
            im.paste(lg, (cx - lg.width // 2, 337 - lg.height // 2), lg)
        except Exception:
            pass
    return im


def _crop169(im):
    w, h = im.size
    if w * 9 > h * 16:
        nw = round(h * 16 / 9); return im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    nh = round(w * 9 / 16); return im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))


def _thumb(im):
    t = im.copy(); t.thumbnail((512, 512))
    b = io.BytesIO(); t.save(b, "JPEG", quality=80); return b.getvalue()


def news_pick(aid, cands, team_ids, fetch, store, subject=None, headline="", judge=None):
    """The candidate that fits the news best (the owner's plan review): the 1200 px and wider ones go to `judge` with the
    headline, which answers an index or -1 (none fits: Tifo's card). Without a judge, or if it fails, the widest."""
    ok = []
    for c in cands:
        try:
            im = Image.open(io.BytesIO(fetch(c["url"]))).convert("RGB")
        except Exception:
            continue
        if im.width >= 1200:
            ok.append((im, c))
    best = max(ok, key=lambda x: x[0].width) if ok else None
    if ok and judge:
        try:
            i = judge(headline, [_thumb(im) for im, _ in ok])
            best = ok[i] if 0 <= i < len(ok) else None
        except Exception as e:
            print(json.dumps({"photo_judge_error": aid, "error": str(e)[:200]}))
    who = f"{subject} — " if subject else ""
    if best:
        im, caption, card = _crop169(best[0]).resize((1200, 675), Image.LANCZOS), f"{who}الصورة من {best[1]['source']}", False
    else:
        im, caption, card = clubs_card(team_ids, fetch), f"{who}بطاقة تيفو", True
    b = io.BytesIO(); im.save(b, "JPEG", quality=86, optimize=True)
    store.put_bytes(f"news/img/{aid}.jpg", b.getvalue(), "image/jpeg", cache="static")
    return {"url": f"{SITE}/v1/news/img/{aid}.jpg", "w": 1200, "h": 675, "caption": caption, "source": "news", "card": card}
```

In `news/articles/write.py`, add this method to `Writer` (and `import base64` at the top):

```python
    PHOTO_SCHEMA = {"type": "object", "properties": {"best": {"type": "integer"}}, "required": ["best"], "additionalProperties": False}
    PHOTO_ASK = ("These are candidate photos, numbered from 0, for an Arabic football news article with the headline below. "
                 "Pick the one that best shows what the news is about: the player, the club or the event it names. Never pick a "
                 "site's logo, a graphic or card full of text, an advert, or a photo of someone else. If none fits, answer -1.\n\n"
                 "Headline: ")

    def pick_photo(self, headline, thumbs, model="claude-haiku-5-5"):
        """-> (index of the best photo or -1, usage). One small call: the thumbnails are 512 px at most."""
        content = []
        for i, t in enumerate(thumbs):
            content += [{"type": "text", "text": f"Photo {i}:"},
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(t).decode()}}]
        content.append({"type": "text", "text": self.PHOTO_ASK + headline})
        msg = self._c().messages.create(model=model, max_tokens=200, messages=[{"role": "user", "content": content}],
                                        output_config={"format": {"type": "json_schema", "schema": self.PHOTO_SCHEMA}})
        text = next((b.text for b in msg.content if b.type == "text"), "")
        try:
            best = int(json.loads(text)["best"])
        except (ValueError, KeyError, TypeError):
            best = -1
        u = msg.usage
        usage = {"in": u.input_tokens or 0, "out": u.output_tokens or 0,
                 "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0, "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0}
        return (best if 0 <= best < len(thumbs) else -1), usage
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_articles_news_check_photo.py tests/test_articles_photo.py tests/test_articles_check.py tests/test_articles_write.py -q`
Expected: PASS. Phase 1's photo, check and write tests stay green.

- [ ] **Step 5: Commit**

```bash
git add news/articles/check.py news/articles/photo.py news/articles/write.py tests/test_articles_news_check_photo.py
git commit -m "articles: news checks (the source named once); the news photo that fits best, picked by Haiku, else Tifo's card"
```

---

### Task 7: The queue, the desk file, the daily cap and updates

**Files:**
- Create: `news/articles/queue.py`
- Test: `tests/test_articles_queue.py`

**Interfaces:**
- Consumes: `state/articles/desk.json` = `{"reject": {story_id: iso}, "write": {story_id: iso}, "withdraw": {article_id: iso}}`. Phase 2b's page will write it; until then, the owner or I write it by hand.
- Produces: `queue.Queue(state, desk, now, cfg)`, with these methods:
  - `.offer(sid, rank)`
  - `.prune(alive_ids)`: drops queued stories that are no longer eligible.
  - `.ready() -> list[str]`: the due stories, not rejected. «write» comes first, then the highest rank, and never past the daily cap.
  - `.mark_written(sid, items, stage)`
  - `.wants_update(sid, items, stage) -> bool`
  - `.written_today() -> int`
- State, under `state["news"]`:
  - `queue`: `{sid: {"first": iso, "rank": [...]}}`
  - `done`: `{sid: {"at", "items", "stage"}}`, each kept 3 days
  - `day`: `"YYYY-MM-DD"`
  - `count`: an int

- [ ] **Step 1: Write the failing test**

```python
# tests/test_articles_queue.py
"""news/articles/queue.py: 20 minutes in the queue, the desk's «ارفض» and «اكتب», 60 a day, updates at most hourly."""
from datetime import datetime, timedelta, timezone
from news.articles import queue as Q

CFG = {"daily": 60, "wait_minutes": 20}
T0 = datetime(2026, 11, 19, 10, 0, tzinfo=timezone.utc)


def q(state, desk=None, now=T0):
    return Q.Queue(state, desk or {}, now, CFG)


def test_a_story_waits_twenty_minutes_then_is_ready():
    st = {}
    q(st).offer("s1", [3, 1])
    assert q(st, now=T0 + timedelta(minutes=19)).ready() == []
    assert q(st, now=T0 + timedelta(minutes=21)).ready() == ["s1"]


def test_the_bigger_story_goes_first():
    st = {}
    q(st).offer("small", [1, 0, 0, 5.0]); q(st).offer("big", [4, 3, 2, 1.0])
    assert q(st, now=T0 + timedelta(minutes=21)).ready() == ["big", "small"]


def test_reject_stops_it_and_write_skips_the_wait():
    st = {}
    q(st).offer("s1", [1]); q(st).offer("s2", [1])
    desk = {"reject": {"s1": T0.isoformat()}, "write": {"s2": T0.isoformat()}}
    assert q(st, desk, now=T0 + timedelta(minutes=1)).ready() == ["s2"]


def test_the_61st_story_of_the_day_waits_even_with_write():
    st = {}
    first = q(st)
    for i in range(61):
        first.offer(f"s{i}", [i])
    later = q(st, {"write": {"s0": T0.isoformat()}}, now=T0 + timedelta(minutes=30))
    got = later.ready()
    assert len(got) == 60 and got[0] == "s0"
    for sid in got:
        later.mark_written(sid, 1, None)
    assert later.written_today() == 60 and later.ready() == []


def test_a_story_that_left_the_journal_window_leaves_the_queue():
    st = {}
    q(st).offer("old", [1]); q(st).offer("new", [1])
    qq = q(st, now=T0 + timedelta(minutes=21)); qq.prune({"new"})
    assert qq.ready() == ["new"]


def test_an_update_needs_two_new_items_or_a_higher_stage_and_an_hour():
    st = {}
    qq = q(st); qq.offer("s1", [1]); qq.mark_written("s1", 3, "rumour")
    assert not q(st, now=T0 + timedelta(minutes=90)).wants_update("s1", 4, "rumour")       # one new item
    assert not q(st, now=T0 + timedelta(minutes=30)).wants_update("s1", 5, "rumour")       # under an hour
    assert q(st, now=T0 + timedelta(minutes=90)).wants_update("s1", 5, "rumour")
    assert q(st, now=T0 + timedelta(minutes=90)).wants_update("s1", 3, "agreed")           # the stage rose


def test_done_entries_older_than_three_days_are_dropped():
    st = {}
    qq = q(st); qq.offer("s1", [1]); qq.mark_written("s1", 1, None)
    assert "s1" not in q(st, now=T0 + timedelta(days=4)).n["done"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_articles_queue.py -q`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write `news/articles/queue.py`**

```python
"""The news queue (spec, «The desk»: automatic, the owner vetoes).

A story waits wait_minutes after it is first offered. The desk file (state/articles/desk.json, written by the desk page in
Phase 2b) can «reject» it, or «write» it at once. At most `daily` new articles a UAE day, and «write» does not lift that.

A written story is updated at most once an hour, and only for 2 or more new items or a higher stage. A queued story that
leaves the journal's window is dropped."""
from datetime import datetime, timedelta, timezone

UAE = timezone(timedelta(hours=4))
STAGE_RANK = {None: -1, "rumour": 0, "talks": 1, "agreed": 2, "here_we_go": 3, "official": 4}


class Queue:
    def __init__(self, state, desk, now, cfg):
        self.now, self.cfg, self.desk = now, cfg, desk or {}
        n = state.setdefault("news", {})
        n.setdefault("queue", {}); n.setdefault("done", {})
        day = now.astimezone(UAE).date().isoformat()
        if n.get("day") != day:
            n["day"], n["count"] = day, 0
        for sid in [s for s, d in n["done"].items() if datetime.fromisoformat(d["at"]) < now - timedelta(days=3)]:
            del n["done"][sid]
        self.n = n

    def offer(self, sid, rank):
        if sid not in self.n["done"]:
            self.n["queue"].setdefault(sid, {"first": self.now.isoformat()})["rank"] = list(rank)

    def prune(self, alive):
        for sid in [s for s in self.n["queue"] if s not in alive]:
            del self.n["queue"][sid]

    def ready(self):
        left = self.cfg["daily"] - self.n["count"]
        if left <= 0:
            return []
        wait = timedelta(minutes=self.cfg["wait_minutes"])
        rej, now_ = set(self.desk.get("reject") or {}), set(self.desk.get("write") or {})
        due = [(sid not in now_, [-x for x in q["rank"]], sid) for sid, q in self.n["queue"].items()
               if sid not in rej and (sid in now_ or datetime.fromisoformat(q["first"]) + wait <= self.now)]
        return [sid for _, _, sid in sorted(due)][:left]

    def mark_written(self, sid, items, stage):
        if sid not in self.n["done"]:
            self.n["count"] += 1
        self.n["done"][sid] = {"at": self.now.isoformat(), "items": items, "stage": stage}
        self.n["queue"].pop(sid, None)

    def wants_update(self, sid, items, stage):
        d = self.n["done"].get(sid)
        if not d or datetime.fromisoformat(d["at"]) + timedelta(hours=1) > self.now:
            return False
        return items - (d.get("items") or 0) >= 2 or STAGE_RANK.get(stage, -1) > STAGE_RANK.get(d.get("stage"), -1)

    def written_today(self):
        return self.n["count"]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_articles_queue.py -q`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add news/articles/queue.py tests/test_articles_queue.py
git commit -m "articles: the news queue (20 min, the desk's reject and write, 60 a day, hourly updates)"
```

---

### Task 8: The news pass and «عاجل»

**Files:**
- Create: `news/articles/news_run.py`
- Modify:
  - `news/articles/publish.py`: `summary()` carries `breaking`.
  - `news/articles/run.py`: `main` runs reports with a 6-minute budget, then news until minute 8.
  - `.github/workflows/tifo-journal.yml`: the step's comment.
- Test: `tests/test_articles_news_run.py`

**Interfaces:**
- Consumes everything above, plus from Phase 1:
  - `publish.article_doc(aid, kind, art, meta, image, model, now_iso, prev)`, `publish.publish(store, doc)` and `publish.withdraw(store, aid, now_iso)`;
  - `spend.Spend.add(model, usage, job)`;
  - `write.Writer.write(kind, sheet, model, notes)`.
- Produces:
  - `news_run.run_news(store, journal, data_get, writer, now, sp, *, deadline, clock, collect=sources.collect, fetch=None, teams_json=None, ar=None, commons=photo.commons) -> dict`, where `journal = {"stories", "items", "pteam"}`.
  - The photo of each article is picked with `photo.news_candidates` and `photo.news_pick`, judged by `writer.pick_photo`; its cost goes to the spend as job `photo`.
  - `news_run.breaking(story, items) -> bool`
- **Ruling:** the reports' budget goes from 8 to 6 minutes, so the news has time in the same 10-minute step. Reports still go first. Cost if wrong: on a night with more than about 6 finished matches, the last reports wait one run (15 minutes).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_articles_news_run.py
"""The news pass end to end with a LocalBackend, a fake writer and fake sources."""
import copy, json
from datetime import datetime, timedelta
from pathlib import Path
import pytest
from store import Store, LocalBackend
from news.articles import news_run as NR, spend

S = json.loads((Path(__file__).parent / "fixtures" / "articles" / "news_state.json").read_text(encoding="utf-8"))
TRANSFER = list(S["stories"].values())[0]
ANCH = [e for s in S["stories"].values() for e in s["anchor"]]
TEAMS = {"teams": {"1": {"comps": [47]}, **{str(i): {"comps": [47]} for k, i in ANCH if k == "team"}}}
PTEAM = {str(i): 1 for k, i in ANCH if k == "player"}
NOW = datetime.fromisoformat(TRANSFER["last_at"].replace("Z", "+00:00"))
TEXTS = [{"source": "Club", "lang": "en", "url": "u", "tier": "official", "text": "Official text.", "image": None}]


class W:
    def __init__(self): self.calls = []
    def write(self, kind, sheet, model, notes=None):
        self.calls.append((sheet["النوع"], model))
        n = 120 if sheet["النوع"] == "عاجل" else 300
        return ({"headline": "عنوان", "standfirst": "مقدمة", "sections": [{"subhead": "ق", "paragraphs": ["كلمة " * n]}], "facts_box": [], "sources_cited": []},
                {"in": 4000, "out": 1500, "cache_read": 0, "cache_write": 0})
    def pick_photo(self, headline, thumbs):
        self.calls.append(("photo", len(thumbs)))
        return 0, {"in": 900, "out": 10, "cache_read": 0, "cache_write": 0}


@pytest.fixture(autouse=True)
def on(monkeypatch):
    monkeypatch.setattr(NR, "TYPES", {"news": {"on": True, "model": "claude-sonnet-5-5", "words": [250, 450], "daily": 60, "wait_minutes": 20},
                                      "breaking": {"on": True, "model": "claude-haiku-5-5", "words": [80, 160]}})


def go(st, now, w, j=None):
    return NR.run_news(st, j or {"stories": S["stories"], "items": S["items"], "pteam": PTEAM}, lambda p: None, w, now,
                       spend.Spend(st, now), deadline=1e12, clock=lambda: 0.0,
                       collect=lambda *a, **k: (TEXTS, {"links": 0, "decoded": 0, "texts": 0}), fetch=lambda u: None,
                       teams_json=TEAMS, ar={}, commons=lambda q: [])


def official_story(title, kind):
    """The transfer story alone, its first item an official account's post with this headline, its others not official."""
    s, items = copy.deepcopy(TRANSFER), copy.deepcopy(S["items"])
    s["kind"] = kind
    items[s["items"][0]].update({"tier": "official", "title": title})
    for i in s["items"][1:]:
        if i in items:
            items[i]["tier"] = "paper"
    return s, {"stories": {s["id"]: s}, "items": items, "pteam": PTEAM}


def test_a_story_is_queued_then_written_by_sonnet_after_twenty_minutes(tmp_path, monkeypatch):
    monkeypatch.setattr(NR, "breaking", lambda s, items: False)
    st, w = Store(LocalBackend(tmp_path)), W()
    assert go(st, NOW, w)["written"] == 0
    assert go(st, NOW + timedelta(minutes=25), w)["written"] >= 1
    doc = st.get_json(f"news/a/n-{TRANSFER['id']}.json")
    assert doc["kind"] == "news" and doc["breaking"] is False and ("خبر", "claude-sonnet-5-5") in w.calls


def test_an_official_signing_goes_out_at_once_as_breaking_by_haiku(tmp_path):
    st, w = Store(LocalBackend(tmp_path)), W()
    s, j = official_story("Official: the club completes the signing", "transfer")
    assert go(st, NOW, w, j)["breaking"] == 1
    assert w.calls == [("عاجل", "claude-haiku-5-5")] and st.get_json(f"news/a/n-{s['id']}.json")["breaking"] is True
    assert st.get_json("news/articles.json")["articles"][0]["breaking"] is True


def test_a_birthday_post_from_an_official_account_is_not_breaking(tmp_path):
    st, w = Store(LocalBackend(tmp_path)), W()
    _, j = official_story("Happy birthday to our legend!", "official")            # what classify.py makes of it
    assert go(st, NOW, w, j)["breaking"] == 0 and w.calls == []


def test_withdraw_from_the_desk_takes_an_article_off_for_good(tmp_path, monkeypatch):
    monkeypatch.setattr(NR, "breaking", lambda s, items: False)
    st, w = Store(LocalBackend(tmp_path)), W()
    go(st, NOW, w); go(st, NOW + timedelta(minutes=25), w)
    aid = f"n-{TRANSFER['id']}"
    st.put_state("articles/desk.json", {"withdraw": {aid: NOW.isoformat()}})
    assert go(st, NOW + timedelta(minutes=30), w)["withdrawn"] == 1
    assert aid not in [a["id"] for a in st.get_json("news/articles-all.json")["articles"]]
    grown = copy.deepcopy(S["stories"]); grown[TRANSFER["id"]]["stage"] = "official"   # the story grows: no rewrite
    go(st, NOW + timedelta(hours=2), w, {"stories": grown, "items": S["items"], "pteam": PTEAM})
    assert aid not in [a["id"] for a in st.get_json("news/articles-all.json")["articles"]]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_articles_news_run.py -q`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write `news/articles/news_run.py`**

```python
"""The news pass (Phase 2a), after the match reports, on the same spend and state.

  journal state -> eligible stories (news_pick) -> the queue (20 min; the desk file) -> source texts (sources) -> sheet
  (facts.news_sheet) -> Sonnet 5.5 -> check_news (one rewrite) -> photo -> v1/news/a/n-<story id>.json

«عاجل» goes out at once, by Haiku 5.5, under the same id; the full article replaces it when its turn comes. It is for an
official announcement of a signing, a sacking, an injury or a sanction (spec, type 8). classify.py makes every non-match post
of an official account kind «official», a birthday greeting too. So the official item's headline must also pass
classify.official() (a done announcement); an injury from an official account needs no more.

Updates happen in place, at most hourly. The desk's «withdraw» takes an article off both lists for good."""
import json
from pathlib import Path
from news import classify as CL
from . import news_pick, queue, sources, facts, check, photo, publish

TYPES = json.loads(Path(__file__).with_name("types.json").read_text(encoding="utf-8"))
STATE, DESK = "articles/state.json", "articles/desk.json"
PHOTO_MODEL = "claude-haiku-5-5"


def breaking(story, items):
    offs = [items[i] for i in story.get("items") or [] if (items.get(i) or {}).get("tier") == "official"]
    if story.get("kind") == "injury":
        return bool(offs)
    return story.get("kind") in ("transfer", "official") and any(CL.official(o.get("title")) for o in offs)


def _write(writer, sp, cfg, sheet, job):
    notes = None
    for _ in (1, 2):
        art, usage = writer.write("news", sheet, cfg["model"], notes=notes)
        sp.add(cfg["model"], usage, job)
        notes = check.check_news(art, sheet, tuple(cfg["words"]))
        if not notes:
            return art, None
    return None, notes


def run_news(store, journal, data_get, writer, now, sp, *, deadline, clock, collect=sources.collect, fetch=None, teams_json=None, ar=None,
             commons=photo.commons):
    out = {"queued": 0, "written": 0, "breaking": 0, "updated": 0, "failed": 0, "withdrawn": 0, "dupes": 0,
           "links": 0, "decoded": 0, "texts": 0}
    news, brk = TYPES.get("news") or {}, TYPES.get("breaking") or {}
    state, desk = store.get_state(STATE) or {}, store.get_state(DESK) or {}
    n = state.setdefault("news", {})

    gone = n.setdefault("withdrawn", [])
    for aid in desk.get("withdraw") or {}:
        if aid not in gone:
            publish.withdraw(store, aid, now.isoformat()); gone.append(aid); out["withdrawn"] += 1
    if not (news.get("on") or brk.get("on")):
        store.put_state(STATE, state); return out

    stories, items, pteam = journal["stories"], journal["items"], journal.get("pteam") or {}
    teams_json = teams_json if teams_json is not None else (data_get("teams.json") or {})
    teams = teams_json.get("teams", teams_json)
    if ar is None:
        from news import entities as E
        ar = E.load(teams_json).names
    q = queue.Queue(state, desk, now, news)
    recent = n.setdefault("recent", [])
    cands = sorted((s for s in stories.values() if news_pick.eligible(s, teams, pteam, now)),
                   key=lambda s: news_pick.rank_key(s, items, teams), reverse=True)
    offered = []
    for s in cands:
        if s["id"] not in n["done"] and news_pick.near_duplicate(s, items, recent):
            out["dupes"] += 1; continue
        q.offer(s["id"], news_pick.rank_key(s, items, teams)); offered.append(s)
    q.prune({s["id"] for s in offered})
    out["queued"] = len(q.n["queue"])

    def save():
        store.put_state(STATE, state); sp.save()

    def publish_story(s, is_breaking):
        aid = f"n-{s['id']}"
        if aid in gone:                                       # withdrawn from the desk: never back
            return None
        texts, counts = collect(s, items)
        for k in ("links", "decoded", "texts"):
            out[k] += counts[k]
        sheet, meta = facts.news_sheet(s, items, texts, data_get, ar, teams, breaking=is_breaking)
        cfg = brk if is_breaking else news
        art, fails = _write(writer, sp, cfg, sheet, "breaking" if is_breaking else "news")
        if not art:
            out["failed"] += 1
            print(json.dumps({"news_failed": s["id"], "fails": (fails or [])[:4]}, ensure_ascii=False)); return None
        def judge(headline, thumbs):
            best, usage = writer.pick_photo(headline, thumbs)
            sp.add(PHOTO_MODEL, usage, "photo")
            return best
        cands = photo.news_candidates(texts, s, items, commons(meta["query"]) if meta.get("query") else [])
        img = photo.news_pick(aid, cands, meta["teams"], fetch or (lambda u: None), store, subject=meta["subject"],
                              headline=art["headline"], judge=judge)
        doc = publish.article_doc(aid, "news", art, meta, img, cfg["model"], now.isoformat(), store.get_json(f"news/a/{aid}.json"))
        doc["breaking"] = is_breaking
        publish.publish(store, doc)
        first = items.get((s.get("items") or [""])[0]) or {}
        recent[:] = [r for r in recent if r["id"] != aid][-299:] + [
            {"id": aid, "anchor": s.get("anchor"), "words": sorted(news_pick.words(first.get("title"))), "at": now.isoformat()}]
        return meta

    rej = set(desk.get("reject") or {})
    if brk.get("on"):                                         # «عاجل» first, at once
        sent = n.setdefault("breaking", [])
        for s in offered:
            if clock() > deadline or not sp.allowed():
                break
            if s["id"] not in sent and s["id"] not in n["done"] and s["id"] not in rej and breaking(s, items):
                if publish_story(s, True):
                    out["breaking"] += 1
                sent.append(s["id"]); del sent[:-500]; save()
    if news.get("on"):
        for sid in q.ready():
            if clock() > deadline or not sp.allowed():
                break
            s = stories[sid]
            if publish_story(s, False):
                q.mark_written(sid, len(s.get("items") or []), s.get("stage")); out["written"] += 1
            else:
                q.n["queue"].pop(sid, None)                    # a story that fails twice is not retried every run
            save()
        for sid in list(n["done"]):
            s = stories.get(sid)
            if not s or clock() > deadline or not sp.allowed():
                continue
            if q.wants_update(sid, len(s.get("items") or []), s.get("stage")):
                if publish_story(s, False):
                    out["updated"] += 1
                q.mark_written(sid, len(s.get("items") or []), s.get("stage"))   # tried: the next try is an hour away
                save()
    save()
    return out
```

`news/articles/publish.py`: `summary()` also copies `breaking`.

```python
def summary(doc):
    return {k: doc.get(k) for k in ("id", "kind", "headline", "standfirst", "image", "published", "modified", "match", "comp", "entities", "breaking")}
```

`news/articles/run.py`: in `main`, replace everything from the `if a.dry:` line to the `return 0` with:

```python
    t0, now = time.monotonic(), datetime.now(timezone.utc)
    if a.dry:
        TYPES["report"]["on"] = True
    out = run(store, get, write.Writer(), now, dry=a.dry, only=a.match, limit=a.limit, budget=6 * 60)
    if not a.match:
        from . import news_run
        j = store.get_state("news/state.json") or {}
        sp = spend.Spend(store, now)                 # reads what run() saved
        if a.dry:
            news_run.TYPES["news"]["on"] = news_run.TYPES["breaking"]["on"] = True
        out["news"] = news_run.run_news(store, {k: j.get(k) or {} for k in ("stories", "items", "pteam")}, get, write.Writer(), now, sp,
                                        deadline=t0 + 8 * 60, clock=time.monotonic, fetch=http_bytes)
    print(json.dumps({"articles": out}, ensure_ascii=False))
    return 0
```

The step's 10-minute timeout stays, since `tests/test_journal_workflow.py` pins it at 10 or less. No news article starts after minute 8, and one takes about a minute.

In `.github/workflows/tifo-journal.yml`, replace the step's two comment lines with:

```yaml
      # Tifo articles (match reports, then news): after the journal's state is saved, so a slow API never costs the journal its
      # state. Reports start no new match after 6 minutes, news no new story after 8 (news/articles/run.py); state is saved after each.
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_articles_news_run.py tests/test_articles_run.py tests/test_journal_workflow.py -q`
Expected: PASS

- [ ] **Step 5: Run the whole suite**

Run: `python -m pytest -q > .superpowers/suite.txt 2>&1; tail -3 .superpowers/suite.txt`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add news/articles/news_run.py news/articles/publish.py news/articles/run.py .github/workflows/tifo-journal.yml tests/test_articles_news_run.py
git commit -m "articles: the news pass (queue, «عاجل» by Haiku, updates, the desk's withdraw) after the match reports"
```

---

### Task 9: «عاجل» on the site and on X, and the X reader's dispatch

**Files:**
- Modify: `site/lib/articles.cjs`, `site/lib/articles.test.cjs` (the «عاجل» label)
- Modify: `news/xreader.js` (start the journal when an official account posts)
- Create: `news/xreader.test.cjs`
- Modify (workspace repo): `content/social/tifo/article_x.py`, `content/social/tifo/tests/test_article_x.py` (news too, «عاجل» first)

**Interfaces:**
- Produces:
  - `xreader.js` exports `shouldDispatch(fresh, lastMs, nowMs) -> boolean`: true when a fresh post has `tier === "official"` and the last dispatch was 5 or more minutes ago.
  - When it is true, the reader runs `gh workflow run tifo-journal.yml --repo MrDMX7/elyoxe-football`.
- **Ruling:**
  - The spec names a GitHub `repository_dispatch`.
  - The journal workflow already accepts `workflow_dispatch`, and `gh` on the laptop has the `workflow` scope since 2026-11-18. So no new trigger is needed.
  - Cost if wrong: none; the effect is the same.

- [ ] **Step 1: Write the failing tests**

`site/lib/articles.test.cjs`, add:

```javascript
test("a breaking article carries the «عاجل» label", () => {
  assert.match(A.articleHtml(doc("n-1", { kind: "news", breaking: true }), []), /<span class="brk">عاجل<\/span>/);
  assert.doesNotMatch(A.articleHtml(doc("n-2", { kind: "news" }), []), /class="brk"/);
});
```

`news/xreader.test.cjs`:

```javascript
// node --test news/xreader.test.cjs: when the X reader starts the journal at once (an official post, at most every 5 min)
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const { shouldDispatch } = require("./xreader.js");
test("an official post starts the journal, not more than every 5 minutes", () => {
  const off = [{ tier: "official" }], paper = [{ tier: "paper" }];
  assert.equal(shouldDispatch(off, 0, 10 * 60e3), true);
  assert.equal(shouldDispatch(paper, 0, 10 * 60e3), false);
  assert.equal(shouldDispatch(off, 8 * 60e3, 10 * 60e3), false);
});
```

`content/social/tifo/tests/test_article_x.py` (workspace), add:

```python
def test_news_articles_are_posted_too_and_breaking_goes_first():
    assert AX.KINDS == {"report", "news"}
    arts = [A("r-2", "2026-11-19T09:00:00+00:00"), dict(A("n-7", "2026-11-19T11:00:00+00:00", "news"), breaking=True)]
    assert AX.next_to_post(arts, set(), NOW, AX.KINDS)["id"] == "n-7"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `node --test site/lib/articles.test.cjs news/xreader.test.cjs` and `cd ~/workspace/content/social/tifo && python -m pytest tests/test_article_x.py -q`
Expected: FAIL. The label is missing, `shouldDispatch` is not exported, and `KINDS` lacks `news`.

- [ ] **Step 3: Implement**

The label, in `site/lib/articles.cjs`'s `articleHtml`:
- The `<h1>` becomes `<h1>${doc.breaking ? '<span class="brk">عاجل</span> ' : ""}${E(doc.headline)}</h1>`.
- Add `.brk{color:var(--live);font-weight:700}` next to the article styles. `--live` is the site's «حيّ» colour; if the stylesheet names it differently, use that name.

`news/xreader.js` (read the whole file first):
1. Add `function shouldDispatch(fresh, lastMs, nowMs) { return fresh.some(p => p.tier === 'official') && nowMs - (lastMs || 0) >= 5 * 60e3; }` and `module.exports = { shouldDispatch };`.
2. Guard the call to `main()` with `if (require.main === module)`, so the test can require the file.
3. In `main`, collect every account's `fresh` posts into one array. Line 226 already gives each post its `tier`.
4. Right after the `--upload` line (237), when `shouldDispatch(allFresh, st.lastDispatchMs, Date.now())` is true:
   - run `execSync('gh workflow run tifo-journal.yml --repo MrDMX7/elyoxe-football', { stdio: 'inherit', timeout: 60000 })` inside a try/catch;
   - store `Date.now()` as `lastDispatchMs` in the reader's state file. The reader already has one; read its name in the file.

`content/social/tifo/article_x.py`:
- `KINDS = {"report", "news"}`.
- In `next_to_post`, sort `fresh` by `(not a.get("breaking"), a["published"])` instead of by `a["published"]`.

- [ ] **Step 4: Run them to verify they pass**

Run: the same commands as Step 2.
Expected: PASS

- [ ] **Step 5: Commit (two repos)**

```bash
git add site/lib/articles.cjs site/lib/articles.test.cjs news/xreader.js news/xreader.test.cjs
git commit -m "articles: «عاجل» label; the X reader starts the journal on an official post (at most every 5 min)"
cd ~/workspace && git add content/social/tifo/article_x.py content/social/tifo/tests/test_article_x.py
git commit -m "tifo article X: news articles too, «عاجل» first"
```

---

### Task 10: Dry run on the real journal, then go live

- [ ] **Step 1: A dry run on the subscription**
  1. Make a local folder `D` and copy two files into it:
     - `aws s3 cp s3://elyoxe-football-574771023173-ap-south-1/state/news/state.json D/state/news/state.json --region ap-south-1`, copying the bytes as they are (`get_state` reads gzip);
     - the live `v1/teams.json` into `D/v1/teams.json`.
  2. In a scratchpad script, call `news_run.run_news` with:
     - `Store(LocalBackend(D))`;
     - `run.http_get` as `data_get`, which reads the live site's data;
     - the Phase 1 dry-run writer, which has `Writer.write`'s signature and answers through `claude -p` with `style.md` and the sheet;
     - `TYPES["news"]["wait_minutes"] = 0` and `daily = 3`.
  3. Read all three articles. Check that:
     - the news is in the first sentence;
     - the source is named once;
     - the facts match the source texts;
     - there is no Latin;
     - the Arabic names are Tifo's;
     - the photo fits the news (who or what it shows), and the caption says who and where from.
  4. Record the `links`, `decoded` and `texts` counts.

- [ ] **Step 2: Can GitHub's servers read Google News?**
  1. With news still off, push a temporary workflow step. It runs `sources.collect` on the 10 newest stories of the journal state and prints the counts.
  2. Run it once with `gh workflow run`, then remove the step.
  3. If fewer than half the links decode:
     - news is written from the headlines, the descriptions and the X posts, which still pass the checks;
     - the text-heavy outlets get direct RSS links in `sources.yaml` (BBC, AS, Marca and Kooora have them);
     - tell the owner. The fix (the laptop decodes and uploads the texts) goes in 2c.

- [ ] **Step 3: Switch on**
  1. The owner decides when. The desk page (2b) is what gives him «ارفض»; until then he vetoes by asking me, and I write `state/articles/desk.json`.
  2. Set `news.on` and `breaking.on` to true, then push.
  3. Watch the first two journal runs:
     - the log line `"news": {...}`, with the queued, written, breaking, dupes and decoded counts;
     - the first articles' text and photos;
     - the spend.

- [ ] **Step 4: A week later**
  1. Check:
     - the articles a day (60 or fewer);
     - the `news_failed` reasons;
     - the duplicates that got through;
     - any «عاجل» that should not have gone out;
     - the spend against $180;
     - the X posts.
  2. Then write Phase 2b.

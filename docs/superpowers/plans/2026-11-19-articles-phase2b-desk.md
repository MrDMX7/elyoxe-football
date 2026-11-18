# Tifo articles, Phase 2b (first version): the desk — implementation plan

> Executed inline in the session that built Phase 2a (the owner asked for the desk's link the moment news went on). Steps are
> TDD for every Python change; the page is checked in a browser at phone width against the live data.

**Goal:** A private page, made for the phone, where the owner sees the news queue and what was published, and acts on it:
- «ارفض» a story before it is written, and «اكتب» one further down the list (inside the 60 a day);
- «اسحب» an article off the site;
- edit any article by hand: headline, standfirst, every paragraph, the facts box, and the photo (picked from the other photos
  the sources carried). Every save is a version; any version can be put back. An article he edited is never rewritten
  automatically;
- see the month's spend against the $180 cap.

Editing by instruction and «اكتب مقال عن…» requests come next. They need the Claude key in AWS as well as in GitHub, which is the
owner's step.

**Architecture:**
- **The journal run writes what the desk shows.** `news/articles/news_run.py` writes `state/articles/desk-view.json` on every
  run: the top 150 candidates, each with its title, kind, stage, outlets, names, and its state. The states are: queued (and
  when it is due), written (and its article), rejected, failed, duplicate, withdrawn, or past the day's cap. It also saves
  each article's fact sheet and photo candidates at `state/articles/sheets/<id>.json`.
- **A Lambda behind an HTTP API serves the page and the API** (`desk/`, stack `tifo-desk`, ap-south-1). A Function URL
  returns 403 in this account, so it uses an HTTP API, like the contact form.
  - Every API call carries the key in a header. The key is generated once into SSM Parameter Store (SecureString
    `/tifo/desk-key`), never in the repo, and the link carries it in the fragment (`#k=…`), which never reaches a server log.
  - The Lambda writes:
    - `state/articles/desk.json` (reject / write / withdraw);
    - the article file and both lists, through `news/articles/publish.py` itself, copied into the bundle;
    - versions at `state/articles/versions/<id>/<n>.json`.
- **«اكتب» is picked up by the next journal run** (within 15 minutes). «اسحب» takes the article off both lists at once, and
  the static page goes with the next hourly build.

**Spec:** `content/social/tifo/articles-test/2026-11-18/articles-design.md` (private workspace repo), section «The desk».

## Files

| File | Responsibility |
|---|---|
| `news/articles/news_run.py` | + the desk view, the per-article sheet and photos, edited articles left alone |
| `desk/lambda/app.py` | the handler: auth, routes, actions, edits, versions |
| `desk/lambda/s3store.py` | the store's file format (gzip JSON, cache headers) for the Lambda |
| `desk/lambda/desk.html` | the page |
| `desk/deploy.py` | SSM key, role, Lambda, HTTP API; prints the link |
| `tests/test_desk_app.py`, `tests/test_articles_news_run.py` | the tests |

## Tasks

1. **news_run:** the desk view, sheets and photo candidates per article, and a doc with `edited: true` is never rewritten
   (and its growth is flagged in the view as `grew`). Tests: the view lists queued, written and rejected stories with their
   due times; an edited article is not rewritten when its story grows.
2. **desk/lambda/app.py** with a fake backend. Tests:
   - no key or a wrong key gets 401;
   - the view returns queue, published and spend;
   - reject / unreject / write / withdraw change desk.json, and withdraw also takes the article off both lists;
   - an edit makes a version, marks the doc edited, and updates the lists' summary;
   - restore puts a version back as a new version;
   - a photo pick replaces the image;
   - an unknown article gets 404.
3. **desk/lambda/desk.html:** three tabs (الطابور، المنشور، المصروف) and the editor, RTL and phone-first, in Tifo's colours.
4. **desk/deploy.py:** idempotent; prints the link.
5. **Verify** at phone width in the browser against the live data, then send the owner the link.

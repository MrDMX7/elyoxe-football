# تيفو: design system v3 ("the stand at night")

**Status:** a prototype for the owner to approve. Nothing outside `/next/` changes until he says yes.

**The brief:** «احس واجهة الموقع مب clean، اريدها احترافية واسطورية كانك داخل Netflix … لا تفرط بالميزات». The owner complained about clutter and order. He did not complain about the brand, so v2's identity stays (`site/DESIGN.md`). v3 changes two things:
- **Weighting:** the site moves from concrete-with-dark-panels to night-pitch-first.
- **Structure:** a small set of fixed slots, so features stop stacking.

## 1. What stays from v2 (unchanged tokens)
| token | value | rule |
|---|---|---|
| ليل الملعب (night) | `#0A2620` | **now the page ground** everywhere |
| night-2 / night-3 | `#123A31` / `#0F3129` | raised surfaces: rail cards, sheets, table heads |
| طباشير (chalk) | `#F6F7F2` | text and lines on night |
| إسمنت (concrete) | `#E9ECE7` | secondary text on night (`#B9C7C0` for tertiary); the light "paper" only inside print/poster pages |
| رمل (dune) | `#B07A3B` | **my team and the selected state only** (active tab underline, my-team row, pressed segment) |
| نبض (pulse) | `#10A04B`; `#5BE08F` for text on night | **live only** |
| yellow / red cards | `#F2C230` / `#D8343F` | **cards only** |

- **Atom:** the flat square card. It is still the atom: no radius, no drop shadows, and the live pulse is still a card flipping.
- **Signature:** the stand mosaic built from club colours is now **the key art** of every hero. It replaces photography, which we can't use for licensing and page-weight reasons.
- **Type:**
  - Noto Kufi Arabic 800 for display.
  - Readex Pro 400/600 for reading.
  - Barlow Condensed 700 for every digit.
  - Digits are always Western, 0-9.

## 2. What v3 adds
- **Scale.** Hero type is huge.
  - Club names in the hero: `clamp(1.6rem, 5vw, 3.4rem)` Kufi.
  - Scores: `clamp(4.5rem, 16vw, 9rem)` Barlow.
  - Everything below the hero is calm, at 0.95rem reading size.
- **Scrim.** Every hero is the mosaic under a night gradient: transparent at the top, solid night at the bottom. The type sits on solid night and stays readable over any club's colours.
- **Rails.** These are horizontal, snap-scrolling rows of fixed-width cards.
  - They start at the right edge (RTL), and the first card is flush with the text gutter.
  - The next card peeks by about 15% so the row reads as scrollable.
  - From 880px, rails get arrow buttons at the rail ends (native scrolling otherwise).
- **Motion.** Motion is limited to the following:
  - The mosaic flips in right to left once.
  - A touch sends a wave, and so does a goal.
  - The hero parallaxes at 0.35× scroll and fades as it leaves.
  - Sections fade up once, 8px over 400ms.
  - Sheets slide 220ms.
  - `prefers-reduced-motion` turns off all of it: the mosaic is static, and there is no parallax and no fade.

## 3. Hard layout rules (these stop clutter coming back)
1. **Primary nav has at most 5 items.** They are: اليوم · البطولات · المنتخبات · الأسبوع · المزيد.
   - On phones the nav is a bottom tab bar. From 880px it sits in the top bar.
   - Search is an icon in the top bar, not a nav item.
   - Every other destination (majlis TV, studio, legends, laws, lab, academy…) lives in the **المزيد sheet**, grouped under headings, and in the footer.
   - A new destination never becomes a sixth nav item.
2. **The home page has a fixed set of slots, in this order.** Nothing else goes on it.
   1. `hero`
   2. `rail:live` (only while something is live)
   3. `rail:today`
   4. `rail:arab`
   5. `rail:mine`
   6. `list:day`, the full match centre: day switcher, one segmented filter, and matches grouped by competition, folded after 4 competitions
   7. `grid:comps`
   8. `rail:tifo`, the editorial rail

   The hero carries `#uaecd` (national-team countdown) as one line, and `#since` («since your last visit») sits directly under it.

   - A feature that wants home space must replace a card inside an existing rail, or become an editorial card in `rail:tifo`.
   - It never becomes a new stacked block.
3. **Every template has a fixed skeleton:** `hero` → one `tabs` bar (at most 5 tabs) → the tab panes → `footer`.
   - A new feature goes by default into an existing tab as a **shelf tile** (see rule 6).
   - If it is a page-level action, it goes into the page's single sheet.
   - It never becomes a new block between the hero and the tabs.
4. **Each page has one share/tools sheet.**
   - It has three triggers that all open the same sheet: the share icon in the top bar, the «شارك» button in the hero, and the share icon on the match mini-bar.
   - The sheet holds everything the page used to show as a tool row:
     - copy the link
     - native share
     - story image
     - second screen
     - majlis TV
     - creator kit
     - calendar and wallpaper on team pages
   - It also holds **one «صورة لأي قسم» picker**, which replaces the per-section «شارك» buttons (feature 250 is kept; it is simply picked from a list).
   - Per-section share buttons are banned.
5. **One segmented control per choice.**
   - A choice between views (table variants, day filter, scorers vs. assisters) is one segmented control: a single bordered row of flat cells, with the selected cell in chalk on night and a dune underline.
   - Rows of pill buttons are banned.
   - Filters that are toggles (Arab only, free only) are segments of the same control («الكل · العرب · المجاني في بلدك»), not separate buttons.
   - A long sequence (rounds 1…26) is a scroller of number cells. It is still one control, with the current cell centred.
6. **Analytics live in tabs, as shelves, and load lazily.**
   - Inside a tab there is at most **one lead block** rendered inline, the thing people came for: the table, the round's fixtures, the scorers.
   - Every other analytics section is a **tile** in that tab's shelf (a grid of titled tiles).
   - Opening a tile opens the **reader panel**. That is a bottom sheet on phones and a centred panel from 880px.
   - A tile's content ships inside `<template>` and is stamped into the DOM the first time it opens. The HTML is there for crawlers, but it costs no layout until someone opens it.
   - Sections that `app.js` wires at start-up (what-if, round predictions image, replay) are not templated. They move into the panel as live nodes.
   - Deep links keep working. `#num` opens the tab, and `#n-cards` opens the tab and then the tile.
7. **Every piece of copy has a single place.**
   - A heading is written once.
   - The «شو يعني؟» glossary links move into the panel header of their tile, one per tile, not repeated inline.
8. **Names are in Arabic.**
   - Player names come from `names/players_ar.json`, applied to player-shaped nodes only (events, lineups, scorer lists).
   - Latin is the fallback, isolated with `.lat`.
9. **Budgets.** Measured on the prototype: CSS 15.0 KB gzip (v2: 9.3 KB), JS 40.7 KB gzip in one file (v2: 34.1 KB across render/app/share/stand). That is +5.7 KB CSS and +6.6 KB JS, with no new frameworks. Only the key-art canvas animates, and only on load and in answer to something (a touch or a goal).

## 4. Components
- **Top bar.**
  - Brand mark on the right (RTL start), search, then «شارك» on pages that have a sheet.
  - Transparent over the hero; it becomes solid night at 90% opacity after 40px of scroll.
- **Bottom tab bar** (<880px): five icon+label cells made of 1.4rem cards. The current cell has a dune underline.
- **Hero** (`data-slot="hero"`): the mosaic canvas, the scrim, a kicker ("مباشر الحين", "الليلة", "فريقك", "انتهت"), the big match line, and two actions («تابع المباراة», «شارك»).
- **Mini-bar:** the match page's sticky compact score. It appears when the hero leaves the viewport and updates live from the same poll.
- **Rail card:** a 15rem match card. It has a club-colour band on each outer edge, crests, names, a score or time, and the competition as a small line. A live card has a pulse border.
- **Segmented control** (`.seg`), **tabs** (`.tabs`: Kufi, with a dune underline on the selected tab, sticky under the top bar), **shelf** (`.shelf` of `.tile`), **reader panel** (`.panel`), **sheet** (`.sheet`).
- **Crest grid:** competitions as square tiles on a mosaic of their clubs' colours, with the name below. «كل البطولات» opens the full list.

## 5. New Arabic UI copy (light Emirati, checked against EMIRATI-LEXICON.json)
- اليوم · البطولات · المنتخبات · الأسبوع · المزيد
- مباشر الحين · الليلة · فريقك · مباريات العرب · من تيفو
- تابع المباراة · شارك · شارك وأدوات · انسخ الرابط · انتسخ ✓ · صورة لأي قسم · سكّر
- كل المباريات · كل البطولات · بعد في هالتبويب
- اختار فريقك من صفحة أي نادي، ومبارياته تطلع لك هني أول شي.
- Forbidden forms: وش، زي، تبي، الجاي، جديد، مين, and never ـج addressing the reader.

## 6. Template map: where every old feature goes
The machine-checked version is `redesign/inventory.diff.json`, from `node redesign/inventory.cjs new`.
- **Home**
  - The stand becomes the hero.
  - `#uaecd` (the countdown) moves into the hero kicker line.
  - `#since` goes under the hero.
  - Majlis TV and the studio go into المزيد and `rail:tifo`.
  - `#mine` becomes `rail:mine`.
  - The day nav and the Arab/free toggles become `list:day` plus a segmented control.
  - Yesterday and tomorrow are the day switcher's arrows. The /today/ and /tomorrow/ pages are the rail headers' links («مباريات اليوم» on the today rail, «مباريات بكرة» on the Arab rail) and entries in المزيد.
  - The editorial blocks (best matches, this day, the international window, match of the week, streaks, birthdays, records tonight, daily 5) go into `rail:tifo` cards, each opening the reader panel.
  - The competitions list becomes `grid:comps`.
- **Match**
  - Hero, then 5 tabs: الأحداث (or «قبل المباراة» before kickoff) · التشكيلة · الإحصائيات · التحليل · المواجهات.
  - The tool row goes into the sheet.
  - The catch-up summary, facts and prayer/weather tiles open the first tab.
  - Opponent report, press sheet, X thread, win-probability chart, firsts, tactics, replay, score grid, fatigue, the AI summary and the preview become the shelf of التحليل.
  - The FAQ sits at the page bottom, folded.
  - Substitutions in the same minute and for the same team go on one line.
- **Competition**
  - A hero with the league's key art (its clubs' colours, in table order), the leader and the next round.
  - 5 tabs: الترتيب · المباريات · الأرقام · التوقعات · التاريخ.
  - Table variants become a segmented control.
  - Scorers and assisters become the lead of الأرقام, as a segmented control.
  - The other 26 number sections, 15 prediction sections and 8 history sections become shelf tiles.
  - Compare and power rankings go into the sheet and onto tiles.

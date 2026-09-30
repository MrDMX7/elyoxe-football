# تيفو v5: «a clean iPhone app» (design rules)

**Status:** preview for the owner at https://tifo.elyoxe.com/next/ (noindex). Production templates are untouched.
**Brief (owner, 2026-09-30):** راقي، نظيف، موديرن بطابع رياضي، سهل للمستخدم مع إبقاء الخصائص، clean iPhone app feel، ممتاز من الهواتف، موقع متكامل.
**Lesson from 2026-09-29:** looks A–F were the same layout re-skinned and all were rejected. v5 changes the structure, the hierarchy and the interaction model; the tokens follow from that.

## 1. Structure: the iOS app shell
- **Tab bar (5, floating glass capsule):** اليوم · البطولات · الأخبار · فريقي · المزيد. A new destination never becomes a sixth tab; it becomes a row in المزيد.
- **Every page has one skeleton:** compact nav bar (transparent, turns to glass with a hairline once the title scrolls under it, the compact title fades in) → large title (34/41 bold) or an entity header → **one segmented control** (≤ 5 segments, sticky under the bar) → grouped inset lists → footer.
- **Search** is the magnifier in the nav bar of every tab, never a tab.
- **Sheets** (`<dialog>`, grabber, swipe down, spring) hold every secondary action: share, the day filter and «بلدك», «نبّهني», picking teams, and every analysis detail.
- **One lead block per segment.** The table, the events, the scorers or the season simulation is shown; every other analysis is a row in a grouped list («بالتفصيل», «كل الأرقام», «بعد في التوقعات», «بعد في التاريخ») that opens a sheet. This is what stops clutter coming back.
- **Entity pages** (match, competition, team, player) open with a header that carries identity and one primary action (تابع), not with a hero banner.

## 2. Components
- **Grouped inset list:** 16 px side margin, 16 px radius, rows ≥ 48 px, 0.5 px inset separators, chevron «‹» on the left (RTL), Settings-style coloured icon squares in المزيد, UISwitch for on/off settings.
- **Match row:** home (right) · score · away (left); the score is one `dir="rtl"` run «1 - 4» so each number sits beside its own team; under it the live minute (red, pulsing dot), «انتهت», or the kick-off time; the winner bold, the loser secondary.
- **Feature card:** big crests and score, the two clubs' colours as a faint wash. Used once per screen (فريقك / مباشر الحين / أبرز مباراة / المباراة الياية).
- **Match header:** club-colour wash at 30 %, 64 px crests, 44 px score, status, scorers under each team, date · venue.
- **Pitch:** one vertical pitch for both line-ups (away top, home bottom), shirt-number discs in club colours, rating badges, event badges.
- **Stats:** value · label · value with a dual bar in club colours; the leader's value in a filled pill.

## 3. Colour
- iOS system neutrals: light `#F2F2F7` ground / `#FFFFFF` cells; dark `#000000` / `#1C1C1E`. Labels at 100 / 64 / 36 % opacity.
- **One accent:** Tifo pitch green `#0B8246` (light) / `#35D07F` (dark): tab selection, links, toggles, the selected day.
- **Semantic only:** live = red `#E5261D` / `#FF453A`; W/D/L = green / grey / red; yellow and red cards are cards only.
- **Club colours only where a club is on screen** (header wash, pitch discs, bars). «ألوان فريقي» (المزيد › الإعدادات) optionally tints the app with the first followed club's colour, contrast-corrected per scheme.

## 4. Type
- System stack `-apple-system, system-ui, "SF Arabic", "Segoe UI", "Noto Sans Arabic", sans-serif`: SF Arabic on iPhone, the platform face elsewhere, no web fonts.
- Scale 34 · 28 · 22 · 17 · 15 · 13 · 12; weights 400/500/600/700/800. Scores 800, tabular.
- Western digits only; tabular numerals for scores, minutes and tables; minutes and signed numbers are LTR-isolated; Arabic is never letter-spaced.

## 5. Motion and touch
- Spring for the segmented thumb (0.36 s) and sheets (0.42 s); press states scale to 0.92–0.96; the only loop is the live dot. `prefers-reduced-motion` turns all of it off.
- Every tap target ≥ 44 × 44 px (small controls grow their hit area with `::after`), and whole rows are tappable.

## 6. Gates (`qa.cjs`)
No horizontal page scroll at 360 / 390 / 430 / 768 / 1280 · every target ≥ 44 px by hit-testing · every score «a - b» drawn with the home number on the home side (character positions) · RTL basics · no script errors. Budgets: CSS ≈ 9 KB gz, one deferred JS ≈ 44 KB gz, no fonts, prerendered HTML.

## 7. Copy
Light Emirati, short labels: الحين، الياية، النتايج، شوف، نبّهني، سكّر، تابع، متابَع. Never وش، زي، تبي، الجاي، جديد، مين.

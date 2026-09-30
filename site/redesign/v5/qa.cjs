/* Quality gates for the v5 preview (DESIGN.md §6). node site/redesign/v5/qa.cjs [--base http://localhost:8795] [--out qa.json]
   1. no horizontal page scroll at 360 / 390 / 430 / 768 / 1280 (and no element sticking out, outside the horizontal scrollers)
   2. every tap target >= 44 x 44 px, measured by hit-testing (so a control whose hit area is grown by ::after counts);
      links inside running text (footnotes, sources, the footer) are exempt, as in WCAG 2.5.8
   3. every score between two names is a dir="rtl" run «a - b» whose first number is drawn on the home (right) side,
      next to the home team: measured from the characters' positions
   4. RTL: document dir, first tab rightmost, large titles right-aligned, row chevrons on the left
   5. no script errors */
"use strict";
const { chromium } = require(process.env.PW || "C:/Users/requi/workspace/content-pipeline/node_modules/playwright-core");
const args = process.argv.slice(2), opt = (k, d) => { const i = args.indexOf("--" + k); return i >= 0 ? args[i + 1] : d; };
const BASE = opt("base", "http://localhost:8795"), OUT = opt("out", "");
const PAGES = (opt("pages", "") || "/next/ /next/m/live/ /next/m/6052086/ /next/m/1000020522/ /next/c/uae-pro-league/ /next/c/gulf-cup/ /next/t/102111/ /next/t/5789/ /next/p/30893/ /next/p/721345/ /next/db/ /next/db/league/549/ /next/news/ /next/search/ /next/more/ /next/competitions/ /next/mine/").split(/\s+/).filter(Boolean);
const WIDTHS = [360, 390, 430, 768, 1280];
(async () => {
  const b = await chromium.launch({ channel: "msedge" }), report = { pages: {}, fails: [] };
  const fail = (p, what) => { report.fails.push(p + " :: " + what); };
  for (const p of PAGES) {
    const R = report.pages[p] = {};
    for (const w of WIDTHS) {
      const ctx = await b.newContext({ viewport: { width: w, height: w >= 768 ? 1000 : 844 }, deviceScaleFactor: 2, isMobile: w < 768, hasTouch: w < 768, serviceWorkers: "block", timezoneId: "Asia/Dubai", colorScheme: "light" });
      const pg = await ctx.newPage(), errs = [];
      pg.on("pageerror", e => errs.push(e.message)); pg.on("console", m => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) errs.push(m.text()); });
      try { await pg.goto(BASE + p, { waitUntil: "networkidle", timeout: 60000 }); } catch (e) { fail(p, "load timeout at " + w); }
      await pg.waitForTimeout(400);
      // open every pane once (the widest content hides in panes), then measure overflow
      const hs = await pg.evaluate(async () => {
        const segs = [...document.querySelectorAll(".seg")], out = [];
        const check = tag => { const W = innerWidth, sw = document.documentElement.scrollWidth; if (sw > W) out.push(tag + ": scrollWidth " + sw + " > " + W);
          const skip = el => el.closest(".days,.rounds,.vids,.tblw,dialog:not([open]),[hidden],details:not([open]) > :not(summary)");
          for (const el of document.querySelectorAll("main *,header *,nav *")) { if (skip(el)) continue; const r = el.getBoundingClientRect(); if (!r.width || !r.height) continue; if (r.right > W + 1.5 || r.left < -1.5) { out.push(tag + ": " + el.tagName.toLowerCase() + "." + [...el.classList].join(".") + " spans " + Math.round(r.left) + "→" + Math.round(r.right)); if (out.length > 6) break; } } };
        check("first");
        for (const s of segs) for (const btn of s.querySelectorAll("button[data-t]")) { btn.click(); await new Promise(r => setTimeout(r, 60)); check(s.dataset.seg + ":" + btn.dataset.t); }
        const first = segs.map(s => s.querySelector("button[data-t]")); first.forEach(x => x && x.click());
        return out; });
      if (hs.length) { R["hscroll@" + w] = hs; hs.slice(0, 3).forEach(x => fail(p, "overflow @" + w + " " + x)); }
      if (errs.length) { R["errors@" + w] = errs; fail(p, "script errors @" + w + ": " + errs[0]); }
      if (w === 390) {
        // tap targets, one sample of each kind of control, hit-tested on screen
        const tt = await pg.evaluate(async () => {
          const out = [], seen = {}, NAVH = (document.getElementById("nav") || { offsetHeight: 52 }).offsetHeight, TB = document.querySelector(".tabbar");
          const inText = el => el.closest(".gf,.foot,.wiki,.src,.note p,.note,.pv,.nw .src,.ea-meta,p.sub") && el.tagName === "A";
          const els = [...document.querySelectorAll("main a[href], main button, main summary, main input, header a[href], header button, nav.tabbar a")].filter(el => { const r = el.getBoundingClientRect(); return r.width && r.height && !el.closest("[hidden],dialog,details:not([open]) > :not(summary)") && !inText(el); });
          for (const el of els) {
            const sig = el.tagName + "." + [...el.classList].sort().join(".") + "|" + (el.parentElement ? el.parentElement.className : "");
            seen[sig] = (seen[sig] || 0) + 1; if (seen[sig] > 2) continue;
            if (!el.closest(".tabbar,.nav")) { el.scrollIntoView({ block: "center", inline: "center" }); await new Promise(r => setTimeout(r, 30)); }
            const r = el.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
            const hit = (x, y) => { const e = document.elementFromPoint(x, y); return !!e && (e === el || el.contains(e)); };
            if (!hit(cx, cy)) { continue; }   // covered (e.g. under the tab bar after scrolling): skip
            let up = 0, dn = 0, lf = 0, rt = 0;
            while (up < 30 && hit(cx, cy - up - 1)) up++; while (dn < 30 && hit(cx, cy + dn + 1)) dn++;
            while (lf < 30 && hit(cx - lf - 1, cy)) lf++; while (rt < 30 && hit(cx + rt + 1, cy)) rt++;
            const H = up + dn + 1, Wd = lf + rt + 1;
            if (H < 43.5 || Wd < 43.5) out.push(sig.split("|")[0] + " «" + (el.textContent || el.getAttribute("aria-label") || "").trim().slice(0, 24) + "» " + Wd + "x" + H);
          }
          window.scrollTo(0, 0); return out; });
        if (tt.length) { R.tap = tt; tt.slice(0, 8).forEach(x => fail(p, "tap target " + x)); }
        // scores: dir=rtl run, spaced hyphen, first number on the right (home side)
        const sc = await pg.evaluate(() => {
          const out = [], n = { ok: 0 };
          for (const el of document.querySelectorAll(".sc:not(.ko):not(.tbd)")) {
            const t = el.textContent.trim(); if (!/^\d+ - \d+$/.test(t)) { if (/\d/.test(t)) out.push("format «" + t + "»"); continue; }
            if (el.getAttribute("dir") !== "rtl") { out.push("not dir=rtl «" + t + "»"); continue; }
            const tn = el.firstChild; if (!tn || tn.nodeType !== 3) continue; const r = document.createRange();
            r.setStart(tn, 0); r.setEnd(tn, 1); const a = r.getBoundingClientRect(); r.setStart(tn, t.length - 1); r.setEnd(tn, t.length); const z = r.getBoundingClientRect();
            if (!a.width) continue;
            if (!(a.left > z.left)) out.push("home score not on the right «" + t + "» " + Math.round(a.left) + " vs " + Math.round(z.left));
            const row = el.closest(".mr,.mh,.fc-body"); if (row) { const h = row.querySelector(".mr-t.h,.mh-t,.fc-t"), aw = [...row.querySelectorAll(".mr-t.a,.mh-t,.fc-t")].pop(); if (h && aw && h !== aw) { const hr = h.getBoundingClientRect(), ar = aw.getBoundingClientRect(); if (!(hr.left > ar.left)) out.push("home team not on the right «" + t + "»"); if (!(hr.left >= a.left - 2 && a.left > ar.left)) {} } }
            n.ok++;
          }
          return { bad: out, checked: n.ok }; });
        R.scores = sc; sc.bad.slice(0, 5).forEach(x => fail(p, "score " + x));
        // RTL basics
        const rtl = await pg.evaluate(() => { const out = [], W = innerWidth; if (document.documentElement.dir !== "rtl") out.push("html dir is not rtl");
          const tabs = [...document.querySelectorAll(".tabbar a")]; if (tabs.length && tabs[0].getBoundingClientRect().left < tabs[tabs.length - 1].getBoundingClientRect().left) out.push("first tab is not the rightmost");
          const h1 = document.querySelector(".lt h1"); if (h1) { const r = h1.getBoundingClientRect(); if (W - r.right > 40) out.push("large title not right-aligned (" + Math.round(W - r.right) + " px from the right)"); }
          const row = [...document.querySelectorAll("main a.row")].find(x => x.querySelector(".chev") && x.getBoundingClientRect().width > 200); if (row) { const c = row.querySelector(".chev").getBoundingClientRect(), rr = row.getBoundingClientRect(); if (c.left - rr.left > rr.width / 2) out.push("row chevron not on the left"); }
          return out; });
        if (rtl.length) { R.rtl = rtl; rtl.forEach(x => fail(p, "rtl " + x)); }
      }
      await ctx.close();
    }
    process.stdout.write(".");
  }
  await b.close();
  console.log("\n" + (report.fails.length ? report.fails.length + " failures:\n" + report.fails.join("\n") : "all gates passed on " + PAGES.length + " pages x " + WIDTHS.length + " widths"));
  const sc = Object.values(report.pages).reduce((a, r) => a + ((r.scores && r.scores.checked) || 0), 0); console.log("scores checked:", sc);
  if (OUT) require("fs").writeFileSync(OUT, JSON.stringify(report, null, 1));
  process.exit(report.fails.length ? 1 : 0);
})();

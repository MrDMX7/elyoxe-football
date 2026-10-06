/* تيفو v5 shell helpers for build.cjs (site/redesign/v5/DESIGN.md, ROLLOUT.md).
   - legacy5(o): any page() body that was written for v2/v3 (crumbs + h1 + season line + <section class="blk"> blocks + tool
     buttons) becomes the v5 skeleton: nav bar (back to the crumb's page), a large title, grouped inset cards, and the tool
     buttons in the page's «شارك» sheet. The inner HTML of each block is kept as is, inside a .lc container that
     src/v5/content.css styles; every id, class and data attribute the old scripts look for survives.
   - secRows(secs): blocks -> one grouped list whose rows open sheets (<dialog>) holding the block, stamped from a <template>
     on first open (a block with a widget the scripts wire at start-up stays live DOM). This is v3's shelf in v5 form.
   Nothing here fetches data; build.cjs passes renderers and names in. */
"use strict";
module.exports = function (X) {
  const { esc, U } = X, LIVE_IDS = X.LIVE_IDS || [];
  const isLiveSec = h => LIVE_IDS.some(id => h.includes('id="' + id + '"'));
  const strip = h => String(h || "").replace(/<(script|style|template)[\s\S]*?<\/\1>/g, "").replace(/<[^>]+>/g, " ").replace(/&nbsp;/g, " ").replace(/&[a-z#0-9]+;/g, " ").replace(/\s+/g, " ").trim();

  // ---- top-level <section class="blk"> blocks of a body (same walk as build.cjs blocks(), kept here so legacy5 is self-contained)
  function blocks(html) {
    const out = [], rest = []; let i = 0;
    while (i < html.length) {
      const s = html.indexOf('<section class="blk"', i); if (s < 0) { rest.push({ html: html.slice(i) }); break; }
      rest.push({ html: html.slice(i, s) }); let d = 0, j = html.length; const re = /<(\/?)section\b[^>]*>/g; re.lastIndex = s; let m;
      while ((m = re.exec(html))) { d += m[1] ? -1 : 1; if (!d) { j = re.lastIndex; break; } }
      const full = html.slice(s, j), open = full.match(/^<section\b[^>]*>/)[0], h2m = full.match(/<h2\b[^>]*>([\s\S]*?)<\/h2>/), h2 = h2m ? h2m[1] : "";
      const title = h2.replace(/<small>[\s\S]*<\/small>/, "").replace(/<[^>]+>/g, "").trim(), sub = (h2.match(/<small>([\s\S]*)<\/small>/) || [])[1] || "";
      const id = (open.match(/\sid="([^"]+)"/) || [])[1] || "", cls = (open.match(/\sclass="([^"]+)"/) || [])[1] || "blk";
      const attrs = open.replace(/^<section\b|>$/g, "").replace(/\s(id|class)="[^"]*"/g, "");
      const inner = h2m ? full.slice(open.length).replace(h2m[0], "").replace(/<\/section>$/, "") : full.slice(open.length).replace(/<\/section>$/, "");
      out.push({ title, titleHtml: h2.replace(/<small>[\s\S]*<\/small>/, "").trim(), sub, id, cls, attrs, full, inner });
      rest.push({ sec: out.length - 1 }); i = j;
    }
    return { secs: out, parts: rest };
  }

  // ---- an icon for a row, picked from the block's title (one line icon per topic, Settings-style colour squares)
  const ICONS = [[/مدرب|حكم|الحكام|قانون/, "whistle", "#636366"], [/هداف|أهداف|هدف|تسديد|الحاسم|يسجل/, "ball", "#34C759"], [/انتقال|صفقات|الصفقات|إعارة|المعارين/, "swap", "#30B0C7"],
    [/تاريخ|التاريخي|عبر|الأبطال|ألقاب|خزانة|كتاب|الأساطير|ما تنتسى|قياسي/, "hist", "#5856D6"], [/توقع|فرص|محاكي|سيناريو|بيفوز|حاسبة|شو لو|كم يحتاج/, "target", "#FF2D55"],
    [/جولة|الياية|مباريات|موعد|ساعة الموسم|التقويم|الشهر|الأسبوع/, "calendar", "#FF3B30"], [/ملعب|ملاعب|حصون|حصن|سافر|رايح/, "pin", "#34C759"], [/جماهير|الحضور|مشجع/, "people", "#5856D6"],
    [/تصنيف|ترتيب|القوة|رحلة|الضغط|ترمومتر|إيلو|فيفا/, "chart", "#0A84FF"], [/بطاقات|بطاقة|كروت|إيقاف|الإيقافات/, "medal", "#FF9500"], [/أعمار|مواهب|تحت 23|لاعبين|اللاعبين|تشكيلة/, "shirt", "#AF52DE"],
    [/تعليق|ثريد|الصحفي|الخلاصة|تقرير|سؤال|أسئلة/, "chat", "#FF9F0A"], [/إعادة|خط المباراة|دقيقة/, "clock", "#FF9500"], [/قناة|تنقل|المجلس/, "tv", "#AF52DE"], [/حساب|الرسمية/, "link", "#0A84FF"]];
  function iconFor(t) { for (const x of ICONS) if (x[0].test(t)) return [x[1], x[2]]; return ["grid", "#8E8E93"]; }

  // ---- blocks -> one grouped list of rows that open sheets; returns {rows, sheets}
  let SEQ = 0;
  function secRows(secs, o) {
    o = o || {}; const rows = [], sheets = [];
    secs.filter(sc => strip(sc.inner).length > 2).forEach(sc => {
      const key = "sx-" + (sc.id || (o.prefix || "s") + (++SEQ)), ic = iconFor(sc.title), live = isLiveSec(sc.full);
      const sub = sc.sub ? strip(sc.sub) : "";
      rows.push(U.row({ btn: 1, icon: ic[0], c: ic[1], t: esc(sc.title), sub: esc(sub), attrs: ' data-sheet="' + key + '"' + (sc.id ? ' data-anchor="' + esc(sc.id) + '"' : "") }));
      const body = '<div class="lc sxb"' + (sc.id ? "" : "") + ">" + sc.inner + "</div>";
      // the sheet keeps the block's own section (id, class) so scripts that look for #id or section.blk still find it once stamped
      const inner = "<section " + 'class="' + esc(sc.cls) + ' sxs"' + (sc.id ? ' id="' + esc(sc.id) + '"' : "") + sc.attrs + ">" + body + "</section>";
      sheets.push(U.sheet(key, esc(sc.title) + (sub ? '<small class="sh-sub">' + esc(sub) + "</small>" : ""), live ? inner : '<template class="lazys">' + inner + "</template>"));
    });
    return { rows: rows.join(""), sheets: sheets.join(""), n: rows.length };
  }

  // ---- one block as a grouped inset card (title above, the block's HTML inside a .card)
  function grp(sc) {
    const sub = sc.sub ? '<span class="ghs">' + sc.sub + "</span>" : "";
    return '<section class="grp ' + esc(sc.cls) + '"' + (sc.id ? ' id="' + esc(sc.id) + '"' : "") + sc.attrs + '><div class="gh"><h2>' + (sc.titleHtml || esc(sc.title)) + "</h2>" + sub + '</div><div class="card lc">' + sc.inner + "</div></section>";
  }

  // ---- which tab of the bar a path belongs to
  function tabOf(o) {
    const p = o.path || "", n = o.nav || "";
    if (n === "home" || /^\/(today|tomorrow|all|live|m)\//.test(p) || p === "/") return "today";
    if (n === "comps" || n === "nat" || /^\d+$/.test(n) || /^\/(competitions|c|country|national|t|p|coach|r|s|h2h|db|uae)\//.test(p)) return "comps";
    if (/^\/news\//.test(p)) return "news";
    if (/^\/mine\//.test(p)) return "mine";
    return "more";
  }

  // ---- legacy body -> v5 page parts {nav, body, tab, sheets, acts}
  const SHELF_PATH = /^\/(worldcup-arabs)\/$|^\/national\/[a-z]{2}\/$/;
  function legacy5(o) {
    let body = o.body || "", tools = o.tools || "";
    // rows of buttons only (print, image, compare…) move to the «شارك» sheet; link rows stay where they are
    body = body.replace(/<p class="tools(?: noprint)?">((?:\s*<button\b[^>]*>[^<]*<\/button>)+)\s*<\/p>/g, (m, bs) => { tools += bs; return ""; });
    // data scripts in front of the title (/week/'s #wkdata) stay in the body, after the title
    const lead = (body.match(/^\s*(?:<script\b[^>]*>[\s\S]*?<\/script>\s*)+/) || [""])[0]; body = body.slice(lead.length);
    const m = body.match(/^\s*(<p class="crumbs">([\s\S]*?)<\/p>)?\s*(<h1\b([^>]*)>([\s\S]*?)<\/h1>)\s*(<p class="(?:season|muted)[^"]*">([\s\S]*?)<\/p>)?/);
    let back = null, crumbs = "", head = "";
    if (m) {
      body = body.slice(m[0].length);
      const links = [...(m[2] || "").matchAll(/<a\b[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/g)];
      if (links.length) { const l = links[links.length - 1]; back = { href: l[1], label: strip(l[2]) }; }
      if (links.length > 1) crumbs = '<p class="lt-k">' + m[2] + "</p>";
      const h1a = (m[4] || "").replace(/\sclass="([^"]*)"/, (x, c) => ' class="' + c + '"'), lg = o.lg ? '<img class="lt-lg" src="/lg/' + o.lg[0] + '.png" alt="" width="44" height="44">' : "";
      const extra = o.heroExtra ? '<div class="lt-x">' + o.heroExtra + "</div>" : "";
      head = '<div class="lt' + (lg || extra ? " lt-row" : "") + '"><div class="lt-t">' + crumbs + "<h1" + h1a + ">" + m[5] + "</h1>" + (m[7] ? '<p class="lt-s">' + m[7] + "</p>" : "") + "</div>" + lg + extra + "</div>";
      o._h1 = strip(m[5]);
    }
    // sheets a builder put in the body (build.cjs shelf()) join the page's sheets before the blocks are read
    const moved = []; body = takeOut(body, "dialog", 'class="sheet"', moved);
    const b = blocks(body), shelfy = SHELF_PATH.test(o.path || "") && b.secs.length >= 4;
    let main = "", sheets = "";
    if (shelfy) {
      const sr = secRows(b.secs, { prefix: "h" });
      main = b.parts.filter(x => x.html != null).map(x => x.html.trim() ? split5(x.html) : "").join("") + U.grp("كل الأقسام", sr.rows, { cls: "mt2" });
      sheets = sr.sheets;
    } else {
      main = b.parts.map(x => x.sec != null ? grp(b.secs[x.sec]) : x.html.trim() ? split5(x.html) : "").join("");
    }
    return { nav: { back: back ? back.href : "/more/", backLabel: back ? back.label : "المزيد", title: esc(o._h1 || ""), trail: U.navLink("search", "بحث", "/search/") + U.navBtn("share", "شارك", ' data-sheet="sh-share"') },
      body: head + lead.trim() + main, tab: tabOf(o), sheets: sheets + moved.join(""), tools };
  }
  // the end of the element that opens at `s` (same tag, nesting counted)
  function endOf(html, s, tag) { const tr = new RegExp("<(/?)" + tag + "\\b[^>]*>", "g"); tr.lastIndex = s; let d = 0, t; while ((t = tr.exec(html))) { d += t[1] ? -1 : 1; if (!d) return tr.lastIndex; } return html.length; }
  // every <tag attr…>…</tag> out of html into `into`
  function takeOut(html, tag, attr, into) { let out = "", i = 0, s; const open = "<" + tag + " " + attr; while ((s = html.indexOf(open, i)) >= 0) { const e = endOf(html, s, tag); out += html.slice(i, s); into.push(html.slice(s, e)); i = e; } return out + html.slice(i); }
  // the old HTML between blocks goes in a .lc container (content.css), except a v5 grouped list a builder put there (build.cjs
  // shelf()) or a search page's <div class="sx"> (lib/seo_days.cjs, seo_leagues.cjs, world_stage.cjs: v5 markup throughout):
  // they stay v5. Only top-level ones (no open <div> around them) are taken out, so the old HTML stays balanced
  function split5(html) {
    const out = [], depth = s => (s.match(/<div\b/g) || []).length - (s.match(/<\/div>/g) || []).length, OPEN = /<section class="grp|<div class="sx[" ]/g;
    let i = 0, buf = "", s, from = 0, mt;
    while ((OPEN.lastIndex = from, mt = OPEN.exec(html))) {
      s = mt.index; const e = endOf(html, s, mt[0][1] === "s" ? "section" : "div"); from = e;
      if (depth(buf + html.slice(i, s))) continue;   // inside an old wrapper: leave it there
      buf += html.slice(i, s); if (buf.trim()) out.push('<div class="lc lcx">' + buf + "</div>"); buf = "";
      out.push(html.slice(s, e)); i = e;
    }
    buf += html.slice(i); if (buf.trim()) out.push('<div class="lc lcx">' + buf + "</div>");
    return out.join("");
  }

  return { blocks, secRows, grp, iconFor, legacy5, tabOf, strip, isLiveSec };
};

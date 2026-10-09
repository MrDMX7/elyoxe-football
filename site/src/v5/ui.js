/* تيفو v5 renderers: data (docs/SCHEMA.md) -> HTML strings. One copy for both sides: build.cjs prerenders pages with it and
   app.js re-renders the same blocks in the browser (live refresh, and pages for ids outside the prerendered set).
   Everything reads U.cfg (links, Arabic names, club colours, time zone); nothing here touches the DOM.
   Scores between two names are one dir="rtl" run with a spaced hyphen, so each number sits beside its own team. */
(function (root) {
  "use strict";
  var U = {};
  var cfg = U.cfg = { base: "/next", pre: { m: {}, t: {}, p: {}, c: {} }, pn: {}, tn: {}, tc: {}, cn: {}, cc: {}, ph: {}, tz: null, now: null, today: null, ea: {} };

  // ------------------------------------------------------------------ basics
  function esc(s) { return s == null ? "" : String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  U.esc = esc;
  var pad = function (n) { return (n < 10 ? "0" : "") + n; };
  var DAY = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"];
  var MON = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];
  U.DAY = DAY; U.MON = MON;
  var ORD = { A: "الأولى", B: "الثانية", C: "الثالثة", D: "الرابعة", E: "الخامسة", F: "السادسة", G: "السابعة", H: "الثامنة", I: "التاسعة", J: "العاشرة", K: "الحادية عشرة", L: "الثانية عشرة", "1": "الأولى", "2": "الثانية", "3": "الثالثة", "4": "الرابعة", "5": "الخامسة", "6": "السادسة", "7": "السابعة", "8": "الثامنة" };
  var KO = [[/group stage\s*-\s*round\s*(\d+)/i, function (m) { return "الجولة " + m[1]; }], [/^(1st|first)\s+preliminary/i, "الدور التمهيدي الأول"], [/^(2nd|second)\s+preliminary/i, "الدور التمهيدي الثاني"], [/^bronze$|^3rd$/i, "مباراة المركز الثالث"], [/^prelim(-\d)?$/i, "الدور التمهيدي"], [/^west$/i, "منطقة الغرب"], [/^east$/i, "منطقة الشرق"],
    [/^1\/64|round of 128/i, "دور الـ128"], [/^1\/32|round of 64/i, "دور الـ64"], [/^1\/16|round of 32/i, "دور الـ32"], [/^1\/8|round of 16|last 16/i, "دور الـ16"], [/^1\/4|quarter/i, "ربع النهائي"], [/^1\/2|semi/i, "نص النهائي"], [/(3rd|third).*(place|play)/i, "مباراة المركز الثالث"], [/^final$|^the final$|^final\b/i, "النهائي"], [/play-?off/i, "الملحق"], [/^preliminary/i, "الدور التمهيدي"], [/^qualif/i, "التصفيات"], [/^group stage$/i, "دور المجموعات"], [/league stage|league phase/i, "مرحلة الدوري"]];
  U.stageAr = function (s) { if (!s) return ""; s = String(s); var g = /Gr(?:ou)?p\.?\s*([A-Za-z0-9]{1,2})\b/.exec(s) || /group\s*([A-Za-z0-9]{1,2})\b/i.exec(s); if (g) return "المجموعة " + (ORD[g[1].toUpperCase()] || g[1]);
    for (var i = 0; i < KO.length; i++) { var mm = KO[i][0].exec(s.trim()); if (mm) return typeof KO[i][1] === "function" ? KO[i][1](mm) : KO[i][1]; } return s; };
  U.groupName = function (x, i) { x = String(x == null ? "" : x).replace(/^Gr(?:ou)?p\.?\s*/i, "").trim(); if (/^west$/i.test(x)) return "منطقة الغرب"; if (/^east$/i.test(x)) return "منطقة الشرق"; return "المجموعة " + (ORD[x.toUpperCase()] || (i != null ? ORD[String(i + 1)] || i + 1 : x)); };
  var arOnly = function (x) { return /[؀-ۿ]/.test(x || "") ? x : ""; };
  U.roundLabel = function (m) { if (!m) return ""; if (m.round && /^\d+$/.test(String(m.round))) return "الجولة " + m.round; if (m.stage) return arOnly(U.stageAr(m.stage)) || arOnly(m.round_ar); if (m.round_ar) return arOnly(m.round_ar); return m.round ? arOnly(U.stageAr(m.round)) : ""; };
  var nf = function (n) { return n == null ? "" : Number(n).toLocaleString("en-US"); };
  U.nf = nf;

  // ------------------------------------------------------------------ time: UAE at build time, the visitor's zone in the browser
  var FMT = {};
  function parts(iso) {
    if (!iso) return null;
    var t = Date.parse(iso); if (isNaN(t)) return null;
    if (cfg.tz) { try { var f = FMT[cfg.tz] || (FMT[cfg.tz] = new Intl.DateTimeFormat("en-US", { timeZone: cfg.tz, hourCycle: "h23", year: "numeric", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", weekday: "short" })); var o = {}; f.formatToParts(new Date(t)).forEach(function (p) { o[p.type] = p.value; });
      return { y: +o.year, mo: +o.month, d: +o.day, h: o.hour === "24" ? "00" : o.hour, mi: o.minute, wd: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(o.weekday) }; } catch (e) {} }
    var d = new Date(t + 4 * 3600e3);
    return { y: d.getUTCFullYear(), mo: d.getUTCMonth() + 1, d: d.getUTCDate(), h: pad(d.getUTCHours()), mi: pad(d.getUTCMinutes()), wd: d.getUTCDay() };
  }
  U.parts = parts;
  U.hhmm = function (iso) { var p = parts(iso); return p ? p.h + ":" + p.mi : ""; };
  U.ymd = function (iso) { var p = parts(iso); return p ? p.y + "-" + pad(p.mo) + "-" + pad(p.d) : ""; };
  U.dname = function (iso, short) { var p = parts(iso); return p ? (short ? "" : DAY[p.wd] + " ") + p.d + " " + MON[p.mo - 1] : ""; };
  function relDay(iso) { if (!cfg.today || !iso) return ""; var a = U.ymd(iso).split("-").map(Number), b = cfg.today.split("-").map(Number), diff = Math.round((Date.UTC(a[0], a[1] - 1, a[2]) - Date.UTC(b[0], b[1] - 1, b[2])) / 864e5); return diff === 0 ? "اليوم" : diff === 1 ? "بكرة" : diff === -1 ? "أمس" : ""; }
  U.relDay = relDay;
  // <time> elements carry the instant; app.js rewrites them in the visitor's zone (f: t time, d date, dt both, r relative)
  function tm(iso, f) { if (!iso) return ""; var txt = f === "d" ? U.dname(iso) : f === "ds" ? U.dname(iso, 1) : f === "dt" ? U.dname(iso) + "، " + U.hhmm(iso) : f === "r" ? (relDay(iso) || U.dname(iso)) : U.hhmm(iso); return '<time data-u="' + esc(iso) + '" data-f="' + (f || "t") + '">' + esc(txt) + "</time>"; }
  U.tm = tm;
  U.timeText = function (iso, f) { return f === "d" ? U.dname(iso) : f === "ds" ? U.dname(iso, 1) : f === "dt" ? U.dname(iso) + "، " + U.hhmm(iso) : f === "r" ? (relDay(iso) || U.dname(iso)) : U.hhmm(iso); };
  U.ago = function (iso) { var m = Math.max(1, Math.round(((cfg.now || Date.now()) - Date.parse(iso)) / 6e4)); if (!isFinite(m)) return ""; return m < 60 ? "قبل " + m + (m > 10 ? " دقيقة" : " دقايق") : m < 1440 ? "قبل " + Math.round(m / 60) + " ساعة" : "قبل " + Math.round(m / 1440) + " يوم"; };

  // ------------------------------------------------------------------ links (prerendered pages get a path, the rest a query the browser renders)
  var L = U.link = function (kind, id) {
    var b = cfg.base, P = cfg.pre;
    if (id == null || id === "") return b + "/";
    // production (cfg.pre null): every entity has its own page; the build's dead-link pass unlinks the few that don't
    if (!P) { if (kind === "c") { var cc = cfg.cn[id]; return cc ? b + "/c/" + cc[0] + "/" : b + "/competitions/"; } return kind === "l" ? (cfg.lgs && !cfg.lgs[id] ? b + "/db/league/?id=" + id : b + "/db/league/" + id + "/") : /^[mtp]$/.test(kind) ? b + "/" + kind + "/" + id + "/" : b + "/"; }
    if (kind === "m") return P.m[id] ? b + "/m/" + id + "/" : b + "/m/?id=" + id;
    if (kind === "t") return P.t[id] ? b + "/t/" + id + "/" : b + "/t/?id=" + id;
    if (kind === "p") return P.p[id] ? b + "/p/" + id + "/" : b + "/p/?id=" + id;
    if (kind === "c") { var c = cfg.cn[id]; return c && P.c[c[0]] ? b + "/c/" + c[0] + "/" : b + "/c/?id=" + id; }
    if (kind === "l") return P.l && P.l[id] ? b + "/db/league/" + id + "/" : b + "/db/league/?id=" + id;
    return b + "/";
  };

  // ------------------------------------------------------------------ icons (24 px line icons, SF Symbols in spirit)
  var IP = {
    today: '<rect x="3.5" y="5" width="17" height="15.5" rx="3.2"/><path d="M3.5 10h17M8 3v4M16 3v4"/><circle cx="12" cy="15" r="1.6" fill="currentColor" stroke="none"/>',
    comps: '<path d="M7.5 4h9v5.5a4.5 4.5 0 0 1-9 0z"/><path d="M7.5 6.2H5a2.4 2.4 0 0 0 2.6 4.3M16.5 6.2H19a2.4 2.4 0 0 1-2.6 4.3M12 14v3.5M8.5 20.5h7M9.8 17.5h4.4"/>',
    news: '<rect x="3.5" y="4.5" width="13.5" height="15.5" rx="2.6"/><path d="M17 8.5h2.2a1.3 1.3 0 0 1 1.3 1.3v7.7a2.5 2.5 0 0 1-2.5 2.5H6M7 9h6.5M7 12.5h6.5M7 16h4"/>',
    star: '<path d="M12 3.8l2.5 5.1 5.6.8-4 4 .9 5.6L12 16.7l-5 2.6.9-5.6-4-4 5.6-.8z"/>',
    starf: '<path fill="currentColor" d="M12 3.8l2.5 5.1 5.6.8-4 4 .9 5.6L12 16.7l-5 2.6.9-5.6-4-4 5.6-.8z"/>',
    more: '<circle cx="12" cy="12" r="8.6"/><circle cx="8" cy="12" r="1.25" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.25" fill="currentColor" stroke="none"/><circle cx="16" cy="12" r="1.25" fill="currentColor" stroke="none"/>',
    search: '<circle cx="10.6" cy="10.6" r="6.6"/><path d="M15.6 15.6L20.5 20.5"/>',
    share: '<path d="M12 3.6v11M8 7.4l4-3.8 4 3.8"/><path d="M8.5 10.5h-2a2 2 0 0 0-2 2V18.5a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V12.5a2 2 0 0 0-2-2h-2"/>',
    filter: '<path d="M4 7h16M7 12h10M10.2 17h3.6"/>',
    bell: '<path d="M6.2 16.5V11a5.8 5.8 0 0 1 11.6 0v5.5l1.6 1.6H4.6z"/><path d="M10 20.4a2.2 2.2 0 0 0 4 0"/>',
    close: '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
    back: '<path d="M9 5l7 7-7 7"/>',
    ball: '<circle cx="12" cy="12" r="8.6"/><path d="M12 8.2l3 2.2-1.1 3.6h-3.8l-1.1-3.6z" fill="currentColor"/><path d="M12 3.5v4.7M15 10.4l4.3-1.5M13.9 14l2.7 3.8M10.1 14l-2.7 3.8M9 10.4L4.7 8.9"/>',
    miss: '<circle cx="12" cy="12" r="8.6"/><path d="M6 6l12 12"/>',
    sub: '<path d="M8 19.5V5.5M4.7 8.8L8 5.5l3.3 3.3" stroke="#28B463"/><path d="M16 4.5v14M12.7 15.2l3.3 3.3 3.3-3.3" stroke="#E5483E"/>',
    vr: '<rect x="3" y="5.5" width="18" height="12" rx="2.6"/><path d="M8.5 20.5h7M7 9.5l1.5 4 1.5-4M12.2 13.5l1.3-4 1.3 4M12.6 12.3h1.8"/>',
    pin: '<path d="M12 21s-6.4-5.6-6.4-11a6.4 6.4 0 0 1 12.8 0c0 5.4-6.4 11-6.4 11z"/><circle cx="12" cy="10" r="2.3"/>',
    clock: '<circle cx="12" cy="12" r="8.6"/><path d="M12 7.5V12l3 2"/>',
    people: '<circle cx="9" cy="8.5" r="3"/><path d="M3.5 19a5.5 5.5 0 0 1 11 0M15.5 11.5a2.6 2.6 0 1 0 0-5.2M16.5 14a4.8 4.8 0 0 1 4 5"/>',
    whistle: '<circle cx="9" cy="14" r="5"/><path d="M13.3 11.2L20.5 8v3.2L14.2 13.4M9 14h.01"/>',
    sun: '<circle cx="12" cy="12" r="3.8"/><path d="M12 2.8v2.2M12 19v2.2M2.8 12H5M19 12h2.2M5.5 5.5l1.5 1.5M17 17l1.5 1.5M5.5 18.5L7 17M17 7l1.5-1.5"/>',
    moon: '<path d="M18.8 14.8A7.4 7.4 0 0 1 9.2 5.2a7.4 7.4 0 1 0 9.6 9.6z"/>',
    tv: '<rect x="3" y="5" width="18" height="12" rx="2.6"/><path d="M8.5 20.5h7M12 17v3.5"/>',
    play: '<circle cx="12" cy="12" r="8.6"/><path d="M10.2 8.6v6.8l5.4-3.4z" fill="currentColor"/>',
    link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 1 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 1 0 5.7 5.7l1-1"/>',
    copy: '<rect x="8.5" y="8.5" width="11.5" height="11.5" rx="2.6"/><path d="M15.5 8.5V6.5a2.5 2.5 0 0 0-2.5-2.5H6.5A2.5 2.5 0 0 0 4 6.5V13a2.5 2.5 0 0 0 2.5 2.5h2"/>',
    image: '<rect x="3.5" y="4.5" width="17" height="15" rx="2.6"/><circle cx="9" cy="9.6" r="1.7"/><path d="M20.5 15.5L16 11l-8.5 8.5"/>',
    globe: '<circle cx="12" cy="12" r="8.6"/><path d="M3.4 12h17.2M12 3.4c2.4 2.5 3.5 5.4 3.5 8.6s-1.1 6.1-3.5 8.6c-2.4-2.5-3.5-5.4-3.5-8.6s1.1-6.1 3.5-8.6z"/>',
    eye: '<path d="M3 3l18 18M10.6 5.6A10 10 0 0 1 12 5.5c5 0 8.5 4.5 9.5 6.5a13 13 0 0 1-2.8 3.7M6.6 6.7A13 13 0 0 0 2.5 12c1 2 4.5 6.5 9.5 6.5 1.6 0 3-.4 4.3-1.1"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
    sound: '<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/>',
    car: '<path d="M5 16.5V12.3l1.8-4.8A2 2 0 0 1 8.7 6.2h6.6a2 2 0 0 1 1.9 1.3l1.8 4.8v4.2M3.8 16.5h16.4M6.3 16.5v2.3M17.7 16.5v2.3"/><circle cx="8" cy="13.4" r=".9" fill="currentColor"/><circle cx="16" cy="13.4" r=".9" fill="currentColor"/>',
    phone: '<rect x="6.5" y="2.8" width="11" height="18.4" rx="2.6"/><path d="M10.5 18.2h3"/>',
    book: '<path d="M5 4.8A1.8 1.8 0 0 1 6.8 3H19v15H6.8A1.8 1.8 0 0 0 5 19.8z"/><path d="M5 19.8A1.8 1.8 0 0 0 6.8 21.5H19M9 7h6"/>',
    crown: '<path d="M4 18h16l1.2-10-5.2 4-4-7-4 7-5.2-4z"/>',
    hist: '<path d="M3.5 12a8.5 8.5 0 1 0 2.5-6L3.5 8.5"/><path d="M3.5 4v4.5H8M12 8v4.5l3 1.6"/>',
    chart: '<path d="M4 20V11M10 20V5M16 20v-7M21 20H3"/>',
    brush: '<path d="M14.5 4.5l5 5-7.8 7.8-5-5z"/><path d="M6.7 12.3c-2 .5-3 2-3.2 5.2 3.2-.2 4.7-1.2 5.2-3.2"/>',
    flask: '<path d="M9 3.5h6M10 3.5v6L5 18a2 2 0 0 0 1.8 3h10.4A2 2 0 0 0 19 18l-5-8.5v-6M7.5 14.5h9"/>',
    mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5v3.5"/>',
    mail: '<rect x="3.5" y="5.5" width="17" height="13" rx="2.6"/><path d="M4 7l8 6 8-6"/>',
    chat: '<path d="M20.5 11.5a7.8 7.8 0 0 1-11.3 7l-4.7 1.3 1.3-4.2A7.8 7.8 0 1 1 20.5 11.5z"/>',
    map: '<path d="M9 4.5L3.5 6.5v13L9 17.5l6 2 5.5-2v-13l-5.5 2z"/><path d="M9 4.5v13M15 6.5v13"/>',
    flag: '<path d="M5.5 21V4.5M5.5 5h11l-2 3.8 2 3.7h-11"/>',
    plane: '<path d="M10.5 13.5L4 11l1.5-1.5 7 .5 3.8-3.8a1.8 1.8 0 0 1 2.5 2.5L15 12.5l.5 7L14 21l-2.5-6.5-3 3v2.5L7 21.5l-1-3.5-3.5-1 1.5-1.5h2.5z"/>',
    swap: '<path d="M7 4.5l-3 3 3 3M4 7.5h12M17 13.5l3 3-3 3M20 16.5H8"/>',
    fire: '<path d="M12 21a6 6 0 0 0 6-6c0-4.5-4-6-4.5-10.5C10 7 8.5 9.5 8.8 12.2 7.4 11.5 6.8 10.3 6.6 9 5.5 10.5 6 13 6 15a6 6 0 0 0 6 6z"/>',
    medal: '<circle cx="12" cy="15" r="5.5"/><path d="M8.5 10.5L6 3.5h4l2 5 2-5h4l-2.5 7M12 12.8l.8 1.6 1.7.2-1.2 1.2.3 1.7-1.6-.8-1.6.8.3-1.7-1.2-1.2 1.7-.2z"/>',
    target: '<circle cx="12" cy="12" r="8.6"/><circle cx="12" cy="12" r="4.8"/><circle cx="12" cy="12" r="1.2" fill="currentColor"/>',
    ticket: '<path d="M3.5 8.5a2 2 0 0 0 0 4v4.5h17v-4.5a2 2 0 0 1 0-4V4h-17zM14 4v3M14 10v2M14 15v3"/>',
    calendar: '<rect x="3.5" y="5" width="17" height="15.5" rx="3.2"/><path d="M3.5 10h17M8 3v4M16 3v4M7.5 13.5h2M11 13.5h2M14.5 13.5h2M7.5 17h2M11 17h2"/>',
    grid: '<rect x="4" y="4" width="6.5" height="6.5" rx="1.8"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.8"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.8"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.8"/>',
    shirt: '<path d="M8.5 3.5L4 6l1.8 4.3 2.2-1v11h8v-11l2.2 1L20 6l-4.5-2.5a3.5 3.5 0 0 1-7 0z"/>',
    info: '<circle cx="12" cy="12" r="8.6"/><path d="M12 11v5.5M12 7.8h.01"/>',
    compare: '<path d="M12 3.5v17M5 8l-2.5 5a3 3 0 0 0 5 0zM19 8l-2.5 5a3 3 0 0 0 5 0zM5 7.5h14"/>',
    download: '<path d="M12 4v11M7.5 10.5L12 15l4.5-4.5M5 19.5h14"/>',
    check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>'
  };
  var I = U.icon = function (n, cls, sw) { return '<svg class="' + (cls || "") + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="' + (sw || 1.8) + '" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (IP[n] || "") + "</svg>"; };
  var CHEV = U.chev = '<svg class="chev" viewBox="0 0 9 15" aria-hidden="true"><path d="M7.4 1.5L1.6 7.5l5.8 6" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  // ------------------------------------------------------------------ names, crests, colours
  U.tname = function (t) { if (!t) return ""; var ar = t.name_ar || cfg.tn[t.id]; return ar ? esc(ar) : '<span class="lat">' + esc(t.name || "") + "</span>"; };
  U.tnameT = function (t) { return t ? (t.name_ar || cfg.tn[t.id] || t.name || "") : ""; };
  U.pname = function (p) { if (!p) return ""; var ar = p.id != null && cfg.pn[p.id]; return ar ? esc(ar) : '<span class="lat">' + esc(p.name || "") + "</span>"; };
  U.pnameT = function (p) { return p ? ((p.id != null && cfg.pn[p.id]) || p.name || "") : ""; };
  U.crest = function (t, cls) { if (!t || !t.id || t.nocrest) return '<span class="cr ' + (cls || "") + '"></span>';
    if (t.logo) return '<img class="cr' + (cls ? " " + cls : "") + '" src="' + esc(t.logo) + '" alt="" width="24" height="24" loading="lazy" onerror="this.style.visibility=\'hidden\'">';   /* 365Scores' crests, as the encyclopedia shows them */
    var big = /\b(lg|xl)\b/.test(cls || ""); return '<img class="cr' + (cls ? " " + cls : "") + '" src="/logo/' + (big ? t.id + ".png" : "96/" + t.id + ".webp") + '" alt="" width="24" height="24"' + (big ? "" : ' loading="lazy"') + ' onerror="if(!this.dataset.f){this.dataset.f=1;this.src=\'/logo/' + t.id + '.png\'}else this.style.visibility=\'hidden\'">'; };
  U.lg = function (cid, cls) { return '<img class="' + (cls || "lg") + '" src="/lg/' + cid + '.png" alt="" width="22" height="22" loading="lazy" onerror="this.style.visibility=\'hidden\'">'; };
  function lumi(h) { var n = parseInt(String(h).slice(1, 7), 16); if (isNaN(n)) return .5; var f = function (v) { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }; return .2126 * f(n >> 16 & 255) + .7152 * f(n >> 8 & 255) + .0722 * f(n & 255); }
  U.col = function (id, i) { var c = cfg.tc[id]; return c ? (c[i || 0] || c[0]) : (i ? "#F2F2F7" : "#8E8E93"); };
  U.ink = function (h) { return lumi(h) > .4 ? "#111" : "#fff"; };
  // two sides that must be told apart (bars, pitch): if both clubs' first colours are close, the away side takes its second
  U.pair = function (h, a) { var c1 = U.col(h), c2 = U.col(a), d = function (x, y) { var p = parseInt(x.slice(1), 16), q = parseInt(y.slice(1), 16); return Math.abs((p >> 16) - (q >> 16)) + Math.abs((p >> 8 & 255) - (q >> 8 & 255)) + Math.abs((p & 255) - (q & 255)); };
    if (d(c1, c2) < 90) { var alt = U.col(a, 1); if (d(c1, alt) >= 90) c2 = alt; else c2 = lumi(c1) > .35 ? "#3A3A3C" : "#C7C7CC"; } return [c1, c2]; };
  var FIFA2 = "UAE:AE,KSA:SA,QAT:QA,BHR:BH,KUW:KW,OMA:OM,IRQ:IQ,JOR:JO,SYR:SY,LBN:LB,PLE:PS,YEM:YE,EGY:EG,LBY:LY,TUN:TN,ALG:DZ,MAR:MA,SUD:SD,MTN:MR".split(",");
  var CCS = { UAE: "الإمارات", ARE: "الإمارات", AE: "الإمارات", KSA: "السعودية", SAU: "السعودية", USA: "أمريكا", GBR: "بريطانيا", KOR: "كوريا الجنوبية", PRK: "كوريا الشمالية", COD: "الكونغو الديمقراطية", CIV: "ساحل العاج", BIH: "البوسنة", CZE: "التشيك" };
  U.country = function (code) { if (!code) return ""; var k = String(code).toUpperCase(), n = CCS[k] || cfg.cc[code] || cfg.cc[k] || code; return String(n).replace(/^الإمارات العربية المتحدة$/, "الإمارات").replace(/^المملكة العربية السعودية$/, "السعودية"); };
  // FotMob venues outside the UAE carry an English name and city: the city in Arabic where we know it
  var CITY = [[/abu ?dhabi|ab[uū] [zẓ]ab[iī]/i, "أبوظبي"], [/dubai/i, "دبي"], [/sharjah/i, "الشارقة"], [/al[- ]?ain/i, "العين"], [/ajman/i, "عجمان"], [/ras al[- ]?khaimah/i, "رأس الخيمة"], [/fujairah/i, "الفجيرة"], [/umm al[- ]?quwain/i, "أم القيوين"], [/khor ?fakkan/i, "خورفكان"], [/kalba/i, "كلباء"], [/hatta/i, "حتا"], [/madinat zayed/i, "مدينة زايد"], [/riyadh/i, "الرياض"], [/jeddah|jiddah/i, "جدة"], [/dammam/i, "الدمام"], [/mecca|makkah/i, "مكة"], [/medina|madinah/i, "المدينة المنورة"], [/buraid/i, "بريدة"], [/abha/i, "أبها"], [/khobar/i, "الخبر"], [/doha/i, "الدوحة"], [/rayyan/i, "الريان"], [/wakrah/i, "الوكرة"], [/kuwait/i, "الكويت"], [/muscat/i, "مسقط"], [/manama/i, "المنامة"], [/riffa/i, "الرفاع"], [/cairo/i, "القاهرة"], [/alexandria/i, "الإسكندرية"], [/casablanca/i, "الدار البيضاء"], [/rabat/i, "الرباط"], [/algiers/i, "الجزائر"], [/tunis/i, "تونس"], [/baghdad/i, "بغداد"], [/basra/i, "البصرة"], [/erbil/i, "أربيل"], [/amman/i, "عمّان"], [/beirut/i, "بيروت"], [/damascus/i, "دمشق"], [/london/i, "لندن"], [/madrid/i, "مدريد"], [/barcelona/i, "برشلونة"], [/manchester/i, "مانشستر"], [/liverpool/i, "ليفربول"], [/paris/i, "باريس"], [/milan/i, "ميلانو"], [/munich|münchen/i, "ميونخ"]];
  U.city = function (c) { if (!c) return ""; for (var i = 0; i < CITY.length; i++) if (CITY[i][0].test(c)) return CITY[i][1]; return ""; };
  U.venueAr = function (v) { if (!v) return ""; if (v.name_ar) return v.name_ar; var c = U.city(v.city || v.name_en || ""); return c ? "في " + c : ""; };
  U.dateAr = function (s) { var m = /^(\d{4})-(\d\d)-(\d\d)/.exec(String(s || "")); return m ? +m[3] + " " + MON[+m[2] - 1] + " " + m[1] : esc(s || ""); };

  // ------------------------------------------------------------------ match status
  var isLive = U.isLive = function (m) { return !!m && (m.status === "live" || m.status === "ht"); };
  var mnt = function (x) { return '<bdi dir="ltr" class="num">' + esc(x) + "'</bdi>"; };
  U.minute = function (m) {
    if (m.status === "ht" || m.period === "HT" || m.period === "break") return "استراحة";
    var st = m.period_start && Date.parse(m.period_start), base = m.period_base, len = m.period_length || 45, now = cfg.now || Date.now();
    if (st && base != null) { var el = Math.floor((now - st) / 6e4) + 1; if (el < 1) el = 1; var mm = base + el, cap = base + len; if (mm > cap) return mnt(cap + "+" + Math.min(mm - cap, 15)); return mnt(mm); }
    return m.minute ? mnt(m.minute) : "مباشر";
  };
  U.score = function (sc, cls) { if (!sc) return ""; return '<span class="sc' + (cls ? " " + cls : "") + '" dir="rtl">' + (sc.home == null ? "" : sc.home) + " - " + (sc.away == null ? "" : sc.away) + "</span>"; };
  U.scoreText = function (sc) { return sc ? sc.home + " - " + sc.away : ""; };
  U.statusWord = function (m) {
    switch (m.status) {
      case "finished": return m.status_detail === "AET" ? "بعد الإضافي" : m.status_detail === "Pen" ? "بالترجيح" : "انتهت";
      case "postponed": return "تأجلت"; case "cancelled": return "ألغيت"; case "abandoned": return "توقفت"; case "awarded": return "قرار إداري";
      default: return "";
    }
  };
  function winner(m) { var s = m.score; if (m.status !== "finished" || !s) return 0; if (s.home > s.away) return 1; if (s.away > s.home) return 2; var p = m.penalties; if (p) return p.home > p.away ? 1 : p.away > p.home ? 2 : 0; return 0; }
  U.winner = winner;
  function caption(m, o) {
    if (isLive(m)) return '<span class="st live"><i class="dot"></i>' + U.minute(m) + "</span>";
    if (m.status === "finished") { var t = U.statusWord(m); if (m.penalties) t = "ترجيح " + '<span dir="rtl" class="num">' + m.penalties.home + " - " + m.penalties.away + "</span>";
      if (o && o.team) { var w = winner(m), r = !w ? "D" : ((w === 1) === (m.home.id === o.team)) ? "W" : "L"; return '<span class="st">' + (o.date ? tm(m.kickoff_uae || m.kickoff_utc, "ds") + " · " : "") + '<i class="rsl ' + r + '">' + { W: "ف", D: "ت", L: "خ" }[r] + "</i></span>"; }
      return '<span class="st">' + (o && o.date ? tm(m.kickoff_uae || m.kickoff_utc, "ds") + " · " : "") + t + "</span>"; }
    var w2 = U.statusWord(m); if (w2) return '<span class="st">' + w2 + "</span>";
    if (o && o.date) return '<span class="st">' + (m.date_tbd ? "الموعد ما تحدد" : tm(m.kickoff_uae || m.kickoff_utc, "r")) + "</span>";
    if (m.time_tbd) return '<span class="st">الساعة ما تحددت</span>';
    return "";
  }
  U.caption = caption;
  function mid(m, cls) {
    if (m.score && (isLive(m) || m.status === "finished" || m.status === "awarded" || m.status === "abandoned")) return U.score(m.score, cls);
    if (m.date_tbd || m.time_tbd || !(m.kickoff_uae || m.kickoff_utc)) return '<span class="sc tbd">—</span>';
    return '<span class="sc ko">' + tm(m.kickoff_uae || m.kickoff_utc) + "</span>";
  }
  U.mid = mid;

  // ------------------------------------------------------------------ match row: home (right) · score · away (left)
  U.mrow = function (m, o) {
    o = o || {};
    var w = winner(m), mine = o.mine && (o.mine[m.home.id] || o.mine[m.away.id]);
    var side = function (t, k, win, lose) { var n = '<span class="tn">' + (t.placeholder && U.slot(t) ? esc(U.slot(t)) : U.tname(t)) + "</span>", c = U.crest(t); return '<span class="mr-t ' + k + (win ? " w" : lose ? " l" : "") + '">' + (k === "h" ? n + c : c + n) + "</span>"; };
    return '<a class="mr' + (mine ? " mine" : "") + (isLive(m) ? " is-live" : "") + '" href="' + esc(m.href || L("m", m.id)) + '" data-mid="' + esc(m.id) + '">' + side(m.home, "h", w === 1, w === 2) + '<span class="mr-m">' + mid(m, o.spoil ? "hide" : "") + caption(m, o) + "</span>" + side(m.away, "a", w === 2, w === 1) + "</a>";
  };
  U.slot = function (t) { var m = /^(winner|loser)\s+(sf|qf|r16|semi[- ]?final|quarter[- ]?final)\s*(\d+)/i.exec(String((t && t.name) || "")); if (!m) return null; var st = /^s/i.test(m[2]) ? "نص النهائي" : /^q/i.test(m[2]) ? "ربع النهائي" : "دور الـ16"; return (/^w/i.test(m[1]) ? "الفايز من " : "الخسران من ") + st + " " + m[3]; };
  // a competition's block in a day list: header row (logo, name, round) + its matches
  function commonRound(ms) { var r = ms.map(U.roundLabel); return r.every(function (x) { return x && x === r[0]; }) ? r[0] : ""; }
  U.compName = function (cid, m) { var c = cfg.cn[cid]; return (c && c[1]) || (m && m.comp_name_ar) || ""; };
  U.compCard = function (cid, ms, o) {
    var sub = commonRound(ms);
    return '<section class="card" data-comp="' + cid + '"><a class="hd-row" href="' + L("c", cid) + '">' + U.lg(cid) + '<span class="rt"><span>' + esc(U.compName(cid, ms[0])) + "</span>" + (sub ? "<small>" + esc(sub) + "</small>" : "") + "</span>" + CHEV + "</a>" +
      ms.map(function (m) { return U.mrow(m, o); }).join("") + "</section>";
  };
  var byKick = function (a, b) { return String(a.kickoff_utc || "").localeCompare(String(b.kickoff_utc || "")) || (a.id - b.id); };
  U.byKick = byKick;
  // what a day list shows of each match, hashed: the page carries the build's, the browser redraws only when its own differs
  U.sig = function (ms) { var s = ""; (ms || []).forEach(function (m) { s += m.id + ":" + m.status + ":" + (m.score ? m.score.home + "-" + m.score.away : "") + ":" + (m.minute || "") + ":" + (m.kickoff_utc || "") + "|"; });
    var h = 5381; for (var i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0; return (h >>> 0).toString(36) + "." + (ms || []).length; };
  // matches grouped by competition: a competition with one of my teams first, then the index order (the UAE first)
  U.groups = function (ms, o) {
    o = o || {}; var g = {}, order = [];
    ms.forEach(function (m) { if (!g[m.comp]) { g[m.comp] = []; order.push(m.comp); } g[m.comp].push(m); });
    var rank = function (cid) { var c = cfg.cn[cid]; return c ? c[3] : 999; };
    var mineIn = function (cid) { return o.mine && g[cid].some(function (m) { return o.mine[m.home.id] || o.mine[m.away.id]; }) ? 0 : 1; };
    order.sort(function (a, b) { return mineIn(a) - mineIn(b) || rank(a) - rank(b) || a - b; });
    return order.map(function (cid) { return [cid, g[cid].sort(byKick)]; });
  };
  U.dayList = function (ms, o) {
    o = o || {}; if (!ms.length) return '<div class="card"><p class="empty">' + (o.empty || "ما في مباريات في هاليوم.") + "</p></div>";
    var gs = U.groups(ms, o), open = o.fold || 12, html = gs.slice(0, open).map(function (g) { return U.compCard(g[0], g[1], o); }).join("");
    if (gs.length > open) html += '<details class="dz rest"><summary class="card"><span class="row more-row">باقي البطولات <span class="num">(' + (gs.length - open) + ")</span></span></summary>" + gs.slice(open).map(function (g) { return U.compCard(g[0], g[1], o); }).join("") + "</details>";
    return html;
  };

  // ------------------------------------------------------------------ feature card (my team / the day's top match)
  U.fcard = function (m, kick) {
    var pc = U.pair(m.home.id, m.away.id);
    return '<a class="card fc" style="--h:' + pc[0] + ";--a:" + pc[1] + '" href="' + esc(m.href || L("m", m.id)) + '" data-mid="' + esc(m.id) + '"><div class="fc-top">' + U.lg(m.comp) + "<span>" + esc(kick || U.compName(m.comp, m)) + "</span>" + (isLive(m) ? caption(m) : m.status === "finished" ? '<span class="st">' + U.statusWord(m) + "</span>" : '<span class="st">' + (m.date_tbd ? "" : tm(m.kickoff_uae || m.kickoff_utc, "r")) + "</span>") + "</div>" +
      '<div class="fc-body"><span class="fc-t">' + U.crest(m.home, "lg") + "<span>" + U.tname(m.home) + '</span></span><span class="mr-m">' + mid(m) + '</span><span class="fc-t">' + U.crest(m.away, "lg") + "<span>" + U.tname(m.away) + "</span></span></div>" +
      '<div class="fc-sub">' + esc(U.compName(m.comp, m)) + (U.roundLabel(m) ? " · " + esc(U.roundLabel(m)) : "") + "</div></a>";
  };

  // ------------------------------------------------------------------ generic building blocks
  U.grp = function (title, inner, o) { o = o || {}; return '<section class="grp' + (o.cls ? " " + o.cls : "") + '"' + (o.id ? ' id="' + o.id + '"' : "") + ">" + (title ? '<div class="gh' + (o.big ? " big" : "") + '"><h2>' + title + "</h2>" + (o.more || "") + "</div>" : "") + (o.raw ? inner : '<div class="card">' + inner + "</div>") + (o.foot ? '<p class="gf">' + o.foot + "</p>" : "") + "</section>"; };
  U.row = function (r) {   // {href, icon, c (icon colour), img, t, sub, v, badge, cls, attrs, btn}
    var tag = r.href ? "a" : r.btn ? "button" : "div", at = r.href ? ' href="' + esc(r.href) + '"' + (r.ext ? ' rel="noopener" target="_blank"' : "") : r.btn ? ' type="button"' : "";
    return "<" + tag + ' class="row' + (r.icon || r.img ? " ins" : "") + (r.cls ? " " + r.cls : "") + '"' + at + (r.attrs || "") + ">" + (r.icon ? '<span class="ic" style="--c:' + (r.c || "#8E8E93") + '">' + I(r.icon, "", 2) + "</span>" : "") + (r.img || "") +
      '<span class="rt">' + r.t + (r.sub ? "<small>" + r.sub + "</small>" : "") + "</span>" + (r.v != null && r.v !== "" ? '<span class="rv">' + r.v + "</span>" : "") + (r.badge ? '<span class="badge num">' + r.badge + "</span>" : "") + (r.sw != null ? '<span class="sw" aria-hidden="true"></span>' : "") + (tag !== "div" && r.sw == null ? CHEV : "") + "</" + tag + ">";
  };
  U.rows = function (rs) { return rs.filter(Boolean).map(U.row).join(""); };
  U.seg = function (group, tabs, sel, o) {
    o = o || {}; var i0 = tabs.findIndex(function (t) { return t[0] === sel; });   // -1: nothing chosen yet (the pick before kickoff)
    return '<div class="seg' + (o.sm ? " sm" : "") + (i0 < 0 ? " none" : "") + '" role="tablist" data-seg="' + group + '" style="--n:' + tabs.length + ";--i:" + Math.max(0, i0) + '"><i class="seg-th" aria-hidden="true"></i>' +
      tabs.map(function (t, i) { return '<button type="button" role="tab" data-t="' + t[0] + '" aria-selected="' + (i === i0) + '"' + (t[2] ? ' aria-label="' + esc(t[2]) + '"' : "") + '><span class="sl">' + t[1] + "</span></button>"; }).join("") + "</div>";
  };
  U.segbar = function (group, tabs, sel) { return '<div class="segbar">' + U.seg(group, tabs, sel) + "</div>"; };
  U.pane = function (group, key, html, shown) { return '<section class="pane" data-g="' + group + '" data-p="' + key + '"' + (shown ? "" : " hidden") + ">" + html + "</section>"; };
  U.empty = function (t) { return '<p class="empty">' + t + "</p>"; };

  // ------------------------------------------------------------------ match page
  var STAT_AR = { BallPossesion: "الاستحواذ", expected_goals: "الأهداف المتوقعة", total_shots: "التسديدات", ShotsOnTarget: "على المرمى", ShotsOffTarget: "برا المرمى", big_chance: "فرص محققة", big_chance_missed_title: "فرص ضايعة", corners: "الركنيات", fouls: "الأخطاء", Offsides: "التسلل", yellow_cards: "الإنذارات", red_cards: "الطرد", passes: "التمريرات", accurate_passes: "تمريرات صحيحة", keeper_saves: "تصديات الحارس", touches_opp_box: "لمسات في منطقة الخصم", blocked_shots: "تسديدات مصدودة", shots_inside_box: "من داخل المنطقة", shots_outside_box: "من برا المنطقة", shots_woodwork: "القائم والعارضة", interceptions: "قطع الكورة", clearances: "إبعاد", "matchstats.headers.tackles": "الافتكاك", duel_won: "التحامات ناجحة", aerials_won: "كرات هوائية", dribbles_succeeded: "مراوغات ناجحة", accurate_crosses: "عرضيات صحيحة", long_balls_accurate: "كرات طويلة صحيحة", player_throws: "رميات تماس", ground_duels_won: "التحامات أرضية", own_half_passes: "تمريرات في نصه", opposition_half_passes: "تمريرات في نص الخصم", expected_goals_on_target_variant: "المتوقعة على المرمى", expected_goals_open_play: "المتوقعة من اللعب المفتوح", expected_goals_set_play: "المتوقعة من الكرات الثابتة" };
  var GRP_AR = { top_stats: "أهم الأرقام", shots: "التسديدات", expected_goals: "الأهداف المتوقعة", passes: "التمريرات", defence: "الدفاع", duels: "الالتحامات", discipline: "الانضباط" };
  U.STAT_AR = STAT_AR;
  var EVT = { penalty_goal: "من ركلة جزاء", own_goal: "هدف عكسي", missed_penalty: "ضيّع ركلة جزاء", yellow: "إنذار", red: "طرد", second_yellow: "إنذار ثاني وطرد" };
  var VAR_AR = { goal_disallowed: "ألغى الهدف", goal_disallowed_offside: "ألغى الهدف: تسلل", offside: "تسلل", goal_confirmed: "أكد الهدف", penalty_cancelled: "ألغى ركلة الجزاء", penalty_awarded: "احتسب ركلة جزاء", card_changed: "غيّر الكرت", card: "كرت", other: "مراجعة" };
  function evIcon(t) {
    if (/^(goal|penalty_goal|own_goal|shootout_goal)$/.test(t)) return I("ball", "ei", 1.6);
    if (t === "missed_penalty" || t === "shootout_miss") return I("miss", "ei");
    if (t === "yellow") return '<i class="cardic ei" style="width:12px"></i>'; if (t === "red") return '<i class="cardic r ei" style="width:12px"></i>'; if (t === "second_yellow") return '<i class="cardic yr ei" style="width:12px"></i>';
    if (t === "sub") return I("sub", "ei", 2); if (t === "var") return I("vr", "ei", 1.6); return "";
  }
  U.evIcon = evIcon;
  function evMin(e) { return e.minute + (e.added ? "+" + e.added : ""); }
  U.events = function (md, o) {
    o = o || {}; var ev = (md.events || []).filter(function (e) { return e.type !== "added_time" && !/^shootout/.test(e.type); });
    if (!ev.length) return '<div class="card">' + U.empty(md.status === "scheduled" ? "المباراة ما بدت." : "ما في أحداث مسجّلة للحين.") + "</div>";
    var key = function (e) { return e.minute * 100 + (e.added || 0) + (e.type === "half" ? 50 : 0); };
    // item 11: goals numbered in the order the match file lists them, like the build's goal pages /m/<id>/g/<n>/ and v3's R.events
    // (id="g<n>" is the anchor of a goal's share link, src/goalshare.js)
    var GL = (md.events || []).filter(function (e) { return /^(goal|penalty_goal|own_goal)$/.test(e.type); });
    ev = ev.slice().sort(function (a, b) { return key(a) - key(b); });
    if (isLive(md)) ev.reverse();
    var li = ev.map(function (e) {
      if (e.type === "half") { var hl = { HT: "الاستراحة", FT: "نهاية المباراة", AET: "نهاية الوقت الإضافي", EHT: "نهاية الشوط الإضافي الأول", Pen: "ركلات الترجيح" }[e.detail] || esc(e.detail || "");
        var s = e.detail === "HT" ? md.halftime_score : e.detail === "FT" || e.detail === "AET" ? md.score : null; return '<li class="mark">' + hl + (s ? " " + U.score(s) : "") + "</li>"; }
      var who = e.player ? "<b>" + U.pname(e.player) + "</b>" : "", sub = "";
      if (/goal/.test(e.type)) sub = [e.type !== "goal" ? EVT[e.type] : "", e.assist ? "صناعة " + U.pname(e.assist) : "", e.score ? U.score(e.score) : ""].filter(Boolean).join(" · ");
      else if (e.type === "sub") { who = e.player ? "<b>" + U.pname(e.player) + "</b>" : ""; sub = (e.player_out ? "طلع " + U.pname(e.player_out) : "") + (e.detail === "injury" ? " · إصابة" : ""); }
      else if (e.type === "var") { who = "<b>الفار: " + (VAR_AR[e.var_outcome] || "مراجعة") + "</b>"; sub = e.player ? U.pname(e.player) : ""; }
      else if (EVT[e.type]) sub = EVT[e.type];
      var side = e.team === "away" ? "away" : "home";
      var gk = /^(goal|penalty_goal|own_goal)$/.test(e.type) && e.player && e.player.id ? ' data-goal-key="' + esc(evMin(e)) + "-" + esc(e.player.id) + '"' : "";   // src/media.js puts «▶ شاهد» on the goals it has a clip for
      var gn = GL.indexOf(e) + 1; if (gn) gk += ' id="g' + gn + '" data-gn="' + gn + '"';
      return '<li class="' + side + (/goal/.test(e.type) && e.type !== "missed_penalty" ? " goal" : "") + '"' + gk + '><span class="em">' + '<bdi dir="ltr">' + esc(evMin(e)) + "'</bdi></span><span class=\"eb\">" + evIcon(e.type) + '<span class="et who">' + who + (sub ? "<small>" + sub + "</small>" : "") + "</span></span></li>";
    }).join("");
    var sh = (md.events || []).filter(function (e) { return /^shootout/.test(e.type); });
    var pens = sh.length ? U.grp("ركلات الترجيح", '<ol class="ev">' + sh.map(function (e) { return '<li class="' + (e.team === "away" ? "away" : "home") + '"><span class="em">' + (e.type === "shootout_goal" ? "✓" : "✗") + '</span><span class="eb">' + evIcon(e.type) + '<span class="et"><b>' + U.pname(e.player) + "</b></span></span></li>"; }).join("") + "</ol>") : "";
    return '<ol class="card ev">' + li + "</ol>" + pens;
  };
  // who scored, under each team in the header
  U.scorers = function (md) {
    var g = { home: [], away: [] };
    (md.events || []).slice().sort(function (a, b) { return a.minute * 100 + (a.added || 0) - (b.minute * 100 + (b.added || 0)); }).forEach(function (e) {
      if (!/^(goal|penalty_goal|own_goal)$/.test(e.type) || !e.player) return;
      var t = e.team === "away" ? "away" : "home", nm = U.pnameT(e.player).split(" "), short = nm.length > 2 ? nm.slice(-1)[0] : nm.join(" ");
      g[t].push(esc(short) + ' <bdi dir="ltr" class="num">' + esc(evMin(e)) + "'</bdi>" + (e.type === "penalty_goal" ? " (ج)" : e.type === "own_goal" ? " (ع)" : ""));
    });
    if (!g.home.length && !g.away.length) return "";
    return '<div class="mh-goals"><ul>' + g.home.map(function (x) { return "<li>" + x + "</li>"; }).join("") + "</ul><span></span><ul>" + g.away.map(function (x) { return "<li>" + x + "</li>"; }).join("") + "</ul></div>";
  };
  U.matchHead = function (md) {
    var live = isLive(md), st;
    if (live) st = '<span class="st live"><i class="dot"></i>' + U.minute(md) + "</span>";
    else if (md.status === "finished") st = '<span class="st">' + U.statusWord(md) + "</span>";
    else if (U.statusWord(md)) st = '<span class="st">' + U.statusWord(md) + "</span>";
    else st = '<span class="st">' + (md.date_tbd ? "الموعد ما تحدد" : tm(md.kickoff_uae || md.kickoff_utc, "r")) + "</span>";
    var w = winner(md);
    return '<div class="mh"><a class="mh-t" href="' + L("t", md.home.id) + '">' + U.crest(md.home, "xl") + "<b" + (w === 2 ? ' class="muted"' : "") + ">" + U.tname(md.home) + '</b></a><div class="mh-mid">' + mid(md) + st +
      (md.penalties ? '<span class="pen">ترجيح <span dir="rtl" class="num">' + md.penalties.home + " - " + md.penalties.away + "</span></span>" : "") +
      (md.status === "finished" && md.halftime_score ? '<span class="pen">الشوط الأول ' + U.score(md.halftime_score, "sm") + "</span>" : "") + '</div><a class="mh-t" href="' + L("t", md.away.id) + '">' + U.crest(md.away, "xl") + "<b" + (w === 1 ? ' class="muted"' : "") + ">" + U.tname(md.away) + "</b></a></div>" + U.scorers(md);
  };
  U.matchTitle = function (md) { return U.tnameT(md.home) + " " + (md.score && (isLive(md) || md.status === "finished") ? md.score.home + " - " + md.score.away : "ضد") + " " + U.tnameT(md.away); };
  // win probability: the latest point while live or after, the pre-match figure before kickoff
  U.probs = function (md) {
    var p = null, src = "";
    if (md.winprob && md.winprob.length && md.status !== "scheduled") { var x = md.winprob[md.winprob.length - 1]; p = [x[1], x[2], x[3]]; src = isLive(md) ? "الحين" : "آخر المباراة"; }
    else if (md.probs && md.probs.home != null) { p = [md.probs.home, md.probs.draw, md.probs.away]; src = "قبل المباراة"; }
    else if (md.winprob_prematch && md.winprob_prematch.p) { p = md.winprob_prematch.p; src = "قبل المباراة"; }
    if (!p) return "";
    var c = U.pair(md.home.id, md.away.id), pc = function (v) { return Math.round(v * 100); };
    return '<div class="wp"><div class="wp-l"><div>' + U.tname(md.home) + "<b>" + pc(p[0]) + "%</b></div><div>تعادل<b>" + pc(p[1]) + "%</b></div><div>" + U.tname(md.away) + "<b>" + pc(p[2]) + '%</b></div></div><div class="wp-bar"><i style="width:' + (p[0] * 100).toFixed(1) + "%;background:" + c[0] + '"></i><i style="width:' + (p[1] * 100).toFixed(1) + '%;background:var(--fill2)"></i><i style="width:' + (p[2] * 100).toFixed(1) + "%;background:" + c[1] + '"></i></div></div>' + (src ? '<p class="gf" style="padding:0 16px 12px">' + src + "، من نموذج تيفو</p>" : "");
  };
  // the win-probability curve (home above the middle, away below), minute 0 at the right
  U.wpChart = function (md) {
    var W = md.winprob; if (!W || W.length < 3) return "";
    var w = 600, h = 180, mx = Math.max(90, W[W.length - 1][0]), X = function (m) { return (w - 10 - (m / mx) * (w - 20)).toFixed(1); }, Y = function (v) { return (h / 2 - v * (h / 2 - 8)).toFixed(1); };
    var c = U.pair(md.home.id, md.away.id), ph = W.map(function (x, i) { return (i ? "L" : "M") + X(x[0]) + " " + Y(x[1]); }).join(""), pa = W.map(function (x, i) { return (i ? "L" : "M") + X(x[0]) + " " + Y(-x[3]); }).join("");
    var ticks = [0, 45, 90].concat(mx > 100 ? [120] : []).map(function (t) { return '<text class="ax" x="' + X(t) + '" y="' + (h + 12) + '" text-anchor="middle">' + t + "</text>"; }).join("");
    var goals = (md.events || []).filter(function (e) { return /^(goal|penalty_goal|own_goal)$/.test(e.type); }).map(function (e) { return '<line x1="' + X(e.minute + (e.added || 0) / 10) + '" x2="' + X(e.minute + (e.added || 0) / 10) + '" y1="4" y2="' + (h - 4) + '" stroke="var(--label3)" stroke-dasharray="2 3"/>'; }).join("");
    return '<svg class="chart" viewBox="0 0 ' + w + " " + (h + 16) + '" role="img" aria-label="فرص الفوز دقيقة بدقيقة"><line class="gl" x1="10" x2="' + (w - 10) + '" y1="' + h / 2 + '" y2="' + h / 2 + '"/>' + goals + '<path d="' + ph + '" fill="none" stroke="' + c[0] + '" stroke-width="2.5"/><path d="' + pa + '" fill="none" stroke="' + c[1] + '" stroke-width="2.5"/>' + ticks + "</svg>" +
      '<p class="gf">فوق الخط: فرصة ' + U.tname(md.home) + "، وتحته: فرصة " + U.tname(md.away) + ". الخطوط المنقطة أهداف.</p>";
  };
  U.momentum = function (md) {
    var M = md.momentum; if (!M || M.length < 5) return "";
    var pts = M.map(function (x, i) { return Array.isArray(x) ? x : x && x.minute != null ? [x.minute, x.value] : [i, x]; }), mx = Math.max(90, pts[pts.length - 1][0]), w = 600, h = 120, top = Math.max.apply(null, pts.map(function (p) { return Math.abs(p[1]); })) || 1;
    var c = U.pair(md.home.id, md.away.id), bw = Math.max(2, (w - 20) / pts.length - 1);
    var bars = pts.map(function (p) { var x = w - 10 - (p[0] / mx) * (w - 20), v = p[1] / top * (h / 2 - 6); return '<rect x="' + (x - bw / 2).toFixed(1) + '" y="' + (v > 0 ? h / 2 - v : h / 2).toFixed(1) + '" width="' + bw.toFixed(1) + '" height="' + Math.abs(v).toFixed(1) + '" fill="' + (v > 0 ? c[0] : c[1]) + '" rx="1"/>'; }).join("");
    return '<svg class="chart" viewBox="0 0 ' + w + " " + h + '" role="img" aria-label="الضغط دقيقة بدقيقة">' + bars + '<line class="gl" x1="10" x2="' + (w - 10) + '" y1="' + h / 2 + '" y2="' + h / 2 + '"/></svg><p class="gf">فوق: ضغط ' + U.tname(md.home) + "، وتحت: ضغط " + U.tname(md.away) + ".</p>";
  };
  U.stats = function (md) {
    var groups = (md.stats || []).filter(function (g) { return g.items && g.items.length; });
    if (!groups.length) return '<div class="card">' + U.empty(md.status === "scheduled" ? "الأرقام تنزل مع بداية المباراة." : "ما عندنا أرقام لهالمباراة.") + "</div>";
    var c = U.pair(md.home.id, md.away.id), seen = {}, poss = null, out = "";
    var cnt = function (side, re) { return (md.events || []).filter(function (e) { return e.team === side && re.test(e.type); }).length; };
    groups.forEach(function (g) {
      var rows = g.items.filter(function (i) { if (seen[i.key] || !STAT_AR[i.key]) return false; seen[i.key] = 1; if (i.key === "BallPossesion") { poss = i; return false; } return (parseFloat(i.home) || 0) + (parseFloat(i.away) || 0) > 0; }).map(function (i) {
        if (i.key === "yellow_cards" && (md.events || []).length) { i = Object.assign({}, i, { home: cnt("home", /^yellow$/), away: cnt("away", /^yellow$/) }); }
        var h = parseFloat(i.home) || 0, a = parseFloat(i.away) || 0, t = h + a || 1, lower = /fouls|cards|Offsides/.test(i.key), hl = lower ? h < a : h > a, al = lower ? a < h : a > h;
        return '<div class="str"><div class="str-top"><b class="num' + (hl ? ' lead" style="--tc:' + c[0] + ";--tci:" + U.ink(c[0]) : "") + '">' + esc(i.home) + "</b><span>" + STAT_AR[i.key] + '</span><b class="num' + (al ? ' lead" style="--tc:' + c[1] + ";--tci:" + U.ink(c[1]) : "") + '">' + esc(i.away) + '</b></div><div class="str-bar" style="--hc:' + c[0] + ";--ac:" + c[1] + '"><i class="hb" style="flex:' + (h / t).toFixed(3) + '"></i><i class="ab" style="flex:' + (a / t).toFixed(3) + '"></i></div></div>';
      }).join("");
      if (rows) out += U.grp(GRP_AR[g.key] || esc(g.title || ""), '<div class="stg">' + rows + "</div>");
    });
    var pz = poss ? '<div class="card poss"><div class="str-top"><span class="num"></span><span>الاستحواذ</span><span></span></div><div class="poss-bar"><i style="width:' + poss.home + "%;background:" + c[0] + ";--ci:" + U.ink(c[0]) + '">' + poss.home + '%</i><i style="width:' + poss.away + "%;background:" + c[1] + ";--ci:" + U.ink(c[1]) + '">' + poss.away + "%</i></div></div>" : "";
    var xg = md.xg && md.xg.home != null ? U.grp("الأهداف المتوقعة (xG)", '<div class="stg"><div class="str"><div class="str-top"><b class="num">' + Number(md.xg.home).toFixed(2) + "</b><span>مجموع الفرص</span><b class=\"num\">" + Number(md.xg.away).toFixed(2) + "</b></div></div></div>") : "";
    return pz + xg + out;
  };
  // lineups on one vertical pitch: away at the top, home at the bottom (xy: FotMob's 0-1 fractions from each side's own goal)
  function rclass(r) { r = +r; return r >= 8 ? "rt-hi" : r >= 7 ? "rt-md" : r >= 6 ? "rt-lo" : "rt-bad"; }
  U.lineups = function (md) {
    var L0 = md.lineups; if (!L0 || !L0.home || !(L0.home.starters || []).length) return '<div class="card">' + U.empty(md.status === "scheduled" ? "التشكيلة تنزل قبل المباراة بساعة تقريباً." : "ما نزلت التشكيلة لهالمباراة.") + "</div>";
    var c = U.pair(md.home.id, md.away.id), evs = md.events || [];
    var badges = function (p) { var b = ""; evs.forEach(function (e) { if (e.player && e.player.id === p.id) { if (/^(goal|penalty_goal)$/.test(e.type)) b += I("ball", "", 1.6); else if (e.type === "yellow") b += '<i class="cardic"></i>'; else if (e.type === "red" || e.type === "second_yellow") b += '<i class="cardic r"></i>'; } if (e.type === "sub" && e.player_out && e.player_out.id === p.id) b += I("sub", "", 2.2); }); return b ? '<span class="bdg">' + b + "</span>" : ""; };
    // one word on the pitch, as broadcasters print it: the family name («الحوسني»), two words when the last is short («عبد الله»)
    var surname = function (p) { var n = U.pnameT(p).trim(), w = n.split(/\s+/); if (w.length < 2) return n; var last = w[w.length - 1]; return last.length <= 3 || /^(الله|الدين|الرحمن)$/.test(last) ? w.slice(-2).join(" ") : last; };
    var dot = function (p, side) { var xy = p.xy; if (!xy) return ""; var x = side === "home" ? xy.x : 1 - xy.x, y = side === "home" ? 100 - xy.y * 47 - 2 : xy.y * 47 + 2, col = c[side === "home" ? 0 : 1];
      return '<a class="pp" href="' + L("p", p.id) + '" style="left:' + (x * 100).toFixed(1) + "%;top:" + y.toFixed(1) + '%"><span class="sh" style="--pc:' + col + ";--pci:" + U.ink(col) + '">' + esc(p.number != null ? p.number : "") + (p.rating ? '<span class="rtg ' + rclass(p.rating) + '">' + Number(p.rating).toFixed(1) + "</span>" : "") + badges(p) + '</span><span class="nm">' + esc(surname(p)) + "</span></a>"; };
    var pitch = '<div class="pitch" dir="ltr"><i class="ln out"></i><i class="ln half"></i><i class="ln cc"></i><i class="ln box1"></i><i class="ln box2"></i>' + (L0.away.starters || []).map(function (p) { return dot(p, "away"); }).join("") + (L0.home.starters || []).map(function (p) { return dot(p, "home"); }).join("") +
      '<span class="pitch-t t1" dir="rtl">' + U.tname(md.away) + (L0.away.formation ? ' <span class="num">' + esc(L0.away.formation) + "</span>" : "") + '</span><span class="pitch-t t2" dir="rtl">' + U.tname(md.home) + (L0.home.formation ? ' <span class="num">' + esc(L0.home.formation) + "</span>" : "") + "</span></div>";
    if (L0.type === "lastStarting11") pitch = '<p class="note">التشكيلة الرسمية ما نزلت. هذي آخر تشكيلة لعب فيها الفريقين.</p><div class="mt">' + pitch + "</div>";
    var list = function (side) { var S = L0[side] || {}, subs = (S.subs || []), un = (S.unavailable || []), co = S.coach;
      var prow = function (p, x) { return '<a class="row" href="' + L("p", p.id) + '"><span class="rt">' + '<span class="num muted">' + esc(p.number != null ? p.number : "") + "</span> " + U.pname(p) + (x ? "<small>" + x + "</small>" : "") + "</span>" + (p.rating ? '<span class="chip num ' + rclass(p.rating) + '" style="color:#fff">' + Number(p.rating).toFixed(1) + "</span>" : "") + CHEV + "</a>"; };
      var cameIn = function (p) { var e = evs.filter(function (e) { return e.type === "sub" && e.player && e.player.id === p.id; })[0]; return e ? "دخل الدقيقة " + '<bdi dir="ltr">' + esc(evMin(e)) + "'</bdi>" : ""; };
      return (co && co.name ? U.grp("المدرب", '<div class="row"><span class="rt">' + (cfg.pn[co.id] ? esc(cfg.pn[co.id]) : '<span class="lat">' + esc(co.name) + "</span>") + "</span></div>") : "") +
        (subs.length ? U.grp("البدلاء", subs.map(function (p) { return prow(p, cameIn(p)); }).join("")) : "") +
        (un.length ? U.grp("الغايبين", un.map(function (p) { return '<a class="row" href="' + L("p", p.id) + '"><span class="rt">' + U.pname(p) + "<small>" + (p.type === "suspension" ? "موقوف" : "مصاب") + (p.expected_return && !/unknown/i.test(p.expected_return) ? " · يرجع " + esc(p.expected_return) : "") + "</small></span>" + CHEV + "</a>"; }).join("")) : ""); };
    return '<div class="card" style="padding:10px;background:var(--bg2)">' + pitch + "</div>" + '<div class="mt2">' + U.seg("lu", [["home", U.tname(md.home)], ["away", U.tname(md.away)]], "home", { sm: 1 }) + "</div>" + U.pane("lu", "home", list("home"), true) + U.pane("lu", "away", list("away"));
  };
  U.h2h = function (md) {
    var H = md.h2h; if (!H || !H.summary) return '<div class="card">' + U.empty("ما عندنا مواجهات سابقة بين الفريقين.") + "</div>";
    var s = H.summary, tot = (s.home_wins || 0) + (s.draws || 0) + (s.away_wins || 0) || 1, c = U.pair(md.home.id, md.away.id);
    var sum = '<div class="card wp"><div class="wp-l"><div>' + U.tname(md.home) + "<b>" + (s.home_wins || 0) + "</b></div><div>تعادل<b>" + (s.draws || 0) + "</b></div><div>" + U.tname(md.away) + "<b>" + (s.away_wins || 0) + '</b></div></div><div class="wp-bar"><i style="width:' + (s.home_wins / tot * 100).toFixed(1) + "%;background:" + c[0] + '"></i><i style="width:' + (s.draws / tot * 100).toFixed(1) + '%;background:var(--fill2)"></i><i style="width:' + (s.away_wins / tot * 100).toFixed(1) + "%;background:" + c[1] + '"></i></div></div>';
    var ms = (H.matches || []).filter(function (m) { return m.score; }).slice(0, 12);
    return sum + (ms.length ? U.grp("آخر المواجهات", ms.map(function (m) { return U.mrow(Object.assign({ status: "finished" }, m), { date: true }); }).join("")) : "");
  };
  var HEAT = { danger: "حر شديد", extreme: "حر خطير", caution: "حر", "extreme caution": "حر شديد", none: "" };
  var PRAY = { fajr: "الفجر", dhuhr: "الظهر", asr: "العصر", maghrib: "المغرب", isha: "العشاء" };
  U.info = function (md, o) {
    o = o || {}; var v = md.venue || {}, rows = [];
    rows.push({ icon: "calendar", c: "#FF3B30", t: "الموعد", v: md.date_tbd ? "ما تحدد" : tm(md.kickoff_uae || md.kickoff_utc, md.time_tbd ? "d" : "dt") });
    rows.push({ icon: "comps", c: "#FF9500", t: "البطولة", href: L("c", md.comp), v: esc(U.compName(md.comp, md)) + (U.roundLabel(md) ? " · " + esc(U.roundLabel(md)) : "") });
    var vn = v.name_ar || v.name_en || v.name; if (vn) rows.push({ icon: "pin", c: "#34C759", t: "الملعب", sub: v.name_ar ? "" : '<span class="lat">' + esc(vn) + "</span>", v: v.name_ar ? esc(v.name_ar) : esc(U.city(v.city || "") || v.city || ""), href: v.lat != null ? "https://www.openstreetmap.org/?mlat=" + v.lat + "&mlon=" + v.lon + "#map=15/" + v.lat + "/" + v.lon : null, ext: 1 });
    if (md.referee && md.referee.name) rows.push({ icon: "whistle", c: "#8E8E93", t: "الحكم", v: esc(md.referee.name) });
    if (md.attendance) rows.push({ icon: "people", c: "#5856D6", t: "الحضور", v: '<span class="num">' + nf(md.attendance) + "</span>" });
    var w = md.weather; if (w && w.available && w.temp_c != null) rows.push({ icon: "sun", c: "#FF9F0A", t: "الطقس", v: '<span class="num">' + Math.round(w.temp_c) + "°</span>" + (w.humidity != null ? " · رطوبة " + '<span class="num">' + w.humidity + "%</span>" : "") + (HEAT[w.heat_category] ? " · " + HEAT[w.heat_category] : "") });
    var pr = md.prayer; if (pr && pr.clashes && pr.clashes.length) pr.clashes.forEach(function (c) { rows.push({ icon: "moon", c: "#0A84FF", t: "صلاة " + (PRAY[c.prayer] || c.prayer), v: '<span class="num">' + esc(c.at_uae) + "</span> · " + (c.segment === "halftime" ? "وقت الاستراحة" : "الدقيقة " + '<span class="num">' + c.minute_of_play + "</span>") }); });
    if (o.ch) rows.push({ icon: "tv", c: "#AF52DE", t: "وين تنقل", v: o.ch, attrs: ' data-ch="' + md.comp + '"' });
    if (md.highlights && md.highlights.url) rows.push({ icon: "play", c: "#FF3B30", t: "شوف الملخص", href: md.highlights.url, ext: 1, cls: "hlrow hlbtn" });   // media.js opens its video sheet from a.hlbtn
    else if (o.hl) rows.push({ icon: "play", c: "#FF3B30", t: "شوف الملخص الرسمي", sub: o.hlsub || "", href: o.hl, ext: 1, cls: "hlrow hlsearch" });   // hidden by media.js once a real video is in
    return U.rows(rows);
  };

  // ------------------------------------------------------------------ competition page
  U.formChips = function (f) { return '<span class="form" aria-label="آخر النتايج">' + (f || []).slice(-5).map(function (x) { return '<i class="' + esc(x) + '">' + ({ W: "ف", D: "ت", L: "خ" }[x] || "") + "</i>"; }).join("") + "</span>"; };
  var gd = function (v) { return '<bdi dir="ltr">' + (v > 0 ? "+" : "") + (v == null ? "" : v) + "</bdi>"; };
  U.table = function (rows, o) {
    o = o || {}; var full = o.full, form = o.form, hl = o.hl || {};
    var head = "<tr><th>#</th><th class=\"tm\">الفريق</th><th>لعب</th>" + (full ? "<th>فوز</th><th>تعادل</th><th>خسارة</th><th>له</th><th>عليه</th>" : "") + "<th>+/-</th><th>نقاط</th>" + (form ? "<th>آخر 5</th>" : "") + "</tr>";
    var body = rows.map(function (r) {
      var z = r.zone && r.zone.color ? '<i style="--z:' + esc(r.zone.color) + '"></i>' : "";
      return '<tr class="' + (hl[r.team.id] ? "hl" : "") + (r.live ? " live" : "") + '"><td class="rk">' + z + (r.rank == null ? "" : r.rank) + '</td><td class="tm"><a href="' + L("t", r.team.id) + '">' + U.crest(r.team) + '<span class="n">' + U.tname(r.team) + "</span></a></td><td>" + (r.played == null ? "" : r.played) + "</td>" +
        (full ? "<td>" + r.won + "</td><td>" + r.drawn + "</td><td>" + r.lost + "</td><td>" + r.gf + "</td><td>" + r.ga + "</td>" : "") + '<td class="dim">' + gd(r.gd != null ? r.gd : (r.gf || 0) - (r.ga || 0)) + '</td><td class="pts">' + (r.pts == null ? "" : r.pts) + "</td>" + (form ? "<td>" + U.formChips(r.form) + "</td>" : "") + "</tr>";
    }).join("");
    return '<div class="tblw"><table class="tbl' + (full || form ? " wide" : "") + '"><thead>' + head + "</thead><tbody>" + body + "</tbody></table></div>";
  };
  var ZONE_AR = function (l) { l = String(l || ""); return /champions league elite|acl elite|afc champions league/i.test(l) ? (/qualif|play-?off/i.test(l) ? "ملحق أبطال آسيا للنخبة" : "أبطال آسيا للنخبة") : /acl two|champions league two|afc cup/i.test(l) ? "أبطال آسيا 2" : /^champions league$/i.test(l) ? "دوري أبطال أوروبا" : /europa league/i.test(l) ? "الدوري الأوروبي" : /conference/i.test(l) ? "دوري المؤتمر" : /relegation play/i.test(l) ? "ملحق الهبوط" : /relegation/i.test(l) ? "الهبوط" : /promotion play/i.test(l) ? "ملحق الصعود" : /promotion/i.test(l) ? "الصعود" : /playoff|play-off/i.test(l) ? "الملحق" : /next round|qualif/i.test(l) ? "التأهل" : /knockout/i.test(l) ? "الأدوار الإقصائية" : /caf champions/i.test(l) ? "دوري أبطال أفريقيا" : /confederation/i.test(l) ? "الكونفدرالية الأفريقية" : l; };
  U.legend = function (st) { var L2 = (st.legend || []).filter(function (x) { return x.color; }); if (!L2.length) return ""; return '<div class="legend">' + L2.map(function (x) { return '<span><i style="--z:' + esc(x.color) + '"></i>' + esc(ZONE_AR(x.label)) + "</span>"; }).join("") + "</div>"; };
  U.standings = function (st, o) {
    o = o || {}; if (!st || !st.groups || !st.groups.length) return '<div class="card">' + U.empty("ما في ترتيب منشور لهالبطولة.") + "</div>";
    var multi = st.groups.length > 1;
    return st.groups.map(function (g, gi) { return U.grp(multi ? esc(g.name ? U.groupName(g.name, gi) : U.groupName(null, gi)) : "", U.table(g.rows || [], o) + (gi === st.groups.length - 1 ? U.legend(st) : ""), { cls: multi ? "" : "tblg" }); }).join("");
  };
  U.rounds = function (fx) {   // {order: [round keys], by: {key: [matches]}, cur}
    var by = {}, order = []; (fx.matches || []).forEach(function (m) { var k = m.round != null ? String(m.round) : m.stage ? String(m.stage) : "—"; if (!by[k]) { by[k] = []; order.push(k); } by[k].push(m); });
    var sr = function (k) { if (/^\d+$/.test(k)) return 100 + +k; var s = String(k); return /prelim/i.test(s) ? 0 : /1\/64/.test(s) ? 300 : /1\/32/.test(s) ? 310 : /1\/16/.test(s) ? 320 : /1\/8/.test(s) ? 330 : /1\/4|quarter/i.test(s) ? 340 : /1\/2|semi/i.test(s) ? 350 : /3rd|bronze/i.test(s) ? 355 : /final/i.test(s) ? 360 : 200; };
    order.sort(function (a, b) { return sr(a) - sr(b); });
    var cur = fx.next_round && by[fx.next_round] ? String(fx.next_round) : (order.filter(function (k) { return by[k].some(function (m) { return m.status !== "finished"; }); })[0] || order[order.length - 1]);
    order.forEach(function (k) { by[k].sort(byKick); });
    return { order: order, by: by, cur: cur };
  };
  U.roundChip = function (k) { return /^\d+$/.test(String(k)) ? esc(k) : esc(U.stageAr(k)); };
  U.roundMatches = function (ms) {   // one round, grouped by day
    if (!ms || !ms.length) return '<div class="card">' + U.empty("ما في مباريات.") + "</div>";
    var byD = {}, ds = [];
    ms.forEach(function (m) { var k = m.date_tbd ? "tbd" : U.ymd(m.kickoff_uae || m.kickoff_utc); if (!byD[k]) { byD[k] = []; ds.push(k); } byD[k].push(m); });
    return ds.map(function (k) { var m0 = byD[k][0]; return U.grp(k === "tbd" ? "الموعد ما تحدد" : tm(m0.kickoff_uae || m0.kickoff_utc, "d"), byD[k].map(function (m) { return U.mrow(m); }).join("")); }).join("");
  };
  U.leaders = function (list, n, unit) {
    list = (list || []).slice(0, n || 10); if (!list.length) return U.empty("ما في أرقام للحين.");
    return list.map(function (r) { return '<a class="ld" href="' + L("p", r.player.id) + '"><span class="rk">' + (r.rank || "") + '</span><span class="rt"><b>' + U.pname(r.player) + "</b><small>" + U.crest(r.team) + U.tname(r.team) + (r.matches ? ' · <span class="num">' + r.matches + "</span> مباراة" : "") + '</small></span><span class="v">' + esc(r.value) + "</span>" + CHEV + "</a>"; }).join("");
  };
  U.champs = function (rows, names, o) {   // [[season, teamId|name ...]] -> bars of the most titles + the full list
    o = o || {}; var cnt = {}, first = {};
    rows.forEach(function (r) { if (!r[1]) return; cnt[r[1]] = (cnt[r[1]] || 0) + 1; });
    var top = Object.keys(cnt).sort(function (a, b) { return cnt[b] - cnt[a]; }).slice(0, o.top || 10), mx = top.length ? cnt[top[0]] : 1;
    return '<ol class="card bars">' + top.map(function (k) { var h = o.link && o.link(k), tag = h && h !== "#" ? "a" : "div"; return "<li><" + tag + ' class="bl"' + (tag === "a" ? ' href="' + esc(h) + '"' : "") + '><span class="bn"><span>' + esc(names(k)) + '</span></span><b class="num">' + cnt[k] + '</b><i style="--w:' + Math.round(cnt[k] / mx * 100) + '%"></i></' + tag + "></li>"; }).join("") + "</ol>";
  };

  // ------------------------------------------------------------------ team page
  var POSG = { keepers: "حراس المرمى", defenders: "الدفاع", midfielders: "الوسط", attackers: "الهجوم", coach: "المدرب" };
  U.squad = function (t) {
    var S = t.squad || []; if (!S.length) return '<div class="card">' + U.empty("ما عندنا قائمة اللاعبين.") + "</div>";
    return S.map(function (g) { return U.grp(POSG[g.group] || esc(g.group), (g.players || []).map(function (p) {
      var meta = [p.age ? '<span class="num">' + p.age + "</span> سنة" : "", t.national && p.club ? esc(cfg.tn[p.club_id] || p.club) : U.country(p.country), p.injury ? '<span style="color:var(--live)">مصاب</span>' : ""].filter(Boolean).join(" · ");
      return '<a class="row" href="' + L("p", p.id) + '"><span class="rt"><b>' + U.pname(p) + "</b>" + (meta ? "<small>" + meta + "</small>" : "") + '</span><span class="rv num">' + (p.number != null ? esc(p.number) : "") + "</span>" + CHEV + "</a>"; }).join("")); }).join("");
  };
  U.teamFixtures = function (t) {
    var now = cfg.now || Date.now(), F = (t.fixtures || []).filter(function (m) { return m && m.home && m.away; });
    var past = F.filter(function (m) { return m.status === "finished" || m.status === "awarded"; }).sort(function (a, b) { return byKick(b, a); });
    var live = F.filter(isLive), next = F.filter(function (m) { return m.status === "scheduled" || m.status === "postponed"; }).sort(byKick);
    return { past: past, next: next, live: live };
  };

  // ------------------------------------------------------------------ player
  var EA_FACE = ["سرعة", "تسديد", "تمرير", "مراوغة", "دفاع", "بدنية"], EA_GKF = ["ارتماء", "إمساك", "ركل", "ردة فعل", "سرعة", "تمركز"];
  var EA_ATTR = ["التسارع", "السرعة القصوى", "التمركز الهجومي", "إنهاء الهجمات", "قوة التسديد", "التسديد البعيد", "الكرات الطائرة", "ضربات الجزاء", "الرؤية", "العرضيات", "الركلات الحرة", "التمرير القصير", "التمرير الطويل", "الانحناء", "الرشاقة", "التوازن", "ردة الفعل", "التحكم بالكرة", "المراوغة", "الهدوء", "قطع الكرات", "الرأسيات", "الوعي الدفاعي", "الافتكاك", "التدخل الانزلاقي", "القفز", "التحمّل", "القوة", "الشراسة"];
  var EA_GROUPS = [["السرعة", 0, 2], ["التسديد", 2, 8], ["التمرير", 8, 14], ["المراوغة", 14, 20], ["الدفاع", 20, 25], ["البدنية", 25, 29]];
  var EA_PS = { "Aerial Fortress": "حصن الكرات العالية", Technical: "تقني", "Long Ball Pass": "الكرات الطويلة", Intercept: "قطع الكرات", Rapid: "سريع", "Precision Header": "الرأسية الدقيقة", "Finesse Shot": "التسديدة الملتفة", "Slide Tackle": "التدخل الانزلاقي", "Whipped Pass": "العرضية المقوّسة", "Quick Step": "الانطلاقة السريعة", "Incisive Pass": "التمريرة القاتلة", Anticipate: "قراءة اللعب", Relentless: "ما يتعب", Block: "صد التسديدات", Bruiser: "قوي في الالتحام", Jockey: "المراقبة اللصيقة", "Press Proven": "يتحمّل الضغط", "Long Throw": "رمية التماس الطويلة", Inventive: "مبتكر", "First Touch": "اللمسة الأولى", "Dead Ball": "الكرات الثابتة", Footwork: "حركة القدمين", "Low Driven Shot": "التسديدة الأرضية", Gamechanger: "صانع الفارق", Enforcer: "صاحب الهيبة", "Power Shot": "التسديدة القوية", "Cross Claimer": "صيّاد العرضيات", "Far Throw": "الرمية البعيدة", "Pinged Pass": "التمريرة المشدودة", "Tiki Taka": "تيكي تاكا", Acrobatic: "الأكروبات", "Chip Shot": "اللوب", Trickster: "الحيل", Deflector: "مبعد الكرات", "Rush Out": "الخروج من المرمى", "Far Reach": "الامتداد الطويل" };
  var POS_AR = { GK: "حارس", CB: "قلب دفاع", LB: "ظهير أيسر", RB: "ظهير أيمن", LWB: "ظهير أيسر", RWB: "ظهير أيمن", CDM: "وسط دفاعي", DM: "وسط دفاعي", CM: "وسط", LM: "وسط أيسر", RM: "وسط أيمن", CAM: "وسط هجومي", AM: "وسط هجومي", LW: "جناح أيسر", RW: "جناح أيمن", ST: "مهاجم", CF: "مهاجم" };
  U.posAr = function (p) { if (!p) return ""; var k = String(p).split(",")[0].trim(); return POS_AR[k.toUpperCase()] || ({ "Goalkeeper": "حارس مرمى", "Centre-Back": "قلب دفاع", "Center Back": "قلب دفاع", "Left-Back": "ظهير أيسر", "Right-Back": "ظهير أيمن", "Left Back": "ظهير أيسر", "Right Back": "ظهير أيمن", "Defensive Midfielder": "وسط دفاعي", "Central Midfielder": "وسط", "Attacking Midfielder": "وسط هجومي", "Left Midfielder": "وسط أيسر", "Right Midfielder": "وسط أيمن", "Left Winger": "جناح أيسر", "Right Winger": "جناح أيمن", "Striker": "مهاجم", "Centre-Forward": "مهاجم", "Center Forward": "مهاجم", "Second Striker": "مهاجم ثاني" })[k] || k; };
  U.eaCard = function (c, o) {
    if (!c || !c[0]) return ""; o = o || {};
    var gk = c[10], face = gk ? EA_GKF : EA_FACE, tier = c[0] >= 75 ? "" : c[0] >= 65 ? " silver" : " bronze";
    var fs = face.map(function (l, i) { return "<span>" + l + " <b>" + ((c[2] || [])[i] == null ? "—" : c[2][i]) + "</b></span>"; }).join("");
    var stars = function (n) { n = +n || 0; return '<span class="stars" aria-label="' + n + ' من 5">' + "★★★★★".slice(0, n) + "<i>" + "★★★★★".slice(n) + "</i></span>"; };
    var bars = (gk ? ["الارتماء", "الإمساك", "ركل الكرة", "ردة الفعل", "التمركز"].map(function (l, i) { return [l, (c[11] || [])[i]]; }) : EA_GROUPS.map(function (g) { var v = (c[6] || []).slice(g[1], g[2]).filter(function (x) { return x != null; }); return [g[0], v.length ? Math.round(v.reduce(function (a, b) { return a + b; }, 0) / v.length) : null]; }));
    var ps = (c[7] || []).map(function (p) { var plus = /\+$/.test(p), k = p.replace(/\+$/, ""); return '<span class="chip"' + (plus ? ' style="background:var(--accent-bg);color:var(--accent)"' : "") + ">" + esc(EA_PS[k] || k) + (plus ? "+" : "") + "</span>"; }).join("");
    var all = gk ? "" : EA_GROUPS.map(function (g) { return '<div class="gh"><h3>' + g[0] + '</h3></div><ul class="ea-b" style="padding:0 16px 8px">' + EA_ATTR.slice(g[1], g[2]).map(function (l, i) { var v = (c[6] || [])[g[1] + i]; return "<li><span>" + l + '</span><i style="--w:' + (+v || 0) + '%"></i><b>' + (v == null ? "—" : v) + "</b></li>"; }).join("") + "</ul>"; }).join("");
    return '<div class="ea"><div class="eac' + tier + '"><span class="ov">' + c[0] + '</span><span class="ps">' + esc(c[1] || "") + "</span>" + (o.photo ? '<div class="ph"><img src="' + o.photo + '" alt="" loading="lazy"></div>' : '<div class="ph"></div>') + '<div class="nm">' + esc(o.name || "") + '</div><div class="fs">' + fs + "</div></div>" +
      '<ul class="ea-b">' + bars.map(function (b) { return "<li><span>" + b[0] + '</span><i style="--w:' + (+b[1] || 0) + '%"></i><b>' + (b[1] == null ? "—" : b[1]) + "</b></li>"; }).join("") + "</ul></div>" +
      '<p class="ea-meta">المهارات ' + stars(c[3]) + " · القدم الضعيفة " + stars(c[4]) + (c[5] ? " · يلعب " + (c[5] === 2 ? "باليسرى" : "باليمنى") : "") + "</p>" + (ps ? '<div class="chips" style="justify-content:flex-start;padding:0 16px 14px;margin:0">' + ps + "</div>" : "") +
      (all ? '<details class="dz"><summary class="row" style="border-top:.5px solid var(--sep)"><span class="rt" style="color:var(--accent)">كل الخصائص</span>' + CHEV + "</summary>" + all + "</details>" : "");
  };
  // a player's transfer history (spec 2026-10-09 transfers, phase 2) from his FotMob career (profile.json career.senior.teams:
  // [id, name, start, end, apps, goals, assists, transferType], or player_seo's trimmed [id, name, start, end, apps, type key]):
  // one move per club change, newest first: [date, from id, from, to id, to, kind, fee]; kind free · loan · back (from a loan,
  // to the club before it) · fee · "" ; fees [[date, to id, EUR]] (Transfermarkt, the ledger) match the same club within 60 days.
  // A stint with no games under 60 days (an All-Star game) is no club
  var MKIND = { free_transfer: "free", on_loan: "loan" };
  U.careerMoves = function (teams, fees) {
    var key = function (r) { var t = r.length === 6 ? r[5] : r[7]; return t && typeof t === "object" ? t.localizationKey : t || ""; };
    var days = function (a, b) { return Math.abs(Date.parse(a) - Date.parse(b)) / 864e5; };
    var T = (teams || []).filter(function (r) { return r && r[2] && !(!+r[4] && r[3] && days(r[2], r[3]) < 60); })
      .slice().sort(function (a, b) { return a[2] < b[2] ? -1 : a[2] > b[2] ? 1 : 0; });
    var out = [];
    for (var i = 1; i < T.length; i++) {
      var p = T[i - 1], c = T[i], k = MKIND[key(c)] || "", fee = null, prev = out[out.length - 1];
      if (String(p[0]) === String(c[0])) continue;
      if (prev && prev[5] === "loan" && String(prev[1]) === String(c[0])) k = "back";
      (fees || []).forEach(function (f) { if (fee == null && f && String(f[1]) === String(c[0]) && days(f[0], c[2]) <= 60 && f[2] != null) fee = f[2]; });
      if (fee === 0) { fee = null; if (!k) k = "free"; }
      if (fee && k !== "loan") k = "fee";
      out.push([c[2], p[0], p[1], c[0], c[1], k, fee]);
    }
    return out.reverse();
  };
  U.MOVE_AR = { free: "انتقال حر", loan: "إعارة", back: "رجع من الإعارة" };
  U.eur = function (v) { return v == null ? "—" : v === 0 ? "مجاناً" : v >= 1e6 ? '<span class="num">€' + (Math.round(v / 1e5) / 10) + "</span> مليون" : '<span class="num">€' + Math.round(v / 1e3) + "</span> ألف"; };

  // ------------------------------------------------------------------ news
  var KIND = { transfer: "انتقالات", injury: "إصابة", presser: "مؤتمر صحفي", statement: "تصريحات", official: "رسمي", match: "مباراة", other: "خبر" };
  var STAGE = { rumour: "إشاعة", talks: "مفاوضات", agreed: "اتفاق", here_we_go: "Here we go", official: "رسمي" };
  U.KIND = KIND;
  // «مؤشر صحة الإشاعة» (owner's second list 4): the journal's score for a transfer story (news/run.py credibility), as a bar and a word
  var CBEST = { official: "منها حساب رسمي", journalist: "منها صحفي معروف بدقته", paper: "منها صحف معروفة", aggregator: "مواقع تنقل عن غيرها بس" };
  U.cred = function (s) {
    var c = s.cred; if (!c || s.kind !== "transfer") return "";
    var w = s.stage === "official" ? "مؤكدة" : c.v >= 75 ? "قوية" : c.v >= 50 ? "متوسطة" : "ضعيفة", lv = c.v >= 75 ? "hi" : c.v >= 50 ? "md" : "lo";
    return '<p class="cred ' + lv + '"><span class="crb" aria-hidden="true"><i style="width:' + Math.max(6, Math.min(100, +c.v || 0)) + '%"></i></span>' +
      "<span>" + (s.stage === "official" ? "الصفقة " : "صحة الإشاعة: ") + "<b>" + w + "</b><small> · " + (c.n === 1 ? "مصدر واحد" : c.n === 2 ? "مصدرين" : c.n + (c.n % 100 >= 3 && c.n % 100 <= 10 ? " مصادر" : " مصدر")) + "، " + (CBEST[c.best] || "") + "</small></span></p>";
  };
  U.newsCard = function (s) {
    var src = s.sources || [], first = src[0] || {}, ar = s.title_lang === "ar", tag = KIND[s.kind] || "خبر";
    var ents = (s.entities || []).slice(0, 4).map(function (e) { var href = e.kind === "team" ? L("t", e.id) : e.kind === "player" ? L("p", e.id) : null; return href ? '<a class="chip" href="' + href + '">' + (e.kind === "team" ? U.crest({ id: e.id }).replace('class="cr"', 'class="lg"') : "") + esc(e.name) + "</a>" : '<span class="chip">' + esc(e.name) + "</span>"; }).join("");
    return '<article class="nw"><p class="nw-k"><span class="tg ' + esc(s.kind) + '">' + tag + (s.kind === "transfer" && s.stage ? " · " + esc(STAGE[s.stage] || s.stage) : "") + "</span>" + (s.here_we_go ? '<span class="hwg">Here we go</span>' : "") + '<time data-u="' + esc(s.last_at || "") + '" data-f="ago">' + U.ago(s.last_at) + "</time></p>" +
      "<h3" + (ar ? "" : ' dir="auto"') + '><a href="' + esc(first.url || "#") + '" rel="noopener" target="_blank">' + esc(s.title) + "</a></h3>" + (s.summary ? '<p class="sm">' + esc(s.summary) + "</p>" : "") + (ents ? '<div class="ents">' + ents + "</div>" : "") +
      U.cred(s) + '<p class="src">' + (src.length > 1 ? src.length + " مصادر: " : "المصدر: ") + src.slice(0, 3).map(function (x) { return esc(x.name); }).join("، ") + "</p></article>";
  };
  U.vids = function (list) { return '<div class="vids">' + list.map(function (v) { return '<a class="vid" href="' + esc(v.url) + '" rel="noopener" target="_blank">' + (v.image ? '<img src="' + esc(v.image) + '" alt="" loading="lazy" width="220" height="124">' : "") + '<span dir="auto">' + esc(v.title) + "</span><small>" + esc(v.channel || "") + (v.platform === "x" ? " على X" : " على يوتيوب") + " · " + U.ago(v.at) + "</small></a>"; }).join("") + "</div>"; };

  // ------------------------------------------------------------------ shell pieces (nav bar, tab bar, sheets)
  var TABS = [["today", "/", "اليوم", "today"], ["comps", "/competitions/", "البطولات", "comps"], ["news", "/news/", "الأخبار", "news"], ["mine", "/mine/", "فريقي", "star"], ["more", "/more/", "المزيد", "more"]];
  U.tabbar = function (cur) { return '<nav class="tabbar" aria-label="الأقسام">' + TABS.map(function (t) { return '<a href="' + cfg.base + t[1] + '"' + (t[0] === cur ? ' aria-current="page"' : "") + ">" + I(t[3], "", t[0] === cur ? 2.1 : 1.7) + "<span>" + t[2] + "</span></a>"; }).join("") + "</nav>"; };
  U.nav = function (o) {   // {back: href|true, title, trail: html, brand}
    o = o || {};
    var lead = o.back ? '<a class="nb back" href="' + esc(o.back === true ? cfg.base + "/" : o.back) + '" data-back>' + I("back", "", 2.4) + "<span>" + esc(o.backLabel || "رجوع") + "</span></a>" : o.brand ? '<a class="brand" href="' + cfg.base + '/" aria-label="تيفو"><span class="mark" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></span>تيفو</a>' : "";
    return '<header class="nav' + (o.solid ? " solid stuck" : "") + '" id="nav"><div class="nav-in"><div class="nav-lead">' + lead + '</div><div class="nav-title" id="navt">' + (o.title || "") + '</div><div class="nav-trail">' + (o.trail || "") + "</div></div></header>";
  };
  U.navBtn = function (icon, label, attrs) { return '<button type="button" class="nb icon" aria-label="' + esc(label) + '"' + (attrs || "") + ">" + I(icon, "", 2) + "</button>"; };
  U.navLink = function (icon, label, href) { return '<a class="nb icon" aria-label="' + esc(label) + '" href="' + href + '">' + I(icon, "", 2) + "</a>"; };
  U.sheet = function (id, title, body) { return '<dialog class="sheet" id="' + id + '" aria-labelledby="' + id + '-t"><div class="sh-grab" aria-hidden="true"></div><header class="sh-hd"><h2 id="' + id + '-t" tabindex="-1" autofocus>' + title + '</h2><button type="button" class="sh-x" data-close aria-label="سكّر">' + I("close", "", 2.6) + '</button></header><div class="sh-bd">' + body + "</div></dialog>"; };
  // the footer: the page's own note, then the site's (production sets cfg.footer: the audit badge, «آخر تحديث», the sitemap links)
  U.foot = function (extra) { return '<footer class="foot">' + (extra || "") + (cfg.footer || '<p>تيفو بدون مراهنات. البيانات من FotMob ورابطة المحترفين الإماراتية.</p><p>من استوديو <a href="https://elyoxe.com/">Elyoxe</a></p>') + "</footer>"; };

  if (typeof module !== "undefined" && module.exports) module.exports = U; else root.U5 = U;
})(typeof window !== "undefined" ? window : this);

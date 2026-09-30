/* تيفو client: refreshes the prerendered blocks from /v1 JSON, polls live data every 20 s while something is live,
   and keeps «فريقي» (my team) in localStorage. The page type and ids come from <body data-page data-id data-comp>. */
(function(){
  "use strict";
  var R = window.TR, B = document.body, PAGE = B.dataset.page, ID = B.dataset.id, V = "/v1/";
  var $ = function(s){ return document.querySelector(s); };
  // 347: sampled error beacon (1 in 5 page views, at most 3 reports): message, file path and line only
  (function(){ if (Math.random() > 0.2) return; var n = 0; function send(m, s, l, c){ if (n++ >= 3) return; try { fetch("/api/tifo/err", { method:"POST", keepalive:true, headers:{ "content-type":"application/json" }, body:JSON.stringify({ m:String(m || "").slice(0, 300), s:s || "", l:l || null, c:c || null, p:location.pathname, v:(document.querySelector('script[src*="/assets/app."]') || {}).src ? document.querySelector('script[src*="/assets/app."]').src.split("app.")[1].slice(0, 10) : "" }) }).catch(function(){}); } catch (e){} }
    window.addEventListener("error", function(e){ if (e.filename && e.filename.indexOf(location.origin) !== 0) return; send(e.message, e.filename, e.lineno, e.colno); });
    window.addEventListener("unhandledrejection", function(e){ var r = e.reason; send(r && r.message ? r.message : r, r && r.stack ? String(r.stack).split("\n")[1] : "", null, null); }); })();
  function get(p){ return fetch(V + p, { cache:"no-cache" }).then(function(r){ if (!r.ok) throw new Error(r.status); return r.json(); }); }
  function mine(){ try { return +localStorage.getItem("tifo.mine") || null; } catch (e){ return null; } }
  function setMine(id, name){ try { if (id) { localStorage.setItem("tifo.mine", id); localStorage.setItem("tifo.mine.name", name || ""); } else { localStorage.removeItem("tifo.mine"); } } catch (e){} }
  function uaeToday(off){ var d = new Date(Date.now() + 4 * 3600e3 + (off || 0) * 864e5); return d.toISOString().slice(0, 10); }
  // QA 23: «اليوم» is the visitor's own calendar day; the UAE day files it overlaps are fetched and filtered to it
  function tzOff(){ try { var tz = R.TZ || "Asia/Dubai", n = new Date(); return Math.round((Date.parse(n.toLocaleString("en-US", { timeZone:tz })) - Date.parse(n.toLocaleString("en-US", { timeZone:"UTC" }))) / 6e4); } catch (e){ return 240; } }
  function localDay(off){ try { return new Date(Date.now() + (off || 0) * 864e5).toLocaleDateString("en-CA", { timeZone:R.TZ || "Asia/Dubai" }); } catch (e){ return uaeToday(off); } }
  function dayFiles(off){ var L = localDay(off), o = tzOff(), step = function(d, k){ var t = new Date(d + "T12:00:00Z"); t.setUTCDate(t.getUTCDate() + k); return t.toISOString().slice(0, 10); };
    var files = [L]; if (o < 240) files.push(step(L, 1)); else if (o > 240) files.unshift(step(L, -1));
    return Promise.all(files.map(function(d, i){ return get("day/" + d.replace(/-/g, "") + ".json").catch(function(e){ return d === L && off === 0 && files.length === 1 ? Promise.reject(e) : { matches:[] }; }); })).then(function(ds){
      var seen = {}, all = []; ds.forEach(function(x){ (x.matches || []).forEach(function(m){ if (!seen[m.id]){ seen[m.id] = 1; all.push(m); } }); });
      return { generated:ds[0].generated, matches:files.length === 1 ? all : all.filter(function(m){ var k = m.kickoff_uae || m.kickoff_utc; return !k || k.length <= 10 || m.time_tbd ? (m.kickoff_uae || "").slice(0, 10) === L : R.ymd(k) === L; }) }; }); }
  function set(sel, html){ var el = $(sel); if (el && el._h !== html){ el._h = html; el.innerHTML = html; R.localize(el); } }   // W2.11: unchanged HTML is not re-rendered
  // ---- country (203, 199): time zone + what comes first; guessed from the browser's time zone, changeable in the header
  function country(){ try { var c = localStorage.getItem("tifo.country"); if (c) return c; } catch (e){} var tz = ""; try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone; } catch (e){} var hit = R.COUNTRIES.filter(function(c){ return c[2] === tz; })[0]; return hit ? hit[0] : "xx"; }
  function applyCountry(){ var c = country(), row = R.COUNTRIES.filter(function(x){ return x[0] === c; })[0]; try { R.TZ = row ? row[2] : Intl.DateTimeFormat().resolvedOptions().timeZone; } catch (e){ R.TZ = "Asia/Dubai"; }
    var b = $("#ctry"); if (b) b.textContent = "بلدك: " + (row ? row[1] : "—") + " · غيّر"; R.localize(document); }
  applyCountry();
  // QA 2026-09-28: the country picker and search are real sheets (history entry, scrim, inert page, «سكّر»); picking a country closes
  // its sheet through the sheet system, so the page behind is never left inert
  var cb = $("#ctry"); if (cb) cb.onclick = function(){ var sh = $("#ctrysh"), box = $("#ctrybody"); if (!sh || !box || !window.TifoSheet) return; var cur = country();
    box.innerHTML = '<p class="small">اختار بلدك: المواعيد تطلع بتوقيته، ومبارياته أول شي.</p><div class="cgrid">' + R.COUNTRIES.map(function(c){ return '<button type="button" data-c="' + c[0] + '"' + (c[0] === cur ? ' aria-pressed="true"' : "") + ">" + c[1] + "</button>"; }).join("") + '<button type="button" data-c="xx"' + (cur === "xx" ? ' aria-pressed="true"' : "") + ">برا الوطن العربي</button></div>";
    box.onclick = function(e){ var t = e.target.closest("button[data-c]"); if (!t) return; try { localStorage.setItem("tifo.country", t.dataset.c); } catch (x){} window.TifoSheet.close("now"); applyCountry(); document.dispatchEvent(new CustomEvent("tifo:country", { detail:{ cc:t.dataset.c } })); if (PAGE === "home") home(); };
    window.TifoSheet.open(sh, cb); };
  function natHref(iso){ var id = (window.NAT || {})[String(iso).toUpperCase()]; return id ? "/t/" + id + "/" : "/national/" + String(iso).toLowerCase() + "/"; }   // W4.3
  // ---- search (167): one small index, loaded on first open; Arabic normalised (أ إ آ ا، ة ه، ى ي) and Latin both matched
  var SIDX = null, sb0 = $("#srch");
  // 363: forgiving search — hamza / ta marbuta / alef maqsura folded, tatweel and doubled letters collapsed (مبخووت), club nicknames,
  // and one-or-two-letter typos matched word by word
  function norm(t){ return String(t || "").toLowerCase().replace(/[أإآٱ]/g, "ا").replace(/ؤ/g, "و").replace(/ئ/g, "ي").replace(/ء/g, "").replace(/ة/g, "ه").replace(/ى/g, "ي").replace(/ـ/g, "").replace(/[\u064b-\u0652]/g, "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/(.)\1+/g, "$1"); }
  var NICK = { "الزعيم":["العين", "الهلال"], "العيناوي":["العين"], "الامبراطور":["الوصل"], "الفهود":["الجزيره"], "فخر ابوظبي":["الجزيره"], "العنابي":["الوحده"], "الملك":["الشارقه"], "الفرسان":["شباب الاهلي"], "العميد":["النصر", "الاتحاد"], "النموذجي":["الاتحاد"], "الملكي":["ريال مدريد"], "البلوز":["تشيلسي"], "الشياطين الحمر":["مانشستر يونايتد"], "السيتي":["مانشستر سيتي"], "البارسا":["برشلونه"], "الاحمر":["الاهلي"], "الابيض":["الزمالك", "الامارات"], "الاخضر":["السعوديه"], "الاحمر العنابي":["البحرين"], "الفراعنه":["مصر"], "اسود الاطلس":["المغرب"], "النشامي":["الاردن"],
    // W3.11: pan-Arab nicknames (keys are folded by norm() below, so they can be written normally)
    "العالمي":["النصر"], "الراقي":["الأهلي"], "النمور":["الاتحاد"], "الليث":["الشباب"], "سكري القصيم":["التعاون"], "الرهيب":["الريان"], "السداوي":["السد"],
    "القلعة الحمراء":["الأهلي", "الوداد"], "الفارس الأبيض":["الزمالك"], "الدراويش":["الإسماعيلي"], "المكشخة":["الترجي"], "جوهرة الساحل":["النجم الساحلي"], "النسور الخضر":["الرجاء"], "الزعيم السداوي":["السد"],
    "الأخضر السعودي":["السعودية"], "الصقور الخضر":["السعودية"], "الأزرق":["الكويت"], "أسود الرافدين":["العراق"], "نسور قرطاج":["تونس"], "محاربو الصحراء":["الجزائر"], "الخضر":["الجزائر"],
    "الفدائي":["فلسطين"], "نسور قاسيون":["سوريا"], "رجال الأرز":["لبنان"], "فرسان المتوسط":["ليبيا"], "صقور الجديان":["السودان"], "العنابي القطري":["قطر"] };
  (function(){ var n = {}; Object.keys(NICK).forEach(function(k){ var nk = norm(k); n[nk] = (n[nk] || []).concat(NICK[k]); }); NICK = n; if (n["الزعيم"]) n["الزعيم"].push("السد"); if (n["العميد"]) n["العميد"].push("مولودية الجزائر"); if (n["العنابي"]) n["العنابي"].push("قطر"); })();
  function lev(a, b, max){ if (Math.abs(a.length - b.length) > max) return max + 1; var p = [], i, j; for (j = 0; j <= b.length; j++) p[j] = j; for (i = 1; i <= a.length; i++){ var c = [i], lo = i; for (j = 1; j <= b.length; j++){ c[j] = Math.min(p[j] + 1, c[j - 1] + 1, p[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)); if (c[j] < lo) lo = c[j]; } if (lo > max) return max + 1; p = c; } return p[b.length]; }
  function fuzzy(item, v){ var max = v.length >= 7 ? 2 : 1; return (item.na + " " + item.nl).split(/\s+/).some(function(w){ return w.length >= 3 && (lev(w, v, max) <= max || lev(w.replace(/^ال/, ""), v.replace(/^ال/, ""), max) <= max); }); }
  if (sb0) sb0.onclick = function(){ var sh = $("#srchsh"), box = $("#srchbox"); if (!sh || !box || !window.TifoSheet) return; if (!sh.hidden){ window.TifoSheet.close(); return; }
    // W2.9: search is a sheet: a real search form, Enter opens the first hit, a failed index load says so
    box.innerHTML = '<form role="search" class="sfrm"><input id="sq" type="search" enterkeyhint="search" placeholder="نادي، لاعب، مباراة، مدرب…" aria-label="بحث" autocomplete="off"></form><div id="sr"></div>'; window.TifoSheet.open(sh, sb0);
    box.querySelector("form").onsubmit = function(e){ e.preventDefault(); var a = box.querySelector("#sr a"); if (a) location.href = a.href; };
    var q = $("#sq"); setTimeout(function(){ q.focus(); }, 60);
    // W3.11: empty state (فريقي chips · مباشر الحين · آخر بحث), a subline on every hit, the visitor's country breaks name ties
    function recent(){ try { return JSON.parse(localStorage.getItem("tifo.sq") || "[]"); } catch (e){ return []; } }
    function remember(v){ v = String(v || "").trim(); if (v.length < 2) return; var r = recent().filter(function(x){ return x !== v; }); r.unshift(v); try { localStorage.setItem("tifo.sq", JSON.stringify(r.slice(0, 5))); } catch (e){} }
    function empty(){ var ch = favs().filter(function(x){ return x.t === "team" && x.n; }).slice(0, 6).map(function(x){ return '<a class="sqc" href="/t/' + x.id + '/">' + R.esc(x.n) + "</a>"; }).join(""), rc = recent().map(function(x){ return '<button type="button" class="sqc" data-q="' + R.esc(x) + '">' + R.esc(x) + "</button>"; }).join("");
      set("#sr", (ch ? '<p class="sre-h">فريقي</p><div class="sre">' + ch + "</div>" : "") + '<div class="sre"><a class="sqc" href="/#matches">مباشر الحين</a><a class="sqc" href="/today/">مباريات اليوم</a></div>' + (rc ? '<p class="sre-h">آخر بحث</p><div class="sre">' + rc + "</div>" : "")); }
    box.addEventListener("click", function(e){ var c = e.target.closest("[data-q]"); if (c){ q.value = c.dataset.q; q.oninput && q.oninput(); q.focus(); return; } if (e.target.closest("#sr a")) remember(q.value); });
    box.querySelector("form").addEventListener("submit", function(){ remember(q.value); });
    empty();
    (SIDX ? Promise.resolve(SIDX) : fetch("/assets/search." + sb0.dataset.v + ".json").then(function(r){ return r.json(); }).then(function(x){ var S = x.s || [], L = x.i || x; SIDX = L.map(function(i){ return { t:i[0], ar:i[1], la:i[2], u:i[3], sub:(typeof i[4] === "number" ? S[i[4]] : i[4]) || "", cc:i[5] || "", ko:i[6] || "", na:norm(i[1]), nl:norm(i[2]) }; }); return SIDX; })).then(function(){
      var TY = { c:"بطولة", t:"نادي", p:"لاعب", r:"صفحة", m:"مباراة", k:"مدرب", f:"حكم" }, O = { c:0, t:1, m:2, k:3, f:4, r:5, p:6 }, CC = country();
      q.oninput = function(){ var v = norm(q.value.trim()); if (v.length < 2){ empty(); return; }
        // QA 57/72: nicknames expand to clubs and national teams only; a multi-word query matches items that contain every word
        // («العين الوحدة» finds «العين ضد الوحدة»), and single words still match anywhere
        var nk = (NICK[v] || []).map(norm), toks = v.split(/\s+/).filter(function(w){ return w.length >= 2; }),
            has = function(i){ var s = i.na + " " + i.nl; if (s.indexOf(v) >= 0) return true; if (nk.length && (i.t === "t") && nk.some(function(x){ return i.na.indexOf(x) >= 0; })) return true; return toks.length > 1 && toks.every(function(w){ return s.indexOf(w) >= 0 || s.indexOf(w.replace(/^ال/, "")) >= 0; }); }, qs = [v].concat(nk);
        var hits = SIDX.filter(has); if (hits.length < 5 && v.length >= 4 && v.indexOf(" ") < 0) hits = hits.concat(SIDX.filter(function(i){ return !has(i) && fuzzy(i, v); }).slice(0, 12));
        var pre = function(i){ return qs.some(function(x){ return i.na.indexOf(x) === 0 || i.nl.indexOf(x) === 0; }) ? 0 : 1; }, now = Date.now();
        hits = hits.filter(function(i){ return i.t !== "m" || !i.ko || Date.parse(i.ko) > now - 3 * 3600e3; })
          .sort(function(a, b){ return pre(a) - pre(b) || O[a.t] - O[b.t] || (a.cc === CC ? 0 : 1) - (b.cc === CC ? 0 : 1) || (a.t === "m" ? Date.parse(a.ko) - Date.parse(b.ko) : 0); }).slice(0, 20);
        set("#sr", hits.length ? "<ul>" + hits.map(function(i){ var sub = i.t === "m" && i.ko ? (i.sub ? R.esc(i.sub) + " · " : "") + R.td(i.ko) + " " + R.tt(i.ko) : R.esc(i.sub);
          return '<li><a href="' + i.u + '"><span class="srn">' + R.esc(i.ar || i.la) + (i.ar && i.la && i.t !== "m" ? ' <span class="muted small lat">' + R.esc(i.la) + "</span>" : "") + '</span><span class="muted small srs">' + (i.t === "t" && i.sub === "منتخب" ? "منتخب" : TY[i.t] + (sub ? " · " + sub : "")) + "</span></a></li>"; }).join("") + "</ul>" : '<p class="muted small">ما لقينا شي.</p>');
        var sr = $("#sr"); if (sr && R.localize) R.localize(sr); };
    }).catch(function(){ set("#sr", '<p class="muted small">ما قدرنا نحمّل البحث، تأكد من النت.</p>'); }); };

  // ---- favourites (179): several clubs and players; the first club stays «فريقي»
  function favs(){ try { return JSON.parse(localStorage.getItem("tifo.favs") || "[]"); } catch (e){ return []; } }
  function setFavs(f){ try { localStorage.setItem("tifo.favs", JSON.stringify(f)); } catch (e){} }
  (function migrate(){ var m = mine(), f = favs(); if (m && !f.some(function(x){ return x.t === "team" && x.id === m; })){ f.unshift({ t:"team", id:m, n:(localStorage.getItem("tifo.mine.name") || "") }); setFavs(f); } })();
  function stamp(g){ var el = $("#updated"); if (el && g){ var tz = R.TZ || "Asia/Dubai", d = new Date(g), day = function(x){ return x.toLocaleDateString("en-CA", { timeZone:tz }); }, t = d.toLocaleTimeString("ar-AE-u-nu-latn", { hour:"2-digit", minute:"2-digit", hourCycle:"h23", timeZone:tz });
      el.textContent = "آخر تحديث " + (day(d) === day(new Date()) ? "" : day(d) === day(new Date(Date.now() - 864e5)) ? "أمس " : d.toLocaleDateString("ar-AE-u-nu-latn", { day:"numeric", month:"long", timeZone:tz }) + " ") + t; }   /* QA 86 */ document.documentElement.classList.remove("stale"); document.dispatchEvent(new CustomEvent("tifo:fresh", { detail:g })); }
  // W1.1d: a failed refresh never blanks what the page already shows; it says so and retries (20 -> 40 -> 60 s)
  var fails = 0; function retry(fn){ fails++; var n = $("#netnote"); if (!n){ n = document.createElement("p"); n.id = "netnote"; n.className = "netnote"; (document.querySelector(".hero-in") || document.querySelector("main")).appendChild(n); } n.textContent = "ما قدرنا نحدّث، نحاول مرة ثانية…"; poll(fn, Math.min(60e3, 20e3 * fails)); }
  function ok(){ fails = 0; var n = $("#netnote"); if (n) n.remove(); }
  function tabs(root){ (root || document).querySelectorAll(".tabs[data-tabs]").forEach(function(t){ t.addEventListener("click", function(e){ var b = e.target.closest("button[data-t]"); if (!b) return; t.querySelectorAll("button").forEach(function(x){ x.setAttribute("aria-selected", x === b ? "true" : "false"); }); document.querySelectorAll("[data-pane]").forEach(function(p){ if (p.dataset.group !== t.dataset.tabs) return; p.hidden = p.dataset.pane !== b.dataset.t;
        var lz = !p.hidden && p.querySelector(":scope > template.lazyp"); if (lz){ p.replaceChild(lz.content.cloneNode(true), lz); if (R.localize) R.localize(p); } });   /* W4.7: a lazy pane is stamped on first open */
      try { history.replaceState(null, "", "#" + b.dataset.t); } catch (e){} }); var h = location.hash.slice(1), b = h && t.querySelector('button[data-t="' + h + '"]'); if (b) b.click(); }); }
  var timer = null; function poll(fn, ms){ clearTimeout(timer); timer = setTimeout(function(){ if (document.hidden){ poll(fn, ms); return; } fn(); }, ms); }
  document.addEventListener("visibilitychange", function(){ if (!document.hidden && (timer || (PAGE === "match" && nearKick(MD)))){ clearTimeout(timer); run(); } });

  var INDEX = null;
  function index(){ return INDEX ? Promise.resolve(INDEX) : get("index.json").then(function(x){ INDEX = x; return x; }); }

  // ---- home: day list + live polling + my team
  var dayOff = 0;
  function home(){
    return Promise.all([index(), dayFiles(dayOff), get("live.json").catch(function(){ return { matches:[] }; })]).then(function(r){
      ok(); var idx = r[0], day = r[1], live = r[2], by = {}; (live.matches || []).forEach(function(m){ by[m.id] = m; });
      var ms = (day.matches || []).map(function(m){ return by[m.id] || m; });
      if (freeOnly() && BCD) ms = ms.filter(function(m){ return freeIn(String(m.comp)); });
      if (arabOnly()){ var AT = window.ARABT || {}, ar = {}; R.COUNTRIES.forEach(function(c){ ar[c[0]] = 1; }); var cc = {}; (idx.competitions || []).forEach(function(c){ cc[c.id] = R.compCountry(c); }); ms = ms.filter(function(m){ return ar[cc[m.comp]] || AT[m.home.id] || AT[m.away.id]; }); }
      set("#daytitle", R.dayNav(localDay(dayOff), localDay(0)));
      var natIds = []; try { natIds = JSON.parse(localStorage.getItem("tifo.natids") || "{}")[country()] || []; } catch (e){}
      set("#day", R.dayList(ms, idx, { mine:mine(), country:country(), natIds:natIds, empty:"ما في مباريات في هاليوم." })); document.dispatchEvent(new CustomEvent("tifo:day", { detail:{ ms:ms, idx:idx, live:live, off:dayOff } }));
      var lv = (live.matches || []); set("#livecount", lv.length ? '<i class="cardflip"></i>' + (R.n ? R.n(lv.length, ["مباراة وحدة مباشرة الحين", "مباراتين مباشرة الحين", "مباريات مباشرة الحين", "مباراة مباشرة الحين"]) : lv.length + " مباريات مباشرة الحين") : "");
      if (dayOff === 0) stand(R.featured(ms));
      stamp(live.generated || day.generated);
      myCard(idx, dayOff === 0 ? ms : [], live); countdown();
      poll(home, lv.length || ms.some(function(m){ var t = Date.parse(m.kickoff_utc); return m.status === "scheduled" && t - Date.now() < 15 * 60e3 && t > Date.now() - 3 * 3600e3; }) ? 20e3 : 120e3);
    }).catch(function(){ retry(home); });
  }
  var ST = null;
  function stand(m){
    var box = $("#stand"); if (!box || !m || !window.TifoStand) return;
    set("#standcap", R.standCap(m)); var k = $("#standkick"); if (k) k.textContent = R.kick ? R.kick(m) : (R.isLive(m) ? "مباشر الحين" : m.status === "finished" ? "انتهت" : "مباراة اليوم");
    if (!ST) ST = window.TifoStand.mount(box.querySelector("canvas"));
    ST.set(m);
  }
  // W3.7: «فريقك» follows you (it absorbed #since). Per team: a live match first; else a result from the last 24 h after full time,
  // with «ليش هالنتيجة؟» and «صورة للستوري», then the next match if it's within a day; else the next match. «يديد» marks a result that
  // finished since the last visit (the visit that started this session). The visitor's national team joins when it has something today.
  // No favourites: the national team and the league of the visitor's country, above the crest grid.
  var LASTV = (function(){ var l = 0; try { var s = sessionStorage.getItem("tifo.lv"); if (s != null) return +s; l = +localStorage.getItem("tifo.lastvisit") || 0; sessionStorage.setItem("tifo.lv", String(l)); localStorage.setItem("tifo.lastvisit", Date.now()); } catch (e){} return l; })();
  var TN = {}, RKD = {}, PKC = null;   // rank moves are worked out once per page load (the home poll re-renders this card every 20 s)
  function tn(id){ return TN[id] || (TN[id] = fetch("/tn/" + id + ".json").then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; })); }
  function myCard(idx, ms, live){
    var el = $("#mine"); if (!el) return; var teams = favs().filter(function(x){ return x.t === "team"; }).slice(0, 6), fb = !teams.length, cc = country(), nid = (window.NAT || {})[cc];
    if (nid && !teams.some(function(x){ return x.id === nid; })) teams.push({ id:nid, nat:1 });
    if (!teams.length){ el.innerHTML = '<div class="mine-card"><div class="h">مفضلتي</div><p class="small" style="margin:0">افتح صفحة أي نادي واضغط «هذا فريقي»، وضيف كم فريق تبا، ومبارياته تطلع لك أول شي هنا.</p></div>'; return; }
    var by = {}; (ms || []).concat((live && live.matches) || []).forEach(function(m){ by[m.id] = Object.assign({}, by[m.id] || {}, m); });
    Promise.all(teams.map(function(x){ return tn(x.id); }).concat([PKC || (PKC = PK.catchUp())])).then(function(rs){
      rs = rs.slice(0, teams.length); var now = Date.now(), rows = [];
      rs.forEach(function(t, i){ if (!t) return; var nat = teams[i].nat, seen = {}, c = [];
        [t.last, t.next].concat((ms || []).filter(function(m){ return m.home.id === t.id || m.away.id === t.id; })).forEach(function(m){ if (!m || seen[m.id]) return; seen[m.id] = 1; c.push(by[m.id] ? Object.assign({}, m, by[m.id]) : m); });
        var ko = function(m){ return Date.parse(m.kickoff_utc) || 0; };
        var lv = c.filter(R.isLive)[0], res = c.filter(function(m){ return m.status === "finished" && now - ko(m) < 26 * 3600e3; }).sort(function(a, b){ return ko(b) - ko(a); })[0],
            nx = c.filter(function(m){ return m.status === "scheduled" && ko(m) > now - 3 * 3600e3; }).sort(function(a, b){ return ko(a) - ko(b); })[0];
        var body = "", nw = false;
        if (lv) body = R.matchRow(lv, { date:false });
        else if (res){ nw = LASTV > 0 && ko(res) + 2 * 3600e3 > LASTV;
          body = R.matchRow(res, { date:true }) + '<p class="mlinks">' + (res.why ? '<a href="/m/' + res.id + '/">ليش هالنتيجة؟</a>' : "") + '<a href="/m/' + res.id + '/#story">صورة للستوري</a></p>' + (nx && ko(nx) - now < 24 * 3600e3 ? R.matchRow(nx, { date:true }) : ""); }
        else if (nat && !fb) return;   // the national team only rides along when it has something now
        else body = nx ? R.matchRow(nx, { date:true }) : t.last ? R.matchRow(t.last, { date:true }) : "";
        if (!body) return;
        if (!(t.id in RKD)){ var prev = null; RKD[t.id] = ""; try { prev = JSON.parse(localStorage.getItem("tifo.rank." + t.id) || "null"); } catch (e){}
          if (t.table){ if (prev && prev.rank !== t.table.rank) RKD[t.id] = '<p class="rkch">' + (t.table.rank < prev.rank ? "طلع" : "نزل") + " من المركز " + prev.rank + " للمركز " + t.table.rank + " في " + R.esc(t.table.comp_ar) + "</p>"; try { localStorage.setItem("tifo.rank." + t.id, JSON.stringify(t.table)); } catch (e){} } }
        var rk = RKD[t.id];
        rows.push({ k:lv ? 0 : res ? 1 : 2, i:i, h:'<div class="' + (nat ? "sugrow" : "favrow") + (nw ? " nw" : "") + '"><a class="h" href="/t/' + t.id + '/">' + R.logo(t) + " " + R.tname(t) + (i === 0 && !fb ? " <small>فريقي</small>" : nat ? ' <span class="tg">منتخب بلدك</span>' : "") + (nw ? ' <i class="nwd">يديد</i>' : "") + "</a>" + body + rk + "</div>" }); });
      // the league of the visitor's country, for a first visit with no favourites
      if (fb){ var L = (window.CL || {})[cc], comp = L && (idx.competitions || []).filter(function(c){ return c.key === L[0]; })[0];
        if (comp){ var lm = (ms || []).filter(function(m){ return m.comp === comp.id; }).sort(function(a, b){ return R.isLive(b) - R.isLive(a); })[0];
          rows.push({ k:3, i:99, h:'<div class="sugrow"><a class="h" href="/c/' + comp.key + '/">' + '<img class="logo" src="/lg/' + comp.id + '.png" alt="" loading="lazy" onerror="this.remove()">' + " " + R.esc(comp.name_ar) + ' <span class="tg">دوري بلدك</span></a>' + (lm ? R.matchRow(by[lm.id] || lm, { date:false }) : '<p class="small muted">الترتيب والمباريات الياية</p>') + "</div>" }); } }
      rows.sort(function(a, b){ return a.k - b.k || a.i - b.i; });
      var tl = PK.tally(), html = '<div class="mine-card">' + rows.map(function(r){ return r.h; }).join("") + (tl.k ? '<p class="picks">توقعاتك: صح <b class="num">' + tl.n + '</b> من <b class="num">' + tl.k + "</b></p>" : "") + (fb ? '<p class="small" style="margin:0">اختار فريقك، ومبارياته تطلع لك هني أول شي.</p>' : '<button type="button" class="btn copy" id="themebtn">ألوان فريقي على الموقع</button>') + "</div>";
      if (el._h === html) return; el._h = html; el.innerHTML = html; R.localize(el);
    });
  }

  // ---- W3.9 /arabs/: the «العرب الليلة» strip keeps moving — minute and score from live.json, goals and assists from the live match file
  function arabs(){
    var cards = [].slice.call(document.querySelectorAll("#atn .atr[data-m]")); if (!cards.length) return Promise.resolve();
    return get("live.json").then(function(l){ var by = {}; (l.matches || []).forEach(function(m){ by[m.id] = m; }); var ids = {};
      cards.forEach(function(c){ var m = by[+c.dataset.m]; if (!m) return; ids[m.id] = m; var st = c.querySelector(".atm"); if (st) st.innerHTML = R.minute(m) + (m.score ? ' <bdi dir="ltr" class="num">' + m.score.home + " - " + m.score.away + "</bdi>" : ""); c.classList.toggle("live", R.isLive(m)); });
      return Promise.all(Object.keys(ids).map(function(id){ return get("match/" + id + ".json").then(function(d){ var g = {}, a = {};
        (d.events || []).forEach(function(e){ if (e.type !== "goal" || e.detail === "own_goal") return; if (e.player && e.player.id) g[e.player.id] = (g[e.player.id] || 0) + 1; if (e.assist && e.assist.id) a[e.assist.id] = (a[e.assist.id] || 0) + 1; });
        cards.forEach(function(c){ if (+c.dataset.m !== +id) return; var p = +c.dataset.p, x = c.querySelector(".atg"); if (!x) return; x.textContent = [g[p] ? (g[p] > 1 ? g[p] + " أهداف" : "هدف") : "", a[p] ? (a[p] > 1 ? a[p] + " صناعة" : "صناعة") : ""].filter(Boolean).join(" · "); }); }).catch(function(){}); }))
        .then(function(){ poll(arabs, Object.keys(ids).length ? 30e3 : 120e3); }); }).catch(function(){ poll(arabs, 120e3); });
  }

  // ---- owner item 9b: «منو بيفوز؟» — picks live in localStorage {mid: {p, ko, h, a, r}}; r = 1 right, 0 wrong, once the result is known
  var PK = { all:function(){ try { return JSON.parse(localStorage.getItem("tifo.picks") || "{}"); } catch (e){ return {}; } }, save:function(o){ try { localStorage.setItem("tifo.picks", JSON.stringify(o)); } catch (e){} },
    res:function(m){ return m && m.status === "finished" && m.score ? (m.score.home > m.score.away ? "h" : m.score.home < m.score.away ? "a" : "d") : null; },
    settle:function(m){ var o = PK.all(), p = o[m.id], r = PK.res(m); if (!p || p.r != null || !r) return p; p.r = p.p === r ? 1 : 0; o[m.id] = p; PK.save(o); return p; },
    tally:function(){ var o = PK.all(), n = 0, k = 0; Object.keys(o).forEach(function(id){ if (o[id].r != null){ k++; n += o[id].r; } }); return { n:n, k:k }; },
    // results for picks past kickoff + 2.5 h, from the match file, at most 3 per page load
    catchUp:function(){ var o = PK.all(), due = Object.keys(o).filter(function(id){ return o[id].r == null && Date.now() - Date.parse(o[id].ko) > 2.5 * 36e5; }).slice(0, 3);
      return Promise.all(due.map(function(id){ return get("match/" + id + ".json").then(function(m){ PK.settle(m); if (m.status === "cancelled" || m.status === "postponed"){ var x = PK.all(); delete x[id]; PK.save(x); } }).catch(function(){}); })); } };
  (function(){ var box = $("#pick"); if (!box) return; var id = +box.dataset.mid, ko = Date.parse(box.dataset.kick), btns = [].slice.call(box.querySelectorAll("[data-p]")), msg = $("#pickm");
    function gone(){ return Date.now() >= ko; } function paint(){ var p = PK.all()[id]; btns.forEach(function(b){ b.setAttribute("aria-pressed", p && p.p === b.dataset.p ? "true" : "false"); }); if (msg) msg.textContent = p ? "توقعك: " + (p.p === "d" ? "تعادل" : btns.filter(function(b){ return b.dataset.p === p.p; })[0].textContent) + ". نشوف بعد النهاية." : ""; }
    if (gone()){ box.hidden = true; return; } paint();
    box.addEventListener("click", function(e){ var b = e.target.closest("[data-p]"); if (!b || gone()) return; var o = PK.all(); o[id] = { p:b.dataset.p, ko:box.dataset.kick, h:+box.dataset.h, a:+box.dataset.a }; PK.save(o); paint(); });
    document.addEventListener("tifo:match", function(e){ if (e.detail && e.detail.status !== "scheduled"){ box.hidden = true; var sk = $("#stakes"); if (sk) sk.hidden = true; } });
    setTimeout(function(){ if (gone()) box.hidden = true; }, Math.max(0, Math.min(ko - Date.now(), 2147483000))); })();
  // on a finished match page: settle the pick and say it in the hero (absolutely placed, so nothing moves)
  document.addEventListener("tifo:match", function(e){ var m = e.detail; if (!m || m.status !== "finished" || $(".pickres")) return; var p = PK.settle(m); if (!p || p.r == null) return; var hin = $(".mhero .hero-in"); if (!hin) return;
    var n = document.createElement("p"); n.className = "pickres" + (p.r ? " ok" : ""); n.textContent = p.r ? "توقعك طلع صح" : "توقعك طلع غلط"; hin.appendChild(n); });

  // ---- competition: standings (live), fixtures, leaders
  function comp(){
    var cid = +B.dataset.comp;
    // W2.11: after the first load a competition page polls only the table and live.json; fixtures and scorers come once
    var first = !comp._fx;
    return Promise.all([get("comp/" + cid + "/standings.json").catch(function(){ return null; }), first ? get("comp/" + cid + "/fixtures.json").catch(function(){ return null; }) : Promise.resolve(comp._fx), first ? get("comp/" + cid + "/stats.json").catch(function(){ return null; }) : Promise.resolve(null), get("live.json").catch(function(){ return { matches:[] }; })]).then(function(r){
      if (r[1]) comp._fx = r[1]; var st = r[0], fx = r[1], stats = r[2], live = (r[3].matches || []).filter(function(m){ return m.comp === cid; });
      if (st){ var lt = R.liveTable(st, live); set("#table", (lt.is_live ? '<p class="note"><i class="cardflip"></i>الترتيب اللحظي: لو انتهت المباريات الحين</p>' : "") + R.standings(lt, { mine:mine() })); }
      if (fx){ var by = {}; live.forEach(function(m){ by[m.id] = m; }); fx.matches = fx.matches.map(function(m){ return by[m.id] || m; }); roundsUI(fx); }
      if (stats){ set("#goals", R.leaders(stats, "goals")); set("#assists", R.leaders(stats, "assists")); }
      if (st && fx) whatif(st, fx);
      stamp((fx && fx.generated) || (st && st.generated));
      poll(comp, live.length ? 20e3 : 300e3);
    });
  }
  // «شو لو؟» (feature 11) and final day (118): pick 1/X/2 for the coming rounds, the table re-sorts
  var WI = { picks:{}, round:null, st:null, fx:null };
  function whatif(st, fx){
    var box = $("#whatif"); if (!box) return; WI.st = st; WI.fx = fx;
    var rounds = box.dataset.rounds.split(","), rr = R.rounds(fx); if (!WI.round || rounds.indexOf(WI.round) < 0) WI.round = rounds[0];
    set("#wi-r", rounds.map(function(k){ return '<button type="button" data-r="' + R.esc(k) + '"' + (k === WI.round ? ' aria-pressed="true"' : "") + ">" + R.roundLabel(k) + "</button>"; }).join(""));
    var ms = (rr.by[WI.round] || []).filter(function(m){ return m.status === "scheduled"; });
    set("#wi-m", ms.map(function(m){ var p = WI.picks[m.id]; var b = function(v, t){ return '<button type="button" data-m="' + m.id + '" data-v="' + v + '" aria-pressed="' + (p === v) + '">' + t + "</button>"; };
      return '<div class="wi"><span class="t">' + R.logo(m.home, "sm") + " " + R.tname(m.home) + '</span><span class="pick">' + b("H", "فوز") + b("D", "تعادل") + b("A", "فوز") + '</span><span class="t a">' + R.tname(m.away) + " " + R.logo(m.away, "sm") + "</span></div>"; }).join("") || '<p class="empty">ما في مباريات باقية في هالجولة.</p>');
    var rows = JSON.parse(JSON.stringify(st.groups[0].rows)), by = {}; rows.forEach(function(r){ r.was = r.rank; by[r.team.id] = r; });
    (fx.matches || []).forEach(function(m){ var p = WI.picks[m.id]; if (!p) return; var h = by[m.home.id], a = by[m.away.id]; if (!h || !a) return;
      var hs = p === "H" ? 1 : 0, as = p === "A" ? 1 : 0; [[h, hs, as], [a, as, hs]].forEach(function(x){ var r = x[0]; r.played++; r.gf += x[1]; r.ga += x[2]; r.gd = r.gf - r.ga; r.pts += x[1] > x[2] ? 3 : x[1] === x[2] ? 1 : 0; }); });
    rows.sort(function(x, y){ return y.pts - x.pts || y.gd - x.gd || y.gf - x.gf || x.was - y.was; });
    set("#wi-t", '<div class="tblwrap"><table class="st"><thead><tr><th>#</th><th style="text-align:start">الفريق</th><th>لعب</th><th>الفارق</th><th>نقاط</th></tr></thead><tbody>' + rows.map(function(r, i){ var d = r.was - (i + 1); return '<tr class="' + (mine() === r.team.id ? "mine" : "") + '"><td>' + (i + 1) + (d ? '<span class="mv ' + (d > 0 ? "up" : "dn") + '">' + (d > 0 ? "▲" : "▼") + Math.abs(d) + "</span>" : "") + '</td><td class="tm">' + R.logo(r.team, "sm") + " " + R.tname(r.team) + "</td><td>" + r.played + '</td><td><bdi dir="ltr">' + (r.gd > 0 ? "+" : "") + r.gd + '</bdi></td><td class="pts">' + r.pts + "</td></tr>"; }).join("") + "</tbody></table></div>");
    if (!box._wired){ box._wired = true; box.addEventListener("click", function(e){ var b = e.target.closest("button"); if (!b) return; if (b.dataset.r){ WI.round = b.dataset.r; } else if (b.dataset.m){ WI.picks[b.dataset.m] = WI.picks[b.dataset.m] === b.dataset.v ? undefined : b.dataset.v; } whatif(WI.st, WI.fx); }); }
  }
  var curRound = null;
  function roundsUI(fx){
    var rr = R.rounds(fx), el = $("#rounds"); if (!el) return;
    if (curRound == null || rr.order.indexOf(curRound) < 0) curRound = fx.next_round && rr.by[fx.next_round] ? fx.next_round : (function(){ var k = rr.order.filter(function(k){ return rr.by[k].some(function(m){ return m.status !== "finished"; }); })[0]; return k || rr.order[rr.order.length - 1]; })();
    var ck = (location.pathname.match(/^\/c\/([^/]+)\//) || [])[1];
    el.innerHTML = (ck && /^\d+$/.test(String(curRound)) ? '<p class="small"><a href="/c/' + ck + "/r/" + R.esc(curRound) + '/">صفحة الجولة ' + R.esc(curRound) + "</a></p>" : "") + '<div class="chips">' + rr.order.map(function(k){ return '<button type="button" data-r="' + R.esc(k) + '"' + (k === curRound ? ' aria-pressed="true"' : "") + ">" + R.roundChip(k) + "</button>"; }).join("") + '</div><div id="roundlist">' + (rr.by[curRound] ? R.roundList(rr.by[curRound], { mine:mine() }) : "") + "</div>";
    var cur = el.querySelector('[aria-pressed="true"]'); if (cur) cur.scrollIntoView({ block:"nearest", inline:"center" });
    el.onclick = function(e){ var b = e.target.closest("button[data-r]"); if (!b) return; curRound = b.dataset.r; roundsUI(fx); };
  }

  // ---- match: detail, live every 20 s
  var MD = null; try { var ms0 = document.getElementById("msum"); if (ms0) MD = JSON.parse(ms0.textContent); } catch (e){}
  // 3D lineup pitch (103): three.js loads only on demand
  var FULL = null, P3 = null, pbtn = $("#p3dbtn");
  if (pbtn) pbtn.onclick = function(){
    var box = $("#p3d"); if (!FULL || !box) return;
    if (P3){ P3.dispose(); P3 = null; box.innerHTML = ""; box.classList.remove("p3d"); pbtn.textContent = "شوفها على ملعب ثلاثي الأبعاد"; return; }
    pbtn.disabled = true; pbtn.textContent = "نجهّز الملعب…";
    import(pbtn.dataset.src).then(function(m){ P3 = m.mount(box, FULL); pbtn.textContent = "سكّر الملعب"; pbtn.disabled = false; box.scrollIntoView({ block:"nearest" }); })
      .catch(function(){ pbtn.textContent = "ما قدرنا نفتح الملعب، جرّب مرة ثانية"; pbtn.disabled = false; });
  };
  var sb = $("#storybtn"); if (sb) sb.onclick = function(){ if (MD && window.TifoShare){ sb.disabled = true; window.TifoShare.story(MD).then(function(){ sb.disabled = false; }); } };
  // QA 14: a page opened long before kickoff waits (no detail fetch, no 404) and wakes 75 min before; a 404 near kickoff retries
  function wake(md){ var t = md && Date.parse(md.kickoff_utc); if (!md || md.status !== "scheduled" || !t) return false; var d = t - Date.now() - 75 * 60e3; if (d <= 0) return false; poll(match, Math.min(d, 2147483000)); return true; }
  function nearKick(md){ var t = md && Date.parse(md.kickoff_utc); return !!t && (R.isLive(md) || (md.status === "scheduled" && t - Date.now() < 90 * 60e3 && t > Date.now() - 4 * 3600e3)); }
  function match(){
    if (MD && !MD._full && wake(MD)) return Promise.resolve();
    return Promise.all([index(), get("match/" + ID + ".json")]).then(function(r){
      var idx = r[0], md = r[1];
      if (MD && md.generated && MD.generated === md.generated && MD._full){ var t0 = Date.parse(md.kickoff_utc); if (R.isLive(md) || (md.status === "scheduled" && t0 - Date.now() < 90 * 60e3)) poll(match, 20e3); return; }   // W2.11: nothing new
      md._full = 1; MD = md; FULL = md; setTimeout(dist, 0); var pb = $("#p3dbtn"); if (pb) pb.hidden = !(md.lineups && md.lineups.home) || (navigator.deviceMemory && navigator.deviceMemory <= 3);   // W4.7: no 3D on phones with 3 GB or less
      set("#mh", R.matchHead(md)); set("#facts", R.matchFacts(md, idx)); set("#catchup", R.catchup(md)); set("#events", R.events(md)); set("#lineups", R.lineups(md)); set("#stats", R.stats(md)); if (md.h2h && md.h2h.summary) set("#h2h", R.h2h(md));   /* QA 2: a detail file without h2h keeps the prerendered history */ document.dispatchEvent(new CustomEvent("tifo:match", { detail:md }));   // v3 shell: after the re-render
      stamp(md.generated); ok();
      var t = Date.parse(md.kickoff_utc), soon = md.status === "scheduled" && t - Date.now() < 90 * 60e3 && t > Date.now() - 3 * 3600e3;
      weak(md); if (R.isLive(md) || soon){ poll(match, 20e3); overlay(); } else wake(md);
    }).catch(function(){ if (nearKick(MD)){ if (MD._full) retry(match); else poll(match, 30e3); overlay(); } else wake(MD); });
  }
  // W1.1c: while live, score / minute / status come from live.json every 10 s (the full match file stays on 20 s)
  var ovT = null;
  function overlay(){ clearTimeout(ovT); ovT = setTimeout(function(){ if (!MD || !(R.isLive(MD) || MD.status === "scheduled")) return; if (document.hidden){ overlay(); return; }
    get("live.json").then(function(lv){ var m = (lv.matches || []).filter(function(x){ return String(x.id) === String(ID); })[0];
      if (m && (JSON.stringify(m.score) !== JSON.stringify(MD.score) || m.minute !== MD.minute || m.status !== MD.status || m.period_start !== MD.period_start)){ ["score", "minute", "status", "status_detail", "penalties", "period", "period_start", "period_base", "period_length"].forEach(function(k){ if (k in m) MD[k] = m[k]; }); set("#mh", R.matchHead(MD)); document.dispatchEvent(new CustomEvent("tifo:match", { detail:MD })); }
      stamp(lv.generated); }).catch(function(){}).then(overlay); }, 10e3); }
  // W1.1g: a live match whose data is more than 90 s old says so (the score stays)
  function weak(md){ var el = $("#weaknote"); var old = R.isLive(md) && md.generated && Date.now() - Date.parse(md.generated) > 90e3;
    if (!old){ if (el) el.remove(); return; } if (!el){ el = document.createElement("p"); el.id = "weaknote"; el.className = "netnote"; var h = document.querySelector(".hero-in"); if (h) h.appendChild(el); }
    el.textContent = "الاتصال ضعيف · آخر تحديث " + new Date(md.generated).toLocaleTimeString("ar-AE-u-nu-latn", { hour:"2-digit", minute:"2-digit", timeZone:"Asia/Dubai" }); }
  // W1.1f: /today/ and /tomorrow/ refresh their list and live scores too
  function daypage(){ var off = /\/tomorrow\//.test(location.pathname) ? 1 : 0, box = $("#day"); if (!box) return Promise.resolve();
    return Promise.all([index(), get("day/" + uaeToday(off).replace(/-/g, "") + ".json"), get("live.json").catch(function(){ return { matches:[] }; })]).then(function(r){ ok(); var by = {}; (r[2].matches || []).forEach(function(m){ by[m.id] = m; });
      var ms = (r[1].matches || []).map(function(m){ return by[m.id] || m; }); set("#day", R.dayList(ms, r[0], { mine:mine(), country:country(), empty:"ما في مباريات." })); stamp(r[2].generated || r[1].generated);
      poll(daypage, (r[2].matches || []).length ? 20e3 : 120e3); }).catch(function(){ retry(daypage); }); }

  // ---- team
  function team(){
    var btn = $("#mybtn");
    function isFav(){ return favs().some(function(x){ return x.t === "team" && x.id === +ID; }); }
    function paint(){ if (!btn) return; var on = isFav(); btn.textContent = on ? (mine() === +ID ? "فريقي ✓" : "في مفضلتي ✓") : (favs().length ? "ضيفه لمفضلتي" : "هذا فريقي"); btn.classList.toggle("on", on); }
    if (btn){ btn.onclick = function(){ var f = favs(); if (isFav()){ f = f.filter(function(x){ return !(x.t === "team" && x.id === +ID); }); if (mine() === +ID){ var nx = f.filter(function(x){ return x.t === "team"; })[0]; setMine(nx ? nx.id : null, nx ? nx.n : ""); } } else { f.push({ t:"team", id:+ID, n:B.dataset.name }); if (!mine()) setMine(+ID, B.dataset.name); } setFavs(f); paint(); }; paint(); }
    // the team file can lag a live match; live.json (fresh every few seconds) wins for the matches it carries
    return Promise.all([get("team/" + ID + ".json"), get("live.json").catch(function(){ return { matches:[] }; })]).then(function(r){
      var t = r[0], by = {}; (r[1].matches || []).forEach(function(m){ by[m.id] = m; }); t.fixtures = (t.fixtures || []).map(function(m){ var l = by[m.id]; return l ? Object.assign({}, m, { status:l.status, score:l.score, minute:l.minute, period:l.period, period_start:l.period_start, period_base:l.period_base, period_length:l.period_length }) : m; });
      // a fixture that says live/ht but live.json doesn't list it: the match file decides (once); never «مباشر» from a stale file
      var stale = t.fixtures.filter(function(m){ return R.isLive(m) && !by[m.id]; });
      return Promise.all(stale.map(function(m){ return get("match/" + m.id + ".json").then(function(d){ ["status", "score", "minute", "status_detail"].forEach(function(k){ m[k] = d[k]; }); }).catch(function(){ if (Date.now() - Date.parse(m.kickoff_utc) > 3 * 3600e3){ m.status = "unknown"; m.minute = null; } }); })).then(function(){ return t; });
    }).then(function(t){
      var f = R.teamFixtures(t);
      set("#next", f.next.length ? f.next.slice(0, 6).map(function(m){ return R.matchRow(m, { date:true }); }).join("") : '<p class="empty">ما في مباريات ياية منشورة.</p>');
      set("#past", f.past.length ? f.past.slice(0, 10).map(function(m){ return R.matchRow(m, { date:true }); }).join("") : '<p class="empty">ما في نتايج.</p>');
      var sqb = $("#squad"); if (sqb && sqb.dataset.clubs && R.setClubNames) try { R.setClubNames(Object.assign(JSON.parse(sqb.dataset.clubs), window.TAR || {})); } catch (e){}
      if ((t.squad || []).length || !document.querySelector("#squad .sq")) set("#squad", R.squad(t)); stamp(t.generated);   /* QA 12: an empty team file never wipes the national squad the build filled */
      var wp = $("#wpbtn"); if (wp && window.TifoShare){ wp.hidden = !f.next.length; wp.onclick = function(){ wp.disabled = true; window.TifoShare.wallpaper({ id:t.id, name:t.name_ar || t.name }, f.next).then(function(){ wp.disabled = false; }); }; }
    }).catch(function(){});
  }

  var pv = $("#prev"), nx = $("#next");
  if (pv && nx && PAGE === "home"){ pv.onclick = function(){ dayOff--; home(); }; nx.onclick = function(){ dayOff++; home(); }; }
  // W3.6: webcal:// does nothing on Android Chrome; Google Calendar subscribes to the same feed by cid
  var ics = $("#ics"); if (ics){ var wc = "webcal://" + location.host + "/v1/team/" + ID + ".ics"; ics.href = /Android/i.test(navigator.userAgent) ? "https://calendar.google.com/calendar/r?cid=" + wc : wc; if (/Android/i.test(navigator.userAgent)){ ics.target = "_blank"; ics.rel = "noopener"; } }
  // ---- countdown to the national team's next match (62), on home and /uae/
  var CD = null;
  // W2.4: the countdown follows the visitor's national team (window.NAT, iso2 -> team id), built once, then only the digits change
  function natId(){ var c = country(); return (window.NAT || {})[c] || null; }
  function countdown(){
    var el = $("#uaecd"); if (!el) return; var tid = PAGE === "team" ? +ID : natId(); if (!tid){ el.innerHTML = ""; return; }
    (CD && CD._t === tid ? Promise.resolve(CD) : fetch("/tn/" + tid + ".json").then(function(r){ return r.ok ? r.json() : null; }).then(function(t){ var m = t && t.next; CD = m && m.kickoff_utc && !m.time_tbd ? m : null; if (CD) CD._t = tid; return CD; })).then(function(m){
      if (!m || m.status === "finished" || Date.now() - Date.parse(m.kickoff_utc) > 3 * 3600e3){ el.innerHTML = ""; return; }
      if (R.isLive(m) || Date.parse(m.kickoff_utc) <= Date.now()){ get("live.json").then(function(lv){ var l = (lv.matches || []).filter(function(x){ return String(x.id) === String(m.id); })[0]; el.innerHTML = l && R.isLive(l) ? '<a class="cd" href="/m/' + m.id + '/"><b>المنتخب يلعب الحين</b><span class="dg">مباشر</span></a>' : ""; }).catch(function(){ el.innerHTML = ""; }); return; }   // live only when live.json confirms it
      var inHero = window.__feat && String(window.__feat.id) === String(m.id);
      if (!el.querySelector(".dg") || el.dataset.m !== String(m.id) + inHero){ el.dataset.m = String(m.id) + inHero;
        el.innerHTML = '<a class="cd" href="/m/' + m.id + '/"><span><b>' + (inHero ? "تبدا بعد" : R.tname(m.home) + " ضد " + R.tname(m.away)) + "</b>" + (inHero ? "" : '<br><span class="small">' + R.esc(R.dayLabel(R.ymd(m.kickoff_uae))) + " " + R.hhmm(m.kickoff_uae) + "</span>") + '</span><span class="dg"></span></a>'; }
      var dg = el.querySelector(".dg"), tick = function(){ var d = Math.max(0, Date.parse(m.kickoff_utc) - Date.now()), dd = Math.floor(d / 864e5), hh = Math.floor(d / 36e5) % 24, mm = Math.floor(d / 6e4) % 60, ss = Math.floor(d / 1e3) % 60, p2 = function(n){ return n < 10 ? "0" + n : n; };
        dg.textContent = (dd ? R.n(dd, ["يوم", "يومين", "أيام", "يوم"]) + " و" : "") + p2(hh) + ":" + p2(mm) + ":" + p2(ss); };   /* QA 75/88 */
      tick(); clearInterval(el._t); el._t = setInterval(tick, 1000);
    }).catch(function(){});
  }

  // ---- majlis TV (22) and matches side by side (131): /tv/ and /tv/?m=id,id
  function tv(){
    var pins = [], mineMode = false; try { var sq = new URLSearchParams(location.search); pins = (sq.get("m") || "").split(",").filter(Boolean).map(Number); mineMode = sq.get("mine") === "1"; } catch (e){}
    var box = $("#tv"); if (!box) return Promise.resolve();
    // W4.2: /tv/?mine=1 is the old وضع المتابعة: each of your teams' live, next or last match, big
    if (mineMode){ var h1 = $("main h1"); if (h1 && h1.textContent !== "وضع المتابعة"){ h1.textContent = "وضع المتابعة"; document.title = "وضع المتابعة | تيفو"; } }
    var myT = favs().filter(function(x){ return x.t === "team"; }).slice(0, 4);
    if (mineMode && !myT.length){ box.className = "tvgrid"; box.innerHTML = '<p class="empty">اختار فريقك من صفحة النادي («هذا فريقي»)، وبعدها افتح هالشاشة.</p>'; return Promise.resolve(); }
    var load = mineMode ? Promise.all([Promise.all(myT.map(function(x){ return fetch("/tn/" + x.id + ".json").then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; }); })), get("live.json").catch(function(){ return { matches:[] }; })]).then(function(r){ var lv = r[1].matches || [], seen = {};
        return r[0].map(function(tn, i){ if (!tn) return null; var id = myT[i].id, l = lv.filter(function(m){ return m.home.id === id || m.away.id === id; })[0]; return l || tn.next || tn.last; }).filter(function(m){ if (!m || seen[m.id]) return false; seen[m.id] = 1; return true; }); })
      : pins.length ? Promise.all(pins.map(function(id){ return get("match/" + id + ".json").catch(function(){ return null; }); })) : Promise.all([get("day/" + uaeToday(0).replace(/-/g, "") + ".json").catch(function(){ return { matches:[] }; }), get("live.json").catch(function(){ return { matches:[] }; })]).then(function(r){ var by = {}; (r[1].matches || []).forEach(function(m){ by[m.id] = m; }); return (r[0].matches || []).map(function(m){ return by[m.id] || m; }).sort(function(a, b){ return (R.isLive(b) - R.isLive(a)) || (a.kickoff_utc || "").localeCompare(b.kickoff_utc || ""); }); });
    return load.then(function(ms){
      ms = ms.filter(Boolean); box.className = "tvgrid" + (pins.length || mineMode ? " pin" : "");
      box.innerHTML = ms.length ? ms.map(function(m){ var live = R.isLive(m), big = m.score ? m.score.home + " - " + m.score.away : R.hhmm(m.kickoff_uae);
        var ev = pins.length ? "<ul>" + (m.events || []).filter(function(e){ return /goal|red|second_yellow/.test(e.type) && e.player; }).reverse().map(function(e){ return "<li>" + e.minute + "' " + (/goal/.test(e.type) ? "⚽ " : "🟥 ") + R.esc(e.player.name) + " (" + R.tname(e.team === "home" ? m.home : m.away) + ")</li>"; }).join("") + "</ul>" : "";
        return '<a class="tvt' + (live ? " live" : "") + '" href="/m/' + m.id + '/"><span class="cmp">' + R.esc(m.comp_name_ar || "") + '</span><span class="row"><span class="tn">' + R.logo(m.home) + R.tname(m.home) + '</span><span class="big">' + big + '</span><span class="tn a">' + R.logo(m.away) + R.tname(m.away) + '</span></span><span class="st">' + (live ? R.minute(m) + (R.hot(m) ? " حامي" : "") : mineMode && m.status === "scheduled" ? R.td(m.kickoff_uae, true) : R.statusText(m)) + "</span>" + ev + "</a>"; }).join("") : '<p class="empty">ما في مباريات اليوم.</p>';
      stamp(new Date().toISOString()); poll(tv, 20e3);
    });
  }
  function tvFull(){ var b = $("#fsbtn"); if (b) b.onclick = function(){ var d = document.documentElement; if (!document.fullscreenElement && d.requestFullscreen) d.requestFullscreen(); else if (document.exitFullscreen) document.exitFullscreen(); }; }

  // ---- Tifo studio (152)
  function studio(){
    var sel = $("#sclub"), txt = $("#stext"), cv = $("#sprev"), btn = $("#sdl"); if (!sel || !window.TifoShare) return Promise.resolve();
    var draw = function(){ window.TifoShare.banner(+sel.value, txt.value.trim()).then(function(c){ var x = cv.getContext("2d"); cv.width = 1500; cv.height = 500; x.drawImage(c, 0, 0, 1500, 500); cv._full = c; }); };
    var t = null; sel.onchange = draw; txt.oninput = function(){ clearTimeout(t); t = setTimeout(draw, 250); };
    btn.onclick = function(){ if (cv._full) window.TifoShare.out(cv._full, "tifo-banner.png"); };
    draw(); return Promise.resolve();
  }

  // ---- no-spoiler mode (41): scores blurred until tapped
  var sp = $("#spoil");
  var spoilReady = false; function spoilSet(on){ var was = document.body.classList.contains("nospoil"); if (spoilReady && was !== !!on) setTimeout(function(){ document.dispatchEvent(new CustomEvent("tifo:nospoil", { detail:!!on })); }, 0); document.body.classList.toggle("nospoil", on); if (sp) sp.setAttribute("aria-pressed", on); try { localStorage.setItem("tifo.nospoil", on ? "1" : ""); } catch (e){} }
  try { spoilSet(localStorage.getItem("tifo.nospoil") === "1"); } catch (e){} spoilReady = true;
  if (sp) sp.onclick = function(){ spoilSet(!document.body.classList.contains("nospoil")); };
  document.addEventListener("click", function(e){ if (!document.body.classList.contains("nospoil")) return; var t = e.target.closest(".chip,.board .dg"); if (t && !t.classList.contains("shown")){ e.preventDefault(); t.classList.add("shown"); } }, true);

  // distance from your emirate (45): remembered choice, rough driving time at ~90 km/h
  function dist(){ var em = "dubai"; try { em = localStorage.getItem("tifo.emirate") || "dubai"; } catch (e){}
    document.querySelectorAll(".dist").forEach(function(d){ var km = JSON.parse(d.dataset.km || "{}"), sel = d.querySelector("select"); if (!sel) return; sel.value = em;
      var paint = function(){ var k = km[sel.value];
        document.querySelectorAll(".leave[data-kick]").forEach(function(l){ if (k == null){ l.textContent = "—"; return; } var t = Date.parse(l.dataset.kick) - (Math.round(k / 90 * 60) + 45) * 6e4; l.textContent = R.hhmm(new Date(t).toISOString()); }); d.querySelector(".dk").textContent = k != null ? Math.round(k) : "—"; d.querySelector(".dt").textContent = k != null ? "حوالي " + Math.max(5, Math.round(k / 90 * 60 / 5) * 5) + " دقيقة سواقة" : ""; };
      sel.onchange = function(){ try { localStorage.setItem("tifo.emirate", sel.value); } catch (e){} em = sel.value; dist(); }; paint(); }); }
  // copy buttons (thread posts, press sheet)
  document.addEventListener("click", function(e){ var b = e.target.closest("[data-copy],[data-copy-from]"); if (!b) return; var t = b.dataset.copy || ((document.querySelector(b.dataset.copyFrom) || {}).innerText || "");
    (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(function(){ var o = b.textContent; b.textContent = "انسخ ✓"; setTimeout(function(){ b.textContent = o; }, 1500); }, function(){}); });
  // «اسأل تيفو» (76)
  var af = $("#askf"); if (af) af.onsubmit = function(e){ e.preventDefault(); var q = $("#askq").value.trim(); if (q.length < 4) return; set("#aska", '<p class="muted">لحظة…</p>'); var sb = af.querySelector("button"); if (sb) sb.disabled = true; var done = function(){ if (sb) sb.disabled = false; };   // W4.6: no double send
    fetch("/api/tifo/ask", { method:"POST", headers:{ "content-type":"application/json" }, body:JSON.stringify({ q:q }) }).then(function(r){ return r.json().then(function(j){ return { ok:r.ok, j:j }; }); })
      .then(function(x){ set("#aska", x.ok ? '<div class="ai"><p>' + R.esc(x.j.answer) + "</p></div>" : '<p class="note">' + R.esc((x.j && (x.j.error || x.j.message)) || "ما قدرنا نجاوب الحين") + "</p>"); done(); })
      .catch(function(){ set("#aska", '<p class="note">ما قدرنا نجاوب الحين، جرّب بعد شوي.</p>'); done(); }); };
  // commentator mode (177): the press sheet full screen, big type, the live score on top, facts cycling every 8 s
  document.addEventListener("click", function(e){ var b = e.target.closest("#commbtn"); if (!b) return; var p = $(".press"); if (!p) return;
    var on = !document.body.classList.contains("comm"); document.body.classList.toggle("comm", on); b.textContent = on ? "سكّر وضع المعلّق" : "وضع المعلّق";
    clearInterval(window._commT); if (!on) return; var lis = p.querySelectorAll("li"), i = 0; lis.forEach(function(l){ l.classList.remove("hot1"); });
    window._commT = setInterval(function(){ lis.forEach(function(l){ l.classList.remove("hot1"); }); if (lis[i]) { lis[i].classList.add("hot1"); lis[i].scrollIntoView({ block:"center", behavior:"smooth" }); } i = (i + 1) % lis.length; }, 8000); });
  // service worker (202)
  if ("serviceWorker" in navigator) try { navigator.serviceWorker.register("/sw.js"); } catch (e){}
  // «بس مباريات العرب» (234)
  function arabOnly(){ try { return localStorage.getItem("tifo.arab") === "1"; } catch (e){ return false; } }
  var ab = $("#arabonly"); if (ab){ ab.setAttribute("aria-pressed", arabOnly()); ab.onclick = function(){ try { localStorage.setItem("tifo.arab", arabOnly() ? "" : "1"); } catch (e){} ab.setAttribute("aria-pressed", arabOnly()); home(); }; }
  // second screen (223): only the scoreboard, the match line and the numbers, big, screen kept awake
  var sb2 = $("#secondbtn"), wl = null;
  if (sb2) sb2.onclick = function(){ var on = !document.body.classList.contains("second"); document.body.classList.toggle("second", on); sb2.textContent = on ? "سكّر الشاشة الثانية" : "الشاشة الثانية";
    if (on && navigator.wakeLock) navigator.wakeLock.request("screen").then(function(l){ wl = l; }).catch(function(){}); else if (wl){ wl.release(); wl = null; } };
  // 250: per-section share buttons became the page sheet's «صورة لأي قسم» (v3, src/shell.js)
  // 235 round story: the table re-sorts as each result lands (FLIP via --i row index)
  (function(){ var d = $("#storydata"); if (!d) return; var snaps = JSON.parse(d.textContent), rows = {}; document.querySelectorAll(".stbl li").forEach(function(li){ rows[li.dataset.t] = li; });
    function show(k){ (snaps[k] || []).forEach(function(x, i){ var li = rows[x[0]]; if (!li) return; li.style.setProperty("--i", i); li.querySelector(".rk").textContent = i + 1; li.querySelector(".pt").textContent = x[1]; li.classList.toggle("moved", k > 0 && snaps[k - 1] && snaps[k - 1].findIndex(function(y){ return y[0] === x[0]; }) !== i); }); }
    // W4.4: «شغّل الجولة» plays each result onto the table; reduced motion jumps to the end
    var play = $("#stplay"), now = $("#stnow"), steps = [].slice.call(document.querySelectorAll(".steps .step")), tmr = null;
    if (play && now){ play.onclick = function(){ clearInterval(tmr); var RMq = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches, k = RMq ? snaps.length - 1 : 0;
        function at(k){ show(k); var st = steps[k]; now.innerHTML = st ? st.innerHTML : ""; R.localize && R.localize(now); play.textContent = k >= snaps.length - 1 ? "شغّلها مرة ثانية" : "شغّالة…"; }
        at(k); if (RMq) return; tmr = setInterval(function(){ k++; if (k >= snaps.length){ clearInterval(tmr); return; } at(k); }, 1400); }; }
    else if ("IntersectionObserver" in window){ var io = new IntersectionObserver(function(es){ es.forEach(function(e){ if (e.isIntersecting){ document.querySelectorAll(".step.on").forEach(function(s){ s.classList.remove("on"); }); e.target.classList.add("on"); show(+e.target.dataset.s); } }); }, { rootMargin:"-45% 0px -45% 0px" }); document.querySelectorAll(".step").forEach(function(s){ io.observe(s); }); } else show(snaps.length - 1); })();
  // 204/205: where to watch in the visitor's country (research/broadcast_by_country.json); UAE list with a note when missing
  var BCD = null; function bcData(){ return BCD ? Promise.resolve(BCD) : fetch("/assets/bc." + B.dataset.bc + ".json").then(function(r){ return r.json(); }).then(function(x){ BCD = x; return x; }).catch(function(){ return {}; }); }
  function freeIn(comp){ var c = country(), e = BCD && BCD[c] && BCD[c][comp]; if (!e || !e.b || !e.b.length) return true; return e.b.some(function(b){ return b[1]; }); }   // unknown channel: keep it (W1.2b)
  (function(){ var box = $("#wwbox"); if (!box) return; var c = country(); if (c === "AE" || c === "xx") return;
    bcData().then(function(d){ var row = R.COUNTRIES.filter(function(x){ return x[0] === c; })[0], e = d[c] && d[c][box.dataset.comp]; if (!e || !e.b.length) { var n = box.querySelector("h2"); if (n) n.insertAdjacentHTML("afterend", '<p class="note">ما لقينا معلومة مؤكدة لـ' + (row ? row[1] : "بلدك") + '، وهذي القنوات في الإمارات.</p>'); return; }
      box.innerHTML = '<section class="blk"><h2>وين تنقل في ' + (row ? row[1] : "بلدك") + '</h2><ul class="bc">' + e.b.map(function(b){ return "<li><b>" + R.esc(b[0]) + "</b>" + (b[1] ? "" : ' <span class="enc">مشفرة</span>') + (b[5] ? ' <span class="muted small">' + R.esc(b[5]) + "</span>" : "") + (b[2] ? ' <span class="num">' + b[2] + "</span> " + R.esc(b[3] || "") : "") + (b[4] ? ' <a class="src" href="' + R.esc(b[4]) + '" rel="noopener">المصدر</a>' : "") + "</li>"; }).join("") + "</ul>" + (e.q && e.q !== "high" ? '<p class="src">ثقة المعلومة: ' + (e.q === "medium" ? "متوسطة" : "قليلة") + "، تأكد من القناة قبل المباراة.</p>" : "") + "</section>"; }); })();
  function freeOnly(){ try { return localStorage.getItem("tifo.free") === "1"; } catch (e){ return false; } }
  try { localStorage.removeItem("tifo.free"); } catch (e){}   // owner 2026-09-30: the free-only filter is gone; a phone that had it on must not stay filtered
  // 291: the coming round's odds as one image
  var rpb = $("#rpbtn"); if (rpb) rpb.onclick = function(){ var d = JSON.parse($("#rpreds").textContent); window.TifoShare.listCard("توقعات تيفو للجولة " + d[0].r, (document.querySelector("h1") || {}).textContent || "", d.map(function(m){ return { h:m.h, a:m.a, home:m.home, away:m.away, mid:Math.round(m.p[0] * 100) + "%   " + Math.round(m.p[1] * 100) + "%   " + Math.round(m.p[2] * 100) + "%", low:"فوز      تعادل      فوز" }; }), "tifo-round-odds.png"); };
  // 314: the week in the visitor's time zone, with their country's channel when known
  var wkb = $("#wkbtn"); if (wkb) wkb.onclick = function(){ var d = JSON.parse($("#wkdata").textContent), c = country(), row = R.COUNTRIES.filter(function(x){ return x[0] === c; })[0];
    bcData().then(function(bc){ window.TifoShare.listCard("مباريات الأسبوع", "بتوقيت " + (row ? row[1] : "بلدك"), d.map(function(m){ var e = bc[c] && bc[c][String(m.comp)], ch = e && e.b[0] ? e.b[0][0] : ""; return { h:m.h, a:m.a, home:m.home, away:m.away, mid:R.hhmm(m.ko), low:R.dayParts(R.ymd(m.ko)).date + (ch ? "، " + ch : "") }; }), "tifo-week.png"); }); };
  // 313: kickoff time and channel in every Arab country
  (function(){ var k = $("#kitct"); if (!k) return; var ko = k.dataset.ko, comp = k.dataset.comp, keep = R.TZ;
    bcData().then(function(bc){ var rows = R.COUNTRIES.map(function(c){ R.TZ = c[2]; var t = R.hhmm(ko), d = R.dayParts(R.ymd(ko)).short, e = bc[c[0]] && bc[c[0]][comp]; return "<tr><td>" + c[1] + '</td><td class="num">' + t + '</td><td class="small">' + d + "</td><td>" + (e && e.b.length ? e.b.map(function(b){ return R.esc(b[0]) + (b[1] ? "" : " (مشفرة)"); }).join("، ") : '<span class="muted">غير معروف</span>') + "</td></tr>"; }).join(""); R.TZ = keep;
      var anyCh = R.COUNTRIES.some(function(c){ var e = bc[c[0]] && bc[c[0]][comp]; return e && e.b.length; }); if (!anyCh) rows = rows.replace(/<td>(?:(?!<td>)[\s\S])*?<\/td><\/tr>/g, "</tr>");   // W1.2f: no channel anywhere -> no column
      k.innerHTML = '<div class="tblwrap"><table class="st"><thead><tr><th style="text-align:start">الدولة</th><th>الساعة</th><th>اليوم</th>' + (anyCh ? '<th style="text-align:start">القناة</th>' : "") + '</tr></thead><tbody>' + rows + '</tbody></table></div><button type="button" class="btn copy" data-copy-from="#kitct">انسخ الجدول</button>'; }); })();
  // 315: coach compare
  (function(){ var a = $("#ca"), b = $("#cb"); if (!a || !b) return; fetch("/assets/coaches." + (B.dataset.cv || "") + ".json").then(function(r){ return r.json(); }).then(function(C){
    var ids = Object.keys(C).sort(function(x, y){ return C[y].r.length - C[x].r.length; }), opts = ids.map(function(id){ return '<option value="' + id + '">' + R.esc(C[id].n) + "</option>"; }).join(""); a.innerHTML = b.innerHTML = opts; a.value = ids[0]; b.value = ids[1];
    try { var q = new URLSearchParams(location.search); if (q.get("a") && C[q.get("a")]) a.value = q.get("a"); } catch (e){}
    function tot(id){ var t = { g:0, w:0, d:0, l:0, s:{}, c:{} }; C[id].r.forEach(function(r){ t.w += r[3]; t.d += r[4]; t.l += r[5]; t.s[r[0]] = 1; t.c[r[2]] = 1; }); t.g = t.w + t.d + t.l; t.ppg = t.g ? (3 * t.w + t.d) / t.g : 0; return t; }
    function line(l, x, y, dir, f){ var w = x === y ? 0 : (x > y) === (dir > 0) ? 1 : 2; return '<div class="cmpt"><b class="' + (w === 1 ? "w" : "") + '">' + f(x) + "</b><span>" + l + '</span><b class="' + (w === 2 ? "w" : "") + '">' + f(y) + "</b></div>"; }
    function draw(){ var x = tot(a.value), y = tot(b.value), i = function(v){ return v; }, f2 = function(v){ return v.toFixed(2); };
      $("#cout").innerHTML = line("مباريات", x.g, y.g, 1, i) + line("فوز", x.w, y.w, 1, i) + line("تعادل", x.d, y.d, 0, i) + line("خسارة", x.l, y.l, -1, i) + line("نقاط بالمباراة", x.ppg, y.ppg, 1, f2) + line("مواسم", Object.keys(x.s).length, Object.keys(y.s).length, 1, i) + '<p class="small">' + R.esc(C[a.value].n) + ": " + R.esc(Object.keys(x.c).join("، ")) + '</p><p class="small">' + R.esc(C[b.value].n) + ": " + R.esc(Object.keys(y.c).join("، ")) + "</p>"; }
    a.onchange = b.onchange = draw; draw(); }); })();
  // 293: a toast when a favourite club scores while any page is open (skipped in no-spoiler mode)
  (function(){ var teams = favs().filter(function(x){ return x.t === "team"; }).map(function(x){ return x.id; }); if (!teams.length) return; var seen = {};
    function check(){ if (document.hidden) return; fetch("/v1/live.json", { cache:"no-cache" }).then(function(r){ return r.json(); }).then(function(l){ (l.matches || []).forEach(function(m){ [["home", m.home], ["away", m.away]].forEach(function(x){ if (teams.indexOf(x[1].id) < 0 || !m.score) return; var k = m.id + x[0], g = m.score[x[0]]; if (seen[k] != null && g > seen[k] && !document.body.classList.contains("nospoil")) toast("⚽ هدف لـ" + R.tname(x[1]) + "! " + m.score.home + " - " + m.score.away, "/m/" + m.id + "/"); seen[k] = g; }); }); }).catch(function(){}); }
    function toast(t, href){ var d = document.createElement("a"); d.className = "toast"; d.href = href; d.textContent = t; document.body.appendChild(d); setTimeout(function(){ d.remove(); }, 9000); }
    check(); setInterval(check, 30000); })();
  // 294: optional club colours from the first favourite
  function theme(){ var on = false; try { on = localStorage.getItem("tifo.theme") === "1"; } catch (e){} var f = favs().filter(function(x){ return x.t === "team"; })[0], c = f && (window.TC || {})[f.id];
    var st = document.documentElement.style; if (on && c){ var h = c[0], n = parseInt(h.slice(1), 16), l = (0.299 * (n >> 16 & 255) + 0.587 * (n >> 8 & 255) + 0.114 * (n & 255)) / 255; st.setProperty("--club1", h); document.body.classList.add("clubtheme"); document.body.style.setProperty("--club2", c[1] || h); } else { st.removeProperty("--club1"); document.body.classList.remove("clubtheme"); } }   // W2.3: the club theme tints the key art only, never --dune
  theme(); document.addEventListener("click", function(e){ if (!e.target.closest("#themebtn")) return; try { localStorage.setItem("tifo.theme", localStorage.getItem("tifo.theme") === "1" ? "" : "1"); } catch (x){} theme(); });
  // 184 newsletter: form anywhere with .nlform; confirm/unsubscribe results via ?ok= / ?bye=
  (function(){ var m = $("#nlmsg"), q = null; try { q = new URLSearchParams(location.search); } catch (e){}
    if (m && q){ if (q.has("ok")) m.innerHTML = '<p class="note">' + (q.get("ok") === "1" ? "تم اشتراكك، النشرة توصلك كل خميس." : "الرابط مب صحيح أو انتهى.") + "</p>"; if (q.has("bye")) m.innerHTML = '<p class="note">' + (q.get("bye") === "1" ? "انلغى اشتراكك." : "الرابط مب صحيح.") + "</p>"; }
    document.querySelectorAll(".nlform").forEach(function(f){ f.onsubmit = function(e){ e.preventDefault(); var em = f.querySelector("input[type=email]").value.trim(), out = f.previousElementSibling && f.previousElementSibling.id === "nlmsg" ? f.previousElementSibling : null;
      var sb = f.querySelector("button"); if (sb) sb.disabled = true; var say = function(t){ if (sb) sb.disabled = false; if (out) out.innerHTML = '<p class="note">' + R.esc(t) + "</p>"; else alert(t); };
      fetch("/api/tifo/subscribe", { method:"POST", headers:{ "content-type":"application/json" }, body:JSON.stringify({ email:em, country:country() }) }).then(function(r){ return r.json().then(function(j){ return { ok:r.ok, j:j }; }); })
        .then(function(x){ if (x.ok) say(x.j.already ? "أنت مشترك من قبل." : "وصلك إيميل تأكيد، افتحه واضغط الزر."); else say((x.j && (x.j.error || x.j.message)) || "صار خطأ، جرّب مرة ثانية."); }).catch(function(){ say("صار خطأ، جرّب مرة ثانية."); }); }; }); })();
  // 333 watch mode: the favourite club's live or next match, big
  (function(){ var box = $("#wbox"); if (!box) return; var t = favs().filter(function(x){ return x.t === "team"; })[0]; if (!t) return;
    function tick(){ Promise.all([fetch("/tn/" + t.id + ".json").then(function(r){ return r.json(); }), fetch("/v1/live.json", { cache:"no-cache" }).then(function(r){ return r.json(); }).catch(function(){ return { matches:[] }; })]).then(function(r){ var tn = r[0], lv = (r[1].matches || []).filter(function(m){ return m.home.id === t.id || m.away.id === t.id; })[0], m = lv || tn.next || tn.last; if (!m) return;
      box.innerHTML = '<a href="/m/' + m.id + '/" class="wb"><span class="wt">' + R.tname(m.home) + '</span><span class="ws2 num">' + (m.score ? m.score.home + " - " + m.score.away : R.hhmm(m.kickoff_uae)) + '</span><span class="wt">' + R.tname(m.away) + '</span><span class="wst">' + (R.isLive(m) ? R.minute(m) : m.score ? "انتهت" : R.dayLabel(R.ymd(m.kickoff_uae))) + "</span></a>"; }); }
    tick(); setInterval(tick, 20000); })();
  // 332 car mode: speak favourite clubs' goals, kickoffs and full-times (speechSynthesis, Arabic voice)
  (function(){ var b = $("#carbtn"); if (!b || !window.speechSynthesis) { if (b) b.hidden = true; return; } var on = false, T = null, seen = {};
    function say(t){ var u = new SpeechSynthesisUtterance(t); u.lang = "ar-AE"; var v = speechSynthesis.getVoices().filter(function(v){ return /^ar/i.test(v.lang); })[0]; if (v) u.voice = v; speechSynthesis.speak(u); }
    function poll(){ var ids = favs().filter(function(x){ return x.t === "team"; }).map(function(x){ return x.id; }); fetch("/v1/live.json", { cache:"no-cache" }).then(function(r){ return r.json(); }).then(function(l){ (l.matches || []).forEach(function(m){ if (ids.indexOf(m.home.id) < 0 && ids.indexOf(m.away.id) < 0) return; var k = m.id, prev = seen[k], H = R.tname(m.home), A = R.tname(m.away), sc = m.score ? m.score.home + " " + m.score.away : "";
      if (!prev) { if (on && m.minute && parseInt(m.minute, 10) < 3) say("بدت مباراة " + H + " و" + A); } else { if (m.score && prev.score && (m.score.home !== prev.score.home || m.score.away !== prev.score.away)) say("هدف! " + H + " " + m.score.home + "، " + A + " " + m.score.away); }
      seen[k] = m; }); Object.keys(seen).forEach(function(k){ if (!(l.matches || []).some(function(m){ return String(m.id) === k; })){ var m = seen[k]; if (m.score) say("خلصت: " + R.tname(m.home) + " " + m.score.home + "، " + R.tname(m.away) + " " + m.score.away); delete seen[k]; } }); }).catch(function(){}); }
    b.onclick = function(){ on = !on; b.setAttribute("aria-pressed", on); b.textContent = on ? "وضع السيارة شغال" : "وضع السيارة"; clearInterval(T); if (on){ say("وضع السيارة شغال. بقولك الأهداف أول بأول"); poll(); T = setInterval(poll, 20000); } }; })();
  // 334 voice search + 174 voice ask: webkitSpeechRecognition ar-AE (hidden when unsupported)
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  function listen(input, done){ var r = new SR(); r.lang = "ar-AE"; r.interimResults = false; r.onresult = function(e){ input.value = e.results[0][0].transcript; input.dispatchEvent(new Event("input")); if (done) done(); }; r.start(); }
  document.addEventListener("click", function(e){ if (e.target.id === "srch" && SR) setTimeout(function(){ var q = $("#sq"); if (q && !$("#sqmic")){ var m = document.createElement("button"); m.type = "button"; m.id = "sqmic"; m.className = "ib mic"; m.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>'; m.setAttribute("aria-label", "دوّر بصوتك"); m.onclick = function(){ listen(q); }; q.insertAdjacentElement("afterend", m); } }, 50); });
  (function(){ var f = $("#askf"); if (!f) return; var q = $("#askq");
    if (SR){ var m = document.createElement("button"); m.type = "button"; m.className = "ib mic"; m.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>'; m.setAttribute("aria-label", "اسأل بصوتك");   /* QA 52: a quiet icon button in the form's third column */ m.onclick = function(){ listen(q, function(){ f.requestSubmit ? f.requestSubmit() : f.onsubmit(new Event("submit")); }); }; f.appendChild(m); }
    new MutationObserver(function(){ var a = $("#aska .ai p"); if (!a || $("#aska .listen")) return; var b = document.createElement("button"); b.type = "button"; b.className = "btn copy listen"; b.textContent = "اسمع الجواب"; b.onclick = function(){ b.disabled = true;
      fetch("/api/tifo/tts", { method:"POST", headers:{ "content-type":"application/json" }, body:JSON.stringify({ lang:"ar", voice:"f", paras:[a.textContent] }) }).then(function(r){ return r.json(); }).then(function(j){ if (j.mp3) new Audio("data:audio/mpeg;base64," + j.mp3).play(); b.disabled = false; }).catch(function(){ b.disabled = false; }); };
      a.parentNode.appendChild(b); }).observe($("#aska"), { childList:true, subtree:true }); })();
  // 189 replay slider
  (function(){ var r = $("#rpr"); if (!r) return; var ev = JSON.parse($("#rpev").textContent), IC = { goal:"⚽", penalty_goal:"⚽", own_goal:"⚽", yellow:"🟨", red:"🟥", second_yellow:"🟥" };
    function draw(){ var t = +r.value, sc = [0, 0]; $("#rpm").textContent = t; var list = ev.filter(function(e){ return e[0] <= t; }); list.forEach(function(e){ if (e[4]) sc = e[4]; }); $("#rps").textContent = sc[0] + " - " + sc[1]; $("#rpe").innerHTML = list.slice().reverse().map(function(e){ return "<li>" + Math.floor(e[0]) + "' " + (IC[e[1]] || "") + ' <span class="lat">' + R.esc(e[3] || "") + "</span></li>"; }).join(""); }
    r.oninput = draw; draw(); })();
  // 230 countdown timers
  (function(){ var els = document.querySelectorAll(".cdt[data-u]"); if (!els.length) return; function tick(){ els.forEach(function(el){ var d = Math.max(0, Date.parse(el.dataset.u) - Date.now()), dd = Math.floor(d / 864e5), hh = Math.floor(d / 36e5) % 24, mm = Math.floor(d / 6e4) % 60; el.textContent = (dd ? R.n(dd, ["يوم", "يومين", "أيام", "يوم"]) + " و" : "") + (hh < 10 ? "0" : "") + hh + ":" + (mm < 10 ? "0" : "") + mm; }); } tick(); setInterval(tick, 30000); })();
  // Arab pages (build_arabs.cjs): country filters, nations head-to-head, TV guide, results archive, birthdays and club anniversaries
  [["#abf", "tr[data-c]"], ["#trf", "li[data-c]"]].forEach(function(x){ var s = $(x[0]); if (!s) return; s.onchange = function(){ document.querySelectorAll(x[1]).forEach(function(r){ r.hidden = !!s.value && r.dataset.c !== s.value; }); if (s.id === "trf") cap(); }; });
  // W4.4 /transfers/: opens on the visitor's country (when it has transfers) and the latest 30, with «ورني الكل»
  var trf = $("#trf"), trAll = false; function cap(){ var n = 0, rows = [].slice.call(document.querySelectorAll(".trl li[data-c]")); rows.forEach(function(r){ var vis = !trf.value || r.dataset.c === trf.value; r.hidden = !vis || (!trAll && ++n > 30); }); var more = $("#trmore"), over = rows.filter(function(r){ return !trf.value || r.dataset.c === trf.value; }).length > 30;
    if (!more){ more = document.createElement("button"); more.type = "button"; more.id = "trmore"; more.className = "ghost"; more.textContent = "ورني الكل"; more.onclick = function(){ trAll = true; cap(); }; var l = $(".trl"); if (l) l.parentNode.insertBefore(more, l.nextSibling); } more.hidden = trAll || !over; }
  if (trf){ var tc = country(); if (tc && [].some.call(trf.options, function(o){ return o.value === tc; })) trf.value = tc; else if ([].some.call(trf.options, function(o){ return o.value === "AE"; })) trf.value = "AE"; cap(); var tl = $("#trl"); if (tl) tl.classList.add("js"); }
  (function(){ var a = $("#nha"), b = $("#nhb"), d = $("#nhdata"); if (!a || !d) return; var D = JSON.parse(d.textContent), c = country();
    a.value = D.n[c] ? c : "AE"; b.value = a.value === "SA" ? "AE" : "SA";
    function show(){ var x = D.m[a.value] && D.m[a.value][b.value], A = D.n[a.value], Bn = D.n[b.value], o = $("#nhout");
      if (a.value === b.value){ o.innerHTML = '<p class="empty">اختار منتخبين مختلفين.</p>'; return; }
      if (!x){ o.innerHTML = '<p class="empty">ما تقابل ' + A + " و" + Bn + " في بياناتنا.</p>"; return; }
      o.innerHTML = '<div class="h2hsum"><div><b>' + x.w + "</b>فوز " + A + "</div><div><b>" + x.d + "</b>تعادل</div><div><b>" + x.l + "</b>فوز " + Bn + '</div></div><p>تقابلوا <b class="num">' + x.p + '</b> مرة، والأهداف <bdi dir="ltr" class="num">' + x.gf + "-" + x.ga + "</bdi> لـ" + A + (x.last ? '. آخر مواجهة <span class="num">' + x.last + "</span>" : "") + '.</p><p class="tools"><a class="btn" href="' + natHref(a.value) + '">منتخب ' + A + '</a><a class="btn" href="' + natHref(b.value) + '">منتخب ' + Bn + "</a></p>"; }
    a.onchange = b.onchange = show; show(); })();
  (function(){ var s = $("#gsel"), box = $("#guide"), fr = $("#gfree"); if (!s || !box) return;
    function free(){}   // the «المجاني بس» box was removed 2026-09-30
    function load(c){ box.innerHTML = '<p class="empty">نحمّل…</p>'; get("guide/" + c + ".json").then(function(g){ box.innerHTML = R.guide(g); R.localize(box); free(); }).catch(function(){ box.innerHTML = '<p class="empty">ما عندنا دليل لهالدولة للحين.</p>'; }); }
    var c = country(); if (c !== "xx" && c !== "AE" && R.COUNTRIES.some(function(x){ return x[0] === c; })){ s.value = c; load(c); } else R.localize(box);
    s.onchange = function(){ load(s.value); }; if (fr) fr.onchange = free; })();
  (function(){ var s = $("#exs"), cs = $("#exc"), q = $("#ext"), out = $("#exout"); if (!s || !out) return; var CN = JSON.parse($("#excomps").textContent), T = null, cur = null;
    function nm(id){ var t = T && T[id]; return t ? (t.name_ar || t.name || "") : ""; }
    function draw(){ if (!cur) return; var c = cs.value, w = q.value.trim().toLowerCase(), rows = cur.matches.filter(function(m){ return (!c || String(m[2]) === c) && (!w || [m[3], m[4]].some(function(id){ var t = T && T[id]; return t && ((t.name_ar || "").indexOf(w) >= 0 || (t.name || "").toLowerCase().indexOf(w) >= 0); })); }).slice().reverse();
      out.innerHTML = rows.length ? '<p class="muted small">' + rows.length + " مباراة" + (rows.length > 300 ? "، نعرض أحدث 300" : "") + '</p><ul class="exl">' + rows.slice(0, 300).map(function(m){ var hw = m[5] > m[6], aw = m[6] > m[5]; return '<li><span class="muted small num">' + m[1] + '</span><span class="' + (hw ? "win" : "") + '">' + R.esc(nm(m[3])) + '</span><bdi dir="ltr" class="num sc">' + m[5] + "-" + m[6] + '</bdi><span class="' + (aw ? "win" : "") + '">' + R.esc(nm(m[4])) + '</span><span class="muted small">' + R.esc(CN[m[2]] || "") + "</span></li>"; }).join("") + "</ul>" : '<p class="empty">ما في نتايج بهالبحث.</p>'; }
    function load(){ out.innerHTML = '<p class="empty">نحمّل…</p>'; Promise.all([T ? Promise.resolve(T) : get("teams.json").then(function(t){ T = t.teams || {}; return T; }), get("archive/all/" + s.value + ".json")]).then(function(r){ cur = r[1]; var ids = {}; cur.matches.forEach(function(m){ ids[m[2]] = 1; }); var v = cs.value; cs.innerHTML = '<option value="">كل البطولات</option>' + Object.keys(ids).filter(function(k){ return CN[k]; }).map(function(k){ return '<option value="' + k + '">' + R.esc(CN[k]) + "</option>"; }).join(""); cs.value = ids[v] ? v : ""; draw(); }).catch(function(){ out.innerHTML = '<p class="empty">ما قدرنا نحمّل هالموسم.</p>'; }); }
    s.onchange = load; cs.onchange = draw; q.oninput = draw; load(); })();
  (function(){ var el = $("#bdays"); if (!el) return; var md = R.ymd(new Date().toISOString()).slice(5), yr = +R.ymd(new Date().toISOString()).slice(0, 4), items = [];
    try { var an = JSON.parse(el.dataset.an || "{}")[md] || []; an.forEach(function(a){ items.push("<li>ذكرى تأسيس " + '<a href="/t/' + a[0] + '/">' + R.esc(a[1]) + '</a> <span class="muted">(' + (yr - a[2]) + " سنة، من " + a[2] + ")</span></li>"); }); } catch (e){}
    function draw(){ if (items.length) el.innerHTML = '<section class="blk"><h2>اليوم في التقويم</h2><ul class="facts-l">' + items.join("") + "</ul></section>"; }
    get("players/birthdays/" + md + ".json").then(function(b){ (b.players || []).slice(0, 8).forEach(function(p){ var age = p.dob ? yr - +p.dob.slice(0, 4) : null; items.push("<li>عيد ميلاد " + (p.name_ar ? R.esc(p.name_ar) : '<span class="lat">' + R.esc(p.name) + "</span>") + (age ? ' <span class="muted">(' + age + " سنة)</span>" : "") + "</li>"); }); draw(); }).catch(draw); })();
  // ---- the journal (owner 2026-09-30): /news/ lists every story; .enews[data-e] on team and player pages lists that entity's
  //      stories (v1/news/e/<kind>-<id>.json), and [data-social] adds the official videos (v1/news/social/…). Rendered here, not
  //      prebuilt: the stories change every 15 minutes and the pages hourly.
  (function(){
    var KIND = { transfer:"انتقالات", injury:"إصابة", presser:"مؤتمر صحفي", statement:"تصريحات", official:"رسمي", match:"مباراة", other:"خبر" };
    var STAGE = { rumour:"إشاعة", talks:"مفاوضات", agreed:"اتفاق", here_we_go:"Here we go", official:"رسمي" };
    var HREF = { team:"/t/", player:"/p/", coach:"/coach/" };
    function ago(iso){ var m = Math.max(1, Math.round((Date.now() - Date.parse(iso)) / 6e4)); if (!isFinite(m)) return "";
      return m < 60 ? "قبل " + m + " دقيقة" : m < 1440 ? "قبل " + Math.round(m / 60) + " ساعة" : "قبل " + Math.round(m / 1440) + " يوم"; }
    function ent(e){ return e.name ? '<a href="' + HREF[e.kind] + e.id + '/">' + R.esc(e.name) + "</a>" : ""; }
    function card(s){
      var src = s.sources || [], first = src[0] || {}, ar = s.title_lang === "ar";
      var tag = KIND[s.kind] || "خبر"; if (s.kind === "transfer" && s.stage) tag += " · " + (STAGE[s.stage] || s.stage);
      var ents = (s.entities || []).map(ent).filter(Boolean).join("، ");
      return '<article class="nw' + (s.kind === "transfer" ? " tr" : "") + '"><p class="nk"><span class="tg">' + tag + '</span> <time datetime="' + R.esc(s.last_at || "") + '">' + ago(s.last_at) + "</time></p>" +
        "<h3" + (ar ? "" : ' dir="auto" class="lat"') + '><a href="' + R.esc(first.url || "#") + '" rel="noopener" target="_blank">' + R.esc(s.title) + "</a></h3>" +
        (s.summary ? '<p class="nsum">' + R.esc(s.summary) + "</p>" : "") + (ents ? '<p class="nent small">' + ents + "</p>" : "") +
        '<p class="nsrc small muted">' + (src.length > 1 ? src.length + " مصادر: " : "المصدر: ") + src.slice(0, 5).map(function(x){ return '<a href="' + R.esc(x.url) + '" rel="noopener" target="_blank">' + R.esc(x.name) + "</a>"; }).join(" · ") + "</p></article>"; }
    function vids(list){ return '<div class="nvid">' + list.map(function(v){ return '<a class="nv" href="' + R.esc(v.url) + '" rel="noopener" target="_blank">' + (v.image ? '<img src="' + R.esc(v.image) + '" alt="" loading="lazy" width="320" height="180">' : "") + '<span dir="auto">' + R.esc(v.title) + '</span><small class="muted">' + R.esc(v.channel) + (v.platform === "x" ? " على X" : " على يوتيوب") + " · " + ago(v.at) + "</small></a>"; }).join("") + "</div>"; }
    // the /news/ page: chips by kind, newest first
    var list = $("#nlist");
    if (list) get("news/latest.json").then(function(d){
      var all = d.stories || [], cur = "", chips = $("#nkinds"), have = {};
      all.forEach(function(s){ have[s.kind] = (have[s.kind] || 0) + 1; });
      chips.innerHTML = ['<button type="button" data-k="" aria-pressed="true">الكل</button>'].concat(["transfer", "injury", "presser", "statement", "official", "match"].filter(function(k){ return have[k]; }).map(function(k){ return '<button type="button" data-k="' + k + '" aria-pressed="false">' + KIND[k] + "</button>"; })).join("");
      function draw(){ var xs = all.filter(function(s){ return !cur || s.kind === cur; }); list.innerHTML = xs.length ? xs.map(card).join("") : '<p class="empty">ما في أخبار من هالنوع الحين.</p>'; }
      chips.onclick = function(e){ var b = e.target.closest("button[data-k]"); if (!b) return; cur = b.dataset.k; [].forEach.call(chips.children, function(c){ c.setAttribute("aria-pressed", String(c === b)); }); draw(); };
      draw();
    }).catch(function(){ list.innerHTML = '<p class="empty">ما قدرنا نحمّل الأخبار الحين.</p>'; });
    // a club's or a player's stories, plus its official videos
    [].forEach.call(document.querySelectorAll(".enews"), function(box){
      var e = box.dataset.e, so = box.dataset.social;
      Promise.all([e ? get("news/e/" + e + ".json").catch(function(){ return { stories:[] }; }) : Promise.resolve({ stories:[] }),
                   so ? get(so === "all" ? "news/social.json" : "news/social/" + so + ".json").catch(function(){ return { videos:[] }; }) : Promise.resolve({ videos:[] })]).then(function(r){
        var st = (r[0].stories || []).slice(0, 20), vs = (r[1].videos || []).slice(0, 12);
        if (!st.length && !vs.length){ if (box.dataset.quiet){ var sec = box.closest("section"); if (sec) sec.hidden = true; } else box.innerHTML = '<p class="empty">ما في أخبار عنه هالأيام. <a href="/news/">كل الأخبار</a></p>'; return; }
        if (so === "all"){ var sec2 = box.closest("section"); if (sec2) sec2.hidden = false; }
        box.innerHTML = (st.length ? '<div class="nwl">' + st.map(card).join("") + "</div>" : "") + (vs.length ? (so === "all" ? "" : "<h3 class=\"nvh\">من حساباته الرسمية</h3>") + vids(vs) : "") + (so === "all" ? "" : '<p class="small"><a href="/news/">كل الأخبار</a></p>');
      });
    });
  })();
  // ---- a club's full history (the «التاريخ» tab): v1/history/club/<id>.json from db/history.py, every match on demand
  (function(){
    var box = $(".chist"); if (!box) return;
    var id = box.dataset.club, D = null, pct = function(a, b){ return b ? Math.round(a / b * 100) : 0; };
    function nm(k){ return (D.names && D.names[k]) || k; }
    function link(k){ return /^\d+$/.test(String(k)) ? '<a href="/t/' + k + '/">' + R.esc(nm(String(k))) + "</a>" : R.esc(nm(String(k))); }
    function line(t){ return '<span class="num">' + t.p + "</span> مباراة · <b class=\"num\">" + t.w + '</b> فوز · <span class="num">' + t.d + '</span> تعادل · <span class="num">' + t.l + '</span> خسارة · <bdi dir="ltr" class="num">' + t.gf + "-" + t.ga + "</bdi>"; }
    function mrow(m){ return "<li><span class=\"num\">" + m[0] + "</span> " + (m[2] ? "" : "في ملعب ") + link(m[1]) + ' <bdi dir="ltr" class="num sc">' + m[3] + "-" + m[4] + '</bdi> <span class="muted small">' + R.esc((D.comps || {})[m[5]] || "") + "</span></li>"; }
    function opps(all, q){ var rows = D.opponents.filter(function(o){ return !q || nm(o[0]).indexOf(q) >= 0; }); var list = all || q ? rows : rows.slice(0, 20);
      return '<table class="tbl"><thead><tr><th>الخصم</th><th>لعب</th><th>فوز</th><th>تعادل</th><th>خسارة</th><th>له-عليه</th><th>آخر مرة</th></tr></thead><tbody>' + list.map(function(o){ return "<tr><td>" + link(o[0]) + '</td><td class="num">' + o[1] + '</td><td class="num">' + o[2] + '</td><td class="num">' + o[3] + '</td><td class="num">' + o[4] + '</td><td class="num"><bdi dir="ltr">' + o[5] + "-" + o[6] + '</bdi></td><td class="num">' + (o[7] || "").slice(0, 4) + "</td></tr>"; }).join("") + "</tbody></table>"; }
    function draw(){
      var T = D.total, dec = Object.keys(D.by_decade), dm = Math.max.apply(null, dec.map(function(k){ return D.by_decade[k].p; }).concat([1]));
      var bars = dec.map(function(k, i){ var v = D.by_decade[k], h = pct(v.w, v.p); return '<g><rect x="' + (i * 22 + 2) + '" y="' + (62 - h * 0.55).toFixed(1) + '" width="18" height="' + (h * 0.55).toFixed(1) + '" class="dw"><title>' + k + ": " + h + "% فوز من " + v.p + '</title></rect><text x="' + (i * 22 + 11) + '" y="72" class="ax">' + k.slice(2) + '</text><text x="' + (i * 22 + 11) + '" y="' + (58 - h * 0.55).toFixed(1) + '" class="ax">' + h + "</text></g>"; }).join("");
      box.innerHTML = '<p class="hl">من <b class="num">' + D.since.slice(0, 4) + "</b>: " + line(T) + " · نسبة الفوز <b class=\"num\">" + pct(T.w, T.p) + "٪</b></p>" +
        '<h3>نسبة الفوز في كل عقد</h3><svg class="chart dec" viewBox="0 0 ' + (dec.length * 22 + 4) + ' 76" role="img" aria-label="نسبة الفوز في كل عقد">' + bars + "</svg>" +
        "<h3>في كل بطولة</h3><ul class=\"mlist\">" + Object.keys(D.by_comp).sort(function(a, b){ return D.by_comp[b].p - D.by_comp[a].p; }).map(function(c){ return "<li><b>" + R.esc((D.comps || {})[c] || c) + "</b>: " + line(D.by_comp[c]) + "</li>"; }).join("") + "</ul>" +
        '<h3>ضد كل خصم (<span class="num">' + D.opponents.length + '</span>)</h3><input type="search" class="hq" placeholder="دوّر على خصم" aria-label="دوّر على خصم"><div class="hopp">' + opps(false) + "</div>" + (D.opponents.length > 20 ? '<button type="button" class="lnk hall">كل الخصوم</button>' : "") +
        '<div class="hbig"><div><h3>أكبر انتصاراته</h3><ul class="mlist">' + D.biggest_wins.map(mrow).join("") + '</ul></div><div><h3>أكبر خساراته</h3><ul class="mlist">' + D.biggest_losses.map(mrow).join("") + "</ul></div></div>" +
        "<p>أول مباراة عندنا: " + mrow(D.first).replace(/^<li>|<\/li>$/g, "") + '</p><p><button type="button" class="btn hmatch">كل مبارياته (<span class="num">' + T.p + "</span>)</button></p><div class=\"hml\"></div>" +
        '<p class="src">النتايج من الدرجة الأولى والبطولات القارية: قاعدة schochastics/football-data لين ' + R.esc((D.source.match(/\d{4}-\d{2}-\d{2}/) || [""])[0]) + "، وبعدها أرشيف تيفو. الكؤوس المحلية والدرجات الأدنى مب داخلة.</p>";
      var q = box.querySelector(".hq"), all = false;
      q.oninput = function(){ box.querySelector(".hopp").innerHTML = opps(all, q.value.trim()); };
      var ha = box.querySelector(".hall"); if (ha) ha.onclick = function(){ all = true; ha.remove(); box.querySelector(".hopp").innerHTML = opps(true, q.value.trim()); };
      box.querySelector(".hmatch").onclick = function(){ var b = this; b.disabled = true; get("history/club/" + id + "/matches.json").then(function(x){ var ms = x.matches.slice().reverse(), shown = 200;
        function more(){ box.querySelector(".hml").innerHTML = '<ul class="mlist hms">' + ms.slice(0, shown).map(mrow).join("") + "</ul>" + (shown < ms.length ? '<button type="button" class="lnk hmore">أقدم</button>' : ""); var hm = box.querySelector(".hmore"); if (hm) hm.onclick = function(){ shown += 400; more(); }; }
        more(); b.remove(); }).catch(function(){ b.disabled = false; }); };
    }
    get("history/club/" + id + ".json").then(function(d){ D = d; draw(); }).catch(function(){});
  })();
  // ---- a national team's Elo rating through its history (v1/history/elo/<id>.json, db/elo_nations.py)
  (function(){
    var box = $(".elo"); if (!box) return;
    get("history/elo/" + box.dataset.team + ".json").then(function(d){
      var S = d.series, W = 600, H = 170, t0 = Date.parse(S[0][0]), t1 = Date.parse(S[S.length - 1][0]), lo = Math.min.apply(null, S.map(function(x){ return x[1]; })), hi = Math.max.apply(null, S.map(function(x){ return x[1]; }));
      var X = function(dt){ return (8 + (Date.parse(dt) - t0) / Math.max(1, t1 - t0) * (W - 16)).toFixed(1); }, Y = function(r){ return (H - 18 - (r - lo) / Math.max(1, hi - lo) * (H - 34)).toFixed(1); };
      var path = S.map(function(x, i){ return (i ? "L" : "M") + X(x[0]) + " " + Y(x[1]); }).join("");
      var y0 = +S[0][0].slice(0, 4), y1 = +S[S.length - 1][0].slice(0, 4), step = Math.max(10, Math.round((y1 - y0) / 6 / 10) * 10), ticks = [];
      for (var y = Math.ceil(y0 / step) * step; y <= y1; y += step) ticks.push('<text x="' + X(y + "-01-01") + '" y="' + (H - 3) + '" class="ax">' + y + "</text>");
      box.innerHTML = '<section class="blk"><h2>تصنيف إيلو عبر التاريخ <small>من ' + y0 + "</small></h2>" +
        '<p>الحين <b class="num">' + d.now[1] + '</b> والمركز <b class="num">' + d.now[2] + '</b> عالمياً. أعلى تصنيف <b class="num">' + d.peak[1] + '</b> في <span class="num">' + d.peak[0].slice(0, 4) + '</span>، وأدناه <span class="num">' + d.low[1] + '</span> في <span class="num">' + d.low[0].slice(0, 4) + "</span>.</p>" +
        '<svg class="chart elo-c" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="تصنيف إيلو عبر السنين"><path d="' + path + '" class="gl2"/><circle cx="' + X(d.peak[0]) + '" cy="' + Y(d.peak[1]) + '" r="3.5" class="pk"/>' + ticks.join("") + "</svg>" +
        '<p class="small muted">إيلو يرتفع مع كل فوز وينزل مع كل خسارة، وقدر التغيير حسب قوة الخصم وأهمية المباراة. أدق من تصنيف فيفا لمقارنة الأجيال.</p><p class="src">المصدر: eloratings.net.</p></section>';
    }).catch(function(){});
  })();
  // ---- a club's expected goals season by season (Understat, db/understat.py)
  (function(){
    var box = $(".cxg"); if (!box) return;
    get("history/xg/" + box.dataset.club + ".json").then(function(d){
      var S = d.seasons; if (!S || !S.length) return;
      var f1 = function(v){ return (Math.round(v * 10) / 10).toFixed(1); }, luck = S.map(function(r){ return r[6] - r[7]; }), best = luck.indexOf(Math.max.apply(null, luck)), worst = luck.indexOf(Math.min.apply(null, luck));
      box.innerHTML = '<section class="blk"><h2>الأهداف المتوقعة موسم بموسم <small>من ' + S[0][0].slice(0, 4) + "</small></h2>" +
        '<p>أكثر موسم حصد فيه نقاط فوق المتوقع: <b class="num">' + S[best][0] + '</b> (<bdi dir="ltr" class="num">+' + f1(luck[best]) + '</bdi> نقطة)، وأكثر موسم تحت المتوقع: <b class="num">' + S[worst][0] + '</b> (<bdi dir="ltr" class="num">' + f1(luck[worst]) + "</bdi>).</p>" +
        '<table class="tbl"><thead><tr><th>الموسم</th><th>أهداف</th><th>المتوقع</th><th>عليه</th><th>المتوقع عليه</th><th>نقاط</th><th>النقاط المتوقعة</th><th>الضغط</th></tr></thead><tbody>' +
        S.slice().reverse().map(function(r){ return '<tr><td class="num">' + r[0] + '</td><td class="num">' + r[4] + '</td><td class="num">' + f1(r[2]) + '</td><td class="num">' + r[5] + '</td><td class="num">' + f1(r[3]) + '</td><td class="num">' + r[6] + '</td><td class="num">' + f1(r[7]) + '</td><td class="num">' + (r[8] == null ? "—" : r[8]) + "</td></tr>"; }).join("") +
        '</tbody></table><p class="small muted">«الضغط» كم تمريرة يخلّي الخصم يمرّرها قبل كل محاولة افتكاك: كل ما قلّ الرقم زاد الضغط.</p><p class="src">المصدر: Understat.</p></section>';
    }).catch(function(){});
  })();
  function run(){ var f = { home:home, comp:comp, match:match, team:team, tv:tv, studio:studio, daypage:daypage, arabs:arabs }[PAGE]; if (f) f().catch(function(){}); if (PAGE === "team" && Object.keys(window.NAT || {}).some(function(k){ return String(window.NAT[k]) === ID; })) countdown(); }
  tvFull();
  tabs(); run(); dist();
})();

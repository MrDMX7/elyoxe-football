/* تيفو «منو يعلّق؟» (owner 2026-09-30): the channel and the commentator of each match, read from /v1/tv/<yyyymmdd>.json
   (news/commentators.py: Kooora's daily list matched to our fixtures, one file per UAE day, refreshed on the Fold every 15 min)
   and painted here, so a new list shows without a rebuild. Self-contained (its own few CSS rules), loaded after app.js:
   - match page: «منو يعلّق؟» right under «وين تنقل» (#wwbox) before and during the match, and one line in the hero (#mh)
   - day lists (home «اليوم», /today/, /tomorrow/): a quiet «🎙 name · channel» line under each row that has one
   - /commentators/ (#tvall): who calls which match today and tomorrow
   The visitor's own country's channel comes first (tifo.country, or the browser's time zone). Nothing to show = nothing drawn. */
(function(){
  "use strict";
  var R = window.TR || {}, B = document.body, PAGE = B.dataset.page, FILES = {}, TV = {}, FX = {}, V5 = !!B.dataset.v5;   // v5 (body[data-v5]): rows are a.mr, /all/ is the home list
  var esc = R.esc || function(s){ return String(s == null ? "" : s).replace(/[&<>"']/g, function(c){ return { "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]; }); };
  var $ = function(s){ return document.querySelector(s); };
  function ymdOf(t){ var n = Date.parse(t); return isNaN(n) ? "" : new Date(n + 4 * 3600e3).toISOString().slice(0, 10).replace(/-/g, ""); }   // the files are UAE days
  function uaeYmd(off){ return new Date(Date.now() + 4 * 3600e3 + (off || 0) * 864e5).toISOString().slice(0, 10).replace(/-/g, ""); }
  function file(ymd){ if (!ymd || ymd < "20260930") return Promise.resolve(null);   // the first file is 30 September 2026: older days would only 403
    return FILES[ymd] || (FILES[ymd] = fetch("/v1/tv/" + ymd + ".json", { cache:"no-cache" }).then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; }).then(function(d){
    if (d && d.matches) Object.keys(d.matches).forEach(function(k){ TV[k] = d.matches[k]; if (d.fixtures && d.fixtures[k]) FX[k] = d.fixtures[k]; }); return d; })); }
  function cc(){ try { var c = localStorage.getItem("tifo.country"); if (c) return c; } catch (e){} try { var tz = Intl.DateTimeFormat().resolvedOptions().timeZone, hit = (R.COUNTRIES || []).filter(function(c){ return c[2] === tz; })[0]; return hit ? hit[0] : "xx"; } catch (e){ return "xx"; } }
  // the visitor's country first, then the pan-Arab networks (beIN, شاهد…), then the other countries' channels; a named voice before «not announced»
  function sorted(es){ var c = cc(), rk = function(e){ return (e.country === c ? 0 : !e.country ? 1 : 2) + (e.commentator ? 0 : 0.5); }; return es.map(function(e, i){ return [rk(e), i, e]; }).sort(function(a, b){ return a[0] - b[0] || a[1] - b[1]; }).map(function(x){ return x[2]; }); }
  function voices(e){ var n = e.commentators && e.commentators.length ? e.commentators : e.commentator ? [e.commentator] : []; return n.map(esc).join(" و"); }
  function lead(es){ var s = sorted(es || []); return s.filter(function(e){ return e.commentator; })[0] || s[0] || null; }
  function done(m){ return m && m.status === "finished"; }

  // ---- styles (v3 tokens, with fallbacks so the block reads right on any skin)
  (function(){ if (document.getElementById("tvcss")) return; var st = document.createElement("style"); st.id = "tvcss";
    st.textContent = ".tvh{margin:.6rem 0 0;font-size:.86rem;color:var(--tert,#B9C7C0);line-height:1.5}.tvh b{color:var(--ink,#F6F7F2);font-weight:600}" +
      ".tvc .tvl{list-style:none;margin:0;padding:0}.tvc .tvl li{display:flex;flex-wrap:wrap;align-items:baseline;gap:.15rem .7rem;padding:.5rem 0;border-block-end:1px dashed var(--line,#F6F7F22B)}.tvc .tvl li:last-child{border-block-end:0}" +
      ".tvc .tvn b{font-weight:600;color:var(--ink,#F6F7F2)}.tvc .tvv{color:var(--tert,#B9C7C0)}.tvc .tvv b{color:var(--ink,#F6F7F2);font-weight:600}.tvc .src{margin-block-start:.6rem}" +
      ".m .tvr{grid-column:1/-1;justify-self:center;font-size:.75rem;color:var(--tert,#B9C7C0);line-height:1.3;margin-block-start:-.2rem;text-align:center}" +
      ".mr .tvr{grid-column:1/-1;justify-self:center;font-size:12px;color:var(--label-2,#8E8E93);line-height:1.3;margin-block-start:-2px;text-align:center}.tvc .card{padding:4px 16px}.tvc .src{font-size:12px;color:var(--label-2,#8E8E93)}" +
      "#tvall h2{margin-block:1.6rem .6rem}#tvall .tvp{list-style:none;margin:0;padding:0}#tvall .tvp>li{padding:.6rem 0;border-block-end:1px solid var(--line-2,#F6F7F214)}#tvall .tvp>li>b{display:block;font-size:1rem;margin-block-end:.25rem}" +
      "#tvall .tvp ul{list-style:none;margin:0;padding:0;font-size:.88rem;color:var(--tert,#B9C7C0)}#tvall .tvp ul li{padding:.1rem 0}#tvall .tvp a{color:var(--ink,#F6F7F2)}";
    document.head.appendChild(st); })();

  // ---- match page (and /live/?id=): one line under the scoreboard, the block under «وين تنقل»
  function heroLine(es, md, after){
    var top = lead(es), h = $("#tvh"); if (!top || !after) return;
    var line = done(md) ? (top.commentator ? "📺 علّق عليها " + voices(top) + " على <b>" + esc(top.channel) + "</b>" : "")
      : "📺 <b>" + esc(top.channel) + "</b>" + (top.commentator ? " · " + (top.commentators && top.commentators.length > 1 ? "المعلقين: " : "المعلق: ") + voices(top) : "");
    if (!line){ if (h) h.remove(); return; }
    if (!h){ h = document.createElement("p"); h.className = "tvh"; h.id = "tvh"; after.insertAdjacentElement("afterend", h); }   // a sibling: the scoreboard is redrawn, this line stays
    if (h._h !== line){ h._h = line; h.innerHTML = line; }
  }
  function paintMatch(es, md){
    if (!es || !es.length) return;
    heroLine(es, md, $("#mh"));
    var ww = $("#wwbox"), box = $("#tvc");
    if (!ww || done(md)){ if (box) box.remove(); return; }   // after full time the hero line is enough
    var rows = sorted(es).map(function(e){ var n = voices(e); return '<li><span class="tvn">📺 <b>' + esc(e.channel) + '</b></span><span class="tvv">' + (n ? (e.commentators && e.commentators.length > 1 ? "المعلقين: " : "المعلق: ") + "<b>" + n + "</b>" : "المعلق ما انعلن للحين") + "</span></li>"; }).join("");
    var sched = es.every(function(e){ return e.from === "schedules"; });   // the channel only, from two schedules that agree
    var html = '<h2 id="tvct">منو يعلّق؟<small>القناة والمعلق</small></h2><ul class="tvl">' + rows + '</ul><p class="src">' + (sched ? "القناة اتفق عليها جدول كووورة وجدول يلا كورة، والمعلق يبان يوم المباراة." : "من جدول القنوات الناقلة والمعلقين اللي ينشره كووورة كل يوم، وممكن يتغيّر قبل المباراة.") + ' <a href="/commentators/">كل معلقين اليوم</a></p>';
    if (V5) html = '<div class="gh"><h2 id="tvct">منو يعلّق؟</h2><span class="ghs">القناة والمعلق</span></div><div class="card lc"><ul class="tvl">' + rows + "</ul>" + html.slice(html.indexOf('<p class="src">')) + "</div>";   // v5: a grouped list
    if (!box){ box = document.createElement("section"); box.className = V5 ? "grp tvc" : "blk tvc"; box.id = "tvc"; box.setAttribute("aria-labelledby", "tvct"); ww.insertAdjacentElement("afterend", box); }   // a sibling: app.js rewrites #wwbox for other countries
    if (box._h !== html){ box._h = html; box.innerHTML = html; }
  }
  if (PAGE === "match"){
    var ID = B.dataset.id, MD = {}; try { MD = JSON.parse(($("#msum") || {}).textContent || "{}"); } catch (e){}
    var y = ymdOf(MD.kickoff_utc || MD.kickoff_uae);
    if (ID && y) file(y).then(function(){ paintMatch(TV[ID], MD); });
    document.addEventListener("tifo:match", function(e){ var m = e.detail || {}; MD = Object.assign({}, MD, m); if (TV[ID]) paintMatch(TV[ID], MD); });
    document.addEventListener("tifo:country", function(){ if (TV[ID]) paintMatch(TV[ID], MD); });
  }

  // ---- day lists: one quiet line under each row whose match has a named voice (or a numbered channel)
  function decorate(root){
    (root || document).querySelectorAll("a.m[data-mid],a.mr[data-mid]").forEach(function(a){
      var es = TV[a.dataset.mid], old = a.querySelector(".tvr"), e = es && lead(es), html = "";
      if (e && (e.commentator || /\d/.test(e.channel))) html = e.commentator ? "🎙 " + voices(e) + " · " + esc(e.channel) : "📺 " + esc(e.channel);
      if (!html){ if (old) old.remove(); return; }
      if (old && old._h === html) return;
      if (!old){ old = document.createElement("span"); old.className = "tvr"; a.appendChild(old); }
      old._h = html; old.innerHTML = html;
      var lb = a.getAttribute("aria-label"); if (lb && e.commentator && lb.indexOf("المعلق") < 0) a.setAttribute("aria-label", lb + "، المعلق " + (e.commentators || [e.commentator]).join(" و"));
    });
  }
  function watch(sel, fn){ var el = $(sel); if (!el || !("MutationObserver" in window)) return; var q = false;
    new MutationObserver(function(){ if (q) return; q = true; setTimeout(function(){ q = false; (fn || decorate)(el); }, 30); }).observe(el, { childList:true, subtree:true }); }   // not rAF: a hidden tab never runs it, and redraws land there too
  if (PAGE === "home" || PAGE === "daypage" || (V5 && PAGE === "all")){
    var first = PAGE === "daypage" && /\/tomorrow\//.test(location.pathname) ? [uaeYmd(1)] : [uaeYmd(0), uaeYmd(1)];
    Promise.all(first.map(file)).then(function(){ decorate(document); });
    ["#day", "#mine", "#homelist", "#minehome", "#world"].forEach(function(s){ watch(s); });
    // home: the list follows the visitor's day (and the ‹ › buttons); load the UAE days those matches fall on
    document.addEventListener("tifo:day", function(e){ var ms = (e.detail && e.detail.ms) || [], ds = {}; ms.forEach(function(m){ var k = ymdOf(m.kickoff_utc || m.kickoff_uae); if (k) ds[k] = 1; });
      Promise.all(Object.keys(ds).map(file)).then(function(){ decorate(document); }); });
    document.addEventListener("tifo:country", function(){ decorate(document); });
  }
  // /all/ (every match of the day, src/allmatches.js): rows are redrawn on a day switch (?d=yesterday|tomorrow), every live
  // refresh and when a league opens; the same quiet line, for the day the page shows. /live/?id=: the hero line.
  var OFFS = { yesterday:-1, today:0, tomorrow:1, "-1":-1, "0":0, "1":1 };
  if (PAGE === "all" && !V5){
    var allDay = function(){ var q = new URLSearchParams(location.search).get("d"); return uaeYmd(OFFS[q] != null ? OFFS[q] : 0); };
    var allPaint = function(el){ file(allDay()).then(function(){ decorate(el || document); }); };
    allPaint(); watch("#alllist", allPaint);
    document.addEventListener("tifo:country", function(){ allPaint(); });
  }
  if (PAGE === "live"){
    var qs = new URLSearchParams(location.search), LID = (qs.get("id") || "").trim(), LD = qs.get("d");
    Promise.all((/^\d{8}$/.test(LD || "") ? [LD] : [uaeYmd(0), uaeYmd(-1), uaeYmd(1)]).map(file)).then(function(){ if (TV[LID]) heroLine(TV[LID], {}, $("#lvh")); });
  }

  // ---- /commentators/: today and tomorrow, one row per voice with the matches they call
  var all = $("#tvall");
  if (all){
    var days = [uaeYmd(0), uaeYmd(1)], words = ["اليوم", "بكرة"];
    Promise.all(days.map(file)).then(function(docs){
      var out = docs.map(function(d, i){
        var per = {}, order = [];
        Object.keys((d && d.matches) || {}).forEach(function(mid){ var f = (d.fixtures || {})[mid] || {}; (d.matches[mid] || []).forEach(function(e){
          (e.commentators && e.commentators.length ? e.commentators : e.commentator ? [e.commentator] : []).forEach(function(n){
            if (!per[n]){ per[n] = []; order.push(n); }
            var same = per[n].filter(function(x){ return x.mid === mid; })[0];   // one voice on شاهد and MBC Action: one line, both channels
            if (same) same.ch += "، " + e.channel; else per[n].push({ mid:mid, f:f, ch:e.channel }); }); }); });
        if (!order.length) return "<h2>" + words[i] + "</h2><p class=\"muted\">" + (i ? "جدول بكرة ينزل عادة بعد نص الليل بتوقيت الإمارات." : "ما نزل جدول المعلقين لهاليوم للحين.") + "</p>";
        order.forEach(function(n){ per[n].sort(function(a, b){ return String(a.f.ko).localeCompare(String(b.f.ko)); }); });
        order.sort(function(a, b){ return String(per[a][0].f.ko).localeCompare(String(per[b][0].f.ko)) || a.localeCompare(b, "ar"); });
        var tm = function(ko){ return R.hhmm ? R.hhmm(ko) : new Date(ko).toLocaleTimeString("ar-AE-u-nu-latn", { hour:"2-digit", minute:"2-digit" }); };
        return "<h2>" + words[i] + "</h2><ul class=\"tvp\">" + order.map(function(n){ return "<li><b>🎙 " + esc(n) + "</b><ul>" + per[n].map(function(x){ return '<li><a href="/m/' + esc(x.mid) + '/">' + esc(x.f.home || "") + " ضد " + esc(x.f.away || "") + '</a> · <span class="num">' + (x.f.ko ? esc(tm(x.f.ko)) : "") + "</span> · " + esc(x.ch) + (x.f.comp ? ' <span class="small">(' + esc(x.f.comp) + ")</span>" : "") + "</li>"; }).join("") + "</ul></li>"; }).join("") + "</ul>";
      }).join("");
      all.innerHTML = out + '<p class="src">المصدر: جدول القنوات الناقلة والمعلقين اللي ينشره كووورة كل يوم، مربوط بمباريات تيفو. المواعيد بتوقيت بلدك.</p>';
      if (R.localize) R.localize(all);
    });
  }
})();

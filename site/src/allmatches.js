/* تيفو: every match of the day (/all/) and a live page for any match (/live/?id=) — owner 2026-09-30 «اريد الموقع شامل
   اي مباراة او احصائية او شي يصير علطول ينلقى في موقعنا».
   /all/   v1/all/<ymd>.json (the poller: FotMob's whole day list + 365Scores' Arab leagues, ours first), the live rows
           from v1/all/live.json every 30 s; أمس / اليوم / بكرة, «مباشر الحين», search by team, leagues fold.
           Our competitions open /m/<id>/, the others /live/?id=, 365Scores' games /db/game/?id=.
   /live/  /api/tifo/match?id= (saas/cards: FotMob matchDetails in the poller's shape, goals with how they went in),
           drawn with the match page's own renderers (render.js), every 30 s while live.
   Self-contained: this file, src/allmatches.css and the two page shells in build.cjs. */
(function(){
  "use strict";
  var R = window.TR, box = document.getElementById("allm"); if (!R || !box) return;
  var $ = function(s, r){ return (r || document).querySelector(s); }, esc = R.esc, V = "/v1/", kind = box.dataset.kind;
  var S365 = "https://imagecache.365scores.com/image/upload/f_png,w_48,h_48,c_limit,q_auto:eco,dpr_2,d_Competitors:default1.png/v1/Competitors/";
  var LIVE = { live:1, ht:1 }, ARAB = "UAE KSA QAT KUW BHR OMA IRQ JOR SYR LBN LIB PLE YEM EGY SUD LBY TUN ALG MAR MTN SOM DJI COM".split(" ");
  function get(u){ return fetch(u).then(function(r){ if (!r.ok){ var e = new Error(r.status); e.status = r.status; throw e; } return r.json(); }); }
  function store(k, v){ try { if (v === undefined) return JSON.parse(localStorage.getItem(k) || "null"); localStorage.setItem(k, JSON.stringify(v)); } catch (e){ return null; } }
  function uaeYmd(off){ return new Date(Date.now() + 4 * 3600e3 + (off || 0) * 864e5).toISOString().slice(0, 10).replace(/-/g, ""); }
  // a UTC instant as a "+04:00" ISO string: what R.chip / R.tt expect (kickoff_uae), shown in the visitor's own time zone
  function uaeIso(utc){ if (!utc) return null; var d = new Date(Date.parse(utc) + 4 * 3600e3).toISOString(); return d.slice(0, 19) + "+04:00"; }
  function fold(s){ return String(s || "").toLowerCase().replace(/[أإآ]/g, "ا").replace(/ة/g, "ه").replace(/ى/g, "ي").replace(/[ً-ْـ]/g, "").replace(/\s+/g, " ").trim(); }
  var timers = {}; function later(k, fn, ms){ clearTimeout(timers[k]); timers[k] = setTimeout(function(){ if (document.hidden){ later(k, fn, ms); return; } fn(); }, ms); }

  // ================================================================ /all/
  if (kind === "all"){
    var q0 = new URLSearchParams(location.search), OFF = { yesterday:-1, today:0, tomorrow:1, "-1":-1, "0":0, "1":1 };
    var st = { off:OFF[q0.get("d")] != null ? OFF[q0.get("d")] : 0, live:q0.get("live") === "1", q:"", doc:null, lv:{}, keys:{}, open:store("tifo.allopen") || {} };
    var list = $("#alllist"), liveBtn = $("#alllive"), qIn = $("#allq"), seg = $("#allday"), info = $("#alln");
    get(V + "index.json").then(function(ix){ (ix.competitions || []).forEach(function(c){ st.keys[c.id] = c.key; }); if (st.doc) draw(); }).catch(function(){});
    function ymd(){ return uaeYmd(st.off); }
    function merged(m){ var l = st.lv[m.id]; if (!l) return m; var o = {}; for (var k in m) o[k] = m[k]; ["status", "minute", "home", "away", "pen", "sd"].forEach(function(k){ if (k in l) o[k] = l[k]; else if (k === "minute" || k === "pen" || k === "sd") delete o[k]; }); return o; }
    function href(m){ var id = String(m.id); if (id.indexOf("365:") === 0) return "/db/game/?id=" + id.slice(4); return m.ours ? "/m/" + id + "/" : "/live/?id=" + id + "&d=" + ymd(); }
    // crests: ours are self-hosted (/logo/96/, the build downloads them); FotMob's are never hotlinked (build.cjs: the visitor's
    // referer would go to FotMob), so the other FotMob rows go without; 365Scores' as the encyclopedia shows them
    function logo(t, own){ var id = String(t[0] || ""); if (!id) return "";
      if (id.indexOf("365:") === 0) return '<img class="logo" src="' + S365 + id.slice(4) + '" alt="" width="24" height="24" loading="lazy" onerror="this.style.visibility=\'hidden\'">';
      return own ? '<img class="logo" src="/logo/96/' + id + '.webp" alt="" width="24" height="24" loading="lazy" onerror="if(!this.dataset.f){this.dataset.f=1;this.src=\'/logo/' + id + '.png\'}else this.style.display=\'none\'">' : ""; }
    function team(t, own, cls){ var reds = t[3] ? '<i class="alred" title="طرد" aria-label="' + t[3] + ' طرد"></i>' : "";
      return '<span class="t ' + cls + '">' + logo(t, own) + "<span>" + esc(t[1] || "") + reds + "</span></span>"; }
    function row(m0, lg){ var m = merged(m0), s = m.status, has = m.home.length > 2 && m.away.length > 2 && m.home[2] != null && m.away[2] != null;
      var mm = { status:s, score:has ? { home:m.home[2], away:m.away[2] } : null, minute:m.minute, penalties:m.pen ? { home:m.pen[0], away:m.pen[1] } : null, status_detail:m.sd, kickoff_uae:uaeIso(m.utc), time_tbd:!!m.tbd };
      var fin = s === "finished" && has, hw = fin && m.home[2] > m.away[2], aw = fin && m.away[2] > m.home[2];
      var own = !!(lg.ours || m.ours);
      return '<a class="m' + (LIVE[s] ? " live" : "") + '" href="' + href(m) + '" data-mid="' + esc(m.id) + '">' + team(m.home, own, "h" + (hw ? " win" : aw ? " lose" : "")) + R.chip(mm, {}) + team(m.away, own, "a" + (aw ? " win" : hw ? " lose" : "")) + "</a>"; }
    function rows(lg, ms){ var out = "", cur = null;
      if (ms.some(function(m){ return m.g; })) ms = ms.slice().sort(function(a, b){ return String(a.g || "").localeCompare(String(b.g || ""), "en", { numeric:true }) || String(a.utc || "").localeCompare(String(b.utc || "")); });
      ms.forEach(function(m){ var g = m.g || ""; if (g !== cur){ cur = g; if (g) out += '<p class="grp-sub">' + esc(/^[A-Za-z0-9]{1,2}$/.test(g) ? R.groupOrd(g) : R.stageAr(g)) + "</p>"; } out += row(m, lg); });
      var link = lg.ours && st.keys[lg.id] ? '<a class="alk" href="/c/' + st.keys[lg.id] + '/">صفحة البطولة ←</a>' : String(lg.id).indexOf("365:") === 0 ? '<a class="alk" href="/db/league/?id=' + String(lg.id).slice(4) + '">البطولة في الموسوعة ←</a>' : "";
      return out + link; }
    function isArab(lg){ return ARAB.indexOf(lg.cc) >= 0 || lg.src === "365"; }
    function draw(){
      var doc = st.doc; if (!doc) return;
      var q = fold(st.q), n = 0, nl = 0, liveN = 0, html = "";
      doc.leagues.forEach(function(lg){
        var ms = lg.matches.map(merged), lgName = lg.name_ar || lg.name, hitL = q && (fold(lgName).indexOf(q) >= 0 || fold(lg.country_ar).indexOf(q) >= 0 || fold(lg.name).indexOf(q) >= 0);
        ms.forEach(function(m){ if (LIVE[m.status]) liveN++; });
        var show = ms.filter(function(m){ if (st.live && !LIVE[m.status]) return false; if (q && !hitL && fold(m.home[1]).indexOf(q) < 0 && fold(m.away[1]).indexOf(q) < 0) return false; return true; });
        if (!show.length) return;
        n += show.length; nl++;
        var lv = show.filter(function(m){ return LIVE[m.status]; }).length, key = String(lg.id);
        var open = q || st.live ? true : key in st.open ? !!st.open[key] : !!(lg.ours || lv || isArab(lg));
        html += '<details class="alg' + (lg.ours ? " ours" : "") + '" data-lg="' + esc(key) + '"' + (open ? " open" : "") + '><summary><span class="aln">' + esc(lgName) + "</span>" + (lg.country_ar ? '<span class="alc">' + esc(lg.country_ar) + "</span>" : "") +
          (lv ? '<span class="alglive"><i class="cardflip"></i>' + lv + " مباشر</span>" : "") + '<span class="aln2 num">' + show.length + "</span></summary>" + (open ? '<div class="algb">' + rows(lg, show) + "</div>" : "") + "</details>";
      });
      list.innerHTML = html || '<p class="empty">' + (st.live ? "ما في مباريات مباشرة الحين." : q ? "ما لقينا فريق بهالاسم في مباريات هاليوم." : "ما في مباريات في هاليوم.") + "</p>";
      if (R.localize) R.localize(list);
      liveBtn.querySelector("b").textContent = liveN ? liveN : "";
      liveBtn.disabled = !liveN && !st.live;
      info.innerHTML = '<span class="num">' + n.toLocaleString("en") + "</span> مباراة في <span class=\"num\">" + nl.toLocaleString("en") + "</span> بطولة" + (liveN ? '، منها <b class="num">' + liveN + "</b> مباشر الحين" : "");
      // a league opened for the first time gets its rows then (a closed league renders only its summary line)
      list.querySelectorAll("details.alg").forEach(function(d){ d.addEventListener("toggle", function(){
        if (!d.open || d.querySelector(".algb")) return; var k = d.dataset.lg, lg = st.doc.leagues.filter(function(x){ return String(x.id) === k; })[0];
        if (lg){ var ms = lg.matches.map(merged).filter(function(m){ return !st.live || LIVE[m.status]; }); d.insertAdjacentHTML("beforeend", '<div class="algb">' + rows(lg, ms) + "</div>"); if (R.localize) R.localize(d); } }); });
    }
    // what the visitor opens or folds is remembered (this browser only); leagues opened by a search or «مباشر الحين» are not
    list.addEventListener("click", function(e){ var s = e.target.closest && e.target.closest("summary"); if (!s || st.q || st.live) return; var d = s.parentNode;
      setTimeout(function(){ st.open[d.dataset.lg] = d.open ? 1 : 0; store("tifo.allopen", st.open); }, 0); });
    function url(){ var p = new URLSearchParams(); if (st.off) p.set("d", st.off < 0 ? "yesterday" : "tomorrow"); if (st.live) p.set("live", "1"); var s = p.toString(); try { history.replaceState(null, "", location.pathname + (s ? "?" + s : "")); } catch (e){} }
    function load(){
      var y = ymd(); list.setAttribute("aria-busy", "true");
      return get(V + "all/" + y + ".json").then(function(doc){ if (y !== ymd()) return; st.doc = doc; list.removeAttribute("aria-busy"); draw(); if (st.off === 0) later("doc", load, 120e3); })
        .catch(function(){ if (y !== ymd()) return; list.removeAttribute("aria-busy"); if (!st.doc || st.doc.date !== y) list.innerHTML = '<p class="empty">ما قدرنا نجيب مباريات هاليوم الحين، نحاول مرة ثانية…</p>'; later("doc", load, 30e3); });
    }
    function live(){
      get(V + "all/live.json").then(function(lv){ var by = {}; (lv.matches || []).forEach(function(r){ by[r.id] = r; }); st.lv = by; draw(); }).catch(function(){}).then(function(){ later("live", live, 30e3); });
    }
    seg.addEventListener("click", function(e){ var b = e.target.closest("button[data-d]"); if (!b) return; st.off = +b.dataset.d; seg.querySelectorAll("button").forEach(function(x){ x.setAttribute("aria-pressed", x === b ? "true" : "false"); }); st.doc = null; list.innerHTML = '<p class="empty">نحمّل…</p>'; url(); load(); });
    seg.querySelectorAll("button").forEach(function(x){ x.setAttribute("aria-pressed", +x.dataset.d === st.off ? "true" : "false"); });
    liveBtn.setAttribute("aria-pressed", st.live ? "true" : "false");
    liveBtn.addEventListener("click", function(){ st.live = !st.live; liveBtn.setAttribute("aria-pressed", st.live ? "true" : "false"); url(); draw(); });
    var qt = null; qIn.addEventListener("input", function(){ clearTimeout(qt); qt = setTimeout(function(){ st.q = qIn.value; draw(); }, 120); });
    document.addEventListener("visibilitychange", function(){ if (!document.hidden && st.off === 0){ load(); live(); } });
    load(); live();
    return;
  }

  // ================================================================ /live/?id=
  if (kind === "live"){
    var qs = new URLSearchParams(location.search), id = (qs.get("id") || "").trim(), d0 = qs.get("d");
    var head = $("#lvh"), hlb = $("#lvhl"), evb = $("#lve"), lub = $("#lvl"), stb = $("#lvst"), srcb = $("#lvsrc"), names = null;
    if (/^365:\d+$/.test(id)){ location.replace("/db/game/?id=" + id.slice(4)); return; }
    if (!/^\d+$/.test(id)){ evb.innerHTML = '<p class="empty">ما حددت مباراة. <a href="/all/">كل المباريات</a></p>'; return; }
    // Arabic team and competition names: the day's all-matches file (the page usually comes from /all/, so it is cached)
    function arNames(md){
      var y = d0 || (md.kickoff_utc ? new Date(Date.parse(md.kickoff_utc) + 4 * 3600e3).toISOString().slice(0, 10).replace(/-/g, "") : "");
      if (names || !y) return Promise.resolve(names);
      return get(V + "all/" + y + ".json").then(function(doc){ names = { t:{}, lg:null };
        doc.leagues.forEach(function(lg){ lg.matches.forEach(function(m){ if (String(m.id) === id){ names.lg = lg; names.m = m; } }); });
        if (names.m){ names.t[names.m.home[0]] = names.m.home[1]; names.t[names.m.away[0]] = names.m.away[1]; } return names; }).catch(function(){ names = { t:{} }; return names; });
    }
    function draw(md){
      if (names){ [md.home, md.away].forEach(function(t){ if (names.t[t.id] && /[؀-ۿ]/.test(names.t[t.id])) t.name_ar = names.t[t.id]; }); }
      var cn = (names && names.lg && (names.lg.name_ar || names.lg.name)) || md.comp_name || "", H = R.tname(md.home), A = R.tname(md.away);
      document.title = (md.score ? H + " " + md.score.home + " - " + md.score.away + " " + A : H + " ضد " + A) + (R.isLive(md) ? " مباشر" : "") + " | تيفو";
      var t = $("#lvt"); if (t) t.textContent = (md.home.name_ar || md.home.name) + " ضد " + (md.away.name_ar || md.away.name);
      // only what reads in Arabic (the match page's rule, QA 65: no Latin-only stage or venue); the referee as the site shows him
      var AR = /[؀-ۿ]/, stg = md.stage ? R.stageAr(md.stage) : "", ven = md.venue && (md.venue.name_ar || md.venue.name) || "";
      var s = $("#lvs"); if (s) s.innerHTML = [cn && esc(cn), AR.test(stg) ? esc(stg) : "", md.round && /^\d+$/.test(String(md.round)) ? "الجولة " + esc(md.round) : "", AR.test(ven) ? esc(ven) : "", md.referee && md.referee.name ? 'الحكم <span class="lat">' + esc(md.referee.name) + "</span>" : ""].filter(Boolean).join(" · ");
      // the board links teams to /t/<id>/, which only our competitions' teams have: the encyclopedia sends them on if they do.
      // A crest we do not host goes (R.logo's fallback asks for the same /logo/<id>.png again and would leave a broken frame)
      head.innerHTML = R.matchHead(md).replace(/href="\/t\/(\d+)\/"/g, 'href="/db/club/?id=$1"').replace(/onerror="[^"]*"/g, 'onerror="this.remove()"');
      hlb.innerHTML = R.hl(md);
      evb.innerHTML = R.events(md); lub.innerHTML = R.lineups(md);
      stb.innerHTML = (md.stats || [])[0] || md.status === "scheduled" ? R.stats(md) : '<p class="empty">المصدر ما ينشر أرقام مفصّلة لهالمباراة.</p>';
      srcb.innerHTML = "من FotMob، تتحدث كل 30 ثانية وقت المباراة." + (md.generated ? ' <span class="muted small">آخر تحديث <span class="num">' + new Date(md.generated).toLocaleTimeString("ar-AE-u-nu-latn", { hour:"2-digit", minute:"2-digit" }) + "</span></span>" : "");
      if (R.localize) R.localize(box.parentNode || box);
    }
    function soon(md){ var t = Date.parse(md.kickoff_utc || ""); return R.isLive(md) || (md.status === "scheduled" && t && t - Date.now() < 90 * 60e3 && t > Date.now() - 3 * 3600e3); }
    function load(){
      return get("/api/tifo/match?id=" + encodeURIComponent(id)).then(function(md){
        return arNames(md).then(function(){ draw(md); var t = Date.parse(md.kickoff_utc || "");
          if (soon(md)) later("m", load, 30e3);
          else if (md.status === "finished" && t && Date.now() - t < 5 * 3600e3) later("m", load, 5 * 60e3);   // the highlights link comes later
          else if (md.status === "scheduled" && t) later("m", load, Math.min(Math.max(t - Date.now() - 80 * 60e3, 60e3), 2147483000)); });
      }).catch(function(e){
        if (e && e.status === 404){ evb.innerHTML = '<p class="empty">ما لقينا هالمباراة. <a href="/all/">كل المباريات</a></p>'; return; }
        srcb.textContent = "ما قدرنا نحدّث الحين، نحاول مرة ثانية…"; later("m", load, 60e3);
      });
    }
    document.addEventListener("visibilitychange", function(){ if (!document.hidden && timers.m){ load(); } });
    load();
  }
})();

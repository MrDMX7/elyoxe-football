/* تيفو client: refreshes the prerendered blocks from /v1 JSON, polls live data every 20 s while something is live,
   and keeps «فريقي» (my team) in localStorage. The page type and ids come from <body data-page data-id data-comp>. */
(function(){
  "use strict";
  var R = window.TR, B = document.body, PAGE = B.dataset.page, ID = B.dataset.id, V = "/v1/";
  var $ = function(s){ return document.querySelector(s); };
  function get(p){ return fetch(V + p, { cache:"no-cache" }).then(function(r){ if (!r.ok) throw new Error(r.status); return r.json(); }); }
  function mine(){ try { return +localStorage.getItem("tifo.mine") || null; } catch (e){ return null; } }
  function setMine(id, name){ try { if (id) { localStorage.setItem("tifo.mine", id); localStorage.setItem("tifo.mine.name", name || ""); } else { localStorage.removeItem("tifo.mine"); } } catch (e){} }
  function uaeToday(off){ var d = new Date(Date.now() + 4 * 3600e3 + (off || 0) * 864e5); return d.toISOString().slice(0, 10); }
  function set(sel, html){ var el = $(sel); if (el) el.innerHTML = html; }
  function stamp(g){ var el = $("#updated"); if (el && g) el.textContent = "آخر تحديث " + new Date(g).toLocaleTimeString("ar-AE-u-nu-latn", { hour:"2-digit", minute:"2-digit", timeZone:"Asia/Dubai" }); }
  function tabs(root){ (root || document).querySelectorAll(".tabs[data-tabs]").forEach(function(t){ t.addEventListener("click", function(e){ var b = e.target.closest("button[data-t]"); if (!b) return; t.querySelectorAll("button").forEach(function(x){ x.setAttribute("aria-selected", x === b ? "true" : "false"); }); document.querySelectorAll("[data-pane]").forEach(function(p){ if (p.dataset.group === t.dataset.tabs) p.hidden = p.dataset.pane !== b.dataset.t; }); try { history.replaceState(null, "", "#" + b.dataset.t); } catch (e){} }); var h = location.hash.slice(1), b = h && t.querySelector('button[data-t="' + h + '"]'); if (b) b.click(); }); }
  var timer = null; function poll(fn, ms){ clearTimeout(timer); timer = setTimeout(function(){ if (document.hidden){ poll(fn, ms); return; } fn(); }, ms); }
  document.addEventListener("visibilitychange", function(){ if (!document.hidden && timer){ clearTimeout(timer); run(); } });

  var INDEX = null;
  function index(){ return INDEX ? Promise.resolve(INDEX) : get("index.json").then(function(x){ INDEX = x; return x; }); }

  // ---- home: day list + live polling + my team
  var dayOff = 0;
  function home(){
    return Promise.all([index(), get("day/" + uaeToday(dayOff).replace(/-/g, "") + ".json").catch(function(){ return { matches:[] }; }), get("live.json").catch(function(){ return { matches:[] }; })]).then(function(r){
      var idx = r[0], day = r[1], live = r[2], by = {}; (live.matches || []).forEach(function(m){ by[m.id] = m; });
      var ms = (day.matches || []).map(function(m){ return by[m.id] || m; });
      set("#daytitle", R.dayNav(uaeToday(dayOff), uaeToday(0)));
      set("#day", R.dayList(ms, idx, { mine:mine(), empty:"ما في مباريات في هاليوم." }));
      var lv = (live.matches || []); set("#livecount", lv.length ? '<i class="cardflip"></i>' + lv.length + " مباراة مباشرة الحين" : "");
      if (dayOff === 0) stand(R.featured(ms));
      stamp(live.generated || day.generated);
      myCard(idx);
      poll(home, lv.length || ms.some(function(m){ var t = Date.parse(m.kickoff_utc); return m.status === "scheduled" && t - Date.now() < 15 * 60e3 && t > Date.now() - 3 * 3600e3; }) ? 20e3 : 120e3);
    });
  }
  var ST = null;
  function stand(m){
    var box = $("#stand"); if (!box || !m || !window.TifoStand) return;
    set("#standcap", R.standCap(m)); var k = $("#standkick"); if (k) k.textContent = R.isLive(m) ? "مباشر الحين" : m.status === "finished" ? "انتهت" : "مباراة اليوم";
    if (!ST) ST = window.TifoStand.mount(box.querySelector("canvas"));
    ST.set(m);
  }
  function myCard(idx){
    var el = $("#mine"); if (!el) return; var id = mine();
    if (!id){ el.innerHTML = '<div class="mine-card"><div class="h">اختار فريقك</div><p class="small" style="margin:0">افتح صفحة ناديك واضغط «هذا فريقي»، ومبارياته تطلع لك أول شي هنا.</p></div>'; return; }
    get("team/" + id + ".json").then(function(t){
      var f = R.teamFixtures(t), n = f.next[0], p = f.past[0];
      el.innerHTML = '<div class="mine-card"><a class="h" href="/t/' + t.id + '/">' + R.logo(t) + " " + R.tname(t) + " <small>فريقي</small></a>" + (n ? '<div class="lbl">المباراة الياية</div>' + R.matchRow(n, { date:true }) : "") + (p ? '<div class="lbl">آخر نتيجة</div>' + R.matchRow(p, { date:true }) : "") + "</div>";
    }).catch(function(){});
  }

  // ---- competition: standings (live), fixtures, leaders
  function comp(){
    var cid = +B.dataset.comp;
    return Promise.all([get("comp/" + cid + "/standings.json").catch(function(){ return null; }), get("comp/" + cid + "/fixtures.json").catch(function(){ return null; }), get("comp/" + cid + "/stats.json").catch(function(){ return null; }), get("live.json").catch(function(){ return { matches:[] }; })]).then(function(r){
      var st = r[0], fx = r[1], stats = r[2], live = (r[3].matches || []).filter(function(m){ return m.comp === cid; });
      if (st){ var lt = R.liveTable(st, live); set("#table", (lt.is_live ? '<p class="note"><i class="cardflip"></i>الترتيب اللحظي: لو انتهت المباريات الحين</p>' : "") + R.standings(lt, { mine:mine() })); }
      if (fx){ var by = {}; live.forEach(function(m){ by[m.id] = m; }); fx.matches = fx.matches.map(function(m){ return by[m.id] || m; }); roundsUI(fx); }
      if (stats){ set("#goals", R.leaders(stats, "goals")); set("#assists", R.leaders(stats, "assists")); }
      stamp((fx && fx.generated) || (st && st.generated));
      poll(comp, live.length ? 20e3 : 300e3);
    });
  }
  var curRound = null;
  function roundsUI(fx){
    var rr = R.rounds(fx), el = $("#rounds"); if (!el) return;
    if (curRound == null || rr.order.indexOf(curRound) < 0) curRound = fx.next_round && rr.by[fx.next_round] ? fx.next_round : (function(){ var k = rr.order.filter(function(k){ return rr.by[k].some(function(m){ return m.status !== "finished"; }); })[0]; return k || rr.order[rr.order.length - 1]; })();
    el.innerHTML = '<div class="chips">' + rr.order.map(function(k){ return '<button type="button" data-r="' + R.esc(k) + '"' + (k === curRound ? ' aria-pressed="true"' : "") + ">" + (isNaN(parseFloat(k)) ? R.esc(k) : k) + "</button>"; }).join("") + '</div><div id="roundlist">' + (rr.by[curRound] ? R.roundList(rr.by[curRound], { mine:mine() }) : "") + "</div>";
    var cur = el.querySelector('[aria-pressed="true"]'); if (cur) cur.scrollIntoView({ block:"nearest", inline:"center" });
    el.onclick = function(e){ var b = e.target.closest("button[data-r]"); if (!b) return; curRound = b.dataset.r; roundsUI(fx); };
  }

  // ---- match: detail, live every 20 s
  function match(){
    return Promise.all([index(), get("match/" + ID + ".json")]).then(function(r){
      var idx = r[0], md = r[1];
      set("#mh", R.matchHead(md)); set("#facts", R.matchFacts(md, idx)); set("#events", R.events(md)); set("#lineups", R.lineups(md)); set("#stats", R.stats(md)); set("#h2h", R.h2h(md));
      stamp(md.generated);
      var t = Date.parse(md.kickoff_utc), soon = md.status === "scheduled" && t - Date.now() < 90 * 60e3 && t > Date.now() - 3 * 3600e3;
      if (R.isLive(md) || soon) poll(match, 20e3);
    }).catch(function(){ /* no detail yet: keep the prerendered summary */ });
  }

  // ---- team
  function team(){
    var btn = $("#mybtn");
    function paint(){ if (!btn) return; var on = mine() === +ID; btn.textContent = on ? "فريقي ✓" : "هذا فريقي"; btn.classList.toggle("on", on); }
    if (btn){ btn.onclick = function(){ setMine(mine() === +ID ? null : +ID, B.dataset.name); paint(); }; paint(); }
    return get("team/" + ID + ".json").then(function(t){
      var f = R.teamFixtures(t);
      set("#next", f.next.length ? f.next.slice(0, 6).map(function(m){ return R.matchRow(m, { date:true }); }).join("") : '<p class="empty">ما في مباريات ياية منشورة.</p>');
      set("#past", f.past.length ? f.past.slice(0, 10).map(function(m){ return R.matchRow(m, { date:true }); }).join("") : '<p class="empty">ما في نتايج.</p>');
      set("#squad", R.squad(t)); stamp(t.generated);
    }).catch(function(){});
  }

  var pv = $("#prev"), nx = $("#next");
  if (pv && nx && PAGE === "home"){ pv.onclick = function(){ dayOff--; home(); }; nx.onclick = function(){ dayOff++; home(); }; }
  var ics = $("#ics"); if (ics) ics.href = "webcal://" + location.host + "/v1/team/" + ID + ".ics";
  function run(){ var f = { home:home, comp:comp, match:match, team:team }[PAGE]; if (f) f().catch(function(){}); }
  tabs(); run();
})();

/* تيفو: share one goal (owner 2026-10-06, item 11). On a match page every goal row (data-gn, numbered by src/v3.js R.events in the
   order the goals went in) gets a share button: the Web Share API where the phone has it (WhatsApp, X, Telegram…), else the link
   is copied. The link is the goal's own page /m/<id>/g/<n>/ (its share card: the score after the goal, the scorer and minute, how
   it went in, «شاهد الهدف» when there is a clip) when the build published one (#events data-gstub), else /m/<id>/#g<n>.
   Arriving on /m/<id>/#g<n> scrolls to that goal and marks it. Self-contained; follows the live redraws of #events. */
(function(){
  "use strict";
  var B = document.body; if (!B || B.dataset.page !== "match") return;
  var ev = document.getElementById("events"); if (!ev) return;
  var MID = B.dataset.id, stubs = (ev.dataset.gstub || "").split(",").filter(Boolean);
  var st = document.createElement("style");
  st.textContent = ".gsh{display:inline-grid;place-items:center;inline-size:2rem;block-size:2rem;margin-inline-start:.35rem;padding:0;border:1px solid var(--line,#F6F7F22B);background:none;color:var(--ink,#F6F7F2);cursor:pointer;vertical-align:middle}" +
    ".gsh:hover,.gsh:focus-visible{background:var(--ink,#F6F7F2);color:var(--bg,#0A2620)}.gsh svg{inline-size:1rem;block-size:1rem;fill:none;stroke:currentColor;stroke-width:1.9}" +
    "li.gflash{outline:2px solid var(--mine,#B07A3B);outline-offset:2px;animation:gfl 2.4s ease-out 1}@keyframes gfl{0%{background:#B07A3B55}100%{background:transparent}}" +
    ".gtoast{position:fixed;inset-inline:0;inset-block-end:calc(5rem + env(safe-area-inset-bottom));margin:auto;inline-size:max-content;max-inline-size:90vw;padding:.55rem 1rem;background:var(--ink,#F6F7F2);color:var(--bg,#0A2620);font-weight:600;z-index:90}";
  document.head.appendChild(st);
  var ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M7 8l5-5 5 5M5 13v8h14v-8"/></svg>';
  function url(n){ return location.origin + (stubs.indexOf(String(n)) >= 0 ? "/m/" + MID + "/g/" + n + "/" : "/m/" + MID + "/#g" + n); }
  function label(li){ var who = li.querySelector(".who"), t = who ? who.textContent.replace(/\s+/g, " ").trim() : "هدف", mn = li.querySelector(".mn");
    var teams = (document.querySelector("h1.vh") || {}).textContent || document.title.split("|")[0];
    return "⚽ " + t + (mn ? " " + mn.textContent.trim() : "") + " · " + String(teams).trim(); }
  function toast(t){ var el = document.createElement("div"); el.className = "gtoast"; el.setAttribute("role", "status"); el.textContent = t; document.body.appendChild(el); setTimeout(function(){ el.remove(); }, 1800); }
  function share(li){ var n = li.dataset.gn, u = url(n), t = label(li);
    if (navigator.share){ navigator.share({ title:t, text:t, url:u }).catch(function(){}); return; }
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(u).then(function(){ toast("انتسخ رابط الهدف"); }, function(){ prompt("رابط الهدف", u); });
    else prompt("رابط الهدف", u); }
  function decorate(){
    ev.querySelectorAll("li[data-gn]").forEach(function(li){ if (li.querySelector(".gsh")) return; var side = li.querySelector(".who"); if (!side) return;
      var b = document.createElement("button"); b.type = "button"; b.className = "gsh"; b.setAttribute("aria-label", "شارك الهدف"); b.title = "شارك الهدف"; b.innerHTML = ICON;
      b.addEventListener("click", function(e){ e.preventDefault(); e.stopPropagation(); share(li); }); side.parentNode.insertBefore(b, side.nextSibling); });
  }
  var done = false;
  function deep(){ if (done) return; var m = /^#g(\d+)$/.exec(location.hash); if (!m) { done = true; return; } var li = document.getElementById("g" + m[1]); if (!li) return; done = true;
    var tab = document.querySelector('[data-tabs="m"] [data-t="events"]'); if (tab && tab.getAttribute("aria-selected") !== "true") tab.click();
    setTimeout(function(){ li.scrollIntoView({ block:"center" }); li.classList.add("gflash"); }, 60); }
  decorate(); deep();
  if ("MutationObserver" in window){ var q = false; new MutationObserver(function(){ if (q) return; q = true; setTimeout(function(){ q = false; decorate(); deep(); }, 40); }).observe(ev, { childList:true, subtree:true }); }
  window.addEventListener("hashchange", function(){ done = false; deep(); });
})();

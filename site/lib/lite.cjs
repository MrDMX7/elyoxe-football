// «تيفو خفيف» (owner's second list, 1, 2026-10-06): the live scores in one small page for a weak connection, /lite/. The full site
// stays the default (owner: «الافتراضي هو الصفحة الثقيلة صح؟» — yes): a page sends the visitor here only when his phone says its
// connection is 2G or that it saves data (navigator.connection: effectiveType «2g» or «slow-2g», saveData), never when he chose
// the full site from here (localStorage tifo.lite = "off"); anyone can open /lite/ by its link. No v5 shell, no fonts, no images:
// the page is its own few KB and polls the poller's live window (/v1/live.json: live, about to start, just finished) every minute.
"use strict";

// the guard every full page carries in its head, before anything heavy loads
const GUARD = '<script>try{var c=navigator.connection;if(c&&(c.saveData||/2g$/.test(c.effectiveType||""))&&localStorage.getItem("tifo.lite")!=="off")location.replace("/lite/?from="+encodeURIComponent(location.pathname+location.search))}catch(e){}</script>';

const CSS = "body{margin:0;font:16px/1.5 system-ui,-apple-system,\"Segoe UI\",Tahoma,sans-serif;background:#fff;color:#111}" +
  "header{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 14px;background:#0B8246;color:#fff}" +
  "header a{color:#fff}h1{font-size:18px;margin:0}" +
  ".c{margin:0;padding:8px 14px 4px;font-size:13px;color:#555;background:#f2f2f2}" +
  ".r{display:flex;align-items:center;gap:8px;padding:10px 14px;border-bottom:1px solid #eee;color:inherit;text-decoration:none}" +
  ".t{flex:1;min-width:0}.a{text-align:left}.s{min-width:72px;text-align:center}.s b{display:block;font-size:18px}" +
  ".l{color:#E5261D;font-weight:700}.m{color:#777;font-size:13px}.p{padding:14px}footer{padding:14px;font-size:13px;color:#666}" +
  "@media(prefers-color-scheme:dark){body{background:#000;color:#eee}.c{background:#1c1c1e;color:#aaa}.r{border-color:#222}.m,footer{color:#999}}";

const JS = "(function(){var D=document,L=D.getElementById('l'),U=D.getElementById('u'),q=location.search.match(/[?&]from=([^&]+)/),from='/';" +
  "try{from=q?decodeURIComponent(q[1]):'/'}catch(x){}if(!/^\\/(?![\\/\\\\])/.test(from)||/[\\\\\\s]/.test(from))from='/';" +   // a path on this site only: never //host, /\host (read as //host), a space
  "D.getElementById('full').onclick=function(e){try{localStorage.setItem('tifo.lite','off')}catch(x){}location.href=from;e.preventDefault()};" +
  "function e(s){return String(s==null?'':s).replace(/[&<>\"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]})}" +
  "function tm(i){try{return new Date(i).toLocaleTimeString('ar-AE-u-nu-latn',{hour:'2-digit',minute:'2-digit',hour12:false})}catch(x){return''}}" +
  "function st(m){if(m.status==='live')return'<span class=\"l\">'+(m.minute!=null?m.minute+\"'\":'مباشر')+'</span>';if(m.status==='ht')return'<span class=\"l\">استراحة</span>';" +
  "if(m.status==='finished'||m.status==='awarded')return'انتهت';if(m.status==='scheduled')return m.time_tbd?'':tm(m.kickoff_utc);return e(m.status_detail||'')}" +
  "function n(t){return e((t&&(t.name_ar||t.name))||'')}" +
  "function draw(j){var ms=((j&&j.matches)||[]).slice(),h='',c=null,k={live:0,ht:0,finished:2,awarded:2};" +
  "ms.sort(function(a,b){return(k[a.status]==null?1:k[a.status])-(k[b.status]==null?1:k[b.status])||String(a.comp_name_ar).localeCompare(String(b.comp_name_ar))||Date.parse(a.kickoff_utc)-Date.parse(b.kickoff_utc)});" +
  "ms.forEach(function(m){if(m.comp_name_ar!==c){c=m.comp_name_ar;h+='<p class=\"c\">'+e(c||'')+'</p>'}" +
  "var s=m.score&&m.score.home!=null?'<span dir=\"rtl\">'+m.score.home+' - '+m.score.away+'</span>':'-';" +   // home on the right, as everywhere on Tifo
  "h+='<a class=\"r\" href=\"/m/'+e(m.id)+'/\"><span class=\"t\">'+n(m.home)+'</span><span class=\"s\"><b>'+s+'</b><span class=\"m\">'+st(m)+'</span></span><span class=\"t a\">'+n(m.away)+'</span></a>'});" +
  "L.innerHTML=h||'<p class=\"p\">ما في مباريات مباشرة أو قريبة الحين. <a href=\"/\">مباريات اليوم في النسخة الكاملة</a></p>';" +
  "U.textContent=j&&j.generated?'آخر تحديث '+tm(j.generated):''}" +
  "function load(){if(D.hidden)return;fetch('/v1/live.json',{cache:'no-cache'}).then(function(r){return r.ok?r.json():null}).then(function(j){if(j)draw(j)}).catch(function(){})}" +
  "load();setInterval(load,60000);D.addEventListener('visibilitychange',load)})()";

function page() {
  return '<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<title>تيفو خفيف: النتايج المباشرة</title><meta name="robots" content="noindex"><link rel="canonical" href="https://tifo.elyoxe.com/"><meta name="theme-color" content="#0B8246">' +
    "<style>" + CSS + "</style></head><body>" +
    '<header><h1>تيفو خفيف</h1><a href="/" id="full">النسخة الكاملة</a></header>' +
    '<main id="l"><p class="p m">نحمّل النتايج…</p></main>' +
    '<footer>نسخة خفيفة للنت الضعيف: النتايج المباشرة وبس، وتتحدّث كل دقيقة. <span id="u"></span></footer>' +
    '<noscript><p class="p"><a href="/">افتح تيفو</a></p></noscript>' +
    "<script>" + JS + "</script></body></html>";
}

module.exports = { GUARD, page };

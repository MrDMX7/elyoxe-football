/* Tifo redesign, phase 0: feature inventory.
   node redesign/inventory.cjs snap   [--out out]            copy one representative page per template from site/out/ into redesign/snap/old/
   node redesign/inventory.cjs old                           extract every heading, button, tab, tool link, control and client mount
                                                             from the snapshot -> redesign/inventory.json (keyed by template)
   node redesign/inventory.cjs new    [--root out_next/next] extract the same from the prototype pages -> redesign/inventory.next.json,
                                                             then diff old vs new for the prototyped templates -> redesign/inventory.diff.json
   The parser is a small tag tokenizer (no deps). In the new pages every item also records its slot: the nearest enclosing
   data-slot (hero | rail | tab:<name> | sheet | more | nav | footer), which is the "home" the layout gives it. */
"use strict";
const fs = require("fs"), path = require("path");
const SITE = path.resolve(__dirname, ".."), SNAP = path.join(__dirname, "snap/old");
const args = process.argv.slice(2), arg = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };

// template key from a site path; the order matters (first match wins)
const RULES = [
  [/^\/$/, "home"], [/^\/c\/[^/]+\/r\/[^/]+\/$/, "round"], [/^\/c\/[^/]+\/compare\/$/, "compare"], [/^\/c\/[^/]+\/power\/$/, "power"], [/^\/c\/[^/]+\/$/, "comp"],
  [/^\/m\/[^/]+\/kit\/$/, "kit"], [/^\/m\/[^/]+\/$/, "match"], [/^\/t\/[^/]+\/poster\/$/, "poster"], [/^\/t\/[^/]+\/month\/[^/]+\/$/, "month"], [/^\/t\/[^/]+\/$/, "team"],
  [/^\/uae\/$/, "national-uae"], [/^\/national\/[^/]+\/$/, "national"], [/^\/p\/[^/]+\/$/, "player"], [/^\/coach\/compare\/$/, "coach-compare"], [/^\/coach\/[^/]+\/$/, "coach"],
  [/^\/r\/[^/]+\/$/, "referee"], [/^\/h2h\/[^/]+\/$/, "h2h"], [/^\/s\/[^/]+\/$/, "stadium"], [/^\/([^/]+)\/$/, m => m[1]], [/^\/([^/]+)\/([^/]+)\/$/, m => m[1] + "-" + m[2]],
];
const tkey = p => { for (const [re, k] of RULES){ const m = p.match(re); if (m) return typeof k === "function" ? k(m) : k; } return null; };
// representative pages: the richest example of each template, and exactly the prototype pages for the three redesigned ones
const PICK = { home:"/", comp:"/c/uae-pro-league/", "comp-2":"/c/saudi-pro-league/", match:"/m/1000020522/", "match-2":"/m/6052085/", team:"/t/5789/", "national-uae":"/uae/",
  player:null, round:"/c/uae-pro-league/r/5/", compare:"/c/uae-pro-league/compare/", kit:"/m/6052085/kit/", coach:null, referee:null, h2h:null, stadium:null, national:null };

// ---- a tiny HTML tokenizer: start/end tags with attributes, text; tracks the open-element stack
const VOID = new Set(["area","base","br","col","embed","hr","img","input","link","meta","source","track","wbr"]);
function attrs(s){ const o = {}; s.replace(/([^\s=\/]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g, (_, k, a, b, c) => { o[k.toLowerCase()] = a ?? b ?? c ?? ""; }); return o; }
function parse(html){
  html = html.replace(/<!--[\s\S]*?-->/g, "").replace(/<script\b[\s\S]*?<\/script>/gi, "").replace(/<style\b[\s\S]*?<\/style>/gi, "");
  const root = { tag:"#root", a:{}, kids:[] }, stack = [root], re = /<(\/?)([a-zA-Z][a-zA-Z0-9-]*)([^>]*)>|([^<]+)/g; let m;
  while ((m = re.exec(html))){
    const top = stack[stack.length - 1];
    if (m[4] != null){ top.kids.push({ text:m[4] }); continue; }
    const tag = m[2].toLowerCase();
    if (m[1]){ for (let i = stack.length - 1; i > 0; i--) if (stack[i].tag === tag){ stack.length = i; break; } continue; }
    const el = { tag, a:attrs(m[3]), kids:[], parent:top }; top.kids.push(el);
    if (!VOID.has(tag) && !/\/\s*$/.test(m[3])) stack.push(el);
  }
  return root;
}
const dec = s => s.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, " ");
function text(el, skipSmall){ if (el.text != null) return el.text; if (skipSmall && el.tag === "small") return ""; return el.kids.map(k => text(k, skipSmall)).join(""); }
const clean = s => dec(s).replace(/\s+/g, " ").trim();
function up(el, f){ for (let p = el.parent; p; p = p.parent) if (f(p)) return p; return null; }
function slotOf(el){ const s = up(el, p => p.a && p.a["data-slot"]); return s ? s.a["data-slot"] : null; }
function cls(el){ return " " + ((el.a && el.a.class) || "") + " "; }

function extract(html){
  const root = parse(html), items = [], seen = new Set();
  const add = (type, label, extra, el) => { label = clean(label || ""); if (!label && !(extra && extra.id)) return; if (/^[\d\s›‹\-–:.]+$/.test(label) && !(extra && extra.id)) return;
    const it = Object.assign({ type, label }, extra || {}); const inShell = up(el, p => p.tag === "header" && /\bbar\b/.test(cls(p))) || up(el, p => p.tag === "footer"); if (inShell) it.shell = true;
    const sl = slotOf(el); if (sl) it.slot = sl; if (up(el, p => p.tag === "template" || /\bvault\b/.test(cls(p)))) it.tile = true; const k = type + "|" + label + "|" + (it.id || "") + "|" + (it.href || ""); if (seen.has(k)) return; seen.add(k); items.push(it); };
  (function walk(el){
    for (const k of el.kids || []){
      if (k.text != null) continue; const t = k.tag, a = k.a;
      if (/^h[1-3]$/.test(t)) add("heading", text(k, true), { level:+t[1], ...(k.kids.some(x => x.tag === "small") ? { sub:clean(k.kids.filter(x => x.tag === "small").map(x => text(x)).join(" ")) } : {}) }, k);
      else if ((t === "button" || t === "a") && /\b(sht|ed)\b/.test(cls(k))){ const tt = k.kids.find(x => x.a && /\btt2\b/.test(cls(x))); add(t === "a" ? "tool" : "tile", tt ? text(tt) : text(k), t === "a" ? { href:a.href || "" } : {}, k); }
      else if (t === "button"){ const tab = a.role === "tab" || up(k, p => /\btabs\b/.test(cls(p))) ; const chip = up(k, p => /\bchips\b/.test(cls(p)));
        if (tab) add("tab", text(k), { group:(up(k, p => p.a && p.a["data-tabs"]) || { a:{} }).a["data-tabs"] || "", key:a["data-t"] || "" }, k);
        else if (!chip || a.id) add("button", text(k) || a["aria-label"] || a.title, a.id ? { id:a.id } : {}, k); }
      else if (t === "a"){
        const href = a.href || "";
        if (up(k, p => p.tag === "header") && up(k, p => p.tag === "nav")) add("nav", text(k), { href }, k);
        else if (up(k, p => p.tag === "footer")) add("footer", text(k), { href }, k);
        else if (/\b(btn|sa|more-l|cta|ghost)\b/.test(cls(k)) || up(k, p => /\btools\b|\bbtnrow\b|\bml\b/.test(cls(p)))) add("tool", text(k), { href:href.replace(/\/next\//, "/") }, k);
        else if (up(k, p => /^h[23]$/.test(p.tag))) add("more-link", text(k), { href:href.replace(/\/next\//, "/") }, k);
      }
      else if (t === "select" || (t === "input" && a.type !== "hidden") || t === "audio") add("control", a["aria-label"] || a.placeholder || t, a.id ? { id:a.id } : {}, k);
      else if (a.id && ["div","section","p","span"].includes(t) && !k.kids.some(x => x.tag || (x.text && x.text.trim())) && !/^(roundlist)$/.test(a.id)) add("mount", "#" + a.id, { id:a.id }, k);
      walk(k);
    }
  })(root);
  const body = (html.match(/<body[^>]*data-page="([^"]*)"/) || [])[1] || "";
  // UI that only exists at runtime (app.js / share.js inject it), so the static parse can't see it: listed from the client code
  const nsec = (html.match(/<section class="blk"[^>]*><h2>/g) || []).length;
  if (nsec && !/data-slot=/.test(html)) items.push({ type:"button", label:"شارك", client:true, note:`app.js injects one «شارك» on every section.blk h2 (${nsec} here)` });
  if (body === "home" && /data-slot=/.test(html) && /id="mine"/.test(html)) items.push({ type:"button", label:"ألوان فريقي على الموقع", id:"themebtn", client:true, slot:"rail", note:"app.js myCard() inside #mine (rail:mine)" });
  if (body === "home" && !/data-slot=/.test(html)) items.push({ type:"button", label:"ألوان فريقي على الموقع", id:"themebtn", client:true, note:"app.js myCard(), shown once a favourite club is set" });
  return { page:body, items };
}

function pageFile(base, p){ return path.join(base, p.replace(/^\//, ""), "index.html"); }
function listPages(base){ const out = []; (function rec(d, rel){ for (const f of fs.readdirSync(d, { withFileTypes:true })){ if (f.isDirectory()){ if (["assets","logo","og","tn","audio"].includes(f.name)) continue; rec(path.join(d, f.name), rel + f.name + "/"); } else if (f.name === "index.html") out.push(rel); } })(base, "/"); return out; }

const cmd = args[0];
if (cmd === "snap"){
  const OUT = path.resolve(SITE, arg("--out", "out")), pages = listPages(OUT), byT = {};
  for (const p of pages){ const k = tkey(p); if (!k) continue; (byT[k] = byT[k] || []).push(p); }
  const chosen = {};
  for (const [k, list] of Object.entries(byT)){
    if (PICK[k]){ chosen[k] = PICK[k]; continue; }
    // otherwise: the largest page of the template (the most features on one page), sampled to keep it quick
    const sample = list.length > 300 ? list.filter((_, i) => i % Math.ceil(list.length / 300) === 0) : list;
    chosen[k] = sample.map(p => [p, fs.statSync(pageFile(OUT, p)).size]).sort((a, b) => b[1] - a[1])[0][0];
  }
  for (const k of ["comp-2", "match-2"]) chosen[k] = PICK[k];
  fs.rmSync(SNAP, { recursive:true, force:true });
  for (const [k, p] of Object.entries(chosen)){ const f = pageFile(OUT, p); if (!fs.existsSync(f)){ console.error("missing", k, p); delete chosen[k]; continue; } const d = pageFile(SNAP, p); fs.mkdirSync(path.dirname(d), { recursive:true }); fs.copyFileSync(f, d); }
  fs.writeFileSync(path.join(__dirname, "snap/chosen.json"), JSON.stringify({ taken:new Date().toISOString(), counts:Object.fromEntries(Object.entries(byT).map(([k, v]) => [k, v.length])), chosen }, null, 1));
  console.log(Object.keys(chosen).length + " templates snapshotted from " + pages.length + " pages");
}
else if (cmd === "old"){
  const ch = JSON.parse(fs.readFileSync(path.join(__dirname, "snap/chosen.json"), "utf8")), inv = { generated:ch.taken, source:"site/out/ (snapshot in redesign/snap/old)", pages:ch.counts, shell:null, templates:{} };
  for (const [k, p] of Object.entries(ch.chosen)){
    const x = extract(fs.readFileSync(pageFile(SNAP, p), "utf8"));
    if (!inv.shell) inv.shell = x.items.filter(i => i.shell);
    inv.templates[k] = { path:p, page:x.page, items:x.items.filter(i => !i.shell) };
  }
  fs.writeFileSync(path.join(__dirname, "inventory.json"), JSON.stringify(inv, null, 1));
  console.log(Object.entries(inv.templates).map(([k, v]) => k + ":" + v.items.length).join(" ") + " | shell:" + inv.shell.length);
}
else if (cmd === "new"){
  const ROOT = path.resolve(SITE, arg("--root", "out_next/next")), inv = JSON.parse(fs.readFileSync(path.join(__dirname, "inventory.json"), "utf8"));
  // renamed labels (old -> new), and old items that deliberately became something else; every entry is explained
  const MAP = JSON.parse(fs.readFileSync(path.join(__dirname, "placement.json"), "utf8"));
  const proto = { home:"/", comp:"/c/uae-pro-league/", "comp-2":"/c/saudi-pro-league/", match:"/m/1000020522/", "match-2":"/m/6052085/" };
  const nx = { generated:new Date().toISOString(), templates:{} }, diff = { generated:nx.generated, templates:{} };
  const norm = s => clean(String(s)).replace(/[أإآ]/g, "ا").replace(/ة/g, "ه").replace(/ى/g, "ي");
  const shellNew = [];
  for (const [k, p] of Object.entries(proto)){
    const f = pageFile(ROOT, p); if (!fs.existsSync(f)){ console.error("no prototype page", p); continue; }
    const x = extract(fs.readFileSync(f, "utf8")); nx.templates[k] = { path:"/next" + p, items:x.items };
    if (!shellNew.length) shellNew.push(...x.items.filter(i => i.slot === "nav" || i.slot === "footer" || i.slot === "shell-sheet"));
    const old = [...(k === "home" ? inv.shell.map(i => Object.assign({ fromShell:true }, i)) : []), ...inv.templates[k].items];
    const rows = [];
    for (const o of old){
      const alias = (MAP.rename[o.label] || []).concat([o.label]).map(norm);
      const hit = x.items.find(n => (o.id && n.id === o.id) || (alias.includes(norm(n.label)) && (n.type === o.type || ["heading","tab","tool","button","more-link","nav","footer"].includes(n.type))))
        || (o.type === "mount" && x.items.find(n => n.id === o.id));
      const why = MAP.dropped[o.label] || MAP.dropped[o.type + ":" + o.label];
      rows.push({ type:o.type, label:o.label, ...(o.id ? { id:o.id } : {}), now:hit ? (hit.slot || "page") + (hit.tile ? " › tile/panel" : "") + (hit.label !== o.label ? " as «" + hit.label + "»" : "") : why ? "merged: " + why : "MISSING" });
    }
    const added = x.items.filter(n => !old.some(o => (o.id && n.id === o.id) || (MAP.rename[o.label] || []).concat([o.label]).map(norm).includes(norm(n.label))));
    diff.templates[k] = { old:"/" === p ? "/" : p, next:"/next" + p, total:rows.length, kept:rows.filter(r => !/^MISSING|^merged/.test(r.now)).length, merged:rows.filter(r => /^merged/.test(r.now)).length, missing:rows.filter(r => r.now === "MISSING"), rows, new_items:added.map(n => ({ type:n.type, label:n.label, slot:n.slot || "page" })) };
  }
  fs.writeFileSync(path.join(__dirname, "inventory.next.json"), JSON.stringify(nx, null, 1));
  fs.writeFileSync(path.join(__dirname, "inventory.diff.json"), JSON.stringify(diff, null, 1));
  for (const [k, d] of Object.entries(diff.templates)) console.log(`${k}: ${d.total} old items -> kept ${d.kept}, merged ${d.merged}, MISSING ${d.missing.length}` + (d.missing.length ? "\n   " + d.missing.map(m => m.type + ":" + m.label + (m.id ? "#" + m.id : "")).join("\n   ") : ""));
}
else if (cmd === "gate"){
  // production gate: every template, up to N sampled pages that exist in both builds, old item by old item
  const OLD = path.resolve(SITE, arg("--old", "out_base")), NEW = path.resolve(SITE, arg("--new", "out")), N = +arg("--n", "20"), only = arg("--only", "");
  const MAP = JSON.parse(fs.readFileSync(path.join(__dirname, "placement.json"), "utf8")), norm = s => clean(String(s)).replace(/[أإآ]/g, "ا").replace(/ة/g, "ه").replace(/ى/g, "ي");
  // player names moved to Arabic (names/players_ar.json): a Latin label found as its Arabic form counts as kept
  const LAT = {}; for (const nf of ["players_ar.json", "coaches_ar.json", "referees_ar.json", "clubs_ar.json"]) try { for (const v of Object.values(JSON.parse(fs.readFileSync(path.join(SITE, "../names/" + nf), "utf8")))) if (v.latin && v.ar) (LAT[v.latin] = LAT[v.latin] || []).push(v.ar); } catch (e){}
  (MAP.rename = MAP.rename || {}); for (const [l, a] of Object.entries(LAT)) MAP.rename[l] = (MAP.rename[l] || []).concat(a);
  const byT = {}; for (const p of listPages(OLD)){ const k = tkey(p); if (!k || (only && !only.split(",").includes(k))) continue; if (fs.existsSync(pageFile(NEW, p))) (byT[k] = byT[k] || []).push(p); }
  const res = {}; let bad = 0;
  for (const [k, list] of Object.entries(byT)){
    const step = Math.max(1, Math.floor(list.length / N)), sample = list.filter((_, i) => i % step === 0).slice(0, N), miss = {};
    for (const p of sample){
      const o = extract(fs.readFileSync(pageFile(OLD, p), "utf8")).items, n = extract(fs.readFileSync(pageFile(NEW, p), "utf8")).items;
      for (const it of o){ if (it.shell) continue; const al = (MAP.rename[it.label] || []).concat([it.label]).map(norm);
        const hit = n.find(x => (it.id && x.id === it.id) || al.includes(norm(x.label))); if (!hit){ const key = it.type + ":" + it.label + (it.id ? "#" + it.id : ""); (miss[key] = miss[key] || []).push(p); } }
    }
    res[k] = { pages:list.length, sampled:sample.length, missing:Object.entries(miss).map(([m, ps]) => ({ item:m, n:ps.length, eg:ps[0] })) }; bad += res[k].missing.length;
  }
  fs.writeFileSync(path.join(__dirname, "gate.json"), JSON.stringify(res, null, 1));
  for (const [k, r] of Object.entries(res)) if (r.missing.length) console.log(k + ": " + r.missing.map(m => m.item + " (" + m.n + ", " + m.eg + ")").join(" | "));
  console.log(`gate: ${Object.keys(res).length} templates, ${Object.values(res).reduce((a, r) => a + r.sampled, 0)} pages, ${bad} missing item kinds`); process.exitCode = bad ? 1 : 0;
}
else console.log("usage: node redesign/inventory.cjs snap|old|new|gate");
module.exports = { extract, tkey };

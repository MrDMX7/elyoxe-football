#!/usr/bin/env node
/* تيفو v5 rollout: the old blocks' stylesheet as a content layer (ROLLOUT.md §CSS).
     node site/redesign/v5/legacy-css.cjs        -> site/src/v5/content.css (committed; build.cjs appends it to src/v5/app.css)
   Pages and sheets that still carry v2/v3 markup (the analysis blocks, the legacy pages' bodies, the history widgets) keep their
   classes inside a .lc container. This takes src/tifo.css + src/v3.css + src/allmatches.css and makes them a layer that only
   reaches those containers and draws in v5's colours:
   - every selector is scoped to .lc: «.a .b» becomes «:is(.lc .a, .a .lc) .b», so a block whose outer section now wraps the .lc
     card (section.grp.blk > .card.lc) still matches; «.v3 …», «body …» lose that prefix; the body states that still exist
     (.nospoil, .comm) and html.stale stay in front; the v3 shell's own parts (bar, sheets, panel, tab bar, footer…) are dropped
   - the role tokens (--ground, --raised, --text, --rule, --dune, --pulse…) are redefined on :root as v5 tokens, so the layer
     follows light and dark; the names v5 owns (--bg, --live, --pitch) keep v5's value; the v3 names (--ink, --tert, --line,
     --surf…) stay defined for the scripts that draw outside .lc (tv.js, media.js)
   - hard-coded palette colours (night, chalk, dune, pulse…) become the matching v5 tokens (alpha through color-mix); the three
     brand faces become v5's system font
   Re-run after editing any of the three source files. */
"use strict";
const fs = require("fs"), path = require("path");
const SITE = path.resolve(__dirname, "../.."), OUT = path.join(SITE, "src/v5/content.css");
const SRC = ["src/tifo.css", "src/v3.css", "src/allmatches.css"];

// ---- tokens: legacy name -> v5 value (anything not listed keeps its legacy value: sizes, z-indexes, timings)
const TOK = { ground: "var(--bg2)", raised: "var(--fill3)", "raised-hi": "var(--fill)", sunken: "var(--bg3)", "sunken-2": "var(--bg3)",
  text: "var(--label)", "text-2": "var(--label2)", "text-3": "var(--label2)", rule: "var(--sep)", "rule-2": "var(--fill)", "rule-ctl": "var(--label3)",
  mine: "var(--accent)", "live-text": "var(--live)", "card-y": "var(--ycard)", "card-r": "var(--rcard)", focus: "var(--accent)", inkbg: "var(--fill2)",
  concrete: "var(--bg)", "concrete-2": "var(--bg3)", night: "var(--bg3)", "night-2": "var(--fill)", chalk: "var(--label)", ink: "var(--label)",
  dune: "var(--accent)", "dune-soft": "var(--accent-bg)", pulse: "var(--live)", "pulse-soft": "var(--live-bg)", stone: "var(--label2)",
  line: "var(--sep)", "line-2": "var(--fill)", kufi: "var(--font)", "font-text": "var(--font)", digits: "var(--font)",
  surf: "var(--bg2)", "surf-2": "var(--bg)", board: "var(--bg3)", tert: "var(--label2)" };
const V5_OWN = new Set(["bg", "live", "pitch", "color-scheme"]);
// ---- hard-coded colours: the v2/v3 palette -> v5 tokens
const PAL = { F6F7F2: "label", B9C7C0: "label2", A7B6AF: "label2", "9BA39E": "label2", "5C6660": "label2", "0A2620": "bg2", "061B16": "bg3", "123A31": "bg3",
  "0F3A2F": "bg3", "0F3129": "bg3", "14403A": "fill3", "1A4A42": "fill", "2D5A4E": "fill2", "0E1512": "label", "0B1512": "label", "141A17": "label",
  "10A04B": "live", "5BE08F": "live", B07A3B: "accent", F2C230: "ycard", F2C94C: "ycard", D8343F: "rcard", D64545: "loss", E5484D: "loss",
  E9ECE7: "bg", E9ECE4: "bg", DFE3DC: "bg3", DDE4DF: "fill", DCE0DA: "fill", CDD3CC: "sep", DDDDDD: "sep", "2A3833": "fill2" };
function hexMap(h) {
  let x = h.slice(1).toUpperCase(); if (x.length === 3 || x.length === 4) x = x.split("").map(c => c + c).join("");
  const base = x.slice(0, 6), a = x.length === 8 ? parseInt(x.slice(6), 16) / 255 : 1, t = PAL[base]; if (!t) return h;
  return a >= 0.995 ? `var(--${t})` : `color-mix(in srgb,var(--${t}) ${Math.round(a * 100)}%,transparent)`;
}
const FONT_RE = /"?(Noto Kufi Arabic|Readex Pro|Barlow Condensed)"?/;
function decls(body) {
  let b = body.replace(/#[0-9a-fA-F]{3,8}\b/g, m => /^#([0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})$/i.test(m) ? hexMap(m) : m);
  b = b.replace(/font-family:([^;}]*)/g, (m, v) => FONT_RE.test(v) ? "font-family:var(--font)" : m);
  b = b.replace(/(^|[;{\s])font:([^;}]*)/g, (m, pre, v) => { const i = v.search(FONT_RE); return i < 0 ? m : pre + "font:" + v.slice(0, i).trim() + " var(--font)"; });
  // white text on the old «dune» (now the accent): v5's ink for that ground
  if (/background(-color)?:[^;]*var\(--(dune|mine|focus)\)/.test(b)) b = b.replace(/(^|[;{\s])color:\s*#(fff|FFF|ffffff|FFFFFF)\b/g, "$1color:var(--on-accent)");
  return b;
}

// ---- a small CSS reader: comments out, then statements (rules and at-rules with their blocks)
function strip(css) { return css.replace(/\/\*[\s\S]*?\*\//g, ""); }
function parse(css) {
  const out = []; let i = 0;
  while (i < css.length) {
    while (i < css.length && /\s/.test(css[i])) i++; if (i >= css.length) break;
    let j = i, q = null; while (j < css.length) { const c = css[j]; if (q) { if (c === q) q = null; } else if (c === '"' || c === "'") q = c; else if (c === "{" || c === ";") break; j++; }
    const pre = css.slice(i, j).trim();
    if (css[j] === ";") { out.push({ at: pre }); i = j + 1; continue; }
    let d = 0, k = j; for (; k < css.length; k++) { const c = css[k]; if (c === "{") d++; else if (c === "}") { d--; if (!d) break; } }
    const inner = css.slice(j + 1, k); i = k + 1;
    if (/^@(media|supports|container|layer)\b/.test(pre)) out.push({ group: pre, children: parse(inner) });
    else if (pre[0] === "@") out.push({ atBlock: pre, body: inner });
    else out.push({ sel: pre, body: inner });
  }
  return out;
}
function splitTop(s, ch) { const out = []; let d = 0, q = null, cur = ""; for (const c of s) { if (q) { if (c === q) q = null; cur += c; continue; } if (c === '"' || c === "'") q = c; else if (c === "(" || c === "[") d++; else if (c === ")" || c === "]") d--; if (c === ch && !d) { out.push(cur); cur = ""; } else cur += c; } out.push(cur); return out.map(x => x.trim()).filter(Boolean); }
// the first compound of a selector and the rest (with its leading combinator)
function firstCompound(sel) { let d = 0, q = null; for (let i = 0; i < sel.length; i++) { const c = sel[i]; if (q) { if (c === q) q = null; continue; } if (c === '"' || c === "'") { q = c; continue; } if (c === "(" || c === "[") d++; else if (c === ")" || c === "]") d--; else if (!d && /[\s>+~]/.test(c)) return [sel.slice(0, i), sel.slice(i)]; } return [sel, ""]; }

const SHELL = /\.(bar|top|tabbar|pnav|foot|fcols|fbrand|sheet|sh-in|sh-h|sh-g|sh-list|panel|pn-in|pn-h|pn-b|pn-sub|scrimall|skip|brand|mset|mswitch|mctry|mg|ml|toast|mini|minibar|hero|mhero|hero-in|hero-acts|keyart|stand|standcap|standkick|wrap|locked|scrim|fsheet|mark|acts|ib)(?![\w-])|^(html|:root|\*)$|header\.top|footer\.foot/;
const KEEP_STATE = new Set(["nospoil", "comm"]);
let dropped = 0;
function scopeOne(sel) {
  sel = sel.trim();
  if (SHELL.test(sel)) { dropped++; return null; }
  let prefix = "", [c1, rest] = firstCompound(sel);
  // html.stale …: the dimming state stays in front
  if (/^html\b/.test(c1)) { if (c1 === "html" || !rest.trim()) { dropped++; return null; } prefix = c1 + " "; sel = rest.trim(); [c1, rest] = firstCompound(sel); }
  // body / .v3 and their states
  const m = /^(?:body)?((?:\.v3)?)((?:\.[\w-]+|\[[^\]]+\]|:not\([^)]*\))*)$/.exec(c1);
  if (/^(body|\.v3)/.test(c1) && m) {
    const states = (m[2].match(/\.[\w-]+/g) || []).map(x => x.slice(1)).filter(x => x !== "v3"), attrs = m[2].match(/\[[^\]]+\]/g) || [], nots = /:not\(/.test(m[2]);
    if (nots || states.some(s => !KEEP_STATE.has(s))) { dropped++; return null; }
    const body = (states.length ? states.map(s => "." + s).join("") : "") + (attrs.length ? "body" + attrs.join("") : "");
    if (!rest.trim()) { if (!body) return ".lc"; if (attrs.length && !states.length) return prefix + body; dropped++; return null; }   // body[data-page=…] alone stays (the poster's white)
    prefix += body ? body + " " : ""; sel = rest.replace(/^\s*>\s*/, "").trim(); [c1, rest] = firstCompound(sel);
  }
  if (!rest.trim()) return prefix + ".lc " + sel;
  return prefix + ":is(.lc " + c1 + "," + c1 + " .lc)" + rest;
}
function rule(r, depth) {
  const sels = splitTop(r.sel, ",").map(scopeOne).filter(Boolean); if (!sels.length) return "";
  if (sels.length === 1 && sels[0] === ".lc") return "";   // the old body rule: .lc gets v5's own (below)
  const body = decls(r.body.trim()); if (!body) return "";
  return sels.join(",") + "{" + body + "}";
}
function walk(nodes) {
  const out = [];
  for (const n of nodes) {
    if (n.sel != null) { if (n.sel === ":root") continue; const x = rule(n); if (x) out.push(x); }
    else if (n.group) { const inner = walk(n.children); if (inner.length) out.push(n.group + "{" + inner.join("\n") + "}"); }
    else if (n.atBlock) { if (/^@font-face|^@import|^@charset/.test(n.atBlock)) continue; out.push(n.atBlock + "{" + n.body.trim() + "}"); }
  }
  return out;
}
// ---- tokens: every legacy :root, later files win, then the v5 mapping
const toks = new Map();
const sheets = SRC.map(f => strip(fs.readFileSync(path.join(SITE, f), "utf8")));
for (const css of sheets) for (const n of parse(css)) if (n.sel === ":root") for (const d of splitTop(n.body, ";")) { const i = d.indexOf(":"); if (i < 0) continue; const k = d.slice(0, i).trim().replace(/^--/, ""); if (!d.trim().startsWith("--")) continue; toks.set(k, d.slice(i + 1).trim()); }
for (const k of V5_OWN) toks.delete(k);
for (const [k, v] of Object.entries(TOK)) toks.set(k, v);
const root = ":root{" + [...toks].map(([k, v]) => "--" + k + ":" + decls(v)).join(";") + "}";
const body = sheets.map(css => walk(parse(css)).join("\n")).join("\n");
const head = "/* تيفو v5 content layer: generated by site/redesign/v5/legacy-css.cjs from src/tifo.css + src/v3.css + src/allmatches.css; do not edit by hand */\n";
const own = ".lc{font-size:15px;line-height:1.6;overflow-wrap:break-word}.lc.lcx,.lc.mounts{margin-top:14px}.card.lc{padding:12px 16px}.card.lc:empty{display:none}\n";
fs.writeFileSync(OUT, head + root + "\n" + own + body + "\n");
console.log(`content.css: ${(fs.statSync(OUT).size / 1024).toFixed(1)} KB, ${toks.size} tokens, ${dropped} shell selectors dropped`);

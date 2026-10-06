/* The share stage (owner 2026-10-06, item 11): share cards for every match and every goal, and a canonical share URL per goal.
   og.py renders the "stage" cards (every match without an hourly card, every recent goal) into cache/og/ and lists them in
   cache/og/staged.json; this stage puts a card into cache/share/delta/og/s/<key>.png only when it is new or changed, and the goal
   pages /m/<id>/g/<n>/ (a share target with the goal's own card, sending people on to /m/<id>/#g<n>) only when their bytes
   change. tools/runner.py uploads the delta with `aws s3 cp` and promotes manifest.next.json; the main `sync --delete` excludes
   og/s/ and the m/<id>/g/<n>/ pages, so a card or a goal page is uploaded once, not re-synced every hour, and stays up once published.
     published()   what the last good upload holds ({"og:<key>": file, "g:<id>/<n>": hash}), read before the pages are written
     run()         after og.py: the delta and manifest.next.json */
"use strict";
const crypto = require("crypto");
const sha = s => crypto.createHash("sha1").update(s).digest("hex").slice(0, 16);

function published(X){ const { CACHE, fs, path } = X; try { return JSON.parse(fs.readFileSync(path.join(CACHE, "share", "manifest.json"), "utf8")); } catch (e){ return {}; } }

function run(X){
  const { CACHE, fs, path, stubs } = X, t0 = Date.now();
  const DIR = path.join(CACHE, "share"), DELTA = path.join(DIR, "delta");
  fs.mkdirSync(DIR, { recursive:true }); fs.rmSync(DELTA, { recursive:true, force:true }); fs.mkdirSync(DELTA, { recursive:true });
  const man = published(X), next = Object.assign({}, man); let cards = 0, pages = 0;
  let staged = []; try { staged = JSON.parse(fs.readFileSync(path.join(CACHE, "og", "staged.json"), "utf8")); } catch (e){}
  for (const [key, file] of staged){ if (man["og:" + key] === file) continue; const src = path.join(CACHE, "og", file); if (!fs.existsSync(src)) continue;
    const dst = path.join(DELTA, "og", "s", key + ".png"); fs.mkdirSync(path.dirname(dst), { recursive:true }); fs.copyFileSync(src, dst); next["og:" + key] = file; cards++; }
  // a goal page shows its own card as soon as og.py has rendered it (this run or before), else the match's card (s.img)
  const have = new Set(staged.map(x => x[0]));
  for (const s of stubs || []){ const k = `g:${s.mid}/${s.n}`, html = s.html.replace("__GIMG__", have.has(s.card) || man["og:" + s.card] ? `${s.site}/og/s/${s.card}.png` : s.img), h = sha(html); if (man[k] === h){ continue; }
    const dst = path.join(DELTA, "m", String(s.mid), "g", String(s.n), "index.html"); fs.mkdirSync(path.dirname(dst), { recursive:true }); fs.writeFileSync(dst, html); next[k] = h; pages++; }
  fs.writeFileSync(path.join(DIR, "manifest.next.json"), JSON.stringify(next)); fs.writeFileSync(path.join(DIR, "delete.txt"), "");
  const st = { staged:staged.length, cards, pages, published:Object.keys(man).length, s:+((Date.now() - t0) / 1000).toFixed(1) };
  console.log("share stage:", JSON.stringify(st)); return st;
}
module.exports = { published, run };

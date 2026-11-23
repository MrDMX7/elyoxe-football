// node --test site/lib/latin_ar.test.cjs — a name the build left in Latin letters, in Arabic where one spelling is known
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), L = require("./latin_ar.cjs");

test("one Arabic spelling per Latin name, an ambiguous name left alone", () => {
  const d = L.dictionary([["Al Ain", "العين"], ["Sami Al-Jaber", "سامي الجابر"], ["Ahmed Hassan", "أحمد حسن"], ["Ahmed Hassan", "أحمد حسان"], ["X", "Y"]]);
  assert.deepEqual(d, { "Al Ain": "العين", "Sami Al-Jaber": "سامي الجابر" });          // «Ahmed Hassan»: two men, two spellings; «Y» no Arabic
});

test("the page's Latin names read in Arabic, the subtitle under a name and an unknown brand stay", () => {
  const d = { "Al Ain": "العين", "Sami Al-Jaber": "سامي الجابر" };
  const h = '<h1>سامي الجابر</h1><p class="muted"><span class="lat">Sami Al-Jaber</span></p><li><span class="lat">Al Ain</span> · <span class="lat">Kooora</span></li>';
  const r = L.arabize(h, d);
  assert.equal(r.html, '<h1>سامي الجابر</h1><p class="muted"><span class="lat">Sami Al-Jaber</span></p><li>العين · <span class="lat">Kooora</span></li>');
  assert.equal(r.n, 1);
});

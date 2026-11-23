// node --test site/lib/world_stage.test.cjs — the encyclopedia's player pages (lib/world_stage.cjs)
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), W = require("./world_stage.cjs");

test("an encyclopedia man who has the archive's profile gets a page that sends him there: one page per man", () => {
  const h = W.forwardPage("/p/k5/", "يوجين فريمبونغ");
  assert.match(h, /<meta http-equiv="refresh" content="0;url=\/p\/k5\/">/);
  assert.match(h, /<link rel="canonical" href="https:\/\/tifo\.elyoxe\.com\/p\/k5\/">/);
  assert.match(h, /noindex/);
  assert.match(h, /يوجين فريمبونغ/);
});

test("the encyclopedia page's card is rows of label and value, as the profiles' (a bare dl piled up on today's pages)", () => {
  const h = W.bioRows([["المركز", "وسط"], ["الطول", '<span class="num">174</span> سم']]);
  assert.equal(h, '<div class="row"><span class="rt">المركز</span><span class="rv">وسط</span></div>' +
    '<div class="row"><span class="rt">الطول</span><span class="rv"><span class="num">174</span> سم</span></div>');
});

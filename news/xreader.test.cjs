// node --test news/xreader.test.cjs: when the X reader starts the journal at once (an official post, at most every 5 min)
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const { shouldDispatch } = require("./xreader.js");
test("an official post starts the journal, not more than every 5 minutes", () => {
  const off = [{ tier: "official" }], paper = [{ tier: "paper" }];
  assert.equal(shouldDispatch(off, 0, 10 * 60e3), true);
  assert.equal(shouldDispatch(paper, 0, 10 * 60e3), false);
  assert.equal(shouldDispatch(off, 8 * 60e3, 10 * 60e3), false);
});

"use strict";
// Loads the UI Builder numeric property-field parsers (numericField.ts —
// React-free pure logic) bundled on the fly with the esbuild already in
// web/programmer/node_modules and checks the clear-means-unset parsing that
// backs the BasicProperties numeric inputs. Mirrors
// config_schema_helpers_harness.cjs. The Python wrapper skips when the Node
// toolchain or esbuild is absent rather than failing the Python-only CI gate.
const path = require("path");

const helpersPath = process.argv[2];

const esbuild = require("esbuild");
const built = esbuild.buildSync({
  entryPoints: [helpersPath],
  bundle: true,
  format: "cjs",
  platform: "node",
  write: false,
  logLevel: "silent",
});
const code = built.outputFiles[0].text;
const moduleObj = { exports: {} };
const fn = new Function("exports", "require", "module", "__filename", "__dirname", code);
fn(moduleObj.exports, require, moduleObj, helpersPath, path.dirname(helpersPath));
const H = moduleObj.exports;

const results = {};
const scenario = (name, fnBody) => {
  try {
    results[name] = fnBody();
  } catch (e) {
    results[name] = { pass: false, detail: String(e) };
  }
};

scenario("empty_unsets_not_zero", () => {
  // The defect this fixes: the editors parsed with Number(v) — and
  // Number("") is 0 — so briefly clearing Min/Max/Step/Digits to retype
  // committed a literal 0 (digits=0 keypad, step=0 slider).
  const legacy = Number("");
  const fixed = H.numOrUndefined("");
  return {
    pass: legacy === 0 && fixed === undefined,
    detail: { legacy, fixed },
  };
});
scenario("whitespace_unsets", () => {
  // Number(" ") is also 0.
  return {
    pass: H.numOrUndefined("  ") === undefined,
    detail: H.numOrUndefined("  "),
  };
});
scenario("zero_stays_zero", () => {
  // An explicit 0 is a real value (e.g. meter max 0 dB) — unset ≠ 0.
  const got = H.numOrUndefined("0");
  return { pass: got === 0, detail: got };
});
scenario("garbage_unsets", () => {
  return {
    pass: H.numOrUndefined("abc") === undefined,
    detail: H.numOrUndefined("abc"),
  };
});
scenario("numbers_parse", () => {
  const checks = {
    negative: H.numOrUndefined("-12") === -12,
    float: H.numOrUndefined("2.5") === 2.5,
    integer: H.numOrUndefined("60") === 60,
  };
  return { pass: Object.values(checks).every(Boolean), detail: checks };
});
scenario("int_truncates_and_unsets", () => {
  // Integer-typed plugin config fields: same unset semantics as the float
  // path, value truncated like the old parseInt read "2.7" — but "" no
  // longer becomes 0 (parseInt("") || 0 did).
  const checks = {
    truncates: H.intOrUndefined("2.7") === 2,
    negativeTruncates: H.intOrUndefined("-2.7") === -2,
    emptyUnsets: H.intOrUndefined("") === undefined,
    zeroKept: H.intOrUndefined("0") === 0,
  };
  return { pass: Object.values(checks).every(Boolean), detail: checks };
});

process.stdout.write(JSON.stringify(results));

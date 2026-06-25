"use strict";
// Bundles variablesShared.helpers.ts (with the esbuild in web/programmer/
// node_modules) and exercises the cross-reference helpers behind the
// Variables / Device States "Used By" panels:
//   - scanBindingForVars / scanBindingForAllKeys treat press/release/change as
//     ARRAYS of actions (the shape the binding editor authors), so button-action
//     var/state references are no longer silently dropped.
//   - globMatch fully regex-escapes the pattern, so a script-derived key with
//     metacharacters can't crash (SyntaxError) or hang (ReDoS) the view.
//   - collectWildcardMatches resolves a wildcard against an arbitrary candidate
//     set, including device-only keys macros/UI never referenced.
// Prints JSON results to stdout; the Python wrapper skips when the Node
// toolchain or esbuild is absent.
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
const V = moduleObj.exports;

const collectVars = (bindings) => {
  const found = [];
  V.scanBindingForVars(bindings, (id) => found.push(id));
  return found;
};
const collectAllKeys = (bindings) => {
  const found = [];
  V.scanBindingForAllKeys(bindings, (key) => found.push(key));
  return found;
};

const results = {};

// --- H-126: event bindings are ARRAYS of actions ---------------------------

// A button whose press binding is an array with a Set Variable action. The old
// single-object scan read `.action` off the array (undefined) and found nothing.
results.h126_array_press_var_found = (() => {
  const ids = collectVars({
    press: [{ action: "state.set", key: "var.lights", value: true }],
  });
  return { pass: ids.includes("lights"), detail: ids };
})();

// Multiple actions in one event array — every var reference is surfaced.
results.h126_array_multi_action = (() => {
  const ids = collectVars({
    press: [
      { action: "device.command", device: "amp", command: "on" },
      { action: "state.set", key: "var.scene", value: "movie" },
    ],
    release: [{ action: "state.set", key: "var.held", value: false }],
  });
  return { pass: ids.includes("scene") && ids.includes("held"), detail: ids };
})();

// value_map nested inside an array action still resolves.
results.h126_array_value_map = (() => {
  const ids = collectVars({
    change: [
      {
        action: "value_map",
        map: { a: { action: "state.set", key: "var.mode", value: 1 } },
      },
    ],
  });
  return { pass: ids.includes("mode"), detail: ids };
})();

// scanBindingForAllKeys gets device.* keys out of an array event binding too.
results.h126_array_allkeys_device = (() => {
  const keys = collectAllKeys({
    press: [{ action: "state.set", key: "device.proj.power", value: "on" }],
  });
  return { pass: keys.includes("device.proj.power"), detail: keys };
})();

// Legacy single-object event binding still works (no regression).
results.h126_legacy_object_still_works = (() => {
  const ids = collectVars({
    press: { action: "state.set", key: "var.legacy", value: 1 },
  });
  return { pass: ids.includes("legacy"), detail: ids };
})();

// Non-event single-object bindings (two-way variable) are unchanged.
results.h126_two_way_binding = (() => {
  const ids = collectVars({ variable: { key: "var.vol" } });
  return { pass: ids.includes("vol"), detail: ids };
})();

// --- M-176: globMatch escapes regex metacharacters -------------------------

// A key with an unbalanced paren used to throw SyntaxError. Now "*" is the only
// special token, everything else is literal, so it matches safely.
results.m176_metachar_no_crash = (() => {
  try {
    const hit = V.globMatch("var.a*b(c", "var.axxb(c");
    const miss = V.globMatch("var.a*b(c", "var.zzz");
    return { pass: hit === true && miss === false, detail: { hit, miss } };
  } catch (e) {
    return { pass: false, detail: `threw: ${e}` };
  }
})();

// A catastrophic-backtracking pattern resolves immediately instead of hanging,
// because the metacharacters are now escaped to literals.
results.m176_no_redos = (() => {
  const start = Date.now();
  let value;
  try {
    value = V.globMatch("var.(a+)+!z", "var." + "a".repeat(60));
  } catch (e) {
    return { pass: false, detail: `threw: ${e}` };
  }
  const elapsed = Date.now() - start;
  return { pass: value === false && elapsed < 1000, detail: { value, elapsed } };
})();

// Wildcard semantics preserved: "*" still spans exactly one path segment.
results.m176_wildcard_segment = (() => {
  const a = V.globMatch("device.*.power", "device.proj.power");
  const b = V.globMatch("device.*.power", "device.proj.sub.power");
  return { pass: a === true && b === false, detail: { a, b } };
})();

// --- L-103: wildcard matches device-only candidate keys --------------------

// A script subscribing to one device's properties ("device.proj.*") must
// annotate that device's state keys even when no macro/UI references them — the
// L-103 fix matches the wildcard against the known device-key set, not just the
// macro/UI-seeded keys. ("*" spans a single path segment, mirroring the existing
// matcher; the device props here are single-segment, the common case.)
results.l103_wildcard_matches_device_keys = (() => {
  const hits = V.collectWildcardMatches("device.proj.*", [
    "device.proj.power",
    "device.proj.input",
    "var.lights",
    "device.amp.mute",
  ]);
  return {
    pass:
      hits.includes("device.proj.power") &&
      hits.includes("device.proj.input") &&
      !hits.includes("device.amp.mute") &&
      !hits.includes("var.lights"),
    detail: hits,
  };
})();

results.l103_wildcard_segment_scoped = (() => {
  const hits = V.collectWildcardMatches("device.*.power", [
    "device.proj.power",
    "device.amp.volume",
  ]);
  return { pass: hits.length === 1 && hits[0] === "device.proj.power", detail: hits };
})();

process.stdout.write(JSON.stringify(results));

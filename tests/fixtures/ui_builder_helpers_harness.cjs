"use strict";
// Loads the real UI Builder helpers (uiBuilderHelpers.ts, transpiled on the fly
// with the esbuild already in web/programmer/node_modules) and runs pure-logic
// checks for the grid-geometry / id / rename helpers, printing JSON results to
// stdout. Mirrors color_utils_harness.cjs: no build step, and the Python wrapper
// skips when the toolchain is absent rather than failing CI. The helper module
// has only `import type` statements, which esbuild strips, so it loads with no
// runtime imports.
const fs = require("fs");
const path = require("path");

const helpersPath = process.argv[2];
const src = fs.readFileSync(helpersPath, "utf8");

const esbuild = require("esbuild");
const { code } = esbuild.transformSync(src, { loader: "ts", format: "cjs" });
const moduleObj = { exports: {} };
const fn = new Function("exports", "require", "module", "__filename", "__dirname", code);
fn(moduleObj.exports, require, moduleObj, helpersPath, path.dirname(helpersPath));
const H = moduleObj.exports;

const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const results = {};

// --- H-038: clampOriginToGrid keeps the full span on-grid ---
{
  const fits = H.clampOriginToGrid(5, 3, 2, 2, 12, 8);
  results.h038_clamp_fits = { pass: eq(fits, { col: 5, row: 3 }), detail: fits };
}
{
  // col 11 + span 3 would reach col 13 on a 12-col grid; clamp to 12-3+1 = 10.
  const r = H.clampOriginToGrid(11, 1, 3, 2, 12, 8);
  results.h038_clamp_overflow_right = { pass: eq(r, { col: 10, row: 1 }), detail: r };
}
{
  // row 8 + span 3 overflows an 8-row grid; clamp to 8-3+1 = 6.
  const r = H.clampOriginToGrid(1, 8, 2, 3, 12, 8);
  results.h038_clamp_overflow_bottom = { pass: eq(r, { col: 1, row: 6 }), detail: r };
}
{
  const r = H.clampOriginToGrid(-2, 0, 3, 2, 12, 8);
  results.h038_clamp_min = { pass: eq(r, { col: 1, row: 1 }), detail: r };
}

// --- M-077: findFreeGridPosition is span- and overlap-aware ---
{
  const r = H.findFreeGridPosition([], 3, 2, 12, 8);
  results.m077_free_empty = { pass: eq(r, { col: 1, row: 1 }), detail: r };
}
{
  // A 3x2 element sits at (1,1); the next 3x2 must skip past it to (4,1),
  // not land on the first free single cell inside it.
  const els = [{ grid_area: { col: 1, row: 1, col_span: 3, row_span: 2 } }];
  const r = H.findFreeGridPosition(els, 3, 2, 12, 8);
  results.m077_free_avoid_overlap = { pass: eq(r, { col: 4, row: 1 }), detail: r };
}
{
  // 4x4 grid, (1,1,3,2) taken — a 3x2 can't fit on rows 1-2, drops to (1,3).
  const els = [{ grid_area: { col: 1, row: 1, col_span: 3, row_span: 2 } }];
  const r = H.findFreeGridPosition(els, 3, 2, 4, 4);
  results.m077_free_drop_down = { pass: eq(r, { col: 1, row: 3 }), detail: r };
}
{
  // Element wider than the grid → clamped (1,1) fallback, never off-grid.
  const r = H.findFreeGridPosition([], 6, 2, 4, 4);
  results.m077_free_too_big_fallback = { pass: eq(r, { col: 1, row: 1 }), detail: r };
}

// --- L-051: pointerToCell excludes the container padding from the cell area ---
{
  const r = H.pointerToCell(0, 0, 120, 0, 12);
  results.l051_ptc_basic = { pass: r === 1, detail: r };
}
{
  // 120px rect, 8px pad → 104px cell area. The centre (60) maps to cell 7.
  const r = H.pointerToCell(60, 0, 120, 8, 12);
  results.l051_ptc_center = { pass: r === 7, detail: r };
}
{
  // x=15 sits in cell 1 once the 8px left pad is removed; the un-padded mapping
  // (x/120*12) would mis-bin it as cell 2.
  const padded = H.pointerToCell(15, 0, 120, 8, 12);
  const unpadded = Math.floor((15 / 120) * 12) + 1;
  results.l051_ptc_pad_corrects_edge = {
    pass: padded === 1 && unpadded === 2,
    detail: { padded, unpadded },
  };
}

// --- H-039: duplicateElementInPage avoids reserved (master) ids ---
{
  const pages = [
    {
      id: "p1",
      grid: { columns: 12, rows: 8 },
      elements: [
        { id: "button_1", type: "button", grid_area: { col: 1, row: 1, col_span: 3, row_span: 2 }, style: {}, bindings: {} },
      ],
    },
  ];
  const withoutReserved = H.duplicateElementInPage(pages, "p1", "button_1");
  const noResId = withoutReserved[0].elements[1].id;
  // master "button_2" reserved → the duplicate must skip to button_3.
  const withReserved = H.duplicateElementInPage(pages, "p1", "button_1", ["button_2"]);
  const resId = withReserved[0].elements[1].id;
  results.h039_dup_reserved_skips_master = {
    pass: noResId === "button_2" && resId === "button_3",
    detail: { noResId, resId },
  };
}

// --- L-052: renameElement preserves untouched-scope array identity ---
function makeProject(macroKey) {
  return {
    pages: [
      {
        id: "p1",
        grid: { columns: 12, rows: 8 },
        elements: [{ id: "btn", type: "button", grid_area: { col: 1, row: 1, col_span: 3, row_span: 2 }, style: {}, bindings: {} }],
      },
    ],
    masters: [],
    macros: [{ id: "m1", name: "M1", steps: [{ action: "state.set", key: macroKey, value: 1 }] }],
    variables: [{ name: "v1", source_key: "device.x.power" }],
    scripts: [],
  };
}
{
  // Macro/var don't reference btn → those arrays come back by reference, while
  // pages (the renamed element lives there) is a fresh array.
  const p = makeProject("var.unrelated");
  const r = H.renameElement(p.pages, p.masters, p.macros, p.variables, p.scripts, "btn", "btn2");
  results.l052_rename_preserves_untouched = {
    pass:
      r.macros === p.macros &&
      r.variables === p.variables &&
      r.master_elements === p.masters &&
      r.pages !== p.pages &&
      r.pages[0].elements[0].id === "btn2",
    detail: {
      macrosSame: r.macros === p.macros,
      varsSame: r.variables === p.variables,
      mastersSame: r.master_elements === p.masters,
      pagesChanged: r.pages !== p.pages,
      newId: r.pages[0].elements[0].id,
    },
  };
}
{
  // A macro that DOES reference ui.btn.* must produce a fresh macros array, so
  // the guard isn't trivially always-true.
  const p = makeProject("ui.btn.pressed");
  const r = H.renameElement(p.pages, p.masters, p.macros, p.variables, p.scripts, "btn", "btn2");
  const rewritten = r.macros[0].steps[0].key;
  results.l052_rename_rewrites_referencing = {
    pass: r.macros !== p.macros && rewritten === "ui.btn2.pressed",
    detail: { macrosChanged: r.macros !== p.macros, rewritten },
  };
}

process.stdout.write(JSON.stringify(results));

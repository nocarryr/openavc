"use strict";
// Loads the restart-dialog poll helpers (restartPollHelpers.ts — zero-import
// pure logic) and checks the cert-error decision. The dialog used to flip to
// the "browser rejecting cert" state after 5 consecutive fetch failures alone,
// so a slow-but-healthy restart (server still rebinding) misdirected the user
// to install a CA cert; the decision now also requires polling to have run past
// the normal restart window. Mirrors project_import_harness.cjs. The Python
// wrapper skips when the Node toolchain or esbuild is absent.
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

const results = {};
const MIN = H.CERT_ERROR_MIN_ATTEMPTS;
const THRESH = H.CERT_ERROR_THRESHOLD;

const certCase = (key, expectsNewCert, failures, attempt, expected) => {
  const got = H.shouldEnterCertError(expectsNewCert, failures, attempt);
  results[key] = { pass: got === expected, detail: { expectsNewCert, failures, attempt, got, expected } };
};

// Persistent failures past the restart window with a new cert expected -> cert error.
certCase("l172_cert_error_when_persistent", true, THRESH, MIN, true);
// THE fix: enough failures but still early in the restart -> NOT a cert error
// (a healthy restart is still rebinding; old code showed cert-error here).
certCase("l172_no_cert_error_too_early", true, THRESH, MIN - 1, false);
certCase("l172_no_cert_error_very_early", true, THRESH, THRESH, false);
// Not enough consecutive failures -> no cert error.
certCase("l172_no_cert_error_below_threshold", true, THRESH - 1, MIN + 10, false);
// No new cert expected (same-protocol restart) -> never a cert error.
certCase("l172_no_cert_error_without_new_cert", false, THRESH + 20, MIN + 20, false);

process.stdout.write(JSON.stringify(results));

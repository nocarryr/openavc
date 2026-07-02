"use strict";
// Bundles the Programmer SPA's api/auth.ts (with the esbuild already in
// web/programmer/node_modules) and exercises the fetch-auth URL matching:
// the admin Basic credential must only ever ride same-origin /api requests.
// Scenarios cover the pure matcher (isSameOriginApiUrl) plus the installed
// interceptor itself, with faked window/sessionStorage capturing whether an
// Authorization header was attached. Prints JSON results to stdout; the
// Python wrapper skips when the Node toolchain or esbuild is absent.
const path = require("path");

const authPath = process.argv[2];

const esbuild = require("esbuild");
const built = esbuild.buildSync({
  entryPoints: [authPath],
  bundle: true,
  format: "cjs",
  platform: "node",
  write: false,
  logLevel: "silent",
});
const code = built.outputFiles[0].text;

// --- Fake browser globals (auth.ts touches them only inside functions) ---
const BASE = "http://192.168.4.10:8080/programmer";
const captured = [];
global.sessionStorage = {
  getItem: () => JSON.stringify({ user: "admin", pass: "secret" }),
  setItem() {},
  removeItem() {},
};
global.window = {
  fetch: async (input, init) => {
    captured.push({ input, init });
    return { status: 200 };
  },
  location: {
    href: BASE,
    origin: "http://192.168.4.10:8080",
    pathname: "/programmer",
  },
  dispatchEvent() {},
};

const moduleObj = { exports: {} };
const fn = new Function("exports", "require", "module", "__filename", "__dirname", code);
fn(moduleObj.exports, require, moduleObj, authPath, path.dirname(authPath));
const A = moduleObj.exports;
const match = A.isSameOriginApiUrl;

const results = {};

// --- Pure matcher: same-origin /api URLs still match ---
const positive = {
  same_origin_relative_api: "/api/status",
  same_origin_bare_relative_api: "api/status",
  same_origin_absolute_api: "http://192.168.4.10:8080/api/status",
  same_origin_api_with_query: "/api/auth/required?probe=1",
  tunnel_api_path: "/tunnel/abc123/api/status",
};
for (const [name, url] of Object.entries(positive)) {
  results[name] = { pass: match(url, BASE) === true, detail: url };
}

// --- Pure matcher: everything else gets no credential ---
const negative = {
  cross_origin_api_path_rejected: "https://elsewhere.example/api/leak",
  protocol_relative_rejected: "//elsewhere.example/api/leak",
  different_port_rejected: "http://192.168.4.10:9999/api/status",
  same_origin_non_api: "/assets/logo.png",
  api_only_in_query_rejected: "/page?redirect=/api/x",
  unparseable_url_rejected: "http://",
};
for (const [name, url] of Object.entries(negative)) {
  results[name] = { pass: match(url, BASE) === false, detail: url };
}

// --- Installed interceptor: header attachment end-to-end ---
async function interceptorChecks() {
  A.installFetchAuth();

  captured.length = 0;
  await window.fetch("/api/status");
  const sameOriginInit = captured[0] && captured[0].init;
  const sameOriginAuth =
    sameOriginInit && new Headers(sameOriginInit.headers).get("Authorization");
  results.interceptor_attaches_same_origin = {
    pass: typeof sameOriginAuth === "string" && sameOriginAuth.startsWith("Basic "),
    detail: sameOriginAuth || null,
  };

  captured.length = 0;
  await window.fetch("https://elsewhere.example/api/leak");
  const crossInit = captured[0] && captured[0].init;
  const crossAuth =
    crossInit && crossInit.headers
      ? new Headers(crossInit.headers).get("Authorization")
      : null;
  results.interceptor_no_credential_cross_origin = {
    pass: crossAuth === null || crossAuth === undefined,
    detail: crossAuth || null,
  };
}

interceptorChecks().then(
  () => process.stdout.write(JSON.stringify(results)),
  (err) => {
    process.stderr.write(String(err && err.stack ? err.stack : err));
    process.exit(1);
  },
);

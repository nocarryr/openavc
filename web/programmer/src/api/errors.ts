// Shared API error helper.
//
// `request()` in api/base.ts throws Errors of the form:
//     "API 409: {\"detail\":\"Cannot uninstall: driver is in use ...\"}"
// This helper unwraps that envelope so views/stores can surface the clean
// human-readable detail instead of the raw JSON.

export function parseApiError(e: unknown): string {
  if (!(e instanceof Error)) return String(e);
  const match = e.message.match(/^API \d+: (.+)/s);
  if (!match) return e.message;
  try {
    const body = JSON.parse(match[1]);
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (detail?.message) {
      const errors: string[] = detail.errors ?? [];
      return errors.length ? `${detail.message}:\n${errors.join("\n")}` : detail.message;
    }
  } catch { /* not JSON, fall through */ }
  return e.message;
}

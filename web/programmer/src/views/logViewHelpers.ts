// Pure helpers for LogView filtering, kept free of React so the test
// harness can exercise them directly.

import type { LogEntry } from "../store/logStore";

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Predicate for the System Log Device filter. An entry belongs to a device
 * when the structured device field matches (driver/transport lines carry a
 * "[id] " prefix the server extracts), or when the message mentions the id
 * as a whole token — device lifecycle lines phrase it loosely, e.g.
 * "Failed to connect 'proj1'". Token boundaries exclude id characters so
 * "proj1" never matches "proj12" or "my-proj1".
 */
export function deviceFilterPredicate(
  deviceId: string,
): (entry: Pick<LogEntry, "device" | "message">) => boolean {
  const id = deviceId.toLowerCase();
  const mention = new RegExp(
    `(^|[^a-z0-9_-])${escapeRegExp(id)}([^a-z0-9_-]|$)`,
    "i",
  );
  return (entry) =>
    entry.device.toLowerCase() === id || mention.test(entry.message);
}

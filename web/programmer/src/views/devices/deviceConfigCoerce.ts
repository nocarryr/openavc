// Coerce a device-config value from its string form (as held by the dialog
// inputs) into the typed value stored in the project, based on the field's
// config_schema `type`.
//
// The Add and Edit dialogs both use this so they can't drift — the drift was
// the bug: the Add dialog stored an object-typed field (e.g. the generic_tcp
// `commands` map) as a raw string, which then broke command sending at runtime
// with an AttributeError. An object field that isn't valid JSON now reports a
// clear error instead of being silently stored as a string.

export type CoerceResult =
  | { ok: true; value: unknown }
  | { ok: false; error: string };

const SIMPLE_NUMBER = /^-?\d+(\.\d+)?$/;

export function coerceConfigValue(val: string, fieldType: string): CoerceResult {
  if (fieldType === "boolean") {
    return { ok: true, value: val === "true" };
  }
  if (fieldType === "integer" || fieldType === "number" || fieldType === "float") {
    return { ok: true, value: SIMPLE_NUMBER.test(val) ? Number(val) : val };
  }
  if (fieldType === "text") {
    // Multi-line free text — preserve the raw string, no coercion.
    return { ok: true, value: val };
  }
  if (fieldType === "object" || fieldType === "json") {
    let parsed: unknown;
    try {
      parsed = JSON.parse(val);
    } catch {
      return { ok: false, error: "must be valid JSON" };
    }
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
      return { ok: false, error: "must be a JSON object" };
    }
    return { ok: true, value: parsed };
  }
  // Untyped / string: accept a JSON object if it happens to parse (back-compat
  // with the Edit dialog), else a plain number, else the raw string.
  try {
    const parsed = JSON.parse(val);
    if (typeof parsed === "object" && parsed !== null) {
      return { ok: true, value: parsed };
    }
  } catch {
    /* not JSON — fall through to number / string */
  }
  return { ok: true, value: SIMPLE_NUMBER.test(val) ? Number(val) : val };
}

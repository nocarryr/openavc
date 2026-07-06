// Pure parsing for numeric property inputs, split out so it can be unit
// tested without React (see openavc/tests/test_numeric_field_helpers.py).
// Mirrors the other UI Builder helper modules.

/**
 * Parse a numeric property input. Clearing the field ("" — usually to
 * retype) means "unset": the property key is removed and the runtime
 * default applies, instead of committing a literal 0 that breaks controls
 * (digits=0 keypad, step=0 slider). Unparseable input is likewise dropped,
 * never stored as 0 or NaN. The editors pair this with `value={x ?? ""}`
 * and a placeholder showing the effective default.
 */
export function numOrUndefined(raw: string): number | undefined {
  if (raw.trim() === "") return undefined;
  const n = Number(raw);
  return Number.isFinite(n) ? n : undefined;
}

/** numOrUndefined for integer-typed fields: same unset semantics, value
 *  truncated toward zero (matching the old parseInt reading of "2.7"). */
export function intOrUndefined(raw: string): number | undefined {
  const n = numOrUndefined(raw);
  return n === undefined ? undefined : Math.trunc(n);
}

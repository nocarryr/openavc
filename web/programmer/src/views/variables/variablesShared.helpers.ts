// Pure cross-reference helpers for the Variables / Device States sub-tabs.
// Extracted from variablesShared.tsx so the binding-scan + glob logic can be
// unit-tested without React/lucide. See tests/test_variables_shared_helpers.py.

/**
 * Glob matcher for state-key patterns like "device.*.power". A "*" matches one
 * path segment (no dots). The pattern is fully regex-escaped first, so a
 * script-derived key carrying regex metacharacters (parentheses, +, brackets,
 * etc.) can never crash the view with a SyntaxError or hang it via ReDoS — only
 * "*" is treated as special.
 */
export function globMatch(pattern: string, key: string): boolean {
  if (pattern === key) return true;
  if (!pattern.includes("*")) return false;
  // Escape every regex metacharacter, then turn the (now-escaped) "*" back into
  // a single-segment wildcard.
  const escaped = pattern.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const regex = new RegExp("^" + escaped.replace(/\\\*/g, "[^.]+") + "$");
  return regex.test(key);
}

/**
 * Normalize an event-binding slot (press/release/change) to a list of action
 * objects. The UI authors these as arrays of actions (PressBindingEditor), but
 * legacy projects and the panel runtime also accept a single action object, so
 * we accept both shapes.
 */
function asActionList(binding: unknown): Record<string, any>[] {
  if (Array.isArray(binding)) return binding as Record<string, any>[];
  if (binding && typeof binding === "object") return [binding as Record<string, any>];
  return [];
}

/** Scan an element's bindings for var.* references. */
export function scanBindingForVars(
  bindings: Record<string, unknown>,
  onFound: (varId: string, detail: string) => void,
) {
  if (!bindings) return;

  const checkKey = (obj: any, context: string) => {
    if (!obj || typeof obj !== "object") return;
    const key = obj.key as string | undefined;
    if (key?.startsWith("var.")) {
      onFound(key.slice(4), context);
    }
  };

  if (bindings.variable) checkKey(bindings.variable, "Two-way variable binding");
  if (bindings.text) checkKey(bindings.text, "Text display binding");
  if (bindings.feedback) checkKey(bindings.feedback, "Feedback/color binding");

  for (const eventType of ["press", "release", "change"]) {
    for (const action of asActionList(bindings[eventType])) {
      if (action.action === "state.set" && typeof action.key === "string" && action.key.startsWith("var.")) {
        onFound(action.key.slice(4), `${eventType} → Set Variable`);
      }
      if (action.action === "value_map" && action.map) {
        const actionMap = action.map as Record<string, any>;
        for (const [optVal, subAction] of Object.entries(actionMap)) {
          if (subAction?.action === "state.set" && typeof subAction.key === "string" && subAction.key.startsWith("var.")) {
            onFound(subAction.key.slice(4), `${eventType} → ${optVal} → Set Variable`);
          }
        }
      }
    }
  }

  if (bindings.value) checkKey(bindings.value, "Slider value source");
}

/** Scan an element's bindings for ALL state key references (not just var.*). */
export function scanBindingForAllKeys(
  bindings: Record<string, unknown>,
  onFound: (key: string, detail: string) => void,
) {
  if (!bindings) return;

  const checkKey = (obj: any, context: string) => {
    if (!obj || typeof obj !== "object") return;
    const key = obj.key as string | undefined;
    if (key) onFound(key, context);
  };

  if (bindings.variable) checkKey(bindings.variable, "Two-way binding");
  if (bindings.text) checkKey(bindings.text, "Text display binding");
  if (bindings.feedback) checkKey(bindings.feedback, "Feedback binding");
  if (bindings.color) checkKey(bindings.color, "Color binding");

  for (const eventType of ["press", "release", "change"]) {
    for (const action of asActionList(bindings[eventType])) {
      if (action.action === "state.set" && typeof action.key === "string") {
        onFound(action.key, `${eventType} → Set state`);
      }
      if (action.action === "value_map" && action.map) {
        const actionMap = action.map as Record<string, any>;
        for (const [optVal, subAction] of Object.entries(actionMap)) {
          if (subAction?.action === "state.set" && typeof subAction.key === "string") {
            onFound(subAction.key, `${eventType} → ${optVal} → Set state`);
          }
        }
      }
    }
  }

  if (bindings.value) checkKey(bindings.value, "Slider value source");
}

/**
 * Return every candidate key matched by a wildcard pattern (e.g. "device.*").
 * Used so a wildcard script reference can annotate device state keys that only
 * it touches — those keys aren't seeded into the usage map by macros/UI, so they
 * must be matched against the known device-key set, not just the seeded keys.
 */
export function collectWildcardMatches(pattern: string, candidateKeys: Iterable<string>): string[] {
  const out: string[] = [];
  for (const key of candidateKeys) {
    if (globMatch(pattern, key)) out.push(key);
  }
  return out;
}

import type {
  DriverDefinition,
  DriverEachChildQuery,
  DriverGatedQuery,
} from "../../api/types";

/**
 * Shape helpers for the entries in `polling.queries` and `on_connect`, shared
 * by PollingConfig and LifecycleEditor so the two can't drift.
 *
 * An entry is one of:
 *   "PWR?\r"                                        plain wire string
 *   { each_child, send }                            one query per child
 *   { send, when }                                  gated on a config field
 *   { each_child, send, when }                      both
 *   { address, args }                               OSC on_connect (opaque here)
 *
 * `when: <config_field>` runs the entry only while that config field is truthy
 * — how a driver arms a chatty subscription (a level-meter stream) behind an
 * integrator checkbox instead of forcing it on every site.
 */
export type QueryEntry =
  | string
  | DriverEachChildQuery
  | DriverGatedQuery
  | Record<string, unknown>;

export function isEachChild(q: QueryEntry): q is DriverEachChildQuery {
  return typeof q === "object" && q !== null && "each_child" in q;
}

export function isGated(q: QueryEntry): q is DriverGatedQuery {
  return (
    typeof q === "object" &&
    q !== null &&
    !("each_child" in q) &&
    typeof (q as DriverGatedQuery).send === "string"
  );
}

/** An object entry we have no inline editor for (an OSC {address, args} step).
 *  Shown read-only rather than corrupted. */
export function isOpaque(q: QueryEntry): boolean {
  return typeof q !== "string" && !isEachChild(q) && !isGated(q);
}

export function querySend(q: QueryEntry): string {
  if (typeof q === "string") return q;
  if (isEachChild(q) || isGated(q)) return q.send;
  return "";
}

export function queryWhen(q: QueryEntry): string {
  if (isEachChild(q) || isGated(q)) return q.when ?? "";
  return "";
}

/** Rebuild an entry from its parts, collapsing to the simplest form that can
 *  carry them: a plain string when it needs neither a child type nor a gate. */
export function buildQueryEntry(
  send: string,
  eachChild: string,
  when: string,
): QueryEntry {
  if (eachChild) {
    return when ? { each_child: eachChild, send, when } : { each_child: eachChild, send };
  }
  return when ? { send, when } : send;
}

/** Config fields a `when:` gate can name — declared in either block, deduped.
 *  Booleans come first: a gate is nearly always a checkbox. */
export function gateFieldNames(draft: DriverDefinition): string[] {
  const schema = (draft.config_schema ?? {}) as Record<
    string,
    { type?: string } | undefined
  >;
  const names = new Set([
    ...Object.keys(schema),
    ...Object.keys((draft.default_config ?? {}) as Record<string, unknown>),
  ]);
  return [...names].sort((a, b) => {
    const aBool = schema[a]?.type === "boolean" ? 0 : 1;
    const bBool = schema[b]?.type === "boolean" ? 0 : 1;
    return aBool - bBool || a.localeCompare(b);
  });
}

import type { DriverDefinition } from "../api/types";
import { validateDriver } from "../components/driver-builder/validateDriver";

/**
 * State patch to apply after a successful driver save.
 *
 * The editor inputs (the ID field included) stay editable while the save
 * network round-trip is in flight, so the user can keep typing during the
 * await. This reconciles three outcomes without clobbering their work:
 *
 *  - draft untouched during the await   -> mark clean, select the saved id.
 *  - draft edited in place during await  -> keep it dirty (don't silently
 *    discard the edits) but still point selection at the id we actually
 *    persisted, so the next save targets the right record instead of a stale
 *    one.
 *  - user navigated to a different driver mid-save -> leave their selection
 *    alone; only clear the saving flag.
 */
export type SavePatch =
  | { saving: false }
  | { saving: false; dirty: boolean; selectedId: string };

export function reconcileAfterSave(args: {
  savedId: string;
  draftUnchanged: boolean;
  selectionUnchanged: boolean;
}): SavePatch {
  if (args.draftUnchanged) {
    return { saving: false, dirty: false, selectedId: args.savedId };
  }
  if (args.selectionUnchanged) {
    return { saving: false, dirty: true, selectedId: args.savedId };
  }
  return { saving: false };
}

/**
 * Latest-wins guard for overlapping async list refreshes. Each refresh takes a
 * token via next(); when it resolves it applies its result only if it is still
 * the latest started refresh (isCurrent). This makes the newest-started request
 * win regardless of which network GET happens to resolve last, so two
 * overlapping install/uninstall refreshes can't settle on a stale snapshot.
 */
export interface LatestWins {
  next: () => number;
  isCurrent: (token: number) => boolean;
}

export function makeLatestWins(): LatestWins {
  let latest = 0;
  return {
    next: () => {
      latest += 1;
      return latest;
    },
    isCurrent: (token: number) => token === latest,
  };
}

/**
 * Blocking problems that should stop an imported/pasted driver from being
 * created server-side. Returns clean, user-facing messages (empty array = safe
 * to create) drawn from the same validator the form editor uses, so the import
 * path surfaces structured issues instead of a terse backend 422. Transport
 * isn't covered by validateDriver (the editor always defaults one) so it's
 * checked explicitly here.
 */
export function importBlockers(
  definition: DriverDefinition,
  siblings: DriverDefinition[],
): string[] {
  const messages: string[] = [];
  if (!definition.transport) {
    messages.push("Transport is required (tcp, serial, udp, http, or osc).");
  }
  for (const issue of validateDriver(definition, siblings, null)) {
    if (issue.severity === "error") messages.push(issue.message);
  }
  return messages;
}

import type { DriverDefinition, DriverCommandDef } from "../../api/types";

export type IssueSection =
  | "general"
  | "connection"
  | "behavior"
  | "discovery"
  | "simulation"
  | "test";

export interface ValidationIssue {
  severity: "error" | "warning";
  section: IssueSection;
  message: string;
  /** Identity anchor for inline rendering — caller decides what to do. */
  field?: string;
  command?: string;
  param?: string;
}

/** Built-in transport config keys that the runtime injects automatically. */
const BASELINE_CONFIG_KEYS = new Set([
  "host",
  "port",
  "baudrate",
  "parity",
  "bytesize",
  "stopbits",
  "poll_interval",
  "inter_command_delay",
  "username",
  "password",
  "timeout",
  "token",
  "api_key",
]);

const ID_RE = /^[a-z][a-z0-9_]*$/;
const PARAM_NAME_RE = /^[a-zA-Z_][a-zA-Z0-9_]*$/;
const PLACEHOLDER_RE = /\{(\w+)\}/g;
// Child type ids and per-child field ids share the device state-key
// namespace, so they follow the same lowercase-identifier rule.
const CHILD_ID_RE = /^[a-z][a-z0-9_]*$/;

/**
 * Validate a driver draft against the runtime contract.
 *
 * Returns a flat list of issues; consumers slice by section to render.
 * Errors block save (caller's responsibility); warnings flag publish-quality
 * problems (missing description, etc.) without blocking.
 *
 * @param draft   The current draft.
 * @param siblings Other saved definitions — used for ID collision detection.
 *                 Pass an empty array for a brand-new draft with no peers.
 * @param originalId The id this draft was loaded under (null for a new draft).
 *                   Lets us skip the "duplicate id" warning when the user is
 *                   editing in place without renaming.
 */
export function validateDriver(
  draft: DriverDefinition,
  siblings: DriverDefinition[],
  originalId: string | null,
): ValidationIssue[] {
  const issues: ValidationIssue[] = [];

  // ── Identity ──────────────────────────────────────────────────────────
  if (!draft.id) {
    issues.push({
      severity: "error",
      section: "general",
      field: "id",
      message: "Driver ID is required.",
    });
  } else if (!ID_RE.test(draft.id)) {
    issues.push({
      severity: "error",
      section: "general",
      field: "id",
      message:
        "ID must start with a lowercase letter and use only lowercase letters, digits, and underscores.",
    });
  } else if (
    draft.id !== originalId &&
    siblings.some((s) => s.id === draft.id && s.id !== originalId)
  ) {
    issues.push({
      severity: "error",
      section: "general",
      field: "id",
      message: `Another driver named "${draft.id}" already exists. Choose a different ID.`,
    });
  }

  if (!draft.name?.trim()) {
    issues.push({
      severity: "error",
      section: "general",
      field: "name",
      message: "Driver name is required.",
    });
  }

  // ── Publish-quality warnings ──────────────────────────────────────────
  if (!draft.description?.trim()) {
    issues.push({
      severity: "warning",
      section: "general",
      field: "description",
      message:
        "Description is empty. Required for community drivers — describe the device family in one sentence.",
    });
  }
  if (!draft.version?.trim()) {
    issues.push({
      severity: "warning",
      section: "general",
      field: "version",
      message: "Version is empty. Use semver (e.g. 1.0.0).",
    });
  }
  if (!draft.author?.trim()) {
    issues.push({
      severity: "warning",
      section: "general",
      field: "author",
      message: "Author is empty. Required for community drivers.",
    });
  }
  if (!draft.help?.overview?.trim()) {
    issues.push({
      severity: "warning",
      section: "general",
      field: "help.overview",
      message:
        "Help overview is empty. Integrators see this in the Add Device dialog — explain what the device is.",
    });
  }

  // ── Child entity types ───────────────────────────────────────────────
  const childTypes = draft.child_entity_types ?? {};
  const childTypeNames = new Set(Object.keys(childTypes));
  for (const [typeName, typeDef] of Object.entries(childTypes)) {
    if (!CHILD_ID_RE.test(typeName)) {
      issues.push({
        severity: "error",
        section: "behavior",
        field: `child_entity_types.${typeName}`,
        message: `Child type "${typeName}" must start with a lowercase letter and use only lowercase letters, digits, and underscores.`,
      });
    }
    if (!typeDef.label?.trim()) {
      issues.push({
        severity: "warning",
        section: "behavior",
        field: `child_entity_types.${typeName}`,
        message: `Child type "${typeName}" has no label. Integrators see this in the Child Entities tab.`,
      });
    }

    // id_format sanity. v1 only supports integer IDs; the runtime raises
    // on anything else, so flag a non-integer type as an error.
    const idf = typeDef.id_format ?? { type: "integer" };
    if (idf.type !== "integer") {
      issues.push({
        severity: "error",
        section: "behavior",
        field: `child_entity_types.${typeName}.id_format`,
        message: `Child type "${typeName}" id_format.type must be "integer" (only integer IDs are supported).`,
      });
    }
    if (
      typeof idf.min === "number" &&
      typeof idf.max === "number" &&
      idf.max < idf.min
    ) {
      issues.push({
        severity: "error",
        section: "behavior",
        field: `child_entity_types.${typeName}.id_format`,
        message: `Child type "${typeName}" id_format.max (${idf.max}) is less than min (${idf.min}).`,
      });
    }
    if (typeof idf.pad_width === "number" && idf.pad_width < 0) {
      issues.push({
        severity: "error",
        section: "behavior",
        field: `child_entity_types.${typeName}.id_format`,
        message: `Child type "${typeName}" id_format.pad_width can't be negative.`,
      });
    }

    // State fields.
    const stateVars = typeDef.state_variables ?? {};
    const fieldNames = Object.keys(stateVars);
    if (fieldNames.length === 0) {
      issues.push({
        severity: "warning",
        section: "behavior",
        field: `child_entity_types.${typeName}`,
        message: `Child type "${typeName}" declares no state fields. Each child would only carry the platform's online/label keys.`,
      });
    }
    for (const fieldName of fieldNames) {
      if (!CHILD_ID_RE.test(fieldName)) {
        issues.push({
          severity: "error",
          section: "behavior",
          field: `child_entity_types.${typeName}.${fieldName}`,
          message: `Field "${fieldName}" in child type "${typeName}" must use lowercase letters, digits, and underscores only.`,
        });
      }
    }

    // summary_fields / label_field must reference declared fields. `online`
    // and `label` are platform-injected, so they're always valid targets.
    const fieldSet = new Set([...fieldNames, "online", "label"]);
    for (const sf of typeDef.summary_fields ?? []) {
      if (!fieldSet.has(sf)) {
        issues.push({
          severity: "warning",
          section: "behavior",
          field: `child_entity_types.${typeName}.summary_fields`,
          message: `Child type "${typeName}" summary field "${sf}" isn't a declared state field.`,
        });
      }
    }
    if (typeDef.label_field && !fieldSet.has(typeDef.label_field)) {
      issues.push({
        severity: "warning",
        section: "behavior",
        field: `child_entity_types.${typeName}.label_field`,
        message: `Child type "${typeName}" name field "${typeDef.label_field}" isn't a declared state field.`,
      });
    }
  }

  // ── Commands: param-name legality + placeholder coverage ─────────────
  const configKeys = new Set([
    ...Object.keys(draft.config_schema ?? {}),
    ...BASELINE_CONFIG_KEYS,
  ]);

  for (const [cmdName, cmd] of Object.entries(draft.commands ?? {})) {
    const declaredParams = new Set(Object.keys(cmd.params ?? {}));

    // child_id params must name a declared child type, else the runtime
    // command picker has nothing to populate the dropdown from.
    for (const [paramName, paramDef] of Object.entries(cmd.params ?? {})) {
      if (paramDef.type !== "child_id") continue;
      if (!paramDef.child_type) {
        issues.push({
          severity: "error",
          section: "behavior",
          command: cmdName,
          param: paramName,
          message: `Parameter "${paramName}" in command "${cmdName}" is a Child ID but no child type is selected.`,
        });
      } else if (!childTypeNames.has(paramDef.child_type)) {
        issues.push({
          severity: "error",
          section: "behavior",
          command: cmdName,
          param: paramName,
          message: `Parameter "${paramName}" in command "${cmdName}" references child type "${paramDef.child_type}", which isn't declared in Child Entity Types.`,
        });
      }
    }

    // Param-name legality. The renamer used to silently strip illegal
    // characters; flag the residue so the user understands what got
    // trimmed.
    for (const paramName of declaredParams) {
      if (!PARAM_NAME_RE.test(paramName)) {
        issues.push({
          severity: "error",
          section: "behavior",
          command: cmdName,
          param: paramName,
          message: `Parameter "${paramName}" in command "${cmdName}" has illegal characters. Use letters, digits, and underscores only.`,
        });
      }
    }

    // Walk every wire-format string and collect placeholders. Anything
    // not in declared params or config keys is undeclared — almost
    // always a typo that would silently leave a literal {token} on
    // the wire.
    const wireStrings = collectWireStrings(cmd);
    const seen = new Set<string>();
    for (const wire of wireStrings) {
      let m: RegExpExecArray | null;
      const re = new RegExp(PLACEHOLDER_RE.source, "g");
      while ((m = re.exec(wire))) {
        const token = m[1];
        if (seen.has(token)) continue;
        seen.add(token);
        if (declaredParams.has(token) || configKeys.has(token)) continue;
        issues.push({
          severity: "warning",
          section: "behavior",
          command: cmdName,
          message: `Command "${cmdName}" references {${token}} but no parameter or config field of that name is declared.`,
        });
      }
    }
  }

  return issues;
}

/** Concatenate every wire-format field that supports {placeholders}. */
function collectWireStrings(cmd: DriverCommandDef): string[] {
  const out: string[] = [];
  const push = (s: string | undefined | null) => {
    if (s) out.push(s);
  };

  push(cmd.send);
  push(cmd.string);
  push(cmd.path);
  push(cmd.body);
  push(cmd.address);

  if (cmd.headers) {
    for (const [k, v] of Object.entries(cmd.headers)) {
      out.push(`${k}: ${v}`);
    }
  }
  if (cmd.query_params) {
    for (const [k, v] of Object.entries(cmd.query_params)) {
      out.push(`${k}=${v}`);
    }
  }
  if (cmd.args) {
    for (const a of cmd.args) {
      if (a.value) out.push(a.value);
    }
  }
  return out;
}

/** Filter helpers used by editors and tab badges. */
export function issuesFor(
  issues: ValidationIssue[],
  section: IssueSection,
): ValidationIssue[] {
  return issues.filter((i) => i.section === section);
}

export function hasError(issues: ValidationIssue[]): boolean {
  return issues.some((i) => i.severity === "error");
}

export function hasWarning(issues: ValidationIssue[]): boolean {
  return issues.some((i) => i.severity === "warning");
}

import { useEffect, useId, useState } from "react";
import type { CSSProperties } from "react";
import * as api from "../../api/restClient";
import type { ChildEntityEntry, DriverParamDef } from "../../api/types";
import { useConnectionStore } from "../../store/connectionStore";
import { childSchemaOptions, parseStateOptionList } from "./paramOptions";
import type { ParamOption } from "./paramOptions";
import { VariableKeyPicker } from "./VariableKeyPicker";

/** The widget for a single command/action parameter — the part that varies by
 *  the param's declared type. One shared control so every authoring surface
 *  (device Send Command, Quick Actions, macro steps, UI Builder bindings)
 *  renders the same dropdowns instead of free-typing values that can be
 *  misspelled. The label/help chrome stays with each surface; this owns only
 *  the input control.
 *
 *  Value in/out is a string (the convention all surfaces already use; numeric
 *  and boolean coercion happens at submit). Supports:
 *   - enum            -> select of the declared `values`
 *   - boolean         -> Yes/No select
 *   - child_id        -> live dropdown of the device's registered children of
 *                        `child_type` (needs `deviceId`); falls back to text
 *   - options_from    -> cascade: a combobox of the controls on the child
 *                        chosen in a sibling `child_id` param (needs `deviceId`
 *                        + `values` + `params`)
 *   - options_state /
 *     options_source  -> combobox sourced from a state-published list
 *                        (device-relative or absolute state key)
 *   - integer/number/float -> number input (honors min/max)
 *   - password/secret -> masked input (never pre-filled)
 *   - everything else -> text input
 *  With `allowDynamic`, a "$" toggle swaps the static control for a state-key
 *  picker ($var/$state, plus $trigger when `showTriggerContext`) — for surfaces
 *  whose runtime resolves $-prefixed values (macro steps). */

export interface ParamInputProps {
  // DriverParamDef plus `secret` (carried by action params) so password fields
  // render masked from either schema source.
  def: Partial<DriverParamDef> & { secret?: boolean };
  value: string;
  onChange: (value: string) => void;
  /** Enables the child_id dropdown (fetches the device's live children) and
   *  resolves `options_state` keys (`device.<deviceId>.<key>`). */
  deviceId?: string;
  /** The full param->value map of the command/action being authored. Lets a
   *  cascading param (`options_from`) read the sibling value it depends on. */
  values?: Record<string, unknown>;
  /** The full param schema of the command/action. Lets a cascading param find
   *  the sibling's `child_type` so it can offer that child's controls. */
  params?: Record<string, Partial<DriverParamDef>>;
  /** Show the "$" toggle -> VariableKeyPicker for dynamic state references. */
  allowDynamic?: boolean;
  /** Pass-through to VariableKeyPicker (offer $trigger.<field> refs). */
  showTriggerContext?: boolean;
  /** Placeholder for free-text inputs (defaults handled per-type). */
  placeholder?: string;
  /** Style for the widget row (e.g. { flex: 1 }). */
  style?: CSSProperties;
}

/** A param value is a dynamic state reference (and should render the picker). */
export function isDynamicParamValue(v: unknown): v is string {
  return typeof v === "string" && v.startsWith("$");
}

const toggleStyle = (active: boolean): CSSProperties => ({
  display: "flex",
  alignItems: "center",
  padding: "3px 6px",
  borderRadius: "var(--border-radius)",
  border: `1px solid ${active ? "var(--accent)" : "var(--border-color)"}`,
  background: active ? "rgba(138,180,147,0.15)" : "transparent",
  color: active ? "var(--accent)" : "var(--text-muted)",
  fontSize: 11,
  cursor: "pointer",
  flexShrink: 0,
  fontFamily: "var(--font-mono)",
});

export function ParamInput({
  def,
  value,
  onChange,
  deviceId,
  values,
  params,
  allowDynamic,
  showTriggerContext,
  placeholder,
  style,
}: ParamInputProps) {
  const type = def.type || "string";
  const optionsFrom =
    def.options_from?.source === "child_schema" ? def.options_from : undefined;

  // The child type whose live children this field needs:
  //  - a child_id field needs its own declared child_type;
  //  - a cascading field needs the sibling child_id param's child_type.
  const ownChildType = type === "child_id" ? def.child_type : undefined;
  const siblingChildType = optionsFrom
    ? params?.[optionsFrom.param]?.child_type
    : undefined;
  const fetchChildType = ownChildType ?? siblingChildType;

  // Children register dynamically as the driver discovers them, so fetch fresh
  // per field. `undefined` => still loading.
  const [children, setChildren] = useState<ChildEntityEntry[] | undefined>(
    undefined,
  );
  useEffect(() => {
    if (!fetchChildType || !deviceId) return;
    let cancelled = false;
    api
      .listChildEntitiesByType(deviceId, fetchChildType)
      .then((resp) => {
        if (!cancelled) setChildren(resp.children);
      })
      .catch(() => {
        if (!cancelled) setChildren([]);
      });
    return () => {
      cancelled = true;
    };
  }, [fetchChildType, deviceId]);

  // State-sourced options: a device-relative key (`options_state`, resolved
  // against this device) or an absolute key (`options_source`, verbatim).
  const stateOptionKey = def.options_state
    ? deviceId
      ? `device.${deviceId}.${def.options_state}`
      : undefined
    : def.options_source || undefined;
  const stateOptionRaw = useConnectionStore((s) =>
    stateOptionKey ? s.liveState[stateOptionKey] : undefined,
  );

  const datalistId = useId();

  const rowStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: 4,
    ...style,
  };

  // A child reference as a state key is a non-sensible combo, so child_id never
  // shows the dynamic toggle.
  const canToggle = allowDynamic && type !== "child_id";
  const dynamic = canToggle && isDynamicParamValue(value);

  const toggle = canToggle ? (
    <button
      type="button"
      onClick={() => onChange(dynamic ? "" : "$var.")}
      title={
        dynamic
          ? "Switch to a fixed value"
          : "Use a dynamic value read from state at runtime"
      }
      style={toggleStyle(!!dynamic)}
    >
      $
    </button>
  ) : null;

  if (dynamic) {
    return (
      <div style={rowStyle}>
        <VariableKeyPicker
          value={value.slice(1)}
          onChange={(key) => onChange(`$${key}`)}
          showDeviceState
          showTriggerContext={showTriggerContext}
          placeholder="Select state key..."
          style={{ flex: 1 }}
        />
        {toggle}
      </div>
    );
  }

  // Resolve option-provider lists. A combobox (input + datalist) renders these
  // so the user can pick a known value or type one the platform can't yet see
  // (offline device, control not discovered, escape-hatch command).
  let comboOptions: ParamOption[] | undefined;
  let comboHint: string | undefined;
  if (optionsFrom) {
    if (!deviceId || !siblingChildType) {
      comboOptions = []; // unresolvable here -> behaves as forgiving free text
    } else {
      const siblingValue = values?.[optionsFrom.param];
      const sv = siblingValue == null ? "" : String(siblingValue);
      if (!sv) {
        comboOptions = [];
        comboHint = `Pick ${optionsFrom.param} first to list its controls.`;
      } else {
        const chosen = (children ?? []).find(
          (c) => String(c.local_id) === sv || c.local_id_padded === sv,
        );
        comboOptions = childSchemaOptions(chosen?.schema);
        if (children !== undefined && !chosen) {
          comboHint = `No "${sv}" found — type the control name.`;
        }
      }
    }
  } else if (stateOptionKey || def.options_state || def.options_source) {
    comboOptions = parseStateOptionList(stateOptionRaw);
  }

  let widget: React.ReactNode;
  if (type === "enum" && def.values) {
    widget = (
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{ flex: 1 }}
      >
        {!def.required && <option value="">(none)</option>}
        {def.values.map((v) => (
          <option key={v} value={v}>
            {v}
          </option>
        ))}
      </select>
    );
  } else if (comboOptions !== undefined) {
    const isNumberCombo =
      type === "integer" || type === "number" || type === "float";
    widget = (
      <div style={{ flex: 1 }}>
        <input
          type={isNumberCombo ? "number" : "text"}
          list={comboOptions.length > 0 ? datalistId : undefined}
          value={value}
          min={def.min}
          max={def.max}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder ?? ""}
          style={{ width: "100%" }}
        />
        {comboOptions.length > 0 && (
          <datalist id={datalistId}>
            {comboOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label !== o.value ? o.label : undefined}
              </option>
            ))}
          </datalist>
        )}
        {comboHint && (
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
            {comboHint}
          </div>
        )}
      </div>
    );
  } else if (type === "boolean") {
    widget = (
      <select
        value={value || "false"}
        onChange={(e) => onChange(e.target.value)}
        style={{ flex: 1 }}
      >
        <option value="true">Yes</option>
        <option value="false">No</option>
      </select>
    );
  } else if (ownChildType && deviceId) {
    const registered = (children ?? []).filter((c) => c.registered);
    widget = (
      <div style={{ flex: 1 }}>
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          style={{ width: "100%" }}
        >
          <option value="">
            {children === undefined
              ? "Loading children..."
              : `(select ${ownChildType})`}
          </option>
          {registered.map((c) => (
            <option key={c.local_id} value={String(c.local_id)}>
              {c.label ? `${c.label} (${c.local_id})` : `${ownChildType} ${c.local_id}`}
            </option>
          ))}
        </select>
        {children !== undefined && registered.length === 0 && (
          <div
            style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}
          >
            No registered {ownChildType} entries on this device yet — see the
            Child Entities tab.
          </div>
        )}
      </div>
    );
  } else {
    const isNumber =
      type === "integer" || type === "number" || type === "float";
    const numberRange =
      def.min !== undefined && def.max !== undefined
        ? `${def.min}-${def.max}`
        : undefined;
    widget = (
      <input
        type={
          def.secret || type === "password"
            ? "password"
            : isNumber
              ? "number"
              : "text"
        }
        autoComplete="new-password"
        value={value}
        min={def.min}
        max={def.max}
        onChange={(e) => onChange(e.target.value)}
        placeholder={numberRange ?? placeholder ?? ""}
        style={{ flex: 1 }}
      />
    );
  }

  return (
    <div style={rowStyle}>
      {widget}
      {toggle}
    </div>
  );
}

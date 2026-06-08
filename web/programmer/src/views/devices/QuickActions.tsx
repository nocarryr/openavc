import { useMemo, useState, useCallback } from "react";
import { Loader2, Check, AlertTriangle, X } from "lucide-react";
import { ElementIcon } from "../../components/ui-builder/ElementIcon";
import { Dialog } from "../../components/shared/Dialog";
import { ConfirmDialog } from "../../components/shared/ConfirmDialog";
import * as api from "../../api/restClient";
import type { ActionParam, DeviceAction } from "../../api/types";
import { isActionVisible } from "./actionVisibility";

/**
 * Quick Actions strip — driver-declared actions promoted to one-click buttons
 * at the top of the device view. No-param actions fire on click (with an
 * optional confirm); actions with params open an input dialog. The full
 * "Send Command" list below stays complete — this strip is purely additive.
 */
export function QuickActions({
  deviceId,
  actions,
  connected,
  liveState,
  onInvoked,
}: {
  deviceId: string;
  actions: DeviceAction[];
  connected: boolean;
  liveState: Record<string, unknown>;
  onInvoked?: () => void;
}) {
  const [dialogAction, setDialogAction] = useState<DeviceAction | null>(null);
  const [confirmAction, setConfirmAction] = useState<DeviceAction | null>(null);
  const [running, setRunning] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<
    { id: string; ok: boolean; message: string } | null
  >(null);

  const visible = useMemo(
    () => actions.filter((a) => isActionVisible(a, connected, liveState, deviceId)),
    [actions, connected, liveState, deviceId],
  );

  const invoke = useCallback(
    async (action: DeviceAction, params: Record<string, unknown>) => {
      setRunning(action.id);
      setFeedback(null);
      try {
        await api.invokeDeviceAction(deviceId, action.id, params);
        setFeedback({ id: action.id, ok: true, message: `${action.label} done` });
        onInvoked?.();
      } catch (e) {
        setFeedback({ id: action.id, ok: false, message: String(e) });
      } finally {
        setRunning(null);
        setDialogAction(null);
        setConfirmAction(null);
      }
    },
    [deviceId, onInvoked],
  );

  const handleClick = useCallback(
    (action: DeviceAction) => {
      if (Object.keys(action.params).length > 0) {
        setDialogAction(action);
      } else if (action.confirm) {
        setConfirmAction(action);
      } else {
        invoke(action, {});
      }
    },
    [invoke],
  );

  if (visible.length === 0) return null;

  return (
    <div style={{ marginBottom: "var(--space-lg)" }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-sm)" }}>
        {visible.map((action) => {
          const isRunning = running === action.id;
          return (
            <button
              key={action.id}
              onClick={() => handleClick(action)}
              disabled={isRunning}
              data-testid={`quick-action-${action.id}`}
              title={action.label}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-xs)",
                padding: "var(--space-sm) var(--space-lg)",
                borderRadius: "var(--border-radius)",
                background: "var(--accent-bg)",
                color: "var(--text-on-accent)",
                fontSize: "var(--font-size-sm)",
                fontWeight: 500,
                border: "none",
                cursor: isRunning ? "default" : "pointer",
                opacity: isRunning ? 0.6 : 1,
              }}
            >
              {isRunning ? (
                <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} />
              ) : action.icon ? (
                <ElementIcon name={action.icon} size={14} />
              ) : null}
              {action.label}
            </button>
          );
        })}
      </div>

      {feedback && (
        <div
          style={{
            marginTop: "var(--space-sm)",
            display: "flex",
            alignItems: "center",
            gap: "var(--space-xs)",
            fontSize: "var(--font-size-sm)",
            color: feedback.ok ? "var(--color-success)" : "var(--color-error)",
          }}
        >
          {feedback.ok ? <Check size={14} /> : <AlertTriangle size={14} />}
          <span>{feedback.message}</span>
          <button
            onClick={() => setFeedback(null)}
            title="Dismiss"
            style={{
              background: "transparent",
              border: "none",
              color: "var(--text-muted)",
              cursor: "pointer",
              padding: 0,
              display: "flex",
            }}
          >
            <X size={12} />
          </button>
        </div>
      )}

      {confirmAction && (
        <ConfirmDialog
          title={confirmAction.label}
          message={
            typeof confirmAction.confirm === "string"
              ? confirmAction.confirm
              : `Run "${confirmAction.label}"?`
          }
          confirmLabel={running ? "Running..." : "Run"}
          destructive
          onConfirm={() => invoke(confirmAction, {})}
          onCancel={() => setConfirmAction(null)}
        />
      )}

      {dialogAction && (
        <ActionParamDialog
          action={dialogAction}
          running={running === dialogAction.id}
          onCancel={() => setDialogAction(null)}
          onRun={(params) => invoke(dialogAction, params)}
        />
      )}
    </div>
  );
}

// --- Param input dialog ---

function defaultFor(def: ActionParam): string {
  if (def.default !== undefined && def.default !== null) return String(def.default);
  if (def.type === "enum" && def.values && def.values.length > 0 && def.required) {
    return def.values[0];
  }
  if (def.type === "boolean") return "false";
  return "";
}

/** Coerce a string field value to the param's declared type. */
function coerce(value: string, type?: string): unknown {
  if (type === "integer") {
    const n = parseInt(value, 10);
    return Number.isNaN(n) ? value : n;
  }
  if (type === "number" || type === "float") {
    const n = parseFloat(value);
    return Number.isNaN(n) ? value : n;
  }
  if (type === "boolean") return value === "true";
  return value;
}

function ActionParamDialog({
  action,
  running,
  onCancel,
  onRun,
}: {
  action: DeviceAction;
  running: boolean;
  onCancel: () => void;
  onRun: (params: Record<string, unknown>) => void;
}) {
  const paramKeys = Object.keys(action.params);
  const [values, setValues] = useState<Record<string, string>>(() => {
    const seed: Record<string, string> = {};
    for (const [name, def] of Object.entries(action.params)) {
      seed[name] = defaultFor(def);
    }
    return seed;
  });

  const setParam = (name: string, val: string) =>
    setValues((v) => ({ ...v, [name]: val }));

  const missingRequired = paramKeys.some(
    (k) => action.params[k].required && values[k].trim() === "",
  );

  const submit = () => {
    const params: Record<string, unknown> = {};
    for (const [name, def] of Object.entries(action.params)) {
      const raw = values[name];
      if (raw === "" && !def.required) continue;
      params[name] = coerce(raw, def.type);
    }
    onRun(params);
  };

  const confirmNote =
    typeof action.confirm === "string" ? action.confirm : null;

  return (
    <Dialog title={action.label} onClose={onCancel}>
      {confirmNote && (
        <div
          style={{
            marginBottom: "var(--space-md)",
            fontSize: "var(--font-size-sm)",
            color: "var(--text-secondary)",
          }}
        >
          {confirmNote}
        </div>
      )}
      <div style={{ marginBottom: "var(--space-lg)" }}>
        {paramKeys.map((name) => {
          const def = action.params[name];
          const label = def.label || name;
          const type = def.type || "string";
          const current = values[name] ?? "";
          return (
            <div key={name} style={{ marginBottom: "var(--space-md)" }}>
              <label
                style={{
                  display: "block",
                  fontSize: "var(--font-size-sm)",
                  color: "var(--text-secondary)",
                  marginBottom: 4,
                }}
              >
                {label}
                {def.required && <span style={{ color: "var(--color-error)" }}> *</span>}
              </label>
              {type === "enum" && def.values ? (
                <select
                  value={current}
                  onChange={(e) => setParam(name, e.target.value)}
                  style={{ width: "100%" }}
                >
                  {!def.required && <option value="">(none)</option>}
                  {def.values.map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </select>
              ) : type === "boolean" ? (
                <select
                  value={current || "false"}
                  onChange={(e) => setParam(name, e.target.value)}
                  style={{ width: "100%" }}
                >
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              ) : (
                <input
                  type={
                    def.secret || type === "password"
                      ? "password"
                      : type === "integer" || type === "number"
                        ? "number"
                        : "text"
                  }
                  value={current}
                  min={def.min}
                  max={def.max}
                  onChange={(e) => setParam(name, e.target.value)}
                  placeholder={
                    def.min !== undefined && def.max !== undefined
                      ? `${def.min}-${def.max}`
                      : name
                  }
                  style={{ width: "100%" }}
                />
              )}
              {def.help && (
                <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                  {def.help}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-sm)" }}>
        <button
          onClick={onCancel}
          style={{
            padding: "var(--space-sm) var(--space-lg)",
            borderRadius: "var(--border-radius)",
            background: "var(--bg-hover)",
          }}
        >
          Cancel
        </button>
        <button
          onClick={submit}
          disabled={running || missingRequired}
          style={{
            padding: "var(--space-sm) var(--space-lg)",
            borderRadius: "var(--border-radius)",
            background: missingRequired ? "var(--bg-hover)" : "var(--accent-bg)",
            color: missingRequired ? "var(--text-muted)" : "var(--text-on-accent)",
            display: "flex",
            alignItems: "center",
            gap: "var(--space-xs)",
            opacity: running ? 0.6 : 1,
          }}
        >
          {running && <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} />}
          Run
        </button>
      </div>
    </Dialog>
  );
}

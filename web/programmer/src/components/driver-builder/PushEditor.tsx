import type { DriverDefinition, DriverPushDef } from "../../api/types";

interface PushEditorProps {
  draft: DriverDefinition;
  onUpdate: (partial: Partial<DriverDefinition>) => void;
}

/**
 * Edits the `push` block — device-initiated notifications delivered on a
 * separate channel the platform opens (today only `type: multicast`).
 * Frames arriving on the channel feed the same `responses` rules as the
 * control connection, so state updates land instantly instead of waiting
 * for the next poll.
 */
export function PushEditor({ draft, onUpdate }: PushEditorProps) {
  const push = draft.push;
  const enabled = !!push;

  const labelStyle: React.CSSProperties = {
    display: "block",
    fontSize: "var(--font-size-sm)",
    color: "var(--text-secondary)",
    marginBottom: "var(--space-xs)",
  };
  const helpStyle: React.CSSProperties = {
    fontSize: "11px",
    color: "var(--text-muted)",
    marginTop: "var(--space-xs)",
  };

  const setEnabled = (next: boolean) => {
    if (next) {
      onUpdate({ push: { type: "multicast", group: "", port: 17000 } });
    } else {
      onUpdate({ push: undefined });
    }
  };

  const update = (partial: Partial<DriverPushDef>) => {
    onUpdate({ push: { ...(push ?? {}), ...partial } });
  };

  return (
    <div>
      <p
        style={{
          fontSize: "var(--font-size-sm)",
          color: "var(--text-muted)",
          marginTop: 0,
          marginBottom: "var(--space-md)",
        }}
      >
        For devices that announce state changes on a separate multicast
        channel instead of the control connection. The platform joins the
        group, and every frame that arrives feeds the driver&apos;s response
        rules — so state updates land instantly, without waiting for the next
        poll. The group and port can reference config fields, which lets one
        driver match devices whose notification target is configurable.
      </p>

      <label
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-sm)",
          fontSize: "var(--font-size-sm)",
          marginBottom: "var(--space-md)",
        }}
      >
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
        />
        Enable push notifications
      </label>

      {enabled && (
        <div
          style={{
            display: "grid",
            gap: "var(--space-md)",
            padding: "var(--space-md)",
            border: "1px solid var(--border-color)",
            borderRadius: "var(--border-radius)",
            background: "var(--bg-surface)",
          }}
        >
          <div>
            <label style={labelStyle}>Type</label>
            <select
              value={push?.type ?? "multicast"}
              onChange={(e) => update({ type: e.target.value })}
              style={{ width: "100%" }}
            >
              <option value="multicast">Multicast</option>
            </select>
            <div style={helpStyle}>
              Multicast is the only supported channel type today — the device
              sends state-change frames to a group address OpenAVC joins.
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-md)" }}>
            <div>
              <label style={labelStyle}>Multicast Group</label>
              <input
                value={push?.group ?? ""}
                onChange={(e) => update({ group: e.target.value })}
                placeholder="239.0.0.100 or {config_field}"
                style={{ width: "100%", fontFamily: "var(--font-mono)" }}
              />
              <div style={helpStyle}>
                An IPv4 multicast address (224.0.0.0 – 239.255.255.255), or a{" "}
                <code>{"{config_field}"}</code> template resolved from device
                config.
              </div>
            </div>
            <div>
              <label style={labelStyle}>Port</label>
              <input
                value={push?.port === undefined ? "" : String(push.port)}
                onChange={(e) => {
                  const raw = e.target.value;
                  update({
                    port: /^\d+$/.test(raw.trim())
                      ? parseInt(raw.trim(), 10)
                      : raw,
                  });
                }}
                placeholder="17000 or {config_field}"
                style={{ width: "100%", fontFamily: "var(--font-mono)" }}
              />
              <div style={helpStyle}>
                UDP port the device sends to (1–65535), or a{" "}
                <code>{"{config_field}"}</code> template.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

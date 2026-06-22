import { useState, useEffect, useRef, useMemo } from "react";
import { useProjectStore } from "../../store/projectStore";
import * as api from "../../api/restClient";
import type { DeviceConfig, DriverInfo } from "../../api/types";
import { DeviceSettingsSetupDialog, hasDriverSetupSettings } from "../../components/shared/DeviceSettingsSetupDialog";
import {
  coerceConfigValue,
  configFieldKind,
  isSecretConfigField,
  splitConnectionFields,
  SERIAL_PICKER_FIELDS,
} from "./deviceConfigCoerce";

// --- Typed Config Fields ---

function ConfigFieldInputs({
  configKeys,
  driverInfo,
  configValues,
  setConfigValues,
}: {
  configKeys: string[];
  driverInfo: DriverInfo | undefined;
  configValues: Record<string, string>;
  setConfigValues: React.Dispatch<React.SetStateAction<Record<string, string>>>;
}) {
  return (
    <>
      {configKeys.map((key) => {
        const schema =
          (driverInfo?.config_schema as Record<string, Record<string, unknown>>)?.[key] ?? {};
        const label = String(schema.label || key);
        const description = schema.description ? String(schema.description) : "";
        const fieldType = String(schema.type || "string");
        const values = schema.values as string[] | undefined;
        const isRequired = schema.required === true;
        const defaultVal = schema.default;
        const isObjectField = fieldType === "object" || fieldType === "json";
        // Widget choice lives in configFieldKind so secret fields reliably
        // mask and the dialogs can't drift from the coercion rules.
        const kind = configFieldKind(schema);
        // Build helpful placeholder from key name conventions
        const placeholder = isObjectField
          ? (defaultVal && typeof defaultVal === "object" && Object.keys(defaultVal).length > 0
              ? JSON.stringify(defaultVal)
              : '{"key": "value"}')
          : key === "host" ? "192.168.1.100"
          : key === "port" ? "1-65535"
          : key === "username" ? "admin"
          : key === "password" ? "password"
          : key === "community" ? "public"
          : key === "baud_rate" || key === "baudrate" ? "9600"
          : defaultVal != null && defaultVal !== "" ? String(defaultVal)
          : label;

        return (
          <div key={key} style={{ marginBottom: "var(--space-sm)" }}>
            <label
              style={{
                display: "block",
                fontSize: "var(--font-size-sm)",
                color: "var(--text-secondary)",
                marginBottom: "var(--space-xs)",
              }}
            >
              {label}
              {isRequired && (
                <span style={{ color: "var(--error, #f44336)", marginLeft: 2 }}>*</span>
              )}
            </label>
            {kind === "boolean" ? (
              <button
                onClick={() =>
                  setConfigValues((v) => ({
                    ...v,
                    [key]: v[key] === "true" ? "false" : "true",
                  }))
                }
                style={{
                  padding: "var(--space-xs) var(--space-md)",
                  borderRadius: "var(--border-radius)",
                  background:
                    configValues[key] === "true"
                      ? "var(--color-success-bg)"
                      : "var(--bg-hover)",
                  color:
                    configValues[key] === "true" ? "var(--color-success)" : "var(--text-secondary)",
                  fontSize: "var(--font-size-sm)",
                }}
              >
                {configValues[key] === "true" ? "Yes" : "No"}
              </button>
            ) : kind === "password" ? (
              <input
                type="password"
                autoComplete="new-password"
                value={configValues[key] ?? ""}
                onChange={(e) =>
                  setConfigValues((v) => ({ ...v, [key]: e.target.value }))
                }
                placeholder={placeholder}
                style={{ width: "100%" }}
              />
            ) : kind === "select" ? (
              <select
                value={configValues[key] ?? ""}
                onChange={(e) =>
                  setConfigValues((v) => ({ ...v, [key]: e.target.value }))
                }
                style={{ width: "100%" }}
              >
                <option value="">Select...</option>
                {values?.map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            ) : kind === "number" ? (
              <input
                type="number"
                value={configValues[key] ?? ""}
                onChange={(e) =>
                  setConfigValues((v) => ({ ...v, [key]: e.target.value }))
                }
                placeholder={placeholder}
                style={{ width: "100%" }}
              />
            ) : kind === "textarea" ? (
              <textarea
                value={configValues[key] ?? ""}
                onChange={(e) =>
                  setConfigValues((v) => ({ ...v, [key]: e.target.value }))
                }
                placeholder={placeholder}
                rows={6}
                spellCheck={false}
                style={{
                  width: "100%",
                  fontFamily: "var(--font-mono, monospace)",
                  fontSize: "var(--font-size-sm)",
                  resize: "vertical",
                  minHeight: "120px",
                }}
              />
            ) : (
              <input
                value={configValues[key] ?? ""}
                onChange={(e) =>
                  setConfigValues((v) => ({ ...v, [key]: e.target.value }))
                }
                placeholder={placeholder}
                style={{ width: "100%" }}
              />
            )}
            {description && (
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                {description}
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}

// --- Connection Mode Picker (serial-capable drivers) ---
//
// For drivers that can speak serial (transport "serial" or `transports`
// includes "serial"), the connection can be made three ways: over the network
// (IP), directly to a serial port on this server, or *through a bridge* device
// (e.g. an iTach) that vends a serial pass-through. A segmented control picks
// the mode and reveals the matching fields. The Add/Edit dialogs exclude these
// connection fields (SERIAL_PICKER_FIELDS) from the generic schema section so
// they aren't rendered twice. Non-serial drivers don't render this at all —
// their connection UI is unchanged.

const NETWORK_TRANSPORTS = ["tcp", "udp", "http", "osc"];
const BAUD_RATES = ["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"];
const PARITY_OPTS: [string, string][] = [["N", "None"], ["E", "Even"], ["O", "Odd"]];
const DATABITS_OPTS = ["5", "6", "7", "8"];
const STOPBITS_OPTS = ["1", "1.5", "2"];
const FLOW_OPTS: [string, string][] = [["none", "None"], ["hardware", "Hardware (RTS/CTS)"]];

export function driverSerialCapable(d: DriverInfo | undefined): boolean {
  if (!d) return false;
  const t = (d.transport || "").toLowerCase();
  const ts = (d.transports || []).map((x) => String(x).toLowerCase());
  return t === "serial" || ts.includes("serial");
}

function driverNetworkCapable(d: DriverInfo | undefined): boolean {
  if (!d) return false;
  const t = (d.transport || "").toLowerCase();
  const ts = (d.transports || []).map((x) => String(x).toLowerCase());
  return NETWORK_TRANSPORTS.includes(t) || ts.some((x) => NETWORK_TRANSPORTS.includes(x));
}

function primaryNetworkTransport(d: DriverInfo | undefined): string {
  const t = (d?.transport || "").toLowerCase();
  if (NETWORK_TRANSPORTS.includes(t)) return t;
  const ts = (d?.transports || []).map((x) => String(x).toLowerCase());
  return ts.find((x) => NETWORK_TRANSPORTS.includes(x)) || "tcp";
}

type ConnMode = "network" | "serial" | "bridge";

function inferConnMode(cv: Record<string, string>, d: DriverInfo | undefined): ConnMode {
  if (cv.bridge && cv.bridge_port) return "bridge";
  if ((cv.transport || "").toLowerCase() === "serial") return "serial";
  if ((cv.host ?? "") !== "") return "network";
  return driverNetworkCapable(d) ? "network" : "serial";
}

// Rebuild the connection-owned keys when the user switches mode so no stale
// field from the previous mode is saved (a TCP port left as a COM path, a host
// left under a bridge binding, ...). Serial line params carry across
// serial<->bridge.
function applyConnMode(
  cv: Record<string, string>,
  next: ConnMode,
  d: DriverInfo | undefined,
): Record<string, string> {
  const v = { ...cv };
  if (next === "network") {
    delete v.bridge;
    delete v.bridge_port;
    delete v.baudrate;
    delete v.bytesize;
    delete v.parity;
    delete v.stopbits;
    delete v.flow_control;
    v.transport = primaryNetworkTransport(d);
    if (v.host == null) v.host = "";
    // A COM path left in `port` is meaningless as a TCP port → reset to the
    // driver's default network port.
    if (v.port && /[A-Za-z]/.test(v.port)) {
      const dp = d?.default_config?.port;
      v.port = dp != null ? String(dp) : "";
    }
  } else if (next === "serial") {
    delete v.host;
    delete v.bridge;
    delete v.bridge_port;
    v.transport = "serial";
    // A numeric TCP port is meaningless as a COM path → clear it.
    if (v.port && /^\d+$/.test(v.port)) v.port = "";
    if (v.baudrate == null) v.baudrate = "9600";
  } else {
    // bridge: the resolver computes transport=tcp + host + pass-through port,
    // so we store only the binding + serial line params.
    delete v.host;
    delete v.transport;
    delete v.port;
    if (v.baudrate == null) v.baudrate = "9600";
  }
  return v;
}

const pickerLabelStyle: React.CSSProperties = {
  display: "block",
  fontSize: "var(--font-size-sm)",
  color: "var(--text-secondary)",
  marginBottom: "var(--space-xs)",
};

function ConnectionModePicker({
  driverInfo,
  configValues,
  setConfigValues,
  devices,
  drivers,
  selfId,
}: {
  driverInfo: DriverInfo | undefined;
  configValues: Record<string, string>;
  setConfigValues: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  devices: DeviceConfig[];
  drivers: DriverInfo[];
  selfId?: string;
}) {
  const [mode, setMode] = useState<ConnMode>(() => inferConnMode(configValues, driverInfo));

  // Re-infer when the driver changes (the parent resets configValues then).
  // Depend only on the id so per-keystroke edits don't reset the mode.
  useEffect(() => {
    setMode(inferConnMode(configValues, driverInfo));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [driverInfo?.id]);

  if (!driverSerialCapable(driverInfo)) return null;

  const set = (key: string, value: string) =>
    setConfigValues((v) => ({ ...v, [key]: value }));

  const switchMode = (next: ConnMode) => {
    if (next === mode) return;
    setMode(next);
    setConfigValues((v) => applyConnMode(v, next, driverInfo));
  };

  const netCapable = driverNetworkCapable(driverInfo);
  const modes: { id: ConnMode; label: string }[] = [];
  if (netCapable) modes.push({ id: "network", label: "Network (IP)" });
  modes.push({ id: "serial", label: "Direct serial" });
  modes.push({ id: "bridge", label: "Through a bridge" });

  const modeHelp: Record<ConnMode, string> = {
    network: "Reach the device over the network by IP address.",
    serial: "A serial (RS-232) port on this server.",
    bridge: "Route this device's serial line through a bridge device (e.g. an iTach).",
  };

  // Bridge devices = project devices whose driver advertises bridge ports
  // (excluding this device itself).
  const bridges = devices.filter((dev) => {
    if (selfId && dev.id === selfId) return false;
    const di = drivers.find((x) => x.id === dev.driver);
    return (di?.bridge?.ports?.length ?? 0) > 0;
  });
  const selectedBridge = bridges.find((b) => b.id === configValues.bridge);
  const selectedBridgeDriver = selectedBridge
    ? drivers.find((x) => x.id === selectedBridge.driver)
    : undefined;
  // Phase 1: only serial pass-through ports are bindable.
  const bridgePorts = (selectedBridgeDriver?.bridge?.ports ?? []).filter(
    (p) => p.kind === "serial",
  );

  const onBridgeChange = (bridgeId: string) => {
    setConfigValues((v) => {
      const bdrv = drivers.find(
        (x) => x.id === devices.find((d) => d.id === bridgeId)?.driver,
      );
      const ports = (bdrv?.bridge?.ports ?? []).filter((p) => p.kind === "serial");
      // Auto-select when the bridge has exactly one serial port (the IP2SL case).
      return {
        ...v,
        bridge: bridgeId,
        bridge_port: ports.length === 1 ? ports[0].id : "",
      };
    });
  };

  const field = (label: string, node: React.ReactNode) => (
    <div style={{ marginBottom: "var(--space-sm)" }}>
      <label style={pickerLabelStyle}>{label}</label>
      {node}
    </div>
  );

  const serialParams = (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-sm)" }}>
        {field(
          "Baud rate",
          <select value={configValues.baudrate ?? "9600"} onChange={(e) => set("baudrate", e.target.value)} style={{ width: "100%" }}>
            {BAUD_RATES.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>,
        )}
        {field(
          "Parity",
          <select value={configValues.parity ?? "N"} onChange={(e) => set("parity", e.target.value)} style={{ width: "100%" }}>
            {PARITY_OPTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>,
        )}
        {field(
          "Data bits",
          <select value={configValues.bytesize ?? "8"} onChange={(e) => set("bytesize", e.target.value)} style={{ width: "100%" }}>
            {DATABITS_OPTS.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>,
        )}
        {field(
          "Stop bits",
          <select value={configValues.stopbits ?? "1"} onChange={(e) => set("stopbits", e.target.value)} style={{ width: "100%" }}>
            {STOPBITS_OPTS.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>,
        )}
      </div>
      {field(
        "Flow control",
        <select value={configValues.flow_control ?? "none"} onChange={(e) => set("flow_control", e.target.value)} style={{ width: "100%" }}>
          {FLOW_OPTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>,
      )}
    </>
  );

  return (
    <div style={{ marginBottom: "var(--space-sm)" }}>
      {/* Segmented mode control */}
      <div style={{ display: "flex", gap: 2, marginBottom: "var(--space-xs)", background: "var(--bg-hover)", borderRadius: "var(--border-radius)", padding: 2 }}>
        {modes.map((m) => (
          <button
            key={m.id}
            onClick={() => switchMode(m.id)}
            style={{
              flex: 1,
              padding: "var(--space-xs) var(--space-sm)",
              borderRadius: "var(--border-radius)",
              background: mode === m.id ? "var(--accent-bg)" : "transparent",
              color: mode === m.id ? "var(--text-on-accent)" : "var(--text-secondary)",
              fontSize: "var(--font-size-sm)",
              border: "none",
              cursor: "pointer",
            }}
          >
            {m.label}
          </button>
        ))}
      </div>
      <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: "var(--space-sm)" }}>
        {modeHelp[mode]}
      </div>

      {mode === "network" && (
        <>
          {field("IP Address", <input value={configValues.host ?? ""} onChange={(e) => set("host", e.target.value)} placeholder="192.168.1.100" style={{ width: "100%" }} />)}
          {field("Port", <input type="number" value={configValues.port ?? ""} onChange={(e) => set("port", e.target.value)} placeholder={String(driverInfo?.default_config?.port ?? "1-65535")} style={{ width: "100%" }} />)}
        </>
      )}

      {mode === "serial" && (
        <>
          {field("Serial Port", <input value={configValues.port ?? ""} onChange={(e) => set("port", e.target.value)} placeholder="COM3 or /dev/ttyUSB0" style={{ width: "100%" }} />)}
          {serialParams}
        </>
      )}

      {mode === "bridge" && (
        bridges.length === 0 ? (
          <div style={{ fontSize: "var(--font-size-sm)", color: "var(--text-muted)", padding: "var(--space-sm)", background: "var(--bg-base)", borderRadius: "var(--border-radius)" }}>
            No bridge devices in this project yet. Add a bridge (such as a Global Cache iTach) first, then bind this device to one of its ports.
          </div>
        ) : (
          <>
            {field(
              "Bridge",
              <select value={configValues.bridge ?? ""} onChange={(e) => onBridgeChange(e.target.value)} style={{ width: "100%" }}>
                <option value="">Select a bridge...</option>
                {bridges.map((b) => <option key={b.id} value={b.id}>{b.name || b.id}</option>)}
              </select>,
            )}
            {configValues.bridge && field(
              "Bridge port",
              <select value={configValues.bridge_port ?? ""} onChange={(e) => set("bridge_port", e.target.value)} style={{ width: "100%" }}>
                <option value="">Select a port...</option>
                {bridgePorts.map((p) => <option key={p.id} value={p.id}>{p.label || p.id}</option>)}
              </select>,
            )}
            {configValues.bridge && serialParams}
          </>
        )
      )}
    </div>
  );
}

// --- Searchable Driver Dropdown ---

const CATEGORY_ORDER = ["projector", "display", "audio", "switcher", "camera", "lighting", "control", "utility", "other"];

function DriverSearchSelect({
  drivers,
  value,
  onChange,
}: {
  drivers: DriverInfo[];
  value: string;
  onChange: (driverId: string) => void;
}) {
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return drivers.filter(
      (d) =>
        !q ||
        (d.name || d.id).toLowerCase().includes(q) ||
        (d.manufacturer || "").toLowerCase().includes(q) ||
        (d.category || "").toLowerCase().includes(q)
    );
  }, [drivers, search]);

  const grouped = useMemo(() => {
    const map = new Map<string, DriverInfo[]>();
    for (const d of filtered) {
      const cat = d.category || "other";
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat)!.push(d);
    }
    const sorted = [...map.entries()].sort(
      (a, b) => (CATEGORY_ORDER.indexOf(a[0]) === -1 ? 99 : CATEGORY_ORDER.indexOf(a[0]))
        - (CATEGORY_ORDER.indexOf(b[0]) === -1 ? 99 : CATEGORY_ORDER.indexOf(b[0]))
    );
    return sorted;
  }, [filtered]);

  const selected = drivers.find((d) => d.id === value);

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <input
        value={open ? search : (selected ? (selected.name || selected.id) : "")}
        onChange={(e) => { setSearch(e.target.value); if (!open) setOpen(true); }}
        onFocus={() => { setOpen(true); setSearch(""); }}
        placeholder="Search drivers..."
        style={{ width: "100%" }}
      />
      {open && (
        <div
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            maxHeight: 260,
            overflow: "auto",
            background: "var(--bg-elevated)",
            border: "1px solid var(--border-color)",
            borderRadius: "var(--border-radius)",
            zIndex: 10,
            boxShadow: "var(--shadow-md)",
          }}
        >
          {grouped.length === 0 && (
            <div style={{ padding: "var(--space-sm) var(--space-md)", color: "var(--text-muted)", fontSize: "var(--font-size-sm)" }}>
              No drivers found
            </div>
          )}
          {grouped.map(([cat, items]) => (
            <div key={cat}>
              <div
                style={{
                  padding: "var(--space-xs) var(--space-md)",
                  fontSize: 11,
                  color: "var(--text-muted)",
                  textTransform: "uppercase",
                  letterSpacing: "0.5px",
                  background: "var(--bg-surface)",
                  position: "sticky",
                  top: 0,
                }}
              >
                {cat}
              </div>
              {items.map((d) => (
                <div
                  key={d.id}
                  onClick={() => { onChange(d.id); setOpen(false); setSearch(""); }}
                  style={{
                    padding: "var(--space-xs) var(--space-md)",
                    cursor: "pointer",
                    fontSize: "var(--font-size-sm)",
                    background: d.id === value ? "var(--accent-dim)" : "transparent",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = d.id === value ? "var(--accent-dim)" : "var(--bg-hover)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = d.id === value ? "var(--accent-dim)" : "transparent")}
                >
                  <span>{d.name || d.id}</span>
                  {d.manufacturer && (
                    <span style={{ color: "var(--text-muted)", fontSize: 11 }}>{d.manufacturer}</span>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// --- Add Device Dialog ---

function generateDeviceDefaults(
  driver: DriverInfo,
  existingDevices: DeviceConfig[],
): { id: string; name: string } {
  const existingIds = new Set(existingDevices.map((d) => d.id));
  const existingNames = new Set(existingDevices.map((d) => d.name));

  // ID: category-based like "projector_1", "display_2"
  const base = driver.category || "device";
  let idNum = 1;
  while (existingIds.has(`${base}_${idNum}`)) idNum++;
  const id = `${base}_${idNum}`;

  // Name: driver name like "PJLink Class 1", append " 2" if taken
  let name = driver.name;
  if (existingNames.has(name)) {
    let nameNum = 2;
    while (existingNames.has(`${driver.name} ${nameNum}`)) nameNum++;
    name = `${driver.name} ${nameNum}`;
  }

  return { id, name };
}

export function AddDeviceDialog({
  onClose,
  prefill,
}: {
  onClose: () => void;
  prefill?: DeviceConfig;
}) {
  const project = useProjectStore((s) => s.project);
  const update = useProjectStore((s) => s.update);
  const save = useProjectStore((s) => s.save);

  const [drivers, setDrivers] = useState<DriverInfo[]>([]);
  const [deviceId, setDeviceId] = useState(prefill ? "" : "");
  const [deviceName, setDeviceName] = useState(prefill?.name ? `${prefill.name} (Copy)` : "");
  const [selectedDriver, setSelectedDriver] = useState(prefill?.driver ?? "");
  const [idTouchedByUser, setIdTouchedByUser] = useState(!!prefill);
  const [nameTouchedByUser, setNameTouchedByUser] = useState(!!prefill?.name);
  const [configValues, setConfigValues] = useState<Record<string, string>>(() => {
    if (!prefill) return {};
    // Merge device.config with connection table overrides (host, port, etc.)
    const conn = useProjectStore.getState().project?.connections?.[prefill.id] ?? {};
    const merged = { ...prefill.config, ...conn };
    const vals: Record<string, string> = {};
    for (const [k, v] of Object.entries(merged)) {
      if (v != null && typeof v === "object") {
        // Pretty-print so object fields (e.g. a command map) are editable as
        // readable JSON in the multi-line textarea.
        vals[k] = JSON.stringify(v, null, 2);
      } else {
        vals[k] = String(v ?? "");
      }
    }
    return vals;
  });
  const [error, setError] = useState("");
  const [isAdding, setIsAdding] = useState(false);
  const [setupDeviceId, setSetupDeviceId] = useState<string | null>(null);

  useEffect(() => {
    api.listDrivers().then(setDrivers).catch(console.error);
  }, []);

  const driverInfo = drivers.find((d) => d.id === selectedDriver);
  const configKeys = Object.keys((driverInfo?.config_schema ?? {}) as Record<string, unknown>);
  const serialCapable = driverSerialCapable(driverInfo);
  // The connection picker owns these fields for serial-capable drivers; keep
  // them out of the generic schema section so they aren't rendered twice.
  const visibleConfigKeys = serialCapable
    ? configKeys.filter((k) => !SERIAL_PICKER_FIELDS.has(k))
    : configKeys;

  // Check if driver has setup settings
  const hasSetupSettings = useMemo(() => hasDriverSetupSettings(driverInfo), [driverInfo]);

  const handleAdd = async () => {
    if (!deviceId || !selectedDriver) {
      setError("Device ID and driver are required");
      return;
    }
    if (project?.devices.some((d) => d.id === deviceId)) {
      setError("A device with this ID already exists");
      return;
    }

    const config: Record<string, unknown> = {};
    const schema = (driverInfo?.config_schema ?? {}) as Record<string, Record<string, unknown>>;
    for (const [key, val] of Object.entries(configValues)) {
      if (val === "") continue;
      const fieldType = String(schema[key]?.type || "");
      const result = coerceConfigValue(val, fieldType, schema[key]?.secret === true);
      if (!result.ok) {
        setError(`${String(schema[key]?.label || key)}: ${result.error}`);
        return;
      }
      config[key] = result.value;
    }

    // Same split the device-update API applies: connection fields go to the
    // connections table (v0.5.0 schema), the rest stays in device.config.
    const { config: protocolConfig, connection } = splitConnectionFields(config);

    const newDevice: DeviceConfig = {
      id: deviceId,
      driver: selectedDriver,
      name: deviceName || deviceId,
      config: protocolConfig,
    };

    // Read devices + connections from the same store snapshot so the two
    // halves of the patch can't disagree.
    const current = useProjectStore.getState().project;
    update({
      devices: [...(current?.devices ?? []), newDevice],
      ...(Object.keys(connection).length > 0
        ? {
            connections: {
              ...(current?.connections ?? {}),
              [deviceId]: connection,
            },
          }
        : {}),
    });

    save();

    // Show setup dialog if driver has setup settings
    if (hasSetupSettings) {
      setIsAdding(true);
      setSetupDeviceId(deviceId);
    } else {
      onClose();
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Add Device"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.6)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "var(--bg-elevated)",
          borderRadius: "var(--border-radius)",
          padding: "var(--space-xl)",
          width: 480,
          maxHeight: "80vh",
          overflow: "auto",
          boxShadow: "var(--shadow-lg)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 style={{ fontSize: "var(--font-size-lg)", marginBottom: "var(--space-lg)" }}>
          {prefill ? "Duplicate Device" : "Add Device"}
        </h3>

        {error && (
          <div
            style={{
              background: "var(--color-error-bg)",
              color: "var(--color-error)",
              padding: "var(--space-sm) var(--space-md)",
              borderRadius: "var(--border-radius)",
              marginBottom: "var(--space-md)",
              fontSize: "var(--font-size-sm)",
            }}
          >
            {error}
          </div>
        )}

        <div style={{ marginBottom: "var(--space-md)" }}>
          <label
            style={{
              display: "block",
              fontSize: "var(--font-size-sm)",
              color: "var(--text-secondary)",
              marginBottom: "var(--space-xs)",
            }}
          >
            Driver <span style={{ color: "var(--color-error, #ef4444)" }}>*</span>
          </label>
          <DriverSearchSelect
            drivers={drivers}
            value={selectedDriver}
            onChange={(newDriverId) => {
              setSelectedDriver(newDriverId);
              const newDriver = drivers.find((d) => d.id === newDriverId);
              const defaults = newDriver?.default_config ?? {};
              const prefilled: Record<string, string> = {};
              for (const [k, v] of Object.entries(defaults)) {
                // Never pre-fill a password/secret field — a masked default is
                // an easy way to save a password by accident.
                if (isSecretConfigField(newDriver?.config_schema, k)) continue;
                if (v !== "" && v != null) prefilled[k] = String(v);
              }
              setConfigValues(prefilled);
              if (newDriver) {
                const generated = generateDeviceDefaults(newDriver, project?.devices ?? []);
                if (!idTouchedByUser) setDeviceId(generated.id);
                if (!nameTouchedByUser) setDeviceName(generated.name);
              }
            }}
          />
          {driverInfo?.help?.overview && (
            <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
              {driverInfo.help.overview}
            </div>
          )}
          {driverInfo?.help?.setup && (
            <div style={{
              fontSize: 11,
              color: "var(--text-secondary)",
              marginTop: 4,
              padding: "var(--space-sm)",
              background: "var(--bg-base)",
              borderRadius: "var(--border-radius)",
              whiteSpace: "pre-line",
            }}>
              {driverInfo.help.setup}
            </div>
          )}
        </div>

        <div style={{ marginBottom: "var(--space-md)" }}>
          <label
            style={{
              display: "block",
              fontSize: "var(--font-size-sm)",
              color: "var(--text-secondary)",
              marginBottom: "var(--space-xs)",
            }}
          >
            Device ID <span style={{ color: "var(--color-error, #ef4444)" }}>*</span>
          </label>
          <input
            value={deviceId}
            onChange={(e) => {
              setIdTouchedByUser(true);
              setDeviceId(e.target.value.replace(/[^a-z0-9_]/gi, "").toLowerCase());
            }}
            placeholder="e.g., projector_room_1"
            style={{
              width: "100%",
              borderColor: deviceId && !isAdding && project?.devices.some((d) => d.id === deviceId)
                ? "var(--color-error, #ef4444)" : undefined,
            }}
          />
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 3 }}>
            Lowercase letters, numbers, and underscores only.
            {deviceId && (
              <span style={{ marginLeft: 6 }}>
                Your ID: <code style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>{deviceId}</code>
                {!isAdding && project?.devices.some((d) => d.id === deviceId) && (
                  <span style={{ color: "var(--color-error, #ef4444)", marginLeft: 6 }}>Already exists</span>
                )}
              </span>
            )}
          </div>
        </div>

        <div style={{ marginBottom: "var(--space-md)" }}>
          <label
            style={{
              display: "block",
              fontSize: "var(--font-size-sm)",
              color: "var(--text-secondary)",
              marginBottom: "var(--space-xs)",
            }}
          >
            Display Name
          </label>
          <input
            value={deviceName}
            onChange={(e) => {
              setNameTouchedByUser(true);
              setDeviceName(e.target.value);
            }}
            placeholder="e.g., Main Projector"
            maxLength={128}
            style={{ width: "100%" }}
          />
        </div>


        {(serialCapable || visibleConfigKeys.length > 0) && (
          <div style={{ marginBottom: "var(--space-md)" }}>
            <div
              style={{
                fontSize: "var(--font-size-sm)",
                color: "var(--text-secondary)",
                marginBottom: "var(--space-sm)",
                textTransform: "uppercase",
                letterSpacing: "0.5px",
              }}
            >
              Connection Settings
            </div>
            {serialCapable && (
              <ConnectionModePicker
                driverInfo={driverInfo}
                configValues={configValues}
                setConfigValues={setConfigValues}
                devices={project?.devices ?? []}
                drivers={drivers}
                selfId={deviceId || undefined}
              />
            )}
            {visibleConfigKeys.length > 0 && (
              <ConfigFieldInputs
                configKeys={visibleConfigKeys}
                driverInfo={driverInfo}
                configValues={configValues}
                setConfigValues={setConfigValues}
              />
            )}
          </div>
        )}

        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: "var(--space-sm)",
            marginTop: "var(--space-lg)",
          }}
        >
          <button
            onClick={onClose}
            style={{
              padding: "var(--space-sm) var(--space-lg)",
              borderRadius: "var(--border-radius)",
              background: "var(--bg-hover)",
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleAdd}
            style={{
              padding: "var(--space-sm) var(--space-lg)",
              borderRadius: "var(--border-radius)",
              background: "var(--accent-bg)",
              color: "var(--text-on-accent)",
            }}
          >
            {prefill ? "Duplicate Device" : "Add Device"}
          </button>
        </div>
      </div>

      {setupDeviceId && driverInfo && (
        <DeviceSettingsSetupDialog
          deviceId={setupDeviceId}
          driverInfo={driverInfo}
          existingDeviceIds={(project?.devices ?? []).map((d) => d.id)}
          onClose={onClose}
        />
      )}
    </div>
  );
}

// --- Edit Device Dialog ---

export function EditDeviceDialog({
  device,
  onClose,
  onSaved,
}: {
  device: DeviceConfig;
  onClose: () => void;
  onSaved: () => void;
}) {
  const project = useProjectStore((s) => s.project);
  const [drivers, setDrivers] = useState<DriverInfo[]>([]);
  const [deviceName, setDeviceName] = useState(device.name);
  const [selectedDriver, setSelectedDriver] = useState(device.driver);
  const [configValues, setConfigValues] = useState<Record<string, string>>(() => {
    // Merge device.config with connection table overrides (host, port, etc.)
    const conn = useProjectStore.getState().project?.connections?.[device.id] ?? {};
    const merged = { ...device.config, ...conn };
    const vals: Record<string, string> = {};
    for (const [k, v] of Object.entries(merged)) {
      if (v != null && typeof v === "object") {
        // Pretty-print so object fields (e.g. a command map) are editable as
        // readable JSON in the multi-line textarea.
        vals[k] = JSON.stringify(v, null, 2);
      } else {
        vals[k] = String(v ?? "");
      }
    }
    return vals;
  });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.listDrivers().then(setDrivers).catch(console.error);
  }, []);

  const driverInfo = drivers.find((d) => d.id === selectedDriver);
  // Show config fields from driver schema if available, otherwise from the device's existing config
  const schemaKeys = Object.keys((driverInfo?.config_schema ?? {}) as Record<string, unknown>);
  const existingKeys = Object.keys(configValues);
  const configKeys = schemaKeys.length > 0 ? schemaKeys : existingKeys;
  const serialCapable = driverSerialCapable(driverInfo);
  // The connection picker owns these fields for serial-capable drivers; keep
  // them out of the generic schema section so they aren't rendered twice.
  const visibleConfigKeys = serialCapable
    ? configKeys.filter((k) => !SERIAL_PICKER_FIELDS.has(k))
    : configKeys;

  // When driver changes, pre-fill config from driver's default_config
  const handleDriverChange = (newDriver: string) => {
    setSelectedDriver(newDriver);
    if (newDriver !== device.driver) {
      const newDriverInfo = drivers.find((d) => d.id === newDriver);
      const defaults = newDriverInfo?.default_config ?? {};
      const prefilled: Record<string, string> = {};
      for (const [k, v] of Object.entries(defaults)) {
        if (isSecretConfigField(newDriverInfo?.config_schema, k)) continue;
        if (v !== "" && v != null) prefilled[k] = String(v);
      }
      setConfigValues(prefilled);
    }
  };

  const handleSave = async () => {
    if (!selectedDriver) {
      setError("Driver is required");
      return;
    }

    setSaving(true);
    setError("");
    try {
      const config: Record<string, unknown> = {};
      const schema = (driverInfo?.config_schema ?? {}) as Record<string, Record<string, unknown>>;
      for (const [key, val] of Object.entries(configValues)) {
        if (val === "") continue;
        const fieldType = String(schema[key]?.type || "");
        const result = coerceConfigValue(val, fieldType, schema[key]?.secret === true);
        if (!result.ok) {
          setError(`${String(schema[key]?.label || key)}: ${result.error}`);
          setSaving(false);
          return;
        }
        config[key] = result.value;
      }

      const updateData: Record<string, unknown> = {
        name: deviceName || device.id,
        driver: selectedDriver,
        config,
      };

      await api.updateDevice(device.id, updateData as {
        name?: string;
        driver?: string;
        config?: Record<string, unknown>;
      });
      onSaved();
      onClose();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Edit Device"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.6)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "var(--bg-elevated)",
          borderRadius: "var(--border-radius)",
          padding: "var(--space-xl)",
          width: 480,
          maxHeight: "80vh",
          overflow: "auto",
          boxShadow: "var(--shadow-lg)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 style={{ fontSize: "var(--font-size-lg)", marginBottom: "var(--space-lg)" }}>
          Edit Device
        </h3>

        {error && (
          <div
            style={{
              background: "var(--color-error-bg)",
              color: "var(--color-error)",
              padding: "var(--space-sm) var(--space-md)",
              borderRadius: "var(--border-radius)",
              marginBottom: "var(--space-md)",
              fontSize: "var(--font-size-sm)",
            }}
          >
            {error}
          </div>
        )}

        <div style={{ marginBottom: "var(--space-md)" }}>
          <label
            style={{
              display: "block",
              fontSize: "var(--font-size-sm)",
              color: "var(--text-secondary)",
              marginBottom: "var(--space-xs)",
            }}
          >
            Device ID
          </label>
          <input value={device.id} disabled style={{ width: "100%", opacity: 0.6 }} />
          <div
            style={{
              fontSize: "11px",
              color: "var(--text-muted)",
              marginTop: "var(--space-xs)",
            }}
          >
            Device ID cannot be changed after creation
          </div>
        </div>

        <div style={{ marginBottom: "var(--space-md)" }}>
          <label
            style={{
              display: "block",
              fontSize: "var(--font-size-sm)",
              color: "var(--text-secondary)",
              marginBottom: "var(--space-xs)",
            }}
          >
            Driver
          </label>
          <DriverSearchSelect
            drivers={
              // Include current driver if not in the loaded list
              selectedDriver && !drivers.some(d => d.id === selectedDriver)
                ? [...drivers, { id: selectedDriver, name: selectedDriver + (drivers.length === 0 ? " (loading...)" : " (not installed)"), manufacturer: "", category: "other", commands: {}, config_schema: {} }]
                : drivers
            }
            value={selectedDriver}
            onChange={handleDriverChange}
          />
        </div>

        <div style={{ marginBottom: "var(--space-md)" }}>
          <label
            style={{
              display: "block",
              fontSize: "var(--font-size-sm)",
              color: "var(--text-secondary)",
              marginBottom: "var(--space-xs)",
            }}
          >
            Display Name
          </label>
          <input
            value={deviceName}
            onChange={(e) => setDeviceName(e.target.value)}
            placeholder="e.g., Main Projector"
            maxLength={128}
            style={{ width: "100%" }}
          />
        </div>


        {(serialCapable || visibleConfigKeys.length > 0) && (
          <div style={{ marginBottom: "var(--space-md)" }}>
            <div
              style={{
                fontSize: "var(--font-size-sm)",
                color: "var(--text-secondary)",
                marginBottom: "var(--space-sm)",
                textTransform: "uppercase",
                letterSpacing: "0.5px",
              }}
            >
              Connection Settings
            </div>
            {serialCapable && (
              <ConnectionModePicker
                driverInfo={driverInfo}
                configValues={configValues}
                setConfigValues={setConfigValues}
                devices={project?.devices ?? []}
                drivers={drivers}
                selfId={device.id}
              />
            )}
            {visibleConfigKeys.length > 0 && (
              <ConfigFieldInputs
                configKeys={visibleConfigKeys}
                driverInfo={driverInfo}
                configValues={configValues}
                setConfigValues={setConfigValues}
              />
            )}
          </div>
        )}

        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: "var(--space-sm)",
            marginTop: "var(--space-lg)",
          }}
        >
          <button
            onClick={onClose}
            style={{
              padding: "var(--space-sm) var(--space-lg)",
              borderRadius: "var(--border-radius)",
              background: "var(--bg-hover)",
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              padding: "var(--space-sm) var(--space-lg)",
              borderRadius: "var(--border-radius)",
              background: "var(--accent-bg)",
              color: "var(--text-on-accent)",
              opacity: saving ? 0.6 : 1,
            }}
          >
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

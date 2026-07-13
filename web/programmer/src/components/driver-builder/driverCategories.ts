// The ten canonical driver categories the community catalog accepts. This is
// the single source of truth for every driver-authoring surface in the IDE, so
// the authoring dropdowns can't drift out of sync with the catalog again. Keep
// it in lockstep with build_index.py's DRIVER_CATEGORIES (openavc-drivers) and
// avcdriver.schema.json's category enum. A value outside this list authors and
// runs locally with no warning but is rejected by build_index.py's validator at
// catalog-submission CI, far from the authoring surface, so the dropdowns must
// only ever offer these.
export interface DriverCategory {
  value: string;
  label: string;
}

export const DRIVER_CATEGORIES: DriverCategory[] = [
  { value: "projector", label: "Projector" },
  { value: "display", label: "Display" },
  { value: "switcher", label: "Switcher" },
  { value: "audio", label: "Audio" },
  { value: "camera", label: "Camera" },
  { value: "video", label: "Video (encoders, decoders, NDI)" },
  { value: "streaming", label: "Streaming" },
  { value: "lighting", label: "Lighting" },
  { value: "power", label: "Power (PDU, UPS, sequencer)" },
  { value: "utility", label: "Utility" },
];

import type { DividerPreset } from "./types";

export const POLL_INTERVAL_MS = 10_000;

export const DIVIDER_PRESETS: Record<DividerPreset, { label: string; gradient: string }> = {
  classic: {
    label: "Classic",
    gradient: "linear-gradient(90deg, #c85000, #ff8c00, #c85000)",
  },
  intense: {
    label: "Intense",
    gradient: "linear-gradient(90deg, #cc0000, #ff3300, #cc0000)",
  },
  ice: {
    label: "Ice",
    gradient: "linear-gradient(90deg, #4080ff, #80b0ff, #4080ff)",
  },
  pulse: {
    label: "Pulse",
    gradient: "linear-gradient(90deg, #aaa, #ddd, #aaa)",
  },
  chaos: {
    label: "Chaos",
    gradient: "linear-gradient(90deg, #ff4400, #ff8800, #ff4400)",
  },
};

export const CELEBRATION_OPTIONS = [
  { value: "freeze", label: "Freeze" },
  { value: "chase", label: "Chase" },
  { value: "twinkle", label: "Twinkle" },
  { value: "flash", label: "Flash" },
  { value: "solid", label: "Solid" },
] as const;

export const AFTER_ACTION_OPTIONS = [
  { value: "fade_off", label: "Fade off" },
  { value: "off", label: "Off" },
  { value: "restore", label: "Restore previous preset" },
  { value: "preset", label: "Switch to preset..." },
] as const;

export const DURATION_OPTIONS = [
  { value: 30, label: "30 seconds" },
  { value: 60, label: "1 minute" },
  { value: 300, label: "5 minutes" },
  { value: 600, label: "10 minutes" },
  { value: -1, label: "Custom" },
] as const;

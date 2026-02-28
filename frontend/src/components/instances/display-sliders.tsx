import { useState } from "react";
import { useDebounce } from "@/lib/use-debounce";
import { api } from "@/lib/api";
import { DIVIDER_PRESETS } from "@/lib/constants";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { DividerPreset, Instance } from "@/lib/types";

interface DisplaySlidersProps {
  instance: Instance;
}

interface SliderRowProps {
  label: string;
  value: number;
  min: number;
  max: number;
  format?: (v: number) => string;
  onChange: (v: number) => void;
}

function SliderRow({ label, value, min, max, format, onChange }: SliderRowProps) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-24 shrink-0 text-[11px] text-muted-foreground">{label}</span>
      <input
        type="range"
        className="h-1.5 flex-1 cursor-pointer appearance-none rounded-full bg-secondary accent-primary"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <span className="w-12 text-right font-mono text-[11px] text-muted-foreground">
        {format ? format(value) : value}
      </span>
    </div>
  );
}

export function DisplaySliders({ instance: inst }: DisplaySlidersProps) {
  const [dignity, setDignity] = useState(Math.round(inst.min_team_pct * 100));
  const [buffer, setBuffer] = useState(inst.dark_buffer_pixels);
  const [divider, setDivider] = useState(inst.contested_zone_pixels);
  const [preset, setPreset] = useState<DividerPreset>(inst.divider_preset);
  const [chaseSpeed, setChaseSpeed] = useState(inst.chase_speed);
  const [chaseIntensity, setChaseIntensity] = useState(inst.chase_intensity);

  const debouncedSave = useDebounce(() => {
    api.updateSettings(inst.host, {
      min_team_pct: dignity / 100,
      dark_buffer_pixels: buffer,
      contested_zone_pixels: divider,
      divider_preset: preset,
      chase_speed: chaseSpeed,
      chase_intensity: chaseIntensity,
    });
  }, 500);

  const update = <T,>(setter: React.Dispatch<React.SetStateAction<T>>) => (v: T) => {
    setter(v);
    debouncedSave();
  };

  const battleZone = buffer * 2 + divider;

  return (
    <div className="space-y-2">
      <SliderRow
        label="Min Dignity"
        value={dignity}
        min={1}
        max={20}
        format={(v) => `${v}%`}
        onChange={update(setDignity)}
      />
      <SliderRow
        label="Buffer"
        value={buffer}
        min={0}
        max={20}
        format={(v) => `${v}px`}
        onChange={update(setBuffer)}
      />
      <SliderRow
        label="Divider"
        value={divider}
        min={2}
        max={30}
        format={(v) => `${v}px`}
        onChange={update(setDivider)}
      />

      <div className="flex items-center gap-3">
        <span className="w-24 shrink-0 text-[11px] text-muted-foreground">Style</span>
        <Select
          value={preset}
          onValueChange={(val) => {
            setPreset(val as DividerPreset);
            debouncedSave();
          }}
        >
          <SelectTrigger size="sm" className="h-7 flex-1 text-[11px] bg-secondary border-input">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(DIVIDER_PRESETS).map(([key, { label }]) => (
              <SelectItem key={key} value={key}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="w-12" />
      </div>

      <SliderRow
        label="Chase Speed"
        value={chaseSpeed}
        min={50}
        max={255}
        onChange={update(setChaseSpeed)}
      />
      <SliderRow
        label="Intensity"
        value={chaseIntensity}
        min={50}
        max={255}
        onChange={update(setChaseIntensity)}
      />

      <div className="text-[11px] text-muted-foreground">
        Battle zone total: {battleZone}px
      </div>
    </div>
  );
}

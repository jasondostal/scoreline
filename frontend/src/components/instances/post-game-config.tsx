import { useEffect, useState } from "react";
import { useDebounce } from "@/lib/use-debounce";
import { api } from "@/lib/api";
import {
  CELEBRATION_OPTIONS,
  AFTER_ACTION_OPTIONS,
  DURATION_OPTIONS,
} from "@/lib/constants";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { AfterAction, CelebrationType, Instance } from "@/lib/types";

interface PostGameConfigProps {
  instance: Instance;
}

export function PostGameConfig({ instance: inst }: PostGameConfigProps) {
  const [celebration, setCelebration] = useState<CelebrationType>(
    inst.post_game_celebration,
  );
  const [duration, setDuration] = useState(inst.post_game_duration);
  const [isCustomDuration, setIsCustomDuration] = useState(
    !DURATION_OPTIONS.some(
      (o) => o.value > 0 && o.value === inst.post_game_duration,
    ),
  );
  const [afterAction, setAfterAction] = useState<AfterAction>(
    inst.post_game_after_action,
  );
  const [presetId, setPresetId] = useState<number | null>(
    inst.post_game_preset_id,
  );

  // Sync local state when props change
  useEffect(() => {
    setCelebration(inst.post_game_celebration);
    setDuration(inst.post_game_duration);
    setIsCustomDuration(!DURATION_OPTIONS.some((o) => o.value > 0 && o.value === inst.post_game_duration));
    setAfterAction(inst.post_game_after_action);
    setPresetId(inst.post_game_preset_id);
  }, [inst.post_game_celebration, inst.post_game_duration, inst.post_game_after_action, inst.post_game_preset_id]);

  const debouncedSave = useDebounce(() => {
    api.updatePostGame(inst.host, {
      celebration,
      celebration_duration_s: duration,
      after_action: afterAction,
      preset_id: afterAction === "preset" ? presetId : null,
    });
  }, 500);

  return (
    <div className="space-y-2">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        Post-Game Celebration
      </div>

      {/* Celebration type */}
      <div className="flex items-center gap-3">
        <span id="celebration-label" className="w-20 shrink-0 text-[11px] text-muted-foreground">
          Celebration
        </span>
        <Select
          value={celebration}
          onValueChange={(val) => {
            setCelebration(val as CelebrationType);
            debouncedSave();
          }}
        >
          <SelectTrigger size="sm" className="h-8 flex-1 text-xs bg-secondary border-input" aria-labelledby="celebration-label">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CELEBRATION_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Duration */}
      <div className="flex items-center gap-3">
        <span id="duration-label" className="w-20 shrink-0 text-[11px] text-muted-foreground">
          Duration
        </span>
        <Select
          value={isCustomDuration ? "custom" : String(duration)}
          onValueChange={(val) => {
            if (val === "custom") {
              setIsCustomDuration(true);
            } else {
              setIsCustomDuration(false);
              setDuration(Number(val));
              debouncedSave();
            }
          }}
        >
          <SelectTrigger size="sm" className="h-8 flex-1 text-xs bg-secondary border-input" aria-labelledby="duration-label">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {DURATION_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value === -1 ? "custom" : String(o.value)}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {isCustomDuration && (
          <>
            <input
              type="number"
              aria-label="Custom duration in seconds"
              className="w-16 rounded border border-input bg-secondary px-2 py-1 text-xs text-foreground"
              value={duration}
              min={5}
              max={3600}
              onChange={(e) => {
                setDuration(Number(e.target.value));
                debouncedSave();
              }}
            />
            <span className="text-[11px] text-muted-foreground">sec</span>
          </>
        )}
      </div>

      {/* After action */}
      <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mt-2">
        After Celebration
      </div>

      <div className="flex items-center gap-3">
        <span id="after-action-label" className="w-20 shrink-0 text-[11px] text-muted-foreground">
          Action
        </span>
        <Select
          value={afterAction}
          onValueChange={(val) => {
            setAfterAction(val as AfterAction);
            debouncedSave();
          }}
        >
          <SelectTrigger size="sm" className="h-8 flex-1 text-xs bg-secondary border-input" aria-labelledby="after-action-label">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {AFTER_ACTION_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {afterAction === "preset" && (
        <div className="flex items-center gap-3">
          <span className="w-20 shrink-0 text-[11px] text-muted-foreground">
            Preset ID
          </span>
          <input
            type="number"
            aria-label="WLED preset ID"
            className="w-20 rounded border border-input bg-secondary px-2 py-1 text-xs text-foreground"
            value={presetId ?? ""}
            min={1}
            onChange={(e) => {
              setPresetId(Number(e.target.value) || null);
              debouncedSave();
            }}
          />
        </div>
      )}
    </div>
  );
}

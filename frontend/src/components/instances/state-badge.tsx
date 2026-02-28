import type { UIState } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Radio, Shield, Eye, Flag, Gamepad2 } from "lucide-react";

interface StateBadgeProps {
  state: UIState;
  simulating: boolean;
  watchTeams?: string[];
  finalLingerRemaining?: number | null;
}

export function StateBadge({
  state,
  simulating,
  watchTeams,
  finalLingerRemaining,
}: StateBadgeProps) {
  return (
    <span className="flex items-center gap-1.5">
      {simulating && (
        <span className="inline-flex items-center gap-1 rounded bg-sim/15 px-1.5 py-0.5 text-[10px] font-semibold text-sim">
          <Gamepad2 className="h-3 w-3" />
          SIM
        </span>
      )}
      <StateBadgeInner
        state={state}
        watchTeams={watchTeams}
        finalLingerRemaining={finalLingerRemaining}
      />
    </span>
  );
}

function StateBadgeInner({
  state,
  watchTeams,
  finalLingerRemaining,
}: {
  state: UIState;
  watchTeams?: string[];
  finalLingerRemaining?: number | null;
}) {
  switch (state) {
    case "watching_auto":
      return (
        <span className="inline-flex items-center gap-1 rounded bg-auto/15 px-1.5 py-0.5 text-[10px] font-semibold text-auto">
          <Eye className="h-3 w-3" />
          AUTO
        </span>
      );
    case "watching_manual":
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-live">
          <Radio className="h-3 w-3" />
          LIVE
        </span>
      );
    case "watching_override":
      return (
        <span className="inline-flex items-center gap-1 rounded bg-override/15 px-1.5 py-0.5 text-[10px] font-semibold text-override">
          <Radio className="h-3 w-3" />
          OVERRIDE
        </span>
      );
    case "final": {
      const secs = finalLingerRemaining ? Math.ceil(finalLingerRemaining) : 0;
      return (
        <span className={cn(
          "inline-flex items-center gap-1 rounded bg-final-state/15 px-1.5 py-0.5 text-[10px] font-semibold text-final-state",
        )}>
          <Flag className="h-3 w-3" />
          FINAL{secs > 0 && ` (${secs}s)`}
        </span>
      );
    }
    case "idle_autowatch":
      return (
        <span
          className="inline-flex items-center gap-1 text-[10px] font-medium text-armed"
          title={`Watching for: ${(watchTeams ?? []).join(", ")}`}
        >
          <Shield className="h-3 w-3" />
          Armed
        </span>
      );
    default:
      return null;
  }
}

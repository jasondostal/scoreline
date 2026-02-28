import type { Instance } from "@/lib/types";
import { TeamDot } from "@/components/shared/team-dot";

interface ScoreboardProps {
  instance: Instance;
}

export function Scoreboard({ instance: inst }: ScoreboardProps) {
  const isFinal = inst.state === "final";

  return (
    <div className="mb-2 rounded border border-border bg-secondary/50 px-3 py-2 text-sm">
      {/* Away team */}
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 font-medium">
          {inst.away_colors && <TeamDot colors={inst.away_colors} size={8} />}
          {inst.away_display || inst.away_team}
        </span>
        <span className="font-mono text-sm font-semibold">
          {inst.away_score ?? "-"}
        </span>
      </div>

      {/* Home team */}
      <div className="mt-0.5 flex items-center justify-between">
        <span className="flex items-center gap-1.5 font-medium">
          {inst.home_colors && <TeamDot colors={inst.home_colors} size={8} />}
          {inst.home_display || inst.home_team}
        </span>
        <span className="font-mono text-sm font-semibold">
          {inst.home_score ?? "-"}
        </span>
      </div>

      {/* Period / Win probability */}
      <div className="mt-1.5 flex items-center justify-between border-t border-border pt-1.5 text-[11px] text-muted-foreground">
        <span>{isFinal ? "FINAL" : inst.period || ""}</span>
        <span>
          {inst.home_win_pct !== undefined &&
            `${(inst.home_win_pct * 100).toFixed(0)}% ${inst.home_display || inst.home_team}`}
        </span>
      </div>
    </div>
  );
}

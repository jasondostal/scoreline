import { useRef, useCallback } from "react";
import type { Instance } from "@/lib/types";
import { TeamDot } from "@/components/shared/team-dot";
import { Sparkline } from "@/components/shared/sparkline";
import { ShareCard } from "./share-card";
import { captureAndShare } from "@/lib/share";
import { Share2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ScoreboardProps {
  instance: Instance;
}

export function Scoreboard({ instance: inst }: ScoreboardProps) {
  const isFinal = inst.state === "final";
  const shareRef = useRef<HTMLDivElement>(null);

  const handleShare = useCallback(async () => {
    if (!shareRef.current) return;
    const away = inst.away_display || inst.away_team || "Away";
    const home = inst.home_display || inst.home_team || "Home";
    await captureAndShare(shareRef.current, `scoreline-${away}-vs-${home}.png`);
  }, [inst]);

  return (
    <>
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

        {/* Period / Win probability / Share */}
        <div className="mt-1.5 flex items-center justify-between border-t border-border pt-1.5 text-[11px] text-muted-foreground">
          <span>{isFinal ? "FINAL" : inst.period || ""}</span>
          <span className="flex items-center gap-2">
            {inst.home_win_pct !== undefined &&
              `${(inst.home_win_pct * 100).toFixed(0)}% ${inst.home_display || inst.home_team}`}
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={handleShare}
              title="Share game card"
              className="h-5 w-5"
            >
              <Share2 className="h-3 w-3" />
            </Button>
          </span>
        </div>

        {/* Win probability sparkline */}
        {inst.win_pct_history && inst.win_pct_history.length > 1 && (
          <div className="mt-1.5 border-t border-border pt-1.5">
            <Sparkline points={inst.win_pct_history} className="w-full" />
          </div>
        )}
      </div>

      {/* Offscreen share card for capture */}
      <div style={{ position: "absolute", left: -9999, top: -9999 }}>
        <ShareCard ref={shareRef} instance={inst} />
      </div>
    </>
  );
}

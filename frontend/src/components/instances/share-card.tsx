import { forwardRef } from "react";
import type { Instance } from "@/lib/types";
import { TeamDot } from "@/components/shared/team-dot";
import { Sparkline } from "@/components/shared/sparkline";
import { StripPreview } from "./strip-preview";

interface ShareCardProps {
  instance: Instance;
}

export const ShareCard = forwardRef<HTMLDivElement, ShareCardProps>(
  ({ instance: inst }, ref) => {
    const previewPct = inst.home_win_pct ?? 0.5;
    const isFinal = inst.state === "final";

    return (
      <div
        ref={ref}
        style={{
          width: 600,
          padding: 24,
          background: "#1a1a1a",
          color: "#f0f0f0",
          fontFamily: "'Inter', sans-serif",
          borderRadius: 12,
        }}
      >
        {/* Teams + Scores */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {inst.away_colors && <TeamDot colors={inst.away_colors} size={16} />}
            <span style={{ fontSize: 20, fontWeight: 600 }}>{inst.away_display || inst.away_team}</span>
          </div>
          <span style={{ fontSize: 28, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>
            {inst.away_score ?? "-"}
          </span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {inst.home_colors && <TeamDot colors={inst.home_colors} size={16} />}
            <span style={{ fontSize: 20, fontWeight: 600 }}>{inst.home_display || inst.home_team}</span>
          </div>
          <span style={{ fontSize: 28, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>
            {inst.home_score ?? "-"}
          </span>
        </div>

        {/* Period + Win Pct */}
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "#888", marginBottom: 12 }}>
          <span>{isFinal ? "FINAL" : inst.period || ""}</span>
          <span>
            {inst.home_win_pct !== undefined &&
              `${(inst.home_win_pct * 100).toFixed(0)}% ${inst.home_display || inst.home_team}`}
          </span>
        </div>

        {/* Sparkline */}
        {inst.win_pct_history && inst.win_pct_history.length > 1 && (
          <div style={{ marginBottom: 12 }}>
            <Sparkline points={inst.win_pct_history} height={40} className="w-full" />
          </div>
        )}

        {/* Strip Preview */}
        <div style={{ marginBottom: 16 }}>
          <StripPreview
            start={inst.start}
            end={inst.end}
            winPct={previewPct}
            minTeamPct={inst.min_team_pct}
            contestedZonePixels={inst.contested_zone_pixels}
            darkBufferPixels={inst.dark_buffer_pixels}
            dividerPreset={inst.divider_preset}
            homeColors={inst.home_colors}
            awayColors={inst.away_colors}
          />
        </div>

        {/* Branding */}
        <div style={{ textAlign: "right", fontSize: 11, color: "#555" }}>
          Scoreline
        </div>
      </div>
    );
  },
);

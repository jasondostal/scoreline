import { DIVIDER_PRESETS } from "@/lib/constants";
import { calculateStripSegments } from "@/lib/strip-math";
import type { DividerPreset } from "@/lib/types";

interface StripPreviewProps {
  start: number;
  end: number;
  winPct: number;
  minTeamPct: number;
  contestedZonePixels: number;
  darkBufferPixels: number;
  dividerPreset: DividerPreset;
  homeColors?: number[][];
  awayColors?: number[][];
}

export function StripPreview({
  start,
  end,
  winPct,
  minTeamPct,
  contestedZonePixels,
  darkBufferPixels,
  dividerPreset,
  homeColors,
  awayColors,
}: StripPreviewProps) {
  const seg = calculateStripSegments(
    start,
    end,
    winPct,
    minTeamPct,
    contestedZonePixels,
    darkBufferPixels,
  );

  const dividerGradient =
    DIVIDER_PRESETS[dividerPreset]?.gradient ?? DIVIDER_PRESETS.classic.gradient;

  const homeGradient = homeColors
    ? `linear-gradient(90deg, rgb(${homeColors[0].join(",")}) 0%, rgb(${homeColors[1].join(",")}) 100%)`
    : "linear-gradient(90deg, #4a90d9, #357abd)";

  const awayGradient = awayColors
    ? `linear-gradient(90deg, rgb(${awayColors[0].join(",")}) 0%, rgb(${awayColors[1].join(",")}) 100%)`
    : "linear-gradient(90deg, #d94a4a, #bd3535)";

  return (
    <div className="flex h-5 w-full overflow-hidden rounded-sm">
      {/* Home segment */}
      <div
        className="flex items-center justify-center text-[9px] font-medium text-white/80"
        style={{ width: `${seg.homePct}%`, background: homeGradient }}
      >
        {seg.homePixels > 30 && `${seg.homePixels}px`}
      </div>

      {/* Dark buffer */}
      <div
        className="bg-black"
        style={{ width: `${seg.bufferPct}%` }}
      />

      {/* Divider / contested zone */}
      <div
        style={{ width: `${seg.dividerPct}%`, background: dividerGradient }}
      />

      {/* Dark buffer */}
      <div
        className="bg-black"
        style={{ width: `${seg.bufferPct}%` }}
      />

      {/* Away segment */}
      <div
        className="flex items-center justify-center text-[9px] font-medium text-white/80"
        style={{ width: `${seg.awayPct}%`, background: awayGradient }}
      >
        {seg.awayPixels > 30 && `${seg.awayPixels}px`}
      </div>
    </div>
  );
}

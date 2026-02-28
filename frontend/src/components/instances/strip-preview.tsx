import { useCallback, useRef } from "react";
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
  onDragPct?: (pct: number) => void;
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
  onDragPct,
}: StripPreviewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const pctFromPointer = useCallback(
    (clientX: number) => {
      const el = containerRef.current;
      if (!el) return winPct;
      const rect = el.getBoundingClientRect();
      const raw = (clientX - rect.left) / rect.width;
      return Math.max(minTeamPct, Math.min(1 - minTeamPct, raw));
    },
    [winPct, minTeamPct],
  );

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (!onDragPct) return;
      dragging.current = true;
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
      onDragPct(pctFromPointer(e.clientX));
    },
    [onDragPct, pctFromPointer],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!dragging.current || !onDragPct) return;
      onDragPct(pctFromPointer(e.clientX));
    },
    [onDragPct, pctFromPointer],
  );

  const handlePointerUp = useCallback(() => {
    dragging.current = false;
  }, []);

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

  const isDraggable = !!onDragPct;

  return (
    <div
      ref={containerRef}
      className={`flex h-5 w-full overflow-hidden rounded-sm ${isDraggable ? "cursor-grab active:cursor-grabbing" : ""}`}
      onPointerDown={isDraggable ? handlePointerDown : undefined}
      onPointerMove={isDraggable ? handlePointerMove : undefined}
      onPointerUp={isDraggable ? handlePointerUp : undefined}
      style={{ touchAction: isDraggable ? "none" : undefined }}
    >
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

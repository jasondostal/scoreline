interface SparklineProps {
  points: { t: number; pct: number }[];
  height?: number;
  className?: string;
}

export function Sparkline({ points, height = 28, className }: SparklineProps) {
  if (points.length < 2) return null;

  const w = 200;
  const h = height;
  const pad = 1;

  // Map points to SVG coordinates
  const coords = points.map((p, i) => {
    const x = (i / (points.length - 1)) * w;
    const y = pad + (1 - p.pct) * (h - pad * 2);
    return `${x},${y}`;
  });

  const polyline = coords.join(" ");
  // Close the fill path along the bottom
  const fillPath = `${coords.join(" ")} ${w},${h} 0,${h}`;

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      className={className}
      style={{ height }}
    >
      <defs>
        <linearGradient id="spark-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.2" />
          <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
        </linearGradient>
      </defs>
      {/* 50% reference line */}
      <line
        x1="0" y1={h / 2} x2={w} y2={h / 2}
        stroke="var(--muted-foreground)"
        strokeOpacity="0.2"
        strokeDasharray="3,3"
      />
      {/* Fill under the line */}
      <polygon points={fillPath} fill="url(#spark-fill)" />
      {/* The line itself */}
      <polyline
        points={polyline}
        fill="none"
        stroke="var(--primary)"
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

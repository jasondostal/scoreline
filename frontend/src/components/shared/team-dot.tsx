interface TeamDotProps {
  colors: number[][];
  size?: number;
  className?: string;
}

export function TeamDot({ colors, size = 10, className }: TeamDotProps) {
  const [r, g, b] = colors[0] ?? [128, 128, 128];
  return (
    <span
      className={`inline-block shrink-0 rounded-full ${className ?? ""}`}
      style={{
        width: size,
        height: size,
        backgroundColor: `rgb(${r}, ${g}, ${b})`,
      }}
    />
  );
}

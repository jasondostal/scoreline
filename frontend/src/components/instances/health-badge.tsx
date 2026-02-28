import type { HealthInfo } from "@/lib/types";
import { cn } from "@/lib/utils";
import { WifiOff, AlertTriangle } from "lucide-react";

interface HealthBadgeProps {
  health: HealthInfo;
}

export function HealthBadge({ health }: HealthBadgeProps) {
  if (health.status === "healthy") return null;

  if (health.status === "unreachable") {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium",
          "bg-destructive/15 text-destructive",
        )}
        title={`Last error: ${health.last_error || "Unknown"}`}
      >
        <WifiOff className="h-3 w-3" />
        WLED
      </span>
    );
  }

  // stale
  return (
    <span
      className="inline-flex items-center gap-0.5 text-[10px] text-override"
      title="No update in 2+ minutes"
    >
      <AlertTriangle className="h-3 w-3" />
    </span>
  );
}

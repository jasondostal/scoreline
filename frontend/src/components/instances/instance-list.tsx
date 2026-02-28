import type { Instance, League } from "@/lib/types";
import { InstanceCard } from "./instance-card";

interface InstanceListProps {
  instances: Instance[] | null;
  instancesLoading: boolean;
  instancesError: string | null;
  leagues: League[];
  onMutate: () => void;
}

export function InstanceList({
  instances,
  instancesLoading,
  instancesError,
  leagues,
  onMutate,
}: InstanceListProps) {
  if (instancesLoading && !instances) {
    return (
      <div className="space-y-3">
        {[1, 2].map((i) => (
          <div
            key={i}
            className="h-24 animate-pulse rounded-lg border border-border bg-card"
          />
        ))}
      </div>
    );
  }

  if (instancesError && !instances) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
        Failed to load instances: {instancesError}
      </div>
    );
  }

  if (!instances || instances.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-6 text-center text-sm text-muted-foreground">
        No WLED instances configured. Add one to get started.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {instances.map((inst) => (
        <InstanceCard
          key={inst.host}
          instance={inst}
          leagues={leagues}
          onMutate={onMutate}
        />
      ))}
    </div>
  );
}

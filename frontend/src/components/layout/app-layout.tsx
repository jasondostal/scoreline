import type { Instance, League } from "@/lib/types";
import { InstanceList } from "@/components/instances/instance-list";
import { SimulatorPanel } from "@/components/simulator/simulator-panel";
import { AddDeviceForm } from "@/components/device/add-device-form";
import { DiscoverPanel } from "@/components/device/discover-panel";
import { Monitor, Play, Activity } from "lucide-react";

function ScorelineMark({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" className={className}>
      <defs>
        <clipPath id="sl-left">
          <polygon points="0,0 18,0 14,10 20,10 12,22 18,22 10,32 0,32" />
        </clipPath>
        <clipPath id="sl-right">
          <polygon points="32,0 18,0 14,10 20,10 12,22 18,22 10,32 32,32" />
        </clipPath>
      </defs>
      <rect width="32" height="32" rx="7" fill="currentColor" opacity="0.15" />
      <rect width="32" height="32" rx="7" className="fill-primary" clipPath="url(#sl-left)" />
      <rect width="32" height="32" rx="7" fill="#e8eaed" clipPath="url(#sl-right)" />
    </svg>
  );
}

interface AppLayoutProps {
  instances: Instance[] | null;
  instancesLoading: boolean;
  instancesError: string | null;
  leagues: League[] | null;
  leaguesLoading: boolean;
  onMutate: () => void;
  wsConnected?: boolean;
}

export function AppLayout({
  instances,
  instancesLoading,
  instancesError,
  leagues,
  leaguesLoading,
  onMutate,
  wsConnected,
}: AppLayoutProps) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border px-6 py-4">
        <div className="mx-auto max-w-4xl">
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-primary">
            <ScorelineMark className="h-7 w-7" />
            Scoreline
          </h1>
          <p className="text-sm text-muted-foreground">
            Live sports win probability on WLED
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-6 py-6 space-y-8">
        {/* WLED Instances */}
        <section>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <Monitor className="h-5 w-5 text-muted-foreground" />
              WLED Instances
            </h2>
            <div className="flex gap-2">
              <AddDeviceForm onMutate={onMutate} />
              <DiscoverPanel onMutate={onMutate} />
            </div>
          </div>
          <InstanceList
            instances={instances}
            instancesLoading={instancesLoading}
            instancesError={instancesError}
            leagues={leagues ?? []}
            onMutate={onMutate}
          />
        </section>

        {/* Simulator */}
        <section>
          <h2 className="flex items-center gap-2 text-lg font-semibold mb-4">
            <Play className="h-5 w-5 text-muted-foreground" />
            Simulator
          </h2>
          <SimulatorPanel
            instances={instances ?? []}
            leagues={leagues ?? []}
            onMutate={onMutate}
          />
        </section>

        {/* Footer */}
        <footer className="text-xs text-muted-foreground pt-4 border-t border-border">
          <p className="flex items-center gap-1.5">
            <Activity className="h-3 w-3" />
            {leaguesLoading
              ? "Loading leagues..."
              : `${leagues?.length ?? 0} leagues`}
            {" · "}
            {instances?.length ?? 0} instance{(instances?.length ?? 0) !== 1 ? "s" : ""}
            {wsConnected !== undefined && (
              <>
                {" · "}
                <span className={`inline-block h-1.5 w-1.5 rounded-full ${wsConnected ? "bg-live" : "bg-muted-foreground/30"}`} />
                {wsConnected ? "Live" : "Polling"}
              </>
            )}
          </p>
        </footer>
      </main>
    </div>
  );
}

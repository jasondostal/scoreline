import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { TeamDot } from "@/components/shared/team-dot";
import { MultiSelect } from "@/components/ui/multi-select";
import type { Instance, League, Team } from "@/lib/types";

interface WatchTeamsProps {
  instance: Instance;
  leagues: League[];
  onMutate: () => void;
}

// Create a team dot icon component factory for the multi-select icon prop
function makeTeamDotIcon(colors: number[][]) {
  return function TeamDotIcon({ className }: { className?: string }) {
    return <TeamDot colors={colors} size={12} className={className} />;
  };
}

export function WatchTeams({ instance: inst, leagues, onMutate }: WatchTeamsProps) {
  const [allTeams, setAllTeams] = useState<Map<string, Team[]>>(new Map());
  const [loading, setLoading] = useState(true);

  // Load teams for ALL leagues on mount
  useEffect(() => {
    if (leagues.length === 0) return;
    setLoading(true);
    Promise.all(
      leagues.map((l) =>
        api.teams(l.id).then((teams) => [l.id, teams] as const),
      ),
    )
      .then((results) => {
        setAllTeams(new Map(results));
      })
      .finally(() => setLoading(false));
  }, [leagues]);

  // Build grouped options for multi-select
  const groupedOptions = useMemo(() => {
    return leagues.map((league) => ({
      heading: league.name,
      options: (allTeams.get(league.id) ?? []).map((team) => ({
        value: `${league.id}:${team.id}`,
        label: team.name,
        icon: makeTeamDotIcon(team.colors),
      })),
    }));
  }, [leagues, allTeams]);

  const handleChange = async (newValues: string[]) => {
    await api.setWatchTeams(inst.host, newValues);
    onMutate();
  };

  return (
    <div>
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        Auto-Watch Teams
      </div>

      <MultiSelect
        options={groupedOptions}
        defaultValue={inst.watch_teams}
        onValueChange={handleChange}
        placeholder={loading ? "Loading teams..." : "Search teams to auto-watch..."}
        disabled={loading}
        maxCount={5}
        className="bg-secondary border-input text-xs"
      />

      <div className="mt-1 text-[11px] text-muted-foreground">
        {inst.watch_teams.length > 1
          ? "Priority: first selected team wins if multiple games start simultaneously."
          : "Select teams to auto-start watching when their games begin."}
      </div>
    </div>
  );
}

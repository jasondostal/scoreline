import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Game, Instance, League } from "@/lib/types";
import { TeamDot } from "@/components/shared/team-dot";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Button } from "@/components/ui/button";
import { Search } from "lucide-react";

interface GamePickerProps {
  instance: Instance;
  leagues: League[];
  onWatch: (league: string, gameId: string) => void;
}

interface LeagueGames {
  league: League;
  games: Game[];
}

export function GamePicker({ instance, leagues, onWatch }: GamePickerProps) {
  const [open, setOpen] = useState(false);
  const [allGames, setAllGames] = useState<LeagueGames[]>([]);
  const [loading, setLoading] = useState(false);

  const loadAllGames = useCallback(async () => {
    setLoading(true);
    try {
      const results = await Promise.all(
        leagues.map(async (l) => {
          try {
            const games = await api.games(l.id);
            return { league: l, games };
          } catch {
            return { league: l, games: [] };
          }
        }),
      );
      // Only show leagues that have games
      setAllGames(results.filter((r) => r.games.length > 0));
    } finally {
      setLoading(false);
    }
  }, [leagues]);

  // Load games when popover opens
  useEffect(() => {
    if (open) loadAllGames();
  }, [open, loadAllGames]);

  const handleSelect = (value: string) => {
    // value format: "league:gameId"
    const sep = value.indexOf(":");
    if (sep === -1) return;
    const league = value.slice(0, sep);
    const gameId = value.slice(sep + 1);
    onWatch(league, gameId);
    setOpen(false);
  };

  const isWatching = ["watching_auto", "watching_manual", "watching_override"].includes(
    instance.state,
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="mb-2 w-full justify-start gap-2 bg-secondary text-xs border-input h-8"
        >
          <Search className="h-3 w-3 shrink-0 text-muted-foreground" />
          <span className="text-muted-foreground">
            {isWatching ? "Switch game..." : "Watch a game..."}
          </span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0" align="start">
        <Command>
          <CommandInput placeholder="Search teams..." />
          <CommandList className="max-h-64">
            <CommandEmpty>
              {loading ? "Loading games..." : "No games found"}
            </CommandEmpty>
            {allGames.map(({ league, games }) => (
              <CommandGroup key={league.id} heading={league.name}>
                {games.map((g) => (
                  <CommandItem
                    key={`${league.id}:${g.id}`}
                    value={`${league.id}:${g.id} ${g.away_display} ${g.home_display}`}
                    onSelect={() => handleSelect(`${league.id}:${g.id}`)}
                    className="gap-2 text-xs"
                  >
                    <span className="flex items-center gap-1">
                      {g.away_colors && <TeamDot colors={g.away_colors} size={8} />}
                      <span>{g.away_display}</span>
                    </span>
                    <span className="text-muted-foreground">@</span>
                    <span className="flex items-center gap-1">
                      {g.home_colors && <TeamDot colors={g.home_colors} size={8} />}
                      <span>{g.home_display}</span>
                    </span>
                    <span className="ml-auto text-[10px] text-muted-foreground">
                      {g.detail}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

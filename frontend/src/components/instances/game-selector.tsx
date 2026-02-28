import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { LeagueSelect } from "@/components/shared/league-select";
import type { Game, Instance, League } from "@/lib/types";

interface GameSelectorProps {
  instance: Instance;
  leagues: League[];
  onWatch: (league: string, gameId: string) => void;
}

export function GameSelector({ instance, leagues, onWatch }: GameSelectorProps) {
  const [selectedLeague, setSelectedLeague] = useState(instance.league ?? "");
  const [games, setGames] = useState<Game[]>([]);
  const [gamesLoading, setGamesLoading] = useState(false);

  // Sync selected league when instance data changes (e.g. auto-watch starts a game)
  useEffect(() => {
    if (instance.league && instance.league !== selectedLeague) {
      setSelectedLeague(instance.league);
    }
  }, [instance.league]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadGames = useCallback(async (league: string) => {
    if (!league) {
      setGames([]);
      return;
    }
    setGamesLoading(true);
    try {
      const data = await api.games(league);
      setGames(data);
    } catch {
      setGames([]);
    } finally {
      setGamesLoading(false);
    }
  }, []);

  // Load games when league changes
  useEffect(() => {
    if (selectedLeague) {
      loadGames(selectedLeague);
    }
  }, [selectedLeague, loadGames]);

  const handleLeagueChange = (value: string) => {
    setSelectedLeague(value);
    setGames([]);
  };

  // Key to force-reset the game select after picking (it's an action trigger, not persistent state)
  const selectResetKey = useRef(0);

  const handleGameChange = (gameId: string) => {
    if (gameId && selectedLeague) {
      onWatch(selectedLeague, gameId);
      selectResetKey.current += 1;
    }
  };

  const isWatching = ["watching_auto", "watching_manual", "watching_override", "final"].includes(
    instance.state,
  );

  const gamePlaceholder = gamesLoading
    ? "Loading..."
    : !selectedLeague
      ? "Select league first..."
      : games.length === 0
        ? "No games available"
        : isWatching
          ? "Switch game..."
          : "Select game...";

  return (
    <div className="mb-2 flex gap-1.5">
      <LeagueSelect
        leagues={leagues}
        value={selectedLeague}
        onValueChange={handleLeagueChange}
        className="flex-1"
      />

      <Select
        key={selectResetKey.current}
        onValueChange={handleGameChange}
        disabled={!selectedLeague || gamesLoading || games.length === 0}
      >
        <SelectTrigger size="sm" className="h-8 flex-[2] text-xs bg-secondary border-input">
          <SelectValue placeholder={gamePlaceholder} />
        </SelectTrigger>
        <SelectContent>
          {games.map((g) => (
            <SelectItem key={g.id} value={g.id}>
              {g.away_display} @ {g.home_display} ({g.detail})
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

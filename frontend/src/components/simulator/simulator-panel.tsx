import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { useDebounce } from "@/lib/use-debounce";
import { DIVIDER_PRESETS } from "@/lib/constants";
import { StripPreview } from "@/components/instances/strip-preview";
import { ScenarioPresets } from "./scenario-presets";
import { LeagueSelect } from "@/components/shared/league-select";
import { TeamDot } from "@/components/shared/team-dot";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import type { DividerPreset, Instance, League, Team } from "@/lib/types";
import { Save, Square } from "lucide-react";

interface SimulatorPanelProps {
  instances: Instance[];
  leagues: League[];
  onMutate: () => void;
}

export function SimulatorPanel({ instances, leagues, onMutate }: SimulatorPanelProps) {
  // Load saved defaults
  const { data: defaults } = useFetch(() => api.simulatorDefaults());

  const [league, setLeague] = useState("");
  const [homeTeam, setHomeTeam] = useState("");
  const [awayTeam, setAwayTeam] = useState("");
  const [winPct, setWinPct] = useState(50);
  const [teams, setTeams] = useState<Team[]>([]);
  const [activeScenario, setActiveScenario] = useState<string | null>(null);
  const animationRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Display settings
  const [dignity, setDignity] = useState(5);
  const [buffer, setBuffer] = useState(4);
  const [divider, setDivider] = useState(6);
  const [preset, setPreset] = useState<DividerPreset>("classic");
  const [chaseSpeed, setChaseSpeed] = useState(185);
  const [chaseIntensity, setChaseIntensity] = useState(190);

  // Apply saved defaults on load
  useEffect(() => {
    if (defaults) {
      if (defaults.league) setLeague(defaults.league);
      if (defaults.home) setHomeTeam(defaults.home);
      if (defaults.away) setAwayTeam(defaults.away);
      if (defaults.win_pct) setWinPct(defaults.win_pct);
    }
  }, [defaults]);

  // Load teams when league changes
  useEffect(() => {
    if (!league) {
      setTeams([]);
      return;
    }
    api.teams(league).then(setTeams).catch(() => setTeams([]));
  }, [league]);

  // Find team colors
  const homeColors = teams.find((t) => t.id === homeTeam)?.colors;
  const awayColors = teams.find((t) => t.id === awayTeam)?.colors;

  // Debounced send to WLED
  const debouncedSend = useDebounce(() => {
    if (!league || !homeTeam || !awayTeam) return;
    api.simTest({
      pct: winPct,
      league,
      home: homeTeam,
      away: awayTeam,
      host: null,
      settings: {
        min_team_pct: dignity / 100,
        dark_buffer_pixels: buffer,
        contested_zone_pixels: divider,
        divider_preset: preset,
        chase_speed: chaseSpeed,
        chase_intensity: chaseIntensity,
      },
    });
  }, 100);

  // Send data whenever relevant state changes
  useEffect(() => {
    debouncedSend();
  }, [winPct, dignity, buffer, divider, preset, chaseSpeed, chaseIntensity]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSetPct = useCallback((pct: number) => {
    setWinPct(pct);
  }, []);

  const handleStop = async () => {
    if (animationRef.current) {
      clearInterval(animationRef.current);
      animationRef.current = null;
    }
    setActiveScenario(null);
    for (const inst of instances.filter((i) => i.simulating)) {
      await api.simStop(inst.host);
    }
    onMutate();
  };

  const handleSave = () => {
    api.saveSimDefaults({ league, home: homeTeam, away: awayTeam, win_pct: winPct });
  };

  const handleToggleSim = async (host: string, active: boolean) => {
    if (active) {
      await api.simStop(host);
    } else {
      await api.simStart(host);
    }
    onMutate();
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (animationRef.current) clearInterval(animationRef.current);
    };
  }, []);

  const hasTeams = league && homeTeam && awayTeam;
  const hasSimulating = instances.some((i) => i.simulating) || activeScenario;

  const homeName = teams.find((t) => t.id === homeTeam)?.name ?? "Home";
  const awayName = teams.find((t) => t.id === awayTeam)?.name ?? "Away";

  return (
    <div className="space-y-3">
      {/* Target toggles */}
      <div className="flex flex-wrap gap-2">
        {instances.map((inst) => (
          <button
            key={inst.host}
            onClick={() => handleToggleSim(inst.host, inst.simulating)}
            className={`flex items-center gap-1.5 rounded border px-2 py-1 text-xs transition-colors ${
              inst.simulating
                ? "border-sim/40 bg-sim/10 text-sim"
                : "border-border bg-secondary text-muted-foreground"
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${
                inst.simulating ? "bg-sim" : "bg-muted-foreground/30"
              }`}
            />
            <span className="font-mono">{inst.host}</span>
            {inst.state.startsWith("watching") && (
              <span className="text-[9px] font-semibold text-live">LIVE</span>
            )}
          </button>
        ))}
      </div>

      {/* Team selection */}
      <div className="flex gap-1.5">
        <LeagueSelect
          leagues={leagues}
          value={league}
          onValueChange={(val) => {
            setLeague(val);
            setHomeTeam("");
            setAwayTeam("");
          }}
          className="flex-1"
        />

        <Select
          value={homeTeam}
          onValueChange={setHomeTeam}
          disabled={!league || teams.length === 0}
        >
          <SelectTrigger size="sm" className="h-8 flex-1 text-xs bg-secondary border-input">
            <SelectValue placeholder="Home..." />
          </SelectTrigger>
          <SelectContent>
            {teams.map((t) => (
              <SelectItem key={t.id} value={t.id}>
                <span className="flex items-center gap-2">
                  <TeamDot colors={t.colors} size={10} />
                  {t.name}
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={awayTeam}
          onValueChange={setAwayTeam}
          disabled={!league || teams.length === 0}
        >
          <SelectTrigger size="sm" className="h-8 flex-1 text-xs bg-secondary border-input">
            <SelectValue placeholder="Away..." />
          </SelectTrigger>
          <SelectContent>
            {teams.map((t) => (
              <SelectItem key={t.id} value={t.id}>
                <span className="flex items-center gap-2">
                  <TeamDot colors={t.colors} size={10} />
                  {t.name}
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Strip preview */}
      <StripPreview
        start={0}
        end={299}
        winPct={winPct / 100}
        minTeamPct={dignity / 100}
        contestedZonePixels={divider}
        darkBufferPixels={buffer}
        dividerPreset={preset}
        homeColors={homeColors}
        awayColors={awayColors}
      />

      {/* Win percentage slider */}
      <div>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{homeName}</span>
          <span className="font-mono font-semibold text-foreground">{winPct}%</span>
          <span>{awayName}</span>
        </div>
        <input
          type="range"
          className="mt-1 h-1.5 w-full cursor-pointer appearance-none rounded-full bg-secondary accent-primary"
          min={0}
          max={100}
          value={winPct}
          onChange={(e) => {
            if (activeScenario) {
              if (animationRef.current) clearInterval(animationRef.current);
              animationRef.current = null;
              setActiveScenario(null);
            }
            setWinPct(Number(e.target.value));
          }}
        />
      </div>

      {/* Scenario presets */}
      <ScenarioPresets
        onSetPct={handleSetPct}
        activeScenario={activeScenario}
        setActiveScenario={setActiveScenario}
        animationRef={animationRef}
      />

      {/* Stop / Save buttons */}
      <div className="flex justify-end gap-1.5">
        <Button
          variant="outline"
          size="xs"
          onClick={handleStop}
          disabled={!hasSimulating}
        >
          <Square className="h-3 w-3" />
          Stop
        </Button>
        <Button
          variant="outline"
          size="icon-xs"
          onClick={handleSave}
          disabled={!hasTeams}
          title="Save current settings as defaults"
        >
          <Save className="h-3 w-3" />
        </Button>
      </div>

      {/* Display settings */}
      <div>
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Display Settings
        </div>
        <div className="space-y-2">
          <SliderRow label="Min Dignity" value={dignity} min={1} max={20} format={(v) => `${v}%`} onChange={setDignity} />
          <SliderRow label="Buffer" value={buffer} min={0} max={20} format={(v) => `${v}px`} onChange={setBuffer} />
          <SliderRow label="Divider" value={divider} min={2} max={30} format={(v) => `${v}px`} onChange={setDivider} />
          <div className="flex items-center gap-3">
            <span className="w-24 shrink-0 text-[11px] text-muted-foreground">Style</span>
            <Select
              value={preset}
              onValueChange={(val) => setPreset(val as DividerPreset)}
            >
              <SelectTrigger size="sm" className="h-7 flex-1 text-[11px] bg-secondary border-input">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(DIVIDER_PRESETS).map(([key, { label }]) => (
                  <SelectItem key={key} value={key}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <span className="w-12" />
          </div>
          <SliderRow label="Chase Speed" value={chaseSpeed} min={50} max={255} onChange={setChaseSpeed} />
          <SliderRow label="Intensity" value={chaseIntensity} min={50} max={255} onChange={setChaseIntensity} />
        </div>
      </div>

      <div className="text-[11px] text-muted-foreground">
        Toggle instances, pick teams, adjust settings. Changes apply instantly to targeted strips.
      </div>
    </div>
  );
}

function SliderRow({
  label,
  value,
  min,
  max,
  format,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  format?: (v: number) => string;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-24 shrink-0 text-[11px] text-muted-foreground">{label}</span>
      <input
        type="range"
        className="h-1.5 flex-1 cursor-pointer appearance-none rounded-full bg-secondary accent-primary"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <span className="w-12 text-right font-mono text-[11px] text-muted-foreground">
        {format ? format(value) : value}
      </span>
    </div>
  );
}

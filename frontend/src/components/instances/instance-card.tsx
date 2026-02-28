import { useState } from "react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import type { Instance, League, UIState } from "@/lib/types";
import { HealthBadge } from "./health-badge";
import { StateBadge } from "./state-badge";
import { Scoreboard } from "./scoreboard";
import { GameSelector } from "./game-selector";
import { StripPreview } from "./strip-preview";
import { Pencil, ChevronDown, ChevronUp, Trash2, RotateCcw, Square, X } from "lucide-react";
import { DisplaySliders } from "./display-sliders";
import { WatchTeams } from "./watch-teams";
import { PostGameConfig } from "./post-game-config";
import { Button } from "@/components/ui/button";

interface InstanceCardProps {
  instance: Instance;
  leagues: League[];
  onMutate: () => void;
}

const cardStyles: Record<UIState, string> = {
  idle: "border-border bg-card",
  idle_autowatch: "border-armed/20 bg-armed/5",
  watching_auto: "border-auto/25 bg-auto/5",
  watching_manual: "border-live/25 bg-live/5",
  watching_override: "border-override/25 bg-override/5",
  final: "border-final-state/25 bg-muted",
  simulating: "border-sim/25 bg-sim/5",
};

export function InstanceCard({ instance: inst, leagues, onMutate }: InstanceCardProps) {
  const [settingsExpanded, setSettingsExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editHost, setEditHost] = useState(inst.host);
  const [editStart, setEditStart] = useState(inst.start);
  const [editEnd, setEditEnd] = useState(inst.end);

  const hasDisplay = !!inst.home_team;
  const isFinal = inst.state === "final";
  const isAutoWatch = inst.state === "idle_autowatch";
  const totalPixels = inst.end - inst.start + 1;

  const handleWatch = async (league: string, gameId: string) => {
    await api.watch(inst.host, league, gameId);
    onMutate();
  };

  const handleStop = async () => {
    await api.stop(inst.host);
    onMutate();
  };

  const handleSaveEdit = async () => {
    await api.editInstance(inst.host, {
      host: editHost,
      start: editStart,
      end: editEnd,
    });
    setEditing(false);
    onMutate();
  };

  const previewPct =
    hasDisplay && inst.home_win_pct !== undefined ? inst.home_win_pct : 0.5;

  return (
    <div
      className={cn(
        "rounded-lg border p-3 transition-colors",
        cardStyles[inst.state] || cardStyles.idle,
      )}
    >
      {/* Header row */}
      <div className="mb-2 flex items-center justify-between">
        <span className="flex items-center gap-2">
          <strong className="font-mono text-sm">{inst.host}</strong>
          <span className="text-xs text-muted-foreground">
            [{inst.start}-{inst.end}] {totalPixels}px
          </span>
        </span>
        <span className="flex items-center gap-1.5">
          <HealthBadge health={inst.health} />
          <StateBadge
            state={inst.state}
            simulating={inst.simulating}
            watchTeams={inst.watch_teams}
            finalLingerRemaining={inst.final_linger_remaining}
          />
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={() => {
              setEditing(!editing);
              setEditHost(inst.host);
              setEditStart(inst.start);
              setEditEnd(inst.end);
            }}
            title="Edit"
          >
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={() => setSettingsExpanded(!settingsExpanded)}
            title="Settings"
          >
            {settingsExpanded ? (
              <ChevronUp className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
          </Button>
        </span>
      </div>

      {/* Inline edit form */}
      {editing && (
        <div className="mb-2 rounded border border-primary/30 bg-primary/5 p-2">
          <div className="mb-2 text-[11px] font-semibold text-primary">
            Edit Instance
          </div>
          <div className="mb-2 flex gap-2">
            <input
              type="text"
              value={editHost}
              onChange={(e) => setEditHost(e.target.value)}
              placeholder="IP / Hostname"
              className="flex-[2] rounded border border-input bg-secondary px-2 py-1 text-xs text-foreground"
            />
            <input
              type="number"
              value={editStart}
              onChange={(e) => setEditStart(Number(e.target.value))}
              placeholder="Start"
              className="w-20 rounded border border-input bg-secondary px-2 py-1 text-xs text-foreground"
            />
            <input
              type="number"
              value={editEnd}
              onChange={(e) => setEditEnd(Number(e.target.value))}
              placeholder="End"
              className="w-20 rounded border border-input bg-secondary px-2 py-1 text-xs text-foreground"
            />
          </div>
          <div className="flex gap-2">
            <Button size="xs" onClick={handleSaveEdit}>
              Save
            </Button>
            <Button variant="outline" size="xs" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* Auto-watch armed notice */}
      {isAutoWatch && !hasDisplay && inst.watch_teams.length > 0 && (
        <div className="mb-2 rounded border border-armed/20 bg-armed/10 px-2 py-1.5 text-[11px] text-armed">
          <strong className="mr-1.5">◉ Watching for:</strong>
          {inst.watch_teams.map((t) => (
            <span
              key={t}
              className="mr-1 inline-flex items-center gap-0.5 rounded bg-armed/15 px-1.5 py-0.5"
            >
              {t.split(":")[1] || t}
              <button
                onClick={async () => {
                  await api.setWatchTeams(
                    inst.host,
                    inst.watch_teams.filter((wt) => wt !== t),
                  );
                  onMutate();
                }}
                className="ml-0.5 rounded-full p-0.5 hover:bg-armed/30 transition-colors"
                title={`Remove ${t.split(":")[1] || t}`}
              >
                <X className="h-2.5 w-2.5" />
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Scoreboard — renders whenever there's display data */}
      {hasDisplay && <Scoreboard instance={inst} />}

      {/* Strip preview */}
      {hasDisplay && (
        <div className="mb-2">
          <StripPreview
            start={inst.start}
            end={inst.end}
            winPct={previewPct}
            minTeamPct={inst.min_team_pct}
            contestedZonePixels={inst.contested_zone_pixels}
            darkBufferPixels={inst.dark_buffer_pixels}
            dividerPreset={inst.divider_preset}
            homeColors={inst.home_colors}
            awayColors={inst.away_colors}
          />
        </div>
      )}

      {/* Game selector — always visible unless FINAL */}
      {!isFinal && (
        <GameSelector
          instance={inst}
          leagues={leagues}
          onWatch={handleWatch}
        />
      )}

      {/* Stop / Resume button */}
      {inst.state === "watching_override" && (
        <Button size="xs" className="bg-armed hover:bg-armed/90" onClick={handleStop}>
          <RotateCcw className="h-3 w-3" />
          Resume Auto-Watch
        </Button>
      )}
      {(inst.state === "watching_auto" || inst.state === "watching_manual") && (
        <Button variant="destructive" size="xs" onClick={handleStop}>
          <Square className="h-3 w-3" />
          Stop
        </Button>
      )}

      {/* Settings panel */}
      {settingsExpanded && (
        <div className="mt-3 border-t border-border pt-3 space-y-4">
          {/* Watch teams */}
          <WatchTeams instance={inst} leagues={leagues} onMutate={onMutate} />

          {/* Strip preview */}
          <div>
            <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Strip Preview
            </div>
            <StripPreview
              start={inst.start}
              end={inst.end}
              winPct={previewPct}
              minTeamPct={inst.min_team_pct}
              contestedZonePixels={inst.contested_zone_pixels}
              darkBufferPixels={inst.dark_buffer_pixels}
              dividerPreset={inst.divider_preset}
              homeColors={inst.home_colors}
              awayColors={inst.away_colors}
            />
          </div>

          {/* Display settings */}
          <div>
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Display Settings
            </div>
            <DisplaySliders instance={inst} />
          </div>

          {/* Post-game config */}
          <PostGameConfig instance={inst} />

          {/* Remove instance */}
          <div className="pt-2 border-t border-border">
            <Button
              variant="ghost"
              size="xs"
              className="text-destructive hover:bg-destructive/10 hover:text-destructive"
              onClick={async () => {
                if (confirm(`Remove ${inst.host}?`)) {
                  await api.removeInstance(inst.host);
                  onMutate();
                }
              }}
            >
              <Trash2 className="h-3 w-3" />
              Remove instance
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

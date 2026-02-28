import { useCallback } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { DisplaySettings } from "@/lib/types";

interface ScenarioPresetsProps {
  onSetPct: (pct: number) => void;
  activeScenario: string | null;
  setActiveScenario: (name: string | null) => void;
  animationRef: React.RefObject<ReturnType<typeof setInterval> | null>;
  demoContext?: {
    league: string;
    home: string;
    away: string;
    settings: DisplaySettings;
  };
}

export function ScenarioPresets({
  onSetPct,
  activeScenario,
  setActiveScenario,
  animationRef,
  demoContext,
}: ScenarioPresetsProps) {
  const clearAnim = useCallback(() => {
    if (animationRef.current) {
      clearInterval(animationRef.current);
      animationRef.current = null;
    }
    setActiveScenario(null);
  }, [animationRef, setActiveScenario]);

  const startAnim = useCallback(
    (name: string) => {
      clearAnim();
      setActiveScenario(name);
    },
    [clearAnim, setActiveScenario],
  );

  const playStatic = (pct: number) => {
    clearAnim();
    onSetPct(pct);
  };

  const playComeback = () => {
    startAnim("comeback");
    let pct = 15;
    onSetPct(pct);
    animationRef.current = setInterval(() => {
      pct += 2;
      if (pct >= 85) {
        clearAnim();
        pct = 85;
      }
      onSetPct(pct);
    }, 300);
  };

  const playCollapse = () => {
    startAnim("collapse");
    let pct = 85;
    onSetPct(pct);
    animationRef.current = setInterval(() => {
      pct -= 2;
      if (pct <= 15) {
        clearAnim();
        pct = 15;
      }
      onSetPct(pct);
    }, 300);
  };

  const playOvertime = () => {
    startAnim("overtime");
    onSetPct(50);
    animationRef.current = setInterval(() => {
      const jitter = (Math.random() - 0.5) * 8;
      const pct = Math.max(42, Math.min(58, 50 + jitter));
      onSetPct(Math.round(pct));
    }, 150);
  };

  const playMomentum = () => {
    startAnim("momentum");
    let pct = 50;
    let direction = 1;
    onSetPct(pct);
    animationRef.current = setInterval(() => {
      pct += direction * 3;
      if (pct >= 80) direction = -1;
      if (pct <= 20) direction = 1;
      onSetPct(Math.round(pct));
    }, 200);
  };

  const playBuzzerBeater = () => {
    startAnim("buzzer");
    let pct = 25;
    let phase: "creep" | "pause" | "win" = "creep";
    onSetPct(pct);
    animationRef.current = setInterval(() => {
      if (phase === "creep") {
        pct += 0.8;
        if (pct >= 48) {
          phase = "pause";
          setTimeout(() => {
            phase = "win";
          }, 800);
        }
      } else if (phase === "win") {
        pct += 8;
        if (pct >= 88) {
          clearAnim();
          pct = 88;
        }
      }
      onSetPct(Math.round(pct));
    }, 250);
  };

  // Scripted demo game — realistic NBA game, ~40 seconds
  const playDemo = () => {
    if (!demoContext) return;
    startAnim("demo");
    const { league, home, away, settings } = demoContext;

    // Each tick: [homePts, awayPts, winPct, period]
    const script: [number, number, number, string][] = [
      // Q1 — away jumps out early
      [0, 0, 50, "Q1 12:00"], [3, 0, 54, "Q1 10:30"], [3, 7, 44, "Q1 9:15"],
      [5, 7, 46, "Q1 8:00"], [5, 10, 41, "Q1 6:40"], [8, 10, 45, "Q1 5:20"],
      [8, 15, 37, "Q1 3:50"], [11, 15, 41, "Q1 2:30"], [14, 18, 40, "Q1 1:00"],
      [17, 22, 39, "End Q1"],
      // Q2 — home rallies, takes lead at half
      [20, 22, 44, "Q2 10:30"], [23, 24, 47, "Q2 9:00"], [26, 24, 53, "Q2 7:30"],
      [29, 27, 54, "Q2 6:00"], [32, 30, 53, "Q2 4:30"], [35, 30, 58, "Q2 3:15"],
      [38, 33, 57, "Q2 2:00"], [41, 36, 57, "Q2 0:45"], [44, 38, 59, "HALF"],
      // Q3 — back and forth, away surges
      [44, 41, 54, "Q3 10:00"], [47, 44, 54, "Q3 8:30"], [47, 49, 46, "Q3 7:00"],
      [50, 52, 46, "Q3 5:30"], [50, 57, 38, "Q3 4:00"], [53, 57, 42, "Q3 3:00"],
      [56, 60, 41, "Q3 1:30"], [59, 63, 40, "End Q3"],
      // Q4 — home comeback, clutch finish
      [62, 63, 47, "Q4 10:00"], [65, 65, 50, "Q4 8:30"], [68, 67, 53, "Q4 7:00"],
      [68, 70, 45, "Q4 5:30"], [71, 70, 54, "Q4 4:30"], [74, 73, 53, "Q4 3:30"],
      [74, 76, 42, "Q4 2:30"], [77, 76, 55, "Q4 1:45"], [77, 79, 40, "Q4 1:00"],
      [80, 79, 58, "Q4 0:30"], [80, 79, 62, "Q4 0:15"], [82, 79, 72, "Q4 0:05"],
      [82, 79, 85, "FINAL"],
    ];

    let i = 0;
    onSetPct(50);
    const tick = () => {
      if (i >= script.length) {
        clearAnim();
        return;
      }
      const [hp, ap, pct, period] = script[i];
      onSetPct(pct);
      api.simTest({
        pct, league, home, away, host: null, settings,
        home_score: hp, away_score: ap, period,
      });
      i++;
    };
    tick();
    animationRef.current = setInterval(tick, 1100);
  };

  const active = (name: string) =>
    activeScenario === name ? "border-primary text-primary" : "";

  return (
    <div className="grid grid-cols-4 gap-1.5">
      <Button variant="outline" size="xs" className="text-[11px]" onClick={() => playStatic(50)}>
        Nail-biter
      </Button>
      <Button variant="outline" size="xs" className="text-[11px]" onClick={() => playStatic(80)}>
        Dominant
      </Button>
      <Button variant="outline" size="xs" className="text-[11px]" onClick={() => playStatic(95)}>
        Blowout
      </Button>
      <Button variant="outline" size="xs" className={cn("text-[11px]", active("comeback"))} onClick={playComeback}>
        Comeback
      </Button>
      <Button variant="outline" size="xs" className={cn("text-[11px]", active("collapse"))} onClick={playCollapse}>
        Collapse
      </Button>
      <Button variant="outline" size="xs" className={cn("text-[11px]", active("overtime"))} onClick={playOvertime}>
        Overtime
      </Button>
      <Button variant="outline" size="xs" className={cn("text-[11px]", active("momentum"))} onClick={playMomentum}>
        Momentum
      </Button>
      <Button variant="outline" size="xs" className={cn("text-[11px]", active("buzzer"))} onClick={playBuzzerBeater}>
        Buzzer
      </Button>
      <Button
        variant="outline"
        size="xs"
        className={cn("text-[11px] col-span-4", active("demo"), demoContext ? "border-live/40 text-live" : "")}
        onClick={playDemo}
        disabled={!demoContext}
      >
        Demo Game
      </Button>
    </div>
  );
}

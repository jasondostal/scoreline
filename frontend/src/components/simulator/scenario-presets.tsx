import { useCallback } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface ScenarioPresetsProps {
  onSetPct: (pct: number) => void;
  activeScenario: string | null;
  setActiveScenario: (name: string | null) => void;
  animationRef: React.RefObject<ReturnType<typeof setInterval> | null>;
}

export function ScenarioPresets({
  onSetPct,
  activeScenario,
  setActiveScenario,
  animationRef,
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
    </div>
  );
}

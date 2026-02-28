import {
  Shield,
  CircleDot,
  Diamond,
  Hexagon,
  Goal,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export const SPORT_ICONS: Record<string, LucideIcon> = {
  football: Shield,     // NFL — combative, defensive
  basketball: CircleDot, // NBA — ball shape
  baseball: Diamond,     // MLB — the diamond
  hockey: Hexagon,       // NHL — puck shape
  soccer: Goal,          // MLS — goal net
};

export function getSportIcon(sport: string): LucideIcon {
  return SPORT_ICONS[sport] ?? CircleDot;
}

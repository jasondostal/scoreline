export type UIState =
  | "idle"
  | "idle_autowatch"
  | "watching_auto"
  | "watching_manual"
  | "watching_override"
  | "final"
  | "simulating";

export type HealthStatus = "healthy" | "stale" | "unreachable";
export type GamePhase = "pre" | "in" | "post";
export type CelebrationType = "freeze" | "chase" | "twinkle" | "flash" | "solid";
export type AfterAction = "fade_off" | "off" | "restore" | "preset";
export type DividerPreset = "classic" | "intense" | "ice" | "pulse" | "chaos";

export interface HealthInfo {
  status: HealthStatus;
  last_success: number;
  consecutive_failures: number;
  last_error: string | null;
}

export interface Instance {
  host: string;
  start: number;
  end: number;
  simulating: boolean;
  watch_teams: string[];
  state: UIState;
  game_phase: GamePhase | null;
  health: HealthInfo;
  final_linger_remaining: number | null;
  // Display settings
  min_team_pct: number;
  contested_zone_pixels: number;
  dark_buffer_pixels: number;
  chase_speed: number;
  chase_intensity: number;
  divider_preset: DividerPreset;
  // Post-game
  post_game_celebration: CelebrationType;
  post_game_duration: number;
  post_game_after_action: AfterAction;
  post_game_preset_id: number | null;
  celebration_remaining: number | null;
  // Game data (present when watching/final)
  league?: string;
  game_id?: string;
  home_team?: string;
  away_team?: string;
  home_display?: string;
  away_display?: string;
  home_colors?: number[][];
  away_colors?: number[][];
  home_score?: number;
  away_score?: number;
  home_win_pct?: number;
  period?: string;
  status?: string;
  win_pct_history?: { t: number; pct: number }[];
}

export interface League {
  id: string;
  name: string;
  sport: string;
}

export interface Game {
  id: string;
  name: string;
  status: string;
  detail: string;
  home_team: string;
  away_team: string;
  home_display: string;
  away_display: string;
  home_colors?: number[][];
  away_colors?: number[][];
  home_score: number;
  away_score: number;
}

export interface Team {
  id: string;
  name: string;
  colors: number[][];
}

export interface DiscoveredDevice {
  name: string;
  ip: string;
  host: string;
  mac: string;
  configured: boolean;
}

export interface DisplaySettings {
  min_team_pct: number;
  contested_zone_pixels: number;
  dark_buffer_pixels: number;
  divider_preset: DividerPreset;
  chase_speed: number;
  chase_intensity: number;
}

export interface PostGameConfig {
  celebration: CelebrationType;
  celebration_duration_s: number;
  after_action: AfterAction;
  preset_id: number | null;
}

export interface SimTestPayload {
  pct: number;
  league: string;
  home: string;
  away: string;
  host: string | null;
  settings: DisplaySettings;
  home_score?: number;
  away_score?: number;
  period?: string;
}

export interface SimulatorDefaults {
  league: string;
  home: string;
  away: string;
  win_pct: number;
}

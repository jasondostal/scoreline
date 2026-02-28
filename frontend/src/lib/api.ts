import { toast } from "sonner";
import type {
  Instance,
  League,
  Game,
  Team,
  DiscoveredDevice,
  DisplaySettings,
  PostGameConfig,
  SimTestPayload,
  SimulatorDefaults,
} from "./types";

// ---------------------------------------------------------------------------
// GET cache: deduplicates in-flight requests and caches responses with TTL.
// Mutations (POST/PATCH/DELETE) invalidate matching cache entries.
// Adapted from Cairn's api.ts pattern.
// ---------------------------------------------------------------------------

const BASE = "/api";

interface CacheEntry {
  data: unknown;
  timestamp: number;
}

const _cache = new Map<string, CacheEntry>();
const _inflight = new Map<string, Promise<unknown>>();

function buildUrl(path: string): string {
  return `${BASE}${path}`;
}

export function invalidateCache(pathPrefix?: string) {
  if (!pathPrefix) {
    _cache.clear();
    return;
  }
  const prefix = `${BASE}${pathPrefix}`;
  for (const key of _cache.keys()) {
    if (key.startsWith(prefix)) _cache.delete(key);
  }
}

async function get<T>(path: string): Promise<T> {
  const key = buildUrl(path);

  const existing = _inflight.get(key);
  if (existing) return existing as Promise<T>;

  const doFetch = async (): Promise<T> => {
    const res = await fetch(key);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const data = await res.json();
    _cache.set(key, { data, timestamp: Date.now() });
    return data;
  };

  const promise = doFetch().finally(() => _inflight.delete(key));
  _inflight.set(key, promise);
  return promise;
}

async function post<T>(path: string, body: unknown, silent = false): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const msg = err.detail || `${res.status} ${res.statusText}`;
    if (!silent) toast.error(msg);
    throw new Error(msg);
  }
  invalidateCache("/instances");
  return res.json();
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const msg = err.detail || `${res.status} ${res.statusText}`;
    toast.error(msg);
    throw new Error(msg);
  }
  invalidateCache("/instances");
  return res.json();
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const msg = err.detail || `${res.status} ${res.statusText}`;
    toast.error(msg);
    throw new Error(msg);
  }
  invalidateCache("/instances");
  return res.json();
}

// ---------------------------------------------------------------------------
// Named API methods
// ---------------------------------------------------------------------------

export const api = {
  // Data fetching
  leagues: () => get<League[]>("/leagues"),
  games: (league: string) => get<Game[]>(`/games/${league}`),
  teams: (league: string) => get<Team[]>(`/teams/${league}`),
  instances: () => get<Instance[]>("/instances"),
  discover: () => get<DiscoveredDevice[]>("/discover"),
  simulatorDefaults: () => get<SimulatorDefaults>("/simulator"),

  // Instance actions
  watch: (host: string, league: string, gameId: string) =>
    post<unknown>(`/instance/${host}/watch`, { league, game_id: gameId }).then((r) => { toast.success("Watching game"); return r; }),
  stop: (host: string) =>
    post<unknown>(`/instance/${host}/stop`, {}).then((r) => { toast.success("Stopped"); return r; }),
  updateSettings: (host: string, settings: Partial<DisplaySettings>) =>
    post<unknown>(`/instance/${host}/settings`, settings, true),
  setWatchTeams: (host: string, teams: string[]) =>
    post<unknown>(`/instance/${host}/watch_teams`, { watch_teams: teams }).then((r) => { toast.success("Watch teams updated"); return r; }),
  updatePostGame: (host: string, config: PostGameConfig) =>
    post<unknown>(`/instance/${host}/post_game`, config, true),
  editInstance: (host: string, data: { host?: string; start?: number; end?: number }) =>
    patch<unknown>(`/instance/${host}`, data).then((r) => { toast.success("Instance updated"); return r; }),
  removeInstance: (host: string) =>
    del<unknown>(`/instance/${host}`).then((r) => { toast.success("Instance removed"); return r; }),

  // Simulator
  simStart: (host: string) =>
    post<unknown>(`/instance/${host}/sim/start`, {}).then((r) => { toast.success("Sim started"); return r; }),
  simStop: (host: string) =>
    post<unknown>(`/instance/${host}/sim/stop`, {}).then((r) => { toast.success("Sim stopped"); return r; }),
  simTest: (data: SimTestPayload) =>
    post<unknown>("/test", data, true),
  saveSimDefaults: (data: SimulatorDefaults) =>
    post<unknown>("/simulator", data).then((r) => { toast.success("Defaults saved"); return r; }),

  // Device management
  addDevice: (host: string, start: number, end: number) =>
    post<unknown>("/wled/add", { host, start, end }).then((r) => { toast.success("Device added"); return r; }),
  reload: () =>
    post<unknown>("/reload", {}).then((r) => { toast.success("Config reloaded"); return r; }),
};

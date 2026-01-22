"""
Game Lights - Live ESPN win probability → WLED visualization.

FastAPI app with game picker UI and background polling.
"""

import asyncio
import logging
import os
import threading
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger("uvicorn.error")

from espn import ESPNClient, GameInfo
from wled import WLEDController, WLEDConfig
from teams import get_team_colors, get_team_display
from config import (
    get_settings, get_leagues, reload_config, add_wled_instance, remove_wled_instance,
    CONFIG_DIR, get_instance_display_settings, get_all_watched_teams,
    get_instance_watch_teams, update_instance_watch_teams,
    get_instance_post_game_settings, update_instance_post_game_settings,
    get_simulator_defaults, update_simulator_defaults,
)
from discovery import discover_wled_devices


def build_wled_config(host: str, start: int, end: int) -> WLEDConfig:
    """Build WLEDConfig with display settings from config file (per-instance or global)."""
    display = get_instance_display_settings(host)
    return WLEDConfig(
        host=host,
        roofline_start=start,
        roofline_end=end,
        min_team_pct=display.get("min_team_pct", 0.05),
        contested_zone_pixels=display.get("contested_zone_pixels", 6),
        dark_buffer_pixels=display.get("dark_buffer_pixels", 4),
        transition_ms=display.get("transition_ms", 500),
        chase_speed=display.get("chase_speed", 185),
        chase_intensity=display.get("chase_intensity", 190),
        divider_color=display.get("divider_color", [200, 80, 0]),
        divider_preset=display.get("divider_preset", "classic"),
    )


# App state - per-instance game tracking
class InstanceState:
    """State for a single WLED instance."""
    def __init__(self, host: str, start: int, end: int):
        self.host = host
        self.start = start
        self.end = end
        self.controller: Optional[WLEDController] = None
        self.game: Optional[dict] = None  # {league, game_id, last_info, last_status}
        self.previous_preset: Optional[int] = None  # Preset to restore after game
        self.simulating: bool = False  # True when driven by simulator
        self.sim_saved_preset: Optional[int] = None  # Preset to restore when sim stops


class AppState:
    espn: Optional[ESPNClient] = None
    instances: dict[str, InstanceState] = {}  # host -> InstanceState
    poll_task: Optional[asyncio.Task] = None
    auto_watch_task: Optional[asyncio.Task] = None


state = AppState()


def init_instances():
    """Initialize WLED instances from config."""
    settings = get_settings()
    state.instances = {}
    for inst in settings.get("wled_instances", []):
        host = inst["host"]
        state.instances[host] = InstanceState(
            host=host,
            start=inst.get("start", 0),
            end=inst.get("end", 629),
        )


# Config file watcher for auto-reload
class ConfigWatcher(FileSystemEventHandler):
    """Watch config directory for changes and auto-reload."""
    def __init__(self):
        self._debounce_timer = None
        self._lock = threading.Lock()

    def on_modified(self, event):
        if event.is_directory:
            return
        # Only watch settings.yaml and league files
        if event.src_path.endswith('.yaml') or event.src_path.endswith('.yml'):
            self._schedule_reload()

    def on_created(self, event):
        if not event.is_directory and (event.src_path.endswith('.yaml') or event.src_path.endswith('.yml')):
            self._schedule_reload()

    def _schedule_reload(self):
        """Debounce reloads - wait 1 second after last change."""
        with self._lock:
            if self._debounce_timer:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(1.0, self._do_reload)
            self._debounce_timer.start()

    def _do_reload(self):
        logger.info("Config changed, reloading...")
        reload_config()
        init_instances()
        logger.info(f"Reloaded: {len(state.instances)} instance(s)")


config_observer: Optional[PollingObserver] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global config_observer
    # Startup
    state.espn = ESPNClient()
    init_instances()
    # Start the unified poll task
    state.poll_task = asyncio.create_task(poll_all_games())
    # Start auto-watch task (scans for watched teams' games)
    state.auto_watch_task = asyncio.create_task(auto_watch_all())
    # Start config file watcher (polling for Docker compatibility)
    config_observer = PollingObserver(timeout=5)
    config_observer.schedule(ConfigWatcher(), CONFIG_DIR, recursive=True)
    config_observer.start()
    logger.info(f"Watching {CONFIG_DIR} for config changes (polling every 5s)")
    yield
    # Shutdown
    if config_observer:
        config_observer.stop()
        config_observer.join()
    if state.poll_task:
        state.poll_task.cancel()
    if state.auto_watch_task:
        state.auto_watch_task.cancel()
    if state.espn:
        await state.espn.close()
    for inst in state.instances.values():
        if inst.controller:
            await inst.controller.close()


app = FastAPI(title="Game Lights", lifespan=lifespan)


# Request/Response models
class WLEDInstance(BaseModel):
    host: str
    start: int = 0
    end: int = 629


class GameStatus(BaseModel):
    watching: bool
    game_id: Optional[str] = None
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    home_win_pct: Optional[float] = None
    period: Optional[str] = None
    last_update: Optional[str] = None


# Background polling
async def poll_all_games():
    """Background task to poll ESPN and update each WLED instance with its game."""
    while True:
        try:
            if state.espn:
                # Collect unique games to poll (avoid duplicate API calls)
                games_to_poll: dict[str, list[InstanceState]] = {}  # game_key -> instances
                for inst in state.instances.values():
                    if inst.game and inst.controller:
                        key = f"{inst.game['league']}:{inst.game['game_id']}"
                        if key not in games_to_poll:
                            games_to_poll[key] = []
                        games_to_poll[key].append(inst)

                # Poll each unique game and update its instances
                for game_key, instances in games_to_poll.items():
                    league, game_id = game_key.split(":", 1)
                    sport = get_leagues().get(league, {}).get("sport", "football")

                    game = await state.espn.get_game_detail(sport, league, game_id)

                    if game:
                        home_colors = get_team_colors(league, game.home_team)
                        away_colors = get_team_colors(league, game.away_team)

                        for inst in instances:
                            # Check for game end (status transition to "post")
                            last_status = inst.game.get("last_status")
                            if game.status == "post" and last_status != "post":
                                # Game just ended - trigger post-game action
                                asyncio.create_task(handle_game_ended(inst, game))
                                continue  # Don't update lights, handler will manage it

                            # Update status tracking
                            inst.game["last_status"] = game.status
                            inst.game["last_info"] = game

                            # Only update lights for in-progress games
                            if game.status == "in":
                                await inst.controller.set_game_mode(
                                    home_win_pct=game.home_win_pct,
                                    home_colors=home_colors,
                                    away_colors=away_colors,
                                )

                        # Log for in-progress games
                        active_instances = [i for i in instances if i.game and i.game.get("last_status") == "in"]
                        if active_instances:
                            logger.info(f"[{league.upper()}] {game.away_team} @ {game.home_team} | "
                                        f"{game.away_score}-{game.home_score} | "
                                        f"Home: {game.home_win_pct:.1%} | "
                                        f"{len(active_instances)} instance(s)")

        except Exception as e:
            logger.error(f"Poll error: {e}")

        await asyncio.sleep(30)  # Poll every 30 seconds


async def auto_watch_all():
    """
    Background task to auto-start games for watched teams.
    Scans scoreboards for leagues with watched teams, auto-starts in-progress games.
    """
    settings = get_settings()
    interval = settings.get("auto_watch_interval", 300)

    while True:
        try:
            watched = get_all_watched_teams()  # {league: [(team, host), ...]}

            if not watched:
                await asyncio.sleep(interval)
                continue

            for league, team_hosts in watched.items():
                if league not in get_leagues():
                    continue

                sport = get_leagues()[league]["sport"]
                games = await state.espn.get_scoreboard(sport, league)

                for game in games:
                    # Only auto-watch in-progress games
                    if game["status"] != "in":
                        continue

                    home_team = game["home_team"].upper()
                    away_team = game["away_team"].upper()

                    # Find instances watching either team
                    for team, host in team_hosts:
                        if team != home_team and team != away_team:
                            continue

                        inst = state.instances.get(host)
                        if not inst:
                            continue

                        # Skip if already watching something
                        if inst.game is not None:
                            continue

                        # Auto-start!
                        logger.info(f"[AUTO-WATCH] {host}: Starting {away_team}@{home_team} ({league.upper()})")

                        if not inst.controller:
                            config = build_wled_config(inst.host, inst.start, inst.end)
                            inst.controller = WLEDController(config)

                        # Save current preset before we take over (for restore action)
                        inst.previous_preset = await inst.controller.get_current_preset()
                        logger.info(f"[AUTO-WATCH] {host}: Saved previous preset {inst.previous_preset}")

                        inst.game = {
                            "league": league,
                            "game_id": game["id"],
                            "last_info": None,
                            "last_status": "in",  # Auto-watch only starts in-progress games
                        }

        except Exception as e:
            logger.error(f"Auto-watch error: {e}")

        await asyncio.sleep(interval)


async def handle_game_ended(inst: InstanceState, game_info: GameInfo):
    """
    Handle post-game actions when a game ends.

    Args:
        inst: The WLED instance that was watching
        game_info: Final game state
    """
    if not inst.controller:
        return

    league = inst.game["league"]
    post_game = get_instance_post_game_settings(inst.host)
    action = post_game.get("action", "flash_then_off")

    # Determine winner colors
    if game_info.home_score > game_info.away_score:
        winner = game_info.home_team
        winner_colors = get_team_colors(league, game_info.home_team)
    elif game_info.away_score > game_info.home_score:
        winner = game_info.away_team
        winner_colors = get_team_colors(league, game_info.away_team)
    else:
        # Tie - use home team colors (rare in most sports)
        winner = "TIE"
        winner_colors = get_team_colors(league, game_info.home_team)

    logger.info(f"[POST-GAME] {inst.host}: {game_info.away_team} @ {game_info.home_team} "
                f"Final: {game_info.away_score}-{game_info.home_score} | "
                f"Winner: {winner} | Action: {action}")

    try:
        if action == "off":
            await inst.controller.turn_off()

        elif action == "fade_off":
            fade_s = post_game.get("fade_duration_s", 3)
            await inst.controller.fade_off(duration_s=fade_s)

        elif action == "flash_then_off":
            flash_count = post_game.get("flash_count", 3)
            flash_ms = post_game.get("flash_duration_ms", 500)
            fade_s = post_game.get("fade_duration_s", 3)

            await inst.controller.flash_colors(
                colors=winner_colors,
                count=flash_count,
                flash_duration_ms=flash_ms,
            )
            # Brief pause then fade
            await asyncio.sleep(0.5)
            await inst.controller.fade_off(duration_s=fade_s)

        elif action == "restore":
            # Restore the preset that was active before the game started
            if inst.previous_preset is not None:
                logger.info(f"[POST-GAME] {inst.host}: Restoring preset {inst.previous_preset}")
                await inst.controller.restore_preset(inst.previous_preset)
            else:
                # No previous preset, just turn off
                logger.info(f"[POST-GAME] {inst.host}: No previous preset, turning off")
                await inst.controller.turn_off()

        elif action == "preset":
            # Switch to a specific configured preset
            preset_id = post_game.get("preset_id")
            if preset_id is not None:
                logger.info(f"[POST-GAME] {inst.host}: Switching to preset {preset_id}")
                await inst.controller.restore_preset(preset_id)
            else:
                logger.warning(f"[POST-GAME] {inst.host}: Action is 'preset' but no preset_id configured, turning off")
                await inst.controller.turn_off()

    except Exception as e:
        logger.error(f"[POST-GAME] Error on {inst.host}: {e}")

    # Clear the game state and previous preset
    inst.game = None
    inst.previous_preset = None


# API Routes
@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse("static/index.html")


@app.get("/api/leagues")
async def list_leagues():
    """Get available leagues."""
    leagues = get_leagues()
    return [
        {"id": k, "name": v["name"], "sport": v["sport"]}
        for k, v in leagues.items()
    ]


@app.get("/api/settings")
async def api_get_settings():
    """Get WLED instances and other settings from YAML config."""
    return get_settings()


@app.post("/api/reload")
async def api_reload_config():
    """Hot-reload config from disk and reinitialize instances."""
    # Close existing controllers
    for inst in state.instances.values():
        if inst.controller:
            await inst.controller.close()

    result = reload_config()
    init_instances()
    return {"status": "reloaded", "instances": len(state.instances), **result}


@app.get("/api/discover")
async def api_discover_wled():
    """Discover WLED devices on the local network via mDNS."""
    devices = await discover_wled_devices(timeout=3.0)

    # Check which devices are already configured
    configured_hosts = {
        inst.get("host") for inst in get_settings().get("wled_instances", [])
    }

    return [
        {
            "name": d.name,
            "ip": d.ip,
            "host": d.host,
            "mac": d.mac,
            "configured": d.ip in configured_hosts or d.host in configured_hosts,
        }
        for d in devices
    ]


class AddWLEDRequest(BaseModel):
    host: str
    start: int = 0
    end: int = 300


@app.post("/api/wled/add")
async def api_add_wled(req: AddWLEDRequest):
    """Add a WLED device to settings.yaml and reload instances."""
    result = add_wled_instance(req.host, req.start, req.end)
    if result.get("status") == "added":
        reload_config()
        init_instances()
    return result


@app.get("/api/teams/{league}")
async def get_teams(league: str):
    """Get all teams for a league (for simulator)."""
    if league not in get_leagues():
        raise HTTPException(404, f"Unknown league: {league}")

    teams = get_leagues()[league].get("teams", {})
    return [
        {
            "id": abbr,
            "name": team["display"],
            "colors": team.get("colors", [[128, 128, 128], [64, 64, 64]])
        }
        for abbr, team in sorted(teams.items(), key=lambda x: x[1]["display"])
    ]


@app.get("/api/games/{league}")
async def get_games(league: str):
    """Get active games for a league."""
    if league not in get_leagues():
        raise HTTPException(404, f"Unknown league: {league}")

    sport = get_leagues()[league]["sport"]
    games = await state.espn.get_scoreboard(sport, league)

    return [
        {
            "id": g["id"],
            "name": g["name"],
            "status": g["status"],
            "detail": g["detail"],
            "home_team": g["home_team"],
            "away_team": g["away_team"],
            "home_display": get_team_display(league, g["home_team"]),
            "away_display": get_team_display(league, g["away_team"]),
            "home_score": g["home_score"],
            "away_score": g["away_score"],
        }
        for g in games
    ]


class InstanceWatchRequest(BaseModel):
    league: str
    game_id: str


async def check_wled_simulation_state(inst: InstanceState) -> bool:
    """
    Check if WLED is still showing our game mode (simulation active).

    Returns True if WLED appears to be in game mode (has our segments),
    False if it was changed externally (preset, off, or different segments).
    """
    if not inst.controller:
        return False

    try:
        wled_state = await inst.controller.get_state()

        # Empty response means connection failed - preserve state
        if not wled_state:
            return True

        # If WLED is off, simulation is stale
        if not wled_state.get("on", False):
            return False

        # Check for our game mode segments by name
        segments = wled_state.get("seg", [])
        segment_names = {seg.get("n", "") for seg in segments if isinstance(seg, dict)}

        # Our game mode creates HOME and AWAY segments
        if "HOME" in segment_names or "AWAY" in segment_names:
            return True

        # No game mode segments found - WLED was changed externally
        return False

    except Exception as e:
        logger.warning(f"[SYNC] {inst.host}: Failed to check WLED state: {e}")
        # On error, assume simulation is still valid (don't lose state on network hiccup)
        return True


@app.get("/api/instances")
async def list_instances():
    """Get all WLED instances and their current status, including display settings."""
    settings = get_settings()
    global_display = settings.get("display", {})

    # Build a map of per-instance settings from config
    instance_configs = {
        i.get("host"): i for i in settings.get("wled_instances", [])
    }

    result = []
    for host, inst in state.instances.items():
        # Get per-instance config, falling back to global display settings
        inst_cfg = instance_configs.get(host, {})
        inst_display = inst_cfg.get("display", {})

        # Get post-game settings for this instance
        post_game = get_instance_post_game_settings(host)

        # Sync check: if instance claims to be simulating, verify WLED state
        # This detects when WLED was changed externally (wife's pink twinkles scenario)
        simulating = inst.simulating
        if simulating:
            still_active = await check_wled_simulation_state(inst)
            if not still_active:
                logger.info(f"[SYNC] {host}: Simulation stale (WLED changed externally), clearing flag")
                inst.simulating = False
                simulating = False
                # Don't restore preset here - just reflect reality

        item = {
            "host": host,
            "start": inst.start,
            "end": inst.end,
            "watching": inst.game is not None,
            "simulating": simulating,
            "watch_teams": get_instance_watch_teams(host),
            # Display settings (per-instance override > global > default)
            "min_team_pct": inst_display.get("min_team_pct", global_display.get("min_team_pct", 0.05)),
            "contested_zone_pixels": inst_display.get("contested_zone_pixels", global_display.get("contested_zone_pixels", 6)),
            "dark_buffer_pixels": inst_display.get("dark_buffer_pixels", global_display.get("dark_buffer_pixels", 4)),
            "chase_speed": inst_display.get("chase_speed", global_display.get("chase_speed", 185)),
            "chase_intensity": inst_display.get("chase_intensity", global_display.get("chase_intensity", 190)),
            "divider_preset": inst_display.get("divider_preset", global_display.get("divider_preset", "classic")),
            # Post-game settings
            "post_game_action": post_game.get("action", "flash_then_off"),
            "post_game_preset_id": post_game.get("preset_id"),
        }
        if inst.game:
            item["league"] = inst.game["league"]
            item["game_id"] = inst.game["game_id"]
            info = inst.game.get("last_info")
            if info:
                item["home_team"] = info.home_team
                item["away_team"] = info.away_team
                item["home_display"] = get_team_display(inst.game["league"], info.home_team)
                item["away_display"] = get_team_display(inst.game["league"], info.away_team)
                item["home_score"] = info.home_score
                item["away_score"] = info.away_score
                item["home_win_pct"] = info.home_win_pct
                # Mini scoreboard: period/clock info
                item["period"] = info.period
                item["status"] = info.status  # pre, in, post
        result.append(item)
    return result


@app.post("/api/instance/{host}/watch")
async def watch_game_on_instance(host: str, req: InstanceWatchRequest):
    """Start watching a game on a specific WLED instance."""
    if host not in state.instances:
        raise HTTPException(404, f"Unknown instance: {host}")

    inst = state.instances[host]

    # If simulating, stop sim first (real games take priority)
    if inst.simulating:
        logger.info(f"[WATCH] {host}: Stopping sim mode to watch real game")
        inst.simulating = False
        inst.sim_saved_preset = None  # Don't restore - game will save its own preset

    # Create controller if needed
    if not inst.controller:
        config = build_wled_config(inst.host, inst.start, inst.end)
        inst.controller = WLEDController(config)

    # Save current preset before we take over (for restore action)
    inst.previous_preset = await inst.controller.get_current_preset()
    logger.info(f"[WATCH] {host}: Saved previous preset {inst.previous_preset}")

    # Set the game
    inst.game = {
        "league": req.league,
        "game_id": req.game_id,
        "last_info": None,
        "last_status": "in",  # Assume in-progress when manually started
    }

    return {"status": "watching", "host": host, "game_id": req.game_id}


@app.post("/api/instance/{host}/stop")
async def stop_instance(host: str):
    """Stop watching on a specific instance and turn off its lights."""
    if host not in state.instances:
        raise HTTPException(404, f"Unknown instance: {host}")

    inst = state.instances[host]
    inst.game = None

    if inst.controller:
        await inst.controller.turn_off()

    return {"status": "stopped", "host": host}


@app.delete("/api/instance/{host}")
async def delete_instance(host: str):
    """Remove a WLED instance from config."""
    # Stop watching if active
    if host in state.instances:
        inst = state.instances[host]
        if inst.controller:
            await inst.controller.turn_off()
            await inst.controller.close()
        del state.instances[host]

    # Remove from config
    result = remove_wled_instance(host)
    return result


class UpdateInstanceRequest(BaseModel):
    host: Optional[str] = None
    start: Optional[int] = None
    end: Optional[int] = None


@app.patch("/api/instance/{host}")
async def update_instance(host: str, req: UpdateInstanceRequest):
    """Update core instance properties (host, start, end)."""
    from config import update_wled_instance

    if host not in state.instances:
        raise HTTPException(404, f"Unknown instance: {host}")

    # Update config
    result = update_wled_instance(
        host,
        new_host=req.host,
        start=req.start,
        end=req.end
    )

    if result.get("status") == "error":
        raise HTTPException(400, result.get("message"))

    # If host changed, update state.instances key
    if req.host and req.host != host:
        old_state = state.instances.pop(host)
        old_state.host = req.host
        if req.start is not None:
            old_state.start = req.start
        if req.end is not None:
            old_state.end = req.end
        state.instances[req.host] = old_state
    else:
        # Just update start/end on existing instance
        inst = state.instances[host]
        if req.start is not None:
            inst.start = req.start
        if req.end is not None:
            inst.end = req.end

    return result


class InstanceSettingsRequest(BaseModel):
    min_team_pct: Optional[float] = None
    contested_zone_pixels: Optional[int] = None
    dark_buffer_pixels: Optional[int] = None
    divider_preset: Optional[str] = None
    chase_speed: Optional[int] = None
    chase_intensity: Optional[int] = None


@app.post("/api/instance/{host}/settings")
async def update_instance_settings(host: str, req: InstanceSettingsRequest):
    """Update display settings for a specific WLED instance."""
    from config import update_instance_settings as cfg_update

    if host not in state.instances:
        raise HTTPException(404, f"Unknown instance: {host}")

    # Build settings dict from non-None values
    settings = {}
    if req.min_team_pct is not None:
        settings["min_team_pct"] = req.min_team_pct
    if req.contested_zone_pixels is not None:
        settings["contested_zone_pixels"] = req.contested_zone_pixels
    if req.dark_buffer_pixels is not None:
        settings["dark_buffer_pixels"] = req.dark_buffer_pixels
    if req.chase_speed is not None:
        settings["chase_speed"] = req.chase_speed
    if req.chase_intensity is not None:
        settings["chase_intensity"] = req.chase_intensity

    if not settings:
        return {"status": "no_changes", "host": host}

    result = cfg_update(host, settings)

    # Recreate controller with new settings if it exists
    inst = state.instances[host]
    if inst.controller:
        await inst.controller.close()
        config = build_wled_config(inst.host, inst.start, inst.end)
        inst.controller = WLEDController(config)

    return {"status": "updated", "host": host, **result}


@app.get("/api/instance/{host}/watch_teams")
async def get_watch_teams(host: str):
    """Get watched teams for a specific WLED instance."""
    if host not in state.instances:
        raise HTTPException(404, f"Unknown instance: {host}")

    watch_teams = get_instance_watch_teams(host)
    return {"host": host, "watch_teams": watch_teams}


class WatchTeamsRequest(BaseModel):
    watch_teams: list[str]  # e.g. ["nfl:GB", "nba:MIL"]


@app.post("/api/instance/{host}/watch_teams")
async def set_watch_teams(host: str, req: WatchTeamsRequest):
    """Set watched teams for a specific WLED instance."""
    if host not in state.instances:
        raise HTTPException(404, f"Unknown instance: {host}")

    result = update_instance_watch_teams(host, req.watch_teams)
    return result


class PostGameRequest(BaseModel):
    action: str  # off | fade_off | flash_then_off | restore | preset
    preset_id: Optional[int] = None


@app.post("/api/instance/{host}/post_game")
async def set_post_game(host: str, req: PostGameRequest):
    """Set post-game action for a specific WLED instance."""
    if host not in state.instances:
        raise HTTPException(404, f"Unknown instance: {host}")

    settings = {"action": req.action}
    if req.preset_id is not None:
        settings["preset_id"] = req.preset_id

    result = update_instance_post_game_settings(host, settings)
    return result


@app.post("/api/instance/{host}/sim/start")
async def start_sim(host: str):
    """
    Start simulator mode on an instance.
    Saves current WLED state for later restoration.
    Turns on WLED with a neutral display.
    Returns warning if instance is watching a live game.
    """
    if host not in state.instances:
        raise HTTPException(404, f"Unknown instance: {host}")

    inst = state.instances[host]

    # Check if already simulating
    if inst.simulating:
        return {"status": "already_simulating", "host": host}

    # Warn if watching a live game (but allow it)
    warning = None
    if inst.game is not None:
        warning = "Instance is watching a live game - simulator will override"

    # Create controller if needed
    if not inst.controller:
        config = build_wled_config(inst.host, inst.start, inst.end)
        inst.controller = WLEDController(config)

    # Save current preset before simulator takes over
    inst.sim_saved_preset = await inst.controller.get_current_preset()
    logger.info(f"[SIM] {host}: Started sim mode, saved preset {inst.sim_saved_preset}")

    inst.simulating = True

    # Turn on WLED with neutral 50/50 display (gray teams)
    # This ensures the lights come on immediately
    await inst.controller.set_game_mode(
        home_win_pct=0.5,
        home_colors=[[100, 100, 100], [60, 60, 60]],
        away_colors=[[100, 100, 100], [60, 60, 60]],
    )

    result = {"status": "simulating", "host": host, "saved_preset": inst.sim_saved_preset}
    if warning:
        result["warning"] = warning
    return result


@app.post("/api/instance/{host}/sim/stop")
async def stop_sim(host: str):
    """
    Stop simulator mode and restore previous WLED state.
    """
    if host not in state.instances:
        raise HTTPException(404, f"Unknown instance: {host}")

    inst = state.instances[host]

    if not inst.simulating:
        return {"status": "not_simulating", "host": host}

    # Restore saved preset
    if inst.controller and inst.sim_saved_preset is not None:
        logger.info(f"[SIM] {host}: Stopping sim, restoring preset {inst.sim_saved_preset}")
        await inst.controller.restore_preset(inst.sim_saved_preset)
    elif inst.controller:
        logger.info(f"[SIM] {host}: Stopping sim, no preset to restore - turning off")
        await inst.controller.turn_off()

    inst.simulating = False
    inst.sim_saved_preset = None

    return {"status": "stopped", "host": host}


@app.get("/api/status")
async def get_status():
    """Get current watching status (summary across all instances)."""
    watching_instances = [i for i in state.instances.values() if i.game]
    if not watching_instances:
        return {"watching": False, "instances": len(state.instances)}

    # Return info from first watching instance for backwards compatibility
    inst = watching_instances[0]
    info = inst.game.get("last_info") if inst.game else None

    result = {
        "watching": True,
        "instances_watching": len(watching_instances),
        "instances_total": len(state.instances),
        "game_id": inst.game["game_id"] if inst.game else None,
    }

    if info:
        result.update({
            "home_team": info.home_team,
            "away_team": info.away_team,
            "home_score": info.home_score,
            "away_score": info.away_score,
            "home_win_pct": info.home_win_pct,
            "period": info.period,
        })

    return result


class SimSettings(BaseModel):
    min_team_pct: Optional[float] = None
    dark_buffer_pixels: Optional[int] = None
    contested_zone_pixels: Optional[int] = None
    divider_preset: Optional[str] = None
    chase_speed: Optional[int] = None
    chase_intensity: Optional[int] = None


class TestRequest(BaseModel):
    pct: int
    league: str = "nfl"
    home: str = "GB"
    away: str = "CHI"
    host: Optional[str] = None  # Specific instance, or all if None
    settings: Optional[SimSettings] = None  # Override display settings for simulation


@app.post("/api/test")
async def test_percentage(req: TestRequest):
    """Test mode: manually set win percentage (0-100) with custom teams."""
    if not state.instances:
        raise HTTPException(400, "No WLED instances configured (check config/settings.yaml)")

    home_colors = get_team_colors(req.league, req.home)
    away_colors = get_team_colors(req.league, req.away)

    # Target specific instance or all
    targets = [state.instances[req.host]] if req.host else state.instances.values()

    for inst in targets:
        # Create controller if needed
        if not inst.controller:
            config = build_wled_config(inst.host, inst.start, inst.end)
            inst.controller = WLEDController(config)

        # Apply simulator settings override if provided (update config in place)
        if req.settings:
            inst.controller.config.min_team_pct = req.settings.min_team_pct or 0.05
            inst.controller.config.contested_zone_pixels = req.settings.contested_zone_pixels or 6
            inst.controller.config.dark_buffer_pixels = req.settings.dark_buffer_pixels or 4
            inst.controller.config.chase_speed = req.settings.chase_speed or 185
            inst.controller.config.chase_intensity = req.settings.chase_intensity or 190
            inst.controller.config.divider_preset = req.settings.divider_preset or "classic"
            # Clear divider_color so preset color is used
            inst.controller.config.divider_color = None

        await inst.controller.set_game_mode(
            home_win_pct=req.pct / 100,
            home_colors=home_colors,
            away_colors=away_colors,
        )

    return {"status": "ok", "pct": req.pct, "home": req.home, "away": req.away}


@app.get("/api/simulator")
async def get_simulator_settings():
    """Get saved simulator defaults."""
    return get_simulator_defaults()


class SimulatorDefaultsRequest(BaseModel):
    league: str
    home: str
    away: str
    win_pct: int


@app.post("/api/simulator")
async def save_simulator_settings(req: SimulatorDefaultsRequest):
    """Save simulator defaults to settings.yaml."""
    return update_simulator_defaults({
        "league": req.league,
        "home": req.home,
        "away": req.away,
        "win_pct": req.win_pct,
    })


# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

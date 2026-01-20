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
from config import get_settings, get_leagues, reload_config, add_wled_instance, CONFIG_DIR, get_instance_display_settings
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
    )


# App state - per-instance game tracking
class InstanceState:
    """State for a single WLED instance."""
    def __init__(self, host: str, start: int, end: int):
        self.host = host
        self.start = start
        self.end = end
        self.controller: Optional[WLEDController] = None
        self.game: Optional[dict] = None  # {league, game_id, last_info}


class AppState:
    espn: Optional[ESPNClient] = None
    instances: dict[str, InstanceState] = {}  # host -> InstanceState
    poll_task: Optional[asyncio.Task] = None


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
                            inst.game["last_info"] = game
                            await inst.controller.set_game_mode(
                                home_win_pct=game.home_win_pct,
                                home_colors=home_colors,
                                away_colors=away_colors,
                            )

                        logger.info(f"[{league.upper()}] {game.away_team} @ {game.home_team} | "
                                    f"{game.away_score}-{game.home_score} | "
                                    f"Home: {game.home_win_pct:.1%} | "
                                    f"{len(instances)} instance(s)")

        except Exception as e:
            logger.error(f"Poll error: {e}")

        await asyncio.sleep(30)  # Poll every 30 seconds


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
        {"id": abbr, "name": team["display"]}
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

        item = {
            "host": host,
            "start": inst.start,
            "end": inst.end,
            "watching": inst.game is not None,
            # Display settings (per-instance override > global > default)
            "min_team_pct": inst_display.get("min_team_pct", global_display.get("min_team_pct", 0.05)),
            "contested_zone_pixels": inst_display.get("contested_zone_pixels", global_display.get("contested_zone_pixels", 6)),
            "dark_buffer_pixels": inst_display.get("dark_buffer_pixels", global_display.get("dark_buffer_pixels", 4)),
            "chase_speed": inst_display.get("chase_speed", global_display.get("chase_speed", 185)),
            "chase_intensity": inst_display.get("chase_intensity", global_display.get("chase_intensity", 190)),
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
        result.append(item)
    return result


@app.post("/api/instance/{host}/watch")
async def watch_game_on_instance(host: str, req: InstanceWatchRequest):
    """Start watching a game on a specific WLED instance."""
    if host not in state.instances:
        raise HTTPException(404, f"Unknown instance: {host}")

    inst = state.instances[host]

    # Create controller if needed
    if not inst.controller:
        config = build_wled_config(inst.host, inst.start, inst.end)
        inst.controller = WLEDController(config)

    # Set the game
    inst.game = {
        "league": req.league,
        "game_id": req.game_id,
        "last_info": None,
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


class InstanceSettingsRequest(BaseModel):
    min_team_pct: Optional[float] = None
    contested_zone_pixels: Optional[int] = None
    dark_buffer_pixels: Optional[int] = None
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


class TestRequest(BaseModel):
    pct: int
    league: str = "nfl"
    home: str = "GB"
    away: str = "CHI"
    host: Optional[str] = None  # Specific instance, or all if None


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
        if not inst.controller:
            config = build_wled_config(inst.host, inst.start, inst.end)
            inst.controller = WLEDController(config)

        await inst.controller.set_game_mode(
            home_win_pct=req.pct / 100,
            home_colors=home_colors,
            away_colors=away_colors,
        )

    return {"status": "ok", "pct": req.pct, "home": req.home, "away": req.away}


# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

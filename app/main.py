"""
Scoreline - Live ESPN win probability → WLED visualization.

FastAPI app with game picker UI and background polling.
"""

import asyncio
import ipaddress
import logging
import os
import re
import threading
import time
from collections import deque
from enum import StrEnum

from auth import AUTH_ENABLED, FORCE_HTTPS, check_auth, log_auth_config
from auth import router as auth_router
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

logger = logging.getLogger("uvicorn.error")


# Explicit UI state machine
class UIState(StrEnum):
    """Explicit states for instance UI behavior."""
    IDLE = "idle"                        # No game, no auto-watch
    IDLE_AUTOWATCH = "idle_autowatch"    # No game, auto-watch armed
    WATCHING_AUTO = "watching_auto"      # Game started from auto-watch
    WATCHING_MANUAL = "watching_manual"  # Manually selected, no auto-watch teams
    WATCHING_OVERRIDE = "watching_override"  # Manually selected, overriding auto-watch
    FINAL = "final"                      # Game ended, showing final score
    SIMULATING = "simulating"            # Simulator active


class HealthStatus(StrEnum):
    """WLED connection health tiers."""
    HEALTHY = "healthy"
    STALE = "stale"
    UNREACHABLE = "unreachable"

from discovery import discover_wled_devices
from espn import ESPNClient, GameInfo
from teams import get_team_colors, get_team_display
from wled import WLEDConfig, WLEDController

from config import (
    CONFIG_DIR,
    add_wled_instance,
    get_instance_display_settings,
    get_instance_post_game_settings,
    get_instance_watch_teams,
    get_leagues,
    get_settings,
    get_simulator_defaults,
    reload_config,
    remove_wled_instance,
    update_instance_post_game_settings,
    update_instance_watch_teams,
    update_simulator_defaults,
)


def espn_slug(league: str) -> str:
    """Resolve our league ID to ESPN's API slug. Falls back to league ID itself."""
    return get_leagues().get(league, {}).get("espn_league") or league


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
        self.mac: str | None = None  # WLED device MAC address
        self.controller: WLEDController | None = None
        self.game: dict | None = None  # {league, game_id, last_info, last_status}
        self.previous_preset: int | None = None  # Preset to restore after game
        self.simulating: bool = False  # True when driven by simulator
        self.sim_saved_preset: int | None = None  # Preset to restore when sim stops
        # Unified display payload — populated by ESPN, simulator, or any future source
        # Keys: league, home_team, away_team, home_display, away_display,
        #        home_colors, away_colors, home_score, away_score, home_win_pct, period, status
        self.display: dict | None = None

        # Explicit state machine
        self.ui_state: UIState = UIState.IDLE
        self.watch_trigger: str | None = None  # "auto" or "manual" - how watching started

        # Health tracking
        self.health_last_success: float = time.time()
        self.health_consecutive_failures: int = 0
        self.health_last_error: str | None = None

        # FINAL state linger
        self.final_linger_until: float | None = None
        self.final_game_info: dict | None = None  # Preserved game info for FINAL display

        # Celebration state tracking (two-phase post-game)
        self.celebration_end_time: float | None = None  # When celebration phase ends
        self.celebration_after_action: str | None = None  # What to do after celebration
        self.celebration_preset_id: int | None = None  # For preset after_action

        # Win probability history for sparkline (circular buffer)
        self.win_pct_history: deque = deque(maxlen=120)

    def get_health_status(self) -> HealthStatus:
        """Derive health tier from tracking data."""
        if self.health_consecutive_failures >= 3:
            return HealthStatus.UNREACHABLE
        if time.time() - self.health_last_success > 120:  # 2 minutes
            return HealthStatus.STALE
        return HealthStatus.HEALTHY

    def record_success(self):
        """Record a successful WLED operation."""
        self.health_last_success = time.time()
        self.health_consecutive_failures = 0
        self.health_last_error = None

    def record_failure(self, error: str):
        """Record a failed WLED operation."""
        self.health_consecutive_failures += 1
        self.health_last_error = error


MAX_WS_CONNECTIONS = 50


class ConnectionManager:
    """WebSocket connection manager for real-time updates."""
    def __init__(self):
        self.connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        if len(self.connections) >= MAX_WS_CONNECTIONS:
            await ws.close(code=1013, reason="Too many connections")
            return False
        await ws.accept()
        self.connections.add(ws)
        return True

    def disconnect(self, ws: WebSocket):
        self.connections.discard(ws)

    async def broadcast(self, message: dict):
        dead = set()
        for ws in self.connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        self.connections -= dead


ws_manager = ConnectionManager()


async def broadcast_state():
    """Broadcast current instance state to all WebSocket clients."""
    if ws_manager.connections:
        try:
            data = await list_instances()
            await ws_manager.broadcast({"type": "instances_update", "data": data})
        except Exception as e:
            logger.debug(f"WebSocket broadcast error: {e}")


class AppState:
    def __init__(self):
        self.espn: ESPNClient | None = None
        self.instances: dict[str, InstanceState] = {}  # host -> InstanceState
        self.poll_task: asyncio.Task | None = None
        self.auto_watch_task: asyncio.Task | None = None


state = AppState()


def compute_ui_state(inst: InstanceState) -> UIState:
    """Compute the correct UI state based on instance data."""
    watch_teams = get_instance_watch_teams(inst.host)
    has_watch_teams = len(watch_teams) > 0

    # Simulating takes priority
    if inst.simulating:
        return UIState.SIMULATING

    # FINAL state persists until linger expires
    if inst.ui_state == UIState.FINAL and inst.final_linger_until:
        if time.time() < inst.final_linger_until:
            return UIState.FINAL

    # Not watching anything
    if inst.game is None:
        return UIState.IDLE_AUTOWATCH if has_watch_teams else UIState.IDLE

    # Watching a game - determine which type
    if inst.watch_trigger == "auto":
        return UIState.WATCHING_AUTO

    # Manual trigger - check if it's override or just manual
    if has_watch_teams:
        # Check if the game is for one of our watched teams
        game_info = inst.game.get("last_info")
        if game_info:
            league = inst.game.get("league", "")
            home_team = game_info.home_team.upper() if hasattr(game_info, 'home_team') else ""
            away_team = game_info.away_team.upper() if hasattr(game_info, 'away_team') else ""

            # Check if either team is in watch list
            for wt in watch_teams:
                parts = wt.split(":")
                if len(parts) == 2:
                    wt_league, wt_team = parts
                    if wt_league == league and wt_team.upper() in (home_team, away_team):
                        # It's our team - treat as manual (eager start), not override
                        return UIState.WATCHING_MANUAL

        # Different team - this is an override
        return UIState.WATCHING_OVERRIDE

    return UIState.WATCHING_MANUAL


def transition_to_watching(inst: InstanceState, game: dict, trigger: str):
    """
    Transition instance to a watching state.

    Args:
        inst: The instance to transition
        game: Game dict with league, game_id, etc.
        trigger: "auto" or "manual"
    """
    inst.game = game
    inst.watch_trigger = trigger
    inst.final_linger_until = None
    inst.final_game_info = None
    inst.display = None
    inst.win_pct_history.clear()

    # Compute the appropriate watching state
    inst.ui_state = compute_ui_state(inst)
    logger.info(f"[STATE] {inst.host}: → {inst.ui_state.value} (trigger={trigger})")


def transition_to_final(inst: InstanceState, linger_seconds: int = 30):
    """
    Transition instance to FINAL state after game ends.

    Args:
        inst: The instance to transition
        linger_seconds: How long to show final score before transitioning
    """
    # Preserve game info for display
    inst.final_game_info = inst.game.copy() if inst.game else None
    inst.final_linger_until = time.time() + linger_seconds
    inst.ui_state = UIState.FINAL
    logger.info(f"[STATE] {inst.host}: → FINAL (linger={linger_seconds}s)")


async def transition_from_final(inst: InstanceState):
    """
    Transition from FINAL state - either cascade to next game or go idle.
    """
    watch_teams = get_instance_watch_teams(inst.host)

    # Check for cascade - another watched team's game in progress
    if watch_teams and state.espn:
        next_game = await find_next_priority_game(inst.host, watch_teams)
        if next_game:
            logger.info(f"[CASCADE] {inst.host}: Found next game, transitioning to WATCHING_AUTO")
            transition_to_watching(inst, next_game, "auto")
            return

    # No cascade - go to idle
    inst.game = None
    inst.watch_trigger = None
    inst.final_linger_until = None
    inst.final_game_info = None
    inst.display = None
    inst.win_pct_history.clear()
    inst.ui_state = UIState.IDLE_AUTOWATCH if watch_teams else UIState.IDLE
    logger.info(f"[STATE] {inst.host}: → {inst.ui_state.value}")


async def find_next_priority_game(host: str, watch_teams: list[str]) -> dict | None:
    """
    Find the next in-progress game from watch list in priority order.

    Args:
        host: Instance host (for logging)
        watch_teams: Ordered list of watched teams (first = highest priority)

    Returns:
        Game dict if found, None otherwise
    """
    for team_spec in watch_teams:
        parts = team_spec.split(":")
        if len(parts) != 2:
            continue
        league, team = parts

        if league not in get_leagues():
            continue

        sport = get_leagues()[league]["sport"]
        try:
            if state.espn is None:
                continue
            games = await state.espn.get_scoreboard(sport, espn_slug(league))
            for game in games:
                if game["status"] != "in":
                    continue
                home_team = game["home_team"].upper()
                away_team = game["away_team"].upper()
                if team.upper() in (home_team, away_team):
                    logger.info(f"[CASCADE] {host}: Found {away_team}@{home_team} for {team_spec}")
                    return {
                        "league": league,
                        "game_id": game["id"],
                        "last_info": None,
                        "last_status": "in",
                    }
        except Exception as e:
            logger.error(f"[CASCADE] Error checking {league} for {host}: {e}")

    return None


def init_instances():
    """Initialize WLED instances from config, preserving existing state."""
    settings = get_settings()
    new_instances = {}

    for inst_cfg in settings.get("wled_instances", []):
        host = inst_cfg["host"]

        # Check if instance already exists - preserve its state
        if host in state.instances:
            existing = state.instances[host]
            # Update config values that might have changed
            existing.start = inst_cfg.get("start", 0)
            existing.end = inst_cfg.get("end", 629)
            # Recompute UI state (watch_teams may have changed)
            existing.ui_state = compute_ui_state(existing)
            new_instances[host] = existing
            logger.debug(f"[INIT] {host}: Preserved existing state ({existing.ui_state.value})")
        else:
            # New instance
            inst = InstanceState(
                host=host,
                start=inst_cfg.get("start", 0),
                end=inst_cfg.get("end", 629),
            )
            inst.ui_state = compute_ui_state(inst)
            new_instances[host] = inst
            logger.debug(f"[INIT] {host}: Created new instance ({inst.ui_state.value})")

    # Remove instances that are no longer in config
    for host in state.instances:
        if host not in new_instances:
            logger.info(f"[INIT] {host}: Removed from config")

    state.instances = new_instances


# Config file watcher for auto-reload
class ConfigWatcher(FileSystemEventHandler):
    """Watch config directory for changes and auto-reload."""
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._debounce_timer = None
        self._lock = threading.Lock()
        self._loop = loop

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
        """Schedule reload on the event loop thread (thread-safe)."""
        self._loop.call_soon_threadsafe(self._reload_sync)

    def _reload_sync(self):
        """Runs on the event loop thread — safe to mutate shared state."""
        logger.info("Config changed, reloading...")
        reload_config()
        init_instances()
        logger.info(f"Reloaded: {len(state.instances)} instance(s)")


config_observer: PollingObserver | None = None


async def resolve_instance_macs():
    """Fetch MAC addresses from all WLED instances (best-effort, non-blocking)."""
    for host, inst in state.instances.items():
        if inst.mac:
            continue
        try:
            config = build_wled_config(host, inst.start, inst.end)
            controller = WLEDController(config)
            mac = await controller.get_mac()
            await controller.close()
            if mac:
                inst.mac = mac
                logger.info(f"[INIT] {host}: Resolved MAC {mac}")
        except Exception as e:
            logger.debug(f"[INIT] {host}: Could not resolve MAC: {e}")


async def lifespan(app: FastAPI):
    global config_observer
    # Startup
    log_auth_config()
    state.espn = ESPNClient()
    init_instances()
    # Resolve WLED MAC addresses in background (non-blocking)
    asyncio.create_task(resolve_instance_macs())
    # Start the unified poll task
    state.poll_task = asyncio.create_task(poll_all_games())
    # Start auto-watch task (scans for watched teams' games)
    state.auto_watch_task = asyncio.create_task(auto_watch_all())
    # Start config file watcher (polling for Docker compatibility)
    loop = asyncio.get_running_loop()
    config_observer = PollingObserver(timeout=5)
    config_observer.schedule(ConfigWatcher(loop), str(CONFIG_DIR), recursive=True)
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
    # Restore WLED strips to known state before closing
    for inst in state.instances.values():
        if inst.controller:
            try:
                if inst.previous_preset is not None:
                    await inst.controller.restore_preset(inst.previous_preset)
                else:
                    await inst.controller.turn_off()
            except Exception as e:
                logger.debug(f"[SHUTDOWN] {inst.host}: Could not restore WLED: {e}")
            await inst.controller.close()


app = FastAPI(title="Game Lights", lifespan=lifespan)

# Auth routes (login, logout, me)
app.include_router(auth_router, prefix="/api")

# CORS — restrict to same-origin by default, configurable via env
_cors_origins = os.environ.get("CORS_ORIGINS", "")
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in _cors_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self' ws: wss:; font-src 'self'"
    )
    if FORCE_HTTPS:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Authentication middleware — protects /api/* routes when auth is enabled."""
    path = request.url.path

    # Open paths — static assets, auth endpoints, health/status, WebSocket
    if not path.startswith("/api/") or path.startswith("/api/auth/") or path in ("/api/status", "/api/health"):
        return await call_next(request)

    if not AUTH_ENABLED:
        return await call_next(request)

    user = check_auth(request)
    if user is None:
        return JSONResponse(status_code=401, content={"detail": "Authentication required"})

    request.state.user = user
    return await call_next(request)


# Background polling
async def poll_all_games():
    """Background task to poll ESPN and update each WLED instance with its game."""
    while True:
        try:
            if state.espn:
                # Collect unique games to poll (avoid duplicate API calls)
                games_to_poll: dict[str, list[InstanceState]] = {}  # game_key -> instances
                for inst in state.instances.values():
                    if inst.game and inst.controller and not inst.simulating:
                        key = f"{inst.game['league']}:{inst.game['game_id']}"
                        if key not in games_to_poll:
                            games_to_poll[key] = []
                        games_to_poll[key].append(inst)

                # Poll each unique game and update its instances
                for game_key, instances in games_to_poll.items():
                    league, game_id = game_key.split(":", 1)
                    sport = get_leagues().get(league, {}).get("sport", "football")

                    game = await state.espn.get_game_detail(sport, espn_slug(league), game_id)

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
                                inst.win_pct_history.append({
                                    "t": time.time(),
                                    "pct": game.home_win_pct,
                                })
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

            # Broadcast updated state to WebSocket clients
            if games_to_poll and ws_manager.connections:
                try:
                    instances_data = await list_instances()
                    await ws_manager.broadcast({"type": "instances_update", "data": instances_data})
                except Exception as ws_err:
                    logger.debug(f"WebSocket broadcast error: {ws_err}")

        except Exception as e:
            logger.error(f"Poll error: {e}")

        await asyncio.sleep(30)  # Poll every 30 seconds


async def auto_watch_all():
    """
    Background task to auto-start games for watched teams.
    Scans scoreboards for leagues with watched teams, auto-starts in-progress games.
    Now uses priority ordering - first team in watch list = highest priority.
    """
    settings = get_settings()
    # Allow env var override for testing (e.g., AUTO_WATCH_INTERVAL=30)
    interval = int(os.environ.get("AUTO_WATCH_INTERVAL", settings.get("auto_watch_interval", 300)))

    while True:
        try:
            # Process each instance individually to respect per-instance priority
            for host, inst in state.instances.items():
                # Skip if already watching or simulating
                if inst.game is not None or inst.simulating:
                    continue

                # Skip if in FINAL state (waiting for linger to expire)
                if inst.ui_state == UIState.FINAL:
                    continue

                watch_teams = get_instance_watch_teams(host)
                if not watch_teams:
                    continue

                # Find best game based on priority (array order)
                best_game = await find_next_priority_game(host, watch_teams)
                if not best_game:
                    continue

                # Auto-start the highest priority game!
                logger.info(f"[AUTO-WATCH] {host}: Starting game (priority-based)")

                if not inst.controller:
                    config = build_wled_config(inst.host, inst.start, inst.end)
                    inst.controller = WLEDController(config)

                # Save current preset before we take over (for restore action)
                try:
                    inst.previous_preset = await inst.controller.get_current_preset()
                    inst.record_success()
                    logger.info(f"[AUTO-WATCH] {host}: Saved previous preset {inst.previous_preset}")
                except Exception as e:
                    inst.record_failure(str(e))
                    logger.warning(f"[AUTO-WATCH] {host}: Could not save preset: {e}")

                # Use state transition
                transition_to_watching(inst, best_game, "auto")

                # Broadcast game started for toast notifications
                game_info = best_game.get("last_info")
                if game_info:
                    league_name = best_game.get("league", "")
                    await ws_manager.broadcast({
                        "type": "game_started",
                        "host": host,
                        "home_team": get_team_display(league_name, game_info.home_team),
                        "away_team": get_team_display(league_name, game_info.away_team),
                    })
                await broadcast_state()

        except Exception as e:
            logger.error(f"Auto-watch error: {e}")

        await asyncio.sleep(interval)


async def handle_game_ended(inst: InstanceState, game_info: GameInfo):
    """
    Handle post-game celebration when a game ends.
    Phase 1: Start celebration effect in winner colors
    Phase 2: Scheduled via check_celebration_end() to execute after_action

    Args:
        inst: The WLED instance that was watching
        game_info: Final game state
    """
    if not inst.controller:
        return

    if inst.game is None:
        return
    league = inst.game["league"]
    post_game = get_instance_post_game_settings(inst.host)

    celebration = post_game.get("celebration", "chase")
    duration = post_game.get("celebration_duration_s", 60)
    after_action = post_game.get("after_action", "fade_off")
    preset_id = post_game.get("preset_id")

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
                f"Winner: {winner} | Celebration: {celebration} ({duration}s) → {after_action}")

    # Store celebration state for later
    inst.celebration_end_time = time.time() + duration
    inst.celebration_after_action = after_action
    inst.celebration_preset_id = preset_id

    # Phase 1: Start celebration effect
    try:
        if celebration == "freeze":
            # Keep current display (do nothing to WLED)
            logger.info(f"[CELEBRATION] {inst.host}: Freeze - keeping current display")

        elif celebration == "chase":
            await inst.controller.set_celebration_chase(winner_colors)

        elif celebration == "twinkle":
            await inst.controller.set_celebration_twinkle(winner_colors)

        elif celebration == "flash":
            await inst.controller.set_celebration_flash_loop(winner_colors)

        elif celebration == "solid":
            await inst.controller.set_celebration_solid(winner_colors)

        else:
            # Unknown celebration type - default to chase
            logger.warning(f"[CELEBRATION] {inst.host}: Unknown type '{celebration}', using chase")
            await inst.controller.set_celebration_chase(winner_colors)

        inst.record_success()
    except Exception as e:
        logger.error(f"[CELEBRATION] Error on {inst.host}: {e}")
        inst.record_failure(str(e))

    # Transition to FINAL state (celebration duration is the linger time)
    transition_to_final(inst, linger_seconds=duration)

    # Broadcast game ended event for toast notifications
    await ws_manager.broadcast({
        "type": "game_ended",
        "host": inst.host,
        "home_team": get_team_display(league, game_info.home_team),
        "away_team": get_team_display(league, game_info.away_team),
        "home_score": game_info.home_score,
        "away_score": game_info.away_score,
    })
    await broadcast_state()

    # Schedule the end of celebration
    asyncio.create_task(check_celebration_end(inst))


async def check_celebration_end(inst: InstanceState):
    """
    Wait for celebration to end, then execute after_action.
    """
    if not inst.celebration_end_time:
        return

    # Wait for celebration period
    wait_time = inst.celebration_end_time - time.time()
    if wait_time > 0:
        await asyncio.sleep(wait_time)

    # Only proceed if still in FINAL state (user might have manually changed)
    if inst.ui_state != UIState.FINAL:
        logger.info(f"[CELEBRATION] {inst.host}: State changed, skipping after_action")
        return

    # Phase 2: Execute after_action
    after_action = inst.celebration_after_action or "fade_off"
    logger.info(f"[CELEBRATION] {inst.host}: Celebration ended, executing {after_action}")

    if not inst.controller:
        return

    try:
        if after_action == "off":
            await inst.controller.turn_off()

        elif after_action == "fade_off":
            fade_s = get_instance_post_game_settings(inst.host).get("fade_duration_s", 3)
            await inst.controller.fade_off(duration_s=fade_s)

        elif after_action == "restore":
            if inst.previous_preset is not None:
                logger.info(f"[CELEBRATION] {inst.host}: Restoring preset {inst.previous_preset}")
                await inst.controller.restore_preset(inst.previous_preset)
            else:
                logger.info(f"[CELEBRATION] {inst.host}: No previous preset, turning off")
                await inst.controller.turn_off()

        elif after_action == "preset":
            preset_id = inst.celebration_preset_id
            if preset_id is not None:
                logger.info(f"[CELEBRATION] {inst.host}: Switching to preset {preset_id}")
                await inst.controller.restore_preset(preset_id)
            else:
                logger.warning(f"[CELEBRATION] {inst.host}: No preset_id configured, turning off")
                await inst.controller.turn_off()

        inst.record_success()
    except Exception as e:
        logger.error(f"[CELEBRATION] After-action error on {inst.host}: {e}")
        inst.record_failure(str(e))

    # Clear celebration state
    inst.celebration_end_time = None
    inst.celebration_after_action = None
    inst.celebration_preset_id = None
    inst.previous_preset = None

    # Transition from FINAL state
    await transition_from_final(inst)


# SPA frontend
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


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


_HOST_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{1,253}$")
_BLOCKED_NETS = [
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("0.0.0.0/8"),          # Unspecified
    ipaddress.ip_network("169.254.0.0/16"),     # Link-local
    ipaddress.ip_network("224.0.0.0/4"),        # Multicast
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
    ipaddress.ip_network("fc00::/7"),           # IPv6 ULA
    ipaddress.ip_network("ff00::/8"),           # IPv6 multicast
]


def _validate_wled_host(host: str) -> str | None:
    """Validate a WLED host. Returns error message or None if valid."""
    if not _HOST_PATTERN.match(host):
        return f"Invalid host: {host!r} (only alphanumeric, dots, hyphens, underscores)"
    try:
        addr = ipaddress.ip_address(host)
        for net in _BLOCKED_NETS:
            if addr in net:
                return f"Blocked address: {host}"
    except ValueError:
        pass  # Not an IP — hostname, that's fine
    return None


class AddWLEDRequest(BaseModel):
    host: str
    start: int = 0
    end: int = 300


@app.post("/api/wled/add")
async def api_add_wled(req: AddWLEDRequest):
    """Add a WLED device to settings.yaml and reload instances."""
    err = _validate_wled_host(req.host)
    if err:
        raise HTTPException(400, err)
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
    if state.espn is None:
        raise HTTPException(503, "ESPN client not initialized")
    games = await state.espn.get_scoreboard(sport, espn_slug(league))

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
            "home_colors": get_team_colors(league, g["home_team"]),
            "away_colors": get_team_colors(league, g["away_team"]),
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
                # Recompute UI state
                inst.ui_state = compute_ui_state(inst)

        # Recompute UI state (ensures it's always current)
        current_state = compute_ui_state(inst)
        if current_state != inst.ui_state:
            inst.ui_state = current_state

        # Get health status
        health_status = inst.get_health_status()

        item = {
            "host": host,
            "mac": inst.mac,
            "start": inst.start,
            "end": inst.end,
            "simulating": simulating,
            "watch_teams": get_instance_watch_teams(host),
            # Explicit state machine
            "state": inst.ui_state.value,
            "game_phase": inst.game.get("last_status") if inst.game else None,
            # Health tracking
            "health": {
                "status": health_status.value,
                "last_success": inst.health_last_success,
                "consecutive_failures": inst.health_consecutive_failures,
                "last_error": inst.health_last_error,
            },
            # FINAL state info
            "final_linger_remaining": max(0, inst.final_linger_until - time.time()) if inst.final_linger_until else None,
            # Display settings (per-instance override > global > default)
            "min_team_pct": inst_display.get("min_team_pct", global_display.get("min_team_pct", 0.05)),
            "contested_zone_pixels": inst_display.get("contested_zone_pixels", global_display.get("contested_zone_pixels", 6)),
            "dark_buffer_pixels": inst_display.get("dark_buffer_pixels", global_display.get("dark_buffer_pixels", 4)),
            "chase_speed": inst_display.get("chase_speed", global_display.get("chase_speed", 185)),
            "chase_intensity": inst_display.get("chase_intensity", global_display.get("chase_intensity", 190)),
            "divider_preset": inst_display.get("divider_preset", global_display.get("divider_preset", "classic")),
            # Post-game celebration settings (two-phase system)
            "post_game_celebration": post_game.get("celebration", "chase"),
            "post_game_duration": post_game.get("celebration_duration_s", 60),
            "post_game_after_action": post_game.get("after_action", "fade_off"),
            "post_game_preset_id": post_game.get("preset_id"),
            # Celebration state (if in FINAL state)
            "celebration_remaining": max(0, inst.celebration_end_time - time.time()) if inst.celebration_end_time else None,
        }

        # Unified display payload — built from whichever source is active
        # The frontend just renders what's here; it never checks the source.
        display = inst.display or {}

        # ESPN game data populates display (authoritative when watching)
        game_data = inst.game
        if inst.ui_state == UIState.FINAL and inst.final_game_info:
            game_data = inst.final_game_info
        if game_data:
            display["league"] = game_data["league"]
            display["game_id"] = game_data["game_id"]
            info = game_data.get("last_info")
            if info:
                league_key = game_data["league"]
                display["home_team"] = info.home_team
                display["away_team"] = info.away_team
                display["home_display"] = get_team_display(league_key, info.home_team)
                display["away_display"] = get_team_display(league_key, info.away_team)
                display["home_colors"] = get_team_colors(league_key, info.home_team)
                display["away_colors"] = get_team_colors(league_key, info.away_team)
                display["home_score"] = info.home_score
                display["away_score"] = info.away_score
                display["home_win_pct"] = info.home_win_pct
                display["period"] = info.period
                display["status"] = info.status

        # Merge display into item — flat, same keys regardless of source
        item.update(display)
        item["win_pct_history"] = list(inst.win_pct_history)
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
    try:
        inst.previous_preset = await inst.controller.get_current_preset()
        inst.record_success()
        logger.info(f"[WATCH] {host}: Saved previous preset {inst.previous_preset}")
    except Exception as e:
        inst.record_failure(str(e))
        logger.warning(f"[WATCH] {host}: Could not save preset: {e}")

    # Build game dict
    game: dict[str, object] = {
        "league": req.league,
        "game_id": req.game_id,
        "last_info": None,
        "last_status": "in",  # Assume in-progress when manually started
    }

    # Fetch game data immediately so UI has scores right away
    try:
        sport = get_leagues().get(req.league, {}).get("sport", "football")
        if state.espn is None:
            raise HTTPException(503, "ESPN client not initialized")
        game_info = await state.espn.get_game_detail(sport, espn_slug(req.league), req.game_id)
        if game_info:
            game["last_info"] = game_info
            game["last_status"] = game_info.status
            # Push initial state to WLED
            home_colors = get_team_colors(req.league, game_info.home_team)
            away_colors = get_team_colors(req.league, game_info.away_team)
            await inst.controller.set_game_mode(
                home_win_pct=game_info.home_win_pct,
                home_colors=home_colors,
                away_colors=away_colors,
            )
            inst.record_success()
    except Exception as e:
        inst.record_failure(str(e))
        logger.warning(f"[WATCH] {host}: Failed to fetch initial game data: {e}")

    # Use state transition (manual trigger)
    transition_to_watching(inst, game, "manual")

    await broadcast_state()
    return {"status": "watching", "host": host, "game_id": req.game_id, "state": inst.ui_state.value}


@app.post("/api/instance/{host}/stop")
async def stop_instance(host: str):
    """Stop watching on a specific instance and turn off its lights."""
    if host not in state.instances:
        raise HTTPException(404, f"Unknown instance: {host}")

    inst = state.instances[host]
    watch_teams = get_instance_watch_teams(host)

    # Clear game state
    inst.game = None
    inst.watch_trigger = None
    inst.final_linger_until = None
    inst.final_game_info = None
    inst.display = None

    # Transition to appropriate idle state
    inst.ui_state = UIState.IDLE_AUTOWATCH if watch_teams else UIState.IDLE
    logger.info(f"[STATE] {host}: → {inst.ui_state.value} (manual stop)")

    if inst.controller:
        try:
            await inst.controller.turn_off()
            inst.record_success()
        except Exception as e:
            inst.record_failure(str(e))

    inst.win_pct_history.clear()
    await broadcast_state()
    return {"status": "stopped", "host": host, "state": inst.ui_state.value}


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
    host: str | None = None
    start: int | None = None
    end: int | None = None


@app.patch("/api/instance/{host}")
async def update_instance(host: str, req: UpdateInstanceRequest):
    """Update core instance properties (host, start, end)."""
    from config import update_wled_instance

    if req.host:
        err = _validate_wled_host(req.host)
        if err:
            raise HTTPException(400, err)

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

    await broadcast_state()
    return result


class InstanceSettingsRequest(BaseModel):
    min_team_pct: float | None = Field(default=None, ge=0.0, le=0.5)
    contested_zone_pixels: int | None = Field(default=None, ge=0, le=50)
    dark_buffer_pixels: int | None = Field(default=None, ge=0, le=20)
    divider_preset: str | None = None
    chase_speed: int | None = Field(default=None, ge=0, le=255)
    chase_intensity: int | None = Field(default=None, ge=0, le=255)


@app.post("/api/instance/{host}/settings")
async def update_instance_settings(host: str, req: InstanceSettingsRequest):
    """Update display settings for a specific WLED instance."""
    from wled import DIVIDER_PRESETS

    from config import update_instance_settings as cfg_update

    if host not in state.instances:
        raise HTTPException(404, f"Unknown instance: {host}")

    # Build settings dict from non-None values
    settings: dict[str, float | int | str] = {}
    if req.min_team_pct is not None:
        settings["min_team_pct"] = req.min_team_pct
    if req.contested_zone_pixels is not None:
        settings["contested_zone_pixels"] = req.contested_zone_pixels
    if req.dark_buffer_pixels is not None:
        settings["dark_buffer_pixels"] = req.dark_buffer_pixels
    if req.divider_preset is not None:
        if req.divider_preset not in DIVIDER_PRESETS:
            raise HTTPException(400, f"Invalid divider_preset: {req.divider_preset!r}")
        settings["divider_preset"] = req.divider_preset
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

        # Push current game state immediately with new settings
        if inst.game and inst.game.get("last_info"):
            info = inst.game["last_info"]
            league = inst.game["league"]
            try:
                await inst.controller.set_game_mode(
                    home_win_pct=info.home_win_pct,
                    home_colors=get_team_colors(league, info.home_team),
                    away_colors=get_team_colors(league, info.away_team),
                )
                inst.record_success()
            except Exception as e:
                inst.record_failure(str(e))
                logger.warning(f"[SETTINGS] {host}: Failed to push update: {e}")

    await broadcast_state()
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
    inst = state.instances[host]
    inst.ui_state = compute_ui_state(inst)
    await broadcast_state()
    return result


class PostGameRequest(BaseModel):
    celebration: str  # freeze | chase | twinkle | flash | solid
    celebration_duration_s: int = 60
    after_action: str  # off | fade_off | restore | preset
    preset_id: int | None = None


@app.post("/api/instance/{host}/post_game")
async def set_post_game(host: str, req: PostGameRequest):
    """Set post-game celebration settings for a specific WLED instance."""
    if host not in state.instances:
        raise HTTPException(404, f"Unknown instance: {host}")

    settings = {
        "celebration": req.celebration,
        "celebration_duration_s": req.celebration_duration_s,
        "after_action": req.after_action,
    }
    if req.preset_id is not None:
        settings["preset_id"] = req.preset_id

    result = update_instance_post_game_settings(host, settings)
    await broadcast_state()
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
        return {"status": "already_simulating", "host": host, "state": inst.ui_state.value}

    # Warn if watching a live game (but allow it)
    warning = None
    previous_state = inst.ui_state
    if inst.game is not None:
        warning = "Instance is watching a live game - simulator will override"

    # Create controller if needed
    if not inst.controller:
        config = build_wled_config(inst.host, inst.start, inst.end)
        inst.controller = WLEDController(config)

    # Save current preset before simulator takes over
    try:
        inst.sim_saved_preset = await inst.controller.get_current_preset()
        inst.record_success()
        logger.info(f"[SIM] {host}: Started sim mode, saved preset {inst.sim_saved_preset}")
    except Exception as e:
        inst.record_failure(str(e))
        logger.warning(f"[SIM] {host}: Could not save preset: {e}")

    inst.simulating = True
    inst.ui_state = UIState.SIMULATING
    logger.info(f"[STATE] {host}: → SIMULATING (was {previous_state.value})")

    # Turn on WLED with neutral 50/50 display (gray teams)
    # This ensures the lights come on immediately
    try:
        await inst.controller.set_game_mode(
            home_win_pct=0.5,
            home_colors=[[100, 100, 100], [60, 60, 60]],
            away_colors=[[100, 100, 100], [60, 60, 60]],
        )
        inst.record_success()
    except Exception as e:
        inst.record_failure(str(e))

    result = {"status": "simulating", "host": host, "saved_preset": inst.sim_saved_preset, "state": inst.ui_state.value}
    if warning:
        result["warning"] = warning
    await broadcast_state()
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
        return {"status": "not_simulating", "host": host, "state": inst.ui_state.value}

    # Restore saved preset
    try:
        if inst.controller and inst.sim_saved_preset is not None:
            logger.info(f"[SIM] {host}: Stopping sim, restoring preset {inst.sim_saved_preset}")
            await inst.controller.restore_preset(inst.sim_saved_preset)
        elif inst.controller:
            logger.info(f"[SIM] {host}: Stopping sim, no preset to restore - turning off")
            await inst.controller.turn_off()
        inst.record_success()
    except Exception as e:
        inst.record_failure(str(e))
        logger.error(f"[SIM] {host}: Error restoring preset: {e}")

    inst.simulating = False
    inst.sim_saved_preset = None
    inst.display = None
    inst.win_pct_history.clear()

    # Recompute state (returns to previous watching state or idle)
    inst.ui_state = compute_ui_state(inst)
    logger.info(f"[STATE] {host}: → {inst.ui_state.value} (sim stopped)")

    await broadcast_state()
    return {"status": "stopped", "host": host, "state": inst.ui_state.value}


@app.get("/api/status")
async def get_status():
    """Get current status summary across all instances."""
    active_instances = [i for i in state.instances.values() if i.game]

    result = {
        "instances_active": len(active_instances),
        "instances_total": len(state.instances),
    }

    # Include first active instance's game info for convenience
    if active_instances:
        inst = active_instances[0]
        info = inst.game.get("last_info") if inst.game else None
        result["game_id"] = inst.game["game_id"] if inst.game else None
        result["state"] = inst.ui_state.value

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


@app.get("/api/health")
async def health_check():
    """Health endpoint — checks ESPN client, background tasks, and config."""
    checks = {}

    # ESPN client alive
    checks["espn_client"] = state.espn is not None

    # Background tasks alive (not done = still running)
    checks["poll_task"] = state.poll_task is not None and not state.poll_task.done()
    checks["auto_watch_task"] = state.auto_watch_task is not None and not state.auto_watch_task.done()

    # Config loaded
    checks["config_loaded"] = len(get_settings()) > 0

    # Instances initialized
    checks["instances"] = len(state.instances)

    healthy = all([checks["espn_client"], checks["poll_task"], checks["auto_watch_task"], checks["config_loaded"]])

    if not healthy:
        return JSONResponse(status_code=503, content={"healthy": False, **checks})

    return {"healthy": True, **checks}


class SimSettings(BaseModel):
    min_team_pct: float | None = None
    dark_buffer_pixels: int | None = None
    contested_zone_pixels: int | None = None
    divider_preset: str | None = None
    chase_speed: int | None = None
    chase_intensity: int | None = None


class TestRequest(BaseModel):
    pct: int = Field(ge=0, le=100)
    league: str = "nfl"
    home: str = "GB"
    away: str = "CHI"
    host: str | None = None  # Specific instance, or all if None
    settings: SimSettings | None = None  # Override display settings for simulation
    home_score: int | None = None  # For demo mode
    away_score: int | None = None
    period: str | None = None


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

        # Populate unified display payload
        if inst.simulating:
            inst.display = {
                "league": req.league,
                "home_team": req.home,
                "away_team": req.away,
                "home_display": get_team_display(req.league, req.home),
                "away_display": get_team_display(req.league, req.away),
                "home_colors": home_colors,
                "away_colors": away_colors,
                "home_win_pct": req.pct / 100,
                "period": req.period or "SIM",
                "home_score": req.home_score,
                "away_score": req.away_score,
            }
            inst.win_pct_history.append({"t": time.time(), "pct": req.pct / 100})

    await broadcast_state()
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


# WebSocket endpoint for real-time updates
WS_IDLE_TIMEOUT = 300.0  # 5 minutes


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Authenticate before accepting — WebSocket inherits HTTPConnection
    if AUTH_ENABLED and check_auth(websocket) is None:
        await websocket.close(code=1008, reason="Authentication required")
        return

    accepted = await ws_manager.connect(websocket)
    if not accepted:
        return
    try:
        # Send initial state immediately on connect
        instances_data = await list_instances()
        await websocket.send_json({"type": "instances_update", "data": instances_data})
        # Keep connection alive — client can send pings, idle connections time out
        while True:
            await asyncio.wait_for(websocket.receive_text(), timeout=WS_IDLE_TIMEOUT)
    except TimeoutError:
        ws_manager.disconnect(websocket)
        try:
            await websocket.close(code=1000, reason="Idle timeout")
        except Exception:
            pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


# SPA fallback — must be AFTER all API routes
@app.get("/{path:path}")
async def spa_fallback(path: str):
    """Serve static assets or fall back to index.html for client-side routing."""
    file_path = os.path.realpath(os.path.join(STATIC_DIR, path))
    static_root = os.path.realpath(STATIC_DIR)
    if file_path.startswith(static_root) and os.path.isfile(file_path):
        return FileResponse(file_path)
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

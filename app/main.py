"""
Game Lights - Live ESPN win probability → WLED visualization.

FastAPI app with game picker UI and background polling.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from espn import ESPNClient, GameInfo
from wled import WLEDController, WLEDConfig
from teams import get_team_colors, get_team_display
from config import get_settings, get_leagues, reload_config


def build_wled_config(host: str, start: int, end: int) -> WLEDConfig:
    """Build WLEDConfig with display settings from config file."""
    display = get_settings().get("display", {})
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


# App state
class AppState:
    espn: Optional[ESPNClient] = None
    wled_controllers: list[WLEDController] = []  # Multiple WLED instances
    current_game: Optional[dict] = None
    poll_task: Optional[asyncio.Task] = None


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    state.espn = ESPNClient()
    state.wled_controllers = []
    yield
    # Shutdown
    if state.poll_task:
        state.poll_task.cancel()
    if state.espn:
        await state.espn.close()
    for wled in state.wled_controllers:
        await wled.close()


app = FastAPI(title="Game Lights", lifespan=lifespan)


# Request/Response models
class WLEDInstance(BaseModel):
    host: str
    start: int = 0
    end: int = 629


class WatchRequest(BaseModel):
    league: str
    game_id: str
    wled_instances: list[WLEDInstance] = []


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
async def poll_game():
    """Background task to poll ESPN and update all WLED instances."""
    while True:
        try:
            if state.current_game and state.espn and state.wled_controllers:
                league = state.current_game["league"]
                game_id = state.current_game["game_id"]
                sport = get_leagues().get(league, {}).get("sport", "football")

                game = await state.espn.get_game_detail(sport, league, game_id)

                if game:
                    state.current_game["last_info"] = game

                    # Get colors
                    home_colors = get_team_colors(league, game.home_team)
                    away_colors = get_team_colors(league, game.away_team)

                    # Update all WLED instances
                    for wled in state.wled_controllers:
                        await wled.set_game_mode(
                            home_win_pct=game.home_win_pct,
                            home_colors=home_colors,
                            away_colors=away_colors,
                        )

                    print(f"Updated {len(state.wled_controllers)} instance(s): "
                          f"{game.away_team} @ {game.home_team} | "
                          f"{game.away_score}-{game.home_score} | "
                          f"Home win: {game.home_win_pct:.1%}")

        except Exception as e:
            print(f"Poll error: {e}")

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
    """Hot-reload config from disk."""
    result = reload_config()
    return {"status": "reloaded", **result}


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


@app.post("/api/watch")
async def watch_game(req: WatchRequest):
    """Start watching a game."""
    # Stop existing poll
    if state.poll_task:
        state.poll_task.cancel()
        try:
            await state.poll_task
        except asyncio.CancelledError:
            pass

    # Close existing WLED controllers
    for wled in state.wled_controllers:
        await wled.close()

    # Use request instances, or fall back to config
    instances = req.wled_instances
    if not instances:
        settings = get_settings()
        instances = [
            WLEDInstance(host=i["host"], start=i.get("start", 0), end=i.get("end", 629))
            for i in settings.get("wled_instances", [])
        ]

    if not instances:
        raise HTTPException(400, "No WLED instances configured (check config/settings.yaml)")

    # Create new WLED controllers
    state.wled_controllers = []
    for instance in instances:
        config = build_wled_config(instance.host, instance.start, instance.end)
        state.wled_controllers.append(WLEDController(config))

    state.current_game = {
        "league": req.league,
        "game_id": req.game_id,
        "last_info": None,
    }

    # Start polling
    state.poll_task = asyncio.create_task(poll_game())

    return {"status": "watching", "game_id": req.game_id}


@app.post("/api/stop")
async def stop_watching():
    """Stop watching and turn off lights."""
    if state.poll_task:
        state.poll_task.cancel()
        try:
            await state.poll_task
        except asyncio.CancelledError:
            pass
        state.poll_task = None

    state.current_game = None

    # Turn off all WLED instances
    for wled in state.wled_controllers:
        await wled.turn_off()

    return {"status": "stopped"}


@app.get("/api/status")
async def get_status() -> GameStatus:
    """Get current watching status."""
    if not state.current_game:
        return GameStatus(watching=False)

    info = state.current_game.get("last_info")
    if not info:
        return GameStatus(
            watching=True,
            game_id=state.current_game["game_id"],
        )

    return GameStatus(
        watching=True,
        game_id=state.current_game["game_id"],
        home_team=info.home_team,
        away_team=info.away_team,
        home_score=info.home_score,
        away_score=info.away_score,
        home_win_pct=info.home_win_pct,
        period=info.period,
    )


class TestRequest(BaseModel):
    pct: int
    league: str = "nfl"
    home: str = "GB"
    away: str = "CHI"
    wled_instances: list[WLEDInstance] = []


@app.post("/api/test")
async def test_percentage(req: TestRequest):
    """Test mode: manually set win percentage (0-100) with custom teams."""
    # Use request instances, or fall back to config
    instances = req.wled_instances
    if not instances:
        settings = get_settings()
        instances = [
            WLEDInstance(host=i["host"], start=i.get("start", 0), end=i.get("end", 629))
            for i in settings.get("wled_instances", [])
        ]

    if not instances:
        raise HTTPException(400, "No WLED instances configured (check config/settings.yaml)")

    home_colors = get_team_colors(req.league, req.home)
    away_colors = get_team_colors(req.league, req.away)

    # Create temporary controllers for test
    for instance in instances:
        config = build_wled_config(instance.host, instance.start, instance.end)
        controller = WLEDController(config)
        await controller.set_game_mode(
            home_win_pct=req.pct / 100,
            home_colors=home_colors,
            away_colors=away_colors,
        )
        await controller.close()

    return {"status": "ok", "pct": req.pct, "home": req.home, "away": req.away}


# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

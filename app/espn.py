"""
ESPN API client for fetching live game data and win probabilities.
"""

import httpx
from typing import Optional
from dataclasses import dataclass
from datetime import datetime


ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"


@dataclass
class GameInfo:
    """Represents a live game with win probability data."""
    game_id: str
    status: str  # "pre", "in", "post"
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    home_win_pct: float  # 0.0 to 1.0
    away_win_pct: float  # 0.0 to 1.0
    period: str
    clock: str
    last_play: Optional[str] = None


class ESPNClient:
    """Client for ESPN's semi-public API."""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)

    async def close(self):
        await self.client.aclose()

    async def get_scoreboard(self, sport: str, league: str) -> list[dict]:
        """
        Get current scoreboard for a sport/league.

        Args:
            sport: "football", "basketball", "baseball", "hockey"
            league: "nfl", "nba", "mlb", "nhl", "college-football"

        Returns:
            List of game summary dicts
        """
        url = f"{ESPN_BASE}/{sport}/{league}/scoreboard"

        try:
            resp = await self.client.get(url)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"ESPN scoreboard error: {e}")
            return []

        games = []
        for event in data.get("events", []):
            competition = event.get("competitions", [{}])[0]
            competitors = competition.get("competitors", [])

            if len(competitors) < 2:
                continue

            home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
            away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

            games.append({
                "id": event.get("id"),
                "name": event.get("name"),
                "status": event.get("status", {}).get("type", {}).get("state", "unknown"),
                "detail": event.get("status", {}).get("type", {}).get("detail", ""),
                "home_team": home.get("team", {}).get("abbreviation", "???"),
                "away_team": away.get("team", {}).get("abbreviation", "???"),
                "home_score": int(home.get("score", 0) or 0),
                "away_score": int(away.get("score", 0) or 0),
            })

        return games

    async def get_game_detail(self, sport: str, league: str, game_id: str) -> Optional[GameInfo]:
        """
        Get detailed game info including win probability.

        Win probability comes from the play-by-play or summary endpoint.
        """
        # Try summary endpoint first (has winprobability for some games)
        url = f"{ESPN_BASE}/{sport}/{league}/summary?event={game_id}"

        try:
            resp = await self.client.get(url)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"ESPN game detail error: {e}")
            return None

        # Extract basic info
        header = data.get("header", {})
        competitions = header.get("competitions", [{}])
        if not competitions:
            return None

        competition = competitions[0]
        competitors = competition.get("competitors", [])

        if len(competitors) < 2:
            return None

        home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

        # Get status
        status_data = competition.get("status", {}) or header.get("status", {})
        status_type = status_data.get("type", {})

        # Extract win probability
        # ESPN puts this in different places depending on sport/game state
        win_prob = data.get("winprobability", [])
        home_win_pct = 0.5  # Default to even

        if win_prob:
            # Get most recent probability
            latest = win_prob[-1] if isinstance(win_prob, list) else win_prob
            home_win_pct = latest.get("homeWinPercentage", 0.5)
        else:
            # Try predictor data
            predictor = data.get("predictor", {})
            home_win_pct = predictor.get("homeTeam", {}).get("gameProjection", 50) / 100

        # Get last play if available
        last_play = None
        plays = data.get("drives", {}).get("current", {}).get("plays", [])
        if plays:
            last_play = plays[-1].get("text")

        return GameInfo(
            game_id=game_id,
            status=status_type.get("state", "unknown"),
            home_team=home.get("team", {}).get("abbreviation", "???"),
            away_team=away.get("team", {}).get("abbreviation", "???"),
            home_score=int(home.get("score", 0) or 0),
            away_score=int(away.get("score", 0) or 0),
            home_win_pct=home_win_pct,
            away_win_pct=1.0 - home_win_pct,
            period=status_type.get("detail", ""),
            clock=status_data.get("displayClock", ""),
            last_play=last_play,
        )


# Singleton for convenience
_client: Optional[ESPNClient] = None


async def get_client() -> ESPNClient:
    global _client
    if _client is None:
        _client = ESPNClient()
    return _client

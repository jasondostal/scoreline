"""
Team color definitions for Scoreline.
Loaded from YAML config files.
"""

from config import get_leagues


def get_team_colors(league: str, team_abbr: str) -> list:
    """Get [primary, secondary] colors for a team."""
    leagues = get_leagues()
    league_data = leagues.get(league.lower(), {})
    teams = league_data.get("teams", {})
    team = teams.get(team_abbr.upper(), {})
    return team.get("colors", [[128, 128, 128], [64, 64, 64]])  # Gray fallback


def get_team_display(league: str, team_abbr: str) -> str:
    """Get display name for a team."""
    leagues = get_leagues()
    league_data = leagues.get(league.lower(), {})
    teams = league_data.get("teams", {})
    team = teams.get(team_abbr.upper(), {})
    return team.get("display", team_abbr)

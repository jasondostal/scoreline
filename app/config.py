"""
YAML-based configuration for Scoreline.
Loads settings from user config, leagues from user config or built-in defaults.
"""

import os
from pathlib import Path
from typing import Any
import yaml

# User config directory (mounted volume)
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", "/app/config"))

# Built-in defaults (baked into container)
DEFAULTS_DIR = Path(os.environ.get("DEFAULTS_DIR", "/app/defaults"))


def _load_yaml(path: Path) -> dict:
    """Load a YAML file, return empty dict if missing."""
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_settings() -> dict:
    """Load settings.yaml - WLED instances, poll interval, etc."""
    settings = _load_yaml(CONFIG_DIR / "settings.yaml")

    # Display settings with defaults
    display = settings.get("display", {})
    display_settings = {
        "divider_color": display.get("divider_color", [200, 80, 0]),
        "min_team_pct": display.get("min_team_pct", 0.05),
        "contested_zone_pixels": display.get("contested_zone_pixels", 6),
        "dark_buffer_pixels": display.get("dark_buffer_pixels", 4),
        "transition_ms": display.get("transition_ms", 500),
        "chase_speed": display.get("chase_speed", 185),
        "chase_intensity": display.get("chase_intensity", 190),
    }

    return {
        "wled_instances": settings.get("wled_instances", []),
        "poll_interval": settings.get("poll_interval", 30),
        "default_league": settings.get("default_league", None),
        "display": display_settings,
    }


def load_leagues() -> dict:
    """Load league YAML files. User config overlays built-in defaults."""
    leagues = {}

    # Load built-in defaults first
    defaults_dir = DEFAULTS_DIR / "leagues"
    if defaults_dir.exists():
        for yaml_file in defaults_dir.glob("*.yaml"):
            league_id = yaml_file.stem
            data = _load_yaml(yaml_file)
            if data:
                leagues[league_id] = {
                    "name": data.get("name", league_id.upper()),
                    "sport": data.get("sport", "football"),
                    "espn_league": data.get("espn_league"),  # For MLS etc.
                    "teams": data.get("teams", {}),
                }

    # User config overlays/extends defaults
    user_dir = CONFIG_DIR / "leagues"
    if user_dir.exists():
        for yaml_file in user_dir.glob("*.yaml"):
            league_id = yaml_file.stem
            data = _load_yaml(yaml_file)
            if data:
                leagues[league_id] = {
                    "name": data.get("name", league_id.upper()),
                    "sport": data.get("sport", "football"),
                    "espn_league": data.get("espn_league"),
                    "teams": data.get("teams", {}),
                }

    return leagues


# Cached data - loaded once at startup, can be reloaded
_settings: dict = None
_leagues: dict = None


def get_settings() -> dict:
    """Get settings (cached)."""
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def get_leagues() -> dict:
    """Get leagues (cached)."""
    global _leagues
    if _leagues is None:
        _leagues = load_leagues()
    return _leagues


def reload_config():
    """Reload all config from disk."""
    global _settings, _leagues
    _settings = load_settings()
    _leagues = load_leagues()
    return {"settings": _settings, "leagues": list(_leagues.keys())}


def add_wled_instance(host: str, start: int = 0, end: int = 300) -> dict:
    """
    Add a WLED instance to settings.yaml.

    Returns the updated settings.
    """
    global _settings

    settings_path = CONFIG_DIR / "settings.yaml"

    # Load raw settings (not the processed version)
    raw_settings = _load_yaml(settings_path)

    # Ensure wled_instances exists
    if "wled_instances" not in raw_settings:
        raw_settings["wled_instances"] = []

    # Check if already exists
    for inst in raw_settings["wled_instances"]:
        if inst.get("host") == host:
            return {"status": "exists", "message": f"{host} already configured"}

    # Add new instance
    raw_settings["wled_instances"].append({
        "host": host,
        "start": start,
        "end": end,
    })

    # Write back
    with open(settings_path, "w") as f:
        yaml.dump(raw_settings, f, default_flow_style=False, sort_keys=False)

    # Reload cache
    _settings = load_settings()

    return {"status": "added", "message": f"{host} added to config"}

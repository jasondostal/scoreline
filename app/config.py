"""
YAML-based configuration for Game Lights.
Loads settings and leagues from config/ directory.
"""

import os
from pathlib import Path
from typing import Any
import yaml

# Config directory - relative to app, or override with env var
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", "/app/config"))


def _load_yaml(path: Path) -> dict:
    """Load a YAML file, return empty dict if missing."""
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_settings() -> dict:
    """Load settings.yaml - WLED instances, poll interval, etc."""
    settings = _load_yaml(CONFIG_DIR / "settings.yaml")

    # Defaults
    return {
        "wled_instances": settings.get("wled_instances", []),
        "poll_interval": settings.get("poll_interval", 30),
        "default_league": settings.get("default_league", None),
    }


def load_leagues() -> dict:
    """Load all league YAML files from config/leagues/."""
    leagues_dir = CONFIG_DIR / "leagues"
    leagues = {}

    if not leagues_dir.exists():
        return leagues

    for yaml_file in leagues_dir.glob("*.yaml"):
        league_id = yaml_file.stem  # filename without extension
        data = _load_yaml(yaml_file)

        if data:
            leagues[league_id] = {
                "name": data.get("name", league_id.upper()),
                "sport": data.get("sport", "football"),
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

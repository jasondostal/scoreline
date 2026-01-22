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
        "divider_preset": display.get("divider_preset", "classic"),
        "min_team_pct": display.get("min_team_pct", 0.05),
        "contested_zone_pixels": display.get("contested_zone_pixels", 6),
        "dark_buffer_pixels": display.get("dark_buffer_pixels", 4),
        "transition_ms": display.get("transition_ms", 500),
        "chase_speed": display.get("chase_speed", 185),
        "chase_intensity": display.get("chase_intensity", 190),
    }

    # Post-game settings with defaults
    post_game = settings.get("post_game", {})
    post_game_settings = {
        "action": post_game.get("action", "flash_then_off"),  # off | fade_off | flash_then_off | restore | preset
        "flash_count": post_game.get("flash_count", 3),
        "flash_duration_ms": post_game.get("flash_duration_ms", 500),
        "fade_duration_s": post_game.get("fade_duration_s", 3),
        "preset_id": post_game.get("preset_id"),  # For action: preset
    }

    # Simulator defaults
    simulator = settings.get("simulator", {})
    simulator_settings = {
        "league": simulator.get("league", "nfl"),
        "home": simulator.get("home", "GB"),
        "away": simulator.get("away", "CHI"),
        "win_pct": simulator.get("win_pct", 50),
    }

    return {
        "wled_instances": settings.get("wled_instances", []),
        "poll_interval": settings.get("poll_interval", 30),
        "auto_watch_interval": settings.get("auto_watch_interval", 300),  # 5 min default
        "display": display_settings,
        "post_game": post_game_settings,
        "simulator": simulator_settings,
    }


def get_instance_watch_teams(host: str) -> list[str]:
    """
    Get watch_teams for a specific instance.
    Returns list of "league:team" strings, e.g. ["nfl:GB", "nba:MIL"]
    """
    settings_path = CONFIG_DIR / "settings.yaml"
    raw_settings = _load_yaml(settings_path)

    for inst in raw_settings.get("wled_instances", []):
        if inst.get("host") == host:
            return inst.get("watch_teams", [])
    return []


def get_all_watched_teams() -> dict[str, list[tuple[str, str]]]:
    """
    Get all watched teams across all instances.
    Returns dict of league -> [(team, host), ...] for efficient scoreboard scanning.
    """
    settings_path = CONFIG_DIR / "settings.yaml"
    raw_settings = _load_yaml(settings_path)

    watched: dict[str, list[tuple[str, str]]] = {}

    for inst in raw_settings.get("wled_instances", []):
        host = inst.get("host")
        for team_spec in inst.get("watch_teams", []):
            if ":" in team_spec:
                league, team = team_spec.split(":", 1)
                if league not in watched:
                    watched[league] = []
                watched[league].append((team.upper(), host))

    return watched


def update_instance_watch_teams(host: str, watch_teams: list[str]) -> dict:
    """
    Update watch_teams for a specific WLED instance.
    """
    global _settings

    settings_path = CONFIG_DIR / "settings.yaml"
    raw_settings = _load_yaml(settings_path)

    if "wled_instances" not in raw_settings:
        return {"status": "error", "message": "No instances configured"}

    found = False
    for inst in raw_settings["wled_instances"]:
        if inst.get("host") == host:
            inst["watch_teams"] = watch_teams
            found = True
            break

    if not found:
        return {"status": "error", "message": f"Instance {host} not found"}

    # Write back
    with open(settings_path, "w") as f:
        yaml.dump(raw_settings, f, default_flow_style=False, sort_keys=False)

    # Reload cache
    _settings = load_settings()

    return {"status": "updated", "watch_teams": watch_teams}


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


def remove_wled_instance(host: str) -> dict:
    """
    Remove a WLED instance from settings.yaml.

    Returns status of the operation.
    """
    global _settings

    settings_path = CONFIG_DIR / "settings.yaml"
    raw_settings = _load_yaml(settings_path)

    if "wled_instances" not in raw_settings:
        return {"status": "error", "message": "No instances configured"}

    # Find and remove the instance
    original_len = len(raw_settings["wled_instances"])
    raw_settings["wled_instances"] = [
        inst for inst in raw_settings["wled_instances"]
        if inst.get("host") != host
    ]

    if len(raw_settings["wled_instances"]) == original_len:
        return {"status": "error", "message": f"{host} not found in config"}

    # Write back
    with open(settings_path, "w") as f:
        yaml.dump(raw_settings, f, default_flow_style=False, sort_keys=False)

    # Reload cache
    _settings = load_settings()

    return {"status": "removed", "message": f"{host} removed from config"}


def update_wled_instance(host: str, new_host: str = None, start: int = None, end: int = None) -> dict:
    """
    Update core properties of a WLED instance (host, start, end).

    If host changes, updates the key in settings.yaml.
    Returns status of the operation.
    """
    global _settings

    settings_path = CONFIG_DIR / "settings.yaml"
    raw_settings = _load_yaml(settings_path)

    if "wled_instances" not in raw_settings:
        return {"status": "error", "message": "No instances configured"}

    # Find the instance
    found_idx = None
    for idx, inst in enumerate(raw_settings["wled_instances"]):
        if inst.get("host") == host:
            found_idx = idx
            break

    if found_idx is None:
        return {"status": "error", "message": f"Instance {host} not found"}

    # Check if new_host already exists (if changing host)
    if new_host and new_host != host:
        for inst in raw_settings["wled_instances"]:
            if inst.get("host") == new_host:
                return {"status": "error", "message": f"{new_host} already configured"}

    # Update the instance
    inst = raw_settings["wled_instances"][found_idx]
    if new_host:
        inst["host"] = new_host
    if start is not None:
        inst["start"] = start
    if end is not None:
        inst["end"] = end

    # Write back
    with open(settings_path, "w") as f:
        yaml.dump(raw_settings, f, default_flow_style=False, sort_keys=False)

    # Reload cache
    _settings = load_settings()

    return {
        "status": "updated",
        "old_host": host,
        "new_host": new_host or host,
        "start": inst.get("start"),
        "end": inst.get("end")
    }


def update_instance_settings(host: str, display_settings: dict) -> dict:
    """
    Update display settings for a specific WLED instance.

    Adds a 'display' section to the instance in settings.yaml for per-instance overrides.
    """
    global _settings

    settings_path = CONFIG_DIR / "settings.yaml"
    raw_settings = _load_yaml(settings_path)

    if "wled_instances" not in raw_settings:
        return {"status": "error", "message": "No instances configured"}

    # Find the instance
    found = False
    for inst in raw_settings["wled_instances"]:
        if inst.get("host") == host:
            # Initialize or update display section
            if "display" not in inst:
                inst["display"] = {}
            inst["display"].update(display_settings)
            found = True
            break

    if not found:
        return {"status": "error", "message": f"Instance {host} not found"}

    # Write back
    with open(settings_path, "w") as f:
        yaml.dump(raw_settings, f, default_flow_style=False, sort_keys=False)

    # Reload cache
    _settings = load_settings()

    return {"status": "updated", "settings": display_settings}


def get_instance_display_settings(host: str) -> dict:
    """
    Get display settings for a specific instance, with fallback to global.
    """
    settings = get_settings()
    global_display = settings.get("display", {})

    # Find instance-specific settings
    for inst in settings.get("wled_instances", []):
        if inst.get("host") == host:
            inst_display = inst.get("display", {})
            # Merge: instance overrides global
            return {
                "min_team_pct": inst_display.get("min_team_pct", global_display.get("min_team_pct", 0.05)),
                "contested_zone_pixels": inst_display.get("contested_zone_pixels", global_display.get("contested_zone_pixels", 6)),
                "dark_buffer_pixels": inst_display.get("dark_buffer_pixels", global_display.get("dark_buffer_pixels", 4)),
                "transition_ms": inst_display.get("transition_ms", global_display.get("transition_ms", 500)),
                "chase_speed": inst_display.get("chase_speed", global_display.get("chase_speed", 185)),
                "chase_intensity": inst_display.get("chase_intensity", global_display.get("chase_intensity", 190)),
                "divider_color": inst_display.get("divider_color", global_display.get("divider_color", [200, 80, 0])),
                "divider_preset": inst_display.get("divider_preset", global_display.get("divider_preset", "default")),
            }

    # Fallback to global
    return global_display


def update_instance_post_game_settings(host: str, post_game_settings: dict) -> dict:
    """
    Update post-game settings for a specific WLED instance.
    """
    global _settings

    settings_path = CONFIG_DIR / "settings.yaml"
    raw_settings = _load_yaml(settings_path)

    if "wled_instances" not in raw_settings:
        return {"status": "error", "message": "No instances configured"}

    found = False
    for inst in raw_settings["wled_instances"]:
        if inst.get("host") == host:
            if "post_game" not in inst:
                inst["post_game"] = {}
            inst["post_game"].update(post_game_settings)
            found = True
            break

    if not found:
        return {"status": "error", "message": f"Instance {host} not found"}

    # Write back
    with open(settings_path, "w") as f:
        yaml.dump(raw_settings, f, default_flow_style=False, sort_keys=False)

    # Reload cache
    _settings = load_settings()

    return {"status": "updated", "post_game": post_game_settings}


def get_instance_post_game_settings(host: str) -> dict:
    """
    Get post-game settings for a specific instance, with fallback to global.
    """
    settings = get_settings()
    global_post_game = settings.get("post_game", {})

    # Load raw settings to check for per-instance overrides
    settings_path = CONFIG_DIR / "settings.yaml"
    raw_settings = _load_yaml(settings_path)

    # Find instance-specific settings
    for inst in raw_settings.get("wled_instances", []):
        if inst.get("host") == host:
            inst_post_game = inst.get("post_game", {})
            # Merge: instance overrides global
            return {
                "action": inst_post_game.get("action", global_post_game.get("action", "flash_then_off")),
                "flash_count": inst_post_game.get("flash_count", global_post_game.get("flash_count", 3)),
                "flash_duration_ms": inst_post_game.get("flash_duration_ms", global_post_game.get("flash_duration_ms", 500)),
                "fade_duration_s": inst_post_game.get("fade_duration_s", global_post_game.get("fade_duration_s", 3)),
                "preset_id": inst_post_game.get("preset_id", global_post_game.get("preset_id")),
            }

    # Fallback to global
    return global_post_game


def get_simulator_defaults() -> dict:
    """Get saved simulator defaults."""
    return get_settings().get("simulator", {
        "league": "nfl",
        "home": "GB",
        "away": "CHI",
        "win_pct": 50,
    })


def update_simulator_defaults(simulator_settings: dict) -> dict:
    """
    Update simulator defaults in settings.yaml.
    """
    global _settings

    settings_path = CONFIG_DIR / "settings.yaml"
    raw_settings = _load_yaml(settings_path)

    # Update simulator section
    if "simulator" not in raw_settings:
        raw_settings["simulator"] = {}
    raw_settings["simulator"].update(simulator_settings)

    # Write back
    with open(settings_path, "w") as f:
        yaml.dump(raw_settings, f, default_flow_style=False, sort_keys=False)

    # Reload cache
    _settings = load_settings()

    return {"status": "updated", "simulator": raw_settings["simulator"]}

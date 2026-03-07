"""Test 4: Config reload preserves running state.

Verifies init_instances preserves active games, adds new instances,
removes deleted ones, and recomputes UI state.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml

from config import (
    _atomic_yaml_write,
    _load_yaml,
    load_settings,
)


class TestLoadSettings:
    """Config loading with defaults."""

    def test_defaults_on_empty(self):
        """Empty settings should produce sensible defaults."""
        with patch("config._load_yaml", return_value={}):
            settings = load_settings()
            assert settings["poll_interval"] == 30
            assert settings["auto_watch_interval"] == 300
            assert isinstance(settings["display"], dict)
            assert settings["display"]["min_team_pct"] == 0.05
            assert settings["wled_instances"] == []

    def test_custom_values_override(self):
        raw = {
            "poll_interval": 10,
            "wled_instances": [{"host": "10.0.0.1", "start": 0, "end": 150}],
            "display": {"min_team_pct": 0.10, "transition_ms": 200},
        }
        with patch("config._load_yaml", return_value=raw):
            settings = load_settings()
            assert settings["poll_interval"] == 10
            assert len(settings["wled_instances"]) == 1
            assert settings["display"]["min_team_pct"] == 0.10
            assert settings["display"]["transition_ms"] == 200
            # Other display defaults still present
            assert settings["display"]["chase_speed"] == 185


class TestAtomicWrite:
    """Verify atomic YAML writes."""

    def test_atomic_write_creates_file(self, tmp_path):
        target = tmp_path / "test.yaml"
        data = {"key": "value", "number": 42}
        _atomic_yaml_write(target, data)

        result = yaml.safe_load(target.read_text())
        assert result == data

    def test_atomic_write_overwrites(self, tmp_path):
        target = tmp_path / "test.yaml"
        target.write_text("old: data\n")

        _atomic_yaml_write(target, {"new": "data"})
        result = yaml.safe_load(target.read_text())
        assert result == {"new": "data"}

    def test_no_temp_files_left_on_success(self, tmp_path):
        target = tmp_path / "test.yaml"
        _atomic_yaml_write(target, {"a": 1})

        files = list(tmp_path.iterdir())
        assert len(files) == 1
        assert files[0].name == "test.yaml"


class TestLoadYaml:
    """_load_yaml edge cases."""

    def test_missing_file_returns_empty(self, tmp_path):
        result = _load_yaml(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_empty_file_returns_empty(self, tmp_path):
        f = tmp_path / "empty.yaml"
        f.write_text("")
        result = _load_yaml(f)
        assert result == {}

    def test_valid_yaml(self, tmp_path):
        f = tmp_path / "valid.yaml"
        f.write_text("key: value\nlist:\n  - a\n  - b\n")
        result = _load_yaml(f)
        assert result == {"key": "value", "list": ["a", "b"]}


class TestInitInstances:
    """Test that init_instances preserves state across reloads."""

    def test_preserves_existing_game(self, mock_watch_teams):
        """Active game should survive config reload."""
        from main import InstanceState, UIState, init_instances, state

        mock_watch_teams.return_value = []

        # Set up initial state with an active game
        inst = InstanceState(host="10.0.0.1", start=0, end=300)
        inst.game = {"league": "nfl", "game_id": "401", "last_info": None, "last_status": "in"}
        inst.watch_trigger = "manual"
        inst.ui_state = UIState.WATCHING_MANUAL
        state.instances = {"10.0.0.1": inst}

        # Reload with same instance in config
        with patch("main.get_settings", return_value={
            "wled_instances": [{"host": "10.0.0.1", "start": 0, "end": 300}],
        }):
            init_instances()

        # Game state should be preserved
        assert "10.0.0.1" in state.instances
        assert state.instances["10.0.0.1"].game is not None
        assert state.instances["10.0.0.1"].game["game_id"] == "401"

    def test_adds_new_instance(self, mock_watch_teams):
        """New instance in config should be created."""
        from main import InstanceState, init_instances, state

        mock_watch_teams.return_value = []
        state.instances = {}

        with patch("main.get_settings", return_value={
            "wled_instances": [{"host": "10.0.0.2", "start": 0, "end": 150}],
        }):
            init_instances()

        assert "10.0.0.2" in state.instances
        assert state.instances["10.0.0.2"].end == 150

    def test_removes_deleted_instance(self, mock_watch_teams):
        """Instance removed from config should be removed from state."""
        from main import InstanceState, init_instances, state

        mock_watch_teams.return_value = []
        state.instances = {
            "10.0.0.1": InstanceState(host="10.0.0.1", start=0, end=300),
            "10.0.0.2": InstanceState(host="10.0.0.2", start=0, end=150),
        }

        with patch("main.get_settings", return_value={
            "wled_instances": [{"host": "10.0.0.1", "start": 0, "end": 300}],
        }):
            init_instances()

        assert "10.0.0.1" in state.instances
        assert "10.0.0.2" not in state.instances

    def test_updates_start_end_on_reload(self, mock_watch_teams):
        """Changed start/end values should be updated."""
        from main import InstanceState, init_instances, state

        mock_watch_teams.return_value = []
        state.instances = {
            "10.0.0.1": InstanceState(host="10.0.0.1", start=0, end=300),
        }

        with patch("main.get_settings", return_value={
            "wled_instances": [{"host": "10.0.0.1", "start": 50, "end": 250}],
        }):
            init_instances()

        assert state.instances["10.0.0.1"].start == 50
        assert state.instances["10.0.0.1"].end == 250

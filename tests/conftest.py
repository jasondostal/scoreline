"""Shared fixtures for Scoreline tests."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add app/ to path so imports work like they do at runtime
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


@pytest.fixture
def instance_state():
    """Create a fresh InstanceState for testing."""
    from main import InstanceState
    return InstanceState(host="10.0.0.1", start=0, end=300)


@pytest.fixture
def mock_watch_teams():
    """Patch get_instance_watch_teams to return configurable teams."""
    with patch("main.get_instance_watch_teams") as mock:
        mock.return_value = []
        yield mock


@pytest.fixture
def wled_config():
    """Create a WLEDConfig with default test values."""
    from wled import WLEDConfig
    return WLEDConfig(host="10.0.0.1", roofline_start=0, roofline_end=300)


@pytest.fixture
def wled_controller(wled_config):
    """Create a WLEDController (no real HTTP calls)."""
    from wled import WLEDController
    return WLEDController(wled_config)

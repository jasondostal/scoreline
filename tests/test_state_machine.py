"""Test 1: State machine transition matrix.

Exercises every compute_ui_state path and verifies transition helpers.
Pure logic — no I/O, no mocks needed (except config lookup).
"""

import time

from main import (
    InstanceState,
    UIState,
    compute_ui_state,
    transition_to_final,
    transition_to_watching,
)
from espn import GameInfo


def _make_game(league="nfl", game_id="401", home="GB", away="CHI"):
    """Create a minimal game dict."""
    return {
        "league": league,
        "game_id": game_id,
        "last_info": GameInfo(
            game_id=game_id,
            status="in",
            home_team=home,
            away_team=away,
            home_score=14,
            away_score=7,
            home_win_pct=0.65,
            period="Q3",
            clock="5:30",
        ),
        "last_status": "in",
    }


class TestComputeUIState:
    """Every return path of compute_ui_state."""

    def test_idle_no_watch_teams(self, instance_state, mock_watch_teams):
        mock_watch_teams.return_value = []
        assert compute_ui_state(instance_state) == UIState.IDLE

    def test_idle_autowatch_with_watch_teams(self, instance_state, mock_watch_teams):
        mock_watch_teams.return_value = ["nfl:GB"]
        assert compute_ui_state(instance_state) == UIState.IDLE_AUTOWATCH

    def test_simulating_takes_priority(self, instance_state, mock_watch_teams):
        mock_watch_teams.return_value = ["nfl:GB"]
        instance_state.simulating = True
        instance_state.game = _make_game()
        assert compute_ui_state(instance_state) == UIState.SIMULATING

    def test_watching_auto(self, instance_state, mock_watch_teams):
        mock_watch_teams.return_value = ["nfl:GB"]
        instance_state.game = _make_game()
        instance_state.watch_trigger = "auto"
        assert compute_ui_state(instance_state) == UIState.WATCHING_AUTO

    def test_watching_manual_no_watch_teams(self, instance_state, mock_watch_teams):
        mock_watch_teams.return_value = []
        instance_state.game = _make_game()
        instance_state.watch_trigger = "manual"
        assert compute_ui_state(instance_state) == UIState.WATCHING_MANUAL

    def test_watching_manual_own_team(self, instance_state, mock_watch_teams):
        """Manual pick of a watched team = WATCHING_MANUAL (not override)."""
        mock_watch_teams.return_value = ["nfl:GB"]
        instance_state.game = _make_game(home="GB", away="CHI")
        instance_state.watch_trigger = "manual"
        assert compute_ui_state(instance_state) == UIState.WATCHING_MANUAL

    def test_watching_override_different_team(self, instance_state, mock_watch_teams):
        """Manual pick of a non-watched team = WATCHING_OVERRIDE."""
        mock_watch_teams.return_value = ["nfl:GB"]
        instance_state.game = _make_game(home="KC", away="SF")
        instance_state.watch_trigger = "manual"
        assert compute_ui_state(instance_state) == UIState.WATCHING_OVERRIDE

    def test_final_state_persists_during_linger(self, instance_state, mock_watch_teams):
        mock_watch_teams.return_value = []
        instance_state.ui_state = UIState.FINAL
        instance_state.final_linger_until = time.time() + 60  # 60s in the future
        assert compute_ui_state(instance_state) == UIState.FINAL

    def test_final_state_expires_to_idle(self, instance_state, mock_watch_teams):
        mock_watch_teams.return_value = []
        instance_state.ui_state = UIState.FINAL
        instance_state.final_linger_until = time.time() - 1  # Already expired
        assert compute_ui_state(instance_state) == UIState.IDLE

    def test_final_state_expires_to_idle_autowatch(self, instance_state, mock_watch_teams):
        mock_watch_teams.return_value = ["nfl:GB"]
        instance_state.ui_state = UIState.FINAL
        instance_state.final_linger_until = time.time() - 1
        assert compute_ui_state(instance_state) == UIState.IDLE_AUTOWATCH

    def test_watching_override_no_game_info(self, instance_state, mock_watch_teams):
        """Manual pick with watch teams but no game_info yet = OVERRIDE."""
        mock_watch_teams.return_value = ["nfl:GB"]
        instance_state.game = {"league": "nfl", "game_id": "401", "last_info": None, "last_status": "in"}
        instance_state.watch_trigger = "manual"
        assert compute_ui_state(instance_state) == UIState.WATCHING_OVERRIDE

    def test_away_team_match_is_manual(self, instance_state, mock_watch_teams):
        """Watching a game where our team is away = WATCHING_MANUAL."""
        mock_watch_teams.return_value = ["nfl:GB"]
        instance_state.game = _make_game(home="CHI", away="GB")
        instance_state.watch_trigger = "manual"
        assert compute_ui_state(instance_state) == UIState.WATCHING_MANUAL


class TestTransitionHelpers:
    """Test transition_to_watching and transition_to_final."""

    def test_transition_to_watching_sets_state(self, instance_state, mock_watch_teams):
        mock_watch_teams.return_value = []
        game = _make_game()
        transition_to_watching(instance_state, game, "manual")

        assert instance_state.game == game
        assert instance_state.watch_trigger == "manual"
        assert instance_state.final_linger_until is None
        assert instance_state.ui_state == UIState.WATCHING_MANUAL

    def test_transition_to_watching_auto(self, instance_state, mock_watch_teams):
        mock_watch_teams.return_value = ["nfl:GB"]
        game = _make_game()
        transition_to_watching(instance_state, game, "auto")

        assert instance_state.watch_trigger == "auto"
        assert instance_state.ui_state == UIState.WATCHING_AUTO

    def test_transition_to_final(self, instance_state, mock_watch_teams):
        mock_watch_teams.return_value = []
        instance_state.game = _make_game()
        transition_to_final(instance_state, linger_seconds=30)

        assert instance_state.ui_state == UIState.FINAL
        assert instance_state.final_linger_until is not None
        assert instance_state.final_linger_until > time.time()
        assert instance_state.final_game_info is not None

    def test_transition_clears_previous_state(self, instance_state, mock_watch_teams):
        """Transitioning to watching clears FINAL state artifacts."""
        mock_watch_teams.return_value = []
        instance_state.final_linger_until = time.time() + 100
        instance_state.final_game_info = {"some": "data"}

        game = _make_game()
        transition_to_watching(instance_state, game, "manual")

        assert instance_state.final_linger_until is None
        assert instance_state.final_game_info is None


class TestHealthStatus:
    """Test InstanceState health tracking."""

    def test_healthy_by_default(self, instance_state):
        assert instance_state.get_health_status().value == "healthy"

    def test_unreachable_after_three_failures(self, instance_state):
        instance_state.record_failure("timeout")
        instance_state.record_failure("timeout")
        instance_state.record_failure("timeout")
        assert instance_state.get_health_status().value == "unreachable"

    def test_success_resets_failures(self, instance_state):
        instance_state.record_failure("timeout")
        instance_state.record_failure("timeout")
        instance_state.record_success()
        assert instance_state.get_health_status().value == "healthy"
        assert instance_state.health_consecutive_failures == 0

    def test_stale_after_timeout(self, instance_state):
        instance_state.health_last_success = time.time() - 200
        assert instance_state.get_health_status().value == "stale"

"""Test 3: ESPN response parsing resilience.

Feed ESPNClient methods with various response shapes and verify graceful handling.
Uses httpx mock transport — no real HTTP calls.
"""

import httpx
import pytest
import pytest_asyncio

from espn import ESPNClient


def _mock_transport(json_data=None, status_code=200, error=None):
    """Create a mock httpx transport that returns canned responses."""

    async def handler(request):
        if error:
            raise error
        return httpx.Response(status_code, json=json_data or {})

    return httpx.MockTransport(handler)


@pytest_asyncio.fixture
async def client():
    c = ESPNClient()
    yield c
    await c.close()


def _swap_transport(client, json_data=None, status_code=200, error=None):
    """Replace the client's transport with a mock."""
    old = client.client
    client.client = httpx.AsyncClient(transport=_mock_transport(json_data, status_code, error))
    return old


# --- Scoreboard Tests ---


class TestGetScoreboard:

    @pytest.mark.asyncio
    async def test_normal_response(self, client):
        data = {
            "events": [{
                "id": "401",
                "name": "GB vs CHI",
                "status": {"type": {"state": "in", "detail": "Q3 5:30"}},
                "competitions": [{
                    "competitors": [
                        {"homeAway": "home", "team": {"abbreviation": "GB"}, "score": "14"},
                        {"homeAway": "away", "team": {"abbreviation": "CHI"}, "score": "7"},
                    ]
                }]
            }]
        }
        _swap_transport(client, json_data=data)
        games = await client.get_scoreboard("football", "nfl")

        assert len(games) == 1
        assert games[0]["home_team"] == "GB"
        assert games[0]["away_team"] == "CHI"
        assert games[0]["home_score"] == 14
        assert games[0]["away_score"] == 7
        assert games[0]["status"] == "in"

    @pytest.mark.asyncio
    async def test_empty_events(self, client):
        _swap_transport(client, json_data={"events": []})
        games = await client.get_scoreboard("football", "nfl")
        assert games == []

    @pytest.mark.asyncio
    async def test_missing_events_key(self, client):
        _swap_transport(client, json_data={})
        games = await client.get_scoreboard("football", "nfl")
        assert games == []

    @pytest.mark.asyncio
    async def test_missing_competitors(self, client):
        data = {"events": [{"id": "1", "competitions": [{"competitors": []}]}]}
        _swap_transport(client, json_data=data)
        games = await client.get_scoreboard("football", "nfl")
        assert games == []

    @pytest.mark.asyncio
    async def test_single_competitor_skipped(self, client):
        data = {"events": [{"id": "1", "competitions": [{"competitors": [
            {"homeAway": "home", "team": {"abbreviation": "GB"}, "score": "7"}
        ]}]}]}
        _swap_transport(client, json_data=data)
        games = await client.get_scoreboard("football", "nfl")
        assert games == []

    @pytest.mark.asyncio
    async def test_null_score_defaults_to_zero(self, client):
        data = {"events": [{
            "id": "1",
            "name": "Test",
            "status": {"type": {"state": "pre", "detail": ""}},
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"abbreviation": "GB"}, "score": None},
                    {"homeAway": "away", "team": {"abbreviation": "CHI"}, "score": ""},
                ]
            }]
        }]}
        _swap_transport(client, json_data=data)
        games = await client.get_scoreboard("football", "nfl")
        assert games[0]["home_score"] == 0
        assert games[0]["away_score"] == 0

    @pytest.mark.asyncio
    async def test_http_error_returns_empty(self, client):
        _swap_transport(client, status_code=500, json_data={"error": "server error"})
        games = await client.get_scoreboard("football", "nfl")
        assert games == []

    @pytest.mark.asyncio
    async def test_network_error_returns_empty(self, client):
        _swap_transport(client, error=httpx.ConnectError("DNS failed"))
        games = await client.get_scoreboard("football", "nfl")
        assert games == []


# --- Game Detail Tests ---


class TestGetGameDetail:

    @pytest.mark.asyncio
    async def test_normal_response_with_win_probability(self, client):
        data = {
            "header": {
                "competitions": [{
                    "competitors": [
                        {"homeAway": "home", "team": {"abbreviation": "GB"}, "score": "21"},
                        {"homeAway": "away", "team": {"abbreviation": "CHI"}, "score": "14"},
                    ],
                    "status": {"type": {"state": "in", "detail": "Q4 2:00"}, "displayClock": "2:00"},
                }]
            },
            "winprobability": [
                {"homeWinPercentage": 0.65},
                {"homeWinPercentage": 0.82},
            ],
        }
        _swap_transport(client, json_data=data)
        info = await client.get_game_detail("football", "nfl", "401")

        assert info is not None
        assert info.home_team == "GB"
        assert info.away_team == "CHI"
        assert info.home_score == 21
        assert info.away_score == 14
        assert info.home_win_pct == 0.82  # Latest entry
        assert info.status == "in"

    @pytest.mark.asyncio
    async def test_missing_win_probability_uses_predictor(self, client):
        data = {
            "header": {
                "competitions": [{
                    "competitors": [
                        {"homeAway": "home", "team": {"abbreviation": "GB"}, "score": "0"},
                        {"homeAway": "away", "team": {"abbreviation": "CHI"}, "score": "0"},
                    ],
                    "status": {"type": {"state": "pre", "detail": "Pre"}, "displayClock": ""},
                }]
            },
            "predictor": {"homeTeam": {"gameProjection": 65.0}},
        }
        _swap_transport(client, json_data=data)
        info = await client.get_game_detail("football", "nfl", "401")

        assert info is not None
        assert info.home_win_pct == 0.65

    @pytest.mark.asyncio
    async def test_no_win_data_defaults_to_50(self, client):
        data = {
            "header": {
                "competitions": [{
                    "competitors": [
                        {"homeAway": "home", "team": {"abbreviation": "GB"}, "score": "0"},
                        {"homeAway": "away", "team": {"abbreviation": "CHI"}, "score": "0"},
                    ],
                    "status": {"type": {"state": "pre", "detail": ""}, "displayClock": ""},
                }]
            },
        }
        _swap_transport(client, json_data=data)
        info = await client.get_game_detail("football", "nfl", "401")

        assert info is not None
        assert info.home_win_pct == 0.5

    @pytest.mark.asyncio
    async def test_empty_competitions_returns_none(self, client):
        data = {"header": {"competitions": []}}
        _swap_transport(client, json_data=data)
        info = await client.get_game_detail("football", "nfl", "401")
        assert info is None

    @pytest.mark.asyncio
    async def test_missing_header_returns_none(self, client):
        data = {}
        _swap_transport(client, json_data=data)
        info = await client.get_game_detail("football", "nfl", "401")
        assert info is None

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self, client):
        _swap_transport(client, status_code=404, json_data={})
        info = await client.get_game_detail("football", "nfl", "999")
        assert info is None

    @pytest.mark.asyncio
    async def test_network_error_returns_none(self, client):
        _swap_transport(client, error=httpx.TimeoutException("timeout"))
        info = await client.get_game_detail("football", "nfl", "401")
        assert info is None

    @pytest.mark.asyncio
    async def test_missing_team_abbreviation(self, client):
        data = {
            "header": {
                "competitions": [{
                    "competitors": [
                        {"homeAway": "home", "team": {}, "score": "7"},
                        {"homeAway": "away", "team": {}, "score": "3"},
                    ],
                    "status": {"type": {"state": "in", "detail": ""}, "displayClock": ""},
                }]
            },
        }
        _swap_transport(client, json_data=data)
        info = await client.get_game_detail("football", "nfl", "401")

        assert info is not None
        assert info.home_team == "???"
        assert info.away_team == "???"

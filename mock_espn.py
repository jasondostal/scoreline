#!/usr/bin/env python3
"""
Mock ESPN API for testing Scoreline auto-watch feature.
Uses only stdlib - no Flask dependency.

Run with: python3 mock_espn.py
Control via: curl -X POST http://localhost:5555/control -d '{"status": "in"}'
"""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Controllable game state
GAME_STATE = {
    "status": "scheduled",  # scheduled, pre, in, post
    "home_team": "NE",      # Patriots
    "away_team": "BUF",     # Bills (AFC Championship opponent)
    "home_score": 0,
    "away_score": 0,
    "home_win_pct": 0.5,
    "period": "1st Quarter",
    "clock": "15:00",
    "game_id": "401547417",
}


class MockESPNHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Custom logging with [MOCK] prefix
        print(f"[MOCK] {args[0]}")

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Control endpoint - get current state
        if path == "/control":
            self.send_json(GAME_STATE)
            return

        # NFL Scoreboard
        if path == "/football/nfl/scoreboard":
            self.handle_scoreboard()
            return

        # NFL Summary
        if path == "/football/nfl/summary":
            self.handle_summary(parsed)
            return

        # Other sports - return empty
        if "/scoreboard" in path:
            print(f"[MOCK] Empty scoreboard for {path}")
            self.send_json({"events": []})
            return

        # Not found
        self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/control":
            self.handle_control()
            return

        self.send_json({"error": "not found"}, 404)

    def handle_control(self):
        """Update mock game state."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else "{}"

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({"error": "invalid json"}, 400)
            return

        for key in ["status", "home_team", "away_team", "home_score", "away_score",
                    "home_win_pct", "period", "clock", "game_id"]:
            if key in data:
                GAME_STATE[key] = data[key]

        print(f"\n{'='*60}")
        print(f"STATE UPDATED: {GAME_STATE['away_team']}@{GAME_STATE['home_team']}")
        print(f"  Status: {GAME_STATE['status']}")
        print(f"  Score: {GAME_STATE['away_score']}-{GAME_STATE['home_score']}")
        print(f"  Home Win%: {GAME_STATE['home_win_pct']:.1%}")
        print(f"{'='*60}\n")

        self.send_json({"ok": True, "state": GAME_STATE})

    def handle_scoreboard(self):
        """Mock NFL scoreboard - returns list of games."""
        game = {
            "id": GAME_STATE["game_id"],
            "name": f"{GAME_STATE['away_team']} at {GAME_STATE['home_team']}",
            "status": {
                "type": {
                    "state": GAME_STATE["status"],
                    "detail": GAME_STATE["period"],
                }
            },
            "competitions": [{
                "competitors": [
                    {
                        "homeAway": "home",
                        "team": {"abbreviation": GAME_STATE["home_team"]},
                        "score": str(GAME_STATE["home_score"]),
                    },
                    {
                        "homeAway": "away",
                        "team": {"abbreviation": GAME_STATE["away_team"]},
                        "score": str(GAME_STATE["away_score"]),
                    }
                ]
            }]
        }

        print(f"[MOCK] Scoreboard -> status={GAME_STATE['status']}, teams={GAME_STATE['away_team']}@{GAME_STATE['home_team']}")
        self.send_json({"events": [game]})

    def handle_summary(self, parsed):
        """Mock NFL game summary - returns detailed game info with win probability."""
        params = parse_qs(parsed.query)
        game_id = params.get("event", ["unknown"])[0]

        response = {
            "header": {
                "competitions": [{
                    "status": {
                        "type": {
                            "state": GAME_STATE["status"],
                            "detail": GAME_STATE["period"],
                        },
                        "displayClock": GAME_STATE["clock"],
                    },
                    "competitors": [
                        {
                            "homeAway": "home",
                            "team": {"abbreviation": GAME_STATE["home_team"]},
                            "score": str(GAME_STATE["home_score"]),
                        },
                        {
                            "homeAway": "away",
                            "team": {"abbreviation": GAME_STATE["away_team"]},
                            "score": str(GAME_STATE["away_score"]),
                        }
                    ]
                }]
            },
            "winprobability": [
                {"homeWinPercentage": GAME_STATE["home_win_pct"]}
            ],
        }

        print(f"[MOCK] Summary (game {game_id}) -> status={GAME_STATE['status']}, win%={GAME_STATE['home_win_pct']:.1%}")
        self.send_json(response)


def main():
    port = 5555
    server = HTTPServer(("0.0.0.0", port), MockESPNHandler)

    print("=" * 60)
    print("MOCK ESPN API SERVER")
    print("=" * 60)
    print(f"Listening on port {port}")
    print(f"Initial state: {GAME_STATE['away_team']}@{GAME_STATE['home_team']} ({GAME_STATE['status']})")
    print()
    print("Quick commands:")
    print()
    print("  # Check state")
    print("  curl http://localhost:5555/control")
    print()
    print("  # Start game (TRIGGERS AUTO-WATCH)")
    print('  curl -X POST http://localhost:5555/control -d \'{"status":"in"}\'')
    print()
    print("  # Update score")
    print('  curl -X POST http://localhost:5555/control -d \'{"home_score":14,"away_score":7,"home_win_pct":0.72}\'')
    print()
    print("  # End game (TRIGGERS POST-GAME)")
    print('  curl -X POST http://localhost:5555/control -d \'{"status":"post","home_score":24,"away_score":21}\'')
    print()
    print("Or use: ./test_autowatch.sh [state|start|score|end|...]")
    print("=" * 60)
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[MOCK] Shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()

#!/bin/bash
# Auto-watch test harness for Scoreline
#
# This script helps you test the auto-watch feature with a mock ESPN API.

MOCK_URL="http://localhost:5555"
CONTROL_URL="$MOCK_URL/control"

case "$1" in
    state)
        echo "Current mock state:"
        curl -s "$CONTROL_URL" | python3 -m json.tool
        ;;

    scheduled)
        echo "Setting game to: SCHEDULED"
        curl -s -X POST "$CONTROL_URL" \
            -H "Content-Type: application/json" \
            -d '{"status": "scheduled", "home_score": 0, "away_score": 0, "home_win_pct": 0.5}' | python3 -m json.tool
        ;;

    pre)
        echo "Setting game to: PRE-GAME"
        curl -s -X POST "$CONTROL_URL" \
            -H "Content-Type: application/json" \
            -d '{"status": "pre", "home_score": 0, "away_score": 0, "home_win_pct": 0.52}' | python3 -m json.tool
        ;;

    start|in)
        echo "Setting game to: IN PROGRESS (this should trigger auto-watch!)"
        curl -s -X POST "$CONTROL_URL" \
            -H "Content-Type: application/json" \
            -d '{"status": "in", "home_score": 0, "away_score": 0, "home_win_pct": 0.55, "period": "1st Quarter", "clock": "15:00"}' | python3 -m json.tool
        ;;

    score)
        # Usage: ./test_autowatch.sh score 14 7 0.72
        home=${2:-14}
        away=${3:-7}
        pct=${4:-0.65}
        echo "Updating score: Home $home - Away $away (Home win%: $pct)"
        curl -s -X POST "$CONTROL_URL" \
            -H "Content-Type: application/json" \
            -d "{\"home_score\": $home, \"away_score\": $away, \"home_win_pct\": $pct}" | python3 -m json.tool
        ;;

    halftime)
        echo "Setting game to: HALFTIME"
        curl -s -X POST "$CONTROL_URL" \
            -H "Content-Type: application/json" \
            -d '{"period": "Halftime", "clock": ""}' | python3 -m json.tool
        ;;

    comeback)
        echo "Simulating AWAY TEAM COMEBACK"
        curl -s -X POST "$CONTROL_URL" \
            -H "Content-Type: application/json" \
            -d '{"home_score": 21, "away_score": 28, "home_win_pct": 0.25, "period": "4th Quarter", "clock": "2:00"}' | python3 -m json.tool
        ;;

    end|post)
        echo "Setting game to: FINAL (this should trigger post-game action!)"
        # Default: home team wins
        home=${2:-24}
        away=${3:-21}
        curl -s -X POST "$CONTROL_URL" \
            -H "Content-Type: application/json" \
            -d "{\"status\": \"post\", \"home_score\": $home, \"away_score\": $away, \"home_win_pct\": 1.0, \"period\": \"Final\"}" | python3 -m json.tool
        ;;

    away-wins)
        echo "Setting game to: FINAL (away team wins - Patriots LOSE)"
        curl -s -X POST "$CONTROL_URL" \
            -H "Content-Type: application/json" \
            -d '{"status": "post", "home_score": 17, "away_score": 24, "home_win_pct": 0.0, "period": "Final"}' | python3 -m json.tool
        ;;

    reset)
        echo "Resetting to initial state"
        curl -s -X POST "$CONTROL_URL" \
            -H "Content-Type: application/json" \
            -d '{"status": "scheduled", "home_score": 0, "away_score": 0, "home_win_pct": 0.5, "period": "1st Quarter", "clock": "15:00"}' | python3 -m json.tool
        ;;

    *)
        echo "Scoreline Auto-Watch Test Harness"
        echo ""
        echo "Usage: $0 <command> [args]"
        echo ""
        echo "Commands:"
        echo "  state         Show current mock state"
        echo "  scheduled     Set game to scheduled (not started)"
        echo "  pre           Set game to pre-game"
        echo "  start|in      Set game to in-progress (TRIGGERS AUTO-WATCH)"
        echo "  score H A P   Update score (home away win_pct)"
        echo "  halftime      Set to halftime"
        echo "  comeback      Simulate away team comeback"
        echo "  end|post      End game, home wins (TRIGGERS POST-GAME)"
        echo "  away-wins     End game, away wins"
        echo "  reset         Reset to initial state"
        echo ""
        echo "Example flow:"
        echo "  $0 state      # Check starting state"
        echo "  $0 start      # Game kicks off - watch for lights!"
        echo "  $0 score 7 0 0.72  # Home scores TD"
        echo "  $0 score 7 7 0.50  # Away ties it"
        echo "  $0 end        # Game over - watch for post-game action!"
        ;;
esac

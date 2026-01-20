# Scoreline

Live sports win probability visualized on your LED strip.

Scoreline polls ESPN for real-time game data and translates win probability into a dynamic light display on [WLED](https://kno.wled.ge/)-controlled LEDs. Watch the colors shift as momentum swings.

## How It Works

1. Pick a live game from the web UI
2. Scoreline polls ESPN every 30 seconds for win probability
3. Your LED strip splits proportionally between team colors
4. Home team on one end, away team on the other - the boundary shifts with the game

## Quick Start

### Docker (Recommended)

**Option A: Pull the image** (easiest)

```bash
# Create your config directory
mkdir -p scoreline/config/leagues
cd scoreline

# Grab the configs
curl -o config/settings.yaml https://raw.githubusercontent.com/jasondostal/scoreline/main/config/settings.yaml
for league in nfl nba mlb nhl mls; do
  curl -o config/leagues/$league.yaml https://raw.githubusercontent.com/jasondostal/scoreline/main/config/leagues/$league.yaml
done

# Edit config/settings.yaml with your WLED IP, then:
docker run -d --name scoreline \
  -p 8084:8080 \
  -v ./config:/app/config \
  ghcr.io/jasondostal/scoreline:latest
```

**Option B: Clone the repo**

```bash
git clone https://github.com/jasondostal/scoreline.git
cd scoreline

# Edit config/settings.yaml with your WLED IP address
docker compose up -d
```

Open `http://localhost:8084` and pick a game.

### Manual

```bash
git clone https://github.com/jasondostal/scoreline.git
cd scoreline
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Edit config/settings.yaml with your WLED IP
cd app
uvicorn main:app --host 0.0.0.0 --port 8080
```

## Configuration

Edit `config/settings.yaml`:

```yaml
wled_instances:
  - host: "192.168.1.100"  # Your WLED IP
    start: 0               # First LED index
    end: 629               # Last LED index

poll_interval: 30          # Seconds between ESPN updates
default_league: nfl        # League shown on startup
```

Multiple WLED instances are supported - each can display its own game.

## Data Directory

All configuration lives in a single directory you control:

```
config/
├── settings.yaml      # Your WLED instances and preferences
└── leagues/           # League definitions
    ├── nfl.yaml
    ├── nba.yaml
    ├── mlb.yaml
    ├── nhl.yaml
    └── mls.yaml
```

Mount it wherever you want:

```yaml
volumes:
  - /path/to/your/scoreline/config:/app/config
```

Back it up with the rest of your homelab configs. The container writes nothing else.

## Supported Leagues

- NFL (32 teams)
- NBA (30 teams)
- MLB (30 teams)
- NHL (32 teams)
- MLS (29 teams)

League definitions live in `config/leagues/` as YAML files. Each includes team colors and ESPN sport mapping. Drop in your own YAML to add a league.

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/leagues` | GET | List available leagues |
| `/api/games/{league}` | GET | Get live games for a league |
| `/api/watch` | POST | Start watching a game |
| `/api/stop` | POST | Stop watching, turn off LEDs |
| `/api/status` | GET | Current game status |
| `/api/test` | POST | Test mode - set arbitrary win % |
| `/api/settings` | GET | Current config |
| `/api/reload` | POST | Hot-reload config from disk |

## Requirements

- WLED-controlled LED strip (any length)
- Network access to your WLED device
- Docker or Python 3.11+

## Project Status

Working and usable. Active development toward v1.0 with planned features:

- [ ] mDNS discovery for WLED devices
- [ ] Per-instance game selection (different games on different strips)
- [ ] Configurable effects and segment sizing
- [ ] Team auto-watch (lights turn on when your team plays)
- [ ] Post-game actions (turn off, switch to preset, etc.)

## License

MIT - see [LICENSE](LICENSE)

## Acknowledgments

- [WLED](https://kno.wled.ge/) - the LED firmware that makes this possible
- ESPN's scoreboard data (unofficial API)

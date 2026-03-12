# Changelog

All notable changes to Scoreline will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.5.0] - 2026-03-12

### Added
- **Login UI** — Frontend login page with auth gate; checks `/api/auth/me` on load, shows login form when authentication is required, redirects on session expiry
- **Login Rate Limiting** — 5 attempts per 15-minute window per IP with `429 Too Many Requests` and `Retry-After` header
- **Security Headers Middleware** — `Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` on all responses
- **Conditional HSTS** — `Strict-Transport-Security` header when `FORCE_HTTPS` env var is set
- **WebSocket Auth Gate** — WebSocket connections require authentication before acceptance (closes with 1008 if unauthenticated)
- **WebSocket Idle Timeout** — Connections idle for 5 minutes are closed cleanly
- **Session Invalidation** — `invalidate_all_sessions()` helper for credential rotation
- **`FORCE_HTTPS` env var** — Controls secure cookie flag and HSTS header independently of proxy config

### Changed
- **SSRF Blocklist Expanded** — Added `0.0.0.0/8`, IPv6 ULA (`fc00::/7`), link-local (`fe80::/10`), and multicast (`224.0.0.0/4`, `ff00::/8`) to blocked networks
- **Input Validation** — Pydantic `Field` validators with bounds on `InstanceSettingsRequest` (min_team_pct, contested_zone_pixels, dark_buffer_pixels, chase_speed, chase_intensity); `divider_preset` validated against `DIVIDER_PRESETS`
- **CSP Policy** — Allows Google Fonts (`fonts.googleapis.com`, `fonts.gstatic.com`) for Inter and JetBrains Mono
- **401 Interceptor** — Frontend API layer detects 401 responses and triggers re-authentication
- **Login Audit Logging** — Success and failure events logged with client IP

## [2.4.0] - 2026-03-07

### Added
- **Authentication System** — Optional single-user local login, API key auth, and reverse proxy header bypass (Authentik/SWAG compatible) with fail-closed proxy trust validation
- **Health Endpoint** — `GET /api/health` with ESPN client, background task, and config checks; Docker `HEALTHCHECK` directive uses it
- **SSRF Protection** — WLED host validation blocks loopback/link-local addresses and enforces hostname format
- **Error Boundary** — React `ErrorBoundary` wraps the app with crash recovery UI
- **Test Suite** — pytest infrastructure with `conftest.py`, tests for config, ESPN client, LED segments, and state machine; CI runs tests between lint and build stages
- **Non-Root Container** — `appuser` created in Dockerfile, entrypoint drops privileges via `gosu` after config setup

### Changed
- **CORS** — Configurable via `CORS_ORIGINS` env var (locked to same-origin by default)
- **WebSocket Limits** — Max 50 concurrent connections with proper rejection (code 1013)
- **Atomic Config Writes** — `settings.yaml` writes use tmp file + rename to prevent partial reads
- **Path Traversal Prevention** — SPA fallback resolves and validates paths against static root
- **Dependency Pinning** — All `requirements.txt` entries now have upper-bound version constraints
- **Structured Logging** — `print()` calls in ESPN/WLED clients replaced with `logging.getLogger("uvicorn.error")`
- **Mutable Class-Level State** — `AppState` fields moved from class variables to `__init__` (prevents cross-instance leakage)
- **ConfigWatcher Thread Safety** — Reload scheduled on event loop via `call_soon_threadsafe` instead of direct mutation
- **Graceful Shutdown** — WLED strips restored to previous preset (or turned off) on container stop
- **Assertion Cleanup** — Bare `assert` statements replaced with proper guards (`if`/`raise HTTPException`)
- **Pydantic Validation** — `TestRequest.pct` constrained to 0–100 via `Field(ge=0, le=100)`
- **settings.yaml.default** — Post-game comments updated to reflect two-phase celebration model

### Fixed
- **Display Sliders Sync** — `useEffect` syncs local slider state when props change (WebSocket updates from other clients no longer ignored)
- **Post-Game Config Sync** — Same `useEffect` sync pattern applied to post-game settings panel

### Accessibility
- `aria-label` added to WLED host/pixel inputs, team selects, watch-team remove buttons, and sim toggle buttons
- `aria-pressed` on simulator instance toggle buttons
- `aria-labelledby` on Style, Celebration, Duration, and Action select triggers
- Slider `<span>` labels converted to proper `<label>` elements with `htmlFor`

## [2.3.0] - 2026-03-05

### Added
- **Home Assistant Integration** — [scoreline-ha](https://github.com/jasondostal/scoreline-ha) HACS custom integration with WebSocket local push, 13 entities per WLED instance, 3 services
- **WLED MAC Address** — Instances now expose MAC address (fetched from WLED `/json/info` at startup), enabling cross-device linking with the WLED HA integration
- **CI Pipeline** — 4-stage GitHub Actions workflow: lint (ruff, mypy, bandit, hadolint, shellcheck, pip-audit, npm audit) > build (Docker + cosign signing) > scan (Trivy CVE) > smoke (API + UI assertions)

### Changed
- All `Optional[X]` annotations modernized to `X | None` (Python 3.12 style)
- `str, Enum` base classes updated to `StrEnum` where applicable
- Import blocks sorted and organized per isort rules
- 25 mypy type errors fixed (narrowing guards, proper annotations)

## [2.2.0] - 2026-02-27

### Added
- **Searchable Game Picker** — Single search-as-you-type combobox replaces dual league+game dropdowns. Finds games across all leagues, grouped by league, with team color dots
- **Demo Game Mode** — Scripted 40-tick NBA game for simulator with realistic scores, periods, and win probability progression
- **Demo Video** — Inline MP4 in README showing the simulator in action

### Changed
- Team colors now included in `/api/games/{league}` response (enables color dots in game picker)
- README restructured: screenshot + demo video above the fold

### Fixed
- Simulator demo mode scores no longer flash/disappear (debounced simTest was overwriting scripted scores)

## [2.1.0] - 2026-02-27

### Added
- **WebSocket Live Updates** — Real-time push via `/ws`, automatic fallback to polling when disconnected
- **Win Probability Sparkline** — SVG chart tracks momentum over the course of a game
- **16 Leagues, 1500+ Teams** — Added WNBA, College Football, Men's/Women's College Basketball, EPL, La Liga, Bundesliga, Serie A, Ligue 1, Liga MX, Champions League
- **Toast Notifications** — Instant feedback on watch, stop, settings, share, and all mutations (sonner)
- **Share Cards** — Export game or sim snapshots as PNG with team colors, scores, sparkline, and strip preview
- **Draggable Strip Preview** — Drag directly on the LED preview bar to set simulator win percentage
- **Dismissible Watch Teams** — Click X on team badges in the "Watching for" notice to remove inline
- **Two-Column Layout** — Instances and simulator side by side on wide screens (>1280px), stacked on narrow
- **Logo + Favicon** — SVG logo mark with lightning-bolt divider
- **Scenario Presets** — Nail-biter, dominant, blowout, comeback, overtime, momentum, buzzer, collapse
- **Unified Display Architecture** — Single rendering path for game and sim data

### Changed
- Simulator uses draggable strip instead of separate range slider
- All mutation endpoints broadcast state via WebSocket (no more stale UI)
- League YAML files support `espn_league` field for ESPN API slug mapping
- Layout widened from `max-w-4xl` to `max-w-6xl` with responsive grid
- Simulator panel sticks to viewport on scroll (wide screens)

### Fixed
- Sim start/stop now syncs instantly across all connected clients
- Share card rendering with oklch/oklab CSS color functions (html2canvas workaround)

## [2.0.0] - 2026-02-27

### Added
- **React Frontend** — Complete rewrite from vanilla JS to React 19 + Vite + TypeScript + Tailwind v4
- **shadcn/ui Components** — All dropdowns, buttons, and badges use shadcn/ui primitives (Radix-based)
- **Multi-Select Watch Teams** — Searchable multi-select across all 153 teams, grouped by league, with team color dots
- **Team Color Dots** — Primary team color shown inline in all team dropdowns and scoreboard
- **Sport Icons** — League-specific icons in all league selectors
- **Icon System** — Lucide icons throughout: status badges, health indicators, section headers, action buttons
- **Electric Blue Palette** — Broadcast-style design with OKLCH color tokens
- **Multi-Stage Docker Build** — Node build stage compiles React frontend, Python stage serves it as SPA

### Changed
- Frontend served as SPA with catch-all fallback (replaces static file mount)
- All native `<select>` elements replaced with shadcn Select
- All raw `<button>` elements replaced with shadcn Button
- Watch teams UX: single multi-select replaces league→team→add workflow
- `config/settings.yaml` removed from version control (use `.default` as template)

### Removed
- Vanilla JS frontend (`static/index.html` — 104KB monolith)

## [1.2.0] - 2025-01-25

### Added
- **Explicit State Machine** - UI now shows clear states: Idle, Armed, Watching (Auto/Manual/Override), Final, Simulating
- **Post-Game Celebration System** - Two-phase post-game: celebration effect + after action
  - Celebration types: freeze, chase, twinkle, flash, solid (in winner colors)
  - Configurable duration: 30s, 1min, 5min, 10min, or custom
  - After actions: fade off, off, restore previous, switch to preset
- **Watch Team Priority** - Drag-and-drop reordering; #1 priority wins when multiple games start
- **Game Cascade** - When a game ends, automatically starts next priority game if available
- **Health Tracking** - WLED connectivity status (Healthy/Stale/Unreachable) shown in UI
- **FINAL State Linger** - Shows final score in UI during celebration before transitioning
- **State-based UI** - Card colors and badges reflect explicit state (green=watching, amber=override, etc.)

### Changed
- Post-game settings migrated from single `action` field to two-phase `celebration` + `after_action`
- Settings changes now push to WLED immediately (was waiting for 30s poll cycle)
- License changed from MIT to GPL-3.0

### Fixed
- Config reload no longer resets instance state (was stopping active games)
- Divider preset changes now apply immediately
- Resume Auto-Watch button only shows in Override state

## [1.1.0] - 2025-01-20

- Live game UX polish
- Simulator improvements
- Auto-watch testing

## [1.0.0] - 2025-01-15

- Initial public release
- Real-time win probability visualization from ESPN data
- Support for NFL, NBA, MLB, NHL, MLS (153 teams)
- Multi-instance WLED support
- Auto-watch favorite teams
- Post-game actions (flash, fade, restore, preset)
- Per-instance display customization
- Simulator for testing without live games
- mDNS device discovery
- Web UI for configuration

[Unreleased]: https://github.com/jasondostal/scoreline/compare/v2.5.0...HEAD
[2.5.0]: https://github.com/jasondostal/scoreline/compare/v2.4.0...v2.5.0
[2.4.0]: https://github.com/jasondostal/scoreline/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/jasondostal/scoreline/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/jasondostal/scoreline/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/jasondostal/scoreline/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/jasondostal/scoreline/compare/v1.2.0...v2.0.0
[1.2.0]: https://github.com/jasondostal/scoreline/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/jasondostal/scoreline/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/jasondostal/scoreline/releases/tag/v1.0.0

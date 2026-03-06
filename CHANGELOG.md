# Changelog

All notable changes to Scoreline will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/jasondostal/scoreline/compare/v2.3.0...HEAD
[2.3.0]: https://github.com/jasondostal/scoreline/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/jasondostal/scoreline/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/jasondostal/scoreline/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/jasondostal/scoreline/compare/v1.2.0...v2.0.0
[1.2.0]: https://github.com/jasondostal/scoreline/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/jasondostal/scoreline/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/jasondostal/scoreline/releases/tag/v1.0.0

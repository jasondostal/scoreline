# Changelog

All notable changes to Scoreline will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/jasondostal/scoreline/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/jasondostal/scoreline/compare/v1.2.0...v2.0.0
[1.2.0]: https://github.com/jasondostal/scoreline/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/jasondostal/scoreline/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/jasondostal/scoreline/releases/tag/v1.0.0

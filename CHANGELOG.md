# Changelog

All notable changes to Scoreline will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/jasondostal/scoreline/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/jasondostal/scoreline/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/jasondostal/scoreline/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/jasondostal/scoreline/releases/tag/v1.0.0

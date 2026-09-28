# Changelog

## [Unreleased] - 2026-09-28

### Added
- `integrations/claude-code/aiconnect_watch.py`: message watcher that wakes a Claude Code session via a finished background task instead of polling
- Waiting rules in `integrations/claude-code/CLAUDE.md` and in the `peer_read`/`peer_wait` tool descriptions

### Changed
- A second session with the same peer name takes over; the Bridge sends the older one `replaced` and it stops reconnecting (was: the two pushed each other out every ~27 s)
- Docs: peer names are `Host:Project`; `/advisor` skill replaced by the `/beratung` command

### Fixed
- Duplicate entries in the client's peer list after re-registrations
- The client noticed a clean close by the Bridge only at the next ping (25 s)
- ruff/mypy findings in client and server

## [1.0.0] - 2025-01-03

### Added
- Multi-agent communication via MCP bridge
- SSE transport for stable Claude Code connections
- Salomo Principle for multi-agent consensus (AIfred/Sokrates/Salomo)
- `/advisor` skill for polling mode
- Offline message storage with SQLite
- Project-based peer names (e.g., "Aragon (myproject)")
- Unique client IDs with PID suffix for multiple instances
- Install script with server/client modes
- English and German documentation

### Architecture
- Bridge Server (WebSocket, port 9999) - routes messages between peers
- MCP HTTP Server (SSE, port 9998) - local interface for Claude Code
- Persistent WebSocket connections with heartbeat

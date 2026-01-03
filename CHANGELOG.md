# Changelog

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

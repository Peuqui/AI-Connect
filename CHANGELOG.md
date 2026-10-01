# Changelog

## [Unreleased] - 2026-10-01

### Added
- The rules make every Claude Code session keep its watcher running from the start, so messages wake the recipient without the user prompting it; the tool descriptions carry the exact watcher command of the installation
- `requirements.txt` as the single list of dependencies; `install.sh` installs from it (`aiosqlite` was missing, the Bridge crashed on fresh machines)
- `config_loader.py`: one config loader for the Bridge and both MCP clients

### Changed
- A missing config file or key stops every service with a message; the silent defaults (including a hard-coded Bridge IP) are gone
- Code, log messages, tool descriptions and `install.sh` are in English; `install.sh` writes the PolicyKit rule for the installing user instead of a fixed one, asks clients for the Bridge address and suggests `0.0.0.0` as the Bridge's listen address (`127.0.0.1` locked out every other machine); it ends with the ready `claude mcp add` line
- `/beratung` renamed to `/consult` and rewritten in English, as are the Claude Code rules and the integration README; tag `[WEITER]` is now `[CONTINUE]`
- README (EN/DE) rewritten: setup via `install.sh`, Claude Code via the STDIO client, current architecture diagram, corrected heartbeat timings

### Fixed
- The watcher read the Bridge's database file and therefore worked on the Bridge machine only; it now asks the Bridge over the network (`watch`, no registration) and works on every machine, pushed instead of polling every 5 s
- `peer_send` with a file and `peer_context` sent only the path and line numbers; the file content (or the given lines) now travels with the message
- `peer_history` showed only the local, already emptied queue; it now asks the Bridge
- A broadcast to offline peers was handed to whichever peer came online first and marked delivered (possibly back to its sender); broadcasts now reach the peers online at that moment
- A client that could not reach the Bridge at start never retried; it now reconnects in the background
- The Bridge refreshed a peer's heartbeat whenever it sent to it, so silent peers never timed out; only the peer's own pings count now
- `register` without a name is rejected instead of registering `None`
- The HTTP/SSE server had its own copy of every tool and lacked `peer_wait`; both servers now share `client/mcp_app.py`

### Removed
- `chat_viewer.py`: it registered as an ordinary peer and therefore never saw the messages it promised to show
- `peer.auto_connect`: with `false` the client stayed disconnected for good
- The "Salomo Principle" (AIfred/Sokrates/Salomo roles, 2/3 voting) from docs and command: nothing in AI-Connect implemented it
- `pyproject.toml`: unused, its entry point named a module that does not exist

## [Unreleased] - 2026-09-28

### Added
- `integrations/claude-code/aiconnect_watch.py`: message watcher that wakes a Claude Code session via a finished background task instead of polling
- Waiting rules in `integrations/claude-code/CLAUDE.md` and in the `peer_read`/`peer_wait` tool descriptions

### Changed
- `aiconnect_watch.py` takes the peer name from the session's MCP client instead of the shell's current directory, prints it at start and exits with an error when it cannot tell (a watcher started from a worktree listened for the wrong name)
- A second session with the same peer name takes over; the Bridge sends the older one `replaced` and it stops reconnecting (was: the two pushed each other out every ~27 s)
- Docs: peer names are `Host:Project`; `/advisor` skill replaced by the `/beratung` command (now `/consult`)

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

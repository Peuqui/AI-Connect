"""The peer name of a STDIO client: one rule for the client and the watcher."""

import socket
from collections.abc import Mapping
from pathlib import Path

# The STDIO client records its name here, one file per parent process (the
# Claude Code session), so the session's watcher can look it up by CLAUDE_PID
# on every operating system
SESSIONS_DIR = Path.home() / ".config" / "ai-connect" / "sessions"


def peer_name(environ: Mapping[str, str], cwd: Path) -> str:
    """AI_CONNECT_PEER_NAME if set, else "Host:Project".

    The project is CLAUDE_PROJECT_DIR when Claude Code sets it for its MCP
    servers, whatever directory it starts them in. Other harnesses start the
    STDIO client in the project itself, so there the working directory
    names it.
    """
    if "AI_CONNECT_PEER_NAME" in environ:
        return environ["AI_CONNECT_PEER_NAME"]
    project = Path(environ["CLAUDE_PROJECT_DIR"]) if "CLAUDE_PROJECT_DIR" in environ else cwd
    return f"{socket.gethostname()}:{project.name}"


def record_session_name(session_pid: int, name: str) -> Path:
    """Note which peer name the session with this process id uses."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = SESSIONS_DIR / str(session_pid)
    path.write_text(name)
    return path


def session_name(session_pid: str) -> str | None:
    """The peer name the session with this process id recorded, if any."""
    path = SESSIONS_DIR / session_pid
    return path.read_text() if path.exists() else None

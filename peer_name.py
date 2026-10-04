"""The peer name of a STDIO client: one rule for the client and the watcher."""

import socket
from collections.abc import Mapping
from pathlib import Path


def peer_name(environ: Mapping[str, str], cwd: Path) -> str:
    """AI_CONNECT_PEER_NAME if set, else "Host:Project".

    The project is CLAUDE_PROJECT_DIR when Claude Code sets it: a plugin's
    MCP server runs in the plugin directory, not in the project. Other
    harnesses start the STDIO client in the project itself, so there the
    working directory names it.
    """
    if "AI_CONNECT_PEER_NAME" in environ:
        return environ["AI_CONNECT_PEER_NAME"]
    project = Path(environ["CLAUDE_PROJECT_DIR"]) if "CLAUDE_PROJECT_DIR" in environ else cwd
    return f"{socket.gethostname()}:{project.name}"

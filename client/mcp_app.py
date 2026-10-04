"""The AI-Connect MCP server: tool definitions and Bridge connection.

Shared by the STDIO client (one per Claude Code session) and the HTTP/SSE
server; they differ only in the peer name and the transport.
"""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP

import tools
from bridge_client import get_client, init_client
from config_loader import bridge_target, load_config

# The exact command of this installation: same Python (it has websockets),
# real path. The tool descriptions carry it, so every assistant can start
# the watcher without knowing where AI-Connect lives.
# Forward slashes and quotes, so the command also runs in the Git Bash that
# Claude Code uses on Windows, and with spaces in the path. abspath, not
# resolve(): resolving follows the venv's symlink to the system Python.
WATCH_COMMAND = (
    f'"{Path(os.path.abspath(sys.executable)).as_posix()}" '
    f'"{(Path(__file__).resolve().parent.parent / "integrations" / "claude-code" / "aiconnect_watch.py").as_posix()}"'
)

WATCHER_NOTE = f"""Incoming messages do not wake a Claude Code session. Keep the watcher
running as a background task (Bash with run_in_background and timeout
7200000) for the whole session — start it at the beginning and again every
time it ends:
    {WATCH_COMMAND}
Without that timeout Claude Code stops the task after its default 30 minutes,
and from then on no message wakes the session.
It costs nothing while it waits and ends at the next message for this peer
(or when the Bridge restarts, or after 110 minutes, which only needs a
restart); the finished task wakes the session. Then
FIRST start the watcher again, THEN call peer_read and react — in this
order a message arriving meanwhile still wakes you."""


def create_app(peer_name: str) -> FastMCP:
    """Build the MCP server that joins the Bridge as peer_name."""

    @asynccontextmanager
    async def lifespan(app):
        bridge = load_config()["bridge"]
        await init_client(host=bridge_target(bridge["host"]), port=bridge["port"], peer_name=peer_name, token=bridge["token"])
        yield
        client = get_client()
        if client:
            await client.disconnect()

    mcp = FastMCP("AI-Connect", lifespan=lifespan)

    @mcp.tool()
    async def peer_list() -> str:
        """Show all peers that are currently online.

        Peer names have the form "Host:Project", e.g. "Mini:AIfred-Intelligence".
        """
        return await tools.peer_list()

    @mcp.tool()
    async def peer_send(to: str, message: str, file: str | None = None, lines: str | None = None) -> str:
        """Send a message to another peer.

        If you expect an answer, make sure your watcher is running (see
        peer_read) — the answer then wakes you by itself.

        Args:
            to: Full name of the target peer ("Host:Project"), or "*" for every online peer
            message: The message
            file: Optional file to attach; its content (or the given lines) travels with the message
            lines: Optional line range of the file, e.g. "42-58" or "42"

        Examples:
            peer_send("Aragon:FreeEchoDot2", "What do you think of this approach?")
            peer_send("Mini:AIfred-Intelligence", "Please review this function", file="src/api.py", lines="42-58")
            peer_send("*", "Does anyone have time for a review?")
        """
        return await tools.peer_send(to, message, file, lines)

    @mcp.tool(description=f"Read all messages received since the last call.\n\n{WATCHER_NOTE}")
    async def peer_read() -> str:
        return await tools.peer_read()

    @mcp.tool()
    async def peer_history(peer: str, limit: int = 20) -> str:
        """Show the conversation with a peer, as stored on the Bridge.

        Args:
            peer: Full name of the peer ("Host:Project")
            limit: Maximum number of messages (default 20)
        """
        return await tools.peer_history(peer, limit)

    @mcp.tool()
    async def peer_context(file: str, lines: str | None = None, message: str | None = None) -> str:
        """Share a file, or some of its lines, with every online peer.

        The content travels with the message, so peers on other machines
        can read it.

        Args:
            file: Path of the file to share
            lines: Optional line range, e.g. "42-58"
            message: Optional message to go with it
        """
        return await tools.peer_context(file, lines, message)

    @mcp.tool()
    async def peer_set_status(status: str) -> str:
        """Tell the other peers in one line what you are working on; peer_list shows it.

        Set it when you start a larger task, clear it with "" when done.

        Args:
            status: One short line, e.g. "Refactoring the Bridge token check"
        """
        return await tools.peer_set_status(status)

    @mcp.tool()
    async def peer_set_state(state: Literal["busy", "idle", "waiting"], detail: str = "") -> str:
        """Report whether this session is busy, idle or waiting for approval.

        Called by hooks of the harness (for Claude Code see
        integrations/claude-code/README.md), not by hand.

        Args:
            state: "busy", "idle" or "waiting" (for an approval)
            detail: Optional, e.g. what the approval is for
        """
        return await tools.peer_set_state(state, detail)

    @mcp.tool()
    async def peer_notify_when_idle(peer: str) -> str:
        """Get one message from the Bridge as soon as a peer is done or waits for approval.

        Answers at once if the peer is idle already. Works only for peers
        whose harness reports its state (see peer_set_state). The message
        wakes you through the watcher like any other (see peer_read).

        Args:
            peer: Full name of the peer ("Host:Project")
        """
        return await tools.peer_notify_when_idle(peer)

    @mcp.tool()
    async def peer_status() -> str:
        """Show the connection to the Bridge Server."""
        return await tools.peer_status()

    return mcp

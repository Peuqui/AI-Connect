#!/usr/bin/env python3
"""Exit as soon as a new AI-Connect message for this peer arrives.

Claude Code is not woken by incoming peer messages. Started as a background
task, this script ends when a message arrives, and the finished task wakes the
session. It polls the bridge's message store read-only and never connects to
the bridge, so it cannot take over the peer name.

The bridge marks a message delivered as soon as the connected MCP client
receives it, so this watches for rows newer than its own start, not for
undelivered ones.

Usage: aiconnect_watch.py [PEER_NAME]
Without PEER_NAME it watches for the name the AI-Connect MCP client of this
Claude Code session registered with (see session_peer_name), else for
AI_CONNECT_PEER_NAME. It prints the name it watches for when it starts.
"""

import os
import socket
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DB = Path.home() / ".config" / "ai-connect" / "messages.db"
POLL_SECONDS = 5



def session_peer_name() -> str | None:
    """The name the MCP client of this Claude Code session registered with.

    Claude Code starts the MCP client (client/server.py) as its child; the
    client names itself from AI_CONNECT_PEER_NAME or from its own start
    directory, which never changes. The shell running this script may sit in
    any directory (a worktree, another project), so its own directory proves
    nothing: on 2026-09-29 a watcher started from a worktree listened for
    "Mini:1Cat-vLLM-upstream" and missed every message.
    """
    claude_pid = os.environ.get("CLAUDE_PID")
    if claude_pid is None:
        return None
    for children in Path(f"/proc/{claude_pid}/task").glob("*/children"):
        for child in children.read_text().split():
            args = Path(f"/proc/{child}/cmdline").read_bytes().split(b"\0")
            if not any(arg.endswith(b"client/server.py") for arg in args):
                continue
            environ = Path(f"/proc/{child}/environ").read_bytes().split(b"\0")
            for entry in environ:
                if entry.startswith(b"AI_CONNECT_PEER_NAME="):
                    return entry.split(b"=", 1)[1].decode()
            directory = Path(os.readlink(f"/proc/{child}/cwd")).name
            return f"{socket.gethostname()}:{directory}"
    return None


peer = (
    sys.argv[1]
    if len(sys.argv) > 1
    else session_peer_name() or os.environ.get("AI_CONNECT_PEER_NAME")
)
if not peer:
    sys.exit(
        "aiconnect_watch.py: no peer name - pass it as the first argument, "
        "run it inside a Claude Code session with the AI-Connect MCP client, "
        "or set AI_CONNECT_PEER_NAME"
    )
print(f"watching for messages to {peer}", flush=True)
start = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

while True:
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
        rows = conn.execute(
            "SELECT from_peer, timestamp, content FROM messages "
            "WHERE (to_peer = ? OR to_peer = '*') AND from_peer != ? "
            "AND timestamp > ? ORDER BY timestamp",
            (peer, peer, start),
        ).fetchall()
    if rows:
        for sender, timestamp, content in rows:
            received = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            local = received.astimezone().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{local}] {sender} -> {peer}: {content}")
        sys.exit(0)
    time.sleep(POLL_SECONDS)

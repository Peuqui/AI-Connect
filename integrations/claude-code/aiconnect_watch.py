#!/usr/bin/env python3
"""Exit as soon as a new AI-Connect message for this peer arrives.

Claude Code is not woken by incoming peer messages. Started as a background
task, this script ends when a message arrives, and the finished task wakes the
session. It asks the Bridge over the network to be told about messages for
the peer, without registering as that peer, so it works on every machine and
cannot take over the peer name. While it waits it costs nothing: the Bridge
pushes, nothing polls.

It also exits when the connection to the Bridge drops (e.g. a Bridge
restart), and after MAX_MINUTES without a message: Claude Code kills
background tasks after two hours, and a killed watcher would leave the
session deaf. Either way the session simply starts it again.

Exit codes: 0 = message arrived (restart, then peer_read), 2 = time limit
reached (restart, nothing to read), 1 = error.

Usage: aiconnect_watch.py [PEER_NAME]
Without PEER_NAME it watches for the name the AI-Connect MCP client of this
Claude Code session registered with (see session_peer_name), else for
AI_CONNECT_PEER_NAME. It prints the name it watches for when it starts.
"""

import asyncio
import json
import os
import socket
import sys
from datetime import datetime
from pathlib import Path

# config_loader lives in the repository root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import websockets

from config_loader import load_config

# Below Claude Code's two-hour limit for background tasks
MAX_MINUTES = 110


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


async def watch(peer: str) -> None:
    bridge = load_config()["bridge"]
    uri = f"ws://{bridge['host']}:{bridge['port']}"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"type": "watch", "peer": peer}))
        async for raw in ws:
            data = json.loads(raw)
            if data.get("type") == "watching":
                print(f"watching for messages to {peer} via {uri}", flush=True)
            elif data.get("type") == "error":
                sys.exit(f"aiconnect_watch.py: Bridge refused: {data.get('error')}")
            elif data.get("type") == "message":
                received = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
                local = received.astimezone().strftime("%H:%M:%S.%f")[:-3]
                print(f"[{local}] {data['from']} -> {data['to']}: {data['content']}")
                return
    sys.exit("aiconnect_watch.py: connection to the Bridge closed - start the watcher again")


def main() -> None:
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
    try:
        asyncio.run(asyncio.wait_for(watch(peer), timeout=MAX_MINUTES * 60))
    except asyncio.TimeoutError:
        print(f"no message for {MAX_MINUTES} min - start the watcher again, nothing to read")
        sys.exit(2)
    except OSError as e:
        sys.exit(f"aiconnect_watch.py: cannot reach the Bridge: {e}")


if __name__ == "__main__":
    main()

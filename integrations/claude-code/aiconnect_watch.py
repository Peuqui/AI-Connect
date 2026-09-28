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
The peer name defaults to the one the MCP client uses: AI_CONNECT_PEER_NAME,
or "<hostname>:<name of the current directory>".
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

peer = (
    sys.argv[1]
    if len(sys.argv) > 1
    else os.environ.get(
        "AI_CONNECT_PEER_NAME", f"{socket.gethostname()}:{Path.cwd().name}"
    )
)
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
            print(f"[{timestamp}] {sender} -> {peer}: {content}")
        sys.exit(0)
    time.sleep(POLL_SECONDS)

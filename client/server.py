"""AI-Connect MCP server over STDIO — one per Claude Code session.

The session's peer name is "Hostname:Project", taken from the directory
Claude Code starts this process in. With the same name, the newer session
takes over and the older one waits on standby until the name is free.
AI_CONNECT_PEER_NAME overrides the name.
"""

import os
import socket
import sys
from pathlib import Path

# Started as a plain script by Claude Code: make the client modules and
# config_loader importable.
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from log_setup import setup_logging
from mcp_app import create_app

peer_name = os.environ.get("AI_CONNECT_PEER_NAME", f"{socket.gethostname()}:{Path.cwd().name}")
# STDIO carries the MCP protocol, so logs go to a file only, one per peer:
# several sessions run at once, and a rotated file must have a single writer
setup_logging(f"mcp-{peer_name.replace(':', '_')}.log")
mcp = create_app(peer_name)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

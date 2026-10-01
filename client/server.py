"""AI-Connect MCP server over STDIO — one per Claude Code session.

The session's peer name is "Hostname:Project", taken from the directory
Claude Code starts this process in. With the same name, the newer session
takes over and the older one is told it was replaced and does not
reconnect. AI_CONNECT_PEER_NAME overrides the name.
"""

import logging
import os
import socket
import sys
from pathlib import Path

# Started as a plain script by Claude Code: make the client modules and
# config_loader importable.
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_app import create_app  # noqa: E402

# STDIO carries the MCP protocol, so logs go to a file only
log_dir = Path.home() / ".config" / "ai-connect"
log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(log_dir / "mcp.log")]
)

peer_name = os.environ.get("AI_CONNECT_PEER_NAME", f"{socket.gethostname()}:{Path.cwd().name}")
mcp = create_app(peer_name)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

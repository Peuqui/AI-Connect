"""AI-Connect MCP server over HTTP/SSE — a permanent service.

For MCP clients that connect to a URL instead of starting a process
(VS Code, Cursor, ...). All of them share one peer: peer.name from the
config, or AI_CONNECT_PEER_NAME.
"""

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_loader import load_config
from log_setup import setup_logging
from mcp_app import create_app

# Also to stdout for the journal
setup_logging("mcp-http.log", logging.StreamHandler())

config = load_config()
mcp = create_app(os.environ.get("AI_CONNECT_PEER_NAME", config["peer"]["name"]))


def main() -> None:
    mcp.run(transport="sse", host=config["mcp"]["host"], port=config["mcp"]["port"])


if __name__ == "__main__":
    main()

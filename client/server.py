"""AI-Connect MCP server over STDIO — one per Claude Code session.

The session's peer name is "Hostname:Project" (see peer_name.py). With
the same name, the newer session takes over and the older one waits on
standby until the name is free.
"""

import os
import signal
import sys
from pathlib import Path

# Started as a plain script by Claude Code: make the client modules and
# config_loader importable.
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from log_setup import setup_logging
from mcp_app import create_app
from peer_name import peer_name, record_session_name

name = peer_name(os.environ, Path.cwd())
# STDIO carries the MCP protocol, so logs go to a file only, one per peer:
# several sessions run at once, and a rotated file must have a single writer
setup_logging(f"mcp-{name.replace(':', '_')}.log")
mcp = create_app(name)


def main() -> None:
    # Claude Code is the parent; its watcher finds the name by CLAUDE_PID
    session_file = record_session_name(os.getppid(), name)
    def end(*_: object) -> None:
        # Claude Code ends its MCP servers with SIGTERM, which would skip the
        # finally below. Remove the file, then end as SIGTERM would have.
        # Windows ends them hard; the file then stays until the next session
        # with that process id overwrites it.
        session_file.unlink(missing_ok=True)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        os.kill(os.getpid(), signal.SIGTERM)

    signal.signal(signal.SIGTERM, end)
    try:
        mcp.run()
    finally:
        session_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

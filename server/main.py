"""Entry point of the AI-Connect Bridge Server."""

import asyncio
import logging
import signal

from config_loader import load_config
from log_setup import setup_logging

from .roles import Roles
from .websocket_server import BridgeServer

# A file as well as stdout: under systemd stdout goes to the journal, but a
# Windows task without a console has nowhere else to log
setup_logging("bridge.log", logging.StreamHandler())
logger = logging.getLogger(__name__)


async def run_server() -> None:
    bridge = load_config()["bridge"]
    server = BridgeServer(
        host=bridge["host"],
        port=bridge["port"],
        history_days=bridge["history_days"],
        roles=Roles(
            peer_token=bridge["token"],
            observer_token_sha256=bridge["observer_token_sha256"],
            user_token_sha256=bridge["user_token_sha256"],
        ),
    )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_stop(*_: object) -> None:
        loop.call_soon_threadsafe(stop_event.set)

    # signal.signal instead of loop.add_signal_handler: the latter does not
    # exist on Windows
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, request_stop)

    await server.start()
    await stop_event.wait()
    logger.info("Shutting down")
    await server.stop()


def main() -> None:
    asyncio.run(run_server())


if __name__ == "__main__":
    main()

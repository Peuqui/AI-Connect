"""Entry point of the AI-Connect Bridge Server."""

import asyncio
import logging
import signal

from config_loader import load_config

from .websocket_server import BridgeServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


async def run_server() -> None:
    bridge = load_config()["bridge"]
    server = BridgeServer(host=bridge["host"], port=bridge["port"], history_days=bridge["history_days"])

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    await server.start()
    await stop_event.wait()
    logger.info("Shutting down")
    await server.stop()


def main() -> None:
    asyncio.run(run_server())


if __name__ == "__main__":
    main()

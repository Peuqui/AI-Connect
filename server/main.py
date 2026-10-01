"""Einstiegspunkt für den AI-Connect Bridge Server."""

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
    """Startet den Bridge Server."""
    config = load_config()
    bridge_config = config["bridge"]

    host = bridge_config["host"]
    port = bridge_config["port"]

    server = BridgeServer(host=host, port=port)

    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def handle_signal():
        logger.info("Shutdown Signal empfangen...")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal)

    await server.start()
    logger.info(f"AI-Connect Bridge läuft auf ws://{host}:{port}")
    logger.info("Drücke Ctrl+C zum Beenden")

    await stop_event.wait()
    await server.stop()
    logger.info("Server beendet")


def main() -> None:
    """CLI Einstiegspunkt."""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

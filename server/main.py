"""Einstiegspunkt für den AI-Connect Bridge Server."""

import asyncio
import logging
import signal
import sys
from pathlib import Path

import yaml

from .websocket_server import BridgeServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    """Lädt die Konfiguration aus config.yaml."""
    config_paths = [
        Path("config.yaml"),
        Path(__file__).parent.parent / "config.yaml",
        Path.home() / ".ai-connect" / "config.yaml"
    ]

    for path in config_paths:
        if path.exists():
            with open(path) as f:
                return yaml.safe_load(f)

    return {"bridge": {"host": "0.0.0.0", "port": 9999}}


async def run_server() -> None:
    """Startet den Bridge Server."""
    config = load_config()
    bridge_config = config.get("bridge", {})

    host = bridge_config.get("host", "0.0.0.0")
    port = bridge_config.get("port", 9999)

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

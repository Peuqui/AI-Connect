"""FastMCP Server für AI-Connect."""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

import yaml
from fastmcp import FastMCP

from .bridge_client import init_client, get_client
from . import tools

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(Path.home() / ".ai-connect" / "mcp.log")]
)
logger = logging.getLogger(__name__)

# MCP Server erstellen
mcp = FastMCP("AI-Connect")


def load_config() -> dict:
    """Lädt die Konfiguration."""
    config_paths = [
        Path.home() / ".ai-connect" / "config.yaml",
        Path(__file__).parent.parent / "config.yaml",
        Path("config.yaml"),
    ]

    for path in config_paths:
        if path.exists():
            with open(path) as f:
                return yaml.safe_load(f)

    return {
        "bridge": {"host": "192.168.0.252", "port": 9999},
        "peer": {"name": "default", "auto_connect": True}
    }


# Tools registrieren
@mcp.tool()
async def peer_list() -> str:
    """Zeigt alle online verbundenen Peers.

    Gibt eine Liste aller aktuell mit dem Bridge Server
    verbundenen KI-Assistenten zurück.
    """
    return await tools.peer_list()


@mcp.tool()
async def peer_send(to: str, message: str, file: Optional[str] = None, lines: Optional[str] = None) -> str:
    """Sendet eine Nachricht an einen anderen Peer.

    Args:
        to: Name des Ziel-Peers (oder '*' für Broadcast)
        message: Die Nachricht die gesendet werden soll
        file: Optional - Dateipfad für Kontext
        lines: Optional - Zeilennummern (z.B. "42-58")

    Beispiele:
        peer_send("minipc", "Was hältst du von diesem Ansatz?")
        peer_send("laptop", "Schau dir mal die Funktion an", file="src/api.py", lines="42-58")
        peer_send("*", "Hat jemand Zeit für ein Review?")
    """
    return await tools.peer_send(to, message, file, lines)


@mcp.tool()
async def peer_read() -> str:
    """Liest alle neuen empfangenen Nachrichten.

    Gibt alle Nachrichten zurück die seit dem letzten Aufruf
    eingegangen sind und markiert sie als gelesen.
    """
    return await tools.peer_read()


@mcp.tool()
async def peer_history(peer: str, limit: int = 20) -> str:
    """Zeigt den Chatverlauf mit einem bestimmten Peer.

    Args:
        peer: Name des Peers
        limit: Maximale Anzahl der Nachrichten (Standard: 20)
    """
    return await tools.peer_history(peer, limit)


@mcp.tool()
async def peer_context(file: str, lines: Optional[str] = None, message: Optional[str] = None) -> str:
    """Teilt den aktuellen Datei-Kontext mit allen Peers.

    Nützlich um anderen KI-Assistenten zu zeigen woran du arbeitest.

    Args:
        file: Pfad zur Datei die geteilt werden soll
        lines: Optional - Zeilennummern (z.B. "42-58")
        message: Optional - Begleitende Nachricht
    """
    return await tools.peer_context(file, lines, message)


@mcp.tool()
async def peer_status() -> str:
    """Zeigt den Verbindungsstatus zum Bridge Server."""
    client = get_client()
    if not client:
        return "Client nicht initialisiert."

    if client.connected:
        return f"Verbunden als '{client.peer_name}' mit Bridge Server {client.host}:{client.port}"
    else:
        return f"Nicht verbunden. Bridge Server: {client.host}:{client.port}"


async def startup() -> None:
    """Initialisiert die Bridge-Verbindung."""
    config = load_config()
    bridge = config.get("bridge", {})
    peer = config.get("peer", {})

    # Peer-Name aus Umgebung oder Config
    peer_name = os.environ.get("AI_CONNECT_PEER_NAME", peer.get("name", "default"))

    if peer.get("auto_connect", True):
        try:
            await init_client(
                host=bridge.get("host", "192.168.0.252"),
                port=bridge.get("port", 9999),
                peer_name=peer_name
            )
            logger.info(f"Mit Bridge verbunden als '{peer_name}'")
        except Exception as e:
            logger.error(f"Verbindung zum Bridge fehlgeschlagen: {e}")


def main() -> None:
    """Startet den MCP Server."""
    # Log-Verzeichnis erstellen
    log_dir = Path.home() / ".ai-connect"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Startup ausführen
    asyncio.get_event_loop().run_until_complete(startup())

    # MCP Server starten
    mcp.run()


if __name__ == "__main__":
    main()

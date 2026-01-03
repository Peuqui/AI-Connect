"""HTTP-basierter MCP Server für AI-Connect.

Läuft als persistenter Service und bietet stabile WebSocket-Verbindung
zum Bridge Server. VS Code verbindet sich per HTTP/SSE.
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

# Füge client-Verzeichnis zum Pfad hinzu
sys.path.insert(0, str(Path(__file__).parent))

import yaml
from fastmcp import FastMCP

from bridge_client import BridgeClient, get_client, init_client

# Log-Verzeichnis erstellen
log_dir = Path.home() / ".config" / "ai-connect"
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "mcp-http.log"),
        logging.StreamHandler()  # Auch auf stdout für systemd
    ]
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    """Lädt die Konfiguration."""
    config_paths = [
        Path.home() / ".config" / "ai-connect" / "config.yaml",
        Path(__file__).parent.parent / "config.yaml",
        Path("config.yaml"),
    ]

    for path in config_paths:
        if path.exists():
            with open(path) as f:
                config = yaml.safe_load(f)
                logger.info(f"Konfiguration geladen von: {path}")
                return config

    logger.warning("Keine Konfigurationsdatei gefunden, verwende Defaults")
    return {
        "bridge": {"host": "192.168.0.252", "port": 9999},
        "peer": {"name": "default", "auto_connect": True},
        "mcp": {"port": 9998}
    }


@asynccontextmanager
async def lifespan(app):
    """Lifecycle manager - verbindet beim Start, trennt beim Ende."""
    config = load_config()
    bridge = config.get("bridge", {})
    peer = config.get("peer", {})

    base_name = os.environ.get("AI_CONNECT_PEER_NAME", peer.get("name", "default"))
    host = bridge.get("host", "192.168.0.252")
    port = bridge.get("port", 9999)

    if peer.get("auto_connect", True):
        try:
            client = await init_client(
                host=host,
                port=port,
                peer_name=base_name
            )
            logger.info(f"Mit Bridge verbunden als '{client.peer_name}'")
        except Exception as e:
            logger.error(f"Verbindung zum Bridge fehlgeschlagen: {e}")

    yield  # Server läuft

    # Cleanup beim Beenden
    client = get_client()
    if client:
        await client.disconnect()
        logger.info("Bridge-Verbindung getrennt")


# MCP Server mit Lifespan erstellen
mcp = FastMCP("AI-Connect", lifespan=lifespan)


def format_timestamp(ts: Optional[str] = None) -> str:
    """Formatiert einen Zeitstempel als HH:MM:SS.mmm."""
    if ts:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.strftime("%H:%M:%S.%f")[:-3]
        except:
            pass
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


# Tools registrieren
@mcp.tool()
async def peer_list() -> str:
    """Zeigt alle online verbundenen Peers.

    Gibt eine Liste aller aktuell mit dem Bridge Server
    verbundenen KI-Assistenten zurück.
    """
    client = get_client()
    if not client or not client.connected:
        return "Nicht mit Bridge Server verbunden."

    peers = await client.list_peers()
    if not peers:
        return "Keine anderen Peers online."

    lines = ["Online Peers:"]
    for peer in peers:
        lines.append(f"  - {peer['name']} [{peer['ip']}]")

    return "\n".join(lines)


@mcp.tool()
async def peer_send(to: str, message: str, file: Optional[str] = None, lines: Optional[str] = None) -> str:
    """Sendet eine Nachricht an einen anderen Peer.

    Args:
        to: Name des Ziel-Peers (oder '*' für Broadcast)
        message: Die Nachricht die gesendet werden soll
        file: Optional - Dateipfad für Kontext
        lines: Optional - Zeilennummern (z.B. "42-58")

    Beispiele:
        peer_send("mini", "Was hältst du von diesem Ansatz?")
        peer_send("Aragon", "Schau dir mal die Funktion an", file="src/api.py", lines="42-58")
        peer_send("*", "Hat jemand Zeit für ein Review?")
    """
    client = get_client()
    if not client or not client.connected:
        return "Nicht mit Bridge Server verbunden."

    context = None
    if file or lines:
        context = {}
        if file:
            context["file"] = file
        if lines:
            context["lines"] = lines

    success = await client.send_message(to, message, context)
    if success:
        timestamp = format_timestamp()
        return f"📤 [{timestamp}] [{client.peer_name} → {to}]: {message}"
    else:
        return "Fehler beim Senden der Nachricht."


@mcp.tool()
async def peer_read() -> str:
    """Liest alle neuen empfangenen Nachrichten.

    Gibt alle Nachrichten zurück die seit dem letzten Aufruf
    eingegangen sind und markiert sie als gelesen.
    """
    client = get_client()
    if not client or not client.connected:
        return "Nicht mit Bridge Server verbunden."

    messages = client.pop_messages()
    if not messages:
        return "Keine neuen Nachrichten."

    me = client.peer_name
    result_lines = []
    for msg in messages:
        sender = msg.get("from", "unbekannt")
        content = msg.get("content", "")
        context = msg.get("context")
        timestamp = format_timestamp(msg.get("timestamp"))

        result_lines.append(f"📥 [{timestamp}] [{sender} → {me}]: {content}")

        if context:
            ctx_parts = []
            if context.get("file"):
                ctx_parts.append(context['file'])
            if context.get("lines"):
                ctx_parts.append(f"Z.{context['lines']}")
            if ctx_parts:
                result_lines.append(f"   📎 Kontext: {' '.join(ctx_parts)}")

    return "\n".join(result_lines)


@mcp.tool()
async def peer_history(peer: str, limit: int = 20) -> str:
    """Zeigt den Chatverlauf mit einem bestimmten Peer.

    Args:
        peer: Name des Peers
        limit: Maximale Anzahl der Nachrichten (Standard: 20)
    """
    client = get_client()
    if not client or not client.connected:
        return "Nicht mit Bridge Server verbunden."

    messages = [m for m in client.messages if m.get("from") == peer or m.get("to") == peer]

    if not messages:
        return f"Kein Chatverlauf mit '{peer}'."

    lines = [f"Chatverlauf mit {peer}:"]
    for msg in messages[-limit:]:
        sender = msg.get("from", "?")
        content = msg.get("content", "")
        timestamp = format_timestamp(msg.get("timestamp"))

        direction = "📤" if sender == client.peer_name else "📥"
        lines.append(f"\n{direction} [{timestamp}] {sender}: {content}")

    return "\n".join(lines)


@mcp.tool()
async def peer_context(file: str, lines: Optional[str] = None, message: Optional[str] = None) -> str:
    """Teilt den aktuellen Datei-Kontext mit allen Peers.

    Nützlich um anderen KI-Assistenten zu zeigen woran du arbeitest.

    Args:
        file: Pfad zur Datei die geteilt werden soll
        lines: Optional - Zeilennummern (z.B. "42-58")
        message: Optional - Begleitende Nachricht
    """
    client = get_client()
    if not client or not client.connected:
        return "Nicht mit Bridge Server verbunden."

    context = {"file": file}
    if lines:
        context["lines"] = lines

    content = message or f"Schaut euch mal {file} an"
    if lines:
        content += f" (Zeilen {lines})"

    success = await client.send_message("*", content, context)
    if success:
        return f"Kontext geteilt: {file}"
    else:
        return "Fehler beim Teilen des Kontexts."


@mcp.tool()
async def peer_status() -> str:
    """Zeigt den Verbindungsstatus zum Bridge Server."""
    client = get_client()
    if not client:
        return "Client nicht initialisiert."

    if client.connected:
        return f"Verbunden als '{client.peer_name}' mit Bridge Server {client.host}:{client.port}"
    elif client.reconnecting:
        return f"Reconnect läuft... (Bridge Server: {client.host}:{client.port})"
    else:
        return f"Nicht verbunden. Bridge Server: {client.host}:{client.port}"


def main() -> None:
    """Startet den HTTP MCP Server."""
    config = load_config()
    mcp_config = config.get("mcp", {})
    port = mcp_config.get("port", 9998)
    host = mcp_config.get("host", "127.0.0.1")

    logger.info(f"Starte MCP HTTP Server auf {host}:{port}")

    try:
        mcp.run(
            transport="sse",
            host=host,
            port=port,
        )
    except KeyboardInterrupt:
        logger.info("Server gestoppt")
    except Exception as e:
        logger.error(f"Server Fehler: {e}")


if __name__ == "__main__":
    main()

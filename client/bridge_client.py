"""WebSocket Client für Verbindung zum AI-Connect Bridge Server."""

import asyncio
import json
import logging
from typing import Optional, Callable
from pathlib import Path

import websockets
from websockets.client import WebSocketClientProtocol

logger = logging.getLogger(__name__)


class BridgeClient:
    """Verbindet sich zum Bridge Server und verwaltet Kommunikation."""

    def __init__(
        self,
        host: str = "192.168.0.252",
        port: int = 9999,
        peer_name: str = "default",
        project: Optional[str] = None
    ):
        self.host = host
        self.port = port
        self._base_name = peer_name  # Original-Name für Registrierung
        self.peer_name = peer_name   # Kann vom Server überschrieben werden
        self.project = project or self._detect_project()

        self._ws: Optional[WebSocketClientProtocol] = None
        self._connected = False
        self._reconnecting = False
        self._should_reconnect = True  # Auto-Reconnect aktiviert
        self._message_queue: list[dict] = []
        self._peers: list[dict] = []
        self._on_message: Optional[Callable] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None

    def _detect_project(self) -> str:
        """Erkennt das aktuelle Projekt basierend auf cwd.

        Gibt immer einen Namen zurück:
        - Git-Repo: Repository-Name
        - Sonst: Verzeichnisname
        """
        cwd = Path.cwd()
        return cwd.name

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def reconnecting(self) -> bool:
        return self._reconnecting

    @property
    def peers(self) -> list[dict]:
        return self._peers.copy()

    @property
    def messages(self) -> list[dict]:
        return self._message_queue.copy()

    def on_message(self, callback: Callable) -> None:
        """Registriert Callback für eingehende Nachrichten."""
        self._on_message = callback

    async def connect(self) -> bool:
        """Verbindet zum Bridge Server."""
        try:
            uri = f"ws://{self.host}:{self.port}"
            # Längere Timeouts für stabilere Verbindungen
            # Ping alle 60s, Timeout nach 300s (5 Minuten)
            self._ws = await websockets.connect(uri, ping_interval=60, ping_timeout=300)
            self._connected = True
            self._reconnecting = False

            # Registrieren - immer den Original-Namen senden, nicht den zugewiesenen
            await self._send({
                "type": "register",
                "name": self._base_name,
                "project": self.project
            })

            # Alte Tasks canceln falls vorhanden
            if self._receive_task and not self._receive_task.done():
                self._receive_task.cancel()
            if self._ping_task and not self._ping_task.done():
                self._ping_task.cancel()

            # Empfangs-Loop starten
            self._receive_task = asyncio.create_task(self._receive_loop())
            # Ping-Loop starten
            self._ping_task = asyncio.create_task(self._ping_loop())

            logger.info(f"Verbunden mit Bridge: {uri}")
            return True

        except Exception as e:
            logger.error(f"Verbindung fehlgeschlagen: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Trennt die Verbindung."""
        self._connected = False
        self._should_reconnect = False  # Auto-Reconnect deaktivieren

        # Tasks stoppen
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
        if self._ping_task and not self._ping_task.done():
            self._ping_task.cancel()

        if self._ws:
            await self._ws.close()
            self._ws = None

    async def send_message(
        self,
        to: str,
        content: str,
        context: Optional[dict] = None
    ) -> bool:
        """Sendet eine Nachricht an einen Peer."""
        if not self._connected:
            return False

        return await self._send({
            "type": "message",
            "to": to,
            "content": content,
            "context": context
        })

    async def list_peers(self) -> list[dict]:
        """Fragt die Liste der online Peers ab."""
        if not self._connected:
            return []

        await self._send({"type": "list_peers"})
        # Warte kurz auf Antwort
        await asyncio.sleep(0.5)
        return self._peers

    async def get_history(self, peer: str, limit: int = 50) -> list[dict]:
        """Holt den Chatverlauf mit einem Peer."""
        if not self._connected:
            return []

        await self._send({
            "type": "history",
            "peer": peer,
            "limit": limit
        })
        # Warte auf Antwort
        await asyncio.sleep(0.5)
        # Hier müssten wir eigentlich auf die Antwort warten
        # Vereinfacht: Antwort kommt über _receive_loop
        return []

    def pop_messages(self) -> list[dict]:
        """Holt und leert die Nachrichtenwarteschlange."""
        messages = self._message_queue.copy()
        self._message_queue.clear()
        return messages

    async def _send(self, data: dict) -> bool:
        """Sendet JSON-Daten über WebSocket."""
        if not self._ws:
            # Verbindung verloren - Reconnect triggern
            if self._should_reconnect and not self._reconnecting:
                asyncio.create_task(self._reconnect())
            return False
        try:
            await self._ws.send(json.dumps(data))
            return True
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Verbindung beim Senden verloren")
            self._connected = False
            self._ws = None
            if self._should_reconnect and not self._reconnecting:
                asyncio.create_task(self._reconnect())
            return False
        except Exception as e:
            logger.error(f"Senden fehlgeschlagen: {e}")
            return False

    async def _receive_loop(self) -> None:
        """Empfängt und verarbeitet eingehende Nachrichten."""
        try:
            async for raw in self._ws:
                try:
                    data = json.loads(raw)
                    msg_type = data.get("type")

                    if msg_type == "message":
                        self._message_queue.append(data)
                        if self._on_message:
                            await self._on_message(data)

                    elif msg_type == "unread":
                        for msg in data.get("messages", []):
                            self._message_queue.append(msg)

                    elif msg_type == "peer_list":
                        self._peers = data.get("peers", [])

                    elif msg_type == "peer_joined":
                        peer = data.get("peer", {})
                        self._peers.append(peer)
                        logger.info(f"Peer beigetreten: {peer.get('name')}")

                    elif msg_type == "peer_left":
                        peer_name = data.get("peer")
                        self._peers = [p for p in self._peers if p.get("name") != peer_name]
                        logger.info(f"Peer gegangen: {peer_name}")

                    elif msg_type == "registered":
                        # Server hat uns einen Namen zugewiesen
                        assigned_name = data.get("name")
                        if assigned_name and assigned_name != self.peer_name:
                            logger.info(f"Server hat Namen zugewiesen: {assigned_name} (angefragt: {self.peer_name})")
                            self.peer_name = assigned_name

                    elif msg_type == "pong":
                        pass  # Heartbeat-Antwort

                except json.JSONDecodeError:
                    logger.warning("Ungültige JSON-Nachricht empfangen")

        except websockets.exceptions.ConnectionClosed:
            logger.warning("Verbindung zum Bridge Server verloren")
            self._connected = False
            self._ws = None
            if self._should_reconnect and not self._reconnecting:
                asyncio.create_task(self._reconnect())

    async def _ping_loop(self) -> None:
        """Sendet regelmäßig Pings."""
        while self._connected:
            await asyncio.sleep(25)
            if self._connected:
                await self._send({"type": "ping"})

    async def _reconnect(self) -> None:
        """Versucht Wiederverbindung mit exponential backoff."""
        if self._reconnecting:
            return  # Bereits ein Reconnect aktiv

        self._reconnecting = True
        delay = 2  # Start mit 2 Sekunden
        max_delay = 30  # Maximal 30 Sekunden warten
        attempt = 0

        while not self._connected and self._should_reconnect:
            attempt += 1
            logger.info(f"Reconnect Versuch {attempt} in {delay}s...")
            await asyncio.sleep(delay)

            if not self._should_reconnect:
                break

            try:
                if await self.connect():
                    logger.info(f"Reconnect erfolgreich nach {attempt} Versuchen")
                    break
            except Exception as e:
                logger.error(f"Reconnect fehlgeschlagen: {e}")

            # Exponential backoff
            delay = min(delay * 1.5, max_delay)

        self._reconnecting = False


# Globale Instanz für MCP Tools
_client: Optional[BridgeClient] = None


def get_client() -> Optional[BridgeClient]:
    """Gibt die globale Client-Instanz zurück."""
    return _client


async def init_client(
    host: str = "192.168.0.252",
    port: int = 9999,
    peer_name: str = "default"
) -> BridgeClient:
    """Initialisiert und verbindet den globalen Client."""
    global _client
    _client = BridgeClient(host=host, port=port, peer_name=peer_name)
    await _client.connect()
    return _client



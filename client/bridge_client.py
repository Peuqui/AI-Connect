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
        self.peer_name = peer_name
        self.project = project or self._detect_project()

        self._ws: Optional[WebSocketClientProtocol] = None
        self._connected = False
        self._message_queue: list[dict] = []
        self._peers: list[dict] = []
        self._on_message: Optional[Callable] = None
        self._reconnect_task: Optional[asyncio.Task] = None

    def _detect_project(self) -> Optional[str]:
        """Erkennt das aktuelle Projekt basierend auf cwd."""
        cwd = Path.cwd()
        if (cwd / ".git").exists():
            return cwd.name
        return None

    @property
    def connected(self) -> bool:
        return self._connected

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
            self._ws = await websockets.connect(uri)
            self._connected = True

            # Registrieren
            await self._send({
                "type": "register",
                "name": self.peer_name,
                "project": self.project
            })

            # Empfangs-Loop starten
            asyncio.create_task(self._receive_loop())
            # Ping-Loop starten
            asyncio.create_task(self._ping_loop())

            logger.info(f"Verbunden mit Bridge: {uri}")
            return True

        except Exception as e:
            logger.error(f"Verbindung fehlgeschlagen: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Trennt die Verbindung."""
        self._connected = False
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
            return False
        try:
            await self._ws.send(json.dumps(data))
            return True
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

                    elif msg_type == "pong":
                        pass  # Heartbeat-Antwort

                except json.JSONDecodeError:
                    logger.warning("Ungültige JSON-Nachricht empfangen")

        except websockets.exceptions.ConnectionClosed:
            logger.warning("Verbindung zum Bridge Server verloren")
            self._connected = False
            asyncio.create_task(self._reconnect())

    async def _ping_loop(self) -> None:
        """Sendet regelmäßig Pings."""
        while self._connected:
            await asyncio.sleep(25)
            if self._connected:
                await self._send({"type": "ping"})

    async def _reconnect(self) -> None:
        """Versucht Wiederverbindung."""
        delay = 5
        while not self._connected:
            logger.info(f"Wiederverbindung in {delay}s...")
            await asyncio.sleep(delay)
            if await self.connect():
                break
            delay = min(delay * 2, 60)


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

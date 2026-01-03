"""WebSocket Server für AI-Connect Bridge."""

import asyncio
import json
import logging
from typing import Optional

import websockets
from websockets.server import WebSocketServerProtocol

from .peer_registry import PeerRegistry
from .message_store import MessageStore

logger = logging.getLogger(__name__)


class BridgeServer:
    """WebSocket Server der Nachrichten zwischen Peers routet."""

    def __init__(self, host: str = "0.0.0.0", port: int = 9999):
        self.host = host
        self.port = port
        self.registry = PeerRegistry()
        self.store = MessageStore()
        self._server = None

        self.registry.on_join(self._broadcast_peer_joined)
        self.registry.on_leave(self._broadcast_peer_left)

    async def start(self) -> None:
        """Startet den WebSocket Server."""
        await self.store.connect()
        self._server = await websockets.serve(
            self._handle_connection,
            self.host,
            self.port
        )
        logger.info(f"Bridge Server gestartet auf ws://{self.host}:{self.port}")

        # Heartbeat-Cleanup Task starten
        asyncio.create_task(self._heartbeat_loop())

    async def stop(self) -> None:
        """Stoppt den Server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        await self.store.close()

    async def _handle_connection(self, websocket: WebSocketServerProtocol) -> None:
        """Verarbeitet eine neue WebSocket-Verbindung."""
        peer_name: Optional[str] = None
        client_ip = websocket.remote_address[0] if websocket.remote_address else "unknown"

        try:
            async for raw_message in websocket:
                try:
                    message = json.loads(raw_message)
                    msg_type = message.get("type")

                    if msg_type == "register":
                        requested_name = message.get("name")
                        project = message.get("project")
                        peer = await self.registry.register(requested_name, client_ip, websocket, project)
                        peer_name = peer.name  # Kann von requested_name abweichen!

                        # Zugewiesenen Namen an Client senden
                        await websocket.send(json.dumps({
                            "type": "registered",
                            "name": peer_name,
                            "requested": requested_name
                        }))

                        if peer_name != requested_name:
                            logger.info(f"Peer registriert: {peer_name} (angefragt: {requested_name}) ({client_ip})")
                        else:
                            logger.info(f"Peer registriert: {peer_name} ({client_ip})")

                        # Ungelesene Nachrichten senden
                        unread = await self.store.get_unread(peer_name)
                        if unread:
                            await websocket.send(json.dumps({
                                "type": "unread",
                                "messages": unread
                            }))
                            await self.store.mark_delivered([m["id"] for m in unread])

                    elif msg_type == "ping":
                        if peer_name:
                            self.registry.update_ping(peer_name)
                        await websocket.send(json.dumps({"type": "pong"}))

                    elif msg_type == "message":
                        await self._route_message(message, peer_name)

                    elif msg_type == "list_peers":
                        peers = self.registry.get_all()
                        await websocket.send(json.dumps({
                            "type": "peer_list",
                            "peers": peers
                        }))

                    elif msg_type == "history":
                        other_peer = message.get("peer")
                        limit = message.get("limit", 50)
                        history = await self.store.get_history(peer_name, other_peer, limit)
                        await websocket.send(json.dumps({
                            "type": "history",
                            "peer": other_peer,
                            "messages": history
                        }))

                except json.JSONDecodeError:
                    logger.warning(f"Ungültige JSON-Nachricht von {client_ip}")

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Verbindung geschlossen: {peer_name or client_ip}")
        finally:
            if peer_name:
                await self.registry.unregister(peer_name)

    async def _route_message(self, message: dict, from_peer: str) -> None:
        """Routet eine Nachricht zum Ziel-Peer."""
        to_peer = message.get("to")
        content = message.get("content", "")
        context = message.get("context")

        # Nachricht speichern
        msg_id = await self.store.store(from_peer, to_peer, content, context)

        # Nachricht für Übertragung vorbereiten
        outgoing = {
            "type": "message",
            "id": msg_id,
            "from": from_peer,
            "to": to_peer,
            "content": content,
            "context": context
        }

        if to_peer == "*":
            # Broadcast an alle außer Sender
            for peer in self.registry.get_all():
                if peer["name"] != from_peer:
                    target = self.registry.get(peer["name"])
                    if target and target.websocket:
                        try:
                            await target.websocket.send(json.dumps(outgoing))
                            await self.store.mark_delivered([msg_id])
                        except Exception as e:
                            logger.warning(f"Fehler beim Senden an {peer['name']}: {e}")
        else:
            # Direkte Nachricht
            target = self.registry.get(to_peer)
            if target and target.websocket:
                try:
                    await target.websocket.send(json.dumps(outgoing))
                    await self.store.mark_delivered([msg_id])
                except Exception as e:
                    logger.warning(f"Fehler beim Senden an {to_peer}: {e}")

    async def _broadcast_peer_joined(self, peer) -> None:
        """Informiert alle Peers über neuen Teilnehmer."""
        message = json.dumps({
            "type": "peer_joined",
            "peer": {
                "name": peer.name,
                "ip": peer.ip,
                "project": peer.project
            }
        })
        await self._broadcast(message, exclude=peer.name)

    async def _broadcast_peer_left(self, peer) -> None:
        """Informiert alle Peers über Austritt."""
        message = json.dumps({
            "type": "peer_left",
            "peer": peer.name
        })
        await self._broadcast(message, exclude=peer.name)

    async def _broadcast(self, message: str, exclude: Optional[str] = None) -> None:
        """Sendet Nachricht an alle Peers."""
        for peer_info in self.registry.get_all():
            if peer_info["name"] != exclude:
                peer = self.registry.get(peer_info["name"])
                if peer and peer.websocket:
                    try:
                        await peer.websocket.send(message)
                    except Exception:
                        pass

    async def _heartbeat_loop(self) -> None:
        """Prüft regelmäßig auf inaktive Peers."""
        while True:
            await asyncio.sleep(30)
            stale = await self.registry.cleanup_stale()
            for name in stale:
                logger.info(f"Peer timeout: {name}")

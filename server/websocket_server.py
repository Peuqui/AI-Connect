"""WebSocket server of the AI-Connect Bridge: routes messages between peers."""

import asyncio
import json
import logging

import websockets
from websockets.asyncio.server import Server, ServerConnection

from .message_store import MessageStore
from .peer_registry import Peer, PeerRegistry

logger = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 60
HISTORY_CLEANUP_SECONDS = 24 * 60 * 60
# Sender of the Bridge's own notices; not of the form Host:Project, so no
# peer can have it
BRIDGE_SENDER = "Bridge"
TAKEOVER_NOTICE = (
    "Another session with the name {name} was online and has been put on standby; "
    "it takes the name back once this session leaves. Two sessions in the same "
    "project directory share a name: close one, or set AI_CONNECT_PEER_NAME."
)


class BridgeServer:
    """Routes messages between peers and keeps them in the message store."""

    def __init__(self, host: str, port: int, history_days: int):
        self.host = host
        self.port = port
        self.history_days = history_days
        self.registry = PeerRegistry()
        self.store = MessageStore()
        self._server: Server | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._history_cleanup_task: asyncio.Task | None = None
        # Watchers per peer name: connections that want to hear about new
        # messages for that peer without registering as it
        self._watchers: dict[str, set[ServerConnection]] = {}
        # Standby connections per peer name: replaced sessions that wait for
        # the name to become free again
        self._standby: dict[str, set[ServerConnection]] = {}

        self.registry.on_join(self._announce_joined)
        self.registry.on_leave(self._handle_left)

    async def start(self) -> None:
        await self.store.connect()
        self._server = await websockets.serve(self._handle_connection, self.host, self.port)
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._history_cleanup_task = asyncio.create_task(self._history_cleanup_loop())
        logger.info(f"Bridge Server listening on ws://{self.host}:{self.port}")

    async def stop(self) -> None:
        for task in (self._heartbeat_task, self._history_cleanup_task):
            if task:
                task.cancel()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        await self.store.close()

    async def _handle_connection(self, websocket: ServerConnection) -> None:
        """Serve one peer connection until it closes."""
        peer_name: str | None = None
        client_ip = websocket.remote_address[0] if websocket.remote_address else "unknown"

        try:
            async for raw_message in websocket:
                try:
                    message = json.loads(raw_message)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from {client_ip}")
                    continue
                msg_type = message.get("type")

                if msg_type == "register":
                    name = message.get("name")
                    if not name:
                        await self._send_error(websocket, "'register' needs a 'name'")
                        continue
                    taken = self.registry.get(name) is not None
                    if taken and message.get("standby"):
                        # A replaced session must not push the new one out again
                        self._standby.setdefault(name, set()).add(websocket)
                        await websocket.send(json.dumps({"type": "standby", "name": name}))
                        logger.info(f"Peer on standby: {name} ({client_ip})")
                        continue
                    self._standby.get(name, set()).discard(websocket)
                    await self.registry.register(name, client_ip, websocket)
                    peer_name = name
                    await websocket.send(json.dumps({"type": "registered", "name": name}))
                    logger.info(f"Peer registered: {name} ({client_ip})")

                    unread = await self.store.get_unread(name)
                    if unread:
                        await websocket.send(json.dumps({"type": "unread", "messages": unread}))
                        await self.store.mark_delivered([m["id"] for m in unread])
                    if taken:
                        # Goes to the new session and wakes the watchers of
                        # both sessions, which watch the same name
                        await self._route_message(
                            {"to": name, "content": TAKEOVER_NOTICE.format(name=name)}, BRIDGE_SENDER
                        )

                elif msg_type == "ping":
                    if peer_name:
                        self.registry.update_ping(peer_name)
                    await websocket.send(json.dumps({"type": "pong"}))

                elif msg_type == "watch":
                    watched = message.get("peer")
                    if not watched:
                        await self._send_error(websocket, "'watch' needs a 'peer'")
                        continue
                    self._watchers.setdefault(watched, set()).add(websocket)
                    await websocket.send(json.dumps({"type": "watching", "peer": watched}))

                elif msg_type == "list_peers":
                    await websocket.send(json.dumps({
                        "type": "peer_list",
                        "peers": [
                            {"name": p.name, "ip": p.ip, "connected_at": p.connected_at}
                            for p in self.registry.all()
                        ]
                    }))

                elif peer_name is None:
                    await self._send_error(websocket, f"'{msg_type}' needs 'register' first")

                elif msg_type == "message":
                    await self._route_message(message, peer_name)

                elif msg_type == "history":
                    history = await self.store.get_history(
                        peer_name, message.get("peer", ""), message.get("limit", 50)
                    )
                    await websocket.send(json.dumps({
                        "type": "history",
                        "peer": message.get("peer", ""),
                        "messages": history
                    }))

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            for connections in (*self._watchers.values(), *self._standby.values()):
                connections.discard(websocket)
            logger.info(f"Connection closed: {peer_name or client_ip}")
            # Only remove the peer if this connection is still the active one;
            # after a takeover the name belongs to the new connection.
            if peer_name:
                current = self.registry.get(peer_name)
                if current and current.websocket is websocket:
                    await self.registry.unregister(peer_name)

    async def _send_error(self, websocket: ServerConnection, error: str) -> None:
        await websocket.send(json.dumps({"type": "error", "error": error}))

    async def _route_message(self, message: dict, from_peer: str) -> None:
        """Deliver a message; direct messages to offline peers wait in the store.

        A broadcast ("*") reaches the peers online right now. Waiting for
        offline peers would need delivery tracking per recipient, and a
        broadcast is about the present ("is anyone using GPU 2?").
        """
        to_peer = message.get("to")
        if not to_peer:
            logger.warning(f"Message from {from_peer} without recipient dropped")
            return

        if to_peer == "*":
            recipients = [p for p in self.registry.all() if p.name != from_peer]
        else:
            target = self.registry.get(to_peer)
            recipients = [target] if target else []

        outgoing = await self.store.store(
            from_peer,
            to_peer,
            message.get("content", ""),
            message.get("context"),
            delivered=to_peer == "*" or bool(recipients)
        )
        outgoing["type"] = "message"
        payload = json.dumps(outgoing)
        for peer in recipients:
            await self._send_to(peer, payload)
        await self._notify_watchers(to_peer, from_peer, payload)

    async def _notify_watchers(self, to_peer: str, from_peer: str, payload: str) -> None:
        """Tell the watchers of every recipient that a message arrived."""
        if to_peer == "*":
            watched = [name for name in self._watchers if name != from_peer]
        else:
            watched = [to_peer]
        for name in watched:
            for watcher in list(self._watchers.get(name, ())):
                try:
                    await watcher.send(payload)
                except websockets.exceptions.ConnectionClosed:
                    self._watchers[name].discard(watcher)

    async def _send_to(self, peer: Peer, payload: str) -> None:
        try:
            await peer.websocket.send(payload)
        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"Could not deliver to {peer.name}: connection closed")

    async def _announce_joined(self, peer: Peer) -> None:
        payload = json.dumps({"type": "peer_joined", "peer": {"name": peer.name, "ip": peer.ip}})
        for other in self.registry.all():
            if other.name != peer.name:
                await self._send_to(other, payload)

    async def _handle_left(self, peer: Peer) -> None:
        await self._announce_left(peer)
        await self._offer_name(peer.name)

    async def _announce_left(self, peer: Peer) -> None:
        payload = json.dumps({"type": "peer_left", "peer": peer.name})
        for other in self.registry.all():
            await self._send_to(other, payload)

    async def _offer_name(self, name: str) -> None:
        """Tell the standby connections of a name that it is free.

        Each answers with a standby register; the first one gets the name,
        the others stay on standby.
        """
        payload = json.dumps({"type": "name_free", "name": name})
        for connection in list(self._standby.get(name, ())):
            try:
                await connection.send(payload)
            except websockets.exceptions.ConnectionClosed:
                self._standby[name].discard(connection)

    async def _heartbeat_loop(self) -> None:
        """Drop peers whose connection is dead or that stopped pinging."""
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            for peer in self.registry.all():
                try:
                    await peer.websocket.send(json.dumps({"type": "ping"}))
                except websockets.exceptions.ConnectionClosed:
                    logger.info(f"Connection dead: {peer.name}")
                    await self.registry.unregister(peer.name)
            for name in await self.registry.cleanup_stale():
                logger.info(f"Peer timed out: {name}")

    async def _history_cleanup_loop(self) -> None:
        """Delete messages older than history_days, at start and then daily."""
        while True:
            deleted = await self.store.delete_older_than(self.history_days)
            logger.info(f"History cleanup: {deleted} messages older than {self.history_days} days deleted")
            await asyncio.sleep(HISTORY_CLEANUP_SECONDS)

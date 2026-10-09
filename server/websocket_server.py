"""WebSocket server of the AI-Connect Bridge: routes messages between peers."""

import asyncio
import json
import logging
from http import HTTPStatus

import websockets
from websockets.asyncio.server import Server, ServerConnection
from websockets.http11 import Request, Response

from .message_store import MessageStore
from .observers import Observers
from .peer_registry import Peer, PeerRegistry, utc_now
from .roles import Roles
from .user_send import is_user_name, user_sender, valid_recipients

logger = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 60
HISTORY_CLEANUP_SECONDS = 24 * 60 * 60
# Messages in one history_all page; the contents often carry code and files
HISTORY_ALL_MAX_LIMIT = 1000
# Sender of the Bridge's own notices; not of the form Host:Project, so no
# peer can have it
BRIDGE_SENDER = "Bridge"
PEER_STATES = ("busy", "idle", "waiting")
IDLE_NOTICE = "{name} is done and idle."
WAITING_NOTICE = "{name} is waiting for approval: {detail}"
TAKEOVER_NOTICE = (
    "Another session with the name {name} was online and has been put on standby; "
    "it takes the name back once this session leaves. Two sessions in the same "
    "project directory share a name: close one, or start the second with AI_CONNECT_PEER_SUFFIX."
)


class BridgeServer:
    """Routes messages between peers and keeps them in the message store."""

    def __init__(self, host: str, port: int, history_days: int, roles: Roles):
        self.host = host
        self.port = port
        self.history_days = history_days
        self.roles = roles
        self.registry = PeerRegistry()
        self.store = MessageStore()
        self.observers = Observers()
        self._server: Server | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._history_cleanup_task: asyncio.Task | None = None
        # Watchers per peer name: connections that want to hear about new
        # messages for that peer without registering as it
        self._watchers: dict[str, set[ServerConnection]] = {}
        # The Claude Code session each watcher belongs to: one watcher per
        # session, because its hooks start one at every turn end
        self._watcher_sessions: dict[ServerConnection, str] = {}
        # Standby connections per peer name: replaced sessions that wait for
        # the name to become free again
        self._standby: dict[str, set[ServerConnection]] = {}
        # Who wants to hear when a peer is done: peer name -> subscriber
        # names; each subscription fires once
        self._idle_subscribers: dict[str, set[str]] = {}

        self.registry.on_join(self._announce_joined)
        self.registry.on_leave(self._handle_left)
        self.store.on_stored(self.observers.broadcast)

    async def start(self) -> None:
        await self.store.connect()
        self._server = await websockets.serve(
            self._handle_connection, self.host, self.port, process_request=self._check_token
        )
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

    def _role(self, request: Request) -> str | None:
        return self.roles.role_for(request.headers.get("Authorization", ""))

    def _check_token(self, connection: ServerConnection, request: Request) -> Response | None:
        """Refuse the handshake unless it carries a known token.

        Checked once per connection, so every message type, the watchers
        and list_peers are covered alike; the token's role decides which
        message types the connection may send.
        """
        if self._role(request) is not None:
            return None
        client_ip = connection.remote_address[0] if connection.remote_address else "unknown"
        logger.warning(f"Refused connection with a missing or wrong token from {client_ip}")
        return connection.respond(HTTPStatus.UNAUTHORIZED, "Missing or wrong AI-Connect token\n")

    async def _handle_connection(self, websocket: ServerConnection) -> None:
        """Serve one peer connection until it closes."""
        peer_name: str | None = None
        client_ip = websocket.remote_address[0] if websocket.remote_address else "unknown"
        # The handshake passed _check_token: the request is there and its token known
        assert websocket.request is not None
        role = self._role(websocket.request)
        assert role is not None

        try:
            async for raw_message in websocket:
                try:
                    message = json.loads(raw_message)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from {client_ip}")
                    continue
                msg_type = message.get("type")
                if not self.roles.allows(role, msg_type):
                    await self._send_error(websocket, f"'{msg_type}' is not allowed for the role {role}")
                    continue

                if msg_type == "register":
                    name = message.get("name")
                    if not name:
                        await self._send_error(websocket, "'register' needs a 'name'")
                        continue
                    if is_user_name(name):
                        await self._send_error(websocket, f"'{name}': names starting with User: belong to users")
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
                    if is_user_name(watched):
                        # Replies to the user are read with the observer token
                        await self._send_error(websocket, f"'{watched}': names starting with User: belong to users")
                        continue
                    session = message.get("session")
                    if session and session in self._watcher_sessions.values():
                        await websocket.send(json.dumps({"type": "already_watching", "peer": watched}))
                        continue
                    self._watchers.setdefault(watched, set()).add(websocket)
                    if session:
                        self._watcher_sessions[websocket] = session
                    await websocket.send(json.dumps({"type": "watching", "peer": watched}))
                    # A message that came after the session last read, while
                    # no watcher ran, wakes the session at once
                    since = message.get("since")
                    missed = await self.store.latest_to_since(watched, since) if since else None
                    if missed:
                        await websocket.send(json.dumps({**missed, "type": "message"}))

                elif msg_type == "list_peers":
                    await websocket.send(json.dumps({"type": "peer_list", "peers": self._peer_list()}))

                elif msg_type == "observe":
                    self.observers.add(websocket)
                    await websocket.send(json.dumps({"type": "observing"}))
                    logger.info(f"Observer connected ({client_ip})")

                elif msg_type == "history_all":
                    since, limit = message.get("since"), message.get("limit")
                    if not since or not isinstance(limit, int) or not 0 < limit <= HISTORY_ALL_MAX_LIMIT:
                        await self._send_error(
                            websocket, f"'history_all' needs 'since' and a 'limit' of 1 to {HISTORY_ALL_MAX_LIMIT}"
                        )
                        continue
                    history = await self.store.history_all(since, message.get("before"), limit)
                    await websocket.send(json.dumps({"type": "history_all", "messages": history}))

                elif msg_type == "user_send":
                    sender = user_sender(message.get("as"))
                    recipients = valid_recipients(message.get("to"))
                    if sender is None or recipients is None:
                        await self._send_error(
                            websocket,
                            "'user_send' needs 'as' (letters, digits, . _ -) and 'to' (a list of peer names or \"*\")",
                        )
                        continue
                    sent = []
                    for recipient in recipients:
                        stored, online = await self._route_message(
                            {"to": recipient, "content": message.get("content", "")}, sender
                        )
                        sent.append({"to": recipient, "id": stored["id"], "online": online})
                    await websocket.send(json.dumps({"type": "user_sent", "sent": sent}))
                    logger.info(f"{sender} sent to {', '.join(recipients)} ({client_ip})")

                elif peer_name is None:
                    await self._send_error(websocket, f"'{msg_type}' needs 'register' first")

                elif msg_type == "message":
                    if not message.get("to"):
                        await self._send_error(websocket, "'message' needs a 'to'")
                        continue
                    await self._route_message(message, peer_name)

                elif msg_type == "set_state":
                    state = message.get("state")
                    if state not in PEER_STATES:
                        await self._send_error(websocket, f"'set_state' needs a state out of {PEER_STATES}")
                        continue
                    await self._set_state(peer_name, state, message.get("detail", ""))

                elif msg_type == "set_status":
                    peer = self.registry.get(peer_name)
                    if peer:
                        peer.status = message.get("status", "")

                elif msg_type == "notify_when_idle":
                    watched = message.get("peer")
                    if not watched:
                        await self._send_error(websocket, "'notify_when_idle' needs a 'peer'")
                        continue
                    await self._subscribe_idle(peer_name, watched)

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
            self._watcher_sessions.pop(websocket, None)
            self.observers.discard(websocket)
            logger.info(f"Connection closed: {peer_name or client_ip}")
            # Only remove the peer if this connection is still the active one;
            # after a takeover the name belongs to the new connection.
            if peer_name:
                current = self.registry.get(peer_name)
                if current and current.websocket is websocket:
                    await self.registry.unregister(peer_name)

    async def _send_error(self, websocket: ServerConnection, error: str) -> None:
        await websocket.send(json.dumps({"type": "error", "error": error}))

    async def _set_state(self, name: str, state: str, detail: str) -> None:
        """Record a peer's state; done or waiting fires its subscriptions."""
        peer = self.registry.get(name)
        if peer is None:
            return
        peer.state, peer.state_detail, peer.state_since = state, detail, utc_now().isoformat()
        if state == "busy":
            return
        notice = IDLE_NOTICE.format(name=name) if state == "idle" else WAITING_NOTICE.format(name=name, detail=detail)
        for subscriber in self._idle_subscribers.pop(name, set()):
            await self._route_message({"to": subscriber, "content": notice}, BRIDGE_SENDER)

    async def _subscribe_idle(self, subscriber: str, watched: str) -> None:
        """Notify subscriber once when watched is done; at once if it already is."""
        peer = self.registry.get(watched)
        if peer and peer.state == "idle":
            await self._route_message({"to": subscriber, "content": IDLE_NOTICE.format(name=watched)}, BRIDGE_SENDER)
            return
        self._idle_subscribers.setdefault(watched, set()).add(subscriber)

    async def _route_message(self, message: dict, from_peer: str) -> tuple[dict, bool]:
        """Deliver a message; direct messages to offline peers wait in the store.

        A broadcast ("*") reaches the peers online right now. Waiting for
        offline peers would need delivery tracking per recipient, and a
        broadcast is about the present ("is anyone using GPU 2?"). A message
        to a user counts as delivered at once: users read along as
        observers and never register, so it must not pile up as unread.

        Returns the stored message and whether a recipient was online.
        """
        to_peer = message["to"]

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
            delivered=to_peer == "*" or bool(recipients) or is_user_name(to_peer)
        )
        payload = json.dumps({**outgoing, "type": "message"})
        for peer in recipients:
            await self._send_to(peer, payload)
        await self._notify_watchers(to_peer, from_peer, payload)
        return outgoing, bool(recipients)

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

    def _peer_list(self) -> list[dict]:
        return [
            {
                "name": p.name,
                "ip": p.ip,
                "connected_at": p.connected_at,
                "state": p.state,
                "state_detail": p.state_detail,
                "state_since": p.state_since,
                "status": p.status,
            }
            for p in self.registry.all()
        ]

    async def _announce_joined(self, peer: Peer) -> None:
        payload = json.dumps({"type": "peer_joined", "peer": {"name": peer.name, "ip": peer.ip}})
        for other in self.registry.all():
            if other.name != peer.name:
                await self._send_to(other, payload)
        await self.observers.peers_changed(self._peer_list())

    async def _handle_left(self, peer: Peer) -> None:
        await self._announce_left(peer)
        await self._offer_name(peer.name)

    async def _announce_left(self, peer: Peer) -> None:
        payload = json.dumps({"type": "peer_left", "peer": peer.name})
        for other in self.registry.all():
            await self._send_to(other, payload)
        await self.observers.peers_changed(self._peer_list())

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

"""WebSocket client that connects an MCP server to the AI-Connect Bridge."""

import asyncio
import json
import logging
from typing import Optional

import websockets
from websockets import ClientConnection

logger = logging.getLogger(__name__)

# How long a request to the Bridge (peer list, history) may take
REQUEST_TIMEOUT_SECONDS = 5.0
PING_INTERVAL_SECONDS = 25


class BridgeClient:
    """Keeps the connection to the Bridge Server and queues incoming messages."""

    def __init__(self, host: str, port: int, peer_name: str):
        self.host = host
        self.port = port
        self.peer_name = peer_name

        self._ws: Optional[ClientConnection] = None
        self._connected = False
        self._reconnecting = False
        self._should_reconnect = True
        self._message_queue: list[dict] = []
        self._message_event: Optional[asyncio.Event] = None
        # Answers to requests, keyed by the response type ("peer_list", "history")
        self._pending: dict[str, asyncio.Future] = {}
        self._receive_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None

    def _ensure_event(self) -> asyncio.Event:
        """Create the message event lazily inside the running event loop."""
        if self._message_event is None:
            self._message_event = asyncio.Event()
        return self._message_event

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def reconnecting(self) -> bool:
        return self._reconnecting

    async def connect(self) -> bool:
        """Connect to the Bridge and register under peer_name."""
        uri = f"ws://{self.host}:{self.port}"
        try:
            self._ws = await websockets.connect(uri, ping_interval=60, ping_timeout=300)
        except (OSError, websockets.exceptions.InvalidHandshake) as e:
            logger.error(f"Cannot reach Bridge at {uri}: {e}")
            self._connected = False
            return False

        self._connected = True
        self._reconnecting = False
        await self._send({"type": "register", "name": self.peer_name})

        for task in (self._receive_task, self._ping_task):
            if task and not task.done():
                task.cancel()
        self._receive_task = asyncio.create_task(self._receive_loop())
        self._ping_task = asyncio.create_task(self._ping_loop())

        logger.info(f"Connected to Bridge at {uri} as '{self.peer_name}'")
        return True

    async def disconnect(self) -> None:
        """Close the connection and stop reconnecting."""
        self._connected = False
        self._should_reconnect = False
        for task in (self._reconnect_task, self._receive_task, self._ping_task):
            if task and not task.done():
                task.cancel()
        if self._ws:
            await self._ws.close()
            self._ws = None

    def start_reconnect(self) -> None:
        """Keep trying to reach the Bridge in the background."""
        if self._should_reconnect and not self._reconnecting:
            self._reconnect_task = asyncio.create_task(self._reconnect())

    async def send_message(self, to: str, content: str, context: Optional[dict] = None) -> bool:
        """Send a message to a peer (or '*' for every online peer)."""
        if not self._connected:
            return False
        return await self._send({
            "type": "message",
            "to": to,
            "content": content,
            "context": context
        })

    async def list_peers(self) -> list[dict]:
        """Ask the Bridge for the peers that are online."""
        response = await self._request({"type": "list_peers"}, "peer_list")
        return response.get("peers", [])

    async def get_history(self, peer: str, limit: int) -> list[dict]:
        """Ask the Bridge for the conversation with a peer, oldest first."""
        response = await self._request({"type": "history", "peer": peer, "limit": limit}, "history")
        return response.get("messages", [])

    def pop_messages(self) -> list[dict]:
        """Return and clear the received messages."""
        messages = self._message_queue.copy()
        self._message_queue.clear()
        if self._message_event is not None:
            self._message_event.clear()
        return messages

    async def wait_for_messages(self, timeout: float) -> list[dict]:
        """Wait until messages arrive or the timeout passes, then return them.

        Returns at once when messages are already queued.
        """
        if not self._message_queue:
            try:
                await asyncio.wait_for(self._ensure_event().wait(), timeout=timeout)
            except asyncio.TimeoutError:
                return []
        return self.pop_messages()

    async def _request(self, data: dict, response_type: str) -> dict:
        """Send a request and wait for the Bridge's answer of response_type."""
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[response_type] = future
        try:
            if not await self._send(data):
                raise ConnectionError("Not connected to the Bridge")
            return await asyncio.wait_for(future, timeout=REQUEST_TIMEOUT_SECONDS)
        finally:
            self._pending.pop(response_type, None)

    async def _send(self, data: dict) -> bool:
        """Send JSON over the WebSocket; a lost connection starts a reconnect."""
        if not self._ws:
            self.start_reconnect()
            return False
        try:
            await self._ws.send(json.dumps(data))
            return True
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Connection lost while sending")
            self._connected = False
            self._ws = None
            self.start_reconnect()
            return False

    async def _receive_loop(self) -> None:
        """Handle everything the Bridge sends."""
        ws = self._ws
        if ws is None:
            return
        try:
            async for raw in ws:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("Received invalid JSON from the Bridge")
                    continue
                self._handle(data)
        except websockets.exceptions.ConnectionClosed:
            pass
        # A clean close by the Bridge ends the loop without an exception, so
        # the state is reset here for both cases.
        logger.warning("Connection to the Bridge lost")
        self._connected = False
        self._ws = None
        self.start_reconnect()

    def _handle(self, data: dict) -> None:
        """Dispatch one message from the Bridge."""
        msg_type = data.get("type")

        if msg_type == "message":
            self._message_queue.append(data)
            self._ensure_event().set()

        elif msg_type == "unread":
            messages = data.get("messages", [])
            self._message_queue.extend(messages)
            if messages:
                self._ensure_event().set()

        elif msg_type in self._pending:
            future = self._pending[msg_type]
            if not future.done():
                future.set_result(data)

        elif msg_type == "peer_joined":
            logger.info(f"Peer joined: {data.get('peer', {}).get('name')}")

        elif msg_type == "peer_left":
            logger.info(f"Peer left: {data.get('peer')}")

        elif msg_type == "replaced":
            # Another session took over our name; reconnecting would only
            # push it out again.
            logger.warning(f"Peer name '{self.peer_name}' taken over by another session, not reconnecting")
            self._should_reconnect = False

        elif msg_type == "error":
            logger.error(f"Bridge reported an error: {data.get('error')}")

    async def _ping_loop(self) -> None:
        """Tell the Bridge regularly that this peer is alive."""
        while self._connected:
            await asyncio.sleep(PING_INTERVAL_SECONDS)
            if self._connected:
                await self._send({"type": "ping"})

    async def _reconnect(self) -> None:
        """Reconnect with exponential backoff, capped at 30 seconds."""
        self._reconnecting = True
        delay: float = 2
        attempt = 0
        while not self._connected and self._should_reconnect:
            attempt += 1
            logger.info(f"Reconnect attempt {attempt} in {delay:.0f} s")
            await asyncio.sleep(delay)
            if self._should_reconnect and await self.connect():
                logger.info(f"Reconnected after {attempt} attempts")
                break
            delay = min(delay * 1.5, 30)
        self._reconnecting = False


# The one client of this MCP server process, used by the tools
_client: Optional[BridgeClient] = None


def get_client() -> Optional[BridgeClient]:
    """Return this process's Bridge client."""
    return _client


async def init_client(host: str, port: int, peer_name: str) -> BridgeClient:
    """Create the Bridge client and connect; if the Bridge is unreachable,
    keep trying in the background."""
    global _client
    _client = BridgeClient(host=host, port=port, peer_name=peer_name)
    if not await _client.connect():
        _client.start_reconnect()
    return _client

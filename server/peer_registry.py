"""Registry of the peers connected to the Bridge."""

import json
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from websockets.exceptions import ConnectionClosed

PeerCallback = Callable[["Peer"], Awaitable[None]]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Peer:
    """A connected peer."""
    name: str
    ip: str
    connected_at: str
    websocket: Any = None
    last_ping: datetime = field(default_factory=utc_now)


class PeerRegistry:
    """Keeps track of all connected peers."""

    def __init__(self, timeout_seconds: int = 300):
        self._peers: dict[str, Peer] = {}
        self._timeout = timeout_seconds
        self._on_join: PeerCallback | None = None
        self._on_leave: PeerCallback | None = None

    def on_join(self, callback: PeerCallback) -> None:
        self._on_join = callback

    def on_leave(self, callback: PeerCallback) -> None:
        self._on_leave = callback

    async def register(self, name: str, ip: str, websocket: Any) -> Peer:
        """Register a peer under the name it sent ("Host:Project").

        If the name is already online, the new connection takes over: the
        old one is told it was replaced, so it reconnects on standby instead
        of pushing the new one out again, and is closed.
        """
        existing = self._peers.pop(name, None)
        if existing and existing.websocket:
            # The old connection may already be dead; it is gone either way.
            with suppress(ConnectionClosed):
                await existing.websocket.send(json.dumps({"type": "replaced"}))
                await existing.websocket.close()

        peer = Peer(
            name=name,
            ip=ip,
            connected_at=utc_now().isoformat(),
            websocket=websocket
        )
        self._peers[name] = peer
        if self._on_join:
            await self._on_join(peer)
        return peer

    async def unregister(self, name: str) -> None:
        peer = self._peers.pop(name, None)
        if peer and self._on_leave:
            await self._on_leave(peer)

    def get(self, name: str) -> Peer | None:
        """Peer by its full name ("Host:Project")."""
        return self._peers.get(name)

    def all(self) -> list[Peer]:
        return list(self._peers.values())

    def update_ping(self, name: str) -> None:
        """Record that the peer itself sent a ping."""
        if name in self._peers:
            self._peers[name].last_ping = utc_now()

    async def cleanup_stale(self) -> list[str]:
        """Remove peers that have not pinged for longer than the timeout."""
        now = utc_now()
        stale = [
            name for name, peer in self._peers.items()
            if (now - peer.last_ping).total_seconds() > self._timeout
        ]
        for name in stale:
            await self.unregister(name)
        return stale

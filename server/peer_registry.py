"""Peer Registry für AI-Connect - verwaltet online Peers."""

import asyncio
from datetime import datetime
from typing import Optional, Callable, Any
from dataclasses import dataclass, field


@dataclass
class Peer:
    """Repräsentiert einen verbundenen Peer."""
    name: str
    ip: str
    connected_at: str
    project: Optional[str] = None
    websocket: Any = None
    last_ping: datetime = field(default_factory=datetime.utcnow)


class PeerRegistry:
    """Verwaltet alle verbundenen Peers."""

    def __init__(self, timeout_seconds: int = 20):
        self._peers: dict[str, Peer] = {}
        self._timeout = timeout_seconds
        self._on_join: Optional[Callable] = None
        self._on_leave: Optional[Callable] = None

    def on_join(self, callback: Callable) -> None:
        """Registriert Callback für Peer-Beitritt."""
        self._on_join = callback

    def on_leave(self, callback: Callable) -> None:
        """Registriert Callback für Peer-Austritt."""
        self._on_leave = callback

    def _find_available_name(self, base_name: str, max_suffix: int = 10) -> str:
        """Findet einen verfügbaren Namen.

        Wenn base_name belegt ist, probiert base_name2, base_name3, etc.
        """
        # Observer-Namen ignorieren
        if base_name.startswith("_") and base_name.endswith("_"):
            return base_name

        if base_name not in self._peers:
            return base_name

        for i in range(2, max_suffix + 1):
            candidate = f"{base_name}{i}"
            if candidate not in self._peers:
                return candidate

        # Fallback mit Timestamp
        import time
        return f"{base_name}_{int(time.time()) % 10000}"

    async def register(
        self,
        name: str,
        ip: str,
        websocket: Any,
        project: Optional[str] = None
    ) -> Peer:
        """Registriert einen neuen Peer.

        Falls der Name bereits belegt ist, wird automatisch
        ein Suffix angehängt (dev → dev2 → dev3 → ...).

        Returns:
            Der registrierte Peer (mit ggf. angepasstem Namen)
        """
        # Verfügbaren Namen finden
        actual_name = self._find_available_name(name)

        peer = Peer(
            name=actual_name,
            ip=ip,
            connected_at=datetime.utcnow().isoformat() + "Z",
            project=project,
            websocket=websocket
        )
        self._peers[actual_name] = peer

        if self._on_join:
            await self._on_join(peer)

        return peer

    async def unregister(self, name: str) -> None:
        """Entfernt einen Peer."""
        peer = self._peers.pop(name, None)
        if peer and self._on_leave:
            await self._on_leave(peer)

    def get(self, name: str) -> Optional[Peer]:
        """Holt einen Peer nach Name."""
        return self._peers.get(name)

    def get_all(self) -> list[dict]:
        """Gibt alle Peers als Liste zurück."""
        return [
            {
                "name": p.name,
                "ip": p.ip,
                "connected_at": p.connected_at,
                "project": p.project
            }
            for p in self._peers.values()
        ]

    def update_ping(self, name: str) -> None:
        """Aktualisiert den letzten Ping eines Peers."""
        if name in self._peers:
            self._peers[name].last_ping = datetime.utcnow()

    async def cleanup_stale(self) -> list[str]:
        """Entfernt Peers ohne Heartbeat."""
        now = datetime.utcnow()
        stale = []

        for name, peer in list(self._peers.items()):
            delta = (now - peer.last_ping).total_seconds()
            if delta > self._timeout:
                stale.append(name)
                await self.unregister(name)

        return stale

    def count(self) -> int:
        """Anzahl der verbundenen Peers."""
        return len(self._peers)

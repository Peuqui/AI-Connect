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

    def __init__(self, timeout_seconds: int = 300):  # 5 Minuten Timeout
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

    async def register(
        self,
        name: str,
        ip: str,
        websocket: Any,
        project: Optional[str] = None
    ) -> Peer:
        """Registriert einen neuen Peer.

        Der Name kommt bereits im Format "Host:Projekt" vom Client
        (z.B. "Mini:AIfred-Intelligence", "Aragon:FreeEchoDot2") und
        wird unverändert übernommen. Das project-Feld wird nur am
        Peer-Objekt gespeichert (für Filterung/Suche).

        Wenn bereits ein Peer mit gleichem Namen existiert:
        - Alte Verbindung wird geschlossen, neue übernimmt

        Returns:
            Der registrierte Peer
        """
        full_name = name

        # Duplikat-Check: Alte Verbindung ersetzen wenn Name bereits existiert
        if full_name in self._peers:
            existing = self._peers[full_name]
            del self._peers[full_name]
            if existing.websocket:
                try:
                    await existing.websocket.close()
                except Exception:
                    pass

        peer = Peer(
            name=full_name,
            ip=ip,
            connected_at=datetime.utcnow().isoformat() + "Z",
            project=project,
            websocket=websocket
        )
        self._peers[full_name] = peer

        if self._on_join:
            await self._on_join(peer)

        return peer

    async def unregister(self, name: str) -> None:
        """Entfernt einen Peer."""
        peer = self._peers.pop(name, None)
        if peer and self._on_leave:
            await self._on_leave(peer)

    def get(self, name: str) -> Optional[Peer]:
        """Holt einen Peer nach exaktem Namen.

        Names sind im Format "Host:Projekt" und müssen vollständig
        angegeben werden (z.B. "Mini:AIfred-Intelligence").
        """
        return self._peers.get(name)

    def get_all(self) -> list[dict]:
        """Gibt alle Peers als Liste zurück.

        Der Name hat Format "Host:Projekt", z.B. "Mini:AIfred-Intelligence".
        """
        return [
            {
                "name": p.name,
                "ip": p.ip,
                "connected_at": p.connected_at
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

"""SQLite-basierter Message Store für AI-Connect."""

import aiosqlite
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


class MessageStore:
    """Speichert Nachrichten in SQLite für Historie und Offline-Zustellung."""

    def __init__(self, db_path: str = "~/.ai-connect/messages.db"):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Verbindet zur Datenbank und erstellt Tabellen."""
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                from_peer TEXT NOT NULL,
                to_peer TEXT NOT NULL,
                content TEXT NOT NULL,
                context TEXT,
                timestamp TEXT NOT NULL,
                delivered INTEGER DEFAULT 0
            )
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_to_peer ON messages(to_peer, delivered)
        """)
        await self._db.commit()

    async def close(self) -> None:
        """Schließt die Datenbankverbindung."""
        if self._db:
            await self._db.close()
            self._db = None

    async def store(
        self,
        from_peer: str,
        to_peer: str,
        content: str,
        context: Optional[dict] = None
    ) -> str:
        """Speichert eine Nachricht und gibt die ID zurück."""
        msg_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + "Z"
        context_json = json.dumps(context) if context else None

        await self._db.execute(
            """
            INSERT INTO messages (id, from_peer, to_peer, content, context, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (msg_id, from_peer, to_peer, content, context_json, timestamp)
        )
        await self._db.commit()
        return msg_id

    async def get_unread(self, peer: str) -> list[dict]:
        """Holt alle ungelesenen Nachrichten für einen Peer."""
        cursor = await self._db.execute(
            """
            SELECT id, from_peer, to_peer, content, context, timestamp
            FROM messages
            WHERE (to_peer = ? OR to_peer = '*') AND delivered = 0
            ORDER BY timestamp ASC
            """,
            (peer,)
        )
        rows = await cursor.fetchall()

        messages = []
        for row in rows:
            messages.append({
                "id": row[0],
                "from": row[1],
                "to": row[2],
                "content": row[3],
                "context": json.loads(row[4]) if row[4] else None,
                "timestamp": row[5]
            })

        return messages

    async def mark_delivered(self, message_ids: list[str]) -> None:
        """Markiert Nachrichten als zugestellt."""
        if not message_ids:
            return
        placeholders = ",".join("?" * len(message_ids))
        await self._db.execute(
            f"UPDATE messages SET delivered = 1 WHERE id IN ({placeholders})",
            message_ids
        )
        await self._db.commit()

    async def get_history(
        self,
        peer1: str,
        peer2: str,
        limit: int = 50
    ) -> list[dict]:
        """Holt den Chatverlauf zwischen zwei Peers."""
        cursor = await self._db.execute(
            """
            SELECT id, from_peer, to_peer, content, context, timestamp
            FROM messages
            WHERE (from_peer = ? AND to_peer = ?)
               OR (from_peer = ? AND to_peer = ?)
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (peer1, peer2, peer2, peer1, limit)
        )
        rows = await cursor.fetchall()

        messages = []
        for row in reversed(rows):
            messages.append({
                "id": row[0],
                "from": row[1],
                "to": row[2],
                "content": row[3],
                "context": json.loads(row[4]) if row[4] else None,
                "timestamp": row[5]
            })

        return messages

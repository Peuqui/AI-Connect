"""SQLite message store of the Bridge: history and offline delivery."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite


class MessageStore:
    """Stores every message; direct messages to offline peers wait here."""

    def __init__(self, db_path: str = "~/.config/ai-connect/messages.db"):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open the database and create the table."""
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

    @property
    def _conn(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("MessageStore not connected, call connect() first")
        return self._db

    async def close(self) -> None:
        """Close the database."""
        if self._db:
            await self._db.close()
            self._db = None

    async def store(
        self,
        from_peer: str,
        to_peer: str,
        content: str,
        context: dict | None,
        delivered: bool
    ) -> dict:
        """Store a message and return it as sent to peers."""
        msg_id = str(uuid.uuid4())
        # ISO with milliseconds, e.g. 2026-01-03T14:30:45.123Z; the watcher
        # compares these strings, so the format must stay fixed.
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        context_json = json.dumps(context) if context else None

        await self._conn.execute(
            """
            INSERT INTO messages (id, from_peer, to_peer, content, context, timestamp, delivered)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (msg_id, from_peer, to_peer, content, context_json, timestamp, int(delivered))
        )
        await self._conn.commit()
        return {
            "id": msg_id,
            "from": from_peer,
            "to": to_peer,
            "content": content,
            "context": context,
            "timestamp": timestamp
        }

    async def get_unread(self, peer: str) -> list[dict]:
        """Direct messages to this peer that have not been delivered yet."""
        cursor = await self._conn.execute(
            """
            SELECT id, from_peer, to_peer, content, context, timestamp
            FROM messages
            WHERE to_peer = ? AND delivered = 0
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
        """Mark messages as delivered."""
        if not message_ids:
            return
        placeholders = ",".join("?" * len(message_ids))
        await self._conn.execute(
            f"UPDATE messages SET delivered = 1 WHERE id IN ({placeholders})",
            message_ids
        )
        await self._conn.commit()

    async def delete_older_than(self, days: int) -> int:
        """Delete messages older than days; return how many."""
        # Compare the date only: older rows use "YYYY-MM-DD HH:MM:SS",
        # newer ones ISO with "T" and "Z"
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        cursor = await self._conn.execute(
            "DELETE FROM messages WHERE substr(timestamp, 1, 10) < ?", (cutoff,)
        )
        await self._conn.commit()
        return cursor.rowcount

    async def get_history(
        self,
        peer1: str,
        peer2: str,
        limit: int = 50
    ) -> list[dict]:
        """The latest messages between two peers, oldest first."""
        cursor = await self._conn.execute(
            """
            SELECT * FROM (
                SELECT id, from_peer, to_peer, content, context, timestamp
                FROM messages
                WHERE (from_peer = ? AND to_peer = ?)
                   OR (from_peer = ? AND to_peer = ?)
                ORDER BY timestamp DESC
                LIMIT ?
            )
            ORDER BY timestamp
            """,
            (peer1, peer2, peer2, peer1, limit)
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

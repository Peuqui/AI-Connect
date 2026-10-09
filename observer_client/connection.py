"""Read-only connection to the Bridge: every message, live and back in time.

    async with ObserverConnection.from_config() as bridge:
        await bridge.start_observing()     # first, so nothing falls between history and live
        history = await bridge.history(since, limit=200)
        async for message in bridge.observed():
            ...

Messages are dicts with id, from, to, content, context and timestamp (see
bridge_time); a live message can also be in the history, compare the ids.
"""

import json
from collections.abc import AsyncIterator
from datetime import datetime
from types import TracebackType
from typing import final

import websockets
from websockets import ClientConnection

from bridge_time import bridge_timestamp
from config_loader import OBSERVER_TOKEN_PATH, bridge_target, load_config


class BridgeError(Exception):
    """The Bridge refused a request."""


# final: Python 3.10 has no typing.Self for __aenter__
@final
class ObserverConnection:
    """One connection with the observer token; requests and live messages share it."""

    def __init__(self, uri: str, token: str):
        self._uri = uri
        self._token = token
        self._ws: ClientConnection | None = None
        # Live messages that arrived while a request waited for its answer
        self._pending: list[dict] = []

    @classmethod
    def from_config(cls) -> "ObserverConnection":
        """Bridge address from config.yaml, token from the observer token file."""
        if not OBSERVER_TOKEN_PATH.exists():
            raise FileNotFoundError(
                f"Observer token not found: {OBSERVER_TOKEN_PATH}\n"
                "Run installer.py observer-token on the Bridge machine."
            )
        bridge = load_config()["bridge"]
        uri = f"ws://{bridge_target(bridge['host'])}:{bridge['port']}"
        return cls(uri, OBSERVER_TOKEN_PATH.read_text(encoding="utf-8").strip())

    async def __aenter__(self) -> "ObserverConnection":
        self._ws = await websockets.connect(
            self._uri, additional_headers={"Authorization": f"Bearer {self._token}"}
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self._connection.close()

    @property
    def _connection(self) -> ClientConnection:
        if self._ws is None:
            raise RuntimeError("ObserverConnection not open, use it with 'async with'")
        return self._ws

    async def start_observing(self) -> None:
        """From now on the Bridge sends a copy of every message it stores."""
        await self._request({"type": "observe"}, "observing")

    async def history(self, since: datetime, limit: int, before: str | None = None) -> list[dict]:
        """The latest messages after since, at most limit, oldest first.

        before (a Bridge timestamp, exclusive) pages further back: pass the
        timestamp of the oldest message of the previous page.
        """
        answer = await self._request(
            {"type": "history_all", "since": bridge_timestamp(since), "before": before, "limit": limit},
            "history_all",
        )
        return answer["messages"]

    async def peers(self) -> list[dict]:
        """The peers online right now, with state and status line."""
        answer = await self._request({"type": "list_peers"}, "peer_list")
        return answer["peers"]

    async def observed(self) -> AsyncIterator[dict]:
        """Every message the Bridge stores, as it comes; ends when the connection closes."""
        while self._pending:
            yield self._pending.pop(0)
        async for raw in self._connection:
            data = json.loads(raw)
            if data["type"] == "observed":
                yield _message(data)

    async def _request(self, payload: dict, answer_type: str) -> dict:
        await self._connection.send(json.dumps(payload))
        async for raw in self._connection:
            data = json.loads(raw)
            if data["type"] == answer_type:
                return data
            if data["type"] == "error":
                raise BridgeError(data["error"])
            if data["type"] == "observed":
                self._pending.append(_message(data))
        raise ConnectionError("The Bridge closed the connection")


def _message(observed: dict) -> dict:
    return {key: value for key, value in observed.items() if key != "type"}

"""Read along with the AI-Connect Bridge in the terminal.

    venv/bin/python -m observer_client.cli tree          # conversations of the last 24 h
    venv/bin/python -m observer_client.cli tree --full   # with the full text of every message
    venv/bin/python -m observer_client.cli live          # the last hour, then every new message

Run it in the AI-Connect directory; it needs the observer token
(installer.py observer-token on the Bridge machine).
"""

import argparse
import asyncio
import shutil
import sys
import textwrap
from datetime import datetime, timedelta, timezone

from bridge_time import parse_bridge_timestamp

from .connection import ObserverConnection
from .tree import build_conversations, preview

DEFAULT_TREE_HOURS = 24
DEFAULT_LIVE_HOURS = 1
DEFAULT_LIMIT = 200


def _local_time(timestamp: str) -> str:
    moment = parse_bridge_timestamp(timestamp).astimezone()
    today = datetime.now().astimezone().date()
    return moment.strftime("%H:%M:%S" if moment.date() == today else "%d.%m. %H:%M:%S")


def _width() -> int:
    return shutil.get_terminal_size().columns


def _print_message_line(prefix: str, message: dict, full: bool) -> None:
    head = f"{prefix}[{_local_time(message['timestamp'])}] {message['from']} -> {message['to']}:"
    if not full:
        print(f"{head} {preview(message['content'], max(_width() - len(head) - 1, 20))}")
        return
    print(head)
    indent = " " * (len(prefix) + 2)
    for line in message["content"].splitlines():
        print(textwrap.indent(line, indent))


def _print_tree(messages: list[dict], online: set[str], full: bool) -> None:
    for conversation in build_conversations(messages):
        names = " <-> ".join(f"{peer} (online)" if peer in online else peer for peer in conversation.peers)
        count = len(conversation.messages)
        print(f"{names}  [{count} message{'s' if count != 1 else ''}, last {_local_time(conversation.last_timestamp)}]")
        for message in reversed(conversation.messages):
            _print_message_line("  ", message, full)
        print()


async def _tree(hours: float, limit: int, full: bool) -> None:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    async with ObserverConnection.from_config() as bridge:
        messages = await bridge.history(since, limit)
        online = {peer["name"] for peer in await bridge.peers()}
    if not messages:
        print(f"No messages in the last {hours:g} h.")
        return
    if len(messages) == limit:
        print(f"Only the latest {limit} messages; --limit shows more.\n")
    _print_tree(messages, online, full)


async def _live(hours: float, limit: int, full: bool) -> None:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    async with ObserverConnection.from_config() as bridge:
        await bridge.start_observing()
        history = await bridge.history(since, limit)
        for message in history:
            _print_message_line("", message, full)
        print("--- live (Ctrl+C ends) ---")
        shown = {message["id"] for message in history}
        async for message in bridge.observed():
            if message["id"] not in shown:
                _print_message_line("", message, full)
    sys.exit("The Bridge closed the connection.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    views = parser.add_subparsers(dest="view", required=True)
    tree = views.add_parser("tree", help="conversations, the latest active first")
    tree.add_argument("--hours", type=float, default=DEFAULT_TREE_HOURS, help=f"how far back (default {DEFAULT_TREE_HOURS})")
    live = views.add_parser("live", help="every message in order, then the new ones as they come")
    live.add_argument("--hours", type=float, default=DEFAULT_LIVE_HOURS, help=f"how far back to start (default {DEFAULT_LIVE_HOURS})")
    for view in (tree, live):
        view.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"at most this many past messages (default {DEFAULT_LIMIT})")
        view.add_argument("--full", action="store_true", help="the full text instead of the first line")
    args = parser.parse_args()

    run = _tree if args.view == "tree" else _live
    try:
        asyncio.run(run(args.hours, args.limit, args.full))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

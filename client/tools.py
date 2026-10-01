"""MCP tools of AI-Connect, shared by the STDIO client and the HTTP/SSE server."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from bridge_client import get_client

NOT_CONNECTED = "❌ Not connected to the Bridge Server."


def _format_time(moment: datetime) -> str:
    """Local HH:MM:SS.mmm — milliseconds keep the order of quick exchanges clear."""
    return moment.astimezone().strftime("%H:%M:%S.%f")[:-3]


def _format_bridge_time(timestamp: str) -> str:
    """A Bridge timestamp (UTC, ISO) in local time."""
    return _format_time(datetime.fromisoformat(timestamp.replace("Z", "+00:00")))


def _read_excerpt(file: str, lines: Optional[str]) -> str:
    """Read a file, or the line range "start-end" / "line" of it.

    Relative paths are resolved against the working directory of this MCP
    server process — for Claude Code that is the session's project.
    """
    path = Path(file).expanduser()
    text = path.read_text(encoding="utf-8")
    if not lines:
        return text
    start_text, _, end_text = lines.partition("-")
    start = int(start_text)
    end = int(end_text) if end_text else start
    return "\n".join(text.splitlines()[start - 1:end])


def _build_context(file: Optional[str], lines: Optional[str]) -> Optional[dict]:
    """Context that travels with a message: path, line range and the text itself."""
    if not file:
        return None
    context = {"file": file, "excerpt": _read_excerpt(file, lines)}
    if lines:
        context["lines"] = lines
    return context


def _format_messages(messages: list[dict], me: str) -> str:
    """Render received messages, including any shared excerpt."""
    rendered = []
    for msg in messages:
        rendered.append(
            f"📥 [{_format_bridge_time(msg['timestamp'])}] [{msg['from']} → {me}]: {msg['content']}"
        )
        context = msg.get("context")
        if context:
            location = context["file"] + (f" lines {context['lines']}" if context.get("lines") else "")
            rendered.append(f"   📎 {location}\n```\n{context['excerpt']}\n```")
    return "\n".join(rendered)


async def peer_list() -> str:
    client = get_client()
    if not client or not client.connected:
        return NOT_CONNECTED
    peers = await client.list_peers()
    lines = ["Online peers:"]
    for peer in peers:
        lines.append(f"  - {peer['name']} [{peer['ip']}]")
    return "\n".join(lines)


async def peer_send(to: str, message: str, file: Optional[str], lines: Optional[str]) -> str:
    client = get_client()
    if not client or not client.connected:
        return NOT_CONNECTED
    try:
        context = _build_context(file, lines)
    except (OSError, ValueError) as e:
        return f"❌ Cannot read {file}: {e}"
    if not await client.send_message(to, message, context):
        return "❌ Sending failed, connection to the Bridge lost."
    attached = f" (+ {file}{' lines ' + lines if lines else ''})" if file else ""
    return f"📤 [{_format_time(datetime.now())}] [{client.peer_name} → {to}]: {message}{attached}"


async def peer_read() -> str:
    client = get_client()
    if not client or not client.connected:
        return NOT_CONNECTED
    messages = client.pop_messages()
    if not messages:
        return "📭 No new messages."
    return _format_messages(messages, client.peer_name)


async def peer_wait(timeout: int) -> str:
    client = get_client()
    if not client or not client.connected:
        return NOT_CONNECTED
    messages = await client.wait_for_messages(timeout=float(timeout))
    if not messages:
        return "📭 Timeout - no new messages."
    return _format_messages(messages, client.peer_name)


async def peer_history(peer: str, limit: int) -> str:
    client = get_client()
    if not client or not client.connected:
        return NOT_CONNECTED
    messages = await client.get_history(peer, limit)
    if not messages:
        return f"No conversation with '{peer}'."
    lines = [f"Conversation with {peer}:"]
    for msg in messages:
        direction = "📤" if msg["from"] == client.peer_name else "📥"
        lines.append(f"{direction} [{_format_bridge_time(msg['timestamp'])}] {msg['from']}: {msg['content']}")
    return "\n".join(lines)


async def peer_context(file: str, lines: Optional[str], message: Optional[str]) -> str:
    client = get_client()
    if not client or not client.connected:
        return NOT_CONNECTED
    try:
        context = _build_context(file, lines)
    except (OSError, ValueError) as e:
        return f"❌ Cannot read {file}: {e}"
    content = message or f"Shared {file}" + (f" (lines {lines})" if lines else "")
    if not await client.send_message("*", content, context):
        return "❌ Sharing failed, connection to the Bridge lost."
    return f"📤 [{_format_time(datetime.now())}] Shared with all online peers: {file}" + (f" lines {lines}" if lines else "")


async def peer_status() -> str:
    client = get_client()
    if not client:
        return "Client not initialised."
    bridge = f"{client.host}:{client.port}"
    if client.connected:
        return f"✅ Connected as '{client.peer_name}' to the Bridge Server {bridge}"
    if client.reconnecting:
        return f"🔄 Reconnecting to the Bridge Server {bridge}..."
    return f"❌ Not connected. Bridge Server: {bridge}"

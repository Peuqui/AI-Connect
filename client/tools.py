"""MCP tools of AI-Connect, shared by the STDIO client and the HTTP/SSE server."""

from datetime import datetime, timezone
from pathlib import Path

from bridge_client import get_client
from peer_name import record_seen, session_pid

NOT_CONNECTED = "❌ Not connected to the Bridge Server (peer_status shows why)."


def _format_time(moment: datetime) -> str:
    """Local HH:MM:SS.mmm — milliseconds keep the order of quick exchanges clear."""
    return moment.astimezone().strftime("%H:%M:%S.%f")[:-3]


def _format_bridge_time(timestamp: str) -> str:
    """A Bridge timestamp (UTC, ISO) in local time."""
    return _format_time(datetime.fromisoformat(timestamp.replace("Z", "+00:00")))


def _read_excerpt(file: str, lines: str | None) -> str:
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


def _build_context(file: str | None, lines: str | None) -> dict | None:
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
        line = f"  - {peer['name']} [{peer['ip']}]"
        if peer["state"]:
            line += f" {peer['state']} since {_format_bridge_time(peer['state_since'])}"
            if peer["state_detail"]:
                line += f" ({peer['state_detail']})"
        if peer["status"]:
            line += f" - {peer['status']}"
        lines.append(line)
    return "\n".join(lines)


async def peer_set_state(state: str, detail: str) -> str:
    client = get_client()
    if not client or not client.connected:
        return NOT_CONNECTED
    if not await client.set_state(state, detail):
        return "❌ Connection to the Bridge lost."
    return f"State: {state}" + (f" ({detail})" if detail else "")


async def peer_set_status(status: str) -> str:
    client = get_client()
    if not client or not client.connected:
        return NOT_CONNECTED
    if not await client.set_status(status):
        return "❌ Connection to the Bridge lost."
    return f"Status: {status}" if status else "Status cleared"


async def peer_notify_when_idle(peer: str) -> str:
    client = get_client()
    if not client or not client.connected:
        return NOT_CONNECTED
    if not await client.notify_when_idle(peer):
        return "❌ Connection to the Bridge lost."
    return f"The Bridge will send you a message once {peer} is done or waits for approval."


async def peer_send(to: str, message: str, file: str | None, lines: str | None) -> str:
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
    return f"📤 [{_format_time(datetime.now(timezone.utc))}] [{client.peer_name} → {to}]: {message}{attached}"


async def peer_read() -> str:
    client = get_client()
    if client and client.standby:
        return "⏸️ This session is on standby: another one holds its name for now. Try again in a few seconds."
    if not client or not client.connected:
        return NOT_CONNECTED
    messages = client.pop_messages()
    if not messages:
        return "📭 No new messages."
    # The watcher started at the next turn end reports only what came later
    from_bridge = [m["timestamp"] for m in messages if "id" in m]
    if from_bridge:
        record_seen(session_pid(), max(from_bridge))
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


async def peer_context(file: str, lines: str | None, message: str | None) -> str:
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
    return f"📤 [{_format_time(datetime.now(timezone.utc))}] Shared with all online peers: {file}" + (f" lines {lines}" if lines else "")


async def peer_status() -> str:
    client = get_client()
    if not client:
        return "Client not initialised."
    bridge = f"{client.host}:{client.port}"
    if client.connected:
        return f"✅ Connected as '{client.peer_name}' to the Bridge Server {bridge}"
    if client.token_refused:
        return f"❌ The Bridge Server {bridge} refused the token: check bridge.token in config.yaml"
    if client.standby:
        return f"⏸️ Standby: another session holds the name '{client.peer_name}' on the Bridge Server {bridge}"
    if client.reconnecting:
        return f"🔄 Reconnecting to the Bridge Server {bridge}..."
    return f"❌ Not connected. Bridge Server: {bridge}"

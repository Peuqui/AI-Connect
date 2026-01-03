"""MCP Tools für AI-Connect."""

from typing import Optional

from bridge_client import get_client


async def peer_list() -> str:
    """Zeigt alle online verbundenen Peers.

    Gibt eine Liste aller aktuell mit dem Bridge Server
    verbundenen KI-Assistenten zurück.
    """
    client = get_client()
    if not client or not client.connected:
        return "Nicht mit Bridge Server verbunden."

    peers = await client.list_peers()
    if not peers:
        return "Keine anderen Peers online."

    lines = ["Online Peers:"]
    for peer in peers:
        # Name enthält bereits das Projekt: "Aragon (AIfred-Intelligence)"
        lines.append(f"  - {peer['name']} [{peer['ip']}]")

    return "\n".join(lines)


async def peer_send(to: str, message: str, file: Optional[str] = None, lines: Optional[str] = None) -> str:
    """Sendet eine Nachricht an einen anderen Peer.

    Args:
        to: Name des Ziel-Peers (oder '*' für Broadcast)
        message: Die Nachricht die gesendet werden soll
        file: Optional - Dateipfad für Kontext
        lines: Optional - Zeilennummern (z.B. "42-58")
    """
    client = get_client()
    if not client or not client.connected:
        return "❌ Nicht mit Bridge Server verbunden."

    context = None
    if file or lines:
        context = {}
        if file:
            context["file"] = file
        if lines:
            context["lines"] = lines

    success = await client.send_message(to, message, context)
    if success:
        me = client.peer_name
        return f"📤 [{me} → {to}]: {message}"
    else:
        return "❌ Fehler beim Senden der Nachricht."


async def peer_read() -> str:
    """Liest alle neuen empfangenen Nachrichten.

    Gibt alle Nachrichten zurück die seit dem letzten Aufruf
    eingegangen sind und markiert sie als gelesen.
    """
    client = get_client()
    if not client or not client.connected:
        return "❌ Nicht mit Bridge Server verbunden."

    messages = client.pop_messages()
    if not messages:
        return "📭 Keine neuen Nachrichten."

    me = client.peer_name
    lines = []
    for msg in messages:
        sender = msg.get("from", "unbekannt")
        content = msg.get("content", "")
        context = msg.get("context")

        # Hauptnachricht
        lines.append(f"📥 [{sender} → {me}]: {content}")

        # Kontext falls vorhanden
        if context:
            ctx_parts = []
            if context.get("file"):
                ctx_parts.append(context['file'])
            if context.get("lines"):
                ctx_parts.append(f"Z.{context['lines']}")
            if ctx_parts:
                lines.append(f"   📎 {' '.join(ctx_parts)}")

    return "\n".join(lines)


async def peer_history(peer: str, limit: int = 20) -> str:
    """Zeigt den Chatverlauf mit einem bestimmten Peer.

    Args:
        peer: Name des Peers
        limit: Maximale Anzahl der Nachrichten (Standard: 20)
    """
    client = get_client()
    if not client or not client.connected:
        return "Nicht mit Bridge Server verbunden."

    # Hier müsste der Client die Historie vom Server holen
    # Vereinfacht: Wir zeigen nur lokale Messages
    messages = [m for m in client.messages if m.get("from") == peer or m.get("to") == peer]

    if not messages:
        return f"Kein Chatverlauf mit '{peer}'."

    lines = [f"Chatverlauf mit {peer}:"]
    for msg in messages[-limit:]:
        sender = msg.get("from", "?")
        content = msg.get("content", "")
        timestamp = msg.get("timestamp", "")[:19].replace("T", " ")
        lines.append(f"\n[{timestamp}] {sender}: {content}")

    return "\n".join(lines)


async def peer_context(file: str, lines: Optional[str] = None, message: Optional[str] = None) -> str:
    """Teilt den aktuellen Datei-Kontext mit allen Peers.

    Args:
        file: Pfad zur Datei die geteilt werden soll
        lines: Optional - Zeilennummern (z.B. "42-58")
        message: Optional - Begleitende Nachricht
    """
    client = get_client()
    if not client or not client.connected:
        return "Nicht mit Bridge Server verbunden."

    context = {"file": file}
    if lines:
        context["lines"] = lines

    content = message or f"Schaut euch mal {file} an"
    if lines:
        content += f" (Zeilen {lines})"

    success = await client.send_message("*", content, context)
    if success:
        return f"Kontext geteilt: {file}"
    else:
        return "Fehler beim Teilen des Kontexts."

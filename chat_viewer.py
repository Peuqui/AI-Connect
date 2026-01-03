#!/usr/bin/env python3
"""Live Chat Viewer für AI-Connect Bridge.

Zeigt alle Peer-Nachrichten in Echtzeit an.
Läuft in einem separaten Terminal-Fenster.

Verwendung:
    python chat_viewer.py
    # oder
    ./chat_viewer.py
"""

import asyncio
import json
import sys
from datetime import datetime

import websockets


# ANSI Farben
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Peer-Farben
    BLUE = "\033[94m"      # Ausgehend
    GREEN = "\033[92m"     # Eingehend
    YELLOW = "\033[93m"    # System
    CYAN = "\033[96m"      # Peer-Name
    MAGENTA = "\033[95m"   # Context


def format_time() -> str:
    """Formatiert aktuelle Zeit."""
    return datetime.now().strftime("%H:%M:%S")


def print_message(msg: dict) -> None:
    """Gibt eine Nachricht formatiert aus."""
    msg_type = msg.get("type", "")

    if msg_type == "message":
        sender = msg.get("from", "?")
        recipient = msg.get("to", "?")
        content = msg.get("content", "")
        context = msg.get("context")

        # Header
        print(f"\n{Colors.DIM}[{format_time()}]{Colors.RESET} ", end="")
        print(f"{Colors.CYAN}{Colors.BOLD}{sender}{Colors.RESET}", end="")
        print(f" → ", end="")
        print(f"{Colors.CYAN}{Colors.BOLD}{recipient}{Colors.RESET}")

        # Content
        print(f"  {content}")

        # Context falls vorhanden
        if context:
            ctx_parts = []
            if context.get("file"):
                ctx_parts.append(context["file"])
            if context.get("lines"):
                ctx_parts.append(f"Z.{context['lines']}")
            if ctx_parts:
                print(f"  {Colors.MAGENTA}📎 {' '.join(ctx_parts)}{Colors.RESET}")

    elif msg_type == "peer_joined":
        peer = msg.get("peer", {})
        name = peer.get("name", "?")
        print(f"\n{Colors.DIM}[{format_time()}]{Colors.RESET} ", end="")
        print(f"{Colors.GREEN}✓ {name} ist beigetreten{Colors.RESET}")

    elif msg_type == "peer_left":
        peer = msg.get("peer", "?")
        print(f"\n{Colors.DIM}[{format_time()}]{Colors.RESET} ", end="")
        print(f"{Colors.YELLOW}✗ {peer} hat die Verbindung getrennt{Colors.RESET}")


def print_header() -> None:
    """Gibt den Header aus."""
    print(f"\n{Colors.BOLD}{'═' * 50}{Colors.RESET}")
    print(f"{Colors.BOLD}  🔗 AI-Connect Live Chat Viewer{Colors.RESET}")
    print(f"{Colors.BOLD}{'═' * 50}{Colors.RESET}")
    print(f"{Colors.DIM}  Drücke Ctrl+C zum Beenden{Colors.RESET}\n")


async def viewer(host: str = "192.168.0.252", port: int = 9999) -> None:
    """Verbindet zur Bridge und zeigt Nachrichten an."""
    uri = f"ws://{host}:{port}"

    print_header()
    print(f"{Colors.DIM}Verbinde zu {uri}...{Colors.RESET}")

    try:
        async with websockets.connect(uri) as ws:
            # Als Observer registrieren (spezieller Name)
            await ws.send(json.dumps({
                "type": "register",
                "name": "_viewer_",
                "observer": True
            }))

            print(f"{Colors.GREEN}✓ Verbunden! Warte auf Nachrichten...{Colors.RESET}")

            async for raw in ws:
                try:
                    msg = json.loads(raw)

                    # Pings/Pongs ignorieren
                    if msg.get("type") in ("ping", "pong"):
                        continue

                    print_message(msg)
                    sys.stdout.flush()

                except json.JSONDecodeError:
                    pass

    except ConnectionRefusedError:
        print(f"{Colors.YELLOW}⚠ Bridge Server nicht erreichbar: {uri}{Colors.RESET}")
        print(f"{Colors.DIM}  Stelle sicher, dass der Bridge Server läuft.{Colors.RESET}")
    except KeyboardInterrupt:
        print(f"\n\n{Colors.DIM}Viewer beendet.{Colors.RESET}")


def main() -> None:
    """Haupteinstiegspunkt."""
    import argparse

    parser = argparse.ArgumentParser(description="AI-Connect Live Chat Viewer")
    parser.add_argument("--host", default="192.168.0.252", help="Bridge Server Host")
    parser.add_argument("--port", type=int, default=9999, help="Bridge Server Port")
    args = parser.parse_args()

    try:
        asyncio.run(viewer(args.host, args.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

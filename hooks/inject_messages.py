#!/usr/bin/env python3
"""Hook-Script für Claude Code: Injiziert Peer-Nachrichten in User-Prompt.

Wird als user-prompt-submit Hook aufgerufen.
Liest stdin (JSON mit user_prompt), prüft auf neue Nachrichten,
und gibt modifizierten Prompt auf stdout aus.

Installation in ~/.claude/settings.local.json:
{
  "hooks": {
    "user-prompt-submit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /home/mp/Projekte/AI-Connect/hooks/inject_messages.py"
          }
        ]
      }
    ]
  }
}
"""

import json
import sys
from pathlib import Path

# Nachrichten-Queue Datei (wird vom MCP Client geschrieben)
MESSAGES_FILE = Path.home() / ".config" / "ai-connect" / "pending_messages.json"


def get_pending_messages() -> list[dict]:
    """Liest und leert die ausstehenden Nachrichten."""
    if not MESSAGES_FILE.exists():
        return []

    try:
        with open(MESSAGES_FILE) as f:
            messages = json.load(f)

        # Datei leeren nach dem Lesen
        MESSAGES_FILE.write_text("[]")

        return messages
    except (json.JSONDecodeError, IOError):
        return []


def format_messages(messages: list[dict]) -> str:
    """Formatiert Nachrichten für den Prompt."""
    if not messages:
        return ""

    lines = ["\n\n---", "📨 **Neue Peer-Nachrichten:**"]

    for msg in messages:
        sender = msg.get("from", "?")
        content = msg.get("content", "")
        lines.append(f"📥 [{sender}]: {content}")

    lines.append("---\n")

    return "\n".join(lines)


def main() -> None:
    """Hauptfunktion: Liest Hook-Input, injiziert Nachrichten."""
    # Hook-Input lesen (JSON von stdin)
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        # Bei Fehler: nichts tun
        sys.exit(0)

    # Original-Prompt holen
    user_prompt = hook_input.get("user_prompt", "")

    # Neue Nachrichten prüfen
    messages = get_pending_messages()

    if messages:
        # Nachrichten an Prompt anhängen
        injected = format_messages(messages)
        modified_prompt = user_prompt + injected

        # Modifizierten Prompt ausgeben
        output = {"user_prompt": modified_prompt}
        json.dump(output, sys.stdout)
    else:
        # Keine Änderung - leere Ausgabe
        pass


if __name__ == "__main__":
    main()

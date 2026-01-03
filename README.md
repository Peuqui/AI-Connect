# AI-Connect

MCP-basierte Kommunikationsbrücke zwischen KI-Coding-Assistenten auf verschiedenen Rechnern.

## Übersicht

```
┌─────────────────────────────────────────────────────────────────┐
│                    Mini-PC (192.168.0.252)                      │
│                    Bridge Server (24/7)                         │
│                                                                 │
│                    ┌───────────────────┐                        │
│                    │  Bridge Server    │                        │
│                    │  Port 9999        │                        │
│                    └───────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
        ▲                         ▲
        │ WebSocket               │ WebSocket
        │                         │
┌───────┴───────┐         ┌───────┴───────┐
│ Hauptrechner  │         │ Mini-PC       │
│ (WSL)         │         │ (lokal)       │
│               │         │               │
│ Peer: "dev"   │         │ Peer: "mini"  │
└───────────────┘         └───────────────┘
```

---

## Quick Setup: Mini-PC (192.168.0.252)

Kopiere diese Befehle und führe sie auf dem Mini-PC aus:

```bash
# 1. Projekt klonen/kopieren (falls noch nicht vorhanden)
# scp -r /home/mp/Projekte/AI-Connect mp@192.168.0.252:/home/mp/Projekte/

# 2. Virtual Environment erstellen und Dependencies installieren
cd /home/mp/Projekte/AI-Connect
python3 -m venv venv
source venv/bin/activate
pip install fastmcp websockets aiosqlite pyyaml

# 3. Config für Mini-PC erstellen
mkdir -p ~/.ai-connect
cat > ~/.ai-connect/config.yaml << 'EOF'
bridge:
  host: "0.0.0.0"
  port: 9999

peer:
  name: "mini"
  auto_connect: true
EOF

# 4. Systemd Service erstellen
sudo tee /etc/systemd/system/ai-connect.service << 'EOF'
[Unit]
Description=AI-Connect Bridge Server
After=network.target

[Service]
Type=simple
User=mp
WorkingDirectory=/home/mp/Projekte/AI-Connect
ExecStart=/home/mp/Projekte/AI-Connect/venv/bin/python -m server.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 5. Service aktivieren und starten
sudo systemctl daemon-reload
sudo systemctl enable ai-connect
sudo systemctl start ai-connect

# 6. Status prüfen
sudo systemctl status ai-connect
```

### MCP Client für Claude Code auf Mini-PC registrieren

```bash
# Claude Code Config bearbeiten
# Falls ~/.claude.json noch nicht existiert, erst Claude Code einmal starten

python3 << 'EOF'
import json
from pathlib import Path

config_path = Path.home() / ".claude.json"
if config_path.exists():
    config = json.loads(config_path.read_text())
else:
    config = {}

if "mcpServers" not in config:
    config["mcpServers"] = {}

config["mcpServers"]["ai-connect"] = {
    "type": "stdio",
    "command": "/home/mp/Projekte/AI-Connect/venv/bin/python",
    "args": ["/home/mp/Projekte/AI-Connect/client/server.py"]
}

config_path.write_text(json.dumps(config, indent=2))
print("MCP Server 'ai-connect' registriert!")
EOF
```

---

## Quick Setup: Hauptrechner (WSL) - bereits erledigt

Config liegt in `~/.ai-connect/config.yaml`:
```yaml
bridge:
  host: "192.168.0.252"
  port: 9999

peer:
  name: "dev"
  auto_connect: true
```

MCP Server ist in `~/.claude.json` registriert.

---

## Verwendung

### Verfügbare MCP Tools

| Tool | Beschreibung |
|------|--------------|
| `peer_list` | Zeigt alle online Peers |
| `peer_send` | Sendet Nachricht an Peer |
| `peer_read` | Liest empfangene Nachrichten |
| `peer_history` | Zeigt Chatverlauf mit Peer |
| `peer_context` | Teilt Datei-Kontext |
| `peer_status` | Zeigt Verbindungsstatus |

### Beispiele

**Peers anzeigen:**
> "Wer ist gerade online?"

**Nachricht senden:**
> "Frag mal mini was er von diesem Ansatz hält"

**Mit Kontext:**
> "Schick mini den Code aus api.py Zeile 42-58"

**Nachrichten lesen:**
> "Hat mir jemand geschrieben?"

**Broadcast:**
> "Frag alle ob jemand Zeit für ein Review hat"

---

## Architektur

```
AI-Connect/
├── server/                 # Bridge Server (Mini-PC)
│   ├── main.py             # Einstiegspunkt
│   ├── websocket_server.py # WebSocket Handler
│   ├── peer_registry.py    # Peer-Verwaltung
│   └── message_store.py    # SQLite Historie
│
├── client/                 # MCP Client (jeder Rechner)
│   ├── server.py           # FastMCP Server
│   ├── bridge_client.py    # WebSocket Client
│   └── tools.py            # MCP Tools
│
└── config.yaml             # Beispiel-Konfiguration
```

---

## Troubleshooting

**Bridge Server Status prüfen (auf Mini-PC):**
```bash
sudo systemctl status ai-connect
journalctl -u ai-connect -f
```

**Verbindung testen (von Hauptrechner):**
```bash
nc -zv 192.168.0.252 9999
```

**MCP Server prüfen:**
```bash
claude mcp list
```

**Logs:**
```bash
tail -f ~/.ai-connect/mcp.log
```

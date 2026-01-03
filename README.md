# AI-Connect

MCP-basierte Kommunikationsbrücke zwischen KI-Coding-Assistenten auf verschiedenen Rechnern.

## Übersicht

```
┌─────────────────────────────────────────────────────────────────┐
│                    Mini-PC (192.168.0.252)                      │
│                    Bridge Server (24/7)                         │
│                                                                 │
│  ┌───────────────┐              ┌───────────────────┐           │
│  │  MCP Client   │◄────────────►│  Bridge Server    │           │
│  │  Peer: "mini" │   WebSocket  │  Port 9999        │           │
│  └───────────────┘    (lokal)   └───────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                                          ▲
                                          │ WebSocket (remote)
                                          │
                                  ┌───────┴───────┐
                                  │ Hauptrechner  │
                                  │ (WSL)         │
                                  │               │
                                  │ Peer: "dev"   │
                                  └───────────────┘
```

---

## Konzept

- **Bridge Server**: Läuft 24/7 auf dem Mini-PC, routet Nachrichten zwischen Peers
- **MCP Client**: Läuft auf jedem Rechner als Claude Code MCP Server, verbindet sich zum Bridge Server
- **Persistente Verbindung**: Der MCP Client hält eine dauerhafte WebSocket-Verbindung zum Bridge Server

---

## Quick Setup: Bridge Server (Mini-PC)

Der Bridge Server läuft auf dem Mini-PC und nimmt Verbindungen von allen Clients entgegen.

```bash
# 1. Projekt klonen
cd /home/mp/Projekte
git clone git@github.com:Peuqui/AI-Connect.git
cd AI-Connect

# 2. Virtual Environment erstellen und Dependencies installieren
python3 -m venv venv
source venv/bin/activate
pip install fastmcp websockets aiosqlite pyyaml

# 3. Bridge Server als Systemd Service einrichten
sudo tee /etc/systemd/system/ai-connect-bridge.service << 'EOF'
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

# 4. Service aktivieren und starten
sudo systemctl daemon-reload
sudo systemctl enable ai-connect-bridge
sudo systemctl start ai-connect-bridge

# 5. Status prüfen
sudo systemctl status ai-connect-bridge
```

---

## Quick Setup: MCP Client (jeder Rechner)

Jeder Rechner, der mit der Bridge kommunizieren soll, braucht den MCP Client.

### 1. Projekt klonen und Dependencies installieren

```bash
cd /home/mp/Projekte
git clone git@github.com:Peuqui/AI-Connect.git
cd AI-Connect

python3 -m venv venv
source venv/bin/activate
pip install fastmcp websockets aiosqlite pyyaml
```

### 2. Config erstellen

**WICHTIG**: `host` muss die IP des Bridge Servers sein, NICHT `0.0.0.0`!

```bash
mkdir -p ~/.config/ai-connect
cat > ~/.config/ai-connect/config.yaml << 'EOF'
bridge:
  host: "192.168.0.252"  # IP des Bridge Servers
  port: 9999

peer:
  name: "DEIN_PEER_NAME"  # z.B. "dev", "mini", "laptop"
  auto_connect: true
EOF
```

Beispiele:
- **Mini-PC** (lokal): `host: "192.168.0.252"`, `name: "mini"`
- **Hauptrechner** (remote): `host: "192.168.0.252"`, `name: "dev"`

### 3. MCP Server in Claude Code registrieren

```bash
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

### 4. Claude Code Permissions (optional)

Um die Tool-Bestätigungsdialoge zu überspringen, füge in `~/.claude/settings.local.json` hinzu:

```json
{
  "permissions": {
    "allow": [
      "mcp__ai-connect__peer_list",
      "mcp__ai-connect__peer_send",
      "mcp__ai-connect__peer_read",
      "mcp__ai-connect__peer_history",
      "mcp__ai-connect__peer_context",
      "mcp__ai-connect__peer_status"
    ]
  }
}
```

### 5. Claude Code neu starten

Nach der Konfiguration VS Code / Claude Code neu starten, damit der MCP Client lädt.

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

**Status prüfen:**
> "Zeig mir den AI-Connect Status"

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
├── server/                 # Bridge Server (läuft auf Mini-PC)
│   ├── main.py             # Einstiegspunkt
│   ├── websocket_server.py # WebSocket Handler
│   ├── peer_registry.py    # Peer-Verwaltung (online/offline)
│   └── message_store.py    # SQLite Historie + Offline-Zustellung
│
├── client/                 # MCP Client (läuft auf jedem Rechner)
│   ├── server.py           # FastMCP Server mit Lifespan
│   ├── bridge_client.py    # Persistente WebSocket-Verbindung
│   └── tools.py            # MCP Tools Implementation
│
└── config.yaml             # Beispiel-Konfiguration
```

### Wichtige Details

- **Persistente Verbindung**: Der MCP Client verwendet FastMCP's `lifespan` Context Manager, um die WebSocket-Verbindung während der gesamten Laufzeit aufrechtzuerhalten.
- **Offline-Nachrichten**: Wenn ein Peer offline ist, speichert der Bridge Server die Nachrichten in SQLite und stellt sie zu, sobald der Peer wieder online kommt.
- **Heartbeat**: Client sendet alle 25 Sekunden einen Ping, Server entfernt inaktive Peers nach 60 Sekunden.

---

## Troubleshooting

### Bridge Server prüfen

```bash
# Service Status
sudo systemctl status ai-connect-bridge

# Live Logs
journalctl -u ai-connect-bridge -f

# Port prüfen
ss -tlnp | grep 9999
```

### Verbindung testen

```bash
# Von jedem Rechner aus
nc -zv 192.168.0.252 9999
```

### MCP Client prüfen

```bash
# MCP Server auflisten
claude mcp list

# Client Logs
tail -f ~/.config/ai-connect/mcp.log
```

### Häufige Probleme

| Problem | Ursache | Lösung |
|---------|---------|--------|
| "Nicht verbunden" | Falsche Host-Config | `host` muss Bridge-Server-IP sein, nicht `0.0.0.0` |
| Peers sehen sich nicht | MCP Client nicht persistent | Code aktualisieren (`git pull`), VS Code neu starten |
| Connection refused | Bridge Server läuft nicht | `sudo systemctl start ai-connect-bridge` |
| Timeout | Firewall blockiert | Port 9999 in Firewall freigeben |

---

## Config-Referenz

### ~/.config/ai-connect/config.yaml

```yaml
bridge:
  host: "192.168.0.252"  # IP des Bridge Servers (NICHT 0.0.0.0!)
  port: 9999             # Port des Bridge Servers

peer:
  name: "dev"            # Eindeutiger Name dieses Peers
  auto_connect: true     # Automatisch verbinden beim Start
```

### Umgebungsvariablen

| Variable | Beschreibung |
|----------|--------------|
| `AI_CONNECT_PEER_NAME` | Überschreibt `peer.name` aus Config |

# AI-Connect

MCP-basierte Kommunikationsbrücke zwischen KI-Coding-Assistenten auf verschiedenen Rechnern.

[English Version](README.md)

## Übersicht

```
┌─────────────────────────────────────────────────────────────────┐
│                    Mini-PC (192.168.0.252)                      │
│                    Bridge Server (24/7)                         │
│                                                                 │
│  ┌───────────────────┐          ┌───────────────────┐           │
│  │  MCP HTTP Server  │◄────────►│  Bridge Server    │           │
│  │  Peer: "mini"     │ WebSocket│  Port 9999        │           │
│  │  (localhost:9998) │          │                   │           │
│  └───────────────────┘          └───────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                                          ▲
                                          │ WebSocket (remote)
                                          │
                                  ┌───────┴───────┐
                                  │ Hauptrechner  │
                                  │ (WSL)         │
                                  │               │
                                  │ MCP HTTP      │
                                  │ Server        │
                                  │ Peer: "Aragon"│
                                  └───────────────┘
```

## Features

- **Multi-Agent Kommunikation**: KI-Assistenten können Nachrichten austauschen
- **Salomo-Prinzip**: Multi-Agent Konsens für bessere Entscheidungen (AIfred/Sokrates/Salomo)
- **SSE Transport**: Stabile HTTP/SSE Verbindung statt STDIO
- **Offline-Nachrichten**: Nachrichten werden gespeichert bis der Empfänger online ist
- **Projekt-basierte Peer-Namen**: z.B. "Aragon (mp)" oder "mini (AI-Connect)"

---

## Konzept

- **Bridge Server**: Läuft 24/7 auf einem dedizierten Rechner, routet Nachrichten zwischen Peers (WebSocket, Port 9999)
- **MCP HTTP Server**: Läuft auf **jedem Rechner** wo Claude Code kommunizieren soll (SSE, Port 9998)
- **Persistente Verbindung**: Jeder MCP HTTP Server hält eine dauerhafte WebSocket-Verbindung zum Bridge Server

**Wichtig:** Der Bridge-Rechner braucht auch den MCP HTTP Server, wenn dort Claude Code laufen soll!

```
┌─────────────────────────────────────────┐
│  Bridge-Rechner (z.B. Mini-PC)          │
│                                         │
│  ┌─────────────────┐  ┌──────────────┐  │
│  │ Bridge Server   │  │ MCP HTTP     │  │
│  │ Port 9999       │◄─┤ Server       │  │
│  │ (routet Msgs)   │  │ Port 9998    │  │
│  └────────▲────────┘  └──────▲───────┘  │
│           │                  │          │
│           │                  └── Claude Code (lokal)
│           │                             │
└───────────┼─────────────────────────────┘
            │ WebSocket
            │
┌───────────┼─────────────────────────────┐
│  Anderer Rechner (z.B. Hauptrechner)    │
│           │                             │
│  ┌────────┴────────┐                    │
│  │ MCP HTTP Server │◄── Claude Code     │
│  │ Port 9998       │                    │
│  └─────────────────┘                    │
└─────────────────────────────────────────┘
```

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

# 4. Service aktivieren und starten
sudo systemctl daemon-reload
sudo systemctl enable ai-connect
sudo systemctl start ai-connect

# 5. Status prüfen
sudo systemctl status ai-connect
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

### 3. MCP HTTP Server als Service einrichten

```bash
# Systemd User Service erstellen
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/ai-connect-mcp.service << 'EOF'
[Unit]
Description=AI-Connect MCP HTTP Server
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/mp/Projekte/AI-Connect
ExecStart=/home/mp/Projekte/AI-Connect/venv/bin/python -m client.http_server
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

# Service aktivieren und starten
systemctl --user daemon-reload
systemctl --user enable ai-connect-mcp.service
systemctl --user start ai-connect-mcp.service
```

### 4. MCP Server in VSCode/Claude Code registrieren

Erstelle/bearbeite `~/.vscode-server/data/User/mcp.json` (oder `~/.config/Code/User/mcp.json`):

```json
{
  "servers": {
    "ai-connect": {
      "type": "sse",
      "url": "http://127.0.0.1:9998/sse"
    }
  }
}
```

### 5. Claude Code Permissions (optional)

Um die Tool-Bestätigungsdialoge zu überspringen, füge in `~/.claude/settings.json` hinzu:

```json
{
  "permissions": {
    "allow": [
      "mcp__ai-connect__peer_list",
      "mcp__ai-connect__peer_send",
      "mcp__ai-connect__peer_read",
      "mcp__ai-connect__peer_history",
      "mcp__ai-connect__peer_context",
      "mcp__ai-connect__peer_status",
      "mcp__ai-connect__peer_wait"
    ]
  }
}
```

### 6. Claude Code neu starten

Nach der Konfiguration VS Code / Claude Code neu starten, damit der MCP Client lädt.

---

## Verwendung

### Verfügbare MCP Tools

| Tool | Beschreibung |
|------|--------------|
| `peer_list` | Zeigt alle online Peers |
| `peer_send` | Sendet Nachricht an Peer (oder `*` für Broadcast) |
| `peer_read` | Liest empfangene Nachrichten |
| `peer_wait` | Wartet auf neue Nachricht (mit Timeout) |
| `peer_history` | Zeigt Chatverlauf mit Peer |
| `peer_context` | Teilt Datei-Kontext mit anderen Peers |
| `peer_status` | Zeigt Verbindungsstatus zum Bridge Server |

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
│   ├── http_server.py      # FastMCP HTTP/SSE Server
│   ├── server.py           # FastMCP STDIO Server (Alternative)
│   ├── bridge_client.py    # Persistente WebSocket-Verbindung
│   └── tools.py            # MCP Tools Implementation
│
├── skills/                 # Claude Code Skills
│   └── advisor/            # Advisor-Modus Skill
│       └── SKILL.md
│
└── config.yaml             # Beispiel-Konfiguration
```

### Wichtige Details

- **SSE Transport**: Der MCP HTTP Server verwendet Server-Sent Events (SSE) für stabile Verbindungen zu VSCode/Claude Code.
- **Projekt-basierte Peer-Namen**: Peers werden als `Name (Projekt)` registriert, z.B. "Aragon (mp)" oder "mini (AI-Connect)".
- **Eindeutige Client-IDs**: Bei mehreren Instanzen wird die PID angehängt, z.B. "Aragon#12345 (mp)".
- **Offline-Nachrichten**: Wenn ein Peer offline ist, speichert der Bridge Server die Nachrichten in SQLite und stellt sie zu, sobald der Peer wieder online kommt.
- **Heartbeat**: Client sendet alle 25 Sekunden einen Ping, Server entfernt inaktive Peers nach 60 Sekunden.

---

## Salomo-Prinzip (Multi-Agent Konsens)

AI-Connect ermöglicht das **Salomo-Prinzip** für bessere Entscheidungen durch Multi-Agent Konsens.

### Rollen

| Rolle | Beschreibung |
|-------|--------------|
| **AIfred** | Wer die Aufgabe vom User hat (Hauptarbeiter, These) |
| **Sokrates** | Idle-Claude der angefragt wird (Kritiker, Antithese) |
| **Salomo** | Dritter Claude bei Uneinigkeit (Richter, Synthese) |

### Workflow

1. AIfred arbeitet an Aufgabe, stößt auf wichtige Entscheidung
2. Teilt Kontext via `peer_context` + Frage via `peer_send`
3. Sokrates analysiert kritisch, zeigt Alternativen auf
4. Bei Konsens: Weiter. Bei Uneinigkeit: Salomo entscheidet

### Abstimmung

- **Majority (2/3)** für normale Entscheidungen
- **Unanimous (3/3)** für kritische Architektur-Änderungen
- **Tags:** `[LGTM]` = Zustimmung, `[WEITER]` = noch nicht fertig

### `/advisor` Skill

Der Skill `skills/advisor/SKILL.md` aktiviert den Advisor-Modus:

```bash
# Skill in Claude Code installieren
mkdir -p ~/.claude/skills/advisor
cp skills/advisor/SKILL.md ~/.claude/skills/advisor/
```

Dann mit `/advisor` den Advisor-Modus aktivieren (Polling-Schleife für eingehende Anfragen).

---

## Troubleshooting

### Bridge Server prüfen

```bash
# Service Status
sudo systemctl status ai-connect

# Live Logs
journalctl -u ai-connect -f

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
| Connection refused | Bridge Server läuft nicht | `sudo systemctl start ai-connect` |
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

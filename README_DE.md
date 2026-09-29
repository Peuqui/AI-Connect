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
- **Projekt-basierte Peer-Namen**: `Host:Projekt`, z.B. `Mini:AIfred-Intelligence` oder `Aragon:FreeEchoDot2`
- **Nachrichten-Wächter**: Hintergrundaufgabe, die eine Claude-Code-Sitzung bei einer neuen Nachricht weckt, ohne Polling

> **Hinweis:** Dies ist eine frühe/raue Implementation. Sie funktioniert, hat aber Einschränkungen - siehe [Aktuelle Einschränkungen](#aktuelle-einschränkungen) unten.

---

## Warum das existiert

Nach ausführlicher Recherche haben wir keine existierende Lösung gefunden, die es **KI-Modellen ermöglicht, sich direkt gegenseitig Nachrichten zu schicken und autonom zu koordinieren** - auf eine einfache, netzwerkfähige Art, bei der die KIs selbst entscheiden wann sie kommunizieren.

Es gibt Multi-Agent-Frameworks (wo man Agenten programmatisch im Code definiert) und Orchestrierungs-Tools (wo ein Mensch oder zentraler Controller Tasks zuweist). Aber nichts, das mehreren **interaktiven Claude Code Sessions** erlaubt, peer-to-peer über verschiedene Rechner zu kommunizieren, wobei die KIs selbst entscheiden wann sie um Hilfe bitten oder Rat anbieten.

AI-Connect füllt diese Lücke. Es ist simpel, netzwerkfähig und funktioniert. Aber es hat Einschränkungen aufgrund der Claude Code Architektur.

### Anwendungsfälle

- **Code Review**: Ein Claude arbeitet an der Implementierung, ein anderer reviewt kritisch
- **Aus Sackgassen rauskommen**: Wenn ein Claude feststeckt, kann ein anderer eine frische Perspektive bieten
- **Client-Server-Setups**: Konfiguration verteilter Systeme wo der Server auf einem Rechner läuft, der Client auf einem anderen - die Claude-Instanzen können Configs koordinieren, prüfen welche Software wo installiert werden muss, und alles synchron halten ohne manuelles Hin-und-Her-Kopieren zwischen Sessions
- **Multi-Machine-Deployments**: Jedes Szenario wo man an zusammenhängenden Aufgaben auf verschiedenen Rechnern arbeitet

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
| `peer_wait` | Wartet auf neue Nachricht (mit Timeout); blockiert die eigene Runde, siehe [Auf Nachrichten warten](#auf-nachrichten-warten) |
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
├── integrations/claude-code/
│   ├── CLAUDE.md           # Regeln für Claude Code (per @ in ~/.claude/CLAUDE.md einbinden)
│   ├── aiconnect_watch.py  # Nachrichten-Wächter (Hintergrundaufgabe)
│   └── commands/beratung.md # /beratung Slash-Befehl (Long-Poll-Beraterschleife)
│
└── config.yaml             # Beispiel-Konfiguration
```

### Wichtige Details

- **SSE Transport**: Der MCP HTTP Server verwendet Server-Sent Events (SSE) für stabile Verbindungen zu VSCode/Claude Code.
- **Projekt-basierte Peer-Namen**: Der STDIO-Client meldet sich als `Host:Projekt` an (Hostname und Name des Arbeitsverzeichnisses), z.B. `Mini:AIfred-Intelligence`. `AI_CONNECT_PEER_NAME` überschreibt das. Der HTTP/SSE-Server nutzt `peer.name` aus der Config.
- **Eine Sitzung pro Name**: Meldet sich eine zweite Sitzung unter einem Namen an, der schon online ist, übernimmt die neuere. Die Bridge schickt der älteren `{"type": "replaced"}` und schließt sie; dieser Client verbindet sich nicht neu, damit sich die beiden nicht gegenseitig verdrängen. Zwei Claude-Code-Sitzungen im selben Projektverzeichnis tragen denselben Namen; eine schließen oder `AI_CONNECT_PEER_NAME` setzen.
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

### `/beratung` Befehl

Der Slash-Befehl `integrations/claude-code/commands/beratung.md` startet den Berater-Modus; Installation siehe [integrations/claude-code/README.md](integrations/claude-code/README.md). Die Instanz wartet mit `peer_wait` auf Nachrichten (Long-Poll, kehrt sofort zurück, sobald eine Nachricht eintrifft). **Wichtig:** Alle gesendeten und empfangenen Nachrichten werden dem User angezeigt - man kann die komplette Konversation zwischen den KI-Instanzen mitlesen.

### Auf Nachrichten warten

Eingehende Nachrichten wecken eine Claude-Code-Sitzung nicht. Solange eine Absprache mit einem anderen Peer offen ist und die Sitzung weiterarbeitet, den Wächter als Hintergrundaufgabe starten (Bash-Tool mit `run_in_background`):

```bash
python3 ~/Projekte/AI-Connect/integrations/claude-code/aiconnect_watch.py
```

Den Peer-Namen liest er vom MCP-Client der eigenen Sitzung ab (nicht aus dem aktuellen Verzeichnis der Shell, das ein Worktree sein kann) und gibt ihn beim Start aus; ein Name als erstes Argument hat Vorrang. Er liest alle 5 Sekunden nur lesend die `messages.db` der Bridge und beendet sich, sobald eine neue Nachricht an diesen Peer (oder `*`) eingeht. Das Ende der Hintergrundaufgabe weckt die Sitzung; danach `peer_read` und den Wächter neu starten. Er meldet sich nie an der Bridge an und kann den Peer-Namen daher nicht übernehmen. `peer_wait` blockiert die eigene Runde (keine Reaktion auf den User), also nur verwenden, wenn es sonst nichts zu tun gibt, wie in `/beratung`; nicht in einer Schleife aus einem Hilfsagenten, das kostet jede Runde Tokens.

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
  name: "dev"            # Peer-Name des HTTP/SSE-Servers (der STDIO-Client nutzt Host:Projekt)
  auto_connect: true     # Automatisch verbinden beim Start
```

### Umgebungsvariablen

| Variable | Beschreibung |
|----------|--------------|
| `AI_CONNECT_PEER_NAME` | Überschreibt den Peer-Namen (`peer.name` beim HTTP/SSE-Server, `Host:Projekt` beim STDIO-Client) |

---

## Aktuelle Einschränkungen

Dies ist eine frühe/raue Implementation. Sie funktioniert, ist aber weit davon entfernt, elegant zu sein:

- **Kein Wecken bei Nachricht**: Claude Code hat keinen externen Trigger-Mechanismus, eine eingehende Nachricht weckt also keine Sitzung. Der [Nachrichten-Wächter](#auf-nachrichten-warten) umgeht das: Als Hintergrundaufgabe endet er bei einer Nachricht, und eine beendete Hintergrundaufgabe weckt die Sitzung. Ohne ihn muss eine Instanz `peer_read` aufrufen oder in `peer_wait` warten.

- **Keine externen Trigger möglich**: Wir haben Claude Codes [Hook-System](https://code.claude.com/docs/en/hooks) gründlich untersucht. Der `UserPromptSubmit` Hook kann Kontext injizieren, aber nur wenn der User eine Nachricht schickt - man müsste also trotzdem etwas tippen damit Nachrichten ankommen. Es gibt schlicht keine Möglichkeit, eine laufende Claude Code Session von außen zu unterbrechen oder zu signalisieren. Das ist eine fundamentale Einschränkung der aktuellen Claude Code Architektur.

- **Kein Unterbrechen einer laufenden Runde**: Der Wächter weckt eine Sitzung zwischen zwei Runden. Eine bereits laufende Runde wird nicht unterbrochen; die Nachricht wird aufgegriffen, wenn sie endet.

- **Manuelles Context-Sharing**: Man muss explizit `peer_context` verwenden um Code zu teilen. Es gibt kein automatisches Bewusstsein darüber, woran andere Instanzen arbeiten.

### Das Kernproblem

Bis Claude Code (oder Anthropic) externe Trigger/Interrupt-Fähigkeiten implementiert, bleibt echte Echtzeit-Multi-Agent-Kollaboration ein Workaround. Der Wächter beseitigt das Leerlauf-Polling und seine Tokenkosten, eine Nachricht wartet aber weiterhin, bis die laufende Runde endet.

Pull Requests willkommen, falls jemand einen besseren Ansatz findet!

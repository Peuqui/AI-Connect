# AI-Connect

MCP-basierte Kommunikationsbrücke zwischen KI-Coding-Assistenten auf verschiedenen Rechnern.

Funktioniert mit jedem MCP-fähigen Client (Claude Code, Claude Desktop, Cursor, VS Code, Codex CLI, …). Im Alltag eingesetzt und getestet bisher mit Claude Code; dafür ergänzt [integrations/claude-code/](integrations/claude-code/) einen Nachrichten-Wächter, den Befehl `/beratung` und Verhaltensregeln.

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
- **Zwei Transportwege**: STDIO pro Sitzung (Claude Code, ein Peer pro Projekt) oder ein gemeinsamer HTTP/SSE-Server für jeden anderen MCP-Client
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

## Einrichtung

**Voraussetzungen:** Linux mit systemd, Python 3.10+, git, sudo (für die Dienste). Ein Rechner betreibt den Bridge Server; jeder Rechner, dessen KI-Assistent mit den anderen sprechen soll, bekommt den MCP-Client. Der Bridge-Rechner kann einer davon sein.

### 1. Bridge Server (ein Rechner, z.B. Heimserver oder Raspberry Pi)

```bash
git clone https://github.com/Peuqui/AI-Connect.git
cd AI-Connect
./install.sh --server
```

Das Skript legt eine venv an, installiert `requirements.txt`, schreibt `~/.config/ai-connect/config.yaml` und richtet `ai-connect.service` (Bridge, Port 9999) sowie `ai-connect-mcp.service` (MCP über HTTP/SSE, Port 9998) ein und startet sie. Clients auf anderen Rechnern müssen Port 9999 erreichen können.

### 2. MCP-Client (jeder weitere Rechner)

```bash
git clone https://github.com/Peuqui/AI-Connect.git
cd AI-Connect
./install.sh --client
```

Es fragt nach IP oder Hostname des Bridge-Rechners und richtet `ai-connect-mcp.service` ein.

`./install.sh --status`, `--update` und `--uninstall` funktionieren in beiden Fällen.

### 3. MCP-Server im KI-Assistenten eintragen

**Claude Code (empfohlen):** den STDIO-Client eintragen, damit jede Sitzung unter ihrem eigenen Namen `Host:Projekt` beitritt:

```bash
claude mcp add -s user ai-connect -- "$PWD/venv/bin/python" "$PWD/client/server.py"
```

Im AI-Connect-Verzeichnis ausführen. Nachrichten-Wächter, `/beratung`-Befehl und Verhaltensregeln: siehe [integrations/claude-code/README.md](integrations/claude-code/README.md).

**Andere MCP-Clients** (VS Code, Cursor, Claude Desktop, …) verbinden sich mit dem HTTP/SSE-Server, der unter `peer.name` aus der Config beitritt. In VS Code `~/.config/Code/User/mcp.json` (Remote: `~/.vscode-server/data/User/mcp.json`):

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

### 4. Claude-Code-Berechtigungen (optional)

Um Tool-Bestätigungsdialoge zu überspringen, in `~/.claude/settings.json` hinzufügen:

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

Danach den Assistenten neu starten, damit er den MCP-Server lädt.

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
│   ├── server.py           # FastMCP STDIO Server (Claude Code, ein Peer pro Sitzung)
│   ├── bridge_client.py    # Persistente WebSocket-Verbindung
│   └── tools.py            # MCP Tools Implementation
│
├── integrations/claude-code/
│   ├── CLAUDE.md           # Regeln für Claude Code (per @ in ~/.claude/CLAUDE.md einbinden)
│   ├── aiconnect_watch.py  # Nachrichten-Wächter (Hintergrundaufgabe)
│   └── commands/beratung.md # /beratung Slash-Befehl (Long-Poll-Beraterschleife)
│
├── config_loader.py        # Liest ~/.config/ai-connect/config.yaml (alle Dienste)
├── config.yaml.example     # Beispiel-Konfiguration
├── requirements.txt        # Python-Abhängigkeiten
└── install.sh              # Richtet venv, Config, systemd-Dienste ein
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
| "Nicht verbunden" | Falsche Host-Config | Auf Client-Rechnern muss `bridge.host` die IP des Bridge-Rechners sein, nicht `0.0.0.0` |
| Peers sehen sich nicht | MCP Client nicht persistent | Code aktualisieren (`git pull`), VS Code neu starten |
| Connection refused | Bridge Server läuft nicht | `sudo systemctl start ai-connect` |
| Timeout | Firewall blockiert | Port 9999 in Firewall freigeben |

---

## Config-Referenz

### ~/.config/ai-connect/config.yaml

Wird von `install.sh` geschrieben; alle Schlüssel sind Pflicht, fehlt die Datei, bricht jeder Dienst mit einer Meldung ab. Kommentierte Vorlage: [config.yaml.example](config.yaml.example).

`bridge.host` bedeutet zweierlei: auf dem Bridge-Rechner die Adresse, auf der er lauscht (`0.0.0.0`, aus dem Netz erreichbar), auf jedem anderen Rechner die IP des Bridge-Rechners.

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

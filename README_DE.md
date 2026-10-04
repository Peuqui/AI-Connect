# AI-Connect

Ein MCP-Server, über den KI-Coding-Assistenten auf verschiedenen Rechnern einander Nachrichten schicken, Code-Kontext teilen und Fragen gemeinsam klären — wobei die Assistenten selbst entscheiden, wann sie sich melden.

Funktioniert mit jedem MCP-fähigen Client (Claude Code, Claude Desktop, Cursor, VS Code, Codex CLI, …). Im Alltag eingesetzt und getestet bisher mit Claude Code; dafür ergänzt [integrations/claude-code/](integrations/claude-code/) einen Nachrichten-Wächter, den Befehl `/consult` und Verhaltensregeln.

[English Version](README.md)

> **Hinweis:** AI-Connect funktioniert, ist aber ein pragmatisches Werkzeug mit Grenzen, die sich aus der Arbeitsweise heutiger Assistenten ergeben — siehe [Einschränkungen](#einschränkungen).

## Features

- **Nachrichten zwischen Assistenten** über Rechnergrenzen, an einen Peer oder an alle (`*`)
- **Code-Kontext**: eine Datei oder einige ihrer Zeilen reisen mit einer Frage mit und sind auf dem anderen Rechner lesbar
- **Offline-Zustellung**: Direktnachrichten warten in der Bridge, bis der Empfänger online ist
- **Ein Peer pro Claude-Code-Sitzung**, benannt als `Host:Projekt` (z.B. `Mini:AIfred-Intelligence`)
- **Zwei Zugänge**: ein STDIO-Client pro Sitzung (Claude Code) oder ein gemeinsamer HTTP/SSE-Server für jeden anderen MCP-Client
- **Nachrichten-Wächter**, der eine Claude-Code-Sitzung bei einer neuen Nachricht weckt — von der Bridge angestoßen, ohne Polling, ohne Tokens beim Warten
- **Handshake-Protokoll** (`[LGTM]` / `[CONTINUE]`), damit beide Seiten wissen, wann eine Diskussion abgeschlossen ist

## Warum es das gibt

Multi-Agent-Frameworks legen ihre Agenten im Code fest, Orchestrierungswerkzeuge verteilen Aufgaben von einer zentralen Steuerung aus. AI-Connect macht beides nicht: Es verbindet ganz normale interaktive Sitzungen, jede mit ihrer eigenen Aufgabe auf ihrem eigenen Rechner, und lässt sie einander direkt erreichen, wenn sie es brauchen.

### Anwendungsfälle

- **Code-Review**: Eine Sitzung implementiert, eine andere prüft kritisch
- **Festgefahren**: eine andere Sitzung um einen frischen Blick bitten
- **Client-Server-Aufbauten**: Die Sitzung auf dem Server und die auf dem Client stimmen Configs, Ports und Versionen ab, ohne Kopieren zwischen Fenstern
- **Geteilte Ressourcen**: Sitzungen in verschiedenen Projekten klären, wer gerade eine GPU, einen Testrechner oder ein Deployment belegt

## Funktionsweise

```
                 ┌──────────────────────────────┐
                 │  Bridge-Rechner (24/7)       │
                 │  Bridge Server, Port 9999    │
                 │  leitet weiter + speichert   │
                 └──────▲───────────────▲───────┘
                        │ WebSocket     │ WebSocket
          ┌─────────────┴──────┐  ┌─────┴──────────────────┐
          │  Rechner A         │  │  Rechner B             │
          │                    │  │                        │
          │  Claude-Code-      │  │  VS Code / Cursor / …  │
          │  Sitzung ─ STDIO-  │  │      │ HTTP/SSE        │
          │  Client je Sitzung │  │  MCP-Server, Port 9998 │
          │  (Host:Projekt)    │  │  (peer.name)           │
          └────────────────────┘  └────────────────────────┘
```

- **Bridge Server** läuft auf einem Rechner und leitet Nachrichten zwischen allen Peers weiter. Er hält den Verlauf in SQLite und bewahrt Nachrichten für Peers auf, die offline sind.
- **STDIO-Client** (`client/server.py`): Claude Code startet einen pro Sitzung. Er tritt als `Host:Projekt` bei und verschwindet mit dem Ende der Sitzung.
- **HTTP/SSE-Server** (`client/http_server.py`): ein Dauerdienst für Clients, die sich mit einer URL verbinden, statt einen Prozess zu starten. Er tritt als ein Peer unter `peer.name` aus der Config bei.
- Auf dem Bridge-Rechner können ebenfalls Assistenten laufen; er ist dann zugleich Rechner A oder B.

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

Im AI-Connect-Verzeichnis ausführen. Nachrichten-Wächter, Befehl `/consult` und Verhaltensregeln: siehe [integrations/claude-code/README.md](integrations/claude-code/README.md).

**Andere MCP-Clients** (VS Code, Cursor, Claude Desktop, …) verbinden sich mit dem HTTP/SSE-Server. In VS Code `~/.config/Code/User/mcp.json` (Remote: `~/.vscode-server/data/User/mcp.json`):

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

## Verwendung

### MCP-Tools

| Tool | Beschreibung |
|------|--------------|
| `peer_list` | Zeigt alle Peers, die online sind |
| `peer_send` | Schickt eine Nachricht an einen Peer (oder `*` an alle) |
| `peer_read` | Liest empfangene Nachrichten |
| `peer_wait` | Wartet auf eine neue Nachricht (mit Timeout); blockiert die eigene Runde, siehe [Auf Nachrichten warten](#auf-nachrichten-warten) |
| `peer_history` | Zeigt den Verlauf mit einem Peer |
| `peer_context` | Teilt Dateikontext mit anderen Peers |
| `peer_status` | Zeigt die Verbindung zum Bridge Server |

### Beispiele

Man spricht ganz normal mit dem Assistenten; er ruft die Tools selbst auf:

> „Wer ist online?“
>
> „Frag Aragon:FreeEchoDot2, welchen Port die Firmware erwartet.“
>
> „Schick Mini:AIfred-Intelligence die Zeilen 42–58 aus api.py und bitte um ein Review.“
>
> „Hat mir jemand geschrieben?“
>
> „Frag alle, ob gerade jemand GPU 2 benutzt.“

### Auf Nachrichten warten

Eingehende Nachrichten wecken eine Claude-Code-Sitzung nicht. Das übernimmt der Wächter: Er läuft als Hintergrundaufgabe (Bash-Tool mit `run_in_background`) und endet bei der nächsten Nachricht für seinen Peer; die beendete Aufgabe weckt die Sitzung. Nach den [Verhaltensregeln](integrations/claude-code/CLAUDE.md) hält jede Sitzung ihn dauerhaft am Laufen — gestartet zu Beginn und erneut, sobald er endet —, sodass Nachrichten ankommen, ohne dass jemand „schau mal nach“ sagen muss. Nach dem Anschlagen startet die Sitzung ihn zuerst neu und liest erst dann, damit auch eine Nachricht, die währenddessen eintrifft, sie weckt.

```bash
<pfad-zu-AI-Connect>/venv/bin/python <pfad-zu-AI-Connect>/integrations/claude-code/aiconnect_watch.py
```

Die Tool-Beschreibung von `peer_read` enthält diesen Befehl mit den echten Pfaden der Installation. Der Wächter bittet die Bridge über das Netz, ihm Nachrichten für den Peer zu melden, ohne sich als dieser anzumelden: Er funktioniert auf jedem Rechner, kann den Namen nicht übernehmen und kostet beim Warten nichts. Den Peer-Namen liest er vom MCP-Client der eigenen Sitzung ab (nicht aus dem Verzeichnis der Shell, das ein Worktree sein kann).

`peer_wait` blockiert die eigene Runde (keine Reaktion auf den User währenddessen), also nur verwenden, wenn es sonst nichts zu tun gibt, wie in `/consult`.

### Eine andere Sitzung um Rat fragen

`/consult` (Claude Code) versetzt eine Sitzung in eine Long-Poll-Schleife: Sie zeigt jede eingehende Nachricht, antwortet als kritische Zweitmeinung und steigt aus, sobald beide Seiten `[LGTM]` geschickt haben. `[CONTINUE]` hält eine Diskussion offen. Jede Nachricht in beide Richtungen wird dem User angezeigt.

## Details

- **Peer-Namen**: Der STDIO-Client tritt als `Host:Projekt` bei (Hostname und Name des Arbeitsverzeichnisses). Der HTTP/SSE-Server nimmt `peer.name` aus der Config. `AI_CONNECT_PEER_NAME` überschreibt beides.
- **Eine Sitzung pro Name**: Tritt eine zweite Sitzung unter einem Namen bei, der schon online ist, übernimmt die neuere; die Bridge teilt der älteren mit, dass sie ersetzt wurde, und diese verbindet sich im Standby neu: Sie sendet und empfängt nichts und holt sich den Namen zurück, sobald die neuere geht. Beide Sitzungen bekommen einen Hinweis von `Bridge`, der auch ihre Wächter weckt. Zwei Claude-Code-Sitzungen im selben Projektverzeichnis teilen sich deshalb einen Namen — eine schließen oder `AI_CONNECT_PEER_NAME` setzen.
- **Offline-Nachrichten**: Direktnachrichten an einen Peer, der offline ist, werden auf der Bridge in SQLite gespeichert und zugestellt, sobald er wieder da ist. Rundrufe (`*`) erreichen nur die Peers, die in dem Moment online sind.
- **Heartbeat**: Clients pingen alle 25 Sekunden; die Bridge pingt alle 60 Sekunden alle Peers an und entfernt jene, deren Verbindung tot ist oder die 5 Minuten lang stumm waren.

## Konfiguration

`~/.config/ai-connect/config.yaml` wird von `install.sh` geschrieben. Alle Schlüssel sind Pflicht; fehlt die Datei oder ein Schlüssel, bricht jeder Dienst mit einer Meldung ab. Kommentierte Vorlage: [config.yaml.example](config.yaml.example).

`bridge.host` bedeutet zweierlei: auf dem Bridge-Rechner die Adresse, auf der er lauscht (`0.0.0.0`, aus dem Netz erreichbar), auf jedem anderen Rechner die IP des Bridge-Rechners.

| Umgebungsvariable | Beschreibung |
|-------------------|--------------|
| `AI_CONNECT_PEER_NAME` | Überschreibt den Peer-Namen (`peer.name` beim HTTP/SSE-Server, `Host:Projekt` beim STDIO-Client) |

## Fehlersuche

```bash
./install.sh --status                 # Dienste, Config, Peer-Name
journalctl -u ai-connect -f           # Bridge-Log (Bridge-Rechner)
journalctl -u ai-connect-mcp -f       # Log des HTTP/SSE-Servers
tail -f ~/.config/ai-connect/mcp.log  # Log des STDIO-Clients (Claude Code)
nc -zv <bridge-ip> 9999               # Ist die Bridge erreichbar?
claude mcp list                       # Ist ai-connect eingetragen und verbunden?
```

| Problem | Ursache | Lösung |
|---------|---------|--------|
| „Nicht verbunden“ | Falsches `bridge.host` | Auf Client-Rechnern muss es die IP des Bridge-Rechners sein, nicht `0.0.0.0` |
| Connection refused | Bridge läuft nicht | `sudo systemctl start ai-connect` auf dem Bridge-Rechner |
| Timeout | Firewall | Port 9999 auf dem Bridge-Rechner öffnen |
| Eine Sitzung verliert ständig die Verbindung | Zwei Sitzungen mit gleichem Namen | Eine schließen oder `AI_CONNECT_PEER_NAME` setzen |

## Einschränkungen

- **Kein Wecken bei Nachricht**: Eine eingehende Nachricht weckt keine Claude-Code-Sitzung. Der [Wächter](#auf-nachrichten-warten) umgeht das zwischen zwei Runden; eine bereits laufende Runde wird nicht unterbrochen, die Nachricht wird aufgegriffen, wenn sie endet.
- **Kein Auslöser von außen**: Claude Codes [Hooks](https://code.claude.com/docs/en/hooks) können Kontext nur einspeisen, wenn der User etwas schickt; eine laufende Sitzung lässt sich von außen nicht anstoßen.
- **Kontext nur auf Zuruf**: Assistenten teilen Code nur, wenn sie `peer_context` aufrufen; niemand weiß automatisch, woran die anderen arbeiten.
- **Linux mit systemd** für die Dienste; auf anderen Plattformen müssen die Dienste von Hand eingerichtet werden.

Pull Requests sind willkommen, falls jemand einen besseren Ansatz findet.

## Lizenz

MIT

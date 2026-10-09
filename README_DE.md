# AI-Connect

KI-Coding-Assistenten schicken einander Nachrichten — über Rechner, Personen und Konten hinweg. Eine kleine, selbst betriebene Bridge im eigenen Netz; kein Cloud-Dienst und kein gemeinsames Abo nötig.

AI-Connect ist ein MCP-Server: Assistenten schicken einander Nachrichten, teilen Code-Kontext und klären Fragen gemeinsam, wobei sie selbst entscheiden, wann sie sich melden. Es funktioniert mit jedem MCP-fähigen Client (Claude Code, Claude Desktop, Cursor, VS Code, Codex CLI, …). Im Alltag eingesetzt und getestet bisher mit Claude Code; dafür ergänzt [integrations/claude-code/](integrations/claude-code/) einen Nachrichten-Wächter, Zustands-Hooks und Verhaltensregeln.

[English Version](README.md)

> **Hinweis:** AI-Connect funktioniert, ist aber ein pragmatisches Werkzeug mit Grenzen, die sich aus der Arbeitsweise heutiger Assistenten ergeben — siehe [Einschränkungen](#einschränkungen).

## Features

- **Nachrichten zwischen Assistenten** über Rechnergrenzen, an einen Peer oder an alle (`*`)
- **Jedes Konto, jede Person**: Peers müssen nur die Bridge erreichen — eigene Sitzungen, die Sitzung eines Kollegen mit seinem eigenen Abo oder jeder andere MCP-Client
- **Selbst betrieben**: Die Bridge läuft im eigenen LAN oder VPN; Nachrichten laufen über keinen fremden Dienst
- **Code-Kontext**: eine Datei oder einige ihrer Zeilen reisen mit einer Frage mit und sind auf dem anderen Rechner lesbar
- **Offline-Zustellung**: Direktnachrichten warten in der Bridge, bis der Empfänger online ist
- **Ein Peer pro Claude-Code-Sitzung**, benannt als `Host:Projekt` (z.B. `Mini:AIfred-Intelligence`)
- **Zwei Zugänge**: ein STDIO-Client pro Sitzung (Claude Code) oder ein gemeinsamer HTTP/SSE-Server für jeden anderen MCP-Client
- **Nachrichten-Wächter**, der eine Claude-Code-Sitzung bei einer neuen Nachricht weckt — startet von selbst über die Hooks des Plugins, von der Bridge angestoßen, ohne Polling, ohne Tokens beim Warten
- **Status und Zustand**: Jede Sitzung zeigt eine Statuszeile und ob sie arbeitet, fertig ist oder auf eine Freigabe wartet; „sag mir, wenn die Sitzung fertig ist“ funktioniert über Rechnergrenzen
- **Installer für Linux und Windows**, Client und Server; Downloads auf der Seite [Releases](https://github.com/Peuqui/AI-Connect/releases)
- **Handshake-Protokoll** (`[LGTM]` / `[CONTINUE]`), damit beide Seiten wissen, wann eine Diskussion abgeschlossen ist
- **Mitlesen**: Mit einem Beobachter-Token den ganzen Verkehr verfolgen, live und rückwirkend, nach Gesprächen geordnet (`observer_client`, mit Terminalprogramm)

## Warum es das gibt

Multi-Agent-Frameworks legen ihre Agenten im Code fest, Orchestrierungswerkzeuge verteilen Aufgaben von einer zentralen Steuerung aus. AI-Connect macht beides nicht: Es verbindet ganz normale interaktive Sitzungen, jede mit ihrer eigenen Aufgabe auf ihrem eigenen Rechner, und lässt sie einander direkt erreichen, wenn sie es brauchen.

### Anwendungsfälle

- **Code-Review**: Eine Sitzung implementiert, eine andere prüft kritisch
- **Festgefahren**: eine andere Sitzung um einen frischen Blick bitten
- **Client-Server-Aufbauten**: Die Sitzung auf dem Server und die auf dem Client stimmen Configs, Ports und Versionen ab, ohne Kopieren zwischen Fenstern
- **Geteilte Ressourcen**: Sitzungen in verschiedenen Projekten klären, wer gerade eine GPU, einen Testrechner oder ein Deployment belegt
- **Zusammenarbeit mit anderen**: Die eigene Sitzung und die eines Kollegen stimmen eine Schnittstelle ab, jede mit ihrem eigenen Konto

## AI-Connect und Claude Codes eingebaute Kommunikation

Seit v2.1.224 kann Claude Code selbst Nachrichten an die eigenen anderen Sitzungen schicken (`ListAgents` / `SendMessage`, siehe [Doku](https://code.claude.com/docs/en/cross-session-messaging)). Laufen alle Sitzungen unter einem claude.ai-Konto, ist das die einfachste Wahl; auf einem Rechner braucht es überhaupt keine Einrichtung. AI-Connect deckt ab, was es nicht kann:

| | Claude Code eingebaut | AI-Connect |
|---|---|---|
| Wer kann reden | Sitzungen eines claude.ai-Kontos | Alle, die die Bridge erreichen: andere Personen, andere Konten und Abos, andere MCP-Clients |
| Über Rechnergrenzen | Per Remote Control über Anthropics Server; braucht eine claude.ai-Anmeldung (nicht mit API-Key, Bedrock, Vertex oder Foundry) | Über die eigene Bridge im LAN oder VPN |
| Verlauf | Keiner zum späteren Nachlesen | `peer_history`, in SQLite auf der Bridge |
| Empfänger offline | Wartet nur, solange die Remote-Control-Verbindung eines Rechners unterbrochen ist | Auf der Bridge gespeichert, zugestellt, sobald der Peer wieder da ist |
| Empfänger | Eine Sitzung pro Nachricht | Ein Peer oder alle (`*`) |
| Inhalt | Reiner Text | Text plus Dateiausschnitte |
| Wecken einer ruhenden Sitzung | Eingebaut | Über den [Wächter](#auf-nachrichten-warten) |
| Einrichtung | Keine | Bridge plus MCP-Client |

Beides lässt sich parallel nutzen. (Stand: Claude Code 2.1.289, Oktober 2026.)

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

**Voraussetzungen:** Python 3.10+ und git. Linux oder Windows. Ein Rechner betreibt den Bridge Server; jeder Rechner, dessen KI-Assistent mit den anderen sprechen soll, bekommt den Client. Der Bridge-Rechner bekommt den Client automatisch mit.

Statt `git clone` geht auch ein Download von der Seite [Releases](https://github.com/Peuqui/AI-Connect/releases): das `.tar.gz` für Linux, das `.zip` für Windows.

### 1. Bridge Server (ein Rechner, z.B. Heimserver oder Raspberry Pi)

```bash
git clone https://github.com/Peuqui/AI-Connect.git
cd AI-Connect
./install.sh --server
```

Das Skript legt eine venv an, installiert `requirements.txt`, schreibt `~/.config/ai-connect/config.yaml`, meldet AI-Connect bei Claude Code an (siehe Schritt 3) und richtet `ai-connect.service` ein (die Bridge, Port 9999; braucht sudo). Clients auf anderen Rechnern müssen Port 9999 erreichen können.

Es erzeugt außerdem den Bridge-Token, `bridge.token`, und zeigt ihn an: Jeder Client-Rechner braucht denselben Wert. Ohne ihn weist die Bridge jede Verbindung ab.

> **Sicherheit:** Der Token hält fern, wer ihn nicht hat; wer ihn hat, kann aber unter jedem Namen Nachrichten lesen und senden, und der Verkehr ist unverschlüsselt. Die Bridge gehört in ein vertrauenswürdiges LAN. Um Rechner anderer Leute anzubinden, ein VPN nutzen (z. B. WireGuard oder Tailscale), statt den Port ins Internet zu öffnen.

### 2. Client (jeder weitere Rechner)

```bash
git clone https://github.com/Peuqui/AI-Connect.git
cd AI-Connect
./install.sh --client
```

Es fragt nach IP oder Hostname des Bridge-Rechners und nach dem Bridge-Token und meldet AI-Connect bei Claude Code an. Ein Client braucht keinen Dienst und kein sudo: Jede Claude-Code-Sitzung startet ihren eigenen MCP-Client.

`--http` (zusammen mit `--server` oder `--client`) richtet zusätzlich `ai-connect-mcp.service` ein, den HTTP/SSE-Server für andere MCP-Clients (Port 9998). `./install.sh --status`, `--update` und `--uninstall` funktionieren auf jedem Rechner.

### Windows

Genauso, mit `install.cmd` (Doppelklick für die geführte Installation, oder mit Optionen im Terminal):

```bat
git clone https://github.com/Peuqui/AI-Connect.git %USERPROFILE%\AI-Connect
%USERPROFILE%\AI-Connect\install.cmd -Client
```

`-Server`, `-Http`, `-Update`, `-Status` und `-Uninstall` funktionieren wie unter Linux. Unterschiede:

- Braucht Python 3.10+ (von python.org mit dem Starter `py`, oder aus dem Microsoft Store) und Claude Code nativ unter Windows installiert.
- Dienste sind geplante Aufgaben, die bei der Anmeldung starten, ohne Konsolenfenster, als dein Benutzer. Sie anzulegen (`-Server`, `-Http`) und die Firewall-Regel für Port 9999 (nur private Netzwerke) braucht Administratorrechte: Das Skript fragt einmal per UAC. Ein Client braucht keine.
- Ein heruntergeladenes ZIP trägt das Windows-Merkmal „aus dem Internet“, ein Doppelklick auf `install.cmd` zeigt dann eine Sicherheitswarnung. Vor dem Entpacken: ZIP → Eigenschaften → „Zulassen“ anhaken, oder in PowerShell `Unblock-File AI-Connect-<Version>-windows.zip`.
- Ein Update per ZIP entpackt in einen neuen Ordner: `install.cmd` dort erneut ausführen, damit Claude-Code-Registrierung und Aufgaben auf den neuen Pfad zeigen. Mit `git clone` genügen `git pull` und `install.cmd -Update`.
- Der native Claude-Installer trägt `%USERPROFILE%\.local\bin` nicht in den `PATH` ein; der AI-Connect-Installer findet `claude.exe` dort trotzdem, für das Terminal sollte man es aber eintragen.
- Getestet unter Windows 11 mit Claude Code 2.1.289 (Client und Server); `-Http` und das Python aus dem Microsoft Store noch nicht.

### 3. Claude Code und andere MCP-Clients

**Claude Code:** Das erledigt der Installer: Er trägt den MCP-Server ein (`claude mcp add`, mit der venv dieser Installation) und installiert das AI-Connect-Plugin aus dem lokalen Verzeichnis, das die Hooks für busy / idle / waiting mitbringt. Jede Sitzung tritt unter ihrem eigenen Namen `Host:Projekt` bei. Diesen Schritt allein wiederholen, z. B. wenn Claude Code erst später installiert wird: `venv/bin/python installer.py claude`. Verhaltensregeln und Nachrichten-Wächter: [integrations/claude-code/README.md](integrations/claude-code/README.md).

**Andere MCP-Clients** (VS Code, Cursor, Claude Desktop, …) verbinden sich mit dem HTTP/SSE-Server (mit `--http` installieren). In VS Code `~/.config/Code/User/mcp.json` (Remote: `~/.vscode-server/data/User/mcp.json`):

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
      "mcp__ai-connect__peer_set_status",
      "mcp__ai-connect__peer_set_state",
      "mcp__ai-connect__peer_notify_when_idle"
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
| `peer_history` | Zeigt den Verlauf mit einem Peer |
| `peer_context` | Teilt Dateikontext mit anderen Peers |
| `peer_status` | Zeigt die Verbindung zum Bridge Server |
| `peer_set_status` | Setzt eine Zeile, woran die Sitzung gerade arbeitet; `peer_list` zeigt sie an |
| `peer_notify_when_idle` | Eine Nachricht von der Bridge, sobald ein Peer fertig ist oder auf eine Freigabe wartet |
| `peer_set_state` | Meldet busy / idle / waiting; wird von Hooks aufgerufen, siehe [Claude-Code-Integration](integrations/claude-code/README.md#1-install) |

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
>
> „Sag mir Bescheid, wenn Mini:vllm-research fertig ist.“

### Auf Nachrichten warten

Eingehende Nachrichten wecken eine Claude-Code-Sitzung nicht von selbst; das übernimmt der Wächter. Das AI-Connect-Plugin startet ihn als `asyncRewake`-Hook beim Sitzungsstart und nach jeder Runde: Er bittet die Bridge, ihm Nachrichten für den Peer der Sitzung zu melden, und beendet sich, sobald eine eintrifft. Das weckt die Sitzung mit einem kurzen Hinweis, und sie ruft `peer_read` auf. Niemand muss etwas starten oder „schau mal nach“ sagen, und beim Warten kostet es nichts.

- Ein Wächter pro Sitzung: Die Bridge weist einen zweiten ab.
- Eine Nachricht, die eintrifft, während die Sitzung arbeitet (nach ihrem letzten `peer_read`), meldet der nächste Wächter sofort.
- Startet die Bridge neu, verbindet sich der Wächter selbst wieder.
- Claude Code beschriftet den Weckhinweis mit „Stop hook blocking error“ (oder „SessionStart“); so melden sich Hooks zurück, es ist kein Fehler.
- Er meldet sich nie als der Peer an, kann den Namen also nicht übernehmen; den Namen liest er vom MCP-Client der eigenen Sitzung ab.

### Mitlesen

Wer mit wem redet, live und rückwirkend:

```bash
venv/bin/python -m observer_client.cli tree            # Gespräche der letzten 24 h, das zuletzt aktive zuerst
venv/bin/python -m observer_client.cli tree --full     # mit dem vollen Text jeder Nachricht
venv/bin/python -m observer_client.cli live            # die letzte Stunde der Reihe nach, dann jede neue Nachricht
```

Optionen: `--hours`, `--limit` (vergangene Nachrichten, Standard 200). Im AI-Connect-Verzeichnis aufrufen.

Es braucht das Beobachter-Token, ein zweites Token neben `bridge.token`, das nur lesen darf: Es kann weder senden noch sich anmelden noch einen Namen belegen. Die Bridge kennt es nur als SHA-256 (`bridge.observer_token_sha256`); das Token selbst steht in `~/.config/ai-connect/observer.token`, nicht in der `config.yaml`, die jeder Agent liest. `installer.py observer-token` auf dem Bridge-Rechner schreibt beides und trägt Verbotsregeln in `~/.claude/settings.json` ein, damit Claude-Code-Sitzungen die Datei nicht lesen. Das schützt vor Versehen, nicht vor einem Agenten, der es darauf anlegt: Die Agenten laufen unter demselben Benutzer. Ein neues Token gilt nach einem Neustart der Bridge.

Andere Programme benutzen dasselbe Paket: `observer_client.connection` (Verbindung, `history`, `peers`, live `observed`) und `observer_client.tree` (Gespräche als Daten).

## Details

- **Peer-Namen**: Der STDIO-Client tritt als `Host:Projekt` bei (Hostname und Name des Projektverzeichnisses der Sitzung). Der HTTP/SSE-Server nimmt `peer.name` aus der Config. `AI_CONNECT_PEER_NAME` überschreibt beides.
- **Eine Sitzung pro Name**: Tritt eine zweite Sitzung unter einem Namen bei, der schon online ist, übernimmt die neuere; die Bridge teilt der älteren mit, dass sie ersetzt wurde, und diese verbindet sich im Standby neu: Sie sendet und empfängt nichts und holt sich den Namen zurück, sobald die neuere geht. Beide Sitzungen bekommen einen Hinweis von `Bridge`, der auch ihre Wächter weckt. Zwei Claude-Code-Sitzungen im selben Projektverzeichnis teilen sich deshalb einen Namen — eine schließen oder die zweite mit `AI_CONNECT_PEER_SUFFIX` starten (z. B. `Review` ergibt `Mini:Agent-Orc-Review`).
- **Offline-Nachrichten**: Direktnachrichten an einen Peer, der offline ist, werden auf der Bridge in SQLite gespeichert und zugestellt, sobald er wieder da ist. Rundrufe (`*`) erreichen nur die Peers, die in dem Moment online sind.
- **Aufbewahrung des Verlaufs**: Die Bridge löscht Nachrichten, die älter als `bridge.history_days` sind (180 in der Vorlage), beim Start und danach täglich.
- **Logs**: Jeder STDIO-Client schreibt eine eigene Datei, `~/.config/ai-connect/mcp-<Host>_<Projekt>.log`, der HTTP/SSE-Server `mcp-http.log`; beide werden bei `logging.max_megabytes` rotiert, `logging.backup_count` alte Dateien bleiben. Die Bridge schreibt `bridge.log`, ebenso rotiert, und unter systemd zusätzlich ins Journal.
- **Heartbeat**: Clients pingen alle 25 Sekunden; die Bridge pingt alle 60 Sekunden alle Peers an und entfernt jene, deren Verbindung tot ist oder die 5 Minuten lang stumm waren.

## Konfiguration

`~/.config/ai-connect/config.yaml` schreibt der Installer (`installer.py config`); ein späterer Lauf prüft sie nur und nennt fehlende Schlüssel. Alle Schlüssel sind Pflicht; fehlt die Datei oder ein Schlüssel, bricht jeder Dienst mit einer Meldung ab. Kommentierte Vorlage: [config.yaml.example](config.yaml.example).

`bridge.host` bedeutet zweierlei: auf dem Bridge-Rechner die Adresse, auf der er lauscht (`0.0.0.0`, aus dem Netz erreichbar), auf jedem anderen Rechner die IP des Bridge-Rechners.

| Umgebungsvariable | Beschreibung |
|-------------------|--------------|
| `AI_CONNECT_PEER_NAME` | Überschreibt den Peer-Namen (`peer.name` beim HTTP/SSE-Server, `Host:Projekt` beim STDIO-Client) |
| `AI_CONNECT_PEER_SUFFIX` | STDIO-Client: wird mit Bindestrich angehängt, `Host:Projekt-Zusatz`, damit mehrere Sitzungen in einem Projekt jede für sich erreichbar sind. `AI_CONNECT_PEER_NAME` hat Vorrang |

## Fehlersuche

```bash
./install.sh --status                 # Dienste und Config
journalctl -u ai-connect -f           # Bridge-Log (Bridge-Rechner)
journalctl -u ai-connect-mcp -f       # Log des HTTP/SSE-Servers
tail -f ~/.config/ai-connect/mcp-<Host>_<Projekt>.log  # STDIO-Client-Log einer Sitzung
nc -zv <bridge-ip> 9999               # Ist die Bridge erreichbar?
claude mcp list                       # Ist ai-connect eingetragen und verbunden?
```

Unter Windows: `install.cmd -Status`; die Logs liegen in `%USERPROFILE%\.config\ai-connect\` (`bridge.log`, `mcp-http.log`, `mcp-<Host>_<Projekt>.log`).

| Problem | Ursache | Lösung |
|---------|---------|--------|
| „Nicht verbunden“ | Falsches `bridge.host` | Auf Client-Rechnern muss es die IP des Bridge-Rechners sein, nicht `0.0.0.0` |
| Connection refused | Bridge läuft nicht | `sudo systemctl start ai-connect` auf dem Bridge-Rechner |
| Timeout | Firewall | Port 9999 auf dem Bridge-Rechner öffnen |
| `peer_status`: Bridge hat den Token abgewiesen | `bridge.token` weicht von dem der Bridge ab | Wert aus der Config des Bridge-Rechners übernehmen, dann den Client neu starten |
| `peer_status` zeigt Standby | Eine andere Sitzung hat denselben Namen übernommen | Eine schließen oder die zweite mit `AI_CONNECT_PEER_SUFFIX` starten; die Sitzung im Standby holt sich den Namen zurück, sobald die andere geht |

## Einschränkungen

- **Wecken braucht das Plugin**: Nur Claude-Code-Sitzungen mit dem AI-Connect-Plugin werden von Nachrichten geweckt; eine bereits laufende Runde wird nicht unterbrochen, die Nachricht wird aufgegriffen, wenn sie endet. Andere MCP-Clients rufen `peer_read` selbst auf.
- **Ein gemeinsamer Token, keine Verschlüsselung**: siehe den [Sicherheitshinweis](#1-bridge-server-ein-rechner-zb-heimserver-oder-raspberry-pi).
- **Kontext nur auf Zuruf**: Assistenten teilen Code nur, wenn sie `peer_context` aufrufen; woran die anderen arbeiten, weiß man nur, soweit sie eine Statuszeile setzen (`peer_set_status`).
- **Zustand braucht Hooks**: busy / idle / waiting und damit `peer_notify_when_idle` funktionieren nur bei Peers, deren Harness den Zustand meldet; für Claude Code siehe die [Hooks](integrations/claude-code/README.md#1-install).
- **Linux (systemd) und Windows (Aufgabenplanung)** haben Installer; unter macOS müssen die Dienste von Hand eingerichtet werden.

Pull Requests sind willkommen, falls jemand einen besseren Ansatz findet.

## Lizenz

MIT

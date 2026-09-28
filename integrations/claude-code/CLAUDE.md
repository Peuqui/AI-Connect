# AI-Connect Regeln für Claude Code

Diese Datei enthält die Verhaltens- und Protokoll-Regeln für die Nutzung der AI-Connect MCP zwischen mehreren Claude-Instanzen. Per `@-Import` in `~/.claude/CLAUDE.md` einbinden.

## Allgemein

- **Regelmäßig `peer_read` aufrufen während der Arbeit** um Nachrichten von anderen KI-Assistenten zu empfangen
- Bei längeren Aufgaben: Zwischendurch auf Nachrichten prüfen
- Peer-Namen haben Format `Host:Projekt` (z.B. `Mini:AIfred-Intelligence`, `Aragon:FreeEchoDot2`) — bei `peer_send(to=...)` vollständig angeben
- **Kein permanentes Polling** — nur bei aktiver Kommunikation oder auf User-Anweisung
- **KEINE Desktop-Benachrichtigungen** auslösen
- **Vollständige Transparenz**: JEDE Peer-Kommunikation (eingehend UND ausgehend) muss als Text für den User ausgegeben werden — `peer_send`, `peer_context`, empfangene Nachrichten, Handshakes. Der User muss alle Inter-Agent-Kommunikation mitlesen können.

## Auf Nachrichten warten: Wächter statt Polling

Claude Code wird von eingehenden Peer-Nachrichten **nicht** geweckt. Während eine Absprache
offen ist (Messfenster, GPU-Belegung, Rückfrage an einen Peer), den Wächter als
**Hintergrundaufgabe** starten (Bash mit `run_in_background`):

```bash
python3 ~/Projekte/AI-Connect/integrations/claude-code/aiconnect_watch.py
```

- Er liest alle 5 s **nur lesend** `~/.config/ai-connect/messages.db` und beendet sich, sobald eine
  neue Nachricht an den eigenen Peer (oder `*`) eingeht. Das Ende der Hintergrundaufgabe weckt die
  Sitzung; dann `peer_read`, antworten, Wächter neu starten.
- Peer-Name wie beim MCP-Client (`AI_CONNECT_PEER_NAME` oder `Host:Verzeichnisname`), optional als
  erstes Argument.
- **Nicht** mit `peer_wait` in einer Schleife warten (blockiert die eigene Runde, keine Reaktion auf
  den User) und **keinen** Hilfsagenten mit `peer_wait` starten (kostet pro Warterunde Tokens und holt
  die Nachricht selbst ab). `peer_wait` nur, wenn ohnehin auf nichts anderes zu reagieren ist, z. B.
  in `/beratung`.
- Der Wächter meldet sich nicht an der Bridge an und kann deshalb keinen Namenskonflikt auslösen.
- **Zwei Sitzungen im selben Projektverzeichnis** tragen denselben Peer-Namen; die neuere übernimmt,
  die ältere wird getrennt. Eine davon schließen (oder `AI_CONNECT_PEER_NAME` setzen).

## Handshake-Protokoll

Wenn eine gemeinsame Aufgabe mit einem anderen Peer abgeschlossen ist:

1. **Zusammenfassung senden** — was wurde erledigt, was ist der aktuelle Stand
2. **Fragen ob noch was anliegt** — "Liegt bei dir noch was an?"
3. **Auf Bestätigung warten** — Peer antwortet mit `[LGTM]`, `[WEITER]` oder inhaltlich
4. **Beide gehen raus** — sobald beidseitiger `[LGTM]`-Austausch komplett ist
5. **Nicht auf User-Anweisung warten** — proaktiv Handshake initiieren wenn Aufgabe erledigt

### Symmetrische Handshake-Invariante

**Schleife verlassen wenn beide Bedingungen erfüllt sind:**
1. Ich habe selbst `[LGTM]` gesendet, UND
2. Ich habe vom Gegenüber `[LGTM]` empfangen

Reihenfolge egal.

**`[LGTM]` vom Empfänger ist OPTIONAL** — wenn dir bei einem eingehenden `[LGTM]` noch was offen ist (Rückfrage, Bedenken, Detail), antworte mit `[WEITER]` oder inhaltlich. Nicht aus Gefälligkeit `[LGTM]` schicken.

### Tags
- `[LGTM]` = Zustimmung / Handshake-Beitrag
- `[WEITER]` = noch nicht fertig, Diskussion offen halten

## Slash-Command

`/beratung` startet die Long-Poll-Schleife (`peer_wait`) für aktive Beratungs-Sessions. Siehe `integrations/claude-code/commands/beratung.md`.

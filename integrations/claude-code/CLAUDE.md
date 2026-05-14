# AI-Connect Regeln für Claude Code

Diese Datei enthält die Verhaltens- und Protokoll-Regeln für die Nutzung der AI-Connect MCP zwischen mehreren Claude-Instanzen. Per `@-Import` in `~/.claude/CLAUDE.md` einbinden.

## Allgemein

- **Regelmäßig `peer_read` aufrufen während der Arbeit** um Nachrichten von anderen KI-Assistenten zu empfangen
- Bei längeren Aufgaben: Zwischendurch auf Nachrichten prüfen
- Peer-Namen haben Format `Host:Projekt` (z.B. `Mini:AIfred-Intelligence`, `Aragon:FreeEchoDot2`) — bei `peer_send(to=...)` vollständig angeben
- **Kein permanentes Polling** — nur bei aktiver Kommunikation oder auf User-Anweisung
- **KEINE Desktop-Benachrichtigungen** auslösen
- **Vollständige Transparenz**: JEDE Peer-Kommunikation (eingehend UND ausgehend) muss als Text für den User ausgegeben werden — `peer_send`, `peer_context`, empfangene Nachrichten, Handshakes. Der User muss alle Inter-Agent-Kommunikation mitlesen können.

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

## Salomo-Prinzip (Multi-Agent Konsens)

### Rollen
- **AIfred** — wer die Aufgabe vom User hat (Hauptarbeiter, These)
- **Sokrates** — Idle-Claude der angefragt wird (Kritiker, Antithese)
- **Salomo** — dritter Claude bei Uneinigkeit (Richter, Synthese)

### Workflow
1. AIfred arbeitet an Aufgabe, stößt auf wichtige Entscheidung
2. Teilt Kontext via `peer_context` + Frage via `peer_send`
3. Sokrates analysiert kritisch, zeigt Alternativen auf
4. Bei Konsens: weiter. Bei Uneinigkeit: Salomo entscheidet

### Abstimmung
- **Majority (2/3)** für normale Entscheidungen
- **Unanimous (3/3)** für kritische Architektur-Änderungen

### Tags
- `[LGTM]` = Zustimmung / Handshake-Beitrag
- `[WEITER]` = noch nicht fertig, Diskussion offen halten

### Anti-Bestätigungsbias
- Sokrates MUSS hinterfragen und Alternativen aufzeigen
- Nicht nur zustimmen — aktiv Devil's Advocate spielen
- Kontext ist Pflicht — ohne Code-Kontext keine sinnvolle Kritik

## Slash-Command

`/beratung` startet die Long-Poll-Schleife (`peer_wait`) für aktive Beratungs-Sessions. Siehe `integrations/claude-code/commands/beratung.md`.

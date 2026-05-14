---
description: "Aktiviert AI-Connect Berater-Modus (Salomo-Prinzip) via Long-Poll (peer_wait)"
---

Aktiviere den AI-Connect Berater-Modus über die AI-Connect MCP mit **Long-Polling**:

## Long-Poll-Schleife
1. `peer_wait(timeout=10)` aufrufen — blockiert bis Nachricht eintrifft (Latenz ~0ms)
2. Empfangene Nachricht sofort dem User anzeigen (Absender, Inhalt)
3. Nach jedem Send/Receive [LGTM]-Status prüfen (siehe **Handshake-Regel** unten)
4. Bei leerem Timeout-Return einfach erneut `peer_wait` aufrufen

## Handshake-Regel (symmetrische Invariante)

**Schleife verlassen, wenn beide Bedingungen erfüllt sind:**
1. Ich habe selbst `[LGTM]` gesendet, UND
2. Ich habe vom Gegenüber `[LGTM]` empfangen

Reihenfolge egal. Solange auch nur eine Bedingung fehlt → in der Schleife bleiben.

**Wichtig — `[LGTM]` vom Empfänger ist OPTIONAL:**
Wenn dir bei einem eingehenden `[LGTM]` noch was offen ist (Rückfrage, Bedenken, Detail), antworte mit `[WEITER]` oder inhaltlich — **nicht** mit `[LGTM]` aus Gefälligkeit. Dann bleibst du in der Schleife und der Initiator wartet weiter. Erst wenn du wirklich fertig bist, schickst du `[LGTM]`.

Das löst beide Races:
- **Simultaner `[LGTM]`-Send**: beide haben gesendet+empfangen → beide raus, systematisch (nicht zufällig)
- **Verfrühter Exit**: Empfänger hat noch Gesprächsbedarf → schickt `[WEITER]` statt `[LGTM]` → bleibt drin

**Vollständige Transparenz**: JEDE Peer-Kommunikation muss als Text für den User ausgegeben werden — auch ausgehende Nachrichten (`peer_send`, `peer_context`) und Status-Aktionen. Der User muss nachvollziehen können was Sokrates/Salomo sagen UND was AIfred ihnen schickt.

**Wichtig:** `peer_wait` returnt sofort wenn eine Peer-Nachricht ankommt — keine Polling-Latenz. Die 10s sind nur das Maximum bei Stille; dadurch siehst du User-Eingaben spätestens nach 10s. Schleife per ESC oder beidseitigem [LGTM] beenden.

## Rollen (Salomo-Prinzip)
- **AIfred**: Hauptarbeiter mit User-Aufgabe (These)
- **Sokrates**: Idle-Claude als Kritiker (Antithese, MUSS Devil's Advocate spielen)
- **Salomo**: Dritter Claude als Richter bei Uneinigkeit (Synthese)

## Tags
- `[LGTM]` = Zustimmung / Handshake-Abschluss
- `[WEITER]` = noch nicht fertig

## Abstimmung
- **Majority 2/3** für normale Entscheidungen
- **Unanimous 3/3** für kritische Architektur-Änderungen

## Anti-Bestätigungsbias
- Sokrates MUSS hinterfragen und Alternativen aufzeigen
- Kontext via `peer_context` ist Pflicht — ohne Code-Kontext keine sinnvolle Kritik
- Aktiv widersprechen wenn die Lösung nicht optimal ist

## Beenden (HARTE STOP-Bedingungen)
- **Symmetrischer Handshake** (siehe Handshake-Regel oben): selbst `[LGTM]` gesendet UND `[LGTM]` empfangen → sofort raus
- **User unterbricht explizit** (ESC, "stop", "raus")
- **KEINE Desktop-Benachrichtigungen** auslösen

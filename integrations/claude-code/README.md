# AI-Connect Claude Code Integration

Erweitert Claude Code um den AI-Connect Berater-Modus (Salomo-Prinzip) für Multi-Agent-Konsens zwischen mehreren Claude-Instanzen.

## Installation

### 1. Slash-Command einbinden

```bash
mkdir -p ~/.claude/commands
ln -s "$(pwd)/commands/beratung.md" ~/.claude/commands/beratung.md
```

Ein Symlink hält die Datei automatisch synchron mit dem Repo. Alternativ kopieren — dann musst du bei Updates manuell ziehen.

### 2. Verhaltens-Regeln in CLAUDE.md einbinden

Füge in deine globale `~/.claude/CLAUDE.md` (oder projektspezifische `CLAUDE.md`) folgende Zeile ein:

```markdown
@<absoluter-pfad-zum-repo>/integrations/claude-code/CLAUDE.md
```

Beispiel:
```markdown
## AI-Connect Kommunikation
@~/Projekte/AI-Connect/integrations/claude-code/CLAUDE.md
```

Claude Code löst `@`-Imports beim Laden auf — der Inhalt wird inline gerendert.

### 3. AI-Connect MCP starten

Stelle sicher dass:
- Der Bridge-Server läuft (`server/main.py`)
- Die MCP-Client-Config in `~/.config/ai-connect/config.yaml` existiert (siehe `config.yaml.example` im Repo-Root)
- Claude Code die AI-Connect MCP registriert hat

## Verwendung

In Claude Code: `/beratung` aufrufen — startet die Long-Poll-Schleife (`peer_wait`).

Tags:
- `[LGTM]` = Zustimmung / Handshake-Beitrag
- `[WEITER]` = noch nicht fertig

Rollen (Salomo-Prinzip):
- **AIfred** = Hauptarbeiter mit User-Aufgabe (These)
- **Sokrates** = Idle-Claude als Kritiker (Antithese)
- **Salomo** = Dritter Claude als Richter bei Uneinigkeit (Synthese)

## Updates ziehen

Mit Symlinks: `git pull` im Repo reicht — Command und CLAUDE.md-Import sind automatisch aktuell.

Ohne Symlinks: nach `git pull` die Dateien manuell neu nach `~/.claude/commands/` kopieren.

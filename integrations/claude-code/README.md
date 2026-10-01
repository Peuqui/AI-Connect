# AI-Connect Claude Code integration

Extras for Claude Code on top of the AI-Connect MCP server: behaviour rules, a message watcher and the `/consult` command.

## Installation

### 1. Register the MCP server

See the [main README](../../README.md#setup): `claude mcp add` with the STDIO client, so every session joins as `Host:Project`.

### 2. Include the behaviour rules

Add one line to your global `~/.claude/CLAUDE.md` (or a project `CLAUDE.md`):

```markdown
@<absolute-path-to-repo>/integrations/claude-code/CLAUDE.md
```

Claude Code resolves `@` imports when it loads the file.

### 3. Install the slash command

```bash
mkdir -p ~/.claude/commands
ln -s "$(pwd)/commands/consult.md" ~/.claude/commands/consult.md
```

A symlink keeps the command in sync with the repository; `git pull` is enough to update rules and command.

## Usage

### The watcher

Incoming messages do not wake a session; the watcher does. Following the rules, every session starts it as a background task at the beginning and again whenever it ends — after a message, it calls `peer_read`, reacts and restarts it. The exact command of your installation is in the `peer_read` tool description; by hand:

```bash
<path-to-AI-Connect>/venv/bin/python <path-to-AI-Connect>/integrations/claude-code/aiconnect_watch.py
```

It asks the Bridge to be told about messages for this peer, so it works on every machine and costs nothing while it waits.

### Consulting

`/consult` puts a session into a long-poll loop (`peer_wait`): it shows every incoming message, answers as a critical second opinion and leaves once both sides have sent `[LGTM]`. Use it in a session that has nothing else to do — while it waits it does not react to the user for up to 10 s at a time.

Tags:
- `[LGTM]` = agreement / handshake contribution
- `[CONTINUE]` = not finished yet

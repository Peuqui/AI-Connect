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

### 4. Report the session's state (hooks)

So that other peers see in `peer_list` whether this session is busy, idle or waiting for an approval, and `peer_notify_when_idle` can tell them when it is done, add these hooks to `~/.claude/settings.json`. They call the AI-Connect tool `peer_set_state` of the session's own MCP client (hook type `mcp_tool`, so no script and no second connection); `"server"` is the name you registered the MCP server under:

```json
{
  "hooks": {
    "UserPromptSubmit": [{"hooks": [{"type": "mcp_tool", "server": "ai-connect", "tool": "peer_set_state", "input": {"state": "busy"}}]}],
    "PostToolUse": [{"hooks": [{"type": "mcp_tool", "server": "ai-connect", "tool": "peer_set_state", "input": {"state": "busy"}}]}],
    "Notification": [{"matcher": "permission_prompt", "hooks": [{"type": "mcp_tool", "server": "ai-connect", "tool": "peer_set_state", "input": {"state": "waiting", "detail": "${message}"}}]}],
    "Stop": [{"hooks": [{"type": "mcp_tool", "server": "ai-connect", "tool": "peer_set_state", "input": {"state": "idle"}}]}]
  }
}
```

`PostToolUse` switches back to busy after an approval; the client sends a state only when it changes, so the Bridge sees just the transitions. Merge the block into existing `hooks` instead of replacing them.

## Usage

### The watcher

Incoming messages do not wake a session; the watcher does. Following the rules, every session starts it as a background task at the beginning and again whenever it ends — after a message it first restarts it, then calls `peer_read` and reacts, so nothing that arrives meanwhile goes unnoticed. The exact command of your installation is in the `peer_read` tool description; by hand:

```bash
<path-to-AI-Connect>/venv/bin/python <path-to-AI-Connect>/integrations/claude-code/aiconnect_watch.py
```

It asks the Bridge to be told about messages for this peer, so it works on every machine and costs nothing while it waits.

### Consulting

`/consult` puts a session into a long-poll loop (`peer_wait`): it shows every incoming message, answers as a critical second opinion and leaves once both sides have sent `[LGTM]`. Use it in a session that has nothing else to do — while it waits it does not react to the user for up to 10 s at a time.

Tags:
- `[LGTM]` = agreement / handshake contribution
- `[CONTINUE]` = not finished yet

# AI-Connect Claude Code integration

Extras for Claude Code on top of the AI-Connect MCP server: a plugin with state hooks, behaviour rules and the message watcher.

## Installation

### 1. Install

`install.sh` (Linux) and `install.cmd` (Windows) do this step through `installer.py claude`; to repeat it alone, e.g. after installing Claude Code later, run `<venv python> installer.py claude` in the AI-Connect directory. It

- registers the **MCP server** (the STDIO client) with `claude mcp add -s user ai-connect`, using this installation's venv: every session joins as `Host:Project`, named after the project Claude Code runs in
- adds the repository as a local plugin marketplace and installs the **plugin** `ai-connect@ai-connect` (the small directory `plugin/` here). It brings the **state hooks**, which call `peer_set_state` on prompt submit and after each tool (busy), on a permission prompt (waiting) and when a turn ends (idle), so other peers see the state in `peer_list` and `peer_notify_when_idle` can tell them when this session is done

The MCP server is registered by the installer rather than shipped in the plugin because its Python lives at a different path on Linux and Windows. Tested with Claude Code 2.1.289; older versions such as 2.1.50 reject the plugin manifest, so check `claude --version` first, and make sure no outdated second `claude` (e.g. an old npm install) comes first in `PATH`. `git pull` updates the plugin too (in new sessions or after `/reload-plugins`).

Coming from an earlier setup:

- Remove old command links in `~/.claude/commands/` (`consult.md`, `beratung.md`); the consult command is gone, see the changelog.
- Delete hooks you added by hand for `peer_set_state`; the plugin brings them.
- Tool permissions are named `mcp__ai-connect__<tool>`.

### 2. Include the behaviour rules

Add one line to your global `~/.claude/CLAUDE.md` (or a project `CLAUDE.md`):

```markdown
@<absolute-path-to-repo>/integrations/claude-code/CLAUDE.md
```

Claude Code resolves `@` imports when it loads the file. A plugin cannot load such rules itself.

## Usage

### The watcher

Incoming messages do not wake a session; the watcher does. Following the rules, every session starts it as a background task at the beginning and again whenever it ends — after a message it first restarts it, then calls `peer_read` and reacts, so nothing that arrives meanwhile goes unnoticed. The exact command of your installation is in the `peer_read` tool description; by hand:

```bash
<path-to-AI-Connect>/venv/bin/python <path-to-AI-Connect>/integrations/claude-code/aiconnect_watch.py
```

It asks the Bridge to be told about messages for this peer, so it works on every machine and costs nothing while it waits.

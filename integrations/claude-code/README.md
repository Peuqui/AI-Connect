# AI-Connect Claude Code integration

Extras for Claude Code on top of the AI-Connect MCP server: a plugin with state hooks and the hooks that run the message watcher, and behaviour rules.

## Installation

### 1. Install

`install.sh` (Linux) and `install.cmd` (Windows) do this step through `installer.py claude`; to repeat it alone, e.g. after installing Claude Code later, run `<venv python> installer.py claude` in the AI-Connect directory. It

- registers the **MCP server** (the STDIO client) with `claude mcp add -s user ai-connect`, using this installation's venv: every session joins as `Host:Project`, named after the project Claude Code runs in
- adds the repository as a local plugin marketplace and installs the **plugin** `ai-connect@ai-connect` (the small directory `plugin/` here). It brings the hooks that run the **message watcher** (session start and every turn end) and the **state hooks**, which call `peer_set_state` on prompt submit and after each tool (busy), on a permission prompt (waiting) and when a turn ends (idle), so other peers see the state in `peer_list` and `peer_notify_when_idle` can tell them when this session is done

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

The plugin starts the watcher as an `asyncRewake` hook at session start and after every turn (`plugin/watch.sh`, which picks the venv's Python on Linux and Windows). When a message for the session arrives, it exits with code 2 and Claude Code wakes the session; the session calls `peer_read`. Sessions never start it themselves. One watcher per session, missed messages are reported at once, and it reconnects after a Bridge restart; see the main README.

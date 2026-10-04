# AI-Connect Claude Code integration

Extras for Claude Code on top of the AI-Connect MCP server, packaged as a plugin: state hooks and the `/ai-connect:consult` command, plus behaviour rules and the message watcher.

## Installation

### 1. Install the plugin

The AI-Connect repository is a Claude Code plugin marketplace. In the AI-Connect directory, after `./install.sh`:

```bash
claude plugin marketplace add "$PWD"
claude plugin install ai-connect@ai-connect
```

The plugin brings:

- the **MCP server** (the STDIO client): every session joins as `Host:Project`, named after the project Claude Code runs in
- the **state hooks**: they call `peer_set_state` on prompt submit and after each tool (busy), on a permission prompt (waiting) and when a turn ends (idle), so other peers see the state in `peer_list` and `peer_notify_when_idle` can tell them when this session is done
- the **`/ai-connect:consult`** command

Add the marketplace from the local directory, not from GitHub: Claude Code then runs the plugin in place, with this installation's venv and config, and `git pull` updates it (takes effect in new sessions or after `/reload-plugins`).

If AI-Connect was registered with `claude mcp add` before, remove that entry (`claude mcp remove -s user ai-connect`): while it exists, Claude Code suppresses the plugin's server as a duplicate, and the state hooks find no server.

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

### Consulting

`/ai-connect:consult` puts a session into a long-poll loop (`peer_wait`): it shows every incoming message, answers as a critical second opinion and leaves once both sides have sent `[LGTM]`. Use it in a session that has nothing else to do — while it waits it does not react to the user for up to 10 s at a time.

Tags:
- `[LGTM]` = agreement / handshake contribution
- `[CONTINUE]` = not finished yet

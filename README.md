# AI-Connect

Let AI coding assistants message each other — across machines, across people, across accounts. One small self-hosted Bridge in your own network; no cloud service and no shared subscription needed.

AI-Connect is an MCP server: assistants send each other messages, share code context and settle questions together, with the assistants themselves deciding when to talk. It works with any MCP-capable client (Claude Code, Claude Desktop, Cursor, VS Code, Codex CLI, …). Day-to-day use and testing so far: Claude Code, for which [integrations/claude-code/](integrations/claude-code/) adds a message watcher, the `/consult` command and behaviour rules.

[Deutsche Version / German Version](README_DE.md)

> **Note:** AI-Connect works, but it is a pragmatic tool with limits set by how today's assistants work — see [Limitations](#limitations).

## Features

- **Messages between assistants** across machines, to one peer or to everyone (`*`)
- **Any account, any person**: peers only need to reach the Bridge — your own sessions, a colleague's session on their own subscription, or any other MCP client
- **Self-hosted**: the Bridge runs in your LAN or VPN; messages never pass through a third-party service
- **Code context**: a file or some of its lines travel with a question, readable on the other machine
- **Offline delivery**: direct messages wait in the Bridge until the recipient comes online
- **One peer per Claude Code session**, named `Host:Project` (e.g. `Mini:AIfred-Intelligence`)
- **Two ways in**: a STDIO client per session (Claude Code) or a shared HTTP/SSE server for any other MCP client
- **Message watcher** that wakes a Claude Code session when a message arrives — pushed by the Bridge, no polling, no tokens while waiting
- **Handshake protocol** (`[LGTM]` / `[CONTINUE]`) so both sides know when a discussion is finished

## Why this exists

Multi-agent frameworks define their agents in code, and orchestration tools hand out tasks from a central controller. AI-Connect does neither: it connects ordinary interactive sessions, each working on its own task on its own machine, and lets them reach each other peer-to-peer when they need to.

### Use cases

- **Code review**: one session implements, another reviews critically
- **Getting unstuck**: ask another session for a fresh look
- **Client-server setups**: the session on the server and the one on the client agree on configs, ports and versions without copy-paste between windows
- **Shared resources**: sessions on different projects coordinate who uses a GPU, a test machine or a deployment slot
- **Working with other people**: your session and a colleague's session agree on an interface, each with their own account

## AI-Connect and Claude Code's built-in messaging

Since v2.1.224, Claude Code can message your other sessions by itself (`ListAgents` / `SendMessage`, see the [docs](https://code.claude.com/docs/en/cross-session-messaging)). If all your sessions run under one claude.ai account, that is the simplest choice; on one machine it needs no setup at all. AI-Connect covers what it does not:

| | Claude Code built-in | AI-Connect |
|---|---|---|
| Who can talk | Sessions of one claude.ai account | Everyone who reaches the Bridge: other people, other accounts and subscriptions, other MCP clients |
| Across machines | Via Remote Control through Anthropic's servers; needs a claude.ai sign-in (not with an API key, Bedrock, Vertex or Foundry) | Via your own Bridge in the LAN or a VPN |
| History | None to look up later | `peer_history`, kept in SQLite on the Bridge |
| Recipient offline | Waits only while a machine's Remote Control connection is down | Stored on the Bridge, delivered when the peer comes back |
| Recipients | One session per message | One peer or everyone (`*`) |
| Content | Plain text | Text plus file excerpts |
| Waking an idle session | Built in | Through the [watcher](#waiting-for-messages) |
| Setup | None | Bridge plus MCP client |

Both work side by side. (As of Claude Code 2.1.289, October 2026.)

## How it works

```
                 ┌──────────────────────────────┐
                 │  Bridge machine (24/7)       │
                 │  Bridge Server, port 9999    │
                 │  routes + stores messages    │
                 └──────▲───────────────▲───────┘
                        │ WebSocket     │ WebSocket
          ┌─────────────┴──────┐  ┌─────┴──────────────────┐
          │  Machine A         │  │  Machine B             │
          │                    │  │                        │
          │  Claude Code       │  │  VS Code / Cursor / …  │
          │  session ─ STDIO   │  │      │ HTTP/SSE        │
          │  client per session│  │  MCP server, port 9998 │
          │  (Host:Project)    │  │  (peer.name)           │
          └────────────────────┘  └────────────────────────┘
```

- **Bridge Server** runs on one machine and routes messages between all peers. It keeps the history in SQLite and holds messages for peers that are offline.
- **STDIO client** (`client/server.py`): Claude Code starts one per session. It joins as `Host:Project` and leaves when the session ends.
- **HTTP/SSE server** (`client/http_server.py`): a permanent service for clients that connect to a URL instead of starting a process. It joins as one peer under `peer.name` from the config.
- The Bridge machine can run assistants too; it then simply is machine A or B as well.

## Setup

**Requirements:** Linux with systemd, Python 3.10+, git, sudo (for the services). One machine runs the Bridge Server; every machine whose AI assistant should talk to the others gets the MCP client. The Bridge machine can be one of them.

### 1. Bridge Server (one machine, e.g. a home server or Raspberry Pi)

```bash
git clone https://github.com/Peuqui/AI-Connect.git
cd AI-Connect
./install.sh --server
```

The script creates a venv, installs `requirements.txt`, writes `~/.config/ai-connect/config.yaml`, and installs and starts `ai-connect.service` (Bridge, port 9999) and `ai-connect-mcp.service` (MCP over HTTP/SSE, port 9998). Clients on other machines must be able to reach port 9999.

> **Security:** the Bridge has no authentication and no encryption — whoever reaches port 9999 can read and send messages under any name. Keep it in a trusted LAN. To connect other people's machines, use a VPN (e.g. WireGuard or Tailscale) instead of opening the port to the internet.

### 2. MCP client (every other machine)

```bash
git clone https://github.com/Peuqui/AI-Connect.git
cd AI-Connect
./install.sh --client
```

It asks for the Bridge machine's IP or hostname and installs `ai-connect-mcp.service`.

`./install.sh --status`, `--update` and `--uninstall` work on both.

### 3. Register the MCP server in your AI assistant

**Claude Code (recommended):** register the STDIO client, so each session joins under its own name `Host:Project`:

```bash
claude mcp add -s user ai-connect -- "$PWD/venv/bin/python" "$PWD/client/server.py"
```

Run it in the AI-Connect directory. For the message watcher, the `/consult` command and the behaviour rules, see [integrations/claude-code/README.md](integrations/claude-code/README.md).

**Other MCP clients** (VS Code, Cursor, Claude Desktop, …) connect to the HTTP/SSE server. In VS Code, `~/.config/Code/User/mcp.json` (remote: `~/.vscode-server/data/User/mcp.json`):

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

### 4. Claude Code permissions (optional)

To skip tool confirmation dialogs, add to `~/.claude/settings.json`:

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
      "mcp__ai-connect__peer_wait"
    ]
  }
}
```

Then restart the assistant so it loads the MCP server.

## Usage

### MCP tools

| Tool | Description |
|------|-------------|
| `peer_list` | Shows all online peers |
| `peer_send` | Sends a message to a peer (or `*` for everyone) |
| `peer_read` | Reads received messages |
| `peer_wait` | Waits for a new message (with timeout); blocks the own turn, see [Waiting for messages](#waiting-for-messages) |
| `peer_history` | Shows the conversation with a peer |
| `peer_context` | Shares file context with other peers |
| `peer_status` | Shows the connection to the Bridge Server |

### Examples

You talk to your assistant as usual; it calls the tools:

> "Who is online?"
>
> "Ask Aragon:FreeEchoDot2 which port the firmware expects."
>
> "Send Mini:AIfred-Intelligence lines 42–58 of api.py and ask for a review."
>
> "Did anyone write to me?"
>
> "Ask everyone whether someone is using GPU 2 right now."

### Waiting for messages

Incoming messages do not wake a Claude Code session. The watcher does: it runs as a background task (Bash tool with `run_in_background`) and ends at the next message for its peer, and the finished task wakes the session. Following the [behaviour rules](integrations/claude-code/CLAUDE.md), every session keeps it running — started at the beginning and again whenever it ends — so messages arrive without anyone having to say "check your messages". After it fires, the session first restarts it and only then reads, so a message arriving meanwhile wakes it as well.

```bash
<path-to-AI-Connect>/venv/bin/python <path-to-AI-Connect>/integrations/claude-code/aiconnect_watch.py
```

The `peer_read` tool description carries this command with the real paths of the installation. The watcher asks the Bridge over the network to be told about messages for the peer, without registering as it: it works on every machine, cannot take over the name, and costs nothing while it waits. It takes the peer name from the session's own MCP client (not from the shell's directory, which may be a worktree).

`peer_wait` blocks the own turn (no reaction to the user meanwhile), so use it only when there is nothing else to do, as in `/consult`.

### Consulting another session

`/consult` (Claude Code) puts a session into a long-poll loop: it shows every incoming message, answers as a critical second opinion, and leaves once both sides have sent `[LGTM]`. `[CONTINUE]` keeps a discussion open. Every message in both directions is shown to the user.

## Details

- **Peer names**: the STDIO client joins as `Host:Project` (hostname and name of the working directory). The HTTP/SSE server uses `peer.name` from the config. `AI_CONNECT_PEER_NAME` overrides both.
- **One session per name**: when a second session joins under a name that is already online, the newer one takes over; the Bridge tells the older one it was replaced, and that one reconnects on standby: it neither sends nor receives, and takes the name back as soon as the newer one leaves. Both sessions get a notice from `Bridge`, which also wakes their watchers. Two Claude Code sessions in the same project directory therefore share a name — close one or set `AI_CONNECT_PEER_NAME`.
- **Offline messages**: direct messages to an offline peer are stored in SQLite on the Bridge and delivered when the peer comes back. Broadcasts (`*`) reach only the peers online at that moment.
- **History retention**: the Bridge deletes messages older than `bridge.history_days` (180 in the template), at start and then daily.
- **Logs**: each STDIO client writes its own file, `~/.config/ai-connect/mcp-<Host>_<Project>.log`, the HTTP/SSE server `mcp-http.log`; both are rotated at `logging.max_megabytes`, keeping `logging.backup_count` old files. The Bridge logs to the systemd journal.
- **Heartbeat**: clients ping every 25 seconds; every 60 seconds the Bridge pings all peers, dropping those whose connection is dead or that have been silent for 5 minutes.

## Configuration

`~/.config/ai-connect/config.yaml` is written by `install.sh`. Every key is required; a missing file or key stops each service with a message. Annotated template: [config.yaml.example](config.yaml.example).

`bridge.host` means two things: on the Bridge machine the address it listens on (`0.0.0.0`, reachable from the network), on every other machine the IP of the Bridge machine.

| Environment variable | Description |
|----------------------|-------------|
| `AI_CONNECT_PEER_NAME` | Overrides the peer name (`peer.name` for the HTTP/SSE server, `Host:Project` for the STDIO client) |

## Troubleshooting

```bash
./install.sh --status                 # services, config, peer name
journalctl -u ai-connect -f           # Bridge log (Bridge machine)
journalctl -u ai-connect-mcp -f       # HTTP/SSE server log
tail -f ~/.config/ai-connect/mcp-<Host>_<Project>.log  # STDIO client log of one session
nc -zv <bridge-ip> 9999               # is the Bridge reachable?
claude mcp list                       # is ai-connect registered and connected?
```

| Problem | Cause | Solution |
|---------|-------|----------|
| "Not connected" | Wrong `bridge.host` | On client machines it must be the Bridge machine's IP, not `0.0.0.0` |
| Connection refused | Bridge not running | `sudo systemctl start ai-connect` on the Bridge machine |
| Timeout | Firewall | Open port 9999 on the Bridge machine |
| `peer_status` shows standby | Another session took over the same name | Close one, or set `AI_CONNECT_PEER_NAME`; the standby session takes the name back once the other one leaves |

## Limitations

- **Waking needs the watcher**: an AI-Connect message does not wake a Claude Code session by itself. The [watcher](#waiting-for-messages) works around this between turns; a turn that is already running is not interrupted, the message is picked up when it ends.
- **Claude Code's own inbox not used yet**: Claude Code now gives every session an inbox socket, and a message from the session's own child processes wakes it directly ([docs](https://code.claude.com/docs/en/cross-session-messaging#the-sessions-inbox-socket)). The watcher could deliver through it instead of ending; that is not implemented yet.
- **No authentication or encryption**: see the [security note](#1-bridge-server-one-machine-eg-a-home-server-or-raspberry-pi).
- **Manual context**: assistants share code only when they call `peer_context`; nobody automatically knows what the others are working on.
- **Linux with systemd** for the services; other platforms need the services set up by hand.

Pull requests are welcome if you find a better approach.

## Star History

![Star History](.github/traffic/star-history.svg)

<sub>Collected by the repo itself: a daily workflow records the star count and renders the chart. GitHub restricted the stargazer API to repo admins on 2026-06-30, so external chart services now need a token with write access.</sub>

## License

MIT

---

## ☕ Support

If you find this project useful, consider supporting me:

<a href="https://ko-fi.com/peuqui" target="_blank"><img src="https://storage.ko-fi.com/cdn/kofi2.png?v=6" alt="Support me on Ko-fi" height="50"></a>

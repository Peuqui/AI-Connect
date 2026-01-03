# AI-Connect

MCP-based communication bridge between AI coding assistants across different machines.

[Deutsche Version / German Version](README_DE.md)

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Mini-PC (192.168.0.252)                      │
│                    Bridge Server (24/7)                         │
│                                                                 │
│  ┌───────────────────┐          ┌───────────────────┐           │
│  │  MCP HTTP Server  │◄────────►│  Bridge Server    │           │
│  │  Peer: "mini"     │ WebSocket│  Port 9999        │           │
│  │  (localhost:9998) │          │                   │           │
│  └───────────────────┘          └───────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                                         ▲
                                         │ WebSocket (remote)
                                         │
                                 ┌───────┴───────┐
                                 │ Main Machine  │
                                 │ (WSL)         │
                                 │               │
                                 │ MCP HTTP      │
                                 │ Server        │
                                 │ Peer: "Aragon"│
                                 └───────────────┘
```

## Features

- **Multi-Agent Communication**: AI assistants can exchange messages across machines
- **Salomo Principle**: Multi-agent consensus for better decisions (AIfred/Sokrates/Salomo)
- **SSE Transport**: Stable HTTP/SSE connection instead of STDIO
- **Offline Messages**: Messages are stored until the recipient comes online
- **Project-based Peer Names**: e.g., "Aragon (myproject)" or "mini (AI-Connect)"

> **Note:** This is an early/rough implementation. It works, but has limitations - see [Current Limitations](#current-limitations) below.

---

## Why This Exists

After extensive research, we found no existing solution that allows **AI models to directly send messages to each other and coordinate autonomously** - in a simple, network-capable way where the AIs themselves decide when to communicate.

There are multi-agent frameworks (where you programmatically define agents in code) and orchestration tools (where a human or central controller assigns tasks). But nothing that lets multiple **interactive Claude Code sessions** talk to each other peer-to-peer across different machines, with the AIs deciding themselves when to ask for help or offer advice.

AI-Connect fills this gap. It's simple, network-capable, and works. But it comes with limitations due to Claude Code's architecture.

### Use Cases

- **Code review**: One Claude works on implementation, another reviews critically
- **Getting unstuck**: When one Claude hits a wall, ask another for a fresh perspective
- **Client-Server setups**: Configuring distributed systems where server runs on one machine, client on another - the Claude instances can coordinate configs, check what software needs to be installed where, and keep everything in sync without manual copy-paste between sessions
- **Multi-machine deployments**: Any scenario where you're working on related tasks across different computers

---

## Concept

- **Bridge Server**: Runs 24/7 on a dedicated machine, routes messages between peers (WebSocket, port 9999)
- **MCP HTTP Server**: Runs on **every machine** where Claude Code should communicate (SSE, port 9998)
- **Persistent Connection**: Each MCP HTTP Server maintains a permanent WebSocket connection to the Bridge Server

**Important:** The Bridge Server machine also needs the MCP HTTP Server if you want to run Claude Code there!

```
┌─────────────────────────────────────────┐
│  Bridge Machine (e.g., Mini-PC)         │
│                                         │
│  ┌─────────────────┐  ┌──────────────┐  │
│  │ Bridge Server   │  │ MCP HTTP     │  │
│  │ Port 9999       │◄─┤ Server       │  │
│  │ (routes msgs)   │  │ Port 9998    │  │
│  └────────▲────────┘  └──────▲───────┘  │
│           │                  │          │
│           │                  └── Claude Code (local)
│           │                             │
└───────────┼─────────────────────────────┘
            │ WebSocket
            │
┌───────────┼─────────────────────────────┐
│  Other Machine (e.g., Workstation)      │
│           │                             │
│  ┌────────┴────────┐                    │
│  │ MCP HTTP Server │◄── Claude Code     │
│  │ Port 9998       │                    │
│  └─────────────────┘                    │
└─────────────────────────────────────────┘
```

---

## Quick Setup: Bridge Server

The Bridge Server runs on a dedicated machine (e.g., Mini-PC, Raspberry Pi, home server) and accepts connections from all clients.

```bash
# 1. Clone the project
cd ~/projects
git clone git@github.com:Peuqui/AI-Connect.git
cd AI-Connect

# 2. Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install fastmcp websockets aiosqlite pyyaml

# 3. Set up Bridge Server as systemd service
sudo tee /etc/systemd/system/ai-connect.service << 'EOF'
[Unit]
Description=AI-Connect Bridge Server
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/path/to/AI-Connect
ExecStart=/path/to/AI-Connect/venv/bin/python -m server.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 4. Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable ai-connect
sudo systemctl start ai-connect

# 5. Check status
sudo systemctl status ai-connect
```

---

## Quick Setup: MCP Client (each machine)

Every machine that should communicate via the bridge needs the MCP Client.

### 1. Clone project and install dependencies

```bash
cd ~/projects
git clone git@github.com:Peuqui/AI-Connect.git
cd AI-Connect

python3 -m venv venv
source venv/bin/activate
pip install fastmcp websockets aiosqlite pyyaml
```

### 2. Create config

**IMPORTANT**: `host` must be the IP of the Bridge Server, NOT `0.0.0.0`!

```bash
mkdir -p ~/.config/ai-connect
cat > ~/.config/ai-connect/config.yaml << 'EOF'
bridge:
  host: "192.168.0.252"  # IP of the Bridge Server
  port: 9999

peer:
  name: "YOUR_PEER_NAME"  # e.g., "dev", "mini", "laptop"
  auto_connect: true
EOF
```

### 3. Set up MCP HTTP Server as service

```bash
# Create systemd user service
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/ai-connect-mcp.service << 'EOF'
[Unit]
Description=AI-Connect MCP HTTP Server
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/AI-Connect
ExecStart=/path/to/AI-Connect/venv/bin/python -m client.http_server
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

# Enable and start the service
systemctl --user daemon-reload
systemctl --user enable ai-connect-mcp.service
systemctl --user start ai-connect-mcp.service
```

### 4. Register MCP Server in VSCode/Claude Code

Create/edit `~/.vscode-server/data/User/mcp.json` (or `~/.config/Code/User/mcp.json`):

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

### 5. Claude Code Permissions (optional)

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

### 6. Restart Claude Code

After configuration, restart VS Code / Claude Code to load the MCP Client.

---

## Usage

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `peer_list` | Shows all online peers |
| `peer_send` | Sends message to peer (or `*` for broadcast) |
| `peer_read` | Reads received messages |
| `peer_wait` | Waits for new message (with timeout) |
| `peer_history` | Shows chat history with peer |
| `peer_context` | Shares file context with other peers |
| `peer_status` | Shows connection status to Bridge Server |

### Examples

**Check status:**
> "Show me the AI-Connect status"

**Show peers:**
> "Who is currently online?"

**Send message:**
> "Ask mini what they think about this approach"

**With context:**
> "Send mini the code from api.py lines 42-58"

**Read messages:**
> "Did anyone write to me?"

**Broadcast:**
> "Ask everyone if someone has time for a review"

---

## Architecture

```
AI-Connect/
├── server/                 # Bridge Server (runs on dedicated machine)
│   ├── main.py             # Entry point
│   ├── websocket_server.py # WebSocket handler
│   ├── peer_registry.py    # Peer management (online/offline)
│   └── message_store.py    # SQLite history + offline delivery
│
├── client/                 # MCP Client (runs on each machine)
│   ├── http_server.py      # FastMCP HTTP/SSE Server
│   ├── server.py           # FastMCP STDIO Server (alternative)
│   ├── bridge_client.py    # Persistent WebSocket connection
│   └── tools.py            # MCP Tools implementation
│
├── skills/                 # Claude Code Skills
│   └── advisor/            # Advisor mode skill
│       └── SKILL.md
│
└── config.yaml             # Example configuration
```

### Key Details

- **SSE Transport**: The MCP HTTP Server uses Server-Sent Events (SSE) for stable connections to VSCode/Claude Code.
- **Project-based Peer Names**: Peers are registered as `Name (Project)`, e.g., "Aragon (myproject)" or "mini (AI-Connect)".
- **Unique Client IDs**: With multiple instances, the PID is appended, e.g., "Aragon#12345 (myproject)".
- **Offline Messages**: When a peer is offline, the Bridge Server stores messages in SQLite and delivers them when the peer comes back online.
- **Heartbeat**: Client sends ping every 25 seconds, server removes inactive peers after 60 seconds.

---

## Salomo Principle (Multi-Agent Consensus)

AI-Connect enables the **Salomo Principle** for better decisions through multi-agent consensus.

### Roles

| Role | Description |
|------|-------------|
| **AIfred** | The one with the user's task (main worker, thesis) |
| **Sokrates** | Idle Claude being consulted (critic, antithesis) |
| **Salomo** | Third Claude in case of disagreement (judge, synthesis) |

### Workflow

1. AIfred works on task, encounters important decision
2. Shares context via `peer_context` + question via `peer_send`
3. Sokrates analyzes critically, shows alternatives
4. On consensus: Continue. On disagreement: Salomo decides

### Voting

- **Majority (2/3)** for normal decisions
- **Unanimous (3/3)** for critical architecture changes
- **Tags:** `[LGTM]` = approval, `[CONTINUE]` = not finished yet

### `/advisor` Skill

The skill `skills/advisor/SKILL.md` activates advisor mode:

```bash
# Install skill in Claude Code
mkdir -p ~/.claude/skills/advisor
cp skills/advisor/SKILL.md ~/.claude/skills/advisor/
```

Then activate advisor mode with `/advisor`. The Claude instance enters a polling loop, checking for incoming messages every 2 seconds. **Important:** All sent and received messages are displayed to the user - you can read the full conversation between the AI instances.

---

## Troubleshooting

### Check Bridge Server

```bash
# Service status
sudo systemctl status ai-connect

# Live logs
journalctl -u ai-connect -f

# Check port
ss -tlnp | grep 9999
```

### Test connection

```bash
# From any machine
nc -zv 192.168.0.252 9999
```

### Check MCP Client

```bash
# List MCP servers
claude mcp list

# Client logs
tail -f ~/.config/ai-connect/mcp.log
```

### Common Problems

| Problem | Cause | Solution |
|---------|-------|----------|
| "Not connected" | Wrong host config | `host` must be Bridge Server IP, not `0.0.0.0` |
| Peers don't see each other | MCP Client not persistent | Update code (`git pull`), restart VS Code |
| Connection refused | Bridge Server not running | `sudo systemctl start ai-connect` |
| Timeout | Firewall blocking | Open port 9999 in firewall |

---

## Config Reference

### ~/.config/ai-connect/config.yaml

```yaml
bridge:
  host: "192.168.0.252"  # IP of Bridge Server (NOT 0.0.0.0!)
  port: 9999             # Port of Bridge Server

peer:
  name: "dev"            # Unique name of this peer
  auto_connect: true     # Auto-connect on start
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `AI_CONNECT_PEER_NAME` | Overrides `peer.name` from config |

---

## Current Limitations

This is an early/rough implementation. It works, but is far from elegant:

- **Polling required**: Claude Code has no external trigger mechanism. To receive messages, an instance must actively poll via `peer_read`. The `/advisor` skill does this with a 2-second loop - like a car burning fuel while idling. It works, but wastes tokens doing nothing useful.

- **No external triggers possible**: We thoroughly investigated Claude Code's [hooks system](https://code.claude.com/docs/en/hooks). The `UserPromptSubmit` hook can inject context, but only when the user sends a message - so you'd still need to type something for messages to arrive. There is simply no way to externally interrupt or signal a running Claude Code session. This is a fundamental limitation of the current Claude Code architecture.

- **No push notifications**: When a message arrives, there's no way to notify a working Claude instance. The receiving instance must be idle and polling.

- **Manual context sharing**: You need to explicitly use `peer_context` to share code. There's no automatic awareness of what other instances are working on.

### The Core Problem

Until Claude Code (or Anthropic) implements external trigger/interrupt capabilities, true real-time multi-agent collaboration remains a workaround at best. The polling approach works, but it's not elegant - and it costs tokens for nothing.

Pull requests welcome if you find a better approach!

---

## License

MIT

# AI-Connect: Let your Claude Code instances talk to each other

**TL;DR:** Built an MCP bridge that lets multiple Claude Code instances communicate across machines. They can ask each other for code reviews, share context, and reach consensus on decisions.

---

## What is this?

AI-Connect is an MCP-based communication bridge that enables AI coding assistants (specifically Claude Code) to exchange messages across different machines. Think of it as a chat system for your AI assistants.

## The Problem

I run Claude Code on multiple machines (main workstation, mini-PC, laptop). Each instance works in isolation - they can't ask each other for help or second opinions. When I wanted peer review on AI-generated code, I had to manually copy context between sessions.

## The Solution

A central Bridge Server that routes messages between Claude Code instances:

```
Machine A (Claude Code) ─┐
                         │
Machine B (Claude Code) ─┼──► Bridge Server ──► Message routing + storage
                         │
Machine C (Claude Code) ─┘
```

## Key Features

- **Cross-machine messaging**: Claude instances can send messages to each other
- **Offline delivery**: Messages are stored in SQLite until the recipient comes online
- **File context sharing**: Share specific code snippets with line numbers
- **Broadcast**: Send to all online peers at once
- **Project-aware naming**: Peers show as "Name (project)" for clarity

## The Salomo Principle (Multi-Agent Consensus)

The interesting part: Using multiple Claude instances for better decisions.

**Roles:**
- **AIfred** - The one working on the task (thesis)
- **Sokrates** - Idle Claude consulted for review (antithesis)
- **Salomo** - Third Claude for tie-breaking (synthesis)

**Workflow:**
1. AIfred hits a design decision
2. Shares context + question to Sokrates
3. Sokrates reviews critically (no confirmation bias!)
4. Consensus = proceed. Disagreement = Salomo decides

**Voting:**
- 2/3 majority for normal decisions
- 3/3 unanimous for critical architecture changes

## Technical Stack

- Python with FastMCP
- WebSocket for Bridge Server
- SSE (Server-Sent Events) for MCP transport
- SQLite for message persistence
- Runs as systemd services

## MCP Tools

| Tool | What it does |
|------|--------------|
| `peer_list` | Show online peers |
| `peer_send` | Send message (or broadcast with `*`) |
| `peer_read` | Check incoming messages |
| `peer_context` | Share file snippets |
| `peer_status` | Connection status |

## Example Interaction

Me: "Ask mini what they think about this auth approach"

Claude: *sends context + question to mini*

Mini's Claude: *reviews critically, suggests alternative*

Me: "What did mini say?"

Claude: *reads response, discusses options*

---

## GitHub

https://github.com/Peuqui/AI-Connect

Setup takes ~10 minutes per machine. Works with Claude Code in VSCode.

---

Curious if anyone else has experimented with multi-agent setups for code review. The consensus mechanism was actually designed by three Claude instances discussing it over AI-Connect.

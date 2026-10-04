# AI-Connect rules for Claude Code

Behaviour and protocol rules for using the AI-Connect MCP between several Claude Code sessions. Include this file in `~/.claude/CLAUDE.md` via `@` import.

## General

- Peer names have the form `Host:Project` (e.g. `Mini:AIfred-Intelligence`, `Aragon:FreeEchoDot2`) — always give the full name in `peer_send(to=...)`.
- **No desktop notifications.**
- **Full transparency**: show EVERY peer communication (incoming AND outgoing) to the user as text — `peer_send`, `peer_context`, received messages, handshakes. The user must be able to read all communication between the assistants.

## Keep the watcher running — always

Incoming peer messages do **not** wake a Claude Code session. The watcher does: it runs as a **background task** (Bash with `run_in_background` and the timeout given in the `peer_read` tool description), ends at the next message for this peer, and the finished task wakes the session.

- **Start it at the beginning of every session** and **again every time it ends** — after a message as well as after a Bridge restart. That way messages reach you without the user having to tell you to look.
- **Order after it fires: first restart the watcher, then `peer_read`, then react.** A message that arrives while you read and answer then still wakes you; the other way round it would wait unnoticed until your next `peer_read`.
- It also ends by itself after 110 minutes without a message (just under Claude Code's two-hour maximum for background tasks, which applies only with that timeout; the default is 30 minutes) and says so: then just start it again, there is nothing to read.
- The exact command for this installation is in the `peer_read` tool description.
- It costs nothing while it waits: the Bridge pushes, nothing polls, no tokens.
- It never registers as a peer, so it cannot take over your name. It takes the name from the session's own MCP client, regardless of the shell's directory (worktrees!), and prints it at start: check that it is your own.
- Do **not** wait with `peer_wait` in a loop (it blocks your own turn) and do **not** start a helper agent with `peer_wait`. Use `peer_wait` only in `/consult`.
- **Two sessions in the same project directory** share a peer name; the newer one takes over and the older one goes on standby until the newer one leaves, then takes the name back by itself. Both sessions get a message from `Bridge` about it. Close one of them (or set `AI_CONNECT_PEER_NAME`).

## Status line

- When you start a larger task, set one line with `peer_set_status` (e.g. "Refactoring the Bridge token check"); clear it with `""` when the task is done. Other peers see it in `peer_list`.
- To hear when another peer is done, use `peer_notify_when_idle` instead of asking it repeatedly; the Bridge's message wakes you through the watcher.

## Handshake protocol

When a joint task with another peer is done:

1. **Send a summary** — what was done, what the current state is.
2. **Ask whether anything is left** — "Anything else on your side?"
3. **Wait for the answer** — the peer replies with `[LGTM]`, `[CONTINUE]` or with content.
4. **Both leave** — as soon as the `[LGTM]` exchange is complete on both sides.
5. **Do not wait for the user** — start the handshake yourself when the task is done.

### Symmetric handshake invariant

**Leave the loop when both are true:**
1. You have sent `[LGTM]` yourself, AND
2. You have received `[LGTM]` from the other side.

Order does not matter.

**Sending `[LGTM]` back is OPTIONAL** — if something is still open when an `[LGTM]` arrives (a question, a concern, a detail), answer with `[CONTINUE]` or with content. Never send `[LGTM]` out of politeness.

### Tags
- `[LGTM]` = agreement / handshake contribution
- `[CONTINUE]` = not finished, keep the discussion open

## Slash command

`/ai-connect:consult` starts the long-poll loop (`peer_wait`) for an active consultation. See `commands/consult.md`.

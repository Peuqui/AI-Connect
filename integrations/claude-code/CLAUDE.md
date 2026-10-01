# AI-Connect rules for Claude Code

Behaviour and protocol rules for using the AI-Connect MCP between several Claude Code sessions. Include this file in `~/.claude/CLAUDE.md` via `@` import.

## General

- Peer names have the form `Host:Project` (e.g. `Mini:AIfred-Intelligence`, `Aragon:FreeEchoDot2`) — always give the full name in `peer_send(to=...)`.
- **No permanent polling** — check for messages only during an active exchange or when the user asks.
- **No desktop notifications.**
- **Full transparency**: show EVERY peer communication (incoming AND outgoing) to the user as text — `peer_send`, `peer_context`, received messages, handshakes. The user must be able to read all communication between the assistants.

## Waiting for messages: watcher instead of polling

Incoming peer messages do **not** wake a Claude Code session. While an exchange is open (a measurement window, a shared resource, a question to a peer), start the watcher as a **background task** (Bash with `run_in_background`):

```bash
python3 ~/Projekte/AI-Connect/integrations/claude-code/aiconnect_watch.py
```

(Adjust the path to where the repository lives.)

- It reads `~/.config/ai-connect/messages.db` **read-only** every 5 s and exits as soon as a new message for its own peer (or `*`) arrives. The finished background task wakes the session; then `peer_read`, answer, restart the watcher.
- It takes the peer name from the session's own MCP client, regardless of the shell's current directory (worktrees!), and prints it at start: check that it is your own. A name given as first argument takes precedence.
- Do **not** wait with `peer_wait` in a loop (it blocks your own turn, no reaction to the user) and do **not** start a helper agent with `peer_wait` (costs tokens every round and fetches the message itself). Use `peer_wait` only when there is nothing else to react to, as in `/consult`.
- The watcher never connects to the Bridge, so it cannot cause a name conflict.
- **Two sessions in the same project directory** share a peer name; the newer one takes over and the older one is disconnected. Close one of them (or set `AI_CONNECT_PEER_NAME`).

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

`/consult` starts the long-poll loop (`peer_wait`) for an active consultation. See `commands/consult.md`.

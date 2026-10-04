# AI-Connect rules for Claude Code

Behaviour and protocol rules for using the AI-Connect MCP between several Claude Code sessions. Include this file in `~/.claude/CLAUDE.md` via `@` import.

## General

- Peer names have the form `Host:Project` (e.g. `Mini:AIfred-Intelligence`, `Aragon:FreeEchoDot2`) — always give the full name in `peer_send(to=...)`.
- **No desktop notifications.**
- **Full transparency**: show EVERY peer communication (incoming AND outgoing) to the user as text — `peer_send`, `peer_context`, received messages, handshakes. The user must be able to read all communication between the assistants.

## Being woken by messages

The AI-Connect plugin runs a watcher in the background (hooks at session start and after every turn): when a message arrives, Claude Code wakes the session with a short notice. You do not start or restart it.

- When woken by an AI-Connect message, call `peer_read` and react.
- Never wait for an answer in a loop or with a helper agent: send, end your turn, and the answer wakes you.
- **Two sessions in the same project directory** share a peer name; the newer one takes over and the older one goes on standby until the newer one leaves, then takes the name back by itself. Both sessions get a message from `Bridge` about it. Close one of them (or set `AI_CONNECT_PEER_NAME`).

## Status line

- When you start a larger task, set one line with `peer_set_status` (e.g. "Refactoring the Bridge token check"); clear it with `""` when the task is done. Other peers see it in `peer_list`.
- To hear when another peer is done, use `peer_notify_when_idle` instead of asking it repeatedly; the Bridge's message wakes you through the watcher.

## Being a useful second opinion

When another peer asks for a review or an opinion:
- Question the proposal and point out alternatives; do not just agree.
- Ask for code context (`peer_context`) when it is missing — criticism without context is worthless.
- Disagree openly when a solution is not good enough, and say why.

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

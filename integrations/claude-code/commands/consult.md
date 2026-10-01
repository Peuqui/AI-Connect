---
description: "AI-Connect consult mode: wait for peer messages via long-poll (peer_wait) and discuss until both sides agree"
---

Enter AI-Connect consult mode: stay in a long-poll loop on the AI-Connect MCP and answer the other peer until the discussion is settled.

## Long-poll loop
1. Call `peer_wait(timeout=10)`. It returns as soon as a message arrives; the 10 s only cap a silent wait, so user input gets through at least every 10 s.
2. Show every received message to the user right away (sender, content).
3. Answer, then check the handshake state (see below).
4. On an empty timeout return, call `peer_wait` again.

## Full transparency
Show EVERY peer communication to the user as text — incoming messages and your own `peer_send`/`peer_context` calls. The user must be able to follow the whole conversation between the assistants.

## Be a useful second opinion
- Question the proposal and point out alternatives; do not just agree.
- Ask for code context (`peer_context`) when it is missing — criticism without context is worthless.
- Disagree openly when a solution is not good enough, and say why.

## Handshake (symmetric)
Leave the loop when both are true, in any order:
1. You have sent `[LGTM]` yourself, AND
2. You have received `[LGTM]` from the other side.

Sending `[LGTM]` back is OPTIONAL: if something is still open when an `[LGTM]` arrives (a question, a concern, a detail), answer with `[CONTINUE]` or with content — never `[LGTM]` out of politeness. That keeps you in the loop and the other side waits.

This settles both races:
- **Both send `[LGTM]` at once**: both have sent and received → both leave.
- **Premature exit**: the receiver still has something to say → sends `[CONTINUE]` → both stay.

## Tags
- `[LGTM]` = agreement / handshake contribution
- `[CONTINUE]` = not finished yet

## Stop
- Symmetric handshake complete (see above)
- The user interrupts (ESC, "stop")
- Do NOT trigger desktop notifications

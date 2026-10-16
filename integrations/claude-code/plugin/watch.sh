#!/bin/sh
# Starts the AI-Connect watcher with this installation's venv. Claude Code runs
# hooks in a POSIX shell on Linux and in Git Bash on Windows, where the venv
# keeps its Python under Scripts/ instead of bin/.
REPO="$(dirname "$0")/../../.."

# Non-interactive sessions (claude -p, Agent SDK, the Code tab of Claude
# Desktop) wait for SessionStart hooks to finish despite asyncRewake, so the
# watcher would block the session from starting. The Code tab is woken at once
# instead (asyncRewake, exit 2): a first turn runs, also when a session is
# resumed after Claude Desktop restarted, and the Stop hook starts the watcher
# after it. claude -p and the SDK get no extra turn; their Stop hook starts it.
# CLAUDE_ENV_FILE is set for SessionStart hooks only.
if [ -n "$CLAUDE_ENV_FILE" ]; then
    case "$CLAUDE_CODE_ENTRYPOINT" in
        claude-desktop)
            echo "AI-Connect: session started. Read your messages with peer_read."
            exit 2 ;;
        sdk-*) exit 0 ;;
    esac
fi
if [ -x "$REPO/venv/bin/python" ]; then
    PYTHON="$REPO/venv/bin/python"
else
    PYTHON="$REPO/venv/Scripts/python.exe"
fi
exec "$PYTHON" "$REPO/integrations/claude-code/aiconnect_watch.py"

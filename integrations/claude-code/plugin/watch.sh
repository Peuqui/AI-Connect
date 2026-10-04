#!/bin/sh
# Starts the AI-Connect watcher with this installation's venv. Claude Code runs
# hooks in a POSIX shell on Linux and in Git Bash on Windows, where the venv
# keeps its Python under Scripts/ instead of bin/.
REPO="$(dirname "$0")/../../.."
if [ -x "$REPO/venv/bin/python" ]; then
    PYTHON="$REPO/venv/bin/python"
else
    PYTHON="$REPO/venv/Scripts/python.exe"
fi
exec "$PYTHON" "$REPO/integrations/claude-code/aiconnect_watch.py"

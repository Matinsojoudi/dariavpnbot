#!/bin/bash
# Start Daria VPN Bot inside a tmux session (used by systemd)
set -euo pipefail

SESSION="dariavpnbot"
WORKDIR="/root/VPN Bots/dariavpnbot"
PYTHON="$WORKDIR/venv/bin/python3"

if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "tmux session '$SESSION' already running"
    exit 0
fi

tmux new-session -d -s "$SESSION" -c "$WORKDIR" "$PYTHON" main.py
echo "Started bot in tmux session: $SESSION"

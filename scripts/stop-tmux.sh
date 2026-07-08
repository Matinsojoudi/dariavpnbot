#!/bin/bash
# Stop Daria VPN Bot tmux session
set -euo pipefail

SESSION="dariavpnbot"

if tmux has-session -t "$SESSION" 2>/dev/null; then
    tmux kill-session -t "$SESSION"
    echo "Stopped tmux session: $SESSION"
else
    echo "No tmux session: $SESSION"
fi

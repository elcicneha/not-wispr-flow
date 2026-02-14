#!/bin/bash
#
# Simple background runner for Whispr
# Alternative to LaunchAgent for users who don't need auto-start
#

# Get absolute paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python3"
LOG_DIR="$HOME/Library/Logs/Whispr"

# Check if already running
if pgrep -f "whispr_clone.py" > /dev/null; then
    echo "Whispr is already running!"
    echo "Process ID: $(pgrep -f whispr_clone.py)"
    echo ""
    echo "To stop: ./scripts/stop_background.sh"
    exit 1
fi

# Create log directory
mkdir -p "$LOG_DIR"

# Run in background with nohup
nohup "$VENV_PYTHON" "$PROJECT_DIR/whispr_clone.py" \
    > "$LOG_DIR/stdout.log" 2> "$LOG_DIR/stderr.log" &

PID=$!

echo "Whispr started in background (PID: $PID)"
echo "Logs: $LOG_DIR/whispr.log"
echo ""
echo "To stop: ./scripts/stop_background.sh"
echo "Or use: kill $PID"
echo ""
echo "View logs: tail -f $LOG_DIR/whispr.log"

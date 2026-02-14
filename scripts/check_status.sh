#!/bin/bash
#
# Whispr Service Status Checker
# Displays current service status, logs, and diagnostics
#

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Paths
LOG_FILE="$HOME/Library/Logs/Whispr/whispr.log"
STDERR_LOG="$HOME/Library/Logs/Whispr/stderr.log"

print_header() {
    echo ""
    echo "Whispr Service Status"
    echo "===================="
    echo ""
}

check_service_status() {
    if launchctl list 2>/dev/null | grep -q "com.whispr.dictation"; then
        # Get PID
        PID=$(launchctl list 2>/dev/null | grep "com.whispr.dictation" | awk '{print $1}')

        echo -e "Status:      ${GREEN}Running ✓${NC}"
        echo -e "Process ID:  $PID"

        # Get uptime and resource usage
        if [ "$PID" != "-" ] && [ -n "$PID" ]; then
            START_TIME=$(ps -p "$PID" -o lstart= 2>/dev/null || echo "Unknown")
            echo -e "Started:     $START_TIME"

            # Get resource usage
            CPU=$(ps -p "$PID" -o %cpu= 2>/dev/null | tr -d ' ' || echo "N/A")
            MEM=$(ps -p "$PID" -o rss= 2>/dev/null | awk '{printf "%.1f MB", $1/1024}' || echo "N/A")
            echo -e "CPU:         $CPU%"
            echo -e "Memory:      $MEM"
        fi
    else
        echo -e "Status:      ${RED}Not Running ✗${NC}"

        # Check if plist exists
        if [ -f "$HOME/Library/LaunchAgents/com.whispr.dictation.plist" ]; then
            echo -e "             ${YELLOW}(Installed but not loaded)${NC}"
            echo ""
            echo "To start: launchctl load ~/Library/LaunchAgents/com.whispr.dictation.plist"
        else
            echo -e "             ${YELLOW}(Not installed)${NC}"
            echo ""
            echo "To install: ./scripts/install_service.sh"
        fi

        return 1
    fi
}

show_recent_logs() {
    echo ""
    echo "Recent Activity (last 10 entries):"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if [ -f "$LOG_FILE" ]; then
        tail -10 "$LOG_FILE" | while read line; do
            # Colorize based on log level
            if [[ $line =~ "ERROR" ]]; then
                echo -e "${RED}$line${NC}"
            elif [[ $line =~ "WARNING" ]]; then
                echo -e "${YELLOW}$line${NC}"
            elif [[ $line =~ "Transcription:" ]]; then
                echo -e "${GREEN}$line${NC}"
            else
                echo "$line"
            fi
        done
    else
        echo "No log file found at: $LOG_FILE"
    fi

    # Check for errors
    if [ -f "$STDERR_LOG" ] && [ -s "$STDERR_LOG" ]; then
        echo ""
        echo -e "${RED}Recent Errors:${NC}"
        tail -5 "$STDERR_LOG"
    fi
}

print_footer() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Full logs: $LOG_FILE"
    echo "View logs: tail -f $LOG_FILE"
    echo ""
}

main() {
    print_header
    check_service_status
    STATUS=$?

    if [ $STATUS -eq 0 ]; then
        show_recent_logs
        print_footer
    fi

    exit $STATUS
}

main

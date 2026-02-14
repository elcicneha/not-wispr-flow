#!/bin/bash
#
# Whispr Service Uninstaller
# Removes Whispr LaunchAgent and optionally cleans up logs
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Paths
PLIST_FILE="$HOME/Library/LaunchAgents/com.whispr.dictation.plist"
LOG_DIR="$HOME/Library/Logs/Whispr"

log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }
log_info() { echo -e "${YELLOW}[i]${NC} $1"; }

print_header() {
    echo ""
    echo "Whispr Service Uninstaller"
    echo "=========================="
    echo ""
}

unload_service() {
    log_info "Checking if service is loaded..."

    if launchctl list 2>/dev/null | grep -q "com.whispr.dictation"; then
        log_info "Unloading service..."
        launchctl unload "$PLIST_FILE" 2>/dev/null || true
        sleep 1
        log_success "Service unloaded"
    else
        log_info "Service is not currently loaded"
    fi
}

remove_plist() {
    if [ -f "$PLIST_FILE" ]; then
        log_info "Removing plist file..."

        # Backup to /tmp
        cp "$PLIST_FILE" "/tmp/com.whispr.dictation.plist.backup"
        rm "$PLIST_FILE"

        log_success "Removed: $PLIST_FILE"
        log_info "Backup saved to: /tmp/com.whispr.dictation.plist.backup"
    else
        log_info "Plist file not found (already removed)"
    fi
}

cleanup_logs() {
    if [ -d "$LOG_DIR" ]; then
        echo ""
        log_info "Found log directory: $LOG_DIR"

        # Show log sizes
        echo ""
        du -sh "$LOG_DIR"/* 2>/dev/null | while read size file; do
            echo "  - $(basename "$file") ($size)"
        done

        echo ""
        read -p "Remove log files? (y/n) " -n 1 -r
        echo

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$LOG_DIR"
            log_success "Removed log directory"
        else
            log_info "Keeping log files"
        fi
    else
        log_info "No log directory found"
    fi
}

print_summary() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}Whispr service has been uninstalled${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "To reinstall, run:"
    echo "  ./scripts/install_service.sh"
    echo ""
}

main() {
    print_header
    unload_service
    remove_plist
    cleanup_logs
    print_summary
}

main

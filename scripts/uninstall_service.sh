#!/bin/bash
#
# Whispr Uninstaller
# Full cleanup: kills processes, removes app, logs, and build artifacts
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLIST_FILE="$HOME/Library/LaunchAgents/com.whispr.dictation.plist"
APP_INSTALL_PATH="/Applications/Whispr.app"
LOG_DIR="$HOME/Library/Logs/Whispr"

log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }
log_info() { echo -e "${YELLOW}[i]${NC} $1"; }

print_header() {
    echo ""
    echo "Whispr Uninstaller"
    echo "=================="
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

kill_processes() {
    log_info "Checking for running Whispr processes..."

    local whispr_pids
    whispr_pids=$(pgrep -fx ".*/Whispr\.app/Contents/MacOS/Whispr" 2>/dev/null) || true
    if [ -n "$whispr_pids" ]; then
        echo "$whispr_pids" | xargs kill 2>/dev/null || true
        sleep 1
        log_success "Killed running Whispr processes"
    else
        log_info "No running processes found"
    fi
}

remove_plist() {
    if [ -f "$PLIST_FILE" ]; then
        rm "$PLIST_FILE"
        log_success "Removed: $PLIST_FILE"
    else
        log_info "Plist file not found (already removed)"
    fi
}

remove_app() {
    if [ -d "$APP_INSTALL_PATH" ]; then
        rm -rf "$APP_INSTALL_PATH"
        log_success "Removed: $APP_INSTALL_PATH"
    else
        log_info "App bundle not found (already removed)"
    fi
}

cleanup_logs() {
    if [ -d "$LOG_DIR" ]; then
        rm -rf "$LOG_DIR"
        log_success "Removed: $LOG_DIR"
    else
        log_info "No log directory found"
    fi
}

cleanup_build_artifacts() {
    local removed=false

    if [ -d "$PROJECT_DIR/build" ]; then
        rm -rf "$PROJECT_DIR/build"
        removed=true
    fi

    if [ -d "$PROJECT_DIR/dist" ]; then
        rm -rf "$PROJECT_DIR/dist"
        removed=true
    fi

    if [ "$removed" = true ]; then
        log_success "Removed: build/ and dist/"
    else
        log_info "No build artifacts found"
    fi
}

print_summary() {
    echo ""
    echo -e "${GREEN}Whispr has been completely uninstalled${NC}"
    echo ""
    echo "To reinstall, run:"
    echo "  ./scripts/install_service.sh"
    echo ""
}

main() {
    print_header
    unload_service
    kill_processes
    remove_plist
    remove_app
    cleanup_logs
    cleanup_build_artifacts
    print_summary
}

main

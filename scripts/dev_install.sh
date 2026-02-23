#!/bin/bash
#
# Not Wispr Flow Fast Development Installer
# Quickly updates Python files in existing app bundle without full rebuild
# Use this for rapid iteration during development
#
# For first install or major changes, use: ./scripts/install_service.sh
#

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_INSTALL_PATH="/Applications/Not Wispr Flow.app"
PYTHON_CODE_PATH="$APP_INSTALL_PATH/Contents/Resources"

# Functions
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }
log_info() { echo -e "${BLUE}[i]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[!]${NC} $1"; }

print_header() {
    echo ""
    echo "Not Wispr Flow Fast Dev Installer"
    echo "=================================="
    echo ""
}

# Check if app bundle exists
check_app_exists() {
    if [ ! -d "$APP_INSTALL_PATH" ]; then
        log_error "App bundle not found at: $APP_INSTALL_PATH"
        log_info "Run full install first: ./scripts/install_service.sh"
        exit 1
    fi
    log_success "Found app bundle"
}

# Kill running app
stop_app() {
    local app_pids
    app_pids=$(pgrep -fx ".*/Not Wispr Flow\.app/Contents/MacOS/Not Wispr Flow" 2>/dev/null) || true
    if [ -n "$app_pids" ]; then
        log_info "Stopping running app..."
        echo "$app_pids" | xargs kill 2>/dev/null || true
        sleep 0.5
        log_success "App stopped"
    fi
}

# Copy Python files
update_python_files() {
    log_info "Updating Python files..."

    # Copy main.py
    if [ -f "$PROJECT_DIR/main.py" ]; then
        cp "$PROJECT_DIR/main.py" "$PYTHON_CODE_PATH/main.py"
        log_success "Updated main.py"
    fi

    # Copy config.py
    if [ -f "$PROJECT_DIR/config.py" ]; then
        cp "$PROJECT_DIR/config.py" "$PYTHON_CODE_PATH/config.py"
        log_success "Updated config.py"
    fi

    # Copy any other .py files in root
    for pyfile in "$PROJECT_DIR"/*.py; do
        if [ -f "$pyfile" ]; then
            filename=$(basename "$pyfile")
            # Skip setup.py
            if [ "$filename" != "setup.py" ]; then
                cp "$pyfile" "$PYTHON_CODE_PATH/$filename"
                log_success "Updated $filename"
            fi
        fi
    done
}

# Start app
start_app() {
    log_info "Starting app..."
    open "$APP_INSTALL_PATH"
    sleep 1
    log_success "App started"
}

print_summary() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}Development update complete!${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Changes applied in ~1 second (vs ~30+ seconds for full rebuild)"
    echo ""
    echo -e "${YELLOW}Note:${NC} This only updates .py files. For dependency changes, run:"
    echo "  ./scripts/install_service.sh"
    echo ""
    echo "Logs: ~/Library/Logs/NotWisprFlow/notwisprflow.log"
    echo ""
}

# Main execution
main() {
    print_header
    check_app_exists
    stop_app
    update_python_files
    start_app
    print_summary
}

main

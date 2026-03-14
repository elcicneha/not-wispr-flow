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
VENV_PYTHON="$PROJECT_DIR/venv/bin/python3"

# Detect Python version for zip file name
PYTHON_VERSION=$("$VENV_PYTHON" -c 'import sys; print(f"{sys.version_info.major}{sys.version_info.minor}")')
PYTHON_ZIP="$PYTHON_CODE_PATH/lib/python${PYTHON_VERSION}.zip"

# Project Python files (everything except setup.py)
PROJECT_FILES=(config.py transcription.py llm_processor.py post_processing.py media_control.py)

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
    if [ ! -f "$PYTHON_ZIP" ]; then
        log_error "Python zip not found at: $PYTHON_ZIP"
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

# Update Python files
update_python_files() {
    log_info "Updating Python files..."

    # main.py is loaded directly from Resources by __boot__.py (not from the zip)
    if [ -f "$PROJECT_DIR/main.py" ]; then
        cp "$PROJECT_DIR/main.py" "$PYTHON_CODE_PATH/main.py"
        log_success "Updated main.py (Resources)"
    fi

    # All other project .py files are compiled to .pyc inside the python zip.
    # We need to compile them and replace the entries in the zip.
    local tmpdir
    tmpdir=$(mktemp -d)
    local updated=0

    for pyfile in "${PROJECT_FILES[@]}"; do
        if [ -f "$PROJECT_DIR/$pyfile" ]; then
            local basename="${pyfile%.py}"
            local pyc_name="${basename}.pyc"

            # Compile .py to .pyc (optimize=1 matches py2app build setting)
            "$VENV_PYTHON" -O -c "
import py_compile, sys, os, importlib.util
src = sys.argv[1]
dst = sys.argv[2]
py_compile.compile(src, dst, doraise=True, optimize=1)
" "$PROJECT_DIR/$pyfile" "$tmpdir/$pyc_name"

            updated=$((updated + 1))
            log_success "Compiled $pyfile"
        fi
    done

    if [ "$updated" -gt 0 ]; then
        # Update the zip file with new .pyc files
        "$VENV_PYTHON" -c "
import zipfile, sys, os

zip_path = sys.argv[1]
tmpdir = sys.argv[2]
pyc_files = [f for f in os.listdir(tmpdir) if f.endswith('.pyc')]

# Read existing zip, write new one with updated entries
tmp_zip = zip_path + '.tmp'
with zipfile.ZipFile(zip_path, 'r') as zin:
    with zipfile.ZipFile(tmp_zip, 'w', compression=zin.compression) as zout:
        for item in zin.infolist():
            if item.filename in pyc_files:
                # Replace with our new compiled version
                with open(os.path.join(tmpdir, item.filename), 'rb') as f:
                    zout.writestr(item, f.read())
            else:
                zout.writestr(item, zin.read(item.filename))

os.replace(tmp_zip, zip_path)
" "$PYTHON_ZIP" "$tmpdir"

        log_success "Updated $updated modules in python${PYTHON_VERSION}.zip"
    fi

    # Cleanup
    rm -rf "$tmpdir"

    # Clear any __pycache__ that might have stale bytecode
    find "$PYTHON_CODE_PATH" -maxdepth 1 -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
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
    echo "Updated: main.py (direct) + ${#PROJECT_FILES[@]} modules (in zip)"
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

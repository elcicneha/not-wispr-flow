#!/bin/bash
#
# Not Wispr Flow App Installer
# Builds and installs Not Wispr Flow.app to /Applications
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python3"
SETUP_PY="$PROJECT_DIR/setup.py"
APP_BUNDLE="$PROJECT_DIR/dist/Not Wispr Flow.app"
APP_INSTALL_PATH="/Applications/Not Wispr Flow.app"
LOG_DIR="$HOME/Library/Logs/NotWisprFlow"
CODESIGN_IDENTITY="Not Wispr Flow Dev"

# Detect Python version dynamically (works with any Python 3.x)
# This will be set after venv is verified in check_prerequisites
PYTHON_VERSION=""

# Functions
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }
log_info() { echo -e "${BLUE}[i]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[!]${NC} $1"; }

print_header() {
    echo ""
    echo "Not Wispr Flow App Installer"
    echo "============================"
    echo ""
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check virtual environment
    if [ ! -f "$VENV_PYTHON" ]; then
        log_error "Virtual environment not found at: $VENV_PYTHON"
        log_info "Please run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
        exit 1
    fi
    log_success "Found virtual environment"

    # Detect Python version (e.g., "3.14", "3.11")
    PYTHON_VERSION=$("$VENV_PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    log_success "Detected Python version: $PYTHON_VERSION"

    # Check setup.py
    if [ ! -f "$SETUP_PY" ]; then
        log_error "setup.py not found at: $SETUP_PY"
        log_info "Please create setup.py first"
        exit 1
    fi
    log_success "Found setup.py"

    # Check code signing certificate exists
    if security find-certificate -c "$CODESIGN_IDENTITY" ~/Library/Keychains/login.keychain-db > /dev/null 2>&1; then
        log_success "Found code signing certificate: '$CODESIGN_IDENTITY'"
    else
        log_error "Code signing certificate '$CODESIGN_IDENTITY' not found"
        log_info "Please create it first: ./scripts/create_certificate.sh"
        exit 1
    fi

    # Kill any running Not Wispr Flow processes before reinstalling
    local app_pids
    app_pids=$(pgrep -fx ".*/Not Wispr Flow\.app/Contents/MacOS/Not Wispr Flow" 2>/dev/null) || true
    if [ -n "$app_pids" ]; then
        log_info "Stopping running Not Wispr Flow processes..."
        echo "$app_pids" | xargs kill 2>/dev/null || true
        sleep 1
    fi

    # Remove stale LaunchAgent if it exists
    if [ -f "$HOME/Library/LaunchAgents/com.notwisprflow.dictation.plist" ]; then
        log_info "Removing old LaunchAgent..."
        launchctl unload "$HOME/Library/LaunchAgents/com.notwisprflow.dictation.plist" 2>/dev/null || true
        rm -f "$HOME/Library/LaunchAgents/com.notwisprflow.dictation.plist"
    fi

    log_success "Prerequisites check passed"
}

create_log_directory() {
    log_info "Creating log directory..."
    mkdir -p "$LOG_DIR"
    chmod 700 "$LOG_DIR"
    log_success "Created: $LOG_DIR (permissions: 700)"
}

build_app_bundle() {
    log_info "Building macOS app bundle with py2app..."

    cd "$PROJECT_DIR"

    # Clean previous build
    if [ -d "build" ] || [ -d "dist" ]; then
        log_info "Cleaning previous build..."
        rm -rf build dist
    fi

    # Build the app
    log_info "Running: python3 setup.py py2app"
    log_info "This may take a few minutes..."
    "$VENV_PYTHON" setup.py py2app

    if [ ! -d "$APP_BUNDLE" ]; then
        log_error "Build failed - app bundle not created"
        exit 1
    fi

    log_success "App bundle created: $APP_BUNDLE"

    # Fix MLX library rpaths
    log_info "Fixing MLX library rpaths..."
    local mlx_core_so="$APP_BUNDLE/Contents/Resources/lib/python$PYTHON_VERSION/lib-dynload/mlx/core.so"
    local frameworks_dir="$APP_BUNDLE/Contents/Frameworks"

    if [ -f "$mlx_core_so" ]; then
        # Add rpath to Frameworks directory so core.so can find libmlx.dylib
        # core.so is at: Contents/Resources/lib/python3.14/lib-dynload/mlx/core.so
        # libmlx.dylib is at: Contents/Frameworks/libmlx.dylib
        # Need to go up 5 levels: mlx -> lib-dynload -> python3.14 -> lib -> Resources -> Contents
        install_name_tool -add_rpath "@loader_path/../../../../../Frameworks" "$mlx_core_so" 2>/dev/null || true
        log_success "Fixed rpath for mlx/core.so"
    else
        log_warning "mlx/core.so not found, skipping rpath fix"
    fi

    # Move MLX metallib to Frameworks (must be colocated with libmlx.dylib)
    log_info "Moving mlx.metallib to Frameworks directory..."
    local metallib_source="$APP_BUNDLE/Contents/Resources/mlx.metallib"
    local metallib_dest="$APP_BUNDLE/Contents/Frameworks/mlx.metallib"

    if [ -f "$metallib_source" ]; then
        mv "$metallib_source" "$metallib_dest"
        log_success "Moved mlx.metallib to Frameworks (colocated with libmlx.dylib)"
    else
        log_warning "mlx.metallib not found at $metallib_source"
    fi

    # Verify bundle
    log_info "Verifying bundle contents..."
    if [ -f "$SCRIPT_DIR/verify_bundle.sh" ]; then
        bash "$SCRIPT_DIR/verify_bundle.sh"
    else
        log_warning "verify_bundle.sh not found, skipping verification"
    fi
}

install_app() {
    log_info "Installing app to /Applications..."

    # Remove old version if exists
    if [ -d "$APP_INSTALL_PATH" ]; then
        log_warning "Removing old version at $APP_INSTALL_PATH"
        rm -rf "$APP_INSTALL_PATH"
    fi

    # Copy to /Applications
    cp -R "$APP_BUNDLE" "$APP_INSTALL_PATH"

    # Sign mlx/core.so individually (install_name_tool invalidated its signature)
    local mlx_core_so="$APP_INSTALL_PATH/Contents/Resources/lib/python$PYTHON_VERSION/lib-dynload/mlx/core.so"
    if [ -f "$mlx_core_so" ]; then
        log_info "Signing modified mlx/core.so..."
        codesign --force --sign "$CODESIGN_IDENTITY" "$mlx_core_so"
        log_success "Signed mlx/core.so"
    fi

    # Sign the installed app (using persistent certificate preserves permissions across rebuilds)
    log_info "Signing app with identity: $CODESIGN_IDENTITY"
    if codesign --force --deep --sign "$CODESIGN_IDENTITY" "$APP_INSTALL_PATH"; then
        log_success "App signed successfully (permissions will persist across rebuilds)"
    else
        log_error "Code signing failed"
        exit 1
    fi

    log_success "Installed to: $APP_INSTALL_PATH"
}

print_summary() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}Not Wispr Flow has been installed!${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo -e "${YELLOW}IMPORTANT: Grant these permissions to 'Not Wispr Flow' (first install only):${NC}"
    echo "  1. System Settings → Privacy & Security → Microphone → Enable 'Not Wispr Flow'"
    echo "  2. System Settings → Privacy & Security → Accessibility → Enable 'Not Wispr Flow'"
    echo "  3. System Settings → Privacy & Security → Input Monitoring → Enable 'Not Wispr Flow'"
    echo ""
    echo "  Permissions persist across rebuilds when signed with '$CODESIGN_IDENTITY' certificate."
    echo ""
    echo "How to use:"
    echo "  • Start: Open '/Applications/Not Wispr Flow.app' (or use Spotlight)"
    echo "  • Running: Look for the microphone icon in the menu bar"
    echo "  • Stop: Click the menu bar icon → Quit Not Wispr Flow"
    echo ""
    echo "Log files:"
    echo "  • Application: $LOG_DIR/notwisprflow.log"
    echo ""
    echo "Uninstall: $SCRIPT_DIR/uninstall_service.sh"
    echo ""
}

# Main execution
main() {
    print_header
    check_prerequisites
    build_app_bundle
    install_app
    create_log_directory
    print_summary
}

main

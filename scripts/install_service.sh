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
        log_info "Without this certificate, you must re-grant permissions after every rebuild."
        log_info "To create it (one-time setup):"
        log_info "  1. Open Keychain Access: open /Applications/Utilities/Keychain\\ Access.app"
        log_info "  2. Menu: Keychain Access > Certificate Assistant > Create a Certificate..."
        log_info "  3. Name: '$CODESIGN_IDENTITY', Identity Type: Self Signed Root, Certificate Type: Code Signing"
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

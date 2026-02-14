#!/bin/bash
#
# Whispr Service Installer
# Installs Whispr as a macOS LaunchAgent for auto-start on login
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
MAIN_SCRIPT="$PROJECT_DIR/whispr_clone.py"
SETUP_PY="$PROJECT_DIR/setup.py"
APP_BUNDLE="$PROJECT_DIR/dist/Whispr.app"
APP_INSTALL_PATH="/Applications/Whispr.app"
PLIST_DEST="$HOME/Library/LaunchAgents/com.whispr.dictation.plist"
LOG_DIR="$HOME/Library/Logs/Whispr"

# Functions
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }
log_info() { echo -e "${BLUE}[i]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[!]${NC} $1"; }

print_header() {
    echo ""
    echo "Whispr Service Installer"
    echo "========================"
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

    # Check if already installed
    if launchctl list 2>/dev/null | grep -q "com.whispr.dictation"; then
        log_warning "Service is already installed and running"
        read -p "Do you want to reinstall? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Installation cancelled"
            exit 0
        fi
        log_info "Unloading existing service..."
        launchctl unload "$PLIST_DEST" 2>/dev/null || true
        sleep 1
    fi

    log_success "Prerequisites check passed"
}

create_log_directory() {
    log_info "Creating log directory..."
    mkdir -p "$LOG_DIR"
    log_success "Created: $LOG_DIR"
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

    log_success "Installed to: $APP_INSTALL_PATH"
}

generate_plist() {
    log_info "Generating plist file..."

    # Create plist with app bundle path
    cat > "$PLIST_DEST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.whispr.dictation</string>

    <key>ProgramArguments</key>
    <array>
        <string>$APP_INSTALL_PATH/Contents/MacOS/Whispr</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$HOME</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>ThrottleInterval</key>
    <integer>10</integer>

    <key>StandardOutPath</key>
    <string>$LOG_DIR/stdout.log</string>

    <key>StandardErrorPath</key>
    <string>$LOG_DIR/stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>

    <key>ProcessType</key>
    <string>Interactive</string>

    <key>Nice</key>
    <integer>0</integer>
</dict>
</plist>
EOF

    log_success "Generated plist at: $PLIST_DEST"
}

validate_plist() {
    log_info "Validating plist syntax..."

    if ! plutil -lint "$PLIST_DEST" > /dev/null 2>&1; then
        log_error "Invalid plist syntax"
        plutil -lint "$PLIST_DEST"
        exit 1
    fi

    log_success "Plist syntax is valid"
}

load_service() {
    log_info "Loading service..."

    if ! launchctl load "$PLIST_DEST" 2>/dev/null; then
        log_error "Failed to load service"
        log_info "Check permissions and try manually:"
        log_info "  launchctl load $PLIST_DEST"
        exit 1
    fi

    # Wait a moment for service to start
    sleep 2

    # Verify service is running
    if launchctl list 2>/dev/null | grep -q "com.whispr.dictation"; then
        log_success "Service loaded successfully"
    else
        log_error "Service loaded but not running"
        log_info "Check logs for errors:"
        log_info "  tail $LOG_DIR/stderr.log"
        exit 1
    fi
}

print_summary() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}Whispr is now running as a background service!${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo -e "${YELLOW}IMPORTANT: You need to grant permissions to 'Whispr':${NC}"
    echo "  1. System Preferences → Privacy & Security → Microphone"
    echo "     → Enable 'Whispr'"
    echo "  2. System Preferences → Privacy & Security → Accessibility"
    echo "     → Enable 'Whispr'"
    echo ""
    echo "  (If you previously granted permissions to 'Python', those won't"
    echo "   transfer to the new app - you need to re-grant them.)"
    echo ""
    echo "Next steps:"
    echo "  • Test dictation in any application"
    echo "  • View logs: tail -f $LOG_DIR/whispr.log"
    echo "  • Check status: $SCRIPT_DIR/check_status.sh"
    echo "  • Uninstall: $SCRIPT_DIR/uninstall_service.sh"
    echo ""
    echo "Log files:"
    echo "  • Application: $LOG_DIR/whispr.log"
    echo "  • System out:  $LOG_DIR/stdout.log"
    echo "  • Errors:      $LOG_DIR/stderr.log"
    echo ""
    echo "The service will automatically start on login."
    echo ""
}

# Main execution
main() {
    print_header
    check_prerequisites
    build_app_bundle
    install_app
    create_log_directory
    generate_plist
    validate_plist
    load_service
    print_summary
}

main

#!/bin/bash
#
# Verify Bundle Script
# Checks that all required native libraries are included in the app bundle
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_PATH="$PROJECT_DIR/dist/Whispr.app"

# Functions
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }
log_info() { echo -e "${YELLOW}[i]${NC} $1"; }

echo ""
echo "Whispr Bundle Verification"
echo "==========================="
echo ""
log_info "Checking bundle at: $APP_PATH"
echo ""

# Check if bundle exists
if [ ! -d "$APP_PATH" ]; then
    log_error "App bundle not found at: $APP_PATH"
    log_info "Run 'python3 setup.py py2app' first"
    exit 1
fi

# Check for main executable
if [ -f "$APP_PATH/Contents/MacOS/Whispr" ]; then
    log_success "Found main executable: Whispr"
else
    log_error "Missing main executable"
    exit 1
fi

# Check for Info.plist
if [ -f "$APP_PATH/Contents/Info.plist" ]; then
    log_success "Found Info.plist"
else
    log_error "Missing Info.plist"
    exit 1
fi

# Check for sounddevice portaudio library
PORTAUDIO_PATH="$APP_PATH/Contents/Resources/lib/python3.14/_sounddevice_data/portaudio-binaries/libportaudio.dylib"
if [ -f "$PORTAUDIO_PATH" ]; then
    SIZE=$(du -h "$PORTAUDIO_PATH" | awk '{print $1}')
    log_success "Found libportaudio.dylib ($SIZE)"
else
    log_error "Missing libportaudio.dylib"
    log_info "Expected at: $_sounddevice_data/portaudio-binaries/libportaudio.dylib"
    exit 1
fi

# Check for av (PyAV) FFmpeg dylibs
AV_DYLIBS_DIR="$APP_PATH/Contents/Resources/lib/python3.14/av/.dylibs"
if [ -d "$AV_DYLIBS_DIR" ]; then
    DYLIB_COUNT=$(find "$AV_DYLIBS_DIR" -name "*.dylib" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$DYLIB_COUNT" -ge 20 ]; then
        TOTAL_SIZE=$(du -sh "$AV_DYLIBS_DIR" | awk '{print $1}')
        log_success "Found $DYLIB_COUNT FFmpeg dylibs ($TOTAL_SIZE total)"
    else
        log_error "Missing FFmpeg dylibs (found $DYLIB_COUNT, expected ~26)"
        exit 1
    fi
else
    log_error "Missing av/.dylibs directory"
    exit 1
fi

# Check for ctranslate2 (compiled extension)
if find "$APP_PATH/Contents/Resources/lib/python3.14" -name "*ctranslate2*" -type f 2>/dev/null | grep -q .; then
    log_success "Found ctranslate2 extension"
else
    log_error "Missing ctranslate2 extension"
    exit 1
fi

# Check for onnxruntime (compiled extension)
if find "$APP_PATH/Contents/Resources/lib/python3.14" -name "*onnxruntime*" -type f 2>/dev/null | grep -q .; then
    log_success "Found onnxruntime extension"
else
    log_error "Missing onnxruntime extension"
    exit 1
fi

# Check for faster_whisper
if [ -d "$APP_PATH/Contents/Resources/lib/python3.14/faster_whisper" ]; then
    log_success "Found faster_whisper package"
else
    log_error "Missing faster_whisper package"
    exit 1
fi

# Check for numpy
if [ -d "$APP_PATH/Contents/Resources/lib/python3.14/numpy" ]; then
    log_success "Found numpy package"
else
    log_error "Missing numpy package"
    exit 1
fi

# Check for pynput
if [ -d "$APP_PATH/Contents/Resources/lib/python3.14/pynput" ]; then
    log_success "Found pynput package"
else
    log_error "Missing pynput package"
    exit 1
fi

# Check bundle size
BUNDLE_SIZE=$(du -sh "$APP_PATH" | awk '{print $1}')
log_info "Total bundle size: $BUNDLE_SIZE"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}Bundle verification passed!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo "  • Test the app: ./dist/Whispr.app/Contents/MacOS/Whispr"
echo "  • Or install as service: ./scripts/install_service.sh"
echo ""

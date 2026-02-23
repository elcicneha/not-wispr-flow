#!/bin/bash

# Script to create a DMG installer for Not Wispr Flow
# This creates a disk image that users can download and install from

set -e  # Exit on any error

echo "🔨 Creating DMG installer..."

# Configuration
APP_NAME="Not Wispr Flow"
DMG_NAME="NotWisprFlow"
VERSION="${1:-1.0.0}"  # Use provided version or default to 1.0.0
APP_PATH="dist/${APP_NAME}.app"
DMG_PATH="dist/${DMG_NAME}-${VERSION}.dmg"
TEMP_DMG="dist/temp.dmg"

# Check if app exists
if [ ! -d "$APP_PATH" ]; then
    echo "❌ Error: ${APP_PATH} not found!"
    echo "Run './scripts/install_service.sh' first to build the app."
    exit 1
fi

# Clean up old DMG if it exists
rm -f "$DMG_PATH" "$TEMP_DMG"

echo "📦 Creating temporary DMG..."
# Create a temporary DMG (1.5GB to fit the app + dependencies)
hdiutil create -size 1500m -fs HFS+ -volname "$APP_NAME" "$TEMP_DMG"

echo "📂 Mounting DMG..."
# Mount the DMG (use cut -f3 to handle spaces in volume name)
MOUNT_DIR=$(hdiutil attach "$TEMP_DMG" | grep Volumes | cut -f3)

echo "📋 Copying app to DMG..."
# Copy the app to the DMG
cp -R "$APP_PATH" "$MOUNT_DIR/"

# Create a symbolic link to Applications folder for easy drag-and-drop
ln -s /Applications "$MOUNT_DIR/Applications"

# Create a README for first-time users
cat > "$MOUNT_DIR/README.txt" << 'EOF'
Installation Instructions:
==========================

1. Drag "Not Wispr Flow" to the Applications folder
2. Open "Not Wispr Flow" from Applications or Spotlight
3. The first time, you'll need to:
   - Right-click the app and select "Open" (this bypasses macOS security)
   - Click "Open" in the dialog
4. Grant permissions when prompted:
   - Microphone
   - Accessibility
   - Input Monitoring

You only need to do the right-click step the first time!

After that, you can launch it normally from Spotlight or Applications.

Usage:
======
- Hold Control key → speak → release (Hold mode)
- Press Control + Space → speak → press Control (Toggle mode)

For help: https://github.com/elcicneha/not-wispr-flow
EOF

echo "💤 Finalizing DMG..."
# Unmount
hdiutil detach "$MOUNT_DIR" -quiet

echo "🗜️  Compressing DMG..."
# Convert to compressed, read-only DMG
hdiutil convert "$TEMP_DMG" -format UDZO -o "$DMG_PATH"

# Clean up temp DMG
rm -f "$TEMP_DMG"

echo "✅ DMG created successfully!"
echo "📍 Location: $DMG_PATH"
echo ""
echo "File size: $(du -h "$DMG_PATH" | cut -f1)"
echo ""
echo "Next steps:"
echo "1. Test the DMG by opening it and dragging the app to Applications"
echo "2. Upload $DMG_PATH to GitHub Releases"

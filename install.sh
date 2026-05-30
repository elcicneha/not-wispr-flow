#!/bin/bash
#
# Not Wispr Flow — One-Step Installer
#
# Usage: ./install.sh
#

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
VENV_PYTHON="$VENV_DIR/bin/python3"
MIN_PYTHON_MINOR=10

# ── Sanity check ──
if [ ! -f "$PROJECT_DIR/setup.py" ] || [ ! -f "$PROJECT_DIR/requirements.txt" ]; then
    echo "Run this from inside the not-wispr-flow folder."
    exit 1
fi

# ── Resolve a WORKING Python 3.MIN+ ──
# Note: macOS ships a /usr/bin/python3 stub that exists on PATH but, when the
# Xcode Command Line Tools are NOT installed, only pops the CLT install dialog
# and produces no usable Python. We must NOT execute that stub (executing it is
# what triggers the dialog), and `command -v python3` succeeding is meaningless.
#
# This app needs only a real Python — NOT Xcode CLT and NOT Homebrew. So when no
# real Python exists we install the official python.org standalone build, which
# is self-contained and pulls in neither Xcode nor Homebrew.
PYTHON_BIN=""

# Official python.org standalone installer (universal2, no Xcode/brew needed).
# Bump these together when updating the bundled Python.
PY_PKG_VERSION="3.12.8"

# True when the Xcode Command Line Tools are actually installed.
clt_installed() { xcode-select -p >/dev/null 2>&1; }

# Returns 0 and echoes the minor version if $1 is a usable python3, else 1.
# Skips the macOS CLT stub WITHOUT running it (running it pops the dialog).
probe_python() {
    local bin="$1" resolved minor
    resolved="$(command -v "$bin" 2>/dev/null)" || return 1
    [ -x "$resolved" ] || return 1
    # The CLT stub lives at /usr/bin/python3 (or under the CLT dir). If CLT is
    # not installed, that path is a non-functional shim — skip it untouched.
    case "$resolved" in
        /usr/bin/python3|/Library/Developer/CommandLineTools/*)
            clt_installed || return 1 ;;
    esac
    minor=$("$resolved" -c 'import sys; print(sys.version_info.minor)' 2>/dev/null) || return 1
    [ -n "$minor" ] || return 1
    [ "$minor" -ge "$MIN_PYTHON_MINOR" ] 2>/dev/null || return 1
    echo "$minor"
}

# Resolve PYTHON_BIN from common locations. python.org framework first, then
# Homebrew, then PATH (the bare `python3` is stub-guarded inside probe_python).
resolve_python() {
    local candidate
    for candidate in \
        "/Library/Frameworks/Python.framework/Versions/${PY_PKG_VERSION%.*}/bin/python3" \
        /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
        /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
        /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
        /opt/homebrew/bin/python3 \
        /usr/local/bin/python3 \
        python3; do
        if probe_python "$candidate" >/dev/null; then
            PYTHON_BIN="$(command -v "$candidate" 2>/dev/null || echo "$candidate")"
            return 0
        fi
    done
    return 1
}

resolve_python

# ── No usable Python → install official python.org build (no Xcode/Homebrew) ──
if [ -z "$PYTHON_BIN" ]; then
    echo "No usable Python 3.$MIN_PYTHON_MINOR+ found."
    echo "Installing the official Python $PY_PKG_VERSION from python.org"
    echo "(self-contained — no Xcode or Homebrew needed)..."

    PY_PKG_URL="https://www.python.org/ftp/python/${PY_PKG_VERSION}/python-${PY_PKG_VERSION}-macos11.pkg"
    PY_PKG_TMP="$(mktemp -t notwisprflow-python).pkg"

    if ! curl -fL --progress-bar "$PY_PKG_URL" -o "$PY_PKG_TMP"; then
        rm -f "$PY_PKG_TMP"
        echo "Couldn't download Python. Install it manually, then re-run ./install.sh:"
        echo "  https://www.python.org/downloads/macos/"
        exit 1
    fi

    echo "Running the Python installer (you'll be asked for your Mac password)..."
    if ! sudo installer -pkg "$PY_PKG_TMP" -target /; then
        rm -f "$PY_PKG_TMP"
        echo "Python install failed. Install it manually, then re-run ./install.sh:"
        echo "  https://www.python.org/downloads/macos/"
        exit 1
    fi
    rm -f "$PY_PKG_TMP"

    if ! resolve_python; then
        echo "Python installed but not visible yet. Open a NEW Terminal window and"
        echo "re-run ./install.sh"
        exit 1
    fi
fi

echo "Using Python: $PYTHON_BIN"

# ── Create venv if needed ──
if [ ! -d "$VENV_DIR" ]; then
    if ! "$PYTHON_BIN" -m venv "$VENV_DIR"; then
        echo "Failed to create virtualenv at $VENV_DIR"
        exit 1
    fi
fi

# ── Verify the venv interpreter exists before handing off ──
if [ ! -x "$VENV_PYTHON" ]; then
    echo "Virtualenv is broken (missing $VENV_PYTHON). Delete it and re-run:"
    echo "  rm -rf \"$VENV_DIR\" && ./install.sh"
    exit 1
fi

# ── Ensure rich is available for the installer UI ──
"$VENV_PYTHON" -m pip install rich --quiet 2>/dev/null

# ── Hand off to Python installer ──
exec "$VENV_PYTHON" "$PROJECT_DIR/scripts/installer.py"

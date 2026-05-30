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
# Note: macOS ships a /usr/bin/python3 stub that exists on PATH but only
# triggers the Command Line Tools installer and produces no usable Python.
# So `command -v python3` is NOT enough — we must verify it actually runs
# and reports a high-enough version before trusting it.
PYTHON_BIN=""

# Returns 0 and echoes the minor version if $1 is a usable python3, else 1.
probe_python() {
    local bin="$1" minor
    [ -x "$(command -v "$bin" 2>/dev/null)" ] || return 1
    # Capture version; the stub exits non-zero / prints nothing.
    minor=$("$bin" -c 'import sys; print(sys.version_info.minor)' 2>/dev/null) || return 1
    [ -n "$minor" ] || return 1
    [ "$minor" -ge "$MIN_PYTHON_MINOR" ] 2>/dev/null || return 1
    echo "$minor"
}

# Try common locations: Homebrew first (avoids the stub), then PATH.
for candidate in /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
    if probe_python "$candidate" >/dev/null; then
        PYTHON_BIN="$(command -v "$candidate")"
        break
    fi
done

# ── No usable Python → install via Homebrew (never rely on the stub) ──
if [ -z "$PYTHON_BIN" ]; then
    echo "No usable Python 3.$MIN_PYTHON_MINOR+ found. Installing via Homebrew..."

    # Install Homebrew if needed
    if ! command -v brew &>/dev/null; then
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    # Apple Silicon / Intel PATH fix (also covers a just-installed brew)
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -f /usr/local/bin/brew ]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi

    if ! command -v brew &>/dev/null; then
        echo "Homebrew install failed. Install Python 3.$MIN_PYTHON_MINOR+ manually:"
        echo "  https://www.python.org/downloads/"
        exit 1
    fi

    brew install python

    # Re-resolve after install.
    for candidate in /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
        if probe_python "$candidate" >/dev/null; then
            PYTHON_BIN="$(command -v "$candidate")"
            break
        fi
    done

    if [ -z "$PYTHON_BIN" ]; then
        echo "Still no usable Python after Homebrew install. Install manually:"
        echo "  https://www.python.org/downloads/"
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

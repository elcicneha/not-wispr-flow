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

# ── Ensure Python 3.10+ ──
if command -v python3 &>/dev/null; then
    py_minor=$(python3 -c 'import sys; print(sys.version_info.minor)')
    if [ "$py_minor" -lt "$MIN_PYTHON_MINOR" ]; then
        echo "Python 3.$MIN_PYTHON_MINOR+ required (found 3.$py_minor)"
        echo "Install from https://www.python.org/downloads/ or via Homebrew: brew install python"
        exit 1
    fi
else
    echo "Python 3 not found. Installing via Homebrew..."

    # Install Homebrew if needed
    if ! command -v brew &>/dev/null; then
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        # Apple Silicon PATH fix
        if [ -f /opt/homebrew/bin/brew ]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        elif [ -f /usr/local/bin/brew ]; then
            eval "$(/usr/local/bin/brew shellenv)"
        fi
    fi

    brew install python
fi

# ── Create venv if needed ──
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

# ── Ensure rich is available for the installer UI ──
"$VENV_PYTHON" -m pip install rich --quiet 2>/dev/null

# ── Hand off to Python installer ──
exec "$VENV_PYTHON" "$PROJECT_DIR/scripts/installer.py"

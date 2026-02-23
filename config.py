#!/usr/bin/env python3
"""
Not Wispr Flow - User Configuration

Edit these settings to customize your dictation experience.
After changing settings, rebuild and reinstall:
    ./scripts/install_service.sh
"""

from pynput.keyboard import Key

# ============================================================================
# WHISPER MODEL SELECTION
# ============================================================================
# Choose your Whisper model (affects speed vs accuracy tradeoff):
#   "mlx-community/whisper-large-v3-turbo"  - Best quality, ~1.6GB, ~2.3GB RAM
#   "mlx-community/whisper-small"           - Faster, ~500MB, ~2GB RAM (may hallucinate)
#   "mlx-community/whisper-base"            - Fastest, ~150MB, ~1GB RAM (less accurate)
#
WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"

# ============================================================================
# HOTKEY CONFIGURATION
# ============================================================================
# HOTKEY_KEYS: The key(s) that trigger recording
#
# IMPORTANT: This is a Python set containing pynput Key objects. macOS may report
# the same physical key with different codes (Key.ctrl vs Key.ctrl_r vs Key.ctrl_l).
# Including multiple variants ensures reliable detection across different keyboards
# and macOS versions.
#
# Common options:
#   {Key.ctrl, Key.ctrl_r}           - Right Control (default, broadest compatibility)
#   {Key.ctrl_r}                     - Right Control only (strict matching)
#   {Key.ctrl, Key.ctrl_l}           - Left Control
#   {Key.cmd_r, Key.cmd}             - Right Command (⌘)
#   {Key.alt_r, Key.alt}             - Right Option/Alt
#   {Key.f13}                        - F13 key
#
HOTKEY_KEYS = {Key.ctrl, Key.ctrl_r}

# TOGGLE_KEY: Press this WITH the hotkey to enable toggle mode
#
# Toggle mode: Press Hotkey+Space to START recording, Hotkey alone to STOP
# Hold mode: Hold Hotkey to record, release to stop (default behavior)
#
TOGGLE_KEY = Key.space

# ============================================================================
# DEBUGGING
# ============================================================================
# Enable verbose logging (writes to ~/Library/Logs/NotWisprFlow/notwisprflow.log)
# Set to True if experiencing issues, then check logs for detailed diagnostics.
#
DEBUG = False

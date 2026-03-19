"""Preferences persistence and API key resolution for Not Wispr Flow.

Provides shared utilities used by multiple modules:
- load/save preferences to ~/.config/notwisprflow/preferences.json
- resolve API keys from config → env var → dotfile
"""

import json
import os
import logging

logger = logging.getLogger("notwisprflow")

_PREFS_DIR = os.path.expanduser("~/.config/notwisprflow")
_PREFS_FILE = os.path.join(_PREFS_DIR, "preferences.json")


def load_preference(key, default=None):
    """Load a single preference from ~/.config/notwisprflow/preferences.json."""
    try:
        if os.path.exists(_PREFS_FILE):
            with open(_PREFS_FILE, "r") as f:
                prefs = json.load(f)
            return prefs.get(key, default)
    except Exception:
        pass
    return default


def save_preference(key, value):
    """Save a single preference to ~/.config/notwisprflow/preferences.json."""
    try:
        os.makedirs(_PREFS_DIR, exist_ok=True)
        prefs = {}
        if os.path.exists(_PREFS_FILE):
            with open(_PREFS_FILE, "r") as f:
                prefs = json.load(f)
        prefs[key] = value
        with open(_PREFS_FILE, "w") as f:
            json.dump(prefs, f, indent=2)
    except Exception:
        pass


def resolve_api_key(config_value, env_var_name, file_path):
    """Resolve an API key from config value → environment variable → dotfile.

    Args:
        config_value: Value from config.py (may be empty string)
        env_var_name: Environment variable name to check (e.g. "GROQ_API_KEY")
        file_path: Path to dotfile (e.g. "~/.config/notwisprflow/api_key")

    Returns:
        str: The resolved API key, or empty string if not found
    """
    if config_value:
        return config_value

    env_val = os.environ.get(env_var_name, "")
    if env_val:
        return env_val

    expanded_path = os.path.expanduser(file_path)
    if os.path.exists(expanded_path):
        try:
            with open(expanded_path, "r") as f:
                key = f.read().strip()
            if key:
                return key
        except Exception:
            pass

    return ""

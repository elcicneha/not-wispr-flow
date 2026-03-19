"""Login item (LaunchAgent) management for Not Wispr Flow.

Creates/removes a macOS LaunchAgent plist to start the app at login.
"""

import logging
import os

logger = logging.getLogger("notwisprflow")

_LAUNCH_AGENT_DIR = os.path.expanduser("~/Library/LaunchAgents")
_LAUNCH_AGENT_PLIST = os.path.join(_LAUNCH_AGENT_DIR, "com.notwisprflow.dictation.plist")

_PLIST_CONTENT = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" \
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.notwisprflow.dictation</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Applications/Not Wispr Flow.app/Contents/MacOS/Not Wispr Flow</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""


def is_login_item_installed():
    """Check if the LaunchAgent plist exists."""
    return os.path.exists(_LAUNCH_AGENT_PLIST)


def install_login_item():
    """Create LaunchAgent plist to start the app at login."""
    try:
        os.makedirs(_LAUNCH_AGENT_DIR, exist_ok=True)
        with open(_LAUNCH_AGENT_PLIST, "w") as f:
            f.write(_PLIST_CONTENT)
        logger.info("Login item installed: %s", _LAUNCH_AGENT_PLIST)
        return True
    except Exception as e:
        logger.error("Failed to install login item: %s", e)
        return False


def uninstall_login_item():
    """Remove LaunchAgent plist to stop starting the app at login."""
    try:
        if os.path.exists(_LAUNCH_AGENT_PLIST):
            os.remove(_LAUNCH_AGENT_PLIST)
            logger.info("Login item removed: %s", _LAUNCH_AGENT_PLIST)
        return True
    except Exception as e:
        logger.error("Failed to remove login item: %s", e)
        return False

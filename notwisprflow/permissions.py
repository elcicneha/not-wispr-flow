"""macOS permission checks for Not Wispr Flow.

Handles microphone access and accessibility permission verification.
"""

import ctypes
import logging
import sys
import time

import soundcard as sc

from .constants import SAMPLE_RATE

logger = logging.getLogger("notwisprflow")


def test_microphone_access():
    """Test if microphone access is granted.

    Returns:
        bool: True if microphone is accessible, False otherwise
    """
    try:
        logger.debug("Testing microphone access...")

        mic = sc.default_microphone()
        with mic.recorder(samplerate=SAMPLE_RATE, channels=[0]) as rec:
            rec.record(numframes=SAMPLE_RATE // 10)  # 100ms test

        logger.debug("Microphone access OK")
        return True

    except Exception as e:
        logger.error("=" * 60)
        logger.error("ERROR: Microphone access denied or unavailable")
        logger.error("=" * 60)
        logger.error(f"Details: {e}")
        logger.error("")
        logger.error("macOS Permissions Required:")
        logger.error("1. Open System Preferences (or System Settings)")
        logger.error("2. Go to Security & Privacy > Privacy")
        logger.error("3. Select 'Microphone' from the left sidebar")
        logger.error("4. Enable access for 'Terminal' (or your IDE/Python)")
        logger.error("\nPlease grant permission and restart the application.")
        logger.error("=" * 60)
        return False


def is_accessibility_trusted(prompt=False):
    """Check if the process has Accessibility permission using macOS API.

    Args:
        prompt: If True, opens System Settings to the Accessibility pane

    Returns:
        bool: True if the process is trusted for accessibility
    """
    try:
        app_services = ctypes.cdll.LoadLibrary(
            '/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices'
        )

        if not prompt:
            return bool(app_services.AXIsProcessTrusted())

        # Use AXIsProcessTrustedWithOptions to show the system prompt
        core_foundation = ctypes.cdll.LoadLibrary(
            '/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation'
        )

        core_foundation.CFStringCreateWithCString.restype = ctypes.c_void_p
        core_foundation.CFStringCreateWithCString.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32
        ]
        key = core_foundation.CFStringCreateWithCString(
            None, b"AXTrustedCheckOptionPrompt", 0x08000100  # kCFStringEncodingUTF8
        )

        kCFBooleanTrue = ctypes.c_void_p.in_dll(core_foundation, 'kCFBooleanTrue')

        core_foundation.CFDictionaryCreate.restype = ctypes.c_void_p
        core_foundation.CFDictionaryCreate.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p
        ]
        keys_arr = (ctypes.c_void_p * 1)(key)
        vals_arr = (ctypes.c_void_p * 1)(kCFBooleanTrue)
        kCFTypeDictionaryKeyCallBacks = ctypes.c_void_p.in_dll(
            core_foundation, 'kCFTypeDictionaryKeyCallBacks'
        )
        kCFTypeDictionaryValueCallBacks = ctypes.c_void_p.in_dll(
            core_foundation, 'kCFTypeDictionaryValueCallBacks'
        )
        opts = core_foundation.CFDictionaryCreate(
            None, keys_arr, vals_arr, 1,
            ctypes.byref(kCFTypeDictionaryKeyCallBacks),
            ctypes.byref(kCFTypeDictionaryValueCallBacks)
        )

        app_services.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
        app_services.AXIsProcessTrustedWithOptions.argtypes = [ctypes.c_void_p]
        result = app_services.AXIsProcessTrustedWithOptions(opts)

        core_foundation.CFRelease(opts)
        core_foundation.CFRelease(key)
        return bool(result)
    except Exception:
        return False


def check_accessibility_permission():
    """Check if accessibility permissions are granted for keyboard control.

    If not granted, opens System Settings and waits up to 30 seconds for the user
    to grant permission. Exits cleanly if not granted after waiting.

    Returns:
        bool: True if granted, exits with code 0 if not
    """
    if is_accessibility_trusted():
        logger.debug("Accessibility permission: OK")
        return True

    logger.warning("Accessibility permission not granted. Opening System Settings...")
    is_accessibility_trusted(prompt=True)

    for i in range(6):
        time.sleep(5)
        if is_accessibility_trusted():
            logger.info("Accessibility permission: OK (granted after prompt)")
            return True
        logger.info("Waiting for accessibility permission... (%d/6)", i + 1)

    logger.error("=" * 60)
    logger.error("FATAL: Accessibility permission not granted after 30 seconds")
    logger.error("Please enable 'Not Wispr Flow' in System Settings > Accessibility and restart")
    logger.error("=" * 60)
    sys.exit(0)  # Clean exit so KeepAlive does NOT restart

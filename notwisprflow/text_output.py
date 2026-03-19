"""Text insertion and cursor context for Not Wispr Flow.

Handles typing text at the cursor position via clipboard paste or CGEvent,
and reading surrounding text via macOS Accessibility APIs.
"""

import ctypes
import logging
import time

import objc
from Quartz import (
    CGEventCreateKeyboardEvent, CGEventKeyboardSetUnicodeString,
    CGEventPost, CGEventSetFlags, kCGHIDEventTap,
)
from ApplicationServices import (
    AXUIElementCreateSystemWide,
    AXUIElementCopyAttributeValue,
    kAXFocusedUIElementAttribute,
    kAXValueAttribute,
    kAXSelectedTextRangeAttribute,
    kAXErrorSuccess,
)
from AppKit import NSPasteboard, NSData
from pynput.keyboard import Key

logger = logging.getLogger("notwisprflow")

# Default context window for cursor context
CONTEXT_CHARS = 200

# CFRange struct for extracting cursor position via ctypes
class _CFRange(ctypes.Structure):
    _fields_ = [("location", ctypes.c_long), ("length", ctypes.c_long)]

_ax_lib = ctypes.cdll.LoadLibrary(
    '/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices'
)
_ax_lib.AXValueGetValue.restype = ctypes.c_bool
_ax_lib.AXValueGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
_kAXValueTypeCFRange = 4


def get_cursor_context(max_chars=CONTEXT_CHARS):
    """Read text around the cursor in the active application using macOS Accessibility APIs.

    Returns:
        tuple: (before_text, after_text) where each is a string or None on failure.
    """
    try:
        from ApplicationServices import AXUIElementCreateApplication
        from AppKit import NSWorkspace

        # Get the frontmost application's PID
        frontmost = NSWorkspace.sharedWorkspace().frontmostApplication()
        if frontmost is None:
            logger.debug("AX: No frontmost application found")
            return None, None
        pid = frontmost.processIdentifier()
        app_name = frontmost.localizedName()

        # Get the focused UI element from the app
        app_element = AXUIElementCreateApplication(pid)
        err, focused = AXUIElementCopyAttributeValue(
            app_element, kAXFocusedUIElementAttribute, None
        )
        if err != kAXErrorSuccess or focused is None:
            logger.debug(f"AX: No focused element in {app_name} (err={err})")
            return None, None

        # Get text value
        err, value = AXUIElementCopyAttributeValue(
            focused, kAXValueAttribute, None
        )
        if err != kAXErrorSuccess or value is None:
            logger.debug(f"AX: No text value in focused element (err={err})")
            return None, None

        text = str(value)
        if not text:
            return "", ""

        # Get cursor position using ctypes to extract CFRange from AXValueRef
        err, range_val = AXUIElementCopyAttributeValue(
            focused, kAXSelectedTextRangeAttribute, None
        )
        if err != kAXErrorSuccess or range_val is None:
            logger.debug(f"AX: No cursor position available (err={err})")
            return None, None

        cf_range = _CFRange()
        ax_ptr = objc.pyobjc_id(range_val)
        if not _ax_lib.AXValueGetValue(ax_ptr, _kAXValueTypeCFRange, ctypes.byref(cf_range)):
            logger.debug("AX: Failed to extract CFRange from AXValueRef")
            return None, None

        cursor_pos = cf_range.location

        before = text[max(0, cursor_pos - max_chars):cursor_pos]
        after = text[cursor_pos:cursor_pos + max_chars]

        logger.debug(f"AX: Cursor context from {app_name}: {len(before)} chars before, {len(after)} chars after (pos {cursor_pos})")
        return before, after

    except Exception as e:
        logger.debug(f"AX: Cursor context detection failed: {e}")
        return None, None


def type_chunked(text, chunk_size=16, delay=0.008):
    """Type text by sending chunks of characters via CGEvent keyboard events.

    Uses CGEventKeyboardSetUnicodeString to send multiple characters per
    keyboard event — the same mechanism macOS input methods (CJK) use to
    commit entire words. Much faster than character-by-character typing
    while avoiding auto-period and character drop issues.

    Args:
        text: The text to type
        chunk_size: Characters per keyboard event (default 16, max ~20)
        delay: Seconds between events (default 8ms)
    """
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        event_down = CGEventCreateKeyboardEvent(None, 0, True)
        event_up = CGEventCreateKeyboardEvent(None, 0, False)
        CGEventSetFlags(event_down, 0)
        CGEventSetFlags(event_up, 0)
        CGEventKeyboardSetUnicodeString(event_down, len(chunk), chunk)
        CGEventKeyboardSetUnicodeString(event_up, len(chunk), chunk)
        CGEventPost(kCGHIDEventTap, event_down)
        CGEventPost(kCGHIDEventTap, event_up)
        time.sleep(delay)


def insert_text(text, state):
    """Insert transcribed text at cursor position.

    Uses clipboard paste by default (instant, unicode-safe) with concealed
    clipboard write to avoid polluting clipboard history.
    Falls back to character-by-character typing when use_type_mode is enabled.

    Args:
        text: The text to insert
        state: AppState instance (needs lock, last_transcription, use_type_mode, keyboard_controller)
    """
    with state.lock:
        state.last_transcription = text

    if state.use_type_mode:
        type_chunked(text)
        return

    pb = NSPasteboard.generalPasteboard()
    old_clipboard = pb.stringForType_('public.utf8-plain-text')

    pb.clearContents()
    if not pb.setString_forType_(text, 'public.utf8-plain-text'):
        logger.error(f"Failed to set clipboard content ({len(text)} chars)")
        return

    # Mark as concealed so clipboard managers (Alfred, Paste, Maccy) ignore it
    pb.setData_forType_(NSData.data(), 'org.nspasteboard.ConcealedType')

    # Small delay for clipboard to settle, then simulate Cmd+V
    time.sleep(0.02)
    state.keyboard_controller.press(Key.cmd)
    state.keyboard_controller.press('v')
    state.keyboard_controller.release('v')
    state.keyboard_controller.release(Key.cmd)

    # Wait for paste to complete before restoring clipboard
    time.sleep(0.2)

    # Restore previous clipboard contents
    pb.clearContents()
    if old_clipboard is not None:
        pb.setString_forType_(old_clipboard, 'public.utf8-plain-text')

#!/usr/bin/env python3
"""Test AX access to Electron/Chrome apps using AXEnhancedUserInterface."""

import time
import ctypes
import objc
from ApplicationServices import (
    AXUIElementCreateSystemWide,
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeValue,
    AXUIElementSetAttributeValue,
    AXUIElementCopyAttributeNames,
    AXIsProcessTrusted,
    kAXFocusedUIElementAttribute,
    kAXValueAttribute,
    kAXSelectedTextRangeAttribute,
    kAXRoleAttribute,
    kAXErrorSuccess,
)
from AppKit import NSWorkspace

# ctypes setup for extracting CFRange from AXValueRef
_ax_lib = ctypes.cdll.LoadLibrary(
    '/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices'
)

class CFRange(ctypes.Structure):
    _fields_ = [("location", ctypes.c_long), ("length", ctypes.c_long)]

_ax_lib.AXValueGetValue.restype = ctypes.c_bool
_ax_lib.AXValueGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
kAXValueTypeCFRange = 4


def extract_range(ax_range_value):
    ax_ptr = objc.pyobjc_id(ax_range_value)
    cf_range = CFRange()
    if _ax_lib.AXValueGetValue(ax_ptr, kAXValueTypeCFRange, ctypes.byref(cf_range)):
        return cf_range.location, cf_range.length
    return None, None


def walk_ax_tree(element, depth=0, max_depth=8):
    """Walk the AX tree looking for focused or text elements."""
    if depth > max_depth:
        return

    indent = "  " * depth

    # Get role
    err, role = AXUIElementCopyAttributeValue(element, kAXRoleAttribute, None)
    role_str = str(role) if err == kAXErrorSuccess else "?"

    # Check if focused
    err, focused_val = AXUIElementCopyAttributeValue(element, "AXFocused", None)
    is_focused = focused_val if err == kAXErrorSuccess else None

    # Get description
    err, desc = AXUIElementCopyAttributeValue(element, "AXDescription", None)
    desc_str = str(desc)[:50] if err == kAXErrorSuccess and desc else ""

    # Get value (only for text-like roles)
    has_value = False
    if role_str in ("AXTextArea", "AXTextField", "AXTextMarkerRange", "AXWebArea", "AXStaticText"):
        err, val = AXUIElementCopyAttributeValue(element, kAXValueAttribute, None)
        if err == kAXErrorSuccess and val:
            has_value = True
            val_preview = repr(str(val))[:60]
            print(f"{indent}[{role_str}] focused={is_focused} desc={desc_str} VALUE={val_preview}")
        else:
            print(f"{indent}[{role_str}] focused={is_focused} desc={desc_str} (no value, err={err})")
    else:
        extra = f" desc={desc_str}" if desc_str else ""
        focused_marker = " ***FOCUSED***" if is_focused else ""
        print(f"{indent}[{role_str}]{focused_marker}{extra}")

    # If this element is focused and has a value, try to get cursor position
    if is_focused and has_value:
        err, rng = AXUIElementCopyAttributeValue(element, kAXSelectedTextRangeAttribute, None)
        if err == kAXErrorSuccess and rng:
            loc, length = extract_range(rng)
            print(f"{indent}  >>> CURSOR at pos {loc}, selection length {length}")

    # Recurse into children
    err, children = AXUIElementCopyAttributeValue(element, "AXChildren", None)
    if err == kAXErrorSuccess and children:
        for child in children:
            walk_ax_tree(child, depth + 1, max_depth)


print(f"AXIsProcessTrusted: {AXIsProcessTrusted()}")
print("\nYou have 5 seconds to click into a text field in VS Code / Antigravity...\n")
time.sleep(5)

frontmost = NSWorkspace.sharedWorkspace().frontmostApplication()
if not frontmost:
    print("No frontmost app found")
    exit(1)

pid = frontmost.processIdentifier()
name = frontmost.localizedName()
print(f"=== Frontmost app: {name} (PID {pid}) ===\n")

app_element = AXUIElementCreateApplication(pid)

# Step 1: Try without enhanced UI
print("--- Before AXEnhancedUserInterface ---")
err, focused = AXUIElementCopyAttributeValue(app_element, kAXFocusedUIElementAttribute, None)
print(f"Focused element: err={err}")

# Step 2: Enable AXEnhancedUserInterface (tells Chrome/Electron to expose AX tree)
print("\n--- Enabling AXEnhancedUserInterface ---")
set_err = AXUIElementSetAttributeValue(app_element, "AXEnhancedUserInterface", True)
print(f"Set AXEnhancedUserInterface: err={set_err}")

# Give Electron a moment to build its AX tree
time.sleep(0.5)

# Step 3: Try again
print("\n--- After AXEnhancedUserInterface ---")
err, focused = AXUIElementCopyAttributeValue(app_element, kAXFocusedUIElementAttribute, None)
print(f"Focused element: err={err}, focused={focused}")

if err == kAXErrorSuccess and focused:
    err, role = AXUIElementCopyAttributeValue(focused, kAXRoleAttribute, None)
    print(f"Role: {role}")

    attr_err, attrs = AXUIElementCopyAttributeNames(focused, None)
    print(f"Attributes: {list(attrs) if attrs else 'None'}")

    err, value = AXUIElementCopyAttributeValue(focused, kAXValueAttribute, None)
    if err == kAXErrorSuccess and value:
        print(f"Value ({len(str(value))} chars): {repr(str(value))[:100]}")

        err, rng = AXUIElementCopyAttributeValue(focused, kAXSelectedTextRangeAttribute, None)
        if err == kAXErrorSuccess and rng:
            loc, length = extract_range(rng)
            print(f"Cursor position: {loc}, selection length: {length}")
    else:
        print(f"Value: err={err}")
else:
    print("Still no focused element. Walking AX tree to find text fields...\n")

    # Get focused window and walk it
    err, window = AXUIElementCopyAttributeValue(app_element, "AXFocusedWindow", None)
    if err == kAXErrorSuccess and window:
        print("Walking focused window AX tree:\n")
        walk_ax_tree(window, max_depth=6)
    else:
        print(f"No focused window either (err={err})")

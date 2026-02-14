#!/usr/bin/env python3
"""
Key Detection Test Tool
Shows exactly which keys are being pressed to help configure hotkeys.
"""

from pynput import keyboard
from pynput.keyboard import Key

print("="*60)
print("Key Detection Tool")
print("="*60)
print("\nPress any keys to see what's detected...")
print("Press ESC to quit\n")
print("-"*60)

def on_press(key):
    """Show which key was pressed"""
    try:
        # Try to get the character
        print(f"✓ Key pressed: '{key.char}' (character key)")
    except AttributeError:
        # It's a special key
        key_name = str(key).replace('Key.', '')

        # Highlight control keys
        if 'ctrl' in key_name.lower():
            print(f"✓ Key pressed: {key_name} ← CONTROL KEY!")
        elif key_name == 'space':
            print(f"✓ Key pressed: {key_name} ← SPACE BAR!")
        else:
            print(f"✓ Key pressed: {key_name}")

        # Check if it's the escape key to quit
        if key == Key.esc:
            print("\n" + "="*60)
            print("Exiting key detection tool")
            print("="*60)
            return False

def on_release(key):
    """Show which key was released"""
    try:
        print(f"  Released: '{key.char}'")
    except AttributeError:
        key_name = str(key).replace('Key.', '')
        print(f"  Released: {key_name}")

# Start listening
with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()

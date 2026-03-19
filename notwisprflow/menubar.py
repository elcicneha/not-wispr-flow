"""Menu bar UI for Not Wispr Flow.

All menu bar icon management, animations, status updates, menu items,
prompt editing panel, and menu delegate logic.
"""

import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

import objc
from AppKit import (
    NSApplication, NSStatusBar, NSMenu, NSMenuItem,
    NSVariableStatusItemLength, NSObject, NSOnState, NSOffState,
    NSImage, NSData,
    NSEventModifierFlagControl, NSEventModifierFlagCommand,
    NSScrollView, NSTextView, NSPanel, NSButton, NSTextField,
    NSBezelStyleRounded, NSFont, NSColor,
    NSWindowStyleMaskTitled, NSWindowStyleMaskClosable,
    NSBackingStoreBuffered,
    NSLineBreakByWordWrapping,
)
from Foundation import NSMakeRect

from .config import LLM_MODELS
from .preferences import save_preference
from .text_output import type_chunked

logger = logging.getLogger("notwisprflow")


# ============================================================================
# Menu Bar Icon Management
# ============================================================================

class MenuBarIconManager:
    """Manages menu bar icon state and animations."""

    RECORDING_FRAME_INTERVAL = 200   # Recording animation speed (ms)
    PROCESSING_FRAME_INTERVAL = 300  # Processing animation speed (ms)

    def __init__(self):
        self.status_button = None
        self.animation_timer = None
        self.current_frame = 0
        self.current_state = None

        self._icons = {
            'idle': self._load_icon('menubar_idle')
        }

        self._recording_frames = [
            self._load_icon(f'menubar_recording_{i}')
            for i in range(1, 4)
        ]
        self._recording_sequence = [0, 1, 2, 1]

        self._processing_frames = [
            self._load_icon(f'menubar_processing_{i}')
            for i in range(1, 4)
        ]
        self._processing_sequence = [0, 1, 2]

    def _load_icon(self, icon_name):
        """Load a menu bar icon with @2x retina support."""
        if getattr(sys, 'frozen', False):
            base_path = os.path.join(os.path.dirname(sys.executable), '..', 'Resources')
        else:
            # __file__ is notwisprflow/menubar.py, icons are at ../resources/icons
            base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'resources', 'icons')

        icon_1x_path = os.path.join(base_path, f'{icon_name}.png')
        icon_2x_path = os.path.join(base_path, f'{icon_name}@2x.png')

        icon = NSImage.alloc().initWithSize_((22, 22))

        if os.path.exists(icon_1x_path):
            rep = NSImage.alloc().initWithContentsOfFile_(icon_1x_path)
            if rep and rep.representations():
                icon.addRepresentation_(rep.representations()[0])

        if os.path.exists(icon_2x_path):
            rep = NSImage.alloc().initWithContentsOfFile_(icon_2x_path)
            if rep and rep.representations():
                icon.addRepresentation_(rep.representations()[0])

        icon.setTemplate_(True)
        return icon

    def set_button(self, button):
        """Set the NSStatusBarButton to update."""
        self.status_button = button

    def update_state(self, state_name):
        """Update menu bar icon for the given state ('idle', 'recording', 'transcribing')."""
        if state_name == self.current_state:
            return

        self.current_state = state_name

        if state_name == 'recording':
            self._start_recording_animation()
        elif state_name == 'transcribing':
            self._start_processing_animation()
        else:
            self._stop_animation()
            self._set_icon(self._icons.get(state_name, self._icons['idle']))

    def _set_icon(self, icon):
        """Set the menu bar icon (thread-safe)."""
        if self.status_button is not None and icon is not None:
            try:
                self.status_button.performSelectorOnMainThread_withObject_waitUntilDone_(
                    'setImage:', icon, False
                )
            except Exception:
                pass

    def _start_recording_animation(self):
        """Start the recording animation (ping-pong: 1->2->3->2->1)."""
        self._stop_animation()
        self.current_frame = 0

        def animate():
            if self.current_state == 'recording' and self.status_button is not None:
                frame_idx = self._recording_sequence[self.current_frame]
                self._set_icon(self._recording_frames[frame_idx])
                self.current_frame = (self.current_frame + 1) % len(self._recording_sequence)

                self.animation_timer = threading.Timer(self.RECORDING_FRAME_INTERVAL / 1000, animate)
                self.animation_timer.daemon = True
                self.animation_timer.start()

        animate()

    def _start_processing_animation(self):
        """Start the processing animation (loop: 1->2->3->1->2->3)."""
        self._stop_animation()
        self.current_frame = 0

        def animate():
            if self.current_state == 'transcribing' and self.status_button is not None:
                frame_idx = self._processing_sequence[self.current_frame]
                self._set_icon(self._processing_frames[frame_idx])
                self.current_frame = (self.current_frame + 1) % len(self._processing_sequence)

                self.animation_timer = threading.Timer(self.PROCESSING_FRAME_INTERVAL / 1000, animate)
                self.animation_timer.daemon = True
                self.animation_timer.start()

        animate()

    def _stop_animation(self):
        """Stop any running animation."""
        if self.animation_timer is not None:
            self.animation_timer.cancel()
            self.animation_timer = None


# Module singleton
_icon_manager = MenuBarIconManager()

# Menu delegate reference — set by setup_menu_bar()
_menu_delegate = None


def update_icon(state_name):
    """Update the menu bar icon state. ('idle', 'recording', 'transcribing')"""
    _icon_manager.update_state(state_name)


# ============================================================================
# Status Updater (main-thread dispatch for menu item text)
# ============================================================================

class _StatusUpdater(NSObject):
    """NSObject subclass for dispatching status menu item updates to the main thread."""

    def setLoading_(self, _):
        if _menu_delegate:
            _menu_delegate.status_item.setTitle_("Loading speech model\u2026")
            if _menu_delegate.hideable_items:
                for item in _menu_delegate.hideable_items:
                    item.setHidden_(True)

    def setReady_(self, _):
        if _menu_delegate:
            _menu_delegate.status_item.setTitle_("Ready")
            if _menu_delegate.hideable_items:
                for item in _menu_delegate.hideable_items:
                    item.setHidden_(False)

_status_updater = _StatusUpdater.alloc().init()


def create_status_callback(state):
    """Create a status callback for TranscriptionManager that updates the menu bar.

    Args:
        state: AppState instance

    Returns:
        callable(event, value) for use as TranscriptionManager's status_callback
    """
    def on_status_change(event, value):
        if event == "loading_model":
            if value:
                state.is_loading_model = True
                update_icon('transcribing')
                _status_updater.performSelectorOnMainThread_withObject_waitUntilDone_(
                    'setLoading:', None, False
                )
            else:
                state.is_loading_model = False
                if not state.is_recording and not state.is_transcribing:
                    update_icon('idle')
                _status_updater.performSelectorOnMainThread_withObject_waitUntilDone_(
                    'setReady:', None, False
                )

    return on_status_change


# ============================================================================
# Prompt Panel UI
# ============================================================================

def _make_text_view(width, height, editable=True, font_size=13):
    """Create an NSScrollView + NSTextView pair for text editing."""
    scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
    scroll.setHasVerticalScroller_(True)
    scroll.setBorderType_(2)  # NSBezelBorder
    inner_w = width - 4
    tv = NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, inner_w, height))
    tv.setMinSize_(NSMakeRect(0, 0, inner_w, height).size)
    tv.setMaxSize_(NSMakeRect(0, 0, inner_w, 10000).size)
    tv.setVerticallyResizable_(True)
    tv.setHorizontallyResizable_(False)
    tv.textContainer().setWidthTracksTextView_(True)
    tv.setFont_(NSFont.systemFontOfSize_(font_size))
    tv.setAllowsUndo_(True)
    tv.setEditable_(editable)
    tv.setSelectable_(True)
    if not editable:
        tv.setBackgroundColor_(NSColor.controlBackgroundColor())
        tv.setTextColor_(NSColor.secondaryLabelColor())
    scroll.setDocumentView_(tv)
    return scroll, tv


class _PromptPanelController(NSObject):
    """Controller for the Personal Prompt editing panel with collapsible system prompt sections."""
    _panel = None
    _subtitle = None
    _personal_scroll = None
    _personal_tv = None
    _sections = None
    _cancel_btn = None
    _save_btn = None
    _should_save = False
    _state = None  # AppState reference, set before use

    def doSave_(self, sender):
        self._should_save = True
        NSApplication.sharedApplication().stopModal()

    def doCancel_(self, sender):
        self._should_save = False
        NSApplication.sharedApplication().stopModal()

    def toggleSection_(self, sender):
        idx = sender.tag()
        sec = self._sections[idx]
        sec["expanded"] = not sec["expanded"]
        arrow = "\u25BC" if sec["expanded"] else "\u25B6"
        sender.setTitle_(f"{arrow} {sec['label']}")
        self._relayout()

    def editSection_(self, sender):
        idx = sender.tag()
        sec = self._sections[idx]
        state = self._state

        if not sec["editing"]:
            sec["editing"] = True
            sec["tv"].setEditable_(True)
            sec["tv"].setBackgroundColor_(NSColor.textBackgroundColor())
            sec["tv"].setTextColor_(NSColor.labelColor())
            self._panel.makeFirstResponder_(sec["tv"])
            sender.setTitle_("Save")
            sec["reset_btn"].setHidden_(False)
        else:
            new_text = sec["tv"].string()
            has_context = sec["variant"] == "with_context"
            if state.llm_processor:
                preset = state.llm_processor.get_preset_system_prompt(has_context)
                if new_text.strip() == preset.strip():
                    state.llm_processor.reset_custom_system_prompt(sec["variant"])
                else:
                    state.llm_processor.set_custom_system_prompt(sec["variant"], new_text)
            sec["tv"].setEditable_(False)
            sec["tv"].setBackgroundColor_(NSColor.controlBackgroundColor())
            sec["tv"].setTextColor_(NSColor.secondaryLabelColor())
            sec["editing"] = False
            sender.setTitle_("Edit")
            has_custom = state.llm_processor.has_custom_system_prompt(sec["variant"]) if state.llm_processor else False
            if has_custom:
                sec["info"].setStringValue_("Custom override")
            else:
                preset_name = state.llm_processor._prompt_config.get("display", "") if state.llm_processor else ""
                sec["info"].setStringValue_(f"From preset: {preset_name}")
            sec["reset_btn"].setHidden_(not has_custom)

    def resetSection_(self, sender):
        idx = sender.tag()
        sec = self._sections[idx]
        state = self._state
        has_context = sec["variant"] == "with_context"
        preset_text = ""
        preset_name = ""
        if state.llm_processor:
            state.llm_processor.reset_custom_system_prompt(sec["variant"])
            preset_text = state.llm_processor.get_preset_system_prompt(has_context)
            preset_name = state.llm_processor._prompt_config.get("display", "")
        sec["tv"].setString_(preset_text)
        sec["tv"].setEditable_(False)
        sec["tv"].setBackgroundColor_(NSColor.controlBackgroundColor())
        sec["tv"].setTextColor_(NSColor.secondaryLabelColor())
        sec["editing"] = False
        sec["edit_btn"].setTitle_("Edit")
        sec["reset_btn"].setHidden_(True)
        sec["info"].setStringValue_(f"From preset: {preset_name}")

    def _relayout(self, animate=True):
        """Reposition all views and resize panel based on current section expand states."""
        W = 420
        PAD = 20
        IW = W - 2 * PAD

        top = 8
        sub_top = top
        top += 36
        pp_top = top
        top += 128

        sec_layout = []
        for sec in self._sections:
            layout = {"disc_top": top}
            top += 28
            if sec["expanded"]:
                layout["info_top"] = top
                top += 22
                layout["scroll_top"] = top
                top += 144
                layout["btn_top"] = top
                top += 30
            sec_layout.append(layout)

        top += 8
        btn_top = top
        top += 42
        total_h = top

        def mac_y(t, h):
            return total_h - t - h

        self._subtitle.setFrame_(NSMakeRect(PAD, mac_y(sub_top, 32), IW, 32))
        self._personal_scroll.setFrame_(NSMakeRect(PAD, mac_y(pp_top, 120), IW, 120))

        state = self._state
        for sec, lay in zip(self._sections, sec_layout):
            sec["disclosure"].setFrame_(NSMakeRect(PAD, mac_y(lay["disc_top"], 24), IW, 24))
            if sec["expanded"]:
                sec["info"].setFrame_(NSMakeRect(PAD, mac_y(lay["info_top"], 18), IW, 18))
                sec["scroll"].setFrame_(NSMakeRect(PAD, mac_y(lay["scroll_top"], 140), IW, 140))
                sec["edit_btn"].setFrame_(NSMakeRect(PAD, mac_y(lay["btn_top"], 24), 60, 24))
                sec["reset_btn"].setFrame_(NSMakeRect(PAD + 70, mac_y(lay["btn_top"], 24), 120, 24))

            for key in ["info", "scroll", "edit_btn"]:
                sec[key].setHidden_(not sec["expanded"])
            if sec["expanded"]:
                has_custom = state.llm_processor.has_custom_system_prompt(sec["variant"]) if state.llm_processor else False
                sec["reset_btn"].setHidden_(not (has_custom or sec["editing"]))
            else:
                sec["reset_btn"].setHidden_(True)

        self._cancel_btn.setFrame_(NSMakeRect(W - 190, mac_y(btn_top, 30), 80, 30))
        self._save_btn.setFrame_(NSMakeRect(W - 100, mac_y(btn_top, 30), 80, 30))

        old_frame = self._panel.frame()
        content_rect = NSMakeRect(0, 0, W, total_h)
        new_frame = self._panel.frameRectForContentRect_(content_rect)
        top_y = old_frame.origin.y + old_frame.size.height
        final = NSMakeRect(old_frame.origin.x, top_y - new_frame.size.height,
                           new_frame.size.width, new_frame.size.height)
        if animate:
            self._panel.setFrame_display_animate_(final, True, True)
        else:
            self._panel.setFrame_display_(final, True)


# ============================================================================
# Menu Delegate
# ============================================================================

class MenuDelegate(NSObject):
    """Handles all menu bar actions."""
    shutdown_event = None
    paste_mode_item = None
    llm_model_items = None
    personal_prompt_item = None
    status_item = None
    hideable_items = None
    _state = None  # AppState reference, set during setup

    def retypeLast_(self, sender):
        state = self._state
        with state.lock:
            text = state.last_transcription
        if text:
            threading.Thread(
                target=type_chunked,
                args=(text,),
                daemon=True
            ).start()

    def togglePasteMode_(self, sender):
        state = self._state
        state.use_type_mode = not state.use_type_mode
        if self.paste_mode_item:
            self.paste_mode_item.setState_(
                NSOffState if state.use_type_mode else NSOnState
            )
        mode_name = "Type" if state.use_type_mode else "Paste"
        logger.debug(f"Text insertion mode: {mode_name}")

    def selectLLMModel_(self, sender):
        state = self._state
        model_name = sender.representedObject()
        if model_name is None:
            return

        state.llm_model = model_name
        if state.llm_processor:
            state.llm_processor.switch_model(model_name)

        save_preference("llm_model", model_name)

        if self.llm_model_items:
            for name, item in self.llm_model_items.items():
                item.setState_(NSOnState if name == model_name else NSOffState)

        display = LLM_MODELS.get(model_name, {}).get("display", model_name)
        logger.info(f"LLM model switched to: {display} ({model_name})")

    def editPersonalPrompt_(self, sender):
        state = self._state
        W = 420
        PAD = 20
        IW = W - 2 * PAD

        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, W, 100),
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable,
            NSBackingStoreBuffered,
            False,
        )
        panel.setTitle_("Personal Prompt")
        content = panel.contentView()

        ctrl = _PromptPanelController.alloc().init()
        ctrl._panel = panel
        ctrl._state = state

        # Subtitle
        subtitle = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, IW, 32))
        subtitle.setStringValue_("Additional instructions for the LLM.\nLeave empty to disable.")
        subtitle.setBezeled_(False)
        subtitle.setDrawsBackground_(False)
        subtitle.setEditable_(False)
        subtitle.setSelectable_(False)
        subtitle.setFont_(NSFont.systemFontOfSize_(12))
        subtitle.setTextColor_(NSColor.secondaryLabelColor())
        subtitle.setLineBreakMode_(NSLineBreakByWordWrapping)
        content.addSubview_(subtitle)
        ctrl._subtitle = subtitle

        # Personal prompt text view
        pp_scroll, pp_tv = _make_text_view(IW, 120)
        pp_tv.setString_((state.llm_processor._personal_prompt or "") if state.llm_processor else "")
        content.addSubview_(pp_scroll)
        ctrl._personal_scroll = pp_scroll
        ctrl._personal_tv = pp_tv

        # System prompt sections (collapsible)
        ctrl._sections = []
        section_defs = [
            ("with_context", "System Prompt (with context)"),
            ("no_context", "System Prompt (no context)"),
        ]
        for i, (variant, label) in enumerate(section_defs):
            has_context = variant == "with_context"

            disc = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, IW, 24))
            disc.setTitle_(f"\u25B6 {label}")
            disc.setBordered_(False)
            disc.setFont_(NSFont.boldSystemFontOfSize_(12))
            disc.setAlignment_(0)
            disc.setTarget_(ctrl)
            disc.setAction_("toggleSection:")
            disc.setTag_(i)
            content.addSubview_(disc)

            info = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, IW, 18))
            info.setBezeled_(False)
            info.setDrawsBackground_(False)
            info.setEditable_(False)
            info.setSelectable_(False)
            info.setFont_(NSFont.systemFontOfSize_(11))
            info.setTextColor_(NSColor.tertiaryLabelColor())
            content.addSubview_(info)

            sys_scroll, sys_tv = _make_text_view(IW, 140, editable=False, font_size=12)
            content.addSubview_(sys_scroll)

            edit_btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, 60, 24))
            edit_btn.setTitle_("Edit")
            edit_btn.setBezelStyle_(NSBezelStyleRounded)
            edit_btn.setFont_(NSFont.systemFontOfSize_(11))
            edit_btn.setTarget_(ctrl)
            edit_btn.setAction_("editSection:")
            edit_btn.setTag_(i)
            content.addSubview_(edit_btn)

            reset_btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, 120, 24))
            reset_btn.setTitle_("Reset to Preset")
            reset_btn.setBezelStyle_(NSBezelStyleRounded)
            reset_btn.setFont_(NSFont.systemFontOfSize_(11))
            reset_btn.setTarget_(ctrl)
            reset_btn.setAction_("resetSection:")
            reset_btn.setTag_(i)
            content.addSubview_(reset_btn)

            has_custom = state.llm_processor.has_custom_system_prompt(variant) if state.llm_processor else False
            if has_custom:
                sys_text = state.llm_processor.get_active_system_prompt(has_context)
                info_text = "Custom override"
            else:
                sys_text = state.llm_processor.get_preset_system_prompt(has_context) if state.llm_processor else ""
                preset_name = state.llm_processor._prompt_config.get("display", "") if state.llm_processor else ""
                info_text = f"From preset: {preset_name}"

            sys_tv.setString_(sys_text)
            info.setStringValue_(info_text)

            ctrl._sections.append({
                "variant": variant, "label": label,
                "disclosure": disc, "info": info,
                "scroll": sys_scroll, "tv": sys_tv,
                "edit_btn": edit_btn, "reset_btn": reset_btn,
                "expanded": False, "editing": False,
            })

        # Cancel button
        cancel_btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, 80, 30))
        cancel_btn.setTitle_("Cancel")
        cancel_btn.setBezelStyle_(NSBezelStyleRounded)
        cancel_btn.setKeyEquivalent_("\x1b")
        content.addSubview_(cancel_btn)
        ctrl._cancel_btn = cancel_btn

        # Save button
        save_btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, 80, 30))
        save_btn.setTitle_("Save")
        save_btn.setBezelStyle_(NSBezelStyleRounded)
        save_btn.setKeyEquivalent_("s")
        save_btn.setKeyEquivalentModifierMask_(NSEventModifierFlagCommand)
        content.addSubview_(save_btn)
        ctrl._save_btn = save_btn

        save_btn.setTarget_(ctrl)
        save_btn.setAction_("doSave:")
        cancel_btn.setTarget_(ctrl)
        cancel_btn.setAction_("doCancel:")

        ctrl._relayout(animate=False)
        panel.center()
        panel.makeFirstResponder_(pp_tv)

        app = NSApplication.sharedApplication()
        app.runModalForWindow_(panel)
        panel.orderOut_(None)

        if ctrl._should_save:
            new_personal = pp_tv.string()
            if state.llm_processor:
                state.llm_processor.set_personal_prompt(new_personal)

            for sec in ctrl._sections:
                if sec["editing"] and state.llm_processor:
                    new_text = sec["tv"].string()
                    has_ctx = sec["variant"] == "with_context"
                    preset = state.llm_processor.get_preset_system_prompt(has_ctx)
                    if new_text.strip() == preset.strip():
                        state.llm_processor.reset_custom_system_prompt(sec["variant"])
                    else:
                        state.llm_processor.set_custom_system_prompt(sec["variant"], new_text)

            has_active = bool(new_personal.strip())
            if not has_active and state.llm_processor:
                has_active = (
                    state.llm_processor.has_custom_system_prompt("with_context") or
                    state.llm_processor.has_custom_system_prompt("no_context")
                )
            if self.personal_prompt_item:
                self.personal_prompt_item.setTitle_(
                    "Personal Prompt (Active)" if has_active else "Personal Prompt..."
                )

    def openLogs_(self, sender):
        log_dir = Path.home() / 'Library' / 'Logs' / 'NotWisprFlow'
        log_file = log_dir / 'notwisprflow.log'

        if log_file.exists():
            subprocess.run(['open', str(log_file)], check=False)
        elif log_dir.exists():
            subprocess.run(['open', str(log_dir)], check=False)
        else:
            logger.warning("Log file not found")

    def quit_(self, sender):
        if self.shutdown_event:
            self.shutdown_event.set()
        NSApplication.sharedApplication().terminate_(None)

    def validateMenuItem_(self, item):
        if item.action() == b"retypeLast:":
            return self._state.last_transcription is not None
        return True


# ============================================================================
# Menu Bar Setup
# ============================================================================

def setup_menu_bar(shutdown_event, state):
    """Create a menu bar status icon with all menu items.

    Args:
        shutdown_event: threading.Event for shutdown signaling
        state: AppState instance

    Returns:
        (status_item, delegate) — keep references alive
    """
    global _menu_delegate

    app = NSApplication.sharedApplication()

    status_bar = NSStatusBar.systemStatusBar()
    status_item = status_bar.statusItemWithLength_(NSVariableStatusItemLength)
    button = status_item.button()

    _icon_manager.set_button(button)
    update_icon('idle')

    delegate = MenuDelegate.alloc().init()
    delegate.shutdown_event = shutdown_event
    delegate._state = state

    menu = NSMenu.alloc().init()
    menu.setMinimumWidth_(180)

    # Status — always visible
    status_menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Loading speech model\u2026", None, ""
    )
    status_menu_item.setEnabled_(False)
    menu.addItem_(status_menu_item)
    delegate.status_item = status_menu_item

    menu.addItem_(NSMenuItem.separatorItem())

    hideable_items = []

    # Retype Last
    retype_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Retype last transcript", "retypeLast:", "c"
    )
    retype_item.setKeyEquivalentModifierMask_(NSEventModifierFlagControl | NSEventModifierFlagCommand)
    retype_item.setTarget_(delegate)
    menu.addItem_(retype_item)
    hideable_items.append(retype_item)

    sep1 = NSMenuItem.separatorItem()
    menu.addItem_(sep1)
    hideable_items.append(sep1)

    # Paste Mode toggle
    paste_mode_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Paste Mode", "togglePasteMode:", ""
    )
    paste_mode_item.setTarget_(delegate)
    paste_mode_item.setState_(NSOffState if state.use_type_mode else NSOnState)
    delegate.paste_mode_item = paste_mode_item
    menu.addItem_(paste_mode_item)
    hideable_items.append(paste_mode_item)

    # LLM Model submenu
    llm_menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "LLM Model", None, ""
    )
    llm_submenu = NSMenu.alloc().init()
    llm_model_items = {}
    current_model = state.llm_model

    available_providers = state.llm_processor.get_available_providers() if state.llm_processor else {None}

    last_group = "FIRST"
    for model_name, model_info in LLM_MODELS.items():
        provider = model_info.get("provider")
        if provider not in available_providers:
            continue

        group = model_info.get("group")
        if group != last_group and last_group != "FIRST":
            llm_submenu.addItem_(NSMenuItem.separatorItem())
        last_group = group

        item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            model_info["display"], "selectLLMModel:", ""
        )
        item.setTarget_(delegate)
        item.setRepresentedObject_(model_name)
        item.setState_(NSOnState if model_name == current_model else NSOffState)
        llm_submenu.addItem_(item)
        llm_model_items[model_name] = item

    llm_menu_item.setSubmenu_(llm_submenu)
    delegate.llm_model_items = llm_model_items
    menu.addItem_(llm_menu_item)
    hideable_items.append(llm_menu_item)

    # Personal Prompt
    has_personal = bool(state.llm_processor and state.llm_processor._personal_prompt)
    personal_title = "Prompts..."
    personal_prompt_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        personal_title, "editPersonalPrompt:", ""
    )
    personal_prompt_item.setTarget_(delegate)
    delegate.personal_prompt_item = personal_prompt_item
    menu.addItem_(personal_prompt_item)
    hideable_items.append(personal_prompt_item)

    sep2 = NSMenuItem.separatorItem()
    menu.addItem_(sep2)
    hideable_items.append(sep2)

    # Open Logs
    logs_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Open Logs", "openLogs:", ""
    )
    logs_item.setTarget_(delegate)
    menu.addItem_(logs_item)

    menu.addItem_(NSMenuItem.separatorItem())

    # Quit
    quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Quit Not Wispr Flow", "quit:", "q"
    )
    quit_item.setTarget_(delegate)
    menu.addItem_(quit_item)

    delegate.hideable_items = hideable_items

    status_item.setMenu_(menu)

    _menu_delegate = delegate

    return status_item, delegate

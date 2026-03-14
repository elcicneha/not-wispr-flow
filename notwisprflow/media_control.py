#!/usr/bin/env python3
"""
Universal media playback control for Not Wispr Flow.

Uses macOS private MediaRemote.framework to send PAUSE/PLAY commands
to whatever app is the current Now Playing source (Spotify, YouTube
in browser, VLC, podcasts, etc.).

Detects playing state via macOS power assertions — apps that produce
audio output create a "Playing audio" power assertion which is checked
before pausing, so we only resume if something was actually playing.
"""

import objc
import subprocess

_MR_COMMAND_PLAY = 0
_MR_COMMAND_PAUSE = 1

# Load MediaRemote framework for sending commands
_has_media_remote = False
_send_command = None

try:
    _mr_bundle = objc.loadBundle(
        'MediaRemote', {},
        bundle_path='/System/Library/PrivateFrameworks/MediaRemote.framework'
    )
    _funcs = {}
    objc.loadBundleFunctions(_mr_bundle, _funcs, [
        ('MRMediaRemoteSendCommand', b'Bi@'),
    ])
    _send_command = _funcs.get('MRMediaRemoteSendCommand')
    _has_media_remote = _send_command is not None
except Exception:
    pass


def is_media_playing():
    """Check if system media is currently playing via macOS power assertions.

    Apps producing audio output (browsers, Spotify, Music, etc.) create
    a "Playing audio" power assertion. This clears a few seconds after
    audio stops, making it a reliable indicator of active playback.
    """
    try:
        result = subprocess.run(
            ['pmset', '-g', 'assertions'],
            capture_output=True, text=True, timeout=2
        )
        return 'Playing audio' in result.stdout
    except Exception:
        return False


def pause_media(logger):
    """Pause system media if currently playing. Returns True if something was playing."""
    if not _has_media_remote:
        return False
    try:
        if not is_media_playing():
            return False
        _send_command(_MR_COMMAND_PAUSE, None)
        logger.debug("Paused system media")
        return True
    except Exception as e:
        logger.debug(f"Media pause failed: {e}")
        return False


def resume_media(logger):
    """Resume system media playback."""
    if not _has_media_remote:
        return
    try:
        _send_command(_MR_COMMAND_PLAY, None)
        logger.debug("Resumed system media")
    except Exception as e:
        logger.debug(f"Media resume failed: {e}")

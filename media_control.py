#!/usr/bin/env python3
"""
Universal media playback control for Not Wispr Flow.

Uses macOS private MediaRemote.framework to send PAUSE/PLAY commands
to whatever app is the current Now Playing source (Spotify, YouTube
in browser, VLC, podcasts, etc.).

Also queries playing state via MRMediaRemoteGetNowPlayingApplicationIsPlaying
so we only resume if something was actually playing when we paused.
"""

import objc
import ctypes
import threading

_MR_COMMAND_PLAY = 0
_MR_COMMAND_PAUSE = 1

# Load MediaRemote framework via PyObjC (handles block callbacks properly)
_has_media_remote = False
_send_command = None
_get_is_playing = None
_global_queue = None

try:
    _mr_bundle = objc.loadBundle(
        'MediaRemote', {},
        bundle_path='/System/Library/PrivateFrameworks/MediaRemote.framework'
    )
    _funcs = {}
    objc.loadBundleFunctions(_mr_bundle, _funcs, [
        ('MRMediaRemoteSendCommand', b'Bi@'),
        ('MRMediaRemoteGetNowPlayingApplicationIsPlaying', b'v@@?'),
    ])
    _send_command = _funcs.get('MRMediaRemoteSendCommand')
    _get_is_playing = _funcs.get('MRMediaRemoteGetNowPlayingApplicationIsPlaying')

    # Get a global dispatch queue for the async callback
    _ld = ctypes.cdll.LoadLibrary('/usr/lib/libdispatch.dylib')
    _ld.dispatch_get_global_queue.argtypes = [ctypes.c_long, ctypes.c_ulong]
    _ld.dispatch_get_global_queue.restype = ctypes.c_void_p
    _queue_ptr = _ld.dispatch_get_global_queue(0, 0)
    if _queue_ptr:
        _global_queue = objc.objc_object(c_void_p=ctypes.c_void_p(_queue_ptr))

    _has_media_remote = _send_command is not None
except Exception:
    pass


def is_media_playing():
    """Check if system media is currently playing. Returns True if playing."""
    if not _get_is_playing or not _global_queue:
        return False
    result = [False]
    event = threading.Event()

    def callback(is_playing):
        result[0] = bool(is_playing)
        event.set()

    try:
        _get_is_playing(_global_queue, callback)
        event.wait(timeout=1.0)
        return result[0]
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

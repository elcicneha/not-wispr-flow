#!/usr/bin/env python3
"""
setup.py for building Not Wispr Flow macOS .app bundle with py2app

This configuration packages the Not Wispr Flow voice dictation tool as a standalone
macOS application with all dependencies bundled, including native libraries.
"""

import sys
import os
import glob
from setuptools import setup

# Increase recursion limit for py2app's dependency analysis
# (needed for complex packages like scipy, numpy, etc.)
sys.setrecursionlimit(10000)

# Detect Python version for paths (works with any Python 3.x version)
PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"

# Find the site-packages directory (works in both venv and system Python)
def find_site_packages():
    """Find the site-packages directory for the current Python environment."""
    for path in sys.path:
        if 'site-packages' in path:
            return path
    # Fallback: use venv path
    return f"venv/lib/python{PYTHON_VERSION}/site-packages"

SITE_PACKAGES = find_site_packages()

APP = ['main.py']
DATA_FILES = [
    ('', [
        'icons/menubar_idle.png',
        'icons/menubar_idle@2x.png',
        # Recording animation frames (3 frames, ping-pong: 1→2→3→2→1)
        'icons/menubar_recording_1.png',
        'icons/menubar_recording_1@2x.png',
        'icons/menubar_recording_2.png',
        'icons/menubar_recording_2@2x.png',
        'icons/menubar_recording_3.png',
        'icons/menubar_recording_3@2x.png',
        # Processing animation frames (3 frames, loop: 1→2→3→1→2→3)
        'icons/menubar_processing_1.png',
        'icons/menubar_processing_1@2x.png',
        'icons/menubar_processing_2.png',
        'icons/menubar_processing_2@2x.png',
        'icons/menubar_processing_3.png',
        'icons/menubar_processing_3@2x.png'
    ]),
    # MLX Metal shader library (will be moved to Frameworks by install script)
    ('', [
        os.path.join(SITE_PACKAGES, 'mlx/lib/mlx.metallib'),
    ])
]

OPTIONS = {
    # Don't emulate command-line arguments
    'argv_emulation': False,

    # App icon
    'iconfile': 'icons/icon_1.icns',

    # App metadata and permissions
    'plist': {
        'CFBundleName': 'Not Wispr Flow',
        'CFBundleDisplayName': 'Not Wispr Flow Voice Dictation',
        'CFBundleIdentifier': 'com.notwisprflow.dictation',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',

        # Permission descriptions (shown in permission prompts)
        'NSMicrophoneUsageDescription':
            'Not Wispr Flow needs microphone access to record your voice for dictation.',
        'NSAppleEventsUsageDescription':
            'Not Wispr Flow needs to control keyboard input to type transcribed text.',

        # Run as background agent (no Dock icon)
        'LSUIElement': True,

        # Allow foreground for permission prompts
        'LSBackgroundOnly': False,

        # High resolution support
        'NSHighResolutionCapable': True,
    },

    # Explicitly include these packages and their dependencies
    'packages': [
        'numpy',
        'sounddevice',
        '_sounddevice_data',
        'pynput',
        'av',
        'huggingface_hub',
        'tokenizers',
        'torch',
        'torchaudio',
        'ApplicationServices',
    ],

    # Include specific compiled extensions
    'includes': [
        # NumPy compiled modules
        'numpy.core._multiarray_umath',
        'numpy.linalg._umath_linalg',

        # MLX modules (namespace package with compiled extensions)
        'mlx.core',
        'mlx.core.metal',
        'mlx.nn',
        'mlx.nn.layers',
        'mlx.utils',
        'mlx._reprlib_fix',

        # mlx_whisper modules
        'mlx_whisper',
        'mlx_whisper.transcribe',
        'mlx_whisper.audio',
        'mlx_whisper.load_models',

        # Other critical imports
        'cffi',
        'pycparser',
    ],

    # Frameworks to bundle (PyObjC frameworks for keyboard control)
    'frameworks': [
        os.path.join(SITE_PACKAGES, 'mlx/lib/libmlx.dylib'),
    ],

    # Don't include these packages (reduce bundle size)
    'excludes': [
        'matplotlib',
        'PIL',
        'tkinter',
    ],

    # Force inclusion of resources (py2app auto-detects package data)
    'resources': [],

    # Strip debug symbols to reduce size
    'strip': True,

    # Optimization level (2 = remove docstrings)
    'optimize': 2,

    # Semi-standalone mode (include Python.framework)
    'semi_standalone': False,

    # Code signing is done post-build in install_service.sh
}

setup(
    name='Not Wispr Flow',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)

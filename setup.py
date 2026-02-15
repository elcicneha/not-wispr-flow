#!/usr/bin/env python3
"""
setup.py for building Whispr macOS .app bundle with py2app

This configuration packages the Whispr voice dictation tool as a standalone
macOS application with all dependencies bundled, including native libraries.
"""

import sys
from setuptools import setup

# Increase recursion limit for py2app's dependency analysis
# (needed for complex packages like scipy, numpy, etc.)
sys.setrecursionlimit(10000)

APP = ['whispr_clone.py']
DATA_FILES = []

OPTIONS = {
    # Don't emulate command-line arguments
    'argv_emulation': False,

    # App icon
    'iconfile': 'icons/whispr_icon_1.icns',

    # App metadata and permissions
    'plist': {
        'CFBundleName': 'Whispr',
        'CFBundleDisplayName': 'Whispr Voice Dictation',
        'CFBundleIdentifier': 'com.whispr.dictation',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',

        # Permission descriptions (shown in permission prompts)
        'NSMicrophoneUsageDescription':
            'Whispr needs microphone access to record your voice for dictation.',
        'NSAppleEventsUsageDescription':
            'Whispr needs to control keyboard input to type transcribed text.',

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
        'faster_whisper',
        'ctranslate2',
        'onnxruntime',
        'av',
        'huggingface_hub',
        'tokenizers',
    ],

    # Include specific compiled extensions
    'includes': [
        # NumPy compiled modules
        'numpy.core._multiarray_umath',
        'numpy.linalg._umath_linalg',

        # Other critical imports
        'cffi',
        'pycparser',
    ],

    # Frameworks to bundle (PyObjC frameworks for keyboard control)
    'frameworks': [],

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
    name='Whispr',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)

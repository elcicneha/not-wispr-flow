#!/usr/bin/env python3
"""
Component validation script for Whispr Clone.
Tests all major components without requiring keyboard interaction.
"""

import sys
import time
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

def test_audio_devices():
    """Test if audio devices are available"""
    print("\n1. Testing audio devices...")
    try:
        devices = sd.query_devices()
        print(f"   ✓ Found {len(devices)} audio devices")

        input_device = sd.query_devices(kind='input')
        print(f"   ✓ Default input: {input_device['name']}")
        return True
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

def test_microphone_recording():
    """Test if microphone recording works"""
    print("\n2. Testing microphone recording...")
    try:
        duration = 1.0  # 1 second
        sample_rate = 16000

        print(f"   Recording {duration}s of audio...")
        recording = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype='int16'
        )
        sd.wait()

        print(f"   ✓ Recorded {len(recording)} samples")
        print(f"   ✓ Audio shape: {recording.shape}")

        # Check if any sound was captured
        max_amplitude = np.max(np.abs(recording))
        print(f"   ✓ Max amplitude: {max_amplitude}")

        return True
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

def test_whisper_model():
    """Test Whisper model loading"""
    print("\n3. Testing Whisper model loading...")
    try:
        print("   Loading base model...")
        start = time.time()
        model = WhisperModel('base', device='cpu', compute_type='int8')
        end = time.time()

        print(f"   ✓ Model loaded in {end-start:.2f} seconds")
        return True, model
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False, None

def test_whisper_transcription(model):
    """Test Whisper transcription with sample audio"""
    print("\n4. Testing Whisper transcription...")
    try:
        # Generate a simple sine wave as test audio (440Hz, 1 second)
        sample_rate = 16000
        duration = 1.0
        frequency = 440

        t = np.linspace(0, duration, int(sample_rate * duration))
        test_audio = np.sin(2 * np.pi * frequency * t).astype(np.float32) * 0.3

        print("   Transcribing test audio...")
        segments, info = model.transcribe(
            test_audio,
            language="en",
            beam_size=5,
            vad_filter=True
        )

        # Extract text
        text = "".join(segment.text for segment in segments).strip()

        print(f"   ✓ Transcription completed")
        print(f"   Result: '{text}' (expected empty for sine wave)")
        print(f"   Language: {info.language} (probability: {info.language_probability:.2f})")

        return True
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

def test_keyboard_controller():
    """Test keyboard controller initialization"""
    print("\n5. Testing keyboard controller...")
    try:
        from pynput.keyboard import Controller, Key

        controller = Controller()
        print("   ✓ Keyboard controller initialized")
        print("   Note: Actual typing requires Accessibility permissions")
        print("         This will be tested when you run the main app")

        return True
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

def main():
    print("="*60)
    print("Whispr Clone - Component Validation")
    print("="*60)

    results = []

    # Test audio devices
    results.append(("Audio Devices", test_audio_devices()))

    # Test microphone recording
    results.append(("Microphone Recording", test_microphone_recording()))

    # Test Whisper model
    model_ok, model = test_whisper_model()
    results.append(("Whisper Model", model_ok))

    # Test transcription if model loaded
    if model_ok and model:
        results.append(("Whisper Transcription", test_whisper_transcription(model)))

    # Test keyboard controller
    results.append(("Keyboard Controller", test_keyboard_controller()))

    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status:8} {name}")

    all_passed = all(result[1] for result in results)

    print("\n" + "="*60)
    if all_passed:
        print("✓ All components working!")
        print("\nYou can now run the main application:")
        print("  python3 whispr_clone.py")
    else:
        print("✗ Some components failed")
        print("\nPlease check the errors above and:")
        print("  - Ensure PortAudio is installed (brew install portaudio)")
        print("  - Grant microphone permissions in System Preferences")
        print("  - Check your internet connection for model download")
    print("="*60 + "\n")

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())

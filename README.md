# Not Wispr Flow

# Not Wispr Flow

A free, offline voice-to-text tool for **macOS**. Hold a key, speak, release — your words get typed wherever your cursor is. Works in any app.

Everything runs locally on your machine. No cloud, no subscription, no data leaving your computer. It uses OpenAI's Whisper model through Apple's MLX framework, so transcription happens on your Mac's GPU.

**Requirements:** Mac with Apple Silicon (M1/M2/M3/M4) • ~1-3GB RAM based on the model you choose.

---

## About this project

This was inspired by [Wispr Flow](https://wisprflow.ai/). I genuinely admire what they've built, the product is commendable. This project doesn't come close to the level of quality and features they offer. 

But this gets the job done for free and runs entirely on your own machine. The tradeoff is it uses some of your RAM (~2-3GB) since the AI model sits in memory while the app is running.

---

## Installation

### Option 1: Homebrew (Recommended - Easiest)

```bash
brew tap elcicneha/tap
brew install --cask not-wispr-flow
```

### Option 2: Download DMG

1. Download the latest release: **[Releases Page](https://github.com/elcicneha/not-wispr-flow/releases)**
2. Open the `.dmg` file
3. Drag "Not Wispr Flow" to Applications folder
4. **First time only**: Right-click the app and select "Open" (this bypasses macOS security for unsigned apps)
5. Click "Open" in the dialog

### First Launch Setup

Grant these permissions in **System Settings → Privacy & Security**:
- Microphone
- Accessibility
- Input Monitoring

**That's it!** Launch "Not Wispr Flow" from Applications or Spotlight.

---

## For Developers: Build From Source

**Setup:**
```bash
# Clone the repository
git clone https://github.com/elcicneha/not-wispr-flow.git
cd not-wispr-flow

# Install system dependencies
brew install python portaudio

# Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Run in Terminal:**
```bash
source venv/bin/activate
python3 main.py
```
Grant permissions for Terminal in System Settings.

**Or build as .app:**
```bash
# Create certificate (one-time)
./scripts/create_certificate.sh

# Build and install
./scripts/install_service.sh
```

Grant permissions for "Not Wispr Flow" in System Settings.

---

## How to use

* **Hold mode:** Hold Control key → speak → release
* **Toggle mode:** Press Control + Space → speak → press Control again

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Hotkey doesn't work | Check permissions (all 3 must be enabled) |
| No text appears | Enable Accessibility permission |
| Logs | `~/Library/Logs/NotWisprFlow/notwisprflow.log` |

---

## Customization

**Note:** Customization requires building from source (see "For Developers" section above).

Edit [config.py](config.py) to change:
- **Whisper models:** `whisper-large-v3-turbo` (default), `whisper-small`, `whisper-base`
- **Hotkeys:** Control key (default), Function key, Command key, Option key, etc.

Then rebuild: `./scripts/install_service.sh`

> A GUI for configuration is planned for future releases.

---

Inspired by [Wispr Flow](https://wisprflow.ai) • Uses [OpenAI Whisper](https://github.com/openai/whisper) via [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper)

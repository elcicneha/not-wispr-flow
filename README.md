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

## Setup

**Step 1: Install Homebrew** (skip if you already have it)

Open Terminal (search "Terminal" in Spotlight) and paste:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
Follow the instructions, then close and reopen Terminal.

**Step 2: Install required software**
```bash
brew install python git portaudio
```

**Step 3: Download the code**

Want the code in a specific folder (like Documents or Desktop)? Open that folder in Finder, right-click on the folder, and select **New Terminal at Folder**. Otherwise, just use the Terminal you already have open.

Then paste:
```bash
git clone https://github.com/elcicneha/not-wispr-flow.git
cd not-wispr-flow
```

**Step 4: Set up the environment**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Done! Now pick how you want to run it:

---

## Pick one: Terminal or Mac App

### A) Terminal Method (Simpler setup, but you run commands each time)

**Every time you want to use the app:**

1. Open Terminal at the folder where you have the code. Or if you have the code in the default folder, just open Terminal and paste:
```bash
cd ~/not-wispr-flow
```
2. Paste these commands:
```bash
source venv/bin/activate
python3 main.py
```
3. Keep Terminal open while using the app
4. When done, press `Ctrl+C` in Terminal to stop

**Grant permissions (first time only):** System Settings → Privacy & Security → Enable these for **Terminal**: Microphone, Accessibility, Input Monitoring

---

### B) Mac App Method (One-time setup, then launch like any app)

**Step 1: Create certificate (one-time)**

Run this script to automatically create a self-signed code signing certificate:
```bash
./scripts/create_certificate.sh
```

You'll be prompted to enter your macOS login password once. The script handles everything else automatically via command line.

**Why a certificate?** macOS ties permissions to an app's signature. Without a certificate, you'd need to re-grant permissions after every update. This creates a local certificate so permissions persist. The certificate never leaves your computer.

**Important:** The install script requires this certificate. If you skip this step, the installation will fail.

**Not comfortable with this?** Use Option A instead — no certificate needed.

**Step 2: Install the app**
```bash
cd ~/not-wispr-flow
./scripts/install_service.sh
```
This takes a minute or two.

**Step 2: Launch the app**

Open "Not Wispr Flow" from Spotlight or your Applications folder. You'll see the icon in your menu bar (top-right).

**Step 4: Grant permissions (first time only)**

System Settings → Privacy & Security → Enable these for **"Not Wispr Flow"**: Microphone, Accessibility, Input Monitoring

**To stop the app:** Click the menu bar icon → Quit

**To uninstall:**
```bash
cd ~/not-wispr-flow
./scripts/uninstall_service.sh
```

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

Edit [config.py](config.py) to change the Whisper model or hotkeys, then rebuild:
```bash
./scripts/install_service.sh  # if using Mac App
# or just restart if using Terminal method
```

**Available options:**
- **Whisper models:** `whisper-large-v3-turbo` (default), `whisper-small`, `whisper-base`
- **Hotkeys:** Control key (default), Function key (`{Key.f13}`), Command key (`{Key.cmd, Key.cmd_r}`), Option key (`{Key.alt, Key.alt_r}`), F13, etc.

> **Note:** I'm planning to add a GUI for hotkey configuration in the future. For now, editing the config file is the only way to change hotkeys.

---

Inspired by [Wispr Flow](https://wisprflow.ai) • Uses [OpenAI Whisper](https://github.com/openai/whisper) via [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper)

# Not Wispr Flow

Free, offline voice-to-text for **macOS**. Hold a key, speak, release — your words appear wherever your cursor is. Works in any app.

Everything runs on your machine. No cloud, no subscription, no data leaving your computer. Uses OpenAI's Whisper model through Apple's MLX framework, running on your Mac's GPU.

**You'll need:** Mac with Apple Silicon (M1/M2/M3/M4) • ~1-3GB RAM depending on your model choice.

---

## About this project

Inspired by [Wispr Flow](https://wisprflow.ai/). They've built something genuinely impressive — this project doesn't come close to their quality and features.

But this gets the job done for free and runs entirely on your machine. The tradeoff? It'll use some of your RAM (~2-3GB) since the AI model stays in memory while running.

---

## Installation

### Prerequisites — Homebrew (Skip if you've got it)

Don't have Homebrew? Open Terminal (search in Spotlight) and run:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
Follow the instructions, then restart Terminal.

### Setup

**Install what you need:**
```bash
brew install python git portaudio
```

**Grab the code:**

Want it in a specific folder (like Documents)? Navigate there in Finder, right-click the folder → **New Terminal at Folder**. Then:

```bash
git clone https://github.com/elcicneha/not-wispr-flow.git
cd not-wispr-flow
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Pick how you want to run it

### Option A: Run in Terminal

Simpler setup, no certificate needed. You'll just run a couple commands each time.

**Start it up:**
```bash
source venv/bin/activate
python3 main.py
```
Keep Terminal open while you're using it. Press `Ctrl+C` when you're done.

**Permissions:** Give **Terminal** access in System Settings → Privacy & Security:
- Microphone, Accessibility, Input Monitoring

---

### Option B: Install as Mac App (Recommended)

Set it up once, then launch it like any other Mac app. You'll need to create a local code signing certificate.

**Why a certificate?** macOS ties permissions to your app's signature. Without it, you'd have to re-grant permissions every time you rebuild. This creates a local-only certificate that makes permissions stick.

**Create your certificate (one-time):**
```bash
./scripts/create_certificate.sh
```
It'll ask for your password a couple times — just macOS checking you have permission to create certificates.

**Build and install:**
```bash
./scripts/install_service.sh
```

**Launch it:** Open "Not Wispr Flow" from Applications or Spotlight.

**Permissions:** Give **"Not Wispr Flow"** access in System Settings → Privacy & Security:
- Microphone
- Accessibility
- Input Monitoring

**To uninstall:** Run `./scripts/uninstall_service.sh`

---

## How to use it

* **Hold mode:** Hold Control → speak → release
* **Toggle mode:** Press Control + Space → speak → press Control again

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Hotkey won't work | Check that all 3 permissions are enabled |
| No text appears | Make sure Accessibility permission is on |
| Need logs? | Check `~/Library/Logs/NotWisprFlow/notwisprflow.log` |

---

## Customization

Want to change things up? Edit [config.py](config.py):
- **Whisper models:** `whisper-large-v3-turbo` (default), `whisper-small`, `whisper-base`
- **Hotkeys:** Control key (default), Command key (`{Key.cmd, Key.cmd_r}`), Option key (`{Key.alt, Key.alt_r}`), F13, etc.

After making changes, rebuild with: `./scripts/install_service.sh`

> Planning to add a GUI for keyboard shortcuts in the future.

---

Inspired by [Wispr Flow](https://wisprflow.ai) • Uses [OpenAI Whisper](https://github.com/openai/whisper) via [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper)

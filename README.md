# Not Wispr Flow

![Social Preview](icons/social%20preview%20card.png)

Free, offline voice-to-text for **macOS**. Hold a key, speak, release — your words appear wherever your cursor is. Runs as a menu bar app, works system-wide in any app.

Everything runs on your machine. No cloud, no subscription, no data leaving your computer. Uses OpenAI's Whisper model through Apple's MLX framework, running on your Mac's GPU.

**You'll need:** Mac with Apple Silicon (M1/M2/M3/M4) • ~1-3GB RAM depending on your model choice.

## About this project

Inspired by [Wispr Flow](https://wisprflow.ai/). They've built something genuinely impressive — this project doesn't come close to their quality and features.

But this gets the job done for free and runs entirely on your machine. The tradeoff? It'll use some of your RAM (~2-3GB) since the AI model stays in memory while running.

## Installation

### Prerequisites — Homebrew

Homebrew is a tool for installing stuff on Mac via Terminal. **Already have it?** Skip to Setup below. If not:

**Open Terminal** (search in Spotlight) and paste the following command:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
Follow the instructions it gives you, then close and reopen Terminal.

---

### Setup

**Install dependencies:**
Paste this command in terminal
```bash
brew install python git portaudio
```

**Download the code:**

Want it in a specific folder (like Documents, Desktop, etc.)?
→ Open that folder in Finder → right-click → **New Terminal at Folder**

Then paste these commands one at a time:

```bash
git clone https://github.com/elcicneha/not-wispr-flow.git
cd not-wispr-flow
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Takes a few minutes. You'll see a lot of text scrolling. That's normal.

---

## Pick how you want to run it

### Option A: Run in Terminal (Simpler)

**Good for:** Testing it out, if you don't want to deal with certificates, if you want a simple setup and don't mind keeping a terminal open while using it.

**How to start:**

Find your `not-wispr-flow` folder in Finder → right-click on it → **New Terminal at Folder**

Then paste these two commands:
```bash
source venv/bin/activate
python3 main.py
```

That's it. Keep the Terminal window open while you're using it. When you're done, press `Ctrl+C` to stop.

**Permissions needed:** System Settings → Privacy & Security → give **Terminal** access to:
- Microphone
- Accessibility
- Input Monitoring

---

### Option B: Install as Mac App (Recommended)

**Good for:** Actually using this regularly without opening Terminal every time

Set it up once, then launch like any other Mac app. You get a menu bar icon, runs in the background.

**The catch:** You need to create a code signing certificate first (I'll walk you through it).

#### Why a certificate?

macOS ties permissions to your app's signature. Without it, you'd re-grant permissions every time you rebuild.

This creates a **local-only** certificate that makes permissions stick. It doesn't go anywhere, just lives on your Mac.

#### Create certificate (one-time):
```bash
./scripts/create_certificate.sh
```
It'll ask for your Mac password a couple times — just macOS verifying you have permission.

#### Build and install:
```bash
./scripts/install_service.sh
```

Takes a few minutes. Builds the app and installs it to Applications.

#### Launch it:
Open "Not Wispr Flow" from Applications or Spotlight (Cmd+Space).

#### Permissions needed:
System Settings → Privacy & Security → give **"Not Wispr Flow"** access to:
- Microphone
- Accessibility
- Input Monitoring

**To uninstall later:** `./scripts/uninstall_service.sh`

---

## How to use it

You'll see a menu bar icon at the top of your screen when it's running. 

* **Hold mode:** Hold Control → speak → release
* **Toggle mode:** Press Control + Space → speak → press Control again

**First time:** Downloads the AI model (~1-3GB). Takes a few minutes, only happens once.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Hotkey won't work | Check all 3 permissions are enabled (Microphone, Accessibility, Input Monitoring) |
| No text appears | Make sure Accessibility permission is on |
| Text is wrong/gibberish | Try talking louder, or switch to larger model in [config.py](config.py) |
| Stopped working after rebuild | Run `./scripts/create_certificate.sh` first, then rebuild |
| Need logs? | `~/Library/Logs/NotWisprFlow/notwisprflow.log` (Cmd+Shift+G in Finder) |

---

## Customization

Want to change things up? Edit [config.py](config.py) in any text editor:

**Whisper models:**
- `whisper-large-v3-turbo` (default) — Fast, accurate, ~2GB RAM
- `whisper-small` — Faster, less accurate, ~1GB RAM
- `whisper-base` — Fastest, least accurate, ~500MB RAM

**Hotkeys:**
- Control key (default) — `{Key.ctrl, Key.ctrl_r}`
- Command key — `{Key.cmd, Key.cmd_r}`
- Option key — `{Key.alt, Key.alt_r}`
- Or F13, etc.

**After making changes:**
- If you installed as an app: Run `./scripts/install_service.sh` to rebuild
- If running in Terminal: Just restart it (`Ctrl+C` then `python3 main.py`)

> Planning to add a GUI for this so you don't have to edit code files.

---

Inspired by [Wispr Flow](https://wisprflow.ai) • Uses [OpenAI Whisper](https://github.com/openai/whisper) via [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper)

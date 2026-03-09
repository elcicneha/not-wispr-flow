# Not Wispr Flow

![Social Preview](icons/social%20preview%20card.png)

Free, offline voice-to-text for **macOS**. Hold a key, speak, release — your words appear wherever your cursor is. Runs as a menu bar app, works system-wide in any app.

Everything runs on your machine by default. No cloud, no subscription, no data leaving your computer. Uses OpenAI's Whisper model through Apple's MLX framework, running on your Mac's GPU.

Optionally, add free API keys for faster cloud transcription (Groq) and AI text enhancement (Gemini/Groq LLM) — falls back to offline automatically if your internet drops.

**You'll need:** Mac with Apple Silicon (M1/M2/M3/M4) • If running offline: ~1-3GB RAM depending on your model choice.

## About this project

Inspired by [Wispr Flow](https://wisprflow.ai/). They've built something genuinely impressive — this project doesn't come close to their quality and features.

But this gets the job done for free and runs entirely on your machine (if privacy is what you need). The tradeoff? It'll use some of your RAM (~2-3GB) since the AI model stays in memory while running.

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
brew install python git
```

**Download the code:**

Want it in a specific folder (like Documents, Desktop, etc.)?
> Open that folder in Finder → right-click → **New Terminal at Folder**

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

**Recording modes:**
* **Hold mode:** Hold Control → speak → release
* **Toggle mode:** Press Control + Space → speak → press Control again

**Other shortcuts:**
* **Retype last:** Press Ctrl+Cmd+C to retype the last transcription (also available from the menu bar)

**First time:** Downloads the AI model (~1-3GB). Takes a few minutes, only happens once.

**Media pause/resume:** If you're listening to music or podcasts, the app automatically pauses playback when you start recording and resumes when transcription is done.

---

## API Keys (Optional)

Out of the box, everything runs offline on your Mac. API keys unlock faster transcription and AI text enhancement.

### Groq API Key — Transcription + LLM

This is the main API key. It does two things:
- **Faster transcription** — uses Groq's cloud Whisper instead of running locally. Less RAM, faster results. Falls back to offline automatically if your internet drops.
- **LLM text cleanup** — uses Groq's Llama models to fix punctuation, capitalization, filler words, and self-corrections. Free, fast, and good enough for most use.

1. Go to [console.groq.com](https://console.groq.com) and create a free account
2. Generate an API key
3. Save the key — two options:

   **Option A — Paste in config.py** (quick and simple, good for personal use)

   Open [config.py](config.py), find `GROQ_API_KEY`, paste your key there.

   **Option B — Save to a file** (keeps your key separate from the code, safer if you share or push your code)
   ```bash
   mkdir -p ~/.config/notwisprflow
   echo "your-api-key" > ~/.config/notwisprflow/api_key
   ```

4. Restart the app

**Don't want online transcription at all?** Set `TRANSCRIPTION_MODE = "offline"` in [config.py](config.py).

### Gemini API Key — Better LLM (Optional)

If you want higher quality text cleanup, you can add a Gemini key. Gemini models are smarter than Llama but a bit slower. This is completely optional — the Groq Llama models above work well for most people.

1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) and create a free key
2. Save the key — two options:

   **Option A — Paste in config.py** (quick and simple, good for personal use)

   Open [config.py](config.py), find `GEMINI_API_KEY`, paste your key there.

   **Option B — Save to a file** (keeps your key separate from the code, safer if you share or push your code)
   ```bash
   mkdir -p ~/.config/notwisprflow
   echo "your-api-key" > ~/.config/notwisprflow/gemini_api_key
   ```

3. Restart the app
4. Switch to a Gemini model: in [config.py](config.py), set `LLM_MODEL` to `"gemini-2.5-flash"` or `"gemini-2.5-pro"` (or change it from the menu bar under LLM Model)

LLM only runs when using online transcription (Groq). It's automatically skipped during offline/local transcription.

---

## Menu Bar

The menu bar icon shows the app state: idle, recording (animated), or processing (animated).

| Menu Item | What it does |
|-----------|-------------|
| **Retype last transcript** | Types the last transcription again (Ctrl+Cmd+C) |
| **Paste Mode** | Toggle between clipboard paste (default) and character-by-character typing |
| **LLM Model** | Switch between LLM models (Gemini Flash, Gemini Pro, Groq Llama, or Disabled) |
| **Prompts...** | Edit personal prompt — additional instructions for the LLM, plus system prompt overrides |
| **Open Logs** | Opens the log file in your default text editor |
| **Quit** | Stops the app (Cmd+Q) |

---

## Customization

Want to change things up? Edit [config.py](config.py) in any text editor:

**Whisper models:**
- `whisper-large-v3` (default in online mode) — Most accurate
- `whisper-large-v3-turbo` (default in offline mode) — Fast, accurate, ~2GB RAM
- `whisper-small` — Faster, less accurate, ~1GB RAM
- `whisper-base` — Fastest, least accurate, ~500MB RAM

**Hotkeys:**
- Control key (default) — `{Key.ctrl, Key.ctrl_r}`
- Command key — `{Key.cmd, Key.cmd_r}`
- Option key — `{Key.alt, Key.alt_r}`
- Or F13, etc.

**LLM models** (in `LLM_MODELS` dict):
- `gemini-2.5-flash` — Fast Gemini model (requires Gemini API key)
- `gemini-2.5-pro` — Best Gemini model (requires Gemini API key)
- `llama-3.3-70b-versatile` — Best Groq LLM (reuses Groq API key)
- `llama-3.1-8b-instant` — Fastest Groq LLM (reuses Groq API key)
- `disabled` — No LLM processing

**After making changes:**
- If you installed as an app: Run `./scripts/install_service.sh` to rebuild
- If running in Terminal: Just restart it (`Ctrl+C` then `python3 main.py`)

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Hotkey won't work | Check all 3 permissions are enabled (Microphone, Accessibility, Input Monitoring) |
| No text appears | Make sure Accessibility permission is on |
| Text is wrong/gibberish | Try talking louder, or switch to larger model in [config.py](config.py) |
| Stopped working after rebuild | Run `./scripts/create_certificate.sh` first, then rebuild |
| Need logs? | `~/Library/Logs/NotWisprFlow/notwisprflow.log` (Cmd+Shift+G in Finder) |
| LLM not running? | Make sure you have the right API key set up and `TRANSCRIPTION_MODE` is not `"offline"` |

---

Inspired by [Wispr Flow](https://wisprflow.ai) • Uses [OpenAI Whisper](https://github.com/openai/whisper) via [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper)

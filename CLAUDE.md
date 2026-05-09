# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Not Wispr Flow is a macOS voice dictation tool providing system-wide speech-to-text with hybrid online/offline support. It uses Groq API for fast cloud transcription when available, with local MLX Whisper as a fallback. Silero VAD handles silence detection. It runs as a background menu bar app with two recording modes:

- **Press-and-Hold**: Hold Control to record, release to transcribe
- **Toggle Mode**: Press Control + Space to start recording, Control to stop

## Development Commands

```bash
# Setup
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# Run in terminal (development)
source venv/bin/activate
python3 main.py

# Build .app bundle
rm -rf build dist && python3 setup.py py2app

# Full install to /Applications (builds + signs + installs)
./scripts/install_service.sh

# One-step installer (end users or first-time setup)
./install.sh

# Uninstall
./uninstall.sh
```

No automated tests. Manual testing requires running the app and dictating into a text editor.

## Code Search

Use `semble search` to find code by describing what it does or naming a symbol/identifier, instead of grep:

```bash
semble search "authentication flow" ./my-project
semble search "save_pretrained" ./my-project
semble search "save model to disk" ./my-project --top-k 10
```

Use `semble find-related` to discover code similar to a known location (pass `file_path` and `line` from a prior search result):

```bash
semble find-related src/auth.py 42 ./my-project
```

`path` defaults to the current directory when omitted; git URLs are accepted. If `semble` is not on `$PATH`, use `uvx --from "semble[mcp]" semble` in its place.

Workflow: start with `semble search`, inspect full files only when the chunk isn't enough, optionally pivot via `semble find-related`, and use grep only for exhaustive literal matches.

## Repository Layout

Two independent subprojects share this repo:

- **Root (`main.py`, `notwisprflow/`)** — the macOS dictation app. Python + PyObjC. This is the primary subject of this CLAUDE.md.
- **`website/`** — Next.js 16 + React 19 + Tailwind v4 marketing/demo site. **This is not the Next.js you know** — Next.js 16 has breaking changes vs. training data; consult `node_modules/next/dist/docs/` before writing API-touching code. pnpm-managed. Scripts: `pnpm dev`, `pnpm build`, `pnpm lint`. See **Website Architecture** section below for full details.

The two subprojects do not import from each other. Treat each as its own working directory when making changes.

## Architecture

### Module Structure
- **`main.py`** — App shell: `AppState`, transcription pipeline, health monitor, entry point
- **`notwisprflow/config.py`** — User-facing settings (model, hotkeys, transcription mode, API keys, LLM prompts)
- **`notwisprflow/constants.py`** — Internal constants (e.g. `SAMPLE_RATE`). NOT for user-facing settings
- **`notwisprflow/keyboard_handler.py`** — Keyboard state machine: `create_handlers()` returns `(on_press, on_release)` closures
- **`notwisprflow/audio.py`** — Recording lifecycle, buffer overflow to disk, recording stats
- **`notwisprflow/menubar.py`** — All menu bar UI: icon manager, menu delegate, prompt panel, status updater
- **`notwisprflow/text_output.py`** — Text insertion (clipboard paste or CGEvent typing), cursor context via Accessibility APIs
- **`notwisprflow/permissions.py`** — macOS mic/accessibility permission checks
- **`notwisprflow/preferences.py`** — Prefs persistence (`~/.config/notwisprflow/preferences.json`), `resolve_api_key()`, `merge_vocabularies()`
- **`notwisprflow/transcription.py`** — `TranscriptionManager`: MLX Whisper, Groq API, Silero VAD, connectivity monitor, model lifecycle, runtime-editable Whisper prompt (custom vocabulary)
- **`notwisprflow/llm_processor.py`** — `LLMProcessor`: multi-provider dispatch (Gemini/Groq/OpenAI/Anthropic)
- **`notwisprflow/post_processing.py`** — LLM enhancement + smart spacing pipeline
- **`notwisprflow/startup.py`** — LaunchAgent plist management for start-at-login
- **`notwisprflow/media_control.py`** — Media pause/resume via macOS private `MediaRemote.framework`
- **`notwisprflow/transcript_history.py`** — SQLite-backed transcript history (`~/.config/notwisprflow/transcript_history.db`). 5MB cap with auto-prune. `init_db()` on startup, `add_transcript()` after each transcription, `get_recent()`/`get_all()` for menu bar display

### Dependency Graph (acyclic)
```
main.py → keyboard_handler, audio, menubar, text_output, permissions, preferences, startup
keyboard_handler → audio, text_output, config
audio → config, constants, media_control
menubar → config, preferences, text_output, startup, transcript_history
text_output, permissions, media_control, startup, transcript_history → standalone (no app imports)
transcription → constants, preferences
llm_processor → config, preferences
post_processing → llm_processor
```

### Key Patterns
- **Explicit state passing**: `AppState` passed as parameter to all modules — no hidden globals. Single thread lock
- **Callback DI**: `stop_recording(state, update_icon_fn, on_audio_ready_fn)` — audio doesn't know about transcription, avoids circular imports
- **Closures for pynput**: `create_handlers()` returns closures because pynput only accepts `(key)` signature
- **Audio pipeline**: `soundcard` → deque (lock-free, GIL-atomic) → VAD → transcribe → clipboard paste
- **Smart model management**: In auto mode, connectivity monitor unloads local model after 60s stable internet (~2.3GB freed), pre-loads when connectivity drops
- **NSObject subclasses** get `_state` attribute set after `alloc().init()` (PyObjC pattern)

### Recording State Machine
```
None + hotkey press              → Hold mode, start recording
None + hotkey press (space held) → Toggle mode, start recording
None + space press (hotkey held) → Toggle mode, start recording
Hold + space press               → Convert to Toggle mode (recording continues)
Hold + hotkey release            → Stop recording, transcribe
Toggle + hotkey press            → Stop recording, transcribe
```

Stuck-state recovery: if mode is set but not recording (stream crashed), next hotkey press salvages captured audio and resets.

### Threading Model
- **Main thread**: NSApplication manual event loop (0.5s timeout for Ctrl+C support)
- **Audio callback**: `soundcard` recorder, lock-free `deque.append()` — must never block
- **MLX worker**: Dedicated thread for all Metal/MLX GPU ops (avoids Metal threading assertions)
- **Transcription**: Per-recording thread, owns buffer snapshot (no shared state)
- **Connectivity monitor**: (auto mode) Checks internet every 30s, manages model load/unload
- **Health monitor**: Daemon, checks stream health every 5s
- **Keyboard listener**: `pynput.Listener` via PyObjC event tap

### Build System
`setup.py` configures py2app. `LSUIElement: True` (no Dock icon). Excludes torch/torchaudio/silero_vad (VAD uses numpy-only ONNX wrapper). `install_service.sh` code-signs and fixes MLX rpaths.

## Configuration

User-facing settings in `notwisprflow/config.py`. Internal constants stay in their respective modules.

Key non-obvious settings:
- `HOTKEY_KEYS` is a **set** — pynput may report `Key.ctrl`, `Key.ctrl_r`, or `Key.ctrl_l` depending on macOS/keyboard
- `TRANSCRIPTION_MODE`: `"auto"` (cloud with offline fallback), `"offline"`, or `"online"`
- `LLM_MODEL`: set to `"disabled"` to turn off. LLM only runs with online transcription, never offline
- `USE_TYPE_MODE`: `False` = clipboard paste (default), `True` = character-by-character typing
- `CUSTOM_VOCABULARY`: comma-separated baseline glossary that biases Whisper (`prompt`/`initial_prompt`). The effective vocabulary at runtime is `merge_vocabularies(CUSTOM_VOCABULARY, preferences["custom_vocabulary"])` — case-insensitive dedupe, config baseline always survives

API key resolution order (via `resolve_api_key()`): config.py → env var → dotfile in `~/.config/notwisprflow/` (`api_key`, `gemini_api_key`, `openai_api_key`, `anthropic_api_key`). Runtime state (LLM model, prompt, custom vocabulary, selected mic) persists in `~/.config/notwisprflow/preferences.json`.

## Important Gotchas

- **macOS permissions** go to the **app bundle** ("Not Wispr Flow"), not Terminal: Microphone + Accessibility + Input Monitoring
- **Clean build required** after code changes: `rm -rf build dist` before `python3 setup.py py2app`
- **MLX pinned to single thread** — all Metal/MLX calls go through `TranscriptionManager`'s dedicated worker queue
- **Audio callback must never block** — blocking I/O in the callback hangs `stream.stop()`
- **`stop_recording()` snapshots buffer** before clearing — transcription thread owns its copy
- **Text insertion** saves/restores clipboard via `NSPasteboard`, restores immediately to avoid clipboard manager capture
- **Media playing detection** uses `pmset -g assertions` because MediaRemote query APIs are broken for browser media on macOS Sequoia. Command APIs (PAUSE/PLAY) still work
- **Exit code 0** on fatal errors — intentional, prevents LaunchAgent restart loops
- **PID file lock**: `~/Library/Logs/NotWisprFlow/notwisprflow.pid`
- **Logs**: `~/Library/Logs/NotWisprFlow/notwisprflow.log` (rotating, 10MB x 5)

## Modifying the Code

### Adding a new recording mode
1. Add mode to `AppState.__init__()` in `main.py`
2. Add activation/deactivation in `on_press()`/`on_release()` in `keyboard_handler.py`
3. Add stuck-state recovery for the new mode

### Tuning VAD sensitivity
In `TranscriptionManager.contains_speech()`, adjust `_get_speech_timestamps_numpy()` params: `threshold` (0.3-0.6), `min_speech_duration_ms`, `min_silence_duration_ms`.

### Adding an LLM provider
Add provider in `llm_processor.py` (key resolution, client init, process method). Add models to `LLM_MODELS` in `config.py`. Add prompt presets to `LLM_PROMPTS` in `config.py`.

### Tweaking the Whisper vocabulary bias
Edit `CUSTOM_VOCABULARY` in `config.py` for the baseline (rebuild required), or use the menu bar's "Custom Vocabulary..." for runtime additions (no rebuild). Both are merged + deduped on every read. The MLX worker reads the prompt via `prompt_getter` lambda each transcription, so edits take effect immediately without reloading the ~2.3GB model.

## Website Architecture

The marketing site lives in `website/` and is independent from the Python app.

### Folder hierarchy

```
website/
├── app/                       # Next.js App Router — routing-related files only
│   ├── layout.tsx             # Root layout: fonts, theme bootstrap, metadata
│   ├── page.tsx               # Home page — composes sections
│   ├── globals.css            # CSS reset, theme tokens, Tailwind @theme wiring, keyframes
│   ├── fonts.ts               # next/font setup (Recoleta + Instrument Sans + JetBrains Mono)
│   └── theme-script.ts        # Inline FOUC-free theme bootstrap (light/dark)
├── components/
│   ├── sections/              # Page-level sections (used once, not reusable)
│   │                          # Header, Hero, Marquee, DemoSection, Features, Install, Footer
│   └── ui/                    # Reusable UI primitives
│                              # Button, TextLink, InlineCode, CodeBlock, Sticker, KbdKey,
│                              # ThemeToggle, HandUnderline, Asterisks
├── lib/                       # Utilities + content/copy
│   ├── content.ts             # All page copy, URLs, structured data (features, install steps)
│   └── cn.ts                  # className joiner utility (naive concat — does NOT dedupe Tailwind conflicts)
├── fonts/                     # Local font files (referenced by app/fonts.ts)
└── public/                    # Static assets served at / (images, video, OG card, favicon)
```

**Rule of thumb:** anything used once on a single page belongs in `components/sections/`. Anything reusable (used in 2+ places, or could be) belongs in `components/ui/`.

### UI primitives — what to use when

Always reach for an existing primitive before writing inline-styled markup. Each one owns its visual identity; consumers pass props, not styles.

- **`Button`** — every button-shaped CTA or affordance. Renders `<a>` if you pass `href`, else `<button>`.
  - `variant`: `primary` (filled accent CTA), `outline` (bordered ink CTA), `chip` (muted mono affordance like the copy chip / theme toggle).
  - `size`: `sm` / `md` / `lg`. Sizes carry **only** dimensions (padding, font-size, border-width, radius). Variants carry treatment identity (bg, text color, font, weight, tracking, shadows). Never put colors or fonts in size; never put dimensions in variant.
  - Uses `twMerge` internally, so `className` overrides reliably win against built-in classes (e.g. `<Button variant="chip" className="rounded-full">` swaps the radius).
- **`TextLink`** — inline anchor with an underline. For links *inside flowing text* (footer credits) or standalone muted nav (header). Inherits font/color/size from context; pass typography classes via `className` only when the parent doesn't provide them.
- **`InlineCode`** — `<code>` with the project's mono pill style for inline code references inside prose.
- **`CodeBlock`** — `<pre>` block with copy button for fenced code samples.
- **`Sticker`**, **`KbdKey`**, **`HandUnderline`**, **`Asterisks`** — purpose-built decorative primitives; see each file for props.
- **`ThemeToggle`** — single instance, lives in `Header`. Don't replicate.

**Do not** layer additional styling on top of a primitive (`<Button style={{...}}>`, `<Button className="text-blue-500">`) unless the call site has a specific, justified deviation from the design system. If you find yourself fighting a primitive with overrides, the primitive needs a new variant/size/prop — not a per-call patch.

**Duplication rule:** if the same chunk of styling repeats across 2+ places (a base heading style, a card pattern, a marquee row), extract it. Either (a) lift to a primitive in `components/ui/` if it's a self-contained unit, or (b) add a base rule in `globals.css` (typically inside `@layer base` for element selectors like `h1`, or as a named class like `.home-h1` for repeated multi-element patterns). Inline duplication is the smell — flag it the moment you notice it.

### Styling

- **Tailwind v4 always.** Reach for utilities first (`bg-accent`, `text-ink`, `border-border`, `font-display`, `py-3.5`, etc.) before any other styling. Don't write inline `style={{...}}` for things a utility can express.
- **CSS variables** on `:root` and `.dark` carry the theme palette and typography scale.
- Theme tokens are wired into Tailwind via `@theme { --color-bg: var(--bg); --font-display: var(--font-display-var), serif; ... }` in `globals.css` — so utilities like `bg-bg`, `text-ink`, `border-border`, `font-display`, `font-mono` resolve to themed values that swap when `.dark` is added/removed on `<html>`. Use plain `@theme` (not `@theme inline`) so utilities reference the runtime variables and react to dark-mode swaps.
- When you need a non-standard color or shadow inside an arbitrary value, reference the Tailwind theme variable name (e.g. `shadow-[4px_4px_0_var(--tw-shadow-color)]` paired with `shadow-ink-soft`), not the raw underlying var (`var(--ink-soft)`).
- **Inline styles** are reserved for: dynamic per-instance values (rotations from arrays), `animation-delay` strings, `animation: <name> ...` longhand, and complex transforms with no Tailwind equivalent. Static design values do not belong in `style={{}}`.
- **Use `rem`** for spacing values written in CSS rules (margin, padding, gap). Inline pixel values inside dynamic JS expressions are the exception.
- **Animations** as `@keyframes` in `globals.css` (`wordReveal`, `marqueeScroll`, `underlineDraw`, `fadeUp`).
- **No `next-themes` or motion libraries** — vanilla CSS handles everything.

### Theme system

- Two themes: `light` (lime BG, dark green ink) and `dark` (dark green BG, lime ink).
- `<html class="dark">` (presence = dark, absence = light) controls everything via CSS variable swap.
- Inline bootstrap script in `<head>` (rendered from `app/theme-script.ts`) reads `localStorage.theme` (or `prefers-color-scheme`) before paint to prevent FOUC.
- `ui/ThemeToggle` is the only client component for state — toggles the `.dark` class on `<html>` and persists to localStorage.

### Semantic HTML conventions

- One `<h1>` per page (in Hero only). `<h2>` = section titles. `<h3>` = card / step titles.
- `<section>` per page block. Each section gets its own component in `components/sections/`.
- `<article>` for self-contained units (e.g. feature cards).
- `<aside>` for tangential content (e.g. the screen-recording placeholder in the install section).
- `<header>` / `<footer>` / `<main>` / `<nav>` per their standard roles.
- `<kbd>` for keyboard keys (rendered via `ui/KbdKey`). `<code>` / `<pre>` for code (rendered via `ui/CodeBlock`).
- `<button>` for actions (toggle, copy). `<a>` for navigation and external links — including in-page anchors like `href="#install"`.

### Color & typography rules

- **Never use `#000` or `#fff` for text or icons.** All colors flow through CSS variables (`--ink`, `--ink-soft`, `--accent-contrast`, etc.).
- Display headings (`h1`/`h2`/`h3` and giant install-step numerals): **Recoleta Bold** via `var(--font-display-var)` or `font-display`.
- Body / UI text: **Instrument Sans** via `font-sans`.
- Code, kbd keys, mono accents (eyebrow tags, captions): **JetBrains Mono** via `font-mono`.

### Adding a new section to the homepage

1. Create `components/sections/YourSection.tsx`.
2. Use `<section>` as the root with appropriate `id` if it's an anchor target.
3. Pull copy from `lib/content.ts` — never hardcode strings in components.
4. Compose into `app/page.tsx`.
5. If it introduces a reusable primitive, lift it to `components/ui/`.

### Adding a new UI primitive

1. Create `components/ui/YourPrimitive.tsx`.
2. Style with Tailwind utilities only — no `style={{}}` for static design values.
3. If the primitive has variants/sizes, follow the Button pattern: `size` carries dimensions only, `variant` carries treatment identity. Never let the two axes set the same property.
4. If consumers will likely want to override classes, use `twMerge` (from `tailwind-merge`) when composing className so overrides win deterministically. Otherwise the naive `cn` from `lib/cn.ts` is fine.
5. Inline styles are reserved for genuinely dynamic per-instance values (rotations from arrays, animation delays).
6. If it needs interactivity (state, click handlers), mark it with `"use client"`.
7. Before shipping, scan the rest of the codebase: if you find inline-styled markup matching this primitive, replace it. Don't let the codebase carry both forms.

### Content / copy

All user-facing strings live in `lib/content.ts`. Components import named exports (`features`, `installSteps`, `marqueeContent`, `REPO_URL`, `DOWNLOAD_ZIP_URL`). This keeps editorial changes one-file.

## Design Decisions Log (MANDATORY)

**After completing any task**, append a new entry to `DESIGN_DECISIONS.md`:

1. **What was done**
2. **What was explicitly NOT done and why**
3. **Alternatives considered**
4. **What was tried and didn't work** (include specifics)
5. **What worked and why**

Format: `## Section Title`, `**Decision: ...**`, bullet points, ending with `---`. Skip ONLY for purely informational tasks with zero code changes.

#!/usr/bin/env python3
"""Not Wispr Flow installer — rich UI for the install steps."""
import os
import sys
import subprocess
import hashlib
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()
PROJECT_DIR = Path(__file__).parent.parent
VENV_PYTHON = PROJECT_DIR / "venv" / "bin" / "python3"
INSTALL_LOG = PROJECT_DIR / ".install.log"
CODESIGN_IDENTITY = "Not Wispr Flow Dev"


def log_cmd(cmd, capture=True):
    """Run a command, appending output to the install log."""
    with open(INSTALL_LOG, "a") as log:
        result = subprocess.run(
            cmd,
            stdout=log if capture else None,
            stderr=log if capture else None,
        )
    return result.returncode == 0


def fail(step, hint=None):
    console.print(f"  [red]✗[/] {step}")
    if hint:
        console.print(f"    [dim]{hint}[/]")
    if INSTALL_LOG.exists():
        lines = INSTALL_LOG.read_text().strip().split("\n")[-15:]
        console.print()
        for line in lines:
            console.print(f"    [dim]{line}[/]")
        console.print(f"\n    Full log: [dim]{INSTALL_LOG}[/]")
    sys.exit(1)


def step_ok(label, detail=""):
    console.print(f"  [green]✓[/] {label:<26} [dim]{detail}[/]")


def main():
    console.print()
    console.print("  [bold]Not Wispr Flow Installer[/]")
    console.print()
    INSTALL_LOG.write_text("")

    # ── Step 1: Python (already verified by install.sh) ──
    py_ver = subprocess.run(
        [sys.executable, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
        capture_output=True, text=True,
    ).stdout.strip()
    step_ok("Python", py_ver)

    # ── Step 2: Dependencies ──
    req_file = PROJECT_DIR / "requirements.txt"
    hash_file = PROJECT_DIR / "venv" / ".requirements_hash"
    current_hash = hashlib.sha256(req_file.read_bytes()).hexdigest()

    if hash_file.exists() and hash_file.read_text().strip() == current_hash:
        step_ok("Dependencies", "up to date")
    else:
        with console.status("  Installing packages (Takes ~1 minute)..."):
            log_cmd([str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip", "--quiet"])
            ok = log_cmd([str(VENV_PYTHON), "-m", "pip", "install", "-r", str(req_file), "--quiet"])
        if not ok:
            fail("Dependencies")
        hash_file.write_text(current_hash)
        step_ok("Dependencies", "installed")

    # ── Step 3: Certificate ──
    cert_check = subprocess.run(
        ["security", "find-certificate", "-c", CODESIGN_IDENTITY,
         os.path.expanduser("~/Library/Keychains/login.keychain-db")],
        capture_output=True,
    )
    if cert_check.returncode == 0:
        step_ok("Certificate", "exists")
    else:
        console.print("  [dim]Creating certificate...[/]")
        console.print("  [dim]You'll be asked for your macOS login password once.[/]")
        console.print()
        subprocess.run(["bash", str(PROJECT_DIR / "scripts" / "create_certificate.sh")])
        console.print()
        step_ok("Certificate", "created")

    # ── Step 4: Read config ──
    config_result = subprocess.run(
        [str(VENV_PYTHON), "-c",
         f"import sys; sys.path.insert(0, '{PROJECT_DIR}'); "
         "from notwisprflow.config import TRANSCRIPTION_MODE, WHISPER_MODEL, GROQ_API_KEY; "
         "print(TRANSCRIPTION_MODE); print(WHISPER_MODEL); print(GROQ_API_KEY)"],
        capture_output=True, text=True,
    )
    config_lines = config_result.stdout.strip().split("\n")
    transcription_mode = config_lines[0] if len(config_lines) > 0 else "auto"
    whisper_model = config_lines[1] if len(config_lines) > 1 else "mlx-community/whisper-large-v3-turbo"
    groq_api_key = config_lines[2] if len(config_lines) > 2 else ""

    # Check all API key sources
    has_api_key = bool(groq_api_key)
    if not has_api_key:
        api_key_file = Path.home() / ".config" / "notwisprflow" / "api_key"
        if api_key_file.exists() and api_key_file.read_text().strip():
            has_api_key = True
    if not has_api_key:
        has_api_key = bool(os.environ.get("GROQ_API_KEY", ""))

    # ── Auto mode without API key: ask before building ──
    if transcription_mode == "auto" and not has_api_key:
        console.print()
        note = Text()
        note.append("No Groq API key found.\n\n", style="bold yellow")
        note.append("Without a key, the app runs offline only.\n")
        note.append("For faster cloud transcription:\n\n")
        note.append("  1. Get a free key at https://console.groq.com\n")
        note.append("  2. Replace YOUR_KEY below and run:\n\n")
        note.append("  mkdir -p ~/.config/notwisprflow && \\\n", style="bold")
        note.append('  echo "YOUR_KEY" > ~/.config/notwisprflow/api_key && \\\n', style="bold")
        note.append("  ./install.sh\n", style="bold")
        console.print(Panel(note, width=60, border_style="yellow"))
        answer = console.input("\n  Continue with offline mode? [Y/n] ")
        if answer.lower() == "n":
            console.print()
            sys.exit(0)
        console.print()

    # ── Online mode without API key: cannot proceed ──
    if transcription_mode == "online" and not has_api_key:
        console.print()
        msg = Text()
        msg.append("Online mode requires a Groq API key.\n\n", style="bold red")
        msg.append("  1. Get a free key at https://console.groq.com\n\n")
        msg.append("  2. Add your key (pick one):\n\n")
        msg.append("     Open ", style="dim")
        msg.append("notwisprflow/config.py", style="dim bold")
        msg.append(" and paste in:\n", style="dim")
        msg.append('     GROQ_API_KEY = "your-key-here"\n\n', style="dim bold")
        msg.append("     ── or run: ─────────────────────────────\n", style="dim")
        msg.append("     mkdir -p ~/.config/notwisprflow && \\\n", style="dim")
        msg.append('     echo "YOUR_KEY" > ~/.config/notwisprflow/api_key\n\n', style="dim")
        msg.append("  3. Re-run ./install.sh")
        console.print(Panel(msg, width=60, border_style="red"))
        console.print()
        sys.exit(1)

    # ── Step 5: Build & Install ──
    # Kill running app
    subprocess.run(
        ["pkill", "-fx", ".*/Not Wispr Flow\\.app/Contents/MacOS/Not Wispr Flow"],
        capture_output=True,
    )

    # Pre-download speech model when local transcription will be needed:
    #   offline mode: always needs local model
    #   auto mode + no API key: will fall back to local model immediately
    #   auto mode + API key: app downloads in background — no install-time download
    #   online mode: no local model needed
    model_proc = None
    model_cached = False
    needs_local_model = (
        transcription_mode == "offline"
        or (transcription_mode == "auto" and not has_api_key)
    )

    if needs_local_model:
        model_check = subprocess.run(
            [str(VENV_PYTHON), "-c",
             "from huggingface_hub import try_to_load_from_cache; "
             f"exit(0 if try_to_load_from_cache('{whisper_model}', 'weights.safetensors') else 1)"],
            capture_output=True,
        )
        model_cached = model_check.returncode == 0

        if not model_cached:
            # Start download in parallel with build — both stdout and stderr go to log
            # to avoid interleaving with the build spinner
            with open(INSTALL_LOG, "a") as log:
                model_proc = subprocess.Popen(
                    [str(VENV_PYTHON), "-c",
                     "from huggingface_hub import snapshot_download; "
                     f"snapshot_download('{whisper_model}')"],
                    stdout=log,
                    stderr=log,
                )

    with console.status("  Building app (takes 2-3 minutes)..."):
        ok = log_cmd(["bash", str(PROJECT_DIR / "scripts" / "install_service.sh")])
    if not ok:
        fail("Build & Install")
    step_ok("Build & Install", "/Applications")

    if needs_local_model:
        if model_cached:
            step_ok("Speech Model", "cached")
        elif model_proc:
            # Build finished but download may still be running
            if model_proc.poll() is None:
                with console.status("  Downloading speech model..."):
                    model_proc.wait()
            if model_proc.returncode != 0:
                fail("Speech Model", "Check your internet connection and try again")
            step_ok("Speech Model", "downloaded")

    # ── Summary ──
    console.print()
    summary = Text()
    summary.append("Not Wispr Flow has been installed!\n\n", style="green bold")
    summary.append("Open from Applications or Spotlight (Cmd+Space).\n\n")
    summary.append("First time? Grant these permissions:\n", style="yellow")
    summary.append("System Settings → Privacy & Security →\n")
    summary.append("  • Microphone\n")
    summary.append("  • Accessibility\n")
    summary.append("  • Input Monitoring")
    console.print(Panel(summary, width=54))
    console.print()


if __name__ == "__main__":
    main()

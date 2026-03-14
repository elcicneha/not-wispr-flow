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
        with console.status("  Installing packages (a few minutes)..."):
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

    # ── Step 4: Build & Install ──
    # Kill running app
    subprocess.run(
        ["pkill", "-fx", ".*/Not Wispr Flow\\.app/Contents/MacOS/Not Wispr Flow"],
        capture_output=True,
    )

    with console.status("  Building app (a few minutes)..."):
        ok = log_cmd(["bash", str(PROJECT_DIR / "scripts" / "install_service.sh")])
    if not ok:
        fail("Build & Install")
    step_ok("Build & Install", "/Applications")

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

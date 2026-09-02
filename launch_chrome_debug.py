#!/usr/bin/env python3
"""
Launch your real Chrome profile with remote-debugging enabled so the bot can
attach to the SAME browser window/profile you already use (via Playwright CDP).

Usage:
    python launch_chrome_debug.py
    (or double-click launch-chrome-debug.bat on Windows)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEBUG_PORT = "9222"


def _chrome_exe() -> str:
    cands = []
    if sys.platform == "win32":
        cands = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
            Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
        ]
    else:
        cands = [
            Path("/usr/bin/google-chrome"),
            Path("/usr/bin/chromium-browser"),
            Path("/usr/bin/chromium"),
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    for c in cands:
        if c.exists():
            return str(c)
    return "chrome"


def _real_profile_dir() -> str | None:
    home = Path.home()
    cands = [
        home / "AppData" / "Local" / "Google" / "Chrome" / "User Data",
        home / "Library" / "Application Support" / "Google" / "Chrome",
        home / ".config" / "google-chrome",
        home / ".config" / "chromium",
    ]
    for c in cands:
        if c.is_dir():
            return str(c)
    return None


def main():
    profile = _real_profile_dir()
    if not profile:
        print("[ERROR] Could not find your Chrome profile.")
        print("        Pass it manually:  python launch_chrome_debug.py \"C:\\path\\to\\Chrome\\User Data\"")
        sys.exit(1)

    # Allow an explicit profile dir argument.
    if len(sys.argv) > 1:
        profile = sys.argv[1].strip().strip('"')

    exe = _chrome_exe()
    print(f"[1/2] Chrome     : {exe}")
    print(f"[2/2] Profile    : {profile}")

    args = [
        exe,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={profile}",
        "--profile-directory=Default",
        "--no-first-run",
        "--no-default-browser-check",
        "https://www.youtube.com",
    ]
    print("\nLaunching Chrome with remote debugging on port", DEBUG_PORT, "...")
    print("KEEP THIS CHROME OPEN. Then click START BOT in the dashboard.")
    print()

    try:
        subprocess.Popen(args)
    except Exception as e:
        print("[ERROR] Failed to launch Chrome:", e)
        sys.exit(1)

    # Give it a moment and confirm the debug endpoint is up.
    import time
    import urllib.request
    time.sleep(3)
    try:
        with urllib.request.urlopen(f"http://localhost:{DEBUG_PORT}/json/version", timeout=5) as r:
            print("✓ Chrome is ready. Debug endpoint responding:", r.status)
    except Exception as e:
        print("[WARNING] Debug endpoint not yet reachable (Chrome may still be starting).")
        print("         If the bot can't connect, close Chrome and run this helper again.")


if __name__ == "__main__":
    main()

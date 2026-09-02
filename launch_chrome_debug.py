#!/usr/bin/env python3
"""
Launch YOUR real Chrome profile with remote-debugging enabled so the bot can
attach to the SAME browser window/profile you already use (via Playwright CDP).

This is the correct way to use your EXISTING logged-in Chrome (with all your
channel accounts) without closing your normal Chrome or re-logging-in.

Which profile it uses:
  * Reads "chrome_profile_dir" from config.json (e.g. "Default", "Profile 5").
  * Or override on the command line:
        python launch_chrome_debug.py --profile "Profile 5"
        python launch_chrome_debug.py --user-data-dir "C:\\...\\Chrome\\User Data" --profile "Profile 5"

IMPORTANT: for the debug port to work, fully QUIT Chrome first (including any
Chrome running in the background / system tray). Chrome cannot open a second
instance on the same profile, so if Chrome is already open this helper's debug
port is ignored and the bot won't be able to connect.

Usage:
    python launch_chrome_debug.py
    (or double-click launch-chrome-debug.bat on Windows)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEBUG_PORT = "9222"


def _load_cfg() -> dict:
    cfg = {}
    cfg_path = HERE / "config.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
    return cfg


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


def _real_user_data_dir() -> str | None:
    """The PARENT 'User Data' folder (contains Default/Profile 1/Profile 5/...)."""
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


def _parse_args():
    cfg = _load_cfg()
    user_data_dir = None
    profile = cfg.get("chrome_profile_dir", "Default")
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--profile" and i + 1 < len(args):
            profile = args[i + 1].strip().strip('"')
            i += 2
        elif a == "--user-data-dir" and i + 1 < len(args):
            user_data_dir = args[i + 1].strip().strip('"')
            i += 2
        elif a == "--port" and i + 1 < len(args):
            global DEBUG_PORT
            DEBUG_PORT = args[i + 1].strip()
            i += 2
        else:
            i += 1
    return user_data_dir, profile


def main():
    user_data_dir, profile = _parse_args()

    # 1. The full path to the chosen profile folder, e.g. ".../User Data/Profile 5"
    if user_data_dir:
        profile_full = str(Path(user_data_dir) / profile)
    else:
        ud = _real_user_data_dir()
        if not ud:
            print("[ERROR] Could not find your Chrome 'User Data' folder.")
            print("        Pass it manually:")
            print("        python launch_chrome_debug.py --user-data-dir \"C:\\path\\to\\Chrome\\User Data\" --profile \"Profile 5\"")
            sys.exit(1)
        profile_full = str(Path(ud) / profile)

    if not os.path.isdir(profile_full):
        print(f"[WARNING] Profile folder not found: {profile_full}")
        print("          Chrome profiles are usually named 'Default', 'Profile 1', 'Profile 2', ...")
        print("          List what exists here:")
        ud = user_data_dir or _real_user_data_dir()
        if ud and os.path.isdir(ud):
            for name in sorted(os.listdir(ud)):
                if name.lower().startswith("profile") or name.lower() == "default":
                    print(f"            - {name}")
        print("          Continuing anyway (Chrome may create it), but double-check the name.")

    exe = _chrome_exe()
    print(f"[1/3] Chrome      : {exe}")
    print(f"[2/3] Using profile: {profile}")
    print(f"      (folder    : {profile_full})")
    print(f"[3/3] Debug port  : {DEBUG_PORT}")

    # 2. IMPORTANT reminder: Chrome must be fully closed for the debug port to work.
    print("\n" + "=" * 70)
    print("  BEFORE CONTINUING: fully QUIT Chrome.")
    print("  - Close every Chrome window.")
    print("  - If Chrome is still running in the background/system tray,")
    print("    it will ignore the debug port and the bot cannot connect.")
    print("  Task Manager: end any 'Google Chrome' / 'chrome.exe' processes.")
    print("=" * 70)
    reply = input("  Type 'yes' after Chrome is fully closed (or press Enter to continue now): ").strip().lower()

    args = [
        exe,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={os.path.dirname(profile_full)}",
        f"--profile-directory={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "https://www.youtube.com",
    ]
    print("\nLaunching Chrome on profile '%s' with remote debugging on port %s ..." % (profile, DEBUG_PORT))
    print("KEEP THIS CHROME WINDOW OPEN. Then click START BOT in the dashboard.")
    print()

    try:
        subprocess.Popen(args)
    except Exception as e:
        print("[ERROR] Failed to launch Chrome:", e)
        sys.exit(1)

    # 3. Wait for the debug endpoint to respond.
    for _ in range(6):
        time.sleep(2)
        try:
            with urllib.request.urlopen(f"http://localhost:{DEBUG_PORT}/json/version", timeout=5) as r:
                print("✓ Chrome is ready. Debug endpoint responding (HTTP %s)." % r.status)
                print("  Now, in the dashboard turn ON 'Attach to running Chrome (CDP)' and press START BOT.")
                return
        except Exception:
            pass
    print("[ERROR] Debug endpoint did not come up. Most likely Chrome was already running.")
    print("        Completely quit Chrome and run this helper again.")


if __name__ == "__main__":
    main()

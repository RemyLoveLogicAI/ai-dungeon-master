#!/usr/bin/env python3
"""
desktop_launcher.py
Innovative, ultra-lightweight Desktop Launcher for Aegis AI Dungeon Master.
Boots the background engine and opens a dedicated, frameless dark-fantasy desktop window.
"""

import argparse
import logging
import os
import subprocess
import sys
import time
import webbrowser
from multiprocessing import Process

import uvicorn

logger = logging.getLogger("DesktopLauncher")


def run_backend(port: int = 8000):
    # Ensure current dir is in python path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from engine.api_server import app

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def open_desktop_window(url: str):
    """Attempts to open in a dedicated standalone app window without browser chrome."""
    # 1. Try macOS Chrome/Brave/Edge in standalone app-mode
    app_browsers = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    for b_path in app_browsers:
        if os.path.exists(b_path):
            try:
                subprocess.Popen([
                    b_path,
                    f"--app={url}",
                    "--window-size=1280,860",
                    "--window-position=100,100",
                ])
                print(
                    f"[*] Launched native frameless desktop app window via {os.path.basename(b_path)}"
                )
                return
            except (OSError, subprocess.SubprocessError) as err:
                logger.debug("Failed opening via %s: %s", b_path, err)

    # 2. Fallback to default browser
    print(f"[*] Opening desktop UI in default browser: {url}")
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(description="Aegis AI Dungeon Master Desktop Launcher")
    parser.add_argument("--port", type=int, default=8000, help="Port to host the engine on")
    parser.add_argument("--tui", action="store_true", help="Launch in Terminal TUI Cockpit mode")
    parser.add_argument("--no-window", action="store_true", help="Start backend server only")
    args = parser.parse_args()

    if args.tui:
        from engine.dm_tui import run_tui

        run_tui()
        return

    print("=" * 65)
    print("      ⚔  AEGIS AI DUNGEON MASTER - DESKTOP RUNNER  ⚔")
    print("=" * 65)
    print(f"[*] Starting local server on http://127.0.0.1:{args.port}...")

    server_process = Process(target=run_backend, args=(args.port,), daemon=True)
    server_process.start()

    time.sleep(1.2)
    app_url = f"http://127.0.0.1:{args.port}"

    if not args.no_window:
        open_desktop_window(app_url)

    print(f"[✓] Aegis AI Dungeon Master running live at {app_url}")
    print("[*] Press Ctrl+C to terminate.")

    try:
        server_process.join()
    except KeyboardInterrupt:
        print("\n[*] Shutting down Aegis Dungeon Master...")
        server_process.terminate()


if __name__ == "__main__":
    main()

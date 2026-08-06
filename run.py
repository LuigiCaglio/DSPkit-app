"""
DSPkit-app entry point.
Starts the FastAPI backend on port 8000 and opens the browser.
Run from the repo root with the correct venv active:
    python run.py                  # opens browser automatically
    python run.py data.csv         # ...and opens the app on that file
    python run.py --no-browser     # used by the AppLauncher (it handles the browser)

If DSPkit is already running, this opens a tab pointing at it rather than
failing to bind the port — launching twice should not be an error, and a second
server on a second port would keep its own separate session store.
"""

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

PORT = 8000
URL = f"http://127.0.0.1:{PORT}"
BACKEND_DIR = Path(__file__).parent / "backend"


def already_running() -> bool:
    """True if something on the port answers as a DSPkit backend."""
    with socket.socket() as s:
        s.settimeout(0.4)
        if s.connect_ex(("127.0.0.1", PORT)) != 0:
            return False
    try:
        with urllib.request.urlopen(f"{URL}/api/example-data", timeout=2):
            return True
    except urllib.error.HTTPError:
        return True          # responding, just not with 200
    except OSError:
        return False


def parse_args(argv):
    """(open_browser, file_to_open). A path that doesn't exist is reported, not fatal."""
    open_browser = "--no-browser" not in argv
    paths = [a for a in argv[1:] if not a.startswith("--")]
    target = None
    if paths:
        candidate = Path(paths[0]).expanduser()
        if candidate.is_file():
            target = str(candidate.resolve())
        else:
            print(f"  Ignoring '{paths[0]}' — no such file.")
    return open_browser, target


def main():
    open_browser, target = parse_args(sys.argv)

    if already_running():
        print(f"  DSPkit is already running at {URL} — opening a tab.")
        if target:
            # The running server consumed its launch target at startup, so there
            # is nothing to hand this to. Say so, rather than opening the app and
            # leaving the user wondering why their file didn't appear.
            print(f"  Open '{Path(target).name}' from that window — the file "
                  "picker and Recent files are in the left sidebar.")
        if open_browser:
            webbrowser.open(URL)
        return

    env = dict(os.environ)
    if target:
        env["DSPKIT_OPEN_FILE"] = target

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=BACKEND_DIR,
        env=env,
    )
    if open_browser:
        # Give uvicorn a moment to start before opening the browser
        time.sleep(1.5)
        webbrowser.open(URL)
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()


if __name__ == "__main__":
    main()

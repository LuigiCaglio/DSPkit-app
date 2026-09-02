"""
DSPkit-app entry point.

    python run.py                  # opens the browser automatically
    python run.py data.csv         # ...and opens the app on that file
    python run.py --port 8123      # use a specific port
    python run.py --no-browser     # used by the AppLauncher (it handles the browser)

Port selection, in order:
  1. --port N, or the DSPKIT_PORT environment variable
  2. the default, 8000
  3. if that is busy with something that is not DSPkit, the next free port

8000 is a crowded default — Django, `python -m http.server`, Jupyter and plenty
of other tools want it. Falling back automatically means a busy port is never
the user's problem; being explicit is still possible when it matters.

If DSPkit itself is already running, this opens a tab pointing at it rather than
starting a second server, which would keep its own separate session store.
"""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

DEFAULT_PORT = 8000
MAX_PORT_TRIES = 20
BACKEND_DIR = Path(__file__).parent / "backend"


def url_for(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def port_is_free(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", port)) != 0


def is_dspkit(port: int) -> bool:
    """
    True only if a *DSPkit* backend answers on this port.

    The check has to be this strict. Any HTTP server returns something, so
    treating a mere response — or a 404 — as proof of identity meant a Django
    or http.server instance on the same port was reported as "DSPkit is already
    running", and the launcher opened a browser onto someone else's app.
    """
    try:
        with urllib.request.urlopen(f"{url_for(port)}/api/health", timeout=2) as r:
            if r.status != 200:
                return False
            return json.loads(r.read()).get("app") == "dspkit-app"
    except (urllib.error.URLError, OSError, ValueError):
        return False


def choose_port(preferred: int, explicit: bool) -> tuple[int, bool]:
    """
    (port, already_running).

    An explicitly requested port is never silently swapped — if the user asked
    for it and something else holds it, that is worth an error rather than a
    surprise.
    """
    if port_is_free(preferred):
        return preferred, False
    if is_dspkit(preferred):
        return preferred, True
    if explicit:
        print(f"  Port {preferred} is in use by something that is not DSPkit.")
        print("  Pick another with:  python run.py --port 8123")
        sys.exit(1)

    for port in range(preferred + 1, preferred + 1 + MAX_PORT_TRIES):
        if port_is_free(port):
            print(f"  Port {preferred} was busy — using {port} instead.")
            return port, False
        if is_dspkit(port):
            return port, True
    print(f"  No free port found between {preferred} and {preferred + MAX_PORT_TRIES}.")
    sys.exit(1)


def parse_args(argv):
    """(open_browser, file_to_open, port, port_was_explicit)."""
    open_browser = "--no-browser" not in argv

    port, explicit = DEFAULT_PORT, False
    env_port = os.environ.get("DSPKIT_PORT")
    if env_port and env_port.isdigit():
        port, explicit = int(env_port), True
    if "--port" in argv:
        i = argv.index("--port")
        if i + 1 < len(argv) and argv[i + 1].isdigit():
            port, explicit = int(argv[i + 1]), True
        else:
            print("  --port needs a number, e.g. --port 8123")
            sys.exit(1)

    # Everything that isn't a flag or the value of --port is a candidate path.
    skip = set()
    if "--port" in argv:
        skip.add(argv.index("--port") + 1)
    paths = [a for i, a in enumerate(argv)
             if i > 0 and i not in skip and not a.startswith("--")]

    target = None
    if paths:
        candidate = Path(paths[0]).expanduser()
        if candidate.is_file():
            target = str(candidate.resolve())
        else:
            print(f"  Ignoring '{paths[0]}' — no such file.")
    return open_browser, target, port, explicit


def main():
    open_browser, target, preferred, explicit = parse_args(sys.argv)
    port, running = choose_port(preferred, explicit)
    url = url_for(port)

    if running:
        print(f"  DSPkit is already running at {url} — opening a tab.")
        if target:
            # The running server consumed its launch target at startup, so there
            # is nothing to hand this to. Say so, rather than opening the app and
            # leaving the user wondering why their file didn't appear.
            print(f"  Open '{Path(target).name}' from that window — the file "
                  "picker and Recent files are in the left sidebar.")
        if open_browser:
            webbrowser.open(url)
        return

    env = dict(os.environ)
    if target:
        env["DSPKIT_OPEN_FILE"] = target

    print(f"  DSPkit is at {url}")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=BACKEND_DIR,
        env=env,
    )
    if open_browser:
        # Give uvicorn a moment to start before opening the browser
        time.sleep(1.5)
        webbrowser.open(url)
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()


if __name__ == "__main__":
    main()

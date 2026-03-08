"""
DSPkit-app entry point.
Starts the FastAPI backend on port 8000 and opens the browser.
Run from the repo root with the correct venv active:
    python run.py
"""

import subprocess
import sys
import time
import webbrowser
from pathlib import Path

PORT = 8000
URL = f"http://127.0.0.1:{PORT}"
BACKEND_DIR = Path(__file__).parent / "backend"


def main():
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=BACKEND_DIR,
    )
    # Give uvicorn a moment to start before opening the browser
    time.sleep(1.5)
    webbrowser.open(URL)
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()


if __name__ == "__main__":
    main()

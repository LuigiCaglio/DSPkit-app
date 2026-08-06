"""Run every test suite. No third-party packages required.

    python tests/run_all.py

Starts a backend on a free port for the API tests, tears it down afterwards,
then runs the frontend unit tests with node's built-in test runner.
Exit code is non-zero if anything failed.
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
FRONTEND_TESTS = Path(__file__).parent / "frontend"
API_TESTS = Path(__file__).parent / "api"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_until_up(base, proc, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            urllib.request.urlopen(base + "/api/example-data", timeout=2)
            return True
        except urllib.error.HTTPError:
            return True          # responding, just not with 200
        except Exception:
            time.sleep(0.4)
    return False


def run_api_tests():
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    # Sessions are written to disk now. Point the server at a throwaway
    # directory so running the tests can't disturb the real recent-files list.
    state_dir = tempfile.mkdtemp(prefix="dspkit-tests-")
    env = {**os.environ, "DSPKIT_STATE_DIR": state_dir}
    print(f"starting backend on {base} …")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=BACKEND,
        env=env,
    )
    try:
        if not wait_until_up(base, proc):
            print("backend failed to start")
            return 1
        rc = 0
        for suite in ("test_api.py", "test_persistence.py", "test_detect.py",
                      "test_fdd_defaults.py"):
            rc |= subprocess.call([sys.executable, str(API_TESTS / suite), base])
        return rc
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(state_dir, ignore_errors=True)


def run_frontend_tests():
    print("\nfrontend unit tests (node --test)")
    # Pass the files explicitly: `node --test <dir>` tries to load the directory
    # itself as a module on some versions.
    files = sorted(str(p) for p in FRONTEND_TESTS.glob("*.test.mjs"))
    if not files:
        print("no frontend tests found")
        return 1
    # plotSpec.js is deliberately free of Svelte runes so node can import it.
    node = "node.exe" if sys.platform == "win32" else "node"
    try:
        return subprocess.call([node, "--test", *files])
    except FileNotFoundError:
        print("node not found on PATH — skipping frontend tests")
        return 1


if __name__ == "__main__":
    rc = run_api_tests()
    rc |= run_frontend_tests()
    print("\nALL SUITES PASSED" if rc == 0 else "\nFAILURES -- see above")
    sys.exit(rc)

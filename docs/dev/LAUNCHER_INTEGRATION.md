# AppLauncher Integration Notes

## How DSPkit-app works with the AppLauncher

The AppLauncher reads `manifest.json` at the repo root, launches `run.py` using a
user-selected venv, and opens the browser tab itself.

### manifest.json fields

```json
{
  "name": "DSPkit GUI",
  "entry": "run.py",
  "args": ["--no-browser"],
  "port": 8000,
  "url": "http://127.0.0.1:8000",
  "requirements": "backend/requirements.txt"
}
```

- `entry` — script the launcher runs: `<venv>/python.exe run.py`
- `args` — extra arguments passed to the script (`--no-browser` prevents double browser open)
- `port` — used by the launcher to check if the app is already running
- `url` — the launcher opens this in the browser after launch
- `requirements` — shown to the user so they know what to install in the venv

### What the launcher does (pseudocode)

```python
import subprocess, webbrowser, time, json
from pathlib import Path

manifest = json.loads((app_folder / "manifest.json").read_text())
venv_python = venv_folder / "Scripts" / "python.exe"  # Windows

proc = subprocess.Popen(
    [venv_python, manifest["entry"], *manifest.get("args", [])],
    cwd=app_folder,
    creationflags=subprocess.DETACHED_PROCESS,
)
time.sleep(1.5)
webbrowser.open(manifest["url"])
```

---

## Setting up on a new machine

1. Clone or download the repo:
   ```
   git clone https://github.com/LuigiCaglio/DSPkit-app
   ```
   Or download the zip from GitHub and extract it.

2. Install dependencies into your venv:
   ```
   pip install -r backend/requirements.txt
   ```
   The shared venv is at `my_packages_github/.venv` (Python 3.12).

3. Register in the AppLauncher:
   - Add the repo folder as an app
   - Select the venv that has the dependencies
   - Click Launch

4. To run without the launcher (standalone):
   ```
   python run.py
   ```

---

## Development workflow

Run backend and frontend separately (hot reload):

```bash
# Terminal 1 — backend
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm run dev
```

After changing frontend code, rebuild dist before committing:

```bash
cd frontend
npm run build
git add dist/
git commit -m "Rebuild frontend dist"
```

The `frontend/dist/` folder is committed to git so end users don't need Node.js.

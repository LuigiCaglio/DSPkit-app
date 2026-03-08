# GUI Template — Instructions for Claude

This document describes how to build a web GUI for a Python package following the
same pattern as DSPkit-app. Read this first, then read any per-package instruction
file (e.g. `GUI_BUILD_INSTRUCTIONS.md`) for package-specific details.

---

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + uvicorn |
| Frontend | Svelte 5 (runes) + Vite |
| Charts | Plotly.js (`plotly.js-dist-min`) |
| Python env | Shared venv at `my_packages_github/.venv` (Python 3.12) |

---

## Repo structure

```
<AppName>/
├── backend/
│   ├── main.py          # FastAPI app
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.svelte
│   │   ├── app.css
│   │   └── lib/
│   │       ├── PlotPanel.svelte
│   │       ├── PreprocessPanel.svelte   # if preprocessing needed
│   │       └── controls/               # one .svelte per analysis type
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── dist/            # committed to git (no Node needed for end users)
├── run.py               # entry point for AppLauncher / standalone use
├── manifest.json        # AppLauncher descriptor
└── .gitignore
```

---

## Backend — FastAPI (backend/main.py)

### Boilerplate

```python
from __future__ import annotations
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import FastAPI, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="<AppName> API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve built frontend in production
_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(_DIST / "index.html")
```

### Endpoint patterns

- **File upload + analysis params:** use `UploadFile` + `Form(...)` fields
- **Preprocessing params** (if any): use `Query(...)` so the frontend can build a URL separately
- **Always return plain Python lists** (not numpy arrays): use `np.asarray(x).tolist()`
- **Error handling:** raise `HTTPException(status_code=400, detail=str(e))` for user errors

```python
@app.post("/api/some_analysis")
async def some_analysis(
    file: UploadFile,
    param1: int = Form(...),
    param2: float = Form(0.5),
    # preprocessing as Query params if applicable
    hp_cutoff: Optional[float] = Query(None),
):
    content = await file.read()
    # ... process ...
    return {"x": x_list, "y": y_list}
```

### requirements.txt

```
fastapi
uvicorn[standard]
python-multipart
numpy
scipy
<package>@git+https://github.com/LuigiCaglio/<Package>.git
```

---

## Frontend — Svelte 5

### Key Svelte 5 rules (runes syntax — do NOT use Svelte 4 syntax)

- State: `let x = $state(value)`
- Derived: `let y = $derived(expr)`
- Effects: `$effect(() => { ... })`
- Props: `let { propName } = $props()`
- Deep reactivity on objects: mutate properties directly — Svelte 5 tracks them
- No `export let`, no `$:`, no `<script context="module">`
- Event handlers: `onclick={fn}` not `on:click={fn}`
- Snippets instead of slots

### vite.config.js

```js
import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

export default defineConfig({
  plugins: [svelte()],
  server: {
    host: '127.0.0.1',   // IMPORTANT: prevents IPv6 binding issues
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
```

### Calling the backend

```js
// File upload + form params
async function runAnalysis() {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('param1', param1)

  // Preprocessing as query params (if applicable)
  const params = new URLSearchParams()
  if (hp_cutoff) params.set('hp_cutoff', hp_cutoff)
  const url = `/api/some_analysis?${params}`

  const res = await fetch(url, { method: 'POST', body: fd })
  if (!res.ok) { error = (await res.json()).detail; return }
  result = await res.json()
}
```

### Plotly.js pattern

```js
import Plotly from 'plotly.js-dist-min'

$effect(() => {
  if (!result) return
  Plotly.react('plot-div', [{
    x: result.x,
    y: result.y,
    type: 'scatter',
    mode: 'lines',
    name: 'Signal',
  }], {
    template: 'plotly_dark',
    margin: { t: 30, r: 20, b: 50, l: 60 },
  })
})
```

For heatmaps (e.g. STFT, CWT): use `type: 'heatmap'` with `z: result.matrix`.

---

## Launcher compatibility

### run.py (repo root)

```python
import subprocess, sys, time, webbrowser
from pathlib import Path

PORT = 8000
URL = f"http://127.0.0.1:{PORT}"
BACKEND_DIR = Path(__file__).parent / "backend"

def main():
    open_browser = "--no-browser" not in sys.argv
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app",
         "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=BACKEND_DIR,
    )
    if open_browser:
        time.sleep(1.5)
        webbrowser.open(URL)
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()

if __name__ == "__main__":
    main()
```

### manifest.json (repo root)

```json
{
  "name": "<App display name>",
  "description": "<One line description>",
  "version": "0.1.0",
  "entry": "run.py",
  "args": ["--no-browser"],
  "port": 8000,
  "url": "http://127.0.0.1:8000",
  "requirements": "backend/requirements.txt"
}
```

---

## .gitignore

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
venv/
env/
*.egg-info/
backend/dist/
build/

# Node
frontend/node_modules/
frontend/.svelte-kit/
# frontend/dist/ is committed so end-users don't need Node

# OS / IDE
.DS_Store
Thumbs.db
.vscode/
.idea/
```

Also create `frontend/.gitignore`:

```gitignore
node_modules
dist-ssr
# dist/ is committed so end-users don't need Node
*.local
```

---

## Development workflow

```bash
# Backend (from backend/)
uvicorn main:app --reload --port 8000

# Frontend (from frontend/)
npm run dev
# → http://127.0.0.1:5173 (proxies /api to backend)
```

## Build and commit frontend

Run this whenever frontend source changes before committing:

```bash
cd frontend && npm run build
git add frontend/dist/
git commit -m "Rebuild frontend dist"
```

---

## Per-package customisation checklist

When building a new GUI, the package-specific instructions will define:

- [ ] What the user inputs (file upload, parameters, etc.)
- [ ] What analysis endpoints to expose and what they return
- [ ] What plots to show and what chart types to use
- [ ] Any preprocessing steps (windowing, filtering, resampling, etc.)
- [ ] Whether dual-signal support is needed
- [ ] The port number (use 8000 for the first app, increment for others to avoid conflicts)

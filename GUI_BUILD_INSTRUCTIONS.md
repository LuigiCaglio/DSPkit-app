# DSPkit-app — Build Instructions for New Claude Session

## Goal

Build a web GUI for the DSPkit Python package. The user uploads a signal file (CSV), selects an analysis, tunes parameters, and sees an interactive Plotly chart. No matplotlib — all rendering is done in the browser via Plotly.js.

---

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Svelte 5 + Vite |
| Charts | Plotly.js |
| Backend | FastAPI (Python 3.10+) |
| Python lib | DSPkit (installed from local clone or pip) |
| Dev runner | `uvicorn` for backend, `npm run dev` for frontend |

---

## Repository layout

```
DSPkit-app/
  backend/
    main.py           ← FastAPI app (single file to start)
    requirements.txt
  frontend/
    src/
      App.svelte
      lib/
        FileUpload.svelte
        AnalysisPanel.svelte
        PlotPanel.svelte
        controls/     ← one .svelte per analysis type
    public/
    package.json
    vite.config.js
  README.md
```

Create this as a **separate git repo** from DSPkit.

---

## Backend — FastAPI

### requirements.txt

```
fastapi
uvicorn[standard]
python-multipart
numpy
scipy
matplotlib       # only needed if DSPkit pulls it; no plots used in backend
dspkit @ git+https://github.com/LuigiCaglio/DSPkit.git
```

Or if working locally alongside DSPkit:
```
dspkit @ file:///absolute/path/to/DSPkit
```

### Running

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### CORS

Enable CORS for `http://localhost:5173` (Vite dev server):

```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### NumPy → JSON serialization

NumPy arrays are not JSON-serializable by default. Use a helper:

```python
import numpy as np

def to_list(arr) -> list:
    """Convert numpy array to Python list for JSON response."""
    return np.asarray(arr).tolist()
```

### File upload pattern

```python
from fastapi import UploadFile, Form
import io, csv
import numpy as np

async def parse_upload(file: UploadFile) -> tuple[np.ndarray, float]:
    """
    Parse uploaded CSV. Expected format:
      - 1-column: signal values only (fs passed as form field)
      - 2-column: time, signal (fs inferred from time column)
    Returns (signal_array, fs).
    """
    content = await file.read()
    text = content.decode("utf-8")
    rows = list(csv.reader(io.StringIO(text)))
    data = np.array([[float(v) for v in r] for r in rows if r and not r[0].startswith('#')])
    if data.ndim == 1 or data.shape[1] == 1:
        raise ValueError("Need fs from form field for 1-column CSV")
    times = data[:, 0]
    signal = data[:, 1]
    fs = 1.0 / np.mean(np.diff(times))
    return signal, fs
```

---

## Backend — API endpoints

### Design rules

- All endpoints: `POST` (signal data is always in the request body)
- Input: `multipart/form-data` — file upload + JSON params as form fields
- Output: `application/json` — always `{ "x": [...], "y": [...], ... }`
- Errors: return `{ "detail": "message" }` with HTTP 422

### Endpoint list

#### `POST /api/signal/info`
Returns basic metadata: `{ "n_samples", "fs", "duration", "rms", "peak", "crest_factor" }`

#### `POST /api/spectral/fft`
Params: `fs`, `window` (default "hann"), `scaling` ("amplitude"|"rms")
Returns: `{ "freqs": [...], "amplitude": [...] }`

Maps to: `dsp.fft_spectrum(x, fs, window, scaling)`

#### `POST /api/spectral/psd`
Params: `fs`, `nperseg` (default 1024), `noverlap` (optional), `window` (default "hann"), `scaling` ("density"|"spectrum")
Returns: `{ "freqs": [...], "Pxx": [...] }`

Maps to: `dsp.psd(x, fs, window, nperseg, noverlap, scaling)`

#### `POST /api/spectral/autocorrelation`
Params: `fs`, `normalize` (bool, default true), `max_lag` (float, optional)
Returns: `{ "lags": [...], "acf": [...] }`

Maps to: `dsp.autocorrelation(x, fs, normalize, max_lag)`

#### `POST /api/filter/apply`
Params: `fs`, `filter_type` ("lowpass"|"highpass"|"bandpass"|"bandstop"|"notch"), `cutoff` (for LP/HP), `low` (for BP/BS), `high` (for BP/BS), `freq` (for notch), `order` (default 4), `zero_phase` (bool, default true)
Returns: `{ "times": [...], "signal_raw": [...], "signal_filtered": [...] }`

Maps to: `dsp.lowpass / dsp.highpass / dsp.bandpass / dsp.bandstop / dsp.notch`

#### `POST /api/timefreq/stft`
Params: `fs`, `nperseg` (default 256), `noverlap` (optional), `window` (default "hann")
Returns: `{ "freqs": [...], "times": [...], "magnitude": [[...]] }` — magnitude is `|Zxx|`, shape (n_freqs, n_times)

Maps to: `dsp.stft(x, fs, window, nperseg, noverlap)` → `np.abs(Zxx)`

#### `POST /api/timefreq/cwt`
Params: `fs`, `f_min` (default 1.0), `f_max` (default fs/4), `n_freqs` (default 50), `w` (default 6.0)
Returns: `{ "freqs": [...], "times": [...], "magnitude": [[...]] }` — `|W|`, shape (n_freqs, n_times)

Maps to: `dsp.cwt_scalogram(x, fs, freqs=np.geomspace(f_min, f_max, n_freqs), w=w)` → `np.abs(W)`

#### `POST /api/timefreq/wvd`
Params: `fs`
**Warning**: enforces `len(x) <= 2048` — return HTTP 422 with message if exceeded.
Returns: `{ "freqs": [...], "times": [...], "wvd": [[...]] }` — shape (n_times, n_freqs)

Maps to: `dsp.wigner_ville(x, fs)`

#### `POST /api/timefreq/spwvd`
Params: `fs`, `lag_samples` (optional), `time_samples` (optional)
**Warning**: enforces `len(x) <= 2048`.
Returns: `{ "freqs": [...], "times": [...], "spwvd": [[...]] }`

Maps to: `dsp.smoothed_pseudo_wv(x, fs, lag_samples, time_samples)`

#### `POST /api/instantaneous`
Params: `fs`
Returns: `{ "times": [...], "envelope": [...], "phase": [...], "inst_freq": [...] }`

Maps to: `dsp.hilbert_attributes(x, fs)`

#### `POST /api/emd/decompose`
Params: `fs`, `max_imfs` (default null → all), `max_sifting` (default 10)
**Warning**: slow for long signals. Recommend len(x) <= 5000.
Returns: `{ "times": [...], "imfs": [[...], ...], "residue": [...] }` — imfs shape (n_imfs, N)

Maps to: `dsp.emd(x, max_imfs, max_sifting)`

#### `POST /api/emd/hht`
Params: `fs`, `n_bins` (default 512)
Takes same file + params as `/api/emd/decompose` but also returns HHT.
Returns: `{ "times": [...], "imfs": [[...]], "residue": [...], "envelopes": [[...]], "inst_freqs": [[...]], "marginal_freqs": [...], "marginal_spectrum": [...] }`

Maps to: `dsp.emd(x)` → `dsp.hht(imfs, fs)` → `dsp.hht_marginal_spectrum(envs, inst_freqs, fs, n_bins)`

---

## DSPkit function reference

All functions are importable from `dspkit` directly (they are all re-exported from `dspkit/__init__.py`).

```python
import dspkit as dsp
```

### spectral.py

```python
fft_spectrum(x, fs, window="hann", scaling="amplitude")
    → (freqs, amplitude)            # both shape (N//2+1,)

psd(x, fs, window="hann", nperseg=None, noverlap=None,
    scaling="density", detrend="constant")
    → (freqs, Pxx)

csd(x, y, fs, window="hann", nperseg=None, noverlap=None, detrend="constant")
    → (freqs, Pxy)                  # Pxy is complex

coherence(x, y, fs, window="hann", nperseg=None, noverlap=None, detrend="constant")
    → (freqs, Cxy)                  # Cxy real, values in [0,1]

autocorrelation(x, fs=None, normalize=True, max_lag=None)
    → (lags, acf)                   # lags in seconds if fs given, else samples

cross_correlation(x, y, fs=None, normalize=True, max_lag=None)
    → (lags, ccf)                   # two-sided, lags symmetric about 0
```

### filters.py

```python
lowpass(x, fs, cutoff, order=4, zero_phase=True)    → ndarray shape (N,)
highpass(x, fs, cutoff, order=4, zero_phase=True)   → ndarray shape (N,)
bandpass(x, fs, low, high, order=4, zero_phase=True) → ndarray shape (N,)
bandstop(x, fs, low, high, order=4, zero_phase=True) → ndarray shape (N,)
notch(x, fs, freq, q=30.0, zero_phase=True)          → ndarray shape (N,)
decimate(x, fs, target_fs, zero_phase=True)          → (x_decimated, target_fs)
    # fs/target_fs must be close to a positive integer
```

### utils.py

```python
detrend(x, order=1)              → ndarray   # 0=mean, 1=linear, higher=poly
rms(x)                           → float
peak(x)                          → float     # max(|x|)
crest_factor(x)                  → float     # peak / rms
integrate(x, fs, detrend_after=True, detrend_order=1)  → ndarray
differentiate(x, fs)             → ndarray
```

### timefreq.py

```python
stft(x, fs, window="hann", nperseg=256, noverlap=None, scaling="spectrum")
    → (freqs, times, Zxx)
    # freqs shape (nperseg//2+1,), Zxx shape (n_freqs, n_times), complex
    # noverlap defaults to nperseg*3//4 (75%)

cwt_scalogram(x, fs, freqs=None, w=6.0)
    → (freqs, times, W)
    # freqs defaults to 50 log-spaced from 1 Hz to fs/4
    # W shape (len(freqs), N), complex

wigner_ville(x, fs, warn_above=2048)
    → (freqs, times, WVD)
    # freqs shape (N//2+1,), range 0..fs/4   ← NOT 0..fs/2
    # times shape (N,)
    # WVD shape (N, N//2+1)  i.e. (n_times, n_freqs)
    # ⚠ O(N²) — hard-limit N <= 2048 in the API

smoothed_pseudo_wv(x, fs, lag_samples=None, time_samples=None, warn_above=2048)
    → (freqs, times, SPWVD)
    # same shapes as wigner_ville
    # lag_samples, time_samples default to max(N//8, 4)
    # ⚠ O(N²) — hard-limit N <= 2048 in the API
```

### instantaneous.py

```python
hilbert_attributes(x, fs)
    → (envelope, phase, freq)   # all shape (N,)
    # envelope: instantaneous amplitude [same units as x]
    # phase: unwrapped instantaneous phase [rad]
    # freq: instantaneous frequency [Hz]

analytic_signal(x)              → ndarray complex (N,)
hilbert_envelope(x)             → ndarray (N,)
instantaneous_phase(x)          → ndarray (N,) [rad]
instantaneous_freq(x, fs)       → ndarray (N,) [Hz]
```

### emd.py

```python
emd(x, max_imfs=None, max_sifting=10, sd_threshold=0.2)
    → (imfs, residue)
    # imfs shape (n_imfs, N), ordered highest→lowest freq
    # residue shape (N,)
    # reconstruction: imfs.sum(axis=0) + residue ≈ x

hht(imfs, fs)
    → (envelopes, inst_freqs)   # both shape (n_imfs, N)

hht_marginal_spectrum(envelopes, inst_freqs, fs, n_bins=512)
    → (freq_bins, spectrum)     # both shape (n_bins,), range 0..fs/2
```

---

## Frontend — Svelte

### Installing

```bash
npm create vite@latest frontend -- --template svelte
cd frontend
npm install
npm install plotly.js-dist-min
npm run dev   # http://localhost:5173
```

### vite.config.js

```js
import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

export default defineConfig({
  plugins: [svelte()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000'   // proxy to FastAPI
    }
  }
})
```

With the proxy, frontend can call `/api/...` without specifying host.

### Key Plotly patterns

**Line chart (PSD, FFT, ACF):**
```js
import Plotly from 'plotly.js-dist-min'

Plotly.newPlot(divEl, [{
  x: freqs,
  y: Pxx,
  type: 'scatter',
  mode: 'lines',
  name: 'PSD'
}], {
  xaxis: { title: 'Frequency [Hz]' },
  yaxis: { title: 'PSD [units²/Hz]', type: 'log' }
})
```

**Heatmap (STFT, CWT, WVD):**
```js
Plotly.newPlot(divEl, [{
  x: times,
  y: freqs,
  z: magnitude,     // 2D array shape [n_freqs][n_times]
  type: 'heatmap',
  colorscale: 'Viridis'
}], {
  xaxis: { title: 'Time [s]' },
  yaxis: { title: 'Frequency [Hz]' }
})
```

Note: CWT and STFT return magnitude in shape `(n_freqs, n_times)` — this is already the right orientation for Plotly heatmap `z`.
WVD/SPWVD return `(n_times, n_freqs)` — **transpose before plotting**: `z = wvd[i]` → just pass the 2D array as-is if you iterate rows as time steps, or transpose to `[n_freqs][n_times]` for Plotly.

**HHT scatter (time-frequency energy plot):**
```js
// One trace per IMF
const traces = inst_freqs.map((fi, i) => ({
  x: times,
  y: fi,
  mode: 'markers',
  marker: { color: envelopes[i], colorscale: 'Viridis', size: 3 },
  name: `IMF ${i+1}`
}))
Plotly.newPlot(divEl, traces, { xaxis: { title: 'Time [s]' }, yaxis: { title: 'Freq [Hz]' } })
```

---

## Suggested UI layout

```
┌──────────────────────────────────────────────────────────┐
│  DSPkit GUI                                              │
├──────────┬───────────────────────────────────────────────┤
│  Sidebar │  Main panel                                   │
│          │                                               │
│ [Upload  │  ┌────────────── Plot ──────────────────┐    │
│  CSV]    │  │  (Plotly chart fills this area)       │    │
│          │  └──────────────────────────────────────┘    │
│ Analysis │                                               │
│  tabs:   │  ┌───── Controls ───────────────────────┐    │
│  • FFT   │  │  Parameter sliders / inputs for the   │    │
│  • PSD   │  │  selected analysis                    │    │
│  • Filter│  │  [Run] button                         │    │
│  • STFT  │  └──────────────────────────────────────┘    │
│  • CWT   │                                               │
│  • WVD   │                                               │
│  • Inst. │                                               │
│  • EMD   │                                               │
└──────────┴───────────────────────────────────────────────┘
```

---

## Build order (recommended)

1. **Backend skeleton** — `main.py` with CORS, `/api/signal/info`, and one endpoint (`/api/spectral/psd`). Test with curl or httpie.
2. **Frontend skeleton** — FileUpload component, one fetch call to `/api/signal/info`, display metadata.
3. **PSD tab end-to-end** — controls (nperseg slider), fetch, Plotly line chart. This proves the full pipeline.
4. **FFT, ACF tabs** — similar line-chart pattern, quick to add.
5. **Filter tab** — two-line chart (raw + filtered), filter_type selector.
6. **STFT tab** — heatmap, nperseg slider.
7. **CWT tab** — heatmap, f_min/f_max/n_freqs inputs.
8. **WVD / SPWVD tabs** — heatmap, warn user if signal > 2048 samples.
9. **Instantaneous tab** — multi-line chart (signal, envelope, inst_freq).
10. **EMD tab** — waterfall of IMF lines + HHT scatter + marginal spectrum.

---

## Important caveats

- **WVD/SPWVD are O(N²).** The API must enforce `len(x) <= 2048` and return HTTP 422 if exceeded. Tell the user to upload a shorter segment or decimate first.
- **EMD is slow** for long signals. Suggest `len(x) <= 5000` and show a loading spinner.
- **WVD frequency axis goes to fs/4, not fs/2.** This is correct — the half-lag WVD covers 0..fs/4.
- **Plotly heatmap `z` orientation**: rows = y-axis, columns = x-axis. STFT/CWT return `(n_freqs, n_times)` — correct. WVD returns `(n_times, n_freqs)` — need `z = wvd.T.tolist()` before sending, or transpose in frontend.
- **CSV format**: recommend user supplies time + signal (2 columns). Or 1 column + fs entered manually.
- Do not use `dspkit.plots` — those are matplotlib wrappers and have no role in the GUI.

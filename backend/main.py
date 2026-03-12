"""
DSPkit-app — FastAPI backend
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import FastAPI, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from scipy.signal import get_window

import dspkit as dsp

app = FastAPI(title="DSPkit GUI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── static frontend (production) ─────────────────────────────────────────────
_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(_DIST / "index.html")


# ─── example data ─────────────────────────────────────────────────────────────
_EXAMPLE_FILE = Path(__file__).parent.parent / "example_data" / "2dof_vibration.csv"


@app.get("/api/example-data")
async def example_data_list():
    """Return list of available example datasets."""
    examples = []
    if _EXAMPLE_FILE.exists():
        examples.append({
            "id": "2dof_vibration",
            "name": "2-DOF Vibration (5ch)",
            "description": "Two-mass spring-damper system under white noise. f1~10 Hz, f2~25 Hz. Columns: time, x1, x2, force1, force2.",
            "filename": _EXAMPLE_FILE.name,
        })
    return {"examples": examples}


@app.get("/api/example-data/{example_id}")
async def example_data_download(example_id: str):
    """Download an example dataset as a file."""
    if example_id == "2dof_vibration" and _EXAMPLE_FILE.exists():
        return FileResponse(_EXAMPLE_FILE, filename=_EXAMPLE_FILE.name, media_type="text/csv")
    raise HTTPException(status_code=404, detail=f"Example '{example_id}' not found")


# ─── file parsing ─────────────────────────────────────────────────────────────


def to_list(arr) -> list:
    a = np.asarray(arr)
    if np.iscomplexobj(a):
        a = np.abs(a)
    return a.tolist()


def detect_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t; ")
        return dialect.delimiter
    except csv.Error:
        return ","


def parse_file(content: bytes, orientation: str = "columns", header_row: int = -1) -> dict:
    """
    Parse CSV / TSV / TXT content.

    orientation : "columns" each column is a signal (default)
                  "rows"    each row is a signal
    header_row  : -1 = no header; >=0 = row index of column names
                  (all rows before it are skipped as metadata/comments)
    Returns dict with column_names, data (n_signals, n_samples), n_samples, n_columns.
    """
    text = content.decode("utf-8-sig")
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        raise ValueError("File is empty")

    sample_start = max(0, header_row if header_row >= 0 else 0)
    sample = "\n".join(lines[sample_start : sample_start + 20])
    delimiter = detect_delimiter(sample)

    reader = csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter)
    all_rows = list(reader)

    column_names: Optional[list[str]] = None
    if header_row >= 0 and header_row < len(all_rows):
        column_names = [c.strip() for c in all_rows[header_row]]
        data_rows = all_rows[header_row + 1 :]
    else:
        data_rows = all_rows

    numeric_rows: list[list[float]] = []
    for row in data_rows:
        if not row or row[0].strip().startswith("#"):
            continue
        try:
            numeric_rows.append([float(v.strip()) for v in row if v.strip()])
        except ValueError:
            continue

    if not numeric_rows:
        raise ValueError("No numeric data found in file")

    data = np.array(numeric_rows)  # (n_file_rows, n_file_cols)

    if orientation == "columns":
        data = data.T  # → (n_signals, n_samples)

    n_signals, n_samples = data.shape

    if column_names is None:
        column_names = [f"Signal {i+1}" for i in range(n_signals)]
    elif len(column_names) < n_signals:
        column_names += [f"Signal {i+1}" for i in range(len(column_names), n_signals)]
    elif len(column_names) > n_signals:
        column_names = column_names[:n_signals]

    return {"column_names": column_names, "data": data, "n_samples": n_samples, "n_columns": n_signals}


def extract_col(parsed: dict, col: int) -> np.ndarray:
    n = parsed["n_columns"]
    if col < 0 or col >= n:
        raise ValueError(f"Column index {col} out of range (file has {n} columns: 0..{n-1})")
    return parsed["data"][col]


def get_signal_times_fs(
    parsed: dict, time_col: int, signal_col: int, fs: Optional[float]
) -> tuple[np.ndarray, Optional[np.ndarray], float]:
    """Return (x, times_or_None, fs)."""
    x = extract_col(parsed, signal_col)
    if time_col >= 0:
        t = extract_col(parsed, time_col)
        fs_calc = 1.0 / float(np.mean(np.diff(t)))
        return x, t, fs_calc
    if fs is not None and fs > 0:
        return x, None, float(fs)
    raise ValueError("Provide either a time column (time_col >= 0) or a sample rate (fs > 0)")


# ─── preprocessing ────────────────────────────────────────────────────────────


def apply_preprocessing(
    x: np.ndarray,
    fs: float,
    times: Optional[np.ndarray],
    win_start: Optional[float],
    win_end: Optional[float],
    win_unit: str,          # "samples" | "time"
    hp_cutoff: Optional[float],
    lp_cutoff: Optional[float],
    target_fs: Optional[float],
) -> tuple[np.ndarray, float, np.ndarray]:
    """
    Apply preprocessing steps in order:
      1. Window (select time range)
      2. High-pass filter
      3. Low-pass filter
      4. Resample (up or down)

    Returns (x_processed, fs_processed, times_processed).
    """
    N = len(x)
    if times is None:
        times = np.arange(N) / fs

    # 1. Windowing
    if win_start is not None or win_end is not None:
        if win_unit == "time":
            i0 = int((win_start or 0.0) * fs) if win_start is not None else 0
            i1 = int(win_end * fs) if win_end is not None else N
        else:  # samples
            i0 = int(win_start) if win_start is not None else 0
            i1 = int(win_end) if win_end is not None else N
        i0 = max(0, min(i0, N - 1))
        i1 = max(i0 + 1, min(i1, N))
        x = x[i0:i1]
        times = times[i0:i1]

    # 2. High-pass filter
    if hp_cutoff is not None and hp_cutoff > 0:
        x = dsp.highpass(x, fs, hp_cutoff, order=4, zero_phase=True)

    # 3. Low-pass filter
    if lp_cutoff is not None and lp_cutoff > 0:
        x = dsp.lowpass(x, fs, lp_cutoff, order=4, zero_phase=True)

    # 4. Resample — use linear interpolation to avoid group-delay time shift
    if target_fs is not None and abs(target_fs - fs) > 0.01:
        n_new = round(len(x) * target_fs / fs)
        t_new = np.linspace(times[0], times[-1], n_new)
        x     = np.interp(t_new, times, x)
        times = t_new
        fs    = float(target_fs)

    return x, fs, times


def get_preprocessed(
    parsed: dict,
    time_col: int,
    signal_col: int,
    fs_manual: Optional[float],
    win_start: Optional[float],
    win_end: Optional[float],
    win_unit: str,
    hp_cutoff: Optional[float],
    lp_cutoff: Optional[float],
    target_fs: Optional[float],
) -> tuple[np.ndarray, float, np.ndarray]:
    """Column extraction + preprocessing in one call. Returns (x, fs, times)."""
    x, times, fs = get_signal_times_fs(parsed, time_col, signal_col, fs_manual)
    return apply_preprocessing(x, fs, times, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)


# ─── /api/signal/parse ───────────────────────────────────────────────────────


@app.post("/api/signal/parse")
async def signal_parse(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    fs: Optional[float] = Form(None),
):
    try:
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        preview_len = min(50, parsed["n_samples"])
        preview = parsed["data"][:, :preview_len].T.tolist()
        result = {
            "column_names": parsed["column_names"],
            "n_columns": parsed["n_columns"],
            "n_samples": parsed["n_samples"],
            "preview": preview,
        }
        inferred_fs: Optional[float] = None
        if time_col >= 0 and time_col < parsed["n_columns"]:
            t = extract_col(parsed, time_col)
            inferred_fs = 1.0 / float(np.mean(np.diff(t)))
        elif fs is not None and fs > 0:
            inferred_fs = float(fs)
        if inferred_fs:
            result["fs"] = round(inferred_fs, 6)
            result["duration"] = round(parsed["n_samples"] / inferred_fs, 4)
        return result
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── /api/signal/info ────────────────────────────────────────────────────────


@app.post("/api/signal/info")
async def signal_info(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_cols: str = Form(...),
    fs: Optional[float] = Form(None),
):
    try:
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        cols = [int(c.strip()) for c in signal_cols.split(",") if c.strip()]
        inferred_fs: Optional[float] = fs
        if time_col >= 0:
            t = extract_col(parsed, time_col)
            inferred_fs = 1.0 / float(np.mean(np.diff(t)))
        signals_info = []
        for col in cols:
            x = extract_col(parsed, col)
            signals_info.append({
                "name": parsed["column_names"][col],
                "rms": float(dsp.rms(x)),
                "peak": float(dsp.peak(x)),
                "crest_factor": float(dsp.crest_factor(x)),
            })
        n_samples = parsed["n_samples"]
        duration = n_samples / inferred_fs if inferred_fs else None
        return {"n_samples": n_samples, "fs": inferred_fs, "duration": duration, "signals": signals_info}
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── /api/signal/timeseries ──────────────────────────────────────────────────


@app.post("/api/signal/timeseries")
async def signal_timeseries(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_cols: str = Form(...),   # JSON array e.g. "[0, 1, 2]"
    fs: Optional[float] = Form(None),
    win_start:  Optional[float] = Query(None),
    win_end:    Optional[float] = Query(None),
    win_unit:   str             = Query("samples"),
    hp_cutoff:  Optional[float] = Query(None),
    lp_cutoff:  Optional[float] = Query(None),
    target_fs:  Optional[float] = Query(None),
):
    try:
        cols = [int(c) for c in json.loads(signal_cols)]
        if not cols:
            raise ValueError("No signal columns selected")
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)

        # Reference time axis from first column
        x0, t_raw, fs_raw = get_signal_times_fs(parsed, time_col, cols[0], fs)
        if t_raw is None:
            t_raw = np.arange(len(x0)) / fs_raw

        # Process first column to get processed time axis
        x0_proc, fs_proc, t_proc = apply_preprocessing(
            x0.copy(), fs_raw, t_raw.copy(),
            win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs,
        )

        preprocessed = any(v is not None for v in [win_start, win_end, hp_cutoff, lp_cutoff, target_fs])

        signals = []
        for i, col in enumerate(cols):
            x_raw = extract_col(parsed, col)
            x_proc, _, _ = apply_preprocessing(
                x_raw.copy(), fs_raw, t_raw.copy(),
                win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs,
            )
            signals.append({
                "name": parsed["column_names"][col],
                "signal_raw": to_list(x_raw),
                "signal_proc": to_list(x_proc),
            })

        return {
            "times_raw":  to_list(t_raw),
            "times_proc": to_list(t_proc),
            "fs_raw":     fs_raw,
            "fs_proc":    fs_proc,
            "n_proc":     len(t_proc),
            "preprocessed": preprocessed,
            "signals":    signals,
        }
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── spectral ────────────────────────────────────────────────────────────────


@app.post("/api/spectral/fft")
async def spectral_fft(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_cols: str = Form(...),
    fs: Optional[float] = Form(None),
    window: str = Form("hann"),
    scaling: str = Form("amplitude"),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        cols = [int(c) for c in json.loads(signal_cols)]
        if not cols:
            raise ValueError("No signal columns selected")
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        x0, fs_, _ = get_preprocessed(parsed, time_col, cols[0], fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
        freqs, _ = dsp.fft_spectrum(x0, fs_, window=window, scaling=scaling)
        signals = []
        for col in cols:
            x, _, _ = get_preprocessed(parsed, time_col, col, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
            _, amp = dsp.fft_spectrum(x, fs_, window=window, scaling=scaling)
            win_arr = get_window(window, len(x))
            phase = np.angle(np.fft.rfft(x * win_arr), deg=True)
            signals.append({"name": parsed["column_names"][col], "amplitude": to_list(amp), "phase": to_list(phase)})
        return {"freqs": to_list(freqs), "signals": signals}
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/spectral/psd")
async def spectral_psd(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_cols: str = Form(...),
    fs: Optional[float] = Form(None),
    window: str = Form("hann"),
    nperseg: int = Form(1024),
    noverlap: Optional[int] = Form(None),
    scaling: str = Form("density"),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        cols = [int(c) for c in json.loads(signal_cols)]
        if not cols:
            raise ValueError("No signal columns selected")
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        x0, fs_, _ = get_preprocessed(parsed, time_col, cols[0], fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
        freqs, _ = dsp.psd(x0, fs_, window=window, nperseg=nperseg, noverlap=noverlap, scaling=scaling)
        signals = []
        for col in cols:
            x, _, _ = get_preprocessed(parsed, time_col, col, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
            _, Pxx = dsp.psd(x, fs_, window=window, nperseg=nperseg, noverlap=noverlap, scaling=scaling)
            signals.append({"name": parsed["column_names"][col], "Pxx": to_list(Pxx)})
        return {"freqs": to_list(freqs), "signals": signals}
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/spectral/autocorrelation")
async def spectral_autocorrelation(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_cols: str = Form(...),
    fs: Optional[float] = Form(None),
    normalize: bool = Form(True),
    max_lag: Optional[float] = Form(None),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        cols = [int(c) for c in json.loads(signal_cols)]
        if not cols:
            raise ValueError("No signal columns selected")
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        x0, fs_, _ = get_preprocessed(parsed, time_col, cols[0], fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
        lags, _ = dsp.autocorrelation(x0, fs=fs_, normalize=normalize, max_lag=max_lag)
        signals = []
        for col in cols:
            x, _, _ = get_preprocessed(parsed, time_col, col, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
            _, acf = dsp.autocorrelation(x, fs=fs_, normalize=normalize, max_lag=max_lag)
            signals.append({"name": parsed["column_names"][col], "acf": to_list(acf)})
        return {"lags": to_list(lags), "signals": signals}
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/spectral/cross_correlation")
async def spectral_cross_correlation(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col_x: int = Form(...),
    signal_col_y: int = Form(...),
    fs: Optional[float] = Form(None),
    normalize: bool = Form(True),
    max_lag: Optional[float] = Form(None),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col_x, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
        y, _, _ = get_preprocessed(parsed, time_col, signal_col_y, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
        lags, ccf = dsp.cross_correlation(x, y, fs=fs_, normalize=normalize, max_lag=max_lag)
        return {"lags": to_list(lags), "ccf": to_list(ccf)}
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/spectral/csd")
async def spectral_csd(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col_x: int = Form(...),
    signal_col_y: int = Form(...),
    fs: Optional[float] = Form(None),
    window: str = Form("hann"),
    nperseg: int = Form(1024),
    noverlap: Optional[int] = Form(None),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col_x, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
        y, _, _ = get_preprocessed(parsed, time_col, signal_col_y, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
        freqs, Pxy = dsp.csd(x, y, fs_, window=window, nperseg=nperseg, noverlap=noverlap)
        return {"freqs": to_list(freqs), "magnitude": to_list(np.abs(Pxy)), "phase_deg": to_list(np.angle(Pxy, deg=True))}
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/spectral/coherence")
async def spectral_coherence(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col_x: int = Form(...),
    signal_col_y: int = Form(...),
    fs: Optional[float] = Form(None),
    window: str = Form("hann"),
    nperseg: int = Form(1024),
    noverlap: Optional[int] = Form(None),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col_x, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
        y, _, _ = get_preprocessed(parsed, time_col, signal_col_y, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
        freqs, Cxy = dsp.coherence(x, y, fs_, window=window, nperseg=nperseg, noverlap=noverlap)
        _, Pxy = dsp.csd(x, y, fs_, window=window, nperseg=nperseg, noverlap=noverlap)
        return {"freqs": to_list(freqs), "Cxy": to_list(Cxy), "phase_deg": to_list(np.angle(Pxy, deg=True))}
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── filter ──────────────────────────────────────────────────────────────────


@app.post("/api/filter/apply")
async def filter_apply(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    filter_type: str = Form(...),
    cutoff: Optional[float] = Form(None),
    low: Optional[float] = Form(None),
    high: Optional[float] = Form(None),
    freq: Optional[float] = Form(None),
    order: int = Form(4),
    zero_phase: bool = Form(True),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)

        ft = filter_type.lower()
        if ft == "lowpass":
            if cutoff is None: raise ValueError("cutoff required for lowpass")
            y = dsp.lowpass(x, fs_, cutoff, order=order, zero_phase=zero_phase)
        elif ft == "highpass":
            if cutoff is None: raise ValueError("cutoff required for highpass")
            y = dsp.highpass(x, fs_, cutoff, order=order, zero_phase=zero_phase)
        elif ft == "bandpass":
            if low is None or high is None: raise ValueError("low and high required for bandpass")
            y = dsp.bandpass(x, fs_, low, high, order=order, zero_phase=zero_phase)
        elif ft == "bandstop":
            if low is None or high is None: raise ValueError("low and high required for bandstop")
            y = dsp.bandstop(x, fs_, low, high, order=order, zero_phase=zero_phase)
        elif ft == "notch":
            if freq is None: raise ValueError("freq required for notch")
            y = dsp.notch(x, fs_, freq, zero_phase=zero_phase)
        else:
            raise ValueError(f"Unknown filter_type: {filter_type!r}")

        return {"times": to_list(t), "signal_raw": to_list(x), "signal_filtered": to_list(y)}
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── time-frequency ───────────────────────────────────────────────────────────


@app.post("/api/timefreq/stft")
async def timefreq_stft(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    window: str = Form("hann"),
    nperseg: int = Form(256),
    noverlap: Optional[int] = Form(None),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
        freqs, times, Zxx = dsp.stft(x, fs_, window=window, nperseg=nperseg, noverlap=noverlap)
        return {"freqs": to_list(freqs), "times": to_list(times), "magnitude": to_list(np.abs(Zxx))}
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/timefreq/cwt")
async def timefreq_cwt(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    f_min: float = Form(1.0),
    f_max: Optional[float] = Form(None),
    n_freqs: int = Form(50),
    w: float = Form(6.0),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
        f_max_ = f_max if f_max is not None else fs_ / 4.0
        freqs = np.geomspace(f_min, f_max_, n_freqs)
        freqs_out, times, W = dsp.cwt_scalogram(x, fs_, freqs=freqs, w=w)
        return {"freqs": to_list(freqs_out), "times": to_list(times), "magnitude": to_list(np.abs(W))}
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/timefreq/wvd")
async def timefreq_wvd(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
        if len(x) > 2048:
            raise HTTPException(status_code=422, detail=f"Signal too long for WVD ({len(x)} samples). Maximum is 2048.")
        freqs, times, WVD = dsp.wigner_ville(x, fs_)
        return {"freqs": to_list(freqs), "times": to_list(times), "wvd": to_list(WVD.T)}
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/timefreq/spwvd")
async def timefreq_spwvd(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    lag_samples: Optional[int] = Form(None),
    time_samples: Optional[int] = Form(None),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
        if len(x) > 2048:
            raise HTTPException(status_code=422, detail=f"Signal too long for SPWVD ({len(x)} samples). Maximum is 2048.")
        freqs, times, SPWVD = dsp.smoothed_pseudo_wv(x, fs_, lag_samples=lag_samples, time_samples=time_samples)
        return {"freqs": to_list(freqs), "times": to_list(times), "spwvd": to_list(SPWVD.T)}
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── instantaneous ────────────────────────────────────────────────────────────


@app.post("/api/instantaneous")
async def instantaneous(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
        envelope, phase, inst_freq = dsp.hilbert_attributes(x, fs_)
        return {
            "times": to_list(t),
            "signal": to_list(x),
            "envelope": to_list(envelope),
            "phase": to_list(phase),
            "inst_freq": to_list(inst_freq),
        }
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── EMD ─────────────────────────────────────────────────────────────────────


@app.post("/api/emd/decompose")
async def emd_decompose(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    max_imfs: Optional[int] = Form(None),
    max_sifting: int = Form(10),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
        imfs, residue = dsp.emd(x, max_imfs=max_imfs, max_sifting=max_sifting)
        return {"times": to_list(t), "imfs": to_list(imfs), "residue": to_list(residue)}
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/emd/hht")
async def emd_hht(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    max_imfs: Optional[int] = Form(None),
    max_sifting: int = Form(10),
    n_bins: int = Form(512),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
        imfs, residue = dsp.emd(x, max_imfs=max_imfs, max_sifting=max_sifting)
        envelopes, inst_freqs = dsp.hht(imfs, fs_)
        marginal_freqs, marginal_spectrum = dsp.hht_marginal_spectrum(envelopes, inst_freqs, fs_, n_bins=n_bins)
        return {
            "times": to_list(t),
            "imfs": to_list(imfs),
            "residue": to_list(residue),
            "envelopes": to_list(envelopes),
            "inst_freqs": to_list(inst_freqs),
            "marginal_freqs": to_list(marginal_freqs),
            "marginal_spectrum": to_list(marginal_spectrum),
        }
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── helpers: multi-channel ──────────────────────────────────────────────────


def get_multichannel(
    parsed: dict,
    time_col: int,
    signal_cols: list[int],
    fs_manual: Optional[float],
    win_start: Optional[float],
    win_end: Optional[float],
    win_unit: str,
    hp_cutoff: Optional[float],
    lp_cutoff: Optional[float],
    target_fs: Optional[float],
) -> tuple[np.ndarray, float, np.ndarray, list[str]]:
    """Return (data [n_ch × N], fs, times, labels)."""
    channels = []
    fs_out = None
    times_out = None
    labels = []
    for col in signal_cols:
        x, fs_, t = get_preprocessed(
            parsed, time_col, col, fs_manual,
            win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs,
        )
        channels.append(x)
        if fs_out is None:
            fs_out, times_out = fs_, t
        labels.append(parsed["column_names"][col])
    return np.array(channels), fs_out, times_out, labels


# ─── peaks ────────────────────────────────────────────────────────────────────


@app.post("/api/peaks/detect")
async def peaks_detect(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    spectrum_type: str = Form("fft"),
    window: str = Form("hann"),
    nperseg: int = Form(1024),
    scaling: str = Form("amplitude"),
    prominence: Optional[float] = Form(None),
    distance_hz: Optional[float] = Form(None),
    max_peaks: Optional[int] = Form(None),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        x, fs_, t = get_preprocessed(
            parsed, time_col, signal_col, fs,
            win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs,
        )
        if spectrum_type == "psd":
            freqs, spectrum = dsp.psd(x, fs_, window=window, nperseg=nperseg, scaling="density")
        else:
            freqs, spectrum = dsp.fft_spectrum(x, fs_, window=window, scaling=scaling)

        from dspkit.peaks import find_peaks as _find_peaks, peak_bandwidth as _peak_bw
        # Default: no prominence filter, limit to top 20 by prominence ranking
        if max_peaks is None and prominence is None:
            max_peaks = 20
        peak_freqs, peak_vals, prominences = _find_peaks(
            freqs, spectrum,
            prominence=prominence, distance_hz=distance_hz, max_peaks=max_peaks,
        )
        bw_freqs, bandwidths, q_factors = _peak_bw(freqs, spectrum, peak_freqs)
        return {
            "freqs": to_list(freqs),
            "spectrum": to_list(spectrum),
            "peak_freqs": to_list(peak_freqs),
            "peak_values": to_list(peak_vals),
            "prominences": to_list(prominences),
            "bandwidths": to_list(bandwidths),
            "q_factors": to_list(q_factors),
        }
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/peaks/harmonics")
async def peaks_harmonics(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    window: str = Form("hann"),
    scaling: str = Form("amplitude"),
    fundamental: float = Form(...),
    n_harmonics: int = Form(5),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        x, fs_, t = get_preprocessed(
            parsed, time_col, signal_col, fs,
            win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs,
        )
        freqs, spectrum = dsp.fft_spectrum(x, fs_, window=window, scaling=scaling)
        from dspkit.peaks import find_harmonics as _find_harmonics
        harm_freqs, harm_vals, orders = _find_harmonics(
            freqs, spectrum, fundamental, n_harmonics=n_harmonics,
        )
        return {
            "freqs": to_list(freqs),
            "spectrum": to_list(spectrum),
            "harmonic_freqs": to_list(harm_freqs),
            "harmonic_values": to_list(harm_vals),
            "orders": to_list(orders),
        }
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── SHM indicators ──────────────────────────────────────────────────────────


@app.post("/api/indicators")
async def shm_indicators(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    segment_duration: Optional[float] = Form(None),
    excess: bool = Form(True),
    window: str = Form("hann"),
    nperseg: int = Form(1024),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        x, fs_, t = get_preprocessed(
            parsed, time_col, signal_col, fs,
            win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs,
        )
        from dspkit.indicators import (
            spectral_entropy as _se, kurtosis as _kurt, skewness as _skew,
            rms_variation as _rms_var, energy_variation as _energy_var,
            frequency_shift as _freq_shift,
        )
        freqs_psd, Pxx = dsp.psd(x, fs_, window=window, nperseg=nperseg)
        se = float(_se(freqs_psd, Pxx))
        kurt = float(_kurt(x, excess=excess))
        skew = float(_skew(x))
        seg = segment_duration if segment_duration and segment_duration > 0 else None
        t_rms, rms_vals = _rms_var(x, fs_, segment_duration=seg)
        t_energy, energy_vals = _energy_var(x, fs_, segment_duration=seg)
        t_freq, dom_freqs = _freq_shift(x, fs_, segment_duration=seg)
        return {
            "spectral_entropy": se,
            "kurtosis": kurt,
            "skewness": skew,
            "rms_times": to_list(t_rms),
            "rms_values": to_list(rms_vals),
            "energy_times": to_list(t_energy),
            "energy_values": to_list(energy_vals),
            "freq_times": to_list(t_freq),
            "dominant_freqs": to_list(dom_freqs),
        }
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── multi-sensor ────────────────────────────────────────────────────────────


@app.post("/api/multisensor/correlation")
async def multisensor_correlation(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_cols: str = Form(...),
    fs: Optional[float] = Form(None),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        cols = [int(c) for c in json.loads(signal_cols)]
        if len(cols) < 2:
            raise ValueError("At least 2 channels required")
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        data, fs_, t, labels = get_multichannel(
            parsed, time_col, cols, fs,
            win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs,
        )
        from dspkit.multisensor import correlation_matrix as _corr_mat
        R = _corr_mat(data)
        return {"R": to_list(R), "labels": labels}
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/multisensor/coherence_matrix")
async def multisensor_coherence_mat(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_cols: str = Form(...),
    fs: Optional[float] = Form(None),
    window: str = Form("hann"),
    nperseg: int = Form(1024),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        cols = [int(c) for c in json.loads(signal_cols)]
        if len(cols) < 2:
            raise ValueError("At least 2 channels required")
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        data, fs_, t, labels = get_multichannel(
            parsed, time_col, cols, fs,
            win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs,
        )
        from dspkit.multisensor import coherence_matrix as _coh_mat
        freqs, C = _coh_mat(data, fs_, window=window, nperseg=nperseg)
        n_ch = len(cols)
        pairs = []
        for i in range(n_ch):
            for j in range(i + 1, n_ch):
                pairs.append({
                    "label": f"{labels[i]} \u2013 {labels[j]}",
                    "Cxy": to_list(C[i, j, :]),
                })
        return {"freqs": to_list(freqs), "pairs": pairs, "labels": labels}
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── FDD ──────────────────────────────────────────────────────────────────────


@app.post("/api/fdd/analyze")
async def fdd_analyze(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_cols: str = Form(...),
    fs: Optional[float] = Form(None),
    window: str = Form("hann"),
    nperseg: int = Form(1024),
    prominence: Optional[float] = Form(None),
    distance_hz: Optional[float] = Form(None),
    max_peaks: Optional[int] = Form(None),
    freq_min: Optional[float] = Form(None),
    freq_max: Optional[float] = Form(None),
    mac_threshold: float = Form(0.8),
    n_crossings: int = Form(10),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        cols = [int(c) for c in json.loads(signal_cols)]
        if len(cols) < 2:
            raise ValueError("At least 2 channels required")
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        data, fs_, t, labels = get_multichannel(
            parsed, time_col, cols, fs,
            win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs,
        )
        from dspkit.fdd import fdd_svd, fdd_peak_picking, fdd_mode_shapes, efdd_damping

        freqs, S, U = fdd_svd(data, fs_, window=window, nperseg=nperseg)
        freq_range = None
        if freq_min is not None and freq_max is not None:
            freq_range = (freq_min, freq_max)
        # Default: no prominence filter, limit to top 10 by prominence ranking
        _max = max_peaks if max_peaks is not None or prominence is not None else 10
        peak_freqs, peak_indices = fdd_peak_picking(
            freqs, S, prominence=prominence,
            distance_hz=distance_hz, max_peaks=_max, freq_range=freq_range,
        )
        modes = fdd_mode_shapes(U, peak_indices)
        damping_ratios = []
        natural_freqs = []
        if len(peak_indices) > 0:
            try:
                dr, nf = efdd_damping(
                    freqs, S, U, peak_indices, fs_,
                    mac_threshold=mac_threshold, n_crossings=n_crossings,
                )
                damping_ratios = to_list(dr)
                natural_freqs = to_list(nf)
            except Exception:
                damping_ratios = [None] * len(peak_indices)
                natural_freqs = to_list(peak_freqs)

        return {
            "freqs": to_list(freqs),
            "S": to_list(S),
            "peak_freqs": to_list(peak_freqs),
            "modes": to_list(modes),
            "damping_ratios": damping_ratios,
            "natural_freqs": natural_freqs,
            "labels": labels,
        }
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── statistics ───────────────────────────────────────────────────────────────


@app.post("/api/statistics/pdf")
async def statistics_pdf(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    bins: int = Form(50),
    bandwidth: Optional[float] = Form(None),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        x, fs_, t = get_preprocessed(
            parsed, time_col, signal_col, fs,
            win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs,
        )
        from dspkit.statistics import pdf_estimate as _pdf, histogram as _hist
        xi, density = _pdf(x, bandwidth=bandwidth)
        bin_centres, counts = _hist(x, bins=bins, density=True)
        return {
            "xi": to_list(xi),
            "density": to_list(density),
            "bin_centres": to_list(bin_centres),
            "hist_density": to_list(counts),
        }
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/statistics/joint")
async def statistics_joint(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col_x: int = Form(...),
    signal_col_y: int = Form(...),
    fs: Optional[float] = Form(None),
    bins: int = Form(50),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        x, fs_, _ = get_preprocessed(
            parsed, time_col, signal_col_x, fs,
            win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs,
        )
        y, _, _ = get_preprocessed(
            parsed, time_col, signal_col_y, fs,
            win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs,
        )
        from dspkit.statistics import joint_histogram as _joint
        x_centres, y_centres, H = _joint(x, y, bins=bins, density=True)
        return {
            "x_centres": to_list(x_centres),
            "y_centres": to_list(y_centres),
            "H": to_list(H),
            "xlabel": parsed["column_names"][signal_col_x],
            "ylabel": parsed["column_names"][signal_col_y],
        }
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/statistics/covariance")
async def statistics_covariance(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_cols: str = Form(...),
    fs: Optional[float] = Form(None),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        cols = [int(c) for c in json.loads(signal_cols)]
        if len(cols) < 2:
            raise ValueError("At least 2 channels required")
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        data, fs_, t, labels = get_multichannel(
            parsed, time_col, cols, fs,
            win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs,
        )
        from dspkit.statistics import covariance_matrix as _cov
        C = _cov(data)
        return {"C": to_list(C), "labels": labels}
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/statistics/mahalanobis")
async def statistics_mahalanobis(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_cols: str = Form(...),
    fs: Optional[float] = Form(None),
    percentile: float = Form(99),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        cols = [int(c) for c in json.loads(signal_cols)]
        if len(cols) < 2:
            raise ValueError("At least 2 channels required")
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        data, fs_, t, labels = get_multichannel(
            parsed, time_col, cols, fs,
            win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs,
        )
        from dspkit.statistics import mahalanobis as _maha
        distances = _maha(data)
        threshold = float(np.percentile(distances, percentile))
        return {
            "times": to_list(t),
            "distances": to_list(distances),
            "threshold": threshold,
            "percentile": percentile,
        }
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

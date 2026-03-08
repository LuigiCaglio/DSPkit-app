"""
DSPkit-app — FastAPI backend
"""

from __future__ import annotations

import csv
import io
from math import gcd
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import FastAPI, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from scipy.signal import resample as fft_resample, resample_poly

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


# ─── file parsing ─────────────────────────────────────────────────────────────


def to_list(arr) -> list:
    return np.asarray(arr).tolist()


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
        column_names = [f"col_{i}" for i in range(n_signals)]
    elif len(column_names) < n_signals:
        column_names += [f"col_{i}" for i in range(len(column_names), n_signals)]
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

    # 4. Resample
    if target_fs is not None and abs(target_fs - fs) > 0.01:
        fs_i  = round(fs * 100)
        tfs_i = round(target_fs * 100)
        g     = gcd(fs_i, tfs_i)
        up, down = tfs_i // g, fs_i // g
        if max(up, down) <= 2000:
            x = resample_poly(x, up, down)
        else:
            n_new = round(len(x) * target_fs / fs)
            x = fft_resample(x, n_new)
        times = np.linspace(times[0], times[-1], len(x))
        fs = float(target_fs)

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
):
    try:
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        preview_len = min(5, parsed["n_samples"])
        preview = parsed["data"][:, :preview_len].T.tolist()
        return {
            "column_names": parsed["column_names"],
            "n_columns": parsed["n_columns"],
            "n_samples": parsed["n_samples"],
            "preview": preview,
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


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
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ─── /api/signal/timeseries ──────────────────────────────────────────────────


@app.post("/api/signal/timeseries")
async def signal_timeseries(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    signal_col_y: Optional[int] = Form(None),
    fs: Optional[float] = Form(None),
    win_start:  Optional[float] = Query(None),
    win_end:    Optional[float] = Query(None),
    win_unit:   str             = Query("samples"),
    hp_cutoff:  Optional[float] = Query(None),
    lp_cutoff:  Optional[float] = Query(None),
    target_fs:  Optional[float] = Query(None),
):
    try:
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)

        x_raw, t_raw, fs_raw = get_signal_times_fs(parsed, time_col, signal_col, fs)
        if t_raw is None:
            t_raw = np.arange(len(x_raw)) / fs_raw

        x_proc, fs_proc, t_proc = apply_preprocessing(
            x_raw.copy(), fs_raw, t_raw.copy(),
            win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs,
        )

        out = {
            "times_raw":    to_list(t_raw),
            "signal_raw_x": to_list(x_raw),
            "fs_raw":       fs_raw,
            "times_proc":   to_list(t_proc),
            "signal_proc_x": to_list(x_proc),
            "fs_proc":      fs_proc,
            "n_proc":       len(x_proc),
            "col_name_x":   parsed["column_names"][signal_col],
        }

        if signal_col_y is not None:
            y_raw, _, _ = get_signal_times_fs(parsed, time_col, signal_col_y, fs)
            y_proc, _, _ = apply_preprocessing(
                y_raw.copy(), fs_raw, t_raw.copy(),
                win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs,
            )
            out["signal_raw_y"]  = to_list(y_raw)
            out["signal_proc_y"] = to_list(y_proc)
            out["col_name_y"]    = parsed["column_names"][signal_col_y]

        return out
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ─── spectral ────────────────────────────────────────────────────────────────


@app.post("/api/spectral/fft")
async def spectral_fft(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    signal_col_y: Optional[int] = Form(None),
    fs: Optional[float] = Form(None),
    window: str = Form("hann"),
    scaling: str = Form("amplitude"),
    win_start: Optional[float] = Query(None), win_end: Optional[float] = Query(None),
    win_unit: str = Query("samples"), hp_cutoff: Optional[float] = Query(None),
    lp_cutoff: Optional[float] = Query(None), target_fs: Optional[float] = Query(None),
):
    try:
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
        freqs, amp_x = dsp.fft_spectrum(x, fs_, window=window, scaling=scaling)
        out = {"freqs": to_list(freqs), "amplitude_x": to_list(amp_x),
               "col_name_x": parsed["column_names"][signal_col]}
        if signal_col_y is not None:
            y, _, _ = get_preprocessed(parsed, time_col, signal_col_y, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
            _, amp_y = dsp.fft_spectrum(y, fs_, window=window, scaling=scaling)
            out["amplitude_y"] = to_list(amp_y)
            out["col_name_y"]  = parsed["column_names"][signal_col_y]
        return out
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/api/spectral/psd")
async def spectral_psd(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    signal_col_y: Optional[int] = Form(None),
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
        content = await file.read()
        parsed = parse_file(content, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
        freqs, Pxx_x = dsp.psd(x, fs_, window=window, nperseg=nperseg, noverlap=noverlap, scaling=scaling)
        out = {"freqs": to_list(freqs), "Pxx_x": to_list(Pxx_x),
               "col_name_x": parsed["column_names"][signal_col]}
        if signal_col_y is not None:
            y, _, _ = get_preprocessed(parsed, time_col, signal_col_y, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
            _, Pxx_y = dsp.psd(y, fs_, window=window, nperseg=nperseg, noverlap=noverlap, scaling=scaling)
            out["Pxx_y"]      = to_list(Pxx_y)
            out["col_name_y"] = parsed["column_names"][signal_col_y]
        return out
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/api/spectral/autocorrelation")
async def spectral_autocorrelation(
    file: UploadFile,
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    signal_col_y: Optional[int] = Form(None),
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
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
        lags, acf_x = dsp.autocorrelation(x, fs=fs_, normalize=normalize, max_lag=max_lag)
        out = {"lags": to_list(lags), "acf_x": to_list(acf_x),
               "col_name_x": parsed["column_names"][signal_col]}
        if signal_col_y is not None:
            y, _, _ = get_preprocessed(parsed, time_col, signal_col_y, fs, win_start, win_end, win_unit, hp_cutoff, lp_cutoff, target_fs)
            _, acf_y = dsp.autocorrelation(y, fs=fs_, normalize=normalize, max_lag=max_lag)
            out["acf_y"]      = to_list(acf_y)
            out["col_name_y"] = parsed["column_names"][signal_col_y]
        return out
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


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
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


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
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


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
        return {"freqs": to_list(freqs), "Cxy": to_list(Cxy)}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


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
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


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
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


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
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


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
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


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
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


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
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


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
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


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
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

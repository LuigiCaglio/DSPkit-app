"""
DSPkit-app — FastAPI backend
"""

from __future__ import annotations

import csv
import io
import json
import os
import time
import uuid
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from scipy.signal import get_window

import dspkit as dsp

app = FastAPI(title="DSPkit GUI API")

_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
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


# ─── launch target ────────────────────────────────────────────────────────────
#
# A file named on the command line (`run.py data.csv`, or dropping a CSV on the
# launcher). The UI asks for it once on mount and opens it, which is what makes
# double-clicking the *data* rather than the app work.


@app.get("/api/launch-target")
async def launch_target():
    # Consumed on first read: a later reload should restore whatever the user
    # last had open, not jump back to the file the app happened to start on.
    path = os.environ.pop("DSPKIT_OPEN_FILE", "") or ""
    if path and Path(path).is_file():
        return {"path": str(Path(path).expanduser().resolve())}
    return {"path": None}


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


# ─── auto-detection ───────────────────────────────────────────────────────────


def _as_floats(row: list[str]) -> Optional[list[float]]:
    """Parse a row as floats, or None if any non-empty field isn't numeric."""
    vals = []
    for tok in row:
        tok = tok.strip()
        if not tok:
            continue
        try:
            vals.append(float(tok))
        except ValueError:
            return None
    return vals or None


_UNIFORM_CV_MAX = 1e-3


def _interval_stats(d: np.ndarray) -> dict:
    """
    Describe a column's sample intervals well enough to judge a near-miss.

    The question a rejected time column raises is always the same: is this a
    genuine gap in the record, or float noise in a written-out time vector that
    happens to sit just over the threshold? The median-vs-extremes spread and
    the count of intervals that stray from the median answer it directly; the
    coefficient of variation alone does not, because one dropout and pervasive
    jitter can produce the same number.
    """
    med = float(np.median(d))
    mean = float(d.mean())
    cv = float(d.std()) / mean if mean > 0 else float("inf")
    irregular = int(np.count_nonzero(np.abs(d - med) > 0.01 * abs(med))) if med else 0
    return {
        "median_dt": med,
        "min_dt": float(d.min()),
        "max_dt": float(d.max()),
        "cv": cv if np.isfinite(cv) else None,
        "n_irregular": irregular,
        "n_intervals": int(d.size),
        "implied_fs": (1.0 / med) if med > 0 else None,
    }


def _detect_time_col(
    data: np.ndarray, max_check: int = 5000,
) -> "tuple[int, Optional[float], Optional[dict]]":
    """
    Find a column that looks like a time vector: strictly increasing with
    near-uniform spacing. Returns (col_index, fs, rejection).

    Uniformity is judged by the coefficient of variation of the sample
    intervals, which tolerates float round-off in a written-out time column
    but rejects a merely monotonic data channel (e.g. a drifting sensor).

    `rejection` describes the closest column that *nearly* qualified, or None if
    nothing came close. Returning only (-1, None) — as this used to — meant a
    record with one dropped sample was indistinguishable from a record with no
    time column at all, and both landed silently on the manual default of
    1000 Hz. Every frequency axis in the app is then wrong by whatever ratio
    that happens to be, with nothing on screen saying so.
    """
    n_sig, n_samp = data.shape
    if n_samp < 3:
        return -1, None, None

    best: Optional[dict] = None

    def consider(candidate: dict) -> None:
        # Rank near-misses by how time-like they are: a strictly increasing
        # column that merely jitters is a far better candidate than one that
        # jumps backwards, which is usually just a data channel.
        nonlocal best
        rank = (candidate["positive_fraction"], -candidate.get("cv_rank", 0.0))
        if best is None or rank > best["_rank"]:
            best = {**candidate, "_rank": rank}

    for col in range(n_sig):
        t = data[col, :min(n_samp, max_check)]
        if not np.all(np.isfinite(t)):
            continue
        d = np.diff(t)
        if d.size < 2:
            continue

        positive = float(np.count_nonzero(d > 0)) / d.size
        if np.any(d <= 0):
            # Only worth reporting when it is otherwise convincingly a time
            # vector — a handful of backwards steps in an otherwise rising
            # column is a clock reset or a badly merged file, not a signal.
            if positive >= 0.99:
                forward = d[d > 0]
                consider({
                    "col": col,
                    "reason": "not_monotonic",
                    "positive_fraction": positive,
                    "n_backwards": int(np.count_nonzero(d <= 0)),
                    **(_interval_stats(forward) if forward.size else {}),
                })
            continue

        mean_d = float(d.mean())
        if mean_d <= 0 or not np.isfinite(mean_d):
            continue

        stats = _interval_stats(d)
        cv = stats["cv"]
        if cv is None or cv > _UNIFORM_CV_MAX:
            consider({
                "col": col,
                "reason": "non_uniform",
                "positive_fraction": positive,
                "cv_rank": cv or 0.0,
                "threshold_cv": _UNIFORM_CV_MAX,
                **stats,
            })
            continue

        fs = 1.0 / mean_d
        if np.isfinite(fs) and fs > 0:
            return col, float(fs), None

    if best is not None:
        best.pop("_rank", None)
        best.pop("cv_rank", None)
    return -1, None, best


def autodetect(content: bytes) -> dict:
    """
    Work out how to read a file so the user doesn't have to.

    Returns {orientation, header_row, time_col, fs, delimiter}. Every value is
    a starting point the user can override in the UI — nothing here is binding.
    """
    text = content.decode("utf-8-sig", errors="replace")
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        raise ValueError("File is empty")

    delimiter = detect_delimiter("\n".join(lines[:20]))
    rows = list(csv.reader(io.StringIO("\n".join(lines[:200])), delimiter=delimiter))

    # First row that is entirely numeric marks where the data starts; anything
    # above it is a header and/or a metadata preamble.
    first_numeric = -1
    for i, row in enumerate(rows):
        if row and not row[0].strip().startswith("#") and _as_floats(row) is not None:
            first_numeric = i
            break
    if first_numeric == -1:
        raise ValueError("No numeric data found in file")

    # The line directly above the data is a header only if it is non-numeric
    # and has one field per data column.
    header_row = -1
    if first_numeric > 0:
        cand = rows[first_numeric - 1]
        n_data_fields = len([t for t in rows[first_numeric] if t.strip()])
        if _as_floats(cand) is None and len([t for t in cand if t.strip()]) == n_data_fields:
            header_row = first_numeric - 1

    # Signals are the short axis: real records have far more samples than channels.
    n_data_rows = sum(1 for r in rows[first_numeric:] if _as_floats(r) is not None)
    n_data_cols = len([t for t in rows[first_numeric] if t.strip()])
    # Only trust this when we've seen enough rows to tell the axes apart;
    # `rows` is capped at 200 lines, so a long file always reads as "columns".
    orientation = "rows" if n_data_cols > max(n_data_rows, 8) else "columns"

    detected = {
        "orientation": orientation,
        "header_row": header_row,
        "delimiter": delimiter,
        "time_col": -1,
        "fs": None,
        # Why a time column was rejected, when one nearly qualified. Carried all
        # the way to the UI: falling back to a typed-in sample rate is fine, but
        # it must never be silent.
        "time_col_rejected": None,
    }

    # Time column + sample rate, from an actual parse of the file.
    try:
        parsed = parse_file(content, orientation, header_row)
        time_col, fs, rejected = _detect_time_col(parsed["data"])
        detected["time_col"] = time_col
        detected["fs"] = round(fs, 6) if fs else None
        detected["time_col_rejected"] = rejected
    except ValueError:
        pass  # detection is best-effort; the user can still set these by hand

    return detected


# ─── session store ────────────────────────────────────────────────────────────
#
# A file is uploaded and parsed once, then every analysis call refers to it by
# id. Before this, each plot re-uploaded and re-parsed the whole file.
#
# Sessions are also written to disk, because the alternative — a dict that dies
# with the process — meant every restart began by re-dropping the same file and
# re-typing the same settings. On disk a session is two files: `<sid>.json` with
# the metadata and the saved UI state, and `<sid>.bin` with the raw bytes. The
# bytes are only copied for uploads; a session opened from a path re-reads the
# original, so the store doesn't duplicate data that already exists.

_STATE_DIR = Path(os.environ.get("DSPKIT_STATE_DIR") or (Path.home() / ".dspkit-app"))
_SESSION_DIR = _STATE_DIR / "sessions"

_SESSIONS: "dict[str, dict]" = {}
_MAX_SESSIONS = 4    # parsed arrays held in RAM — these are the expensive ones
_MAX_RECENT = 12     # session records kept on disk


def _meta_path(sid: str) -> Path:
    return _SESSION_DIR / f"{sid}.json"


def _data_path(sid: str) -> Path:
    return _SESSION_DIR / f"{sid}.bin"


def _read_meta(sid: str) -> Optional[dict]:
    try:
        with open(_meta_path(sid), "r", encoding="utf-8") as fh:
            meta = json.load(fh)
        return meta if isinstance(meta, dict) else None
    except (OSError, ValueError):
        return None


def _write_meta(meta: dict) -> None:
    """Write a session record. Never fatal — a read-only home just loses recents."""
    try:
        _SESSION_DIR.mkdir(parents=True, exist_ok=True)
        path = _meta_path(meta["session_id"])
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(meta, fh)
        os.replace(tmp, path)
    except OSError:
        pass


def _all_meta() -> "list[dict]":
    """Every session on disk, most recently opened first."""
    if not _SESSION_DIR.exists():
        return []
    metas = []
    for path in _SESSION_DIR.glob("*.json"):
        meta = _read_meta(path.stem)
        if meta and meta.get("session_id"):
            metas.append(meta)
    metas.sort(key=lambda m: m.get("opened_at", 0), reverse=True)
    return metas


def _forget_session(sid: str) -> None:
    _SESSIONS.pop(sid, None)
    for path in (_meta_path(sid), _data_path(sid)):
        try:
            path.unlink()
        except OSError:
            pass


def _prune_recent() -> None:
    for meta in _all_meta()[_MAX_RECENT:]:
        _forget_session(meta["session_id"])


def _evict_ram() -> None:
    """Drop the oldest parsed arrays; the disk records they came from survive."""
    while len(_SESSIONS) > _MAX_SESSIONS:
        _SESSIONS.pop(next(iter(_SESSIONS)))


def _source_mtime(source_path: Optional[str]) -> Optional[float]:
    if not source_path:
        return None
    try:
        return os.path.getmtime(source_path)
    except OSError:
        return None


def _load_raw(meta: dict) -> bytes:
    """
    The file's bytes, preferring the original on disk.

    Reading the source back means a session opened from a path picks up edits to
    that file, and that the store holds one copy of the data rather than two.
    """
    source_path = meta.get("source_path")
    if source_path:
        try:
            with open(source_path, "rb") as fh:
                return fh.read()
        except OSError:
            pass  # moved or deleted — fall through to the cached copy, if any
    try:
        with open(_data_path(meta["session_id"]), "rb") as fh:
            return fh.read()
    except OSError as e:
        raise HTTPException(
            status_code=410,
            detail=(
                f"'{meta.get('filename', 'The file')}' could not be re-read"
                + (f" from {source_path}" if source_path else "")
                + " — it may have been moved or deleted. Load it again."
            ),
        ) from e


def _new_session(
    raw: bytes,
    filename: str,
    orientation: str,
    header_row: int,
    source_path: Optional[str] = None,
) -> str:
    parsed = parse_file(raw, orientation, header_row)
    sid = uuid.uuid4().hex
    _SESSIONS[sid] = {
        "raw": raw,
        "filename": filename,
        "orientation": orientation,
        "header_row": header_row,
        "parsed": parsed,
    }
    _evict_ram()

    # Only uploads need their bytes copied; a path-backed session re-reads them.
    if not source_path:
        try:
            _SESSION_DIR.mkdir(parents=True, exist_ok=True)
            with open(_data_path(sid), "wb") as fh:
                fh.write(raw)
        except OSError:
            pass
    _write_meta({
        "session_id": sid,
        "filename": filename,
        "source_path": source_path,
        "source_mtime": _source_mtime(source_path),
        "orientation": orientation,
        "header_row": header_row,
        "opened_at": time.time(),
        "n_columns": parsed["n_columns"],
        "n_samples": parsed["n_samples"],
        "ui": None,
    })
    _prune_recent()
    return sid


def get_session(session_id: str) -> dict:
    """
    A session's parsed data, re-reading from disk if it isn't in RAM.

    The rehydration path is what makes a restart invisible: the id the frontend
    remembered still resolves, so no reload is needed.
    """
    sess = _SESSIONS.get(session_id)
    if sess is not None:
        return sess

    meta = _read_meta(session_id)
    if meta is None:
        raise HTTPException(
            status_code=404,
            detail="Session expired or not found — reload the file.",
        )
    raw = _load_raw(meta)
    try:
        parsed = parse_file(raw, meta["orientation"], meta["header_row"])
    except (ValueError, TypeError, KeyError, IndexError) as e:
        raise HTTPException(
            status_code=422,
            detail=f"'{meta.get('filename', 'file')}' could not be re-read: {e}",
        ) from e
    sess = {
        "raw": raw,
        "filename": meta.get("filename", "data.csv"),
        "orientation": meta["orientation"],
        "header_row": meta["header_row"],
        "parsed": parsed,
    }
    _SESSIONS[session_id] = sess
    _evict_ram()
    return sess


def _touch_session(sid: str, **fields) -> None:
    """Update a session's record in place, keeping it at the top of recents."""
    meta = _read_meta(sid)
    if meta is None:
        return
    meta.update(fields)
    meta["opened_at"] = time.time()
    _write_meta(meta)


async def resolve_parsed(
    file: Optional[UploadFile],
    session_id: Optional[str],
    orientation: str,
    header_row: int,
) -> dict:
    """
    Get parsed data for a request: from the session cache when a session_id is
    given, otherwise by parsing an uploaded file (kept for direct API use).
    """
    if session_id:
        sess = get_session(session_id)
        # Re-parse only if the caller asked for a different layout.
        if orientation != sess["orientation"] or header_row != sess["header_row"]:
            sess["parsed"] = parse_file(sess["raw"], orientation, header_row)
            sess["orientation"] = orientation
            sess["header_row"] = header_row
        return sess["parsed"]
    if file is None:
        raise HTTPException(status_code=422, detail="Provide either session_id or a file upload.")
    return parse_file(await file.read(), orientation, header_row)


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


class PreprocParams:
    """
    Preprocessing applied before every analysis, taken from query parameters.

    Bundled into one dependency because 27 endpoints need the identical set —
    listing them separately meant every new option had to be added in 27 places
    and passed positionally through two helpers.
    """

    def __init__(
        self,
        win_start: Optional[float] = Query(None),
        win_end: Optional[float] = Query(None),
        win_unit: str = Query("samples"),           # "samples" | "time"
        detrend_order: Optional[int] = Query(None), # 0 = mean, 1 = linear, n = poly
        hp_cutoff: Optional[float] = Query(None),
        hp_order: int = Query(4),
        lp_cutoff: Optional[float] = Query(None),
        lp_order: int = Query(4),
        notch_freq: Optional[float] = Query(None),
        notch_q: float = Query(30.0),
        zero_phase: bool = Query(True),
        target_fs: Optional[float] = Query(None),
    ):
        self.win_start = win_start
        self.win_end = win_end
        self.win_unit = win_unit
        self.detrend_order = detrend_order
        self.hp_cutoff = hp_cutoff
        self.hp_order = hp_order
        self.lp_cutoff = lp_cutoff
        self.lp_order = lp_order
        self.notch_freq = notch_freq
        self.notch_q = notch_q
        self.zero_phase = zero_phase
        self.target_fs = target_fs


def apply_preprocessing(
    x: np.ndarray,
    fs: float,
    times: Optional[np.ndarray],
    pp: PreprocParams,
) -> tuple[np.ndarray, float, np.ndarray]:
    """
    Apply preprocessing steps in order:
      1. Window (select time range)
      2. Detrend
      3. Notch
      4. High-pass filter
      5. Low-pass filter
      6. Resample (up or down)

    Detrending comes before the filters on purpose: a large DC offset or drift
    makes a high-pass ring badly at the edges of the record.

    Returns (x_processed, fs_processed, times_processed).
    """
    N = len(x)
    if times is None:
        times = np.arange(N) / fs

    # 1. Windowing
    if pp.win_start is not None or pp.win_end is not None:
        if pp.win_unit == "time":
            i0 = int((pp.win_start or 0.0) * fs) if pp.win_start is not None else 0
            i1 = int(pp.win_end * fs) if pp.win_end is not None else N
        else:  # samples
            i0 = int(pp.win_start) if pp.win_start is not None else 0
            i1 = int(pp.win_end) if pp.win_end is not None else N
        i0 = max(0, min(i0, N - 1))
        i1 = max(i0 + 1, min(i1, N))
        x = x[i0:i1]
        times = times[i0:i1]

    # 2. Detrend
    if pp.detrend_order is not None and pp.detrend_order >= 0:
        x = dsp.detrend(x, order=pp.detrend_order)

    # 3. Notch (mains hum and other fixed tones)
    if pp.notch_freq is not None and pp.notch_freq > 0:
        x = dsp.notch(x, fs, pp.notch_freq, q=pp.notch_q, zero_phase=pp.zero_phase)

    # 4. High-pass filter
    if pp.hp_cutoff is not None and pp.hp_cutoff > 0:
        x = dsp.highpass(x, fs, pp.hp_cutoff, order=pp.hp_order, zero_phase=pp.zero_phase)

    # 5. Low-pass filter
    if pp.lp_cutoff is not None and pp.lp_cutoff > 0:
        x = dsp.lowpass(x, fs, pp.lp_cutoff, order=pp.lp_order, zero_phase=pp.zero_phase)

    # 6. Resample — use linear interpolation to avoid group-delay time shift
    if pp.target_fs is not None and abs(pp.target_fs - fs) > 0.01:
        n_new = round(len(x) * pp.target_fs / fs)
        t_new = np.linspace(times[0], times[-1], n_new)
        x     = np.interp(t_new, times, x)
        times = t_new
        fs    = float(pp.target_fs)

    return x, fs, times


def get_preprocessed(
    parsed: dict,
    time_col: int,
    signal_col: int,
    fs_manual: Optional[float],
    pp: PreprocParams,
) -> tuple[np.ndarray, float, np.ndarray]:
    """Column extraction + preprocessing in one call. Returns (x, fs, times)."""
    x, times, fs = get_signal_times_fs(parsed, time_col, signal_col, fs_manual)
    return apply_preprocessing(x, fs, times, pp)


# ─── /api/session ────────────────────────────────────────────────────────────


def _session_summary(sid: str, parsed: dict, time_col: int, fs: Optional[float]) -> dict:
    preview_len = min(50, parsed["n_samples"])
    result = {
        "session_id": sid,
        "column_names": parsed["column_names"],
        "n_columns": parsed["n_columns"],
        "n_samples": parsed["n_samples"],
        "preview": parsed["data"][:, :preview_len].T.tolist(),
    }
    if fs and fs > 0:
        result["fs"] = round(fs, 6)
        result["duration"] = round(parsed["n_samples"] / fs, 4)
    result["time_col"] = time_col
    return result


def _session_response(
    sid: str,
    filename: str,
    detected: Optional[dict],
    orientation: str,
    header_row: int,
    time_col: int,
    fs: Optional[float],
) -> dict:
    """The payload the UI needs to show a loaded file, shared by every entry point."""
    parsed = get_session(sid)["parsed"]

    # fs: the time column wins, then an explicit value, then detection.
    use_fs: Optional[float] = None
    if 0 <= time_col < parsed["n_columns"]:
        t = extract_col(parsed, time_col)
        use_fs = 1.0 / float(np.mean(np.diff(t)))
    elif fs is not None and fs > 0:
        use_fs = float(fs)
    elif detected and detected.get("fs"):
        use_fs = detected["fs"]

    result = _session_summary(sid, parsed, time_col, use_fs)
    result["filename"] = filename
    result["detected"] = detected
    result["orientation"] = orientation
    result["header_row"] = header_row
    return result


@app.post("/api/session/create")
async def session_create(
    file: UploadFile,
    orientation: Optional[str] = Form(None),
    header_row: Optional[int] = Form(None),
    time_col: Optional[int] = Form(None),
    fs: Optional[float] = Form(None),
    source_path: Optional[str] = Form(None),
):
    """
    Upload a file once and start a session.

    With no overrides, layout is auto-detected and echoed back under
    "detected" so the UI can show what it decided. Any field the caller does
    supply wins over detection.
    """
    try:
        raw = await file.read()
        detected = autodetect(raw)

        use_orientation = orientation or detected["orientation"]
        use_header_row  = header_row if header_row is not None else detected["header_row"]
        use_time_col    = time_col   if time_col   is not None else detected["time_col"]

        sid = _new_session(
            raw, file.filename or "data.csv", use_orientation, use_header_row,
            source_path=source_path or None,
        )
        _touch_session(sid, detected=detected)
        return _session_response(
            sid, file.filename or "data.csv", detected,
            use_orientation, use_header_row, use_time_col, fs,
        )
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}


def _require_local_origin(request: Request) -> None:
    """
    Refuse cross-site calls to the endpoints that touch the filesystem.

    The server listens on loopback, but any page in the browser can still POST
    to it. Reading an arbitrary path is the one operation where that matters.

    Two checks, and both are needed:

    * the request must have been addressed to a loopback name. Without this, an
      attacker can point their own domain at 127.0.0.1 (DNS rebinding), at which
      point their Origin and the Host agree and an origin comparison alone
      passes.
    * the Origin, when the browser sends one, must be this server's own.

    Compared against the request's actual host rather than a fixed list, because
    the port is not fixed — the tests run on a random one.
    """
    host = (request.headers.get("host") or "").strip()
    hostname = host.rsplit(":", 1)[0] if not host.startswith("[") else host.split("]")[0] + "]"
    if hostname not in _LOOPBACK_HOSTS:
        raise HTTPException(
            status_code=403,
            detail="Local file access is only available over loopback.",
        )

    origin = request.headers.get("origin")
    if not origin:
        return  # not a browser fetch (curl, the launcher) — no origin to check
    if origin.split("//", 1)[-1] == host or origin in _ALLOWED_ORIGINS:
        return
    raise HTTPException(status_code=403, detail="Cross-site request refused.")


def _find_by_path(source_path: str) -> Optional[str]:
    """The most recent session for this file, if it has been opened before."""
    target = os.path.normcase(os.path.abspath(source_path))
    for meta in _all_meta():
        existing = meta.get("source_path")
        if existing and os.path.normcase(os.path.abspath(existing)) == target:
            return meta["session_id"]
    return None


def _reopen(session_id: str, force_reread: bool = False) -> dict:
    """
    Rebuild the response for an existing session, with the state it was left in.

    `force_reread` drops the cached parse so a file edited since it was opened
    comes back with its new contents rather than the copy still in memory.
    """
    meta = _read_meta(session_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="No such session.")
    if force_reread:
        _SESSIONS.pop(session_id, None)

    ui = meta.get("ui") or {}
    # Absent is not the same as -1. A blob that never got written — the session
    # was closed inside the 700 ms save debounce — used to reopen with *no* time
    # column, so the time axis came back as a selectable signal and the rate
    # went manual. Fall back to what detection found, exactly as create does.
    # An explicit -1 is a real choice ("this file has no time column") and is
    # still honoured, which is why this tests for None rather than falsiness.
    saved_time_col = ui.get("timeCol")
    detected_meta = meta.get("detected") or {}
    use_time_col = (
        saved_time_col if saved_time_col is not None
        else detected_meta.get("time_col", -1)
    )
    try:
        get_session(session_id)  # rehydrates, raising with a clear reason if it can't
        result = _session_response(
            session_id,
            meta.get("filename", "data.csv"),
            meta.get("detected"),
            meta["orientation"],
            meta["header_row"],
            use_time_col,
            ui.get("fsManual"),
        )
    except HTTPException:
        raise
    except (ValueError, TypeError, KeyError, IndexError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")

    result["source_path"] = meta.get("source_path")
    result["ui"] = meta.get("ui")
    result["reopened"] = True
    _touch_session(
        session_id,
        source_mtime=_source_mtime(meta.get("source_path")),
        n_columns=result["n_columns"],
        n_samples=result["n_samples"],
    )
    return result


@app.post("/api/session/open")
async def session_open(
    request: Request,
    path: str = Form(...),
    orientation: Optional[str] = Form(None),
    header_row: Optional[int] = Form(None),
    time_col: Optional[int] = Form(None),
    fs: Optional[float] = Form(None),
):
    """
    Start a session from a file already on this machine.

    The upload round-trip is pointless when the data sits next to the app: this
    is what makes a recent-files list and "open DSPkit on this file" possible.

    Opening a path that has been opened before returns *that* session rather
    than a fresh one, so the channels and preprocessing chosen for that record
    come back with it.
    """
    _require_local_origin(request)
    src = Path(path).expanduser()
    if not src.is_file():
        raise HTTPException(status_code=404, detail=f"No file at {src}")

    known = _find_by_path(str(src))
    if known and orientation is None and header_row is None:
        return _reopen(known, force_reread=True)

    try:
        raw = src.read_bytes()
    except OSError as e:
        raise HTTPException(status_code=422, detail=f"Could not read {src}: {e}") from e

    try:
        detected = autodetect(raw)
        use_orientation = orientation or detected["orientation"]
        use_header_row  = header_row if header_row is not None else detected["header_row"]
        use_time_col    = time_col   if time_col   is not None else detected["time_col"]

        sid = _new_session(
            raw, src.name, use_orientation, use_header_row, source_path=str(src),
        )
        _touch_session(sid, detected=detected)
        result = _session_response(
            sid, src.name, detected, use_orientation, use_header_row, use_time_col, fs,
        )
        result["source_path"] = str(src)
        return result
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.get("/api/session/recent")
async def session_recent():
    """
    Files opened before, newest first.

    `available` is false when a path-backed file has moved and no copy was kept,
    so the UI can show it greyed rather than failing on click. `changed` means
    the file on disk has been written since it was opened — worth re-reading.
    """
    items = []
    for meta in _all_meta():
        sid = meta["session_id"]
        source_path = meta.get("source_path")
        on_disk = _source_mtime(source_path)
        items.append({
            "session_id": sid,
            "filename": meta.get("filename"),
            "source_path": source_path,
            "opened_at": meta.get("opened_at"),
            "n_columns": meta.get("n_columns"),
            "n_samples": meta.get("n_samples"),
            "available": bool(on_disk is not None or _data_path(sid).exists()),
            "changed": bool(
                on_disk is not None
                and meta.get("source_mtime") is not None
                and on_disk > meta["source_mtime"]
            ),
        })
    return {"recent": items}


@app.get("/api/session/{session_id}")
async def session_get(session_id: str):
    """
    Reopen a session by id, with the UI state it was left in.

    This is the restore path: the frontend remembers only the id, and everything
    else — layout, channels, preprocessing, analysis parameters — comes back
    from here.
    """
    return _reopen(session_id)


@app.put("/api/session/{session_id}/state")
async def session_save_state(session_id: str, request: Request):
    """
    Store the UI state for a session.

    Kept per file rather than globally: the channels and cutoffs that suit one
    record are usually wrong for the next, so restoring them by file is the only
    version that is actually useful.
    """
    if _read_meta(session_id) is None:
        raise HTTPException(status_code=404, detail="No such session.")
    try:
        ui = await request.json()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid JSON: {e}") from e
    if not isinstance(ui, dict):
        raise HTTPException(status_code=422, detail="Expected a JSON object.")
    _touch_session(session_id, ui=ui)
    return {"ok": True}


@app.post("/api/session/reparse")
async def session_reparse(
    session_id: str = Form(...),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    fs: Optional[float] = Form(None),
):
    """Re-read a session's file with a different layout, without re-uploading."""
    try:
        sess = get_session(session_id)
        parsed = parse_file(sess["raw"], orientation, header_row)
        sess["parsed"] = parsed
        sess["orientation"] = orientation
        sess["header_row"] = header_row
        # Remember the corrected layout, so reopening doesn't re-guess wrongly.
        _touch_session(
            session_id,
            orientation=orientation,
            header_row=header_row,
            n_columns=parsed["n_columns"],
            n_samples=parsed["n_samples"],
        )

        use_fs: Optional[float] = None
        if 0 <= time_col < parsed["n_columns"]:
            t = extract_col(parsed, time_col)
            use_fs = 1.0 / float(np.mean(np.diff(t)))
        elif fs is not None and fs > 0:
            use_fs = float(fs)

        result = _session_summary(session_id, parsed, time_col, use_fs)
        result["orientation"] = orientation
        result["header_row"] = header_row
        return result
    except (ValueError, TypeError, KeyError, IndexError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.delete("/api/session/{session_id}")
async def session_delete(session_id: str):
    _forget_session(session_id)
    return {"ok": True}


# ─── /api/signal/parse ───────────────────────────────────────────────────────


@app.post("/api/signal/parse")
async def signal_parse(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    fs: Optional[float] = Form(None),
):
    try:
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
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
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── /api/signal/info ────────────────────────────────────────────────────────


@app.post("/api/signal/info")
async def signal_info(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_cols: str = Form(...),
    fs: Optional[float] = Form(None),
):
    try:
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
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
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── /api/signal/timeseries ──────────────────────────────────────────────────


@app.post("/api/signal/timeseries")
async def signal_timeseries(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_cols: str = Form(...),   # JSON array e.g. "[0, 1, 2]"
    fs: Optional[float] = Form(None),
    pp: PreprocParams = Depends(),
):
    try:
        cols = [int(c) for c in json.loads(signal_cols)]
        if not cols:
            raise ValueError("No signal columns selected")
        parsed = await resolve_parsed(file, session_id, orientation, header_row)

        # Reference time axis from first column
        x0, t_raw, fs_raw = get_signal_times_fs(parsed, time_col, cols[0], fs)
        if t_raw is None:
            t_raw = np.arange(len(x0)) / fs_raw

        # Process first column to get processed time axis
        x0_proc, fs_proc, t_proc = apply_preprocessing(x0.copy(), fs_raw, t_raw.copy(), pp)

        preprocessed = any(v is not None for v in [
            pp.win_start, pp.win_end, pp.detrend_order,
            pp.hp_cutoff, pp.lp_cutoff, pp.notch_freq, pp.target_fs,
        ])

        signals = []
        for i, col in enumerate(cols):
            x_raw = extract_col(parsed, col)
            x_proc, _, _ = apply_preprocessing(x_raw.copy(), fs_raw, t_raw.copy(), pp)
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
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── spectral ────────────────────────────────────────────────────────────────


@app.post("/api/spectral/fft")
async def spectral_fft(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_cols: str = Form(...),
    fs: Optional[float] = Form(None),
    window: str = Form("hann"),
    scaling: str = Form("amplitude"),
    pp: PreprocParams = Depends(),
):
    try:
        cols = [int(c) for c in json.loads(signal_cols)]
        if not cols:
            raise ValueError("No signal columns selected")
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        x0, fs_, _ = get_preprocessed(parsed, time_col, cols[0], fs, pp)
        freqs, _ = dsp.fft_spectrum(x0, fs_, window=window, scaling=scaling)
        signals = []
        for col in cols:
            x, _, _ = get_preprocessed(parsed, time_col, col, fs, pp)
            _, amp = dsp.fft_spectrum(x, fs_, window=window, scaling=scaling)
            win_arr = get_window(window, len(x))
            phase = np.angle(np.fft.rfft(x * win_arr), deg=True)
            signals.append({"name": parsed["column_names"][col], "amplitude": to_list(amp), "phase": to_list(phase)})
        return {"freqs": to_list(freqs), "signals": signals}
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/spectral/psd")
async def spectral_psd(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_cols: str = Form(...),
    fs: Optional[float] = Form(None),
    window: str = Form("hann"),
    nperseg: int = Form(1024),
    noverlap: Optional[int] = Form(None),
    scaling: str = Form("density"),
    pp: PreprocParams = Depends(),
):
    try:
        cols = [int(c) for c in json.loads(signal_cols)]
        if not cols:
            raise ValueError("No signal columns selected")
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        x0, fs_, _ = get_preprocessed(parsed, time_col, cols[0], fs, pp)
        freqs, _ = dsp.psd(x0, fs_, window=window, nperseg=nperseg, noverlap=noverlap, scaling=scaling)
        signals = []
        for col in cols:
            x, _, _ = get_preprocessed(parsed, time_col, col, fs, pp)
            _, Pxx = dsp.psd(x, fs_, window=window, nperseg=nperseg, noverlap=noverlap, scaling=scaling)
            signals.append({"name": parsed["column_names"][col], "Pxx": to_list(Pxx)})
        return {"freqs": to_list(freqs), "signals": signals}
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/spectral/autocorrelation")
async def spectral_autocorrelation(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_cols: str = Form(...),
    fs: Optional[float] = Form(None),
    normalize: bool = Form(True),
    max_lag: Optional[float] = Form(None),
    pp: PreprocParams = Depends(),
):
    try:
        cols = [int(c) for c in json.loads(signal_cols)]
        if not cols:
            raise ValueError("No signal columns selected")
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        x0, fs_, _ = get_preprocessed(parsed, time_col, cols[0], fs, pp)
        lags, _ = dsp.autocorrelation(x0, fs=fs_, normalize=normalize, max_lag=max_lag)
        signals = []
        for col in cols:
            x, _, _ = get_preprocessed(parsed, time_col, col, fs, pp)
            _, acf = dsp.autocorrelation(x, fs=fs_, normalize=normalize, max_lag=max_lag)
            signals.append({"name": parsed["column_names"][col], "acf": to_list(acf)})
        # Echoed because it decides the y-axis units: a normalized ACF is a
        # dimensionless ratio, an unnormalized one is in the signal's unit squared.
        return {"lags": to_list(lags), "signals": signals, "normalized": normalize}
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/spectral/cross_correlation")
async def spectral_cross_correlation(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col_x: int = Form(...),
    signal_col_y: int = Form(...),
    fs: Optional[float] = Form(None),
    normalize: bool = Form(True),
    max_lag: Optional[float] = Form(None),
    pp: PreprocParams = Depends(),
):
    try:
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col_x, fs, pp)
        y, _, _ = get_preprocessed(parsed, time_col, signal_col_y, fs, pp)
        lags, ccf = dsp.cross_correlation(x, y, fs=fs_, normalize=normalize, max_lag=max_lag)
        # See the ACF endpoint: this decides whether the axis carries a unit.
        return {"lags": to_list(lags), "ccf": to_list(ccf), "normalized": normalize}
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/spectral/csd")
async def spectral_csd(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col_x: int = Form(...),
    signal_col_y: int = Form(...),
    fs: Optional[float] = Form(None),
    window: str = Form("hann"),
    nperseg: int = Form(1024),
    noverlap: Optional[int] = Form(None),
    pp: PreprocParams = Depends(),
):
    try:
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col_x, fs, pp)
        y, _, _ = get_preprocessed(parsed, time_col, signal_col_y, fs, pp)
        freqs, Pxy = dsp.csd(x, y, fs_, window=window, nperseg=nperseg, noverlap=noverlap)
        return {"freqs": to_list(freqs), "magnitude": to_list(np.abs(Pxy)), "phase_deg": to_list(np.angle(Pxy, deg=True))}
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/spectral/coherence")
async def spectral_coherence(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col_x: int = Form(...),
    signal_col_y: int = Form(...),
    fs: Optional[float] = Form(None),
    window: str = Form("hann"),
    nperseg: int = Form(1024),
    noverlap: Optional[int] = Form(None),
    pp: PreprocParams = Depends(),
):
    try:
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col_x, fs, pp)
        y, _, _ = get_preprocessed(parsed, time_col, signal_col_y, fs, pp)
        freqs, Cxy = dsp.coherence(x, y, fs_, window=window, nperseg=nperseg, noverlap=noverlap)
        _, Pxy = dsp.csd(x, y, fs_, window=window, nperseg=nperseg, noverlap=noverlap)
        return {"freqs": to_list(freqs), "Cxy": to_list(Cxy), "phase_deg": to_list(np.angle(Pxy, deg=True))}
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── filter ──────────────────────────────────────────────────────────────────


@app.post("/api/filter/apply")
async def filter_apply(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
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
    pp: PreprocParams = Depends(),
):
    try:
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, pp)

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
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/filter/response")
async def filter_response(
    fs: float = Form(...),
    hp_cutoff: Optional[float] = Form(None),
    hp_order: int = Form(4),
    lp_cutoff: Optional[float] = Form(None),
    lp_order: int = Form(4),
    notch_freq: Optional[float] = Form(None),
    notch_q: float = Form(30.0),
    zero_phase: bool = Form(True),
    n_points: int = Form(512),
):
    """
    Magnitude response of the preprocessing filter chain, for overlaying on a
    spectrum.

    Designed with the same scipy calls dspkit uses, so the curve is the filter
    that actually runs rather than an idealised one. Zero-phase filtering
    applies the filter forwards and backwards, so the magnitude response is
    squared -- which moves the real -3 dB point well inside the nominal cutoff.
    That discrepancy is the main reason to draw this at all.
    """
    try:
        from scipy import signal as _sig

        if fs <= 0:
            raise ValueError("fs must be positive")
        nyq = fs / 2.0
        w = np.linspace(0.0, nyq, max(16, min(n_points, 8192)))
        mag = np.ones_like(w)
        stages = []

        if hp_cutoff is not None and 0 < hp_cutoff < nyq:
            stages.append(_sig.butter(hp_order, hp_cutoff, btype="high", fs=fs, output="sos"))
        if lp_cutoff is not None and 0 < lp_cutoff < nyq:
            stages.append(_sig.butter(lp_order, lp_cutoff, btype="low", fs=fs, output="sos"))
        for sos in stages:
            _, h = _sig.sosfreqz(sos, worN=w, fs=fs)
            mag *= np.abs(h)

        if notch_freq is not None and 0 < notch_freq < nyq:
            b, a = _sig.iirnotch(notch_freq, notch_q, fs=fs)
            _, h = _sig.freqz(b, a, worN=w, fs=fs)
            mag *= np.abs(h)

        applied = bool(stages) or (notch_freq is not None and 0 < notch_freq < nyq)
        if zero_phase:
            mag = mag ** 2          # filtfilt: forward + reverse

        # Where the response actually crosses -3 dB, which is what you read off.
        half_power = float(1 / np.sqrt(2))
        crossings = []
        for i in range(1, len(w)):
            a0, b0 = mag[i - 1], mag[i]
            if (a0 - half_power) * (b0 - half_power) < 0:
                frac = (half_power - a0) / (b0 - a0) if b0 != a0 else 0.0
                crossings.append(float(w[i - 1] + frac * (w[i] - w[i - 1])))

        return {
            "freqs": to_list(w),
            "magnitude": to_list(mag),
            "applied": applied,
            "zero_phase": zero_phase,
            "minus3db": crossings[:4],
            "effective_order": {
                "hp": hp_order * (2 if zero_phase else 1),
                "lp": lp_order * (2 if zero_phase else 1),
            },
        }
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── time-frequency ───────────────────────────────────────────────────────────


@app.post("/api/timefreq/stft")
async def timefreq_stft(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    window: str = Form("hann"),
    nperseg: int = Form(256),
    noverlap: Optional[int] = Form(None),
    pp: PreprocParams = Depends(),
):
    try:
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, pp)
        freqs, times, Zxx = dsp.stft(x, fs_, window=window, nperseg=nperseg, noverlap=noverlap)
        return {"freqs": to_list(freqs), "times": to_list(times), "magnitude": to_list(np.abs(Zxx))}
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/timefreq/cwt")
async def timefreq_cwt(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    f_min: float = Form(1.0),
    f_max: Optional[float] = Form(None),
    n_freqs: int = Form(50),
    w: float = Form(6.0),
    pp: PreprocParams = Depends(),
):
    try:
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, pp)
        f_max_ = f_max if f_max is not None else fs_ / 4.0
        freqs = np.geomspace(f_min, f_max_, n_freqs)
        freqs_out, times, W = dsp.cwt_scalogram(x, fs_, freqs=freqs, w=w)
        return {"freqs": to_list(freqs_out), "times": to_list(times), "magnitude": to_list(np.abs(W))}
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/timefreq/wvd")
async def timefreq_wvd(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    pp: PreprocParams = Depends(),
):
    try:
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, pp)
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
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    lag_samples: Optional[int] = Form(None),
    time_samples: Optional[int] = Form(None),
    pp: PreprocParams = Depends(),
):
    try:
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, pp)
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
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    pp: PreprocParams = Depends(),
):
    try:
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, pp)
        envelope, phase, inst_freq = dsp.hilbert_attributes(x, fs_)
        return {
            "times": to_list(t),
            "signal": to_list(x),
            "envelope": to_list(envelope),
            "phase": to_list(phase),
            "inst_freq": to_list(inst_freq),
        }
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── EMD ─────────────────────────────────────────────────────────────────────


@app.post("/api/emd/decompose")
async def emd_decompose(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    max_imfs: Optional[int] = Form(None),
    max_sifting: int = Form(10),
    pp: PreprocParams = Depends(),
):
    try:
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, pp)
        imfs, residue = dsp.emd(x, max_imfs=max_imfs, max_sifting=max_sifting)
        return {"times": to_list(t), "imfs": to_list(imfs), "residue": to_list(residue)}
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/emd/hht")
async def emd_hht(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    max_imfs: Optional[int] = Form(None),
    max_sifting: int = Form(10),
    n_bins: int = Form(512),
    pp: PreprocParams = Depends(),
):
    try:
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, pp)
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
    except HTTPException:
        raise
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
    pp: PreprocParams,
) -> tuple[np.ndarray, float, np.ndarray, list[str]]:
    """Return (data [n_ch × N], fs, times, labels)."""
    channels = []
    fs_out = None
    times_out = None
    labels = []
    for col in signal_cols:
        x, fs_, t = get_preprocessed(parsed, time_col, col, fs_manual, pp)
        channels.append(x)
        if fs_out is None:
            fs_out, times_out = fs_, t
        labels.append(parsed["column_names"][col])
    return np.array(channels), fs_out, times_out, labels


# ─── peaks ────────────────────────────────────────────────────────────────────


@app.post("/api/peaks/detect")
async def peaks_detect(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
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
    pp: PreprocParams = Depends(),
):
    try:
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, pp)
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
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/peaks/harmonics")
async def peaks_harmonics(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    window: str = Form("hann"),
    scaling: str = Form("amplitude"),
    fundamental: float = Form(...),
    n_harmonics: int = Form(5),
    pp: PreprocParams = Depends(),
):
    try:
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, pp)
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
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── SHM indicators ──────────────────────────────────────────────────────────


@app.post("/api/indicators")
async def shm_indicators(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    segment_duration: Optional[float] = Form(None),
    excess: bool = Form(True),
    window: str = Form("hann"),
    nperseg: int = Form(1024),
    pp: PreprocParams = Depends(),
):
    try:
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, pp)
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
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── multi-sensor ────────────────────────────────────────────────────────────


@app.post("/api/multisensor/correlation")
async def multisensor_correlation(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_cols: str = Form(...),
    fs: Optional[float] = Form(None),
    pp: PreprocParams = Depends(),
):
    try:
        cols = [int(c) for c in json.loads(signal_cols)]
        if len(cols) < 2:
            raise ValueError("At least 2 channels required")
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        data, fs_, t, labels = get_multichannel(parsed, time_col, cols, fs, pp)
        from dspkit.multisensor import correlation_matrix as _corr_mat
        R = _corr_mat(data)
        return {"R": to_list(R), "labels": labels}
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/multisensor/coherence_matrix")
async def multisensor_coherence_mat(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_cols: str = Form(...),
    fs: Optional[float] = Form(None),
    window: str = Form("hann"),
    nperseg: int = Form(1024),
    pp: PreprocParams = Depends(),
):
    try:
        cols = [int(c) for c in json.loads(signal_cols)]
        if len(cols) < 2:
            raise ValueError("At least 2 channels required")
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        data, fs_, t, labels = get_multichannel(parsed, time_col, cols, fs, pp)
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
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── FDD ──────────────────────────────────────────────────────────────────────
#
# Peak-picking defaults. These matter more than most defaults in the app,
# because every peak FDD returns arrives with a damping ratio and a mode shape
# attached — it *looks* like a result whether or not it is one. With no filter
# at all, the picker returned the ten most prominent local maxima of the SV1
# curve, which on a clean two-mode record meant the two real modes plus eight
# pieces of noise, indistinguishable in the table.
#
# Both thresholds were set from `test_2dof.csv`, whose modes are known to be at
# 10 and 25 Hz. There the true peaks have 19–27 dB prominence and 25–38 dB
# SV1/SV2 dominance, while every noise peak sits below 5 dB on both measures —
# so 6 dB separates them with a wide margin from either side. Running the same
# file with its force channels included (the documented trap, where FDD is
# meaningless) leaves nothing above either threshold, which is the right answer.

_FDD_MIN_PROMINENCE_DB = 6.0
_FDD_MIN_DOMINANCE_DB = 6.0
_FDD_MAX_PEAKS = 10


def _fdd_dominance_db(S: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """
    How far SV1 stands above SV2 at each peak, in dB.

    A single dominant mode at a frequency line drives SV1 well clear of SV2;
    broadband noise leaves them comparable. This is the measure that catches a
    prominent-looking rise that isn't a mode at all.
    """
    idx = np.asarray(indices, dtype=int)
    if idx.size == 0:
        return np.zeros(0)
    sv1 = np.maximum(S[idx, 0], 1e-300)
    if S.shape[1] < 2:
        # One channel cannot express dominance; don't let the gate reject
        # everything on a degenerate input.
        return np.full(idx.size, np.inf)
    sv2 = np.maximum(S[idx, 1], 1e-300)
    return 10.0 * np.log10(sv1 / sv2)


@app.post("/api/fdd/analyze")
async def fdd_analyze(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
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
    min_dominance_db: float = Form(_FDD_MIN_DOMINANCE_DB),
    pp: PreprocParams = Depends(),
):
    try:
        cols = [int(c) for c in json.loads(signal_cols)]
        if len(cols) < 2:
            raise ValueError("At least 2 channels required")
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        data, fs_, t, labels = get_multichannel(parsed, time_col, cols, fs, pp)
        from dspkit.fdd import fdd_svd, fdd_peak_picking, fdd_mode_shapes, efdd_damping

        freqs, S, U = fdd_svd(data, fs_, window=window, nperseg=nperseg)
        freq_range = None
        if freq_min is not None and freq_max is not None:
            freq_range = (freq_min, freq_max)

        # Every local maximum in the SV1 curve, as the denominator for "n of m
        # candidates survived". Cheap, and it lets the panel say what was
        # discarded instead of silently presenting the remainder.
        _, all_candidates = fdd_peak_picking(
            freqs, S, distance_hz=distance_hz, freq_range=freq_range,
        )

        use_prominence = (
            prominence if prominence is not None else _FDD_MIN_PROMINENCE_DB
        )
        _max = max_peaks if max_peaks is not None else _FDD_MAX_PEAKS
        peak_freqs, peak_indices = fdd_peak_picking(
            freqs, S, prominence=use_prominence,
            distance_hz=distance_hz, max_peaks=_max, freq_range=freq_range,
        )

        # Second gate: at a real mode one shape dominates, so SV1 stands well
        # clear of SV2. Noise gives SV1 ≈ SV2. Prominence alone doesn't catch
        # this — a broad rise in a flat spectrum can be prominent and still be
        # nothing — which is how force channels used to yield "modes" at
        # 285/442/72 Hz with damping ratios attached.
        dominance = _fdd_dominance_db(S, peak_indices)
        if min_dominance_db > 0 and peak_indices.size:
            keep = dominance >= min_dominance_db
            peak_indices = peak_indices[keep]
            peak_freqs = peak_freqs[keep]
            dominance = dominance[keep]

        # Report modes in frequency order. dspkit returns them ranked by
        # prominence, which is right for truncating to max_peaks but wrong for
        # a table someone reads as a mode list.
        if peak_indices.size:
            order = np.argsort(peak_freqs)
            peak_indices = peak_indices[order]
            peak_freqs = peak_freqs[order]
            dominance = dominance[order]

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
            # What was required, and what didn't make it. A mode table is only
            # readable if the criteria behind it are visible — and an empty
            # result has to be distinguishable from a failed one.
            "peak_dominance_db": to_list(dominance),
            "criteria": {
                "prominence_db": float(use_prominence),
                "min_dominance_db": float(min_dominance_db),
                "max_peaks": int(_max),
                "defaulted": prominence is None,
                "n_candidates": int(np.size(all_candidates)),
                "n_accepted": int(peak_indices.size),
            },
        }
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ─── statistics ───────────────────────────────────────────────────────────────


@app.post("/api/statistics/pdf")
async def statistics_pdf(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col: int = Form(...),
    fs: Optional[float] = Form(None),
    bins: int = Form(50),
    bandwidth: Optional[float] = Form(None),
    pp: PreprocParams = Depends(),
):
    try:
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        x, fs_, t = get_preprocessed(parsed, time_col, signal_col, fs, pp)
        from dspkit.statistics import pdf_estimate as _pdf, histogram as _hist
        xi, density = _pdf(x, bandwidth=bandwidth)
        bin_centres, counts = _hist(x, bins=bins, density=True)
        return {
            "xi": to_list(xi),
            "density": to_list(density),
            "bin_centres": to_list(bin_centres),
            "hist_density": to_list(counts),
        }
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/statistics/joint")
async def statistics_joint(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_col_x: int = Form(...),
    signal_col_y: int = Form(...),
    fs: Optional[float] = Form(None),
    bins: int = Form(50),
    pp: PreprocParams = Depends(),
):
    try:
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        x, fs_, _ = get_preprocessed(parsed, time_col, signal_col_x, fs, pp)
        y, _, _ = get_preprocessed(parsed, time_col, signal_col_y, fs, pp)
        from dspkit.statistics import joint_histogram as _joint
        x_centres, y_centres, H = _joint(x, y, bins=bins, density=True)
        return {
            "x_centres": to_list(x_centres),
            "y_centres": to_list(y_centres),
            "H": to_list(H),
            "xlabel": parsed["column_names"][signal_col_x],
            "ylabel": parsed["column_names"][signal_col_y],
        }
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/statistics/covariance")
async def statistics_covariance(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_cols: str = Form(...),
    fs: Optional[float] = Form(None),
    pp: PreprocParams = Depends(),
):
    try:
        cols = [int(c) for c in json.loads(signal_cols)]
        if len(cols) < 2:
            raise ValueError("At least 2 channels required")
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        data, fs_, t, labels = get_multichannel(parsed, time_col, cols, fs, pp)
        from dspkit.statistics import covariance_matrix as _cov
        C = _cov(data)
        return {"C": to_list(C), "labels": labels}
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/statistics/mahalanobis")
async def statistics_mahalanobis(
    file: Optional[UploadFile] = None,
    session_id: Optional[str] = Form(None),
    orientation: str = Form("columns"),
    header_row: int = Form(-1),
    time_col: int = Form(-1),
    signal_cols: str = Form(...),
    fs: Optional[float] = Form(None),
    percentile: float = Form(99),
    pp: PreprocParams = Depends(),
):
    try:
        cols = [int(c) for c in json.loads(signal_cols)]
        if len(cols) < 2:
            raise ValueError("At least 2 channels required")
        parsed = await resolve_parsed(file, session_id, orientation, header_row)
        data, fs_, t, labels = get_multichannel(parsed, time_col, cols, fs, pp)
        from dspkit.statistics import mahalanobis as _maha
        distances = _maha(data)
        threshold = float(np.percentile(distances, percentile))
        return {
            "times": to_list(t),
            "distances": to_list(distances),
            "threshold": threshold,
            "percentile": percentile,
        }
    except HTTPException:
        raise
    except (ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

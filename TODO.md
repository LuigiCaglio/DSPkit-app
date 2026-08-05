# DSPkit-app — what's left

State as of 2026-08-05, branch `plug-and-play-gui` (2 commits ahead of `master`:
`bb3a186`, `02f252e`).

The app is usable for day-to-day work now. Everything below is either
*repeatability* or *someone-else-sized* — nothing here blocks your own use.

---

## 1. Gate for other people using it

### 1.1 File formats beyond delimited text
**Why it's first:** `parse_file` (`backend/main.py:86`) handles CSV/TSV/TXT only.
Real SHM and vibration data arrives as `.mat`, `.tdms` (NI), `.h5`/HDF5 or
`.parquet`. For anyone else's "drop a file and it works", this is the single
biggest gap.

**Why it's contained:** `parse_file` is the one entry point — `autodetect`
(`main.py:191`) and `_new_session` (`main.py:261`) both funnel through it.
Dispatch on magic bytes / extension, and return the same
`{data, column_names, n_columns, n_samples}` dict; nothing downstream changes.

Watch out: `.mat` and `.tdms` carry channel names and often a sample rate, so
they can skip the `_detect_time_col` guesswork entirely — the session response
already has fields for both.

### 1.2 Commit a test suite
Currently **zero committed tests** against ~1,700 lines of backend and a
frontend that was just restructured.

> ⚠️ The suites written during this work live in a **session temp directory that
> will be deleted**. They are not in the repo. Recreate or ask for them to be
> committed before they're gone.

What they covered, worth reproducing:

| suite | asserts |
|---|---|
| API smoke | session create → Overview trio → STFT/peaks fan-out per channel → pairwise → FDD refusing 1 channel |
| single-channel | 14 analyses reachable with one channel; the 4 between-sensor ones return 422; `coherence(x,x) == 1.000000` |
| zoom unit (node) | window-before-decimate: point budget, full-rate at 1 s, x/y pairing, over-wide windows, out-of-range and inverted ranges |
| cross-corr lag unit (node) | axis ranges per side, full trace retained, peak found *within the visible half*, anticorrelation sign, one-sided records |

The node suites import `frontend/src/lib/plotSpec.js` directly — it's pure, so it
tests without a browser. That was a deliberate reason to extract it.

### 1.3 Error messages are raw exception strings
`ValueError: At least 2 channels required` is fine for you; it reads as a crash
to anyone else. Every endpoint's `except` block formats `f"{type(e).__name__}: {e}"`.
Map the common ones to plain sentences.

---

## 2. Research correctness

### 2.1 FDD peak-picking defaults are weak
**Evidence:** on `test_2dof.csv` with the two response channels, the true modes
are 10.0 and 25.0 Hz. The top two picks are right; everything below is noise.
With all four columns (including `force1`/`force2`) it returns 285/442/72 Hz —
garbage.

The force-channel half is handled: the Overview panel names the channels it ran
on and states that FDD is output-only. **The defaults are not.**
`fdd_analyze` (`main.py:1470`) falls back to `max_peaks=10` with no prominence
filter, so you get ~7 fake modes *with damping ratios attached* — exactly the
table that ends up in a paper by accident.

Options, roughly in order of value:
- prominence default relative to the SV1 noise floor rather than absolute
- require SV1 dominance (SV1/SV2 ratio) at a candidate peak
- a stabilization diagram across `nperseg`, which is the real answer
- mode-shape (MAC) plot — currently only the numeric table exists

Deliberately **not** done: guessing excitation channels from column names.
That would silently override an explicit selection.

### 2.2 No units
Axes say "Amplitude". No way to declare m/s², g, mm. Needed for any figure that
leaves your machine. Would live per-channel, alongside the channel names.

### 2.3 Irregular sampling falls back silently-ish
`_detect_time_col` (`main.py:161`) rejects a time column whose interval
coefficient of variation exceeds 1e-3, then returns `(-1, None)` — so a record
with gaps or jitter lands on the manual default of **1000 Hz**
(`App.svelte`, `fsManual`). The topbar does say `fs 1000 Hz (manual)`, so it
isn't invisible, but nothing says *why* detection failed. A file with a dropout
gets analysed at a made-up rate and looks fine.

Better: report *why* the time column was rejected (non-monotonic vs non-uniform)
and show the interval spread.

---

## 3. Nice, not blocking

- **Figure export** at publication size / SVG. Plotly's modebar already gives a
  PNG, so this is only about vector output and fixed dimensions.
- **Saved analysis config.** Theme and pane heights persist (`localStorage`);
  channel selection, preprocessing and analysis params do not survive a reload.
  `paramStore.svelte.js` is the natural place to hang this.
- **Batch / multi-file comparison.** Sessions are capped at 4
  (`_MAX_SESSIONS`, `main.py:258`) with oldest-out eviction, so the backend can
  already hold several files — nothing in the UI exposes that.
- **Bundle size.** 4.9 MB / 1.5 MB gzipped, almost entirely Plotly. Fine over
  localhost, not fine if this is ever served remotely.

---

## Known-unverified

The Chrome extension was **not connected** throughout this work, so **no part of
the UI has been visually confirmed** — only builds, API behaviour and pure-logic
unit tests.

Highest-value things to click through:
1. Param persistence — PSD `nperseg` → FFT → back to PSD, does it hold?
2. Drag-resize feel — is an 11 px handle a comfortable target?
3. Auto-run eagerness — if any tab is too keen, it's one line in the `AUTORUN`
   set in `frontend/src/lib/analyses.js`.

Useful trick when the extension is unavailable: **headless Edge** renders and
reports layout, where headless Chrome produced empty output in this environment.
Build a harness page that copies the real CSS rules, measure
`scrollHeight`/`clientHeight` and element rects in inline JS, write the results
into the DOM, then read them back with:

```
msedge.exe --headless=new --disable-gpu --no-sandbox --virtual-time-budget=4000 \
           --user-data-dir=<tmp> --dump-dom file:///<harness>.html
```

That's how the scroll/clipping fix was verified.

# DSPkit-app — what's left

State as of 2026-08-06. `master` is at `df2fa36`; current branch is
`timefreq-display`, which carries §3.1 and the session-persistence work below,
and is **not yet merged**.

The app is usable for day-to-day work now. Everything below is either
*repeatability* or *someone-else-sized* — nothing here blocks your own use.

Run the tests with `python tests/run_all.py` — no third-party packages needed.
232 assertions (63 API, 33 persistence, 26 detection, 23 FDD, 87 frontend).

**§1.1 (file formats) is deliberately closed.** Confirmed 2026-08-06 that the
data here is CSV/TSV/TXT only, so `.mat`/`.tdms`/HDF5 support would be work for
a hypothetical other user. Reopen it if that stops being true.

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

### 1.2 Widen test coverage
`tests/` now holds 108 assertions (63 API, 45 frontend) — run with
`python tests/run_all.py`, no third-party packages needed. See `tests/README.md`.

Still uncovered, because it needs a rendered DOM: drag-resizing, the plot area's
scroll behaviour, parameter persistence across tab switches, and whether
auto-run fires on mount.

### 1.3 Error messages are raw exception strings
`ValueError: At least 2 channels required` is fine for you; it reads as a crash
to anyone else. Every endpoint's `except` block formats `f"{type(e).__name__}: {e}"`.
Map the common ones to plain sentences.

---

## 2. Research correctness

§2.1 and §2.3 are done (2026-08-06) — both were cases where the app stated
something it hadn't earned. §2.2 (units) is the one left.

### 2.1 FDD peak-picking defaults — done 2026-08-06
Two gates, both defaulting to 6 dB (`_FDD_MIN_PROMINENCE_DB`,
`_FDD_MIN_DOMINANCE_DB` in `main.py`): peak prominence on the SV1 curve, and
SV1/SV2 dominance at the candidate. On `test_2dof.csv` the response channels now
return **exactly 10.0 and 25.0 Hz** out of 119 candidates, and the four-column
selection including `force1`/`force2` returns **nothing** rather than
285/442/72 Hz.

The thresholds were measured, not guessed: true modes there have 19–27 dB
prominence and 25–38 dB dominance, every noise peak sits under 5 dB on both, so
6 dB has a wide margin from either side. Both are exposed in `FddControls`;
setting either to 0 restores the old everything-goes behaviour.

Also changed, because the table is what gets read:
- modes come back in **frequency order** (dspkit ranks by prominence, which is
  right for truncating to `max_peaks` and wrong for a list someone reads)
- an **SV1/SV2 column**, and it travels into the CSV export
- the criteria and the survival count sit under the table, and an empty result
  says what the bar was and that an excitation channel is the usual cause —
  an empty FDD table is now a real answer, so it must not read as a broken panel

Still open, and still the real answer:
- a **stabilization diagram** across `nperseg`
- **mode-shape (MAC) plot** — only the numeric table exists

Deliberately **not** done: guessing excitation channels from column names.
That would silently override an explicit selection.

### 2.2 No units
Axes say "Amplitude". No way to declare m/s², g, mm. Needed for any figure that
leaves your machine. Would live per-channel, alongside the channel names.

### 2.3 Irregular sampling — done 2026-08-06
`_detect_time_col` now returns `(col, fs, rejection)`, where `rejection`
describes the closest column that nearly qualified: `non_uniform` or
`not_monotonic`, plus the interval spread, the count of intervals that stray
from the median, and the rate that median implies. It travels through
`autodetect` → `detected.time_col_rejected` → the session response, so a
restored session still knows why its rate is manual.

The distinction that earns its keep is **one gap vs pervasive jitter**, and
`n_irregular / n_intervals` is what separates them — the coefficient of
variation cannot, because a single dropout and constant jitter produce the same
number. One gap is reported as an note ("the rate between the gaps is steady, so
1000 Hz is still right — but the record is not continuous"); widespread
irregularity is a warning that says frequency-domain results are suspect.

`fsManual` is now seeded from the rejected column's median interval rather than
the hardcoded 1000 Hz, and the banner says where the number came from. Messages
live in `frontend/src/lib/detect.js` (tested); the API side is
`tests/api/test_detect.py`.

Still open: nothing offers to **resample** an irregular record onto a uniform
grid, which is what a jittery file actually needs before any spectrum.

---

## 3. Time-frequency: deepen, don't rebuild

Decided 2026-08-05. **Not** separate software, and **not** more transforms first.

The coverage is already decent — STFT, CWT, WVD, SPWVD, plus EMD/HHT under
Decomposition. WVD and SPWVD are more than most vibration tools ship. What's
weak is the *interaction*: each transform is a static heatmap with two numeric
knobs and a fixed Viridis scale.

A standalone app would have to re-implement the loading, auto-detection,
preprocessing and channel selection that already work here. The value is being
next to them.

### 3.1 dB and colour-range control — done
See "Done since this file was written" below.

### 3.2 A linked Time-Frequency Explorer tab
Time series on top, spectrogram below, PSD rotated on the right, all sharing
axes. Plus:

- **crosshair slices** — click a time to get the spectrum there, click a
  frequency to get its envelope over time
- **one transform selector** (STFT / CWT / WVD / SPWVD) with the relevant
  params, so you can flip between them *on the same data with the same colour
  scale*. That comparison is what tells you which one to trust — right now they
  live in four tabs with independent scales, so they can't be compared.
- **resolution readout** — show the resulting Δt and Δf for the chosen window
  instead of making you infer it from `nperseg`

Mostly frontend work against endpoints that already exist. `PlotCanvas` +
`plotSpec` were built to make exactly this kind of composition cheap.

⚠️ **WVD is O(N²)** — it is excluded from `AUTORUN` for that reason
(`analyses.js`). An explorer that recomputes on every slider nudge needs a
decimation/length-cap story first, or it will hang on a real record.

### 3.3 New DSP — belongs in `dspkit`, not this app
- **Synchrosqueezing / reassignment** — the single highest-value addition;
  sharpens both STFT and CWT dramatically
- Multitaper spectrogram
- Stockwell (S) transform

### 3.4 Move the filter response off a second y-axis
The response overlay on the FFT and PSD (`plotSpec.js`, `responseTrace`) draws
filter gain on `yaxis2`, over the spectrum. A dual-axis chart is the most common
charting mistake: two unrelated scales share one plot area, so where the curves
cross reads as meaningful when it is an artefact of how each axis was scaled.

The remedy is a **small linked panel below the spectrum sharing the x-axis**,
rather than an overlay — the response then gets a readable 0–1 axis of its own
instead of being squeezed against the PSD. `ResizablePane` and `PlotCanvas`
already make this cheap; roughly half an hour.

Deferred 2026-08-05 to see whether the overlay is a problem in practice. If it
stays, it should at least keep its dotted, muted styling so it reads as an
annotation rather than a second data series.

---

## 4. Nice, not blocking

- **Figure export** at publication size / SVG. Plotly's modebar already gives a
  PNG, so this is only about vector output and fixed dimensions.
- ~~**Saved analysis config.**~~ Done — see "Sessions that survive" below.
- **Batch / multi-file comparison.** The store now keeps 12 files on disk
  (`_MAX_RECENT`) and the Recent files list can reach any of them, but only one
  at a time. Comparing two records side by side still isn't possible.
- **Bundle size.** 4.9 MB / 1.5 MB gzipped, almost entirely Plotly. Fine over
  localhost, not fine if this is ever served remotely.

---

## Done since this file was written

- **The two silent-wrongness fixes** (2026-08-06) — §2.1 and §2.3 above, both
  verified in a real browser. The FDD change was checked at both ends: the
  mode table renders 10.01 / 25.01 Hz with their SV1/SV2 figures on the
  response channels, and the four-column selection renders the empty state
  naming the excitation channels instead of a table of noise.
- **Sessions that survive a restart** (2026-08-06). A session is now two files
  under `~/.dspkit-app/sessions/` — metadata plus the raw bytes, though the
  bytes are only copied for uploads, since a file opened by path is re-read
  from where it lives. `_SESSIONS` is a parse cache in front of that, so an
  evicted session rehydrates on next use instead of 404ing.
  - **Launch resumes.** `resumeOnLaunch` in `App.svelte` opens the file named on
    the command line if there is one, else the most recent session.
  - **Settings come back per file.** Channel selection, preprocessing, layout
    overrides, active tab and every analysis parameter are saved against the
    session (debounced, 700 ms) and restored on reopen. Per *file*, not
    globally — the channels that suit one record are wrong for the next. A
    "settings restored" chip says when this has happened, because a filter left
    on last week would otherwise silently shape today's results.
  - **`applyState` distrusts what it reads** (`sessionState.js`): channels past
    the end of the file are dropped, the time column can never come back as a
    signal, and a state whose selection no longer fits falls through to
    defaults. This is where the sharp edges are — see `sessionstate.test.mjs`.
  - **Open by path, and Recent files.** `POST /api/session/open` takes a path;
    reopening a path returns the session it already had rather than a duplicate.
    The list flags files that changed on disk since they were opened.
  - **`run.py <file>`** opens the app on that file, and `run_dspkit_app.bat`
    forwards its argument — so a CSV can be dragged onto the launcher or set as
    the "Open with" program. Launching twice now opens a tab against the running
    instance instead of failing to bind port 8000.
  - Path access is gated on a loopback `Host` *and* a same-origin `Origin`
    (`_require_local_origin`). The Host check is what stops DNS rebinding; the
    origin check alone would pass it.

- **Filter cutoffs picked from the PSD *and* FFT** (`setFilterFromRange` in
  `App.svelte`). "Pick from plot" switches the chart to a horizontal selection
  and the bounds stay typeable; the rejected bands are shaded onto the spectrum
  so the filter is visible against the data it was chosen from. Band-pass is the
  high- and low-pass together, which is how preprocessing already represents it.
- **Committed test suites** under `tests/` (see §1.2).
- **dB and colour-range control on the time-frequency heatmaps** (§3.1). dB
  relative to peak is now the default with an adjustable dynamic range; linear
  mode clips the top percentile. Ramp is selectable among perceptually uniform
  options only. Settings persist.

---

## Known-unverified

The Chrome extension has never connected in this environment, so **layout and
visual design remain unconfirmed** — nobody has looked at the app.

*Behaviour*, however, is no longer unverified. The whole restore path was driven
in a real browser on 2026-08-06 (headless Edge, recipe below) and checked by
reading the requests the app actually sent:

```
GET  /api/launch-target                     → nothing to open
GET  /api/session/recent → GET /api/session/<id>   → last session restored
POST /api/spectral/psd?hp_cutoff=7&hp_order=4&zero_phase=true
     signal_cols=[1,2]  nperseg=4096              → every layer restored
```

That covers channel selection, preprocessing, the analysis parameters and the
active tab, and confirms the write-back doesn't clobber what it just restored.
Two bugs surfaced this way that no unit test had caught: the origin check
hardcoded port 8000 (so it refused the app's own request on any other port), and
Recent files was fetched once at mount, before the restored session existed.

Still needing eyes rather than assertions:
1. Drag-resize feel — is an 11 px handle a comfortable target?
2. Auto-run eagerness — if any tab is too keen, it's one line in the `AUTORUN`
   set in `frontend/src/lib/analyses.js`.
3. Whether the sidebar is crowded now that Recent files sits in it.

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

Pointing the same command at a **running backend** renders the real app, which
is how the restore path above was checked. Two gotchas:

- `--dump-dom` serialises *attributes*, and Svelte sets input values and
  checkboxes as DOM *properties* — so a restored `nperseg` or channel tick is
  invisible in the dump even when it is correct. Don't read absence there as a
  bug.
- To see those, read the wire instead: wrap the app in a tiny ASGI shim that
  logs each `/api/` request line and form body, and run
  `uvicorn probe:app` against it. The request the app sends is the ground truth
  for what got restored, and it needs no changes to the app itself.

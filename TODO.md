# DSPkit-app — what's left

State as of 2026-08-07. `timefreq-display` is **merged**; `master` carries
§3.1, the session-persistence work and per-channel units.

The app is usable for day-to-day work now. Everything below is either
*repeatability* or *someone-else-sized* — nothing here blocks your own use.

Run the tests with `python tests/run_all.py` — no third-party packages needed.
342 assertions (83 API, 39 persistence, 26 detection, 23 FDD, 171 frontend).
dspkit has its own suite: `pytest tests/` in the DSPkit repo, 189 passing.

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
Counts live in the header above, so there is one number to keep current. Run with
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

All three are done. §2.1 and §2.3 (2026-08-06) and §2.2 (2026-08-07) were the
same kind of problem: the app stating something it hadn't earned, or refusing to
state something it knew.

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

### 2.2 Units — done 2026-08-07
Declared per channel, in the channel list behind a "Units" toggle (off until one
is set, then it stays open — 20 extra boxes in that sidebar is a bad default).
They persist per session and are clamped on the way back in like everything else.

Display only: **nothing is converted or rescaled**, because the numbers in the
file are already in whatever you say they are in.

The algebra is the part worth having (`frontend/src/lib/units.js`): an
acceleration PSD is `(m/s²)²/Hz`, not `m/s²/Hz`, and a probability density is
`1/(m/s²)`. Compound units get bracketed before taking an exponent; simple ones
don't, so `g` gives the `g²/Hz` everyone actually writes.

The rule that decides every case: **a unit is shown only when it is known and
unambiguous.** Concretely —
- channels that disagree silence the shared axis rather than letting the first
  channel's unit stand for all of them; the small-multiples cells still label
  individually, since each shows one channel
- normalising strips the unit — dividing by RMS leaves a dimensionless ratio
- an unnormalized ACF is in the unit *squared*, a normalized one is
  dimensionless, so `/api/spectral/{autocorrelation,cross_correlation}` now echo
  `normalized` rather than making the frontend guess
- STFT and CWT linear colourbars carry the signal unit; **WVD and SPWVD stay
  bare**, because their energy-density scaling makes the unit ambiguous and a
  wrong unit is worse than none
- dB colourbars are relative to peak, so no unit applies

Units travel into the **CSV headers** too (`acc1 [m/s²]`, `PSD [g²/Hz]`) — a
table pasted into a report is exactly where nobody can ask what the numbers were
in. Commas and quotes are stripped from a unit on entry so a header cannot split.

Not done: unit-aware *conversion* (g ↔ m/s²), and no unit appears on the
covariance matrix, whose entries have pairwise-different units.

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

### 3.2 A linked Time-Frequency Explorer tab — done 2026-08-07
First tab under **Time-Freq**. Time series on top, the surface below, the PSD
rotated on the right, all sharing the axes that make them comparable — a ridge
traces *up* to when it happened and *across* to the frequency it happened at.

- **One transform selector** (STFT / CWT / WVD / SPWVD) on the same data with
  the same colour scale. That comparison is the point: four tabs with
  independent scales could not be compared at all.
- **Crosshair slices.** Click the surface: the spectrum at that instant is drawn
  *against* the average PSD on the same panel, and the picked frequency's
  energy-over-time gets a panel of its own. Both are taken from the matrix
  already in memory, so picking costs a redraw, not a request.
- **Resolution readout** — the Δt and Δf the window actually bought, measured
  off the returned axes rather than re-derived from `nperseg`. A CWT says
  "Δf varies (geometric axis)" instead of quoting a number that doesn't exist.

The envelope slice gets a fourth panel rather than a second y-axis on the time
series, for the reason §3.4 gives: they are different quantities, and overlaying
them would make where the curves cross look meaningful.

**The O(N²) story, which had to come first.** It turned out to be two problems:

1. *Compute.* WVD and SPWVD are capped at 2048 input samples — not a new
   number, it is the limit the WVD tab has always warned about, now enforced
   rather than left to you. The window is taken from the **middle** of the
   record, since the start is usually settling, and it is intersected with any
   preprocessing window rather than replacing it. Neither auto-runs.
2. *Payload.* The cap alone was not enough: a capped WVD is still 1025 × 2048
   values — **48 MB of JSON** for a panel a few hundred pixels tall. The
   timefreq endpoints now take optional `max_freq`/`max_time` and thin the
   surface server-side, keeping the **largest-magnitude value in each block**
   rather than striding, so a one-bin ridge survives. 48 MB → 4 MB. The
   parameters are opt-in, so the standalone tabs are untouched.

Also fixed on the way, because the Explorer is what exposed it: every transform
built its time axis from zero while the time series used the record's own
timestamps, so a windowed STFT said 0–2 s for what the time-series tab called
9–11 s. Invisible while they lived in separate tabs; fatal on a shared axis.
`_absolute_times` puts every surface on the record's clock.

Still open: the transform selector re-fetches rather than caching the surfaces,
so flipping STFT → CWT → STFT recomputes the first one. Cheap for STFT, less so
for CWT.

### 3.3 New DSP — in `dspkit`, not this app
- ~~**Synchrosqueezing / reassignment**~~ — **done 2026-08-07**, see below.
- Multitaper spectrogram
- Stockwell (S) transform
- **Second-order synchrosqueezing.** First-order is biased for strongly
  chirping components: the IF estimate lags a fast chirp. Second-order fixes
  it and is the natural follow-up now the machinery exists.
- **The FSST inverse.** Coefficients are summed as complex numbers precisely so
  an inverse stays possible, but it is not written. That is what mode
  extraction needs — integrate one ridge back into a time-domain signal, and
  you can take damping off a single isolated mode or follow one that drifts.
  This is the highest-value item left in `dspkit`.

**Synchrosqueezing (FSST) — done 2026-08-07.** `dspkit.synchrosqueeze_stft`,
pushed to `LuigiCaglio/DSPkit@e6a037d`. Fifth transform in the Explorer, sitting
next to STFT so flipping between them on one colour scale shows exactly what
reassignment buys.

A spectrogram smears a pure tone to the window's bandwidth; no `nperseg`
escapes that. But the phase still knows the true instantaneous frequency, so
the energy can be moved where it belongs. On a synthetic 100 Hz tone, 90 % of
the energy lands in **1 bin against the STFT's 14**. On `test_2dof.csv` the
10 Hz ridge goes from **4 Hz wide to a single bin** — the 25 Hz mode is already
at the bin spacing for `nperseg=512`, so there is nothing left to sharpen there.

Three things had to be right, each found by measuring rather than by reading:
- scipy's `scaling='spectrum'` divides by `window.sum()`, and a symmetric
  window's *derivative* sums to zero — that normalisation divides `S_dg` by
  ~1e-16 and destroys the ratio the method rests on. The framing is done by
  hand instead.
- No boundary zero-padding. Padding invents a step discontinuity, which is
  broadband, so the phase derivative across it is meaningless: the padded edge
  frames came out **64× larger** than the real ridge. Frames now lie wholly
  inside the signal, so FSST's `times` starts half a window in, not at zero.
- The FFT is referenced to the window **centre**, a factor `(-1)**j`. It leaves
  the IF untouched (the factor cancels in `S_dg/S_g`) but squeezing sums
  *complex* coefficients, and bins straddling a ridge only reinforce when
  referenced to a common instant. Referenced to the frame start they cancelled,
  and `|Tx|` swung **30×** with the tone's phase against the hop. A test written
  about boundaries is what caught it.

It sharpens; it does not create resolution. Components closer than the window
bandwidth merge into one confident-looking ridge, which is arguably worse than
a blurry one. Both caveats are in the docstring.

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

## 5. Response spectrum

Not started. Decided 2026-08-07 that it **does** belong in `dspkit`: the
"is this signal processing?" objection was already moot — `fdd.py`,
`indicators.py` and `multisensor.py` are structural dynamics, and FDD's own
docstrings talk about fitting the SDOF bell. A response spectrum is closer to
the core of that than FDD is.

### 5.1 The transform, in `dspkit`
For a base-excitation record, the peak response of a family of SDOF oscillators
against period T, at one or more damping ratios.

**Use Nigam–Jennings, not Newmark.** The exact piecewise-linear recurrence is a
2x2 state transition that is *exact* when the input is linearly interpolated
between samples, which is the standard assumption anyway. It drops into
`scipy.signal.lfilter` as an IIR filter, so 200 periods over a 20 000-sample
record is milliseconds rather than a loop worth optimising later.

Sensible home: a new `response.py` holding SDOF simulation generally, since the
same machinery gives the shock response spectrum (SRS) used in mechanical and
aerospace testing — same solver, different conventions (maximax / primary /
residual).

**The correctness trap, and it is the same one this file keeps hitting.**
Pseudo-velocity and pseudo-acceleration are *defined* as `Sv = w*Sd` and
`Sa = w^2*Sd`. They are **not** the oscillator's peak velocity and peak
acceleration. They are close for light damping and diverge as damping rises, so
labelling a pseudo-spectrum "acceleration" is exactly the class of error §2.1
and §2.3 were about: stating something that has not been earned. Either name
them pseudo, or return both and let the difference be visible.

Second, smaller: the recurrence is exact for the *interpolated* input, but the
interpolation itself is the approximation. It breaks down at short periods on a
coarsely sampled record — the usual guidance is `dt < T/10`. Refuse or warn
below that rather than draw a confident wrong curve, the way `_detect_time_col`
already refuses a rate it cannot justify.

### 5.2 The tab, in this app
A good fit for the by-eye argument: damping ratio and period range are exactly
the parameters you cannot pick from a formula, and the standard plot is several
damping curves overlaid — which is a comparison, so it belongs on one axis with
one scale for the same reason the Explorer exists.

Worth having: log-log axes, the classic tripartite (four-coordinate) grid, and
per-channel units flowing in as they now do everywhere else — `Sd` is in the
channel's unit integrated twice, which the unit algebra does not yet express.

## Done since this file was written

- **Synchrosqueezing in `dspkit`, wired in as the Explorer's fifth transform**
  (2026-08-07) — §3.3 above.
- **`dspkit` is now an editable install** in `venv_dspkit` (2026-08-07). It was
  a *copy* under `site-packages`, so edits to the source repo silently did not
  reach the app. `pip install -e ../DSPkit`; `pytest` added to the venv too.
- **The Time-Frequency Explorer** (2026-08-07) — §3.2 above, including the
  surface-decimation and shared-clock fixes it forced.
- **Per-channel units** (2026-08-07) — §2.2 above.
- **Reopening a session lost its time column** (2026-08-07). Found by driving
  the app headlessly while checking units, not by any test: `_reopen` read the
  time column as `ui.get("timeCol", -1)`, so a session whose state blob had
  never been written — closed inside the 700 ms save debounce — came back with
  **no time column at all**. The time axis reappeared as a selectable signal and
  the sample rate silently went manual. It now falls back to what detection
  found, exactly as `create` does, while an explicit `-1` ("this file has no
  time column") is still honoured. `test_persistence.py` covers both directions.

  This is the third bug in a row that only browser driving caught, after the
  hardcoded port 8000 and the mount-order Recent files fetch. The pattern is
  consistent: they all live in the seam between two code paths that unit tests
  exercise separately.

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
3. Whether the sidebar is crowded now that Recent files sits in it — and now
   that each channel row can carry a unit box. The box is deliberately
   borderless until hovered, but nobody has looked at the result.
4. **Whether a unit actually reads well on a rendered axis.** The strings are
   asserted (`plotunits.test.mjs`), and the units reaching the *page* is
   confirmed — a session restored with units auto-opened the unit inputs on the
   right four channels. But see the Plotly caveat below.
5. **The Explorer's proportions.** It renders correctly — three linked subplots
   (`xy` surface, `xy2` time series, `x2y` PSD), the resolution readout live,
   the colourbar in dB. Whether the surface gets enough of the height, and
   whether the fourth panel appearing on a click is jarring, needs eyes.
6. **The Explorer on WVD.** The data path is verified by request (capped,
   decimated, on the right clock), but the *render* has only been seen for
   STFT — switching transform needs a click, which `--dump-dom` cannot do.

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
- **Plotly axis titles never appear in the dump**, even with a 30 s virtual-time
  budget and a real window size. Tick labels, legends and trace paths all
  serialise fine; `<text class="xtitle">` simply is not there. Checked against
  `Frequency [Hz]`, which predates any of this work — so absence proves nothing
  about a label, and axis text has to be verified another way.
- To see those, read the wire instead: wrap the app in a tiny ASGI shim that
  logs each `/api/` request line and form body, and run
  `uvicorn probe:app` against it. The request the app sends is the ground truth
  for what got restored, and it needs no changes to the app itself.

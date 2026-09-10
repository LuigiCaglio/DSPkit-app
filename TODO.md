# DSPkit-app — what's left

State as of **2026-09-10**, at **v0.5.0**. Public, MIT, with a Zenodo DOI.

Run the tests with `python tests/run_all.py` — no third-party packages needed.
The library has its own suite (`pytest tests/` in the DSPkit repo, 306 passing)
and its own `TODO.md` for anything algorithmic.

## Direction — read before proposing work

**No SHM-framed features for now.** Decided 2026-09-10. Damage detection,
baseline-versus-current comparison, condition monitoring and anything else that
frames the app as a structural-health tool are off the list until further
notice. This is a scope decision, not a technical one — the pieces exist and
some of them work; they are simply not what this app is for at the moment.

What that rules out concretely: motivating a feature by "you could compare a
healthy and a damaged record", building baseline distributions for the
Mahalanobis view, and anything under `indicators` growing a reference dataset.
Those analyses stay as they are — single-record, descriptive, no baseline.

What it does *not* rule out: general multi-dataset support, which is built and
described in §9. Comparing two files is an ordinary thing to want and stands on
its own; it just should not be designed around, or sold as, a damage-detection
workflow.

## Where to pick up

Nothing here blocks day-to-day use. In rough order of value:

1. **§8.2, the bundled example file.** It reports 39% of a displacement as
   unexplainable when the true answer is zero, at the default settings, on the
   tab that ships with it. The library fix is `../DSPkit/TODO.md` §7.1; a longer
   example record is the app-side half.
2. **Verify the new tabs in a browser.** FRF, Random decrement, the Blackman-
   Tukey panel and the Envelope spectrum were all built and checked through the
   API, but only partly seen rendered. Two reactivity bugs this session got past
   a clean build *and* passing tests, because neither exercises a mounted
   component — see §3.7.
3. **§3.7, the untested surface.** Anything needing a rendered DOM: drag
   resizing, plot scroll behaviour, parameter persistence across tab switches,
   whether auto-run fires on mount, and now the newer control panels.
4. **§1.1, file formats.** Still CSV/TSV/TXT. Deliberately closed for your own
   use; reopens the moment someone else's `.mat` or `.tdms` arrives.
5. **§3.6, time-resolved mutual information.** App-side windowing over the
   existing library call; watch the estimator bias as windows shorten.
6. **Bundle size.** 5 MB, nearly all Plotly. Fine over localhost, not fine if
   this is ever served remotely.

### Known rough edges

- The envelope tab's "most impulsive band" suggestion picked 0-42 Hz on a test
  whose true answer was 200-400 Hz. It is a suggestion, not a default, so it
  does no harm — but do not trust it blindly, and it is worth refining.
- `docs/dev/` is gitignored: development notes stay local and are not published.

### One thing to know when working on this

A frontend change needs a browser reload; a **backend change needs the app
restarted**, because Python loads its module once at startup. A stale backend
shows as a 404, which the app now explains rather than reporting "Not Found" —
but it will still catch you out.

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
*Now tracked in `../DSPkit/TODO.md` §3. Kept here for the FSST summary below.*
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

## 3.4b Row-oriented files with row labels are rejected

Found 2026-09-02. Orientation detection handles rows correctly when the data is
bare numbers (3 x 2000 detected as `rows`), but a row-oriented file that names
each row -- `t,0.0,0.002,...` / `acc1,...` -- fails outright with "No numeric
data found in file".

`autodetect` (`backend/main.py`) looks for the first row that parses as *fully*
numeric. Every row here starts with a label, so no row qualifies and it gives
up before orientation is ever considered. `parse_file` then never gets a chance.

A leading label per row is the row-orientation equivalent of a header row, and
is common in exported data, so this is worth handling: if no row is fully
numeric, retry ignoring the first field of each row, and use those first fields
as the channel names. The user can still override in File layout, but they have
to get past the load error first, and right now they cannot.

---

## 3.5 Zoom on a small-multiples grid — done 2026-09-02

Grid cells rendered `<PlotCanvas>` with no `onRelayout`, and `zoomable` was
`ZOOMABLE.has(tab) && !!single` — null for a grid — so a zoom was never captured
and died on the next spec recompute. Reported on Decomposition > Instantaneous
with the channel scope set to All.

Cells now wire a handler and `zoomable` covers the grid. Zoom is **linked across
cells by default**: they are the same record on a common time axis, so
independent windows break the comparison the grid exists for. A "Linked zoom"
toggle in the toolbar gives per-cell ranges instead, and a Reset appears once
anything is zoomed.

Confirmed by hand 2026-09-02 on Decomposition > Instantaneous with the channel
scope set to All: linked zoom moves every cell together, unlinked moves only the
cell dragged, and Reset restores the full record.

---

## 3.6 Mutual information: two extensions worth having

The Cross-Signal tab computes MI for a pair, optionally scanned over lag, with a
surrogate null. Two things it deliberately does not do.

### Time-resolved MI
MI is currently one number per lag, global over the whole record — the same
scope as coherence. Computing it on overlapping windows would give MI against
*time*, which is a different axis from the lag scan and shows a relationship
appearing or breaking during a record. That is the same shape as the SHM
indicators tab, and each window is shorter so the per-window cost is lower.
App-side work: it windows the existing `dspkit.mutual_information`, no new
library function needed.

Watch the bias. The KSG estimator's floor rises as the sample count falls, so a
short window reads higher than a long one for reasons that have nothing to do
with the data. Either hold the window length fixed and say so, or show the
per-window null alongside — a curve that drifts up as windows shorten would
otherwise look like a strengthening relationship.

### Conditional MI
`I(X;Y|Z)` is the MI analogue of partial coherence, and multivariate MI
generalises multiple coherence. Not possible yet: `../DSPkit/TODO.md` §6 defers
conditional MI in the library, and it is genuinely harder — k-nearest-neighbour
estimators degrade quickly with dimension, so conditioning on several channels
needs far more samples before the number means anything. Library first, app
after.

---

## 3.7 The untested surface

`tests/run_all.py` covers the API, persistence, detection, FDD and the chart
builders, and none of it mounts a component. Two bugs this session went through
a clean build and a green suite:

- `PlotPanel` created its Plotly div in `onMount` with an empty trace list.
  Svelte 5 runs `$effect` before `onMount`, so the draw effect rendered the data
  and `onMount` then wiped it. The request succeeded, the chart was blank.
- `FrfControls` had an effect that both read and assigned `output`. Svelte 5
  treats that as an update loop and throws, so the tab either crashed or left
  Run permanently disabled.

Both are the same shape: reactive wiring that only fails once mounted. Either
add a DOM test runner, or accept that this class of bug is found by hand and
check the tabs after touching `PlotPanel` or any control.

Still uncovered: drag-resizing, plot-area scrolling, parameter persistence
across tab switches, whether auto-run fires on mount, and the newer control
panels (FRF, Random decrement, Envelope, Response spectrum).

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

The **algorithm** now lives in `../DSPkit/TODO.md` §2, along with the two things
that would be got wrong by default (pseudo- vs true velocity and acceleration,
and the `dt < T/10` limit). Decided 2026-08-07 that it belongs in `dspkit`: the
"is this signal processing?" objection was already moot, since `fdd.py` and
`indicators.py` are structural dynamics and FDD fits SDOF bells.

What belongs *here* is the tab. It is a good fit for the by-eye argument —
damping ratio and period range are exactly the parameters you cannot pick from
a formula, and the standard plot is several damping curves overlaid, which is a
comparison and so belongs on one axis with one scale for the same reason the
Explorer does.

Worth having: log-log axes, the classic tripartite (four-coordinate) grid, and
per-channel units flowing in as they now do everywhere else. Note `Sd` is the
channel's unit integrated twice, which `units.js` does not currently express —
it can square and divide, but not integrate.

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

**Updated 2026-09-10: the app has now been looked at.** Headless Chromium via
Playwright renders it fully and screenshots it, which makes everything below
about `--dump-dom` a fallback rather than the state of the art. The recipe, from
a throwaway venv so nothing here gains a dependency:

```
python -m venv <shortpath>/pwenv          # NOT under a deep temp path: without
<shortpath>/pwenv/Scripts/python -m pip install playwright    # Windows long-path
<shortpath>/pwenv/Scripts/python -m playwright install chromium   # support, the
                                          # sync API silently fails to unpack —
                                          # `playwright.async_api` still works
```

Then drive it with `async_playwright`, `page.goto`, `set_input_files` on the
real upload input, `get_by_text` for the tab groups (they nest: `Multi-Ch` then
`Coherence (conditioned)`), and `page.screenshot`. Listen on `console` and
`pageerror` — that is what caught §8.3, a race no assertion in either suite
could see. Plotly renders properly in the screenshot, titles and all, which the
`--dump-dom` route could never show.

Seen and fine as of that date: the Overview tab with all three plots, the
sidebar with channels and preprocessing, the Multi-Ch tab group, and the
control strip on Coherence (conditioned). Layout holds at 1600×1000. Nobody has
looked at the app at a narrow window, and items 1, 2, 5 and 6 below are still
open — they need judgement or a click sequence nobody has written yet.

The Chrome extension has never connected in this environment.

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
3. ~~Whether the sidebar is crowded now that Recent files sits in it.~~ Looked
   at 2026-09-10: it reads fine at 1600×1000 — Recent files, the detected-format
   note, sample counts, channels and preprocessing all fit without scrolling.
   The unit box was not exercised, since the example file declares no units.
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

---

## 8. Error spectrum on the Predictability tab — done 2026-09-10

A third mode on the existing tab rather than a new one: pick a target channel,
the rest of the selection become predictors, and the plot shows the target's
own spectrum against the part of it no linear model can reproduce. Library side
is `dspkit.frf.error_spectrum` — see `../DSPkit/TODO.md` §7.

Touched: `coherence_conditioned` in `main.py` (a `mode="error"` branch and a
`target_col` field), `PredictabilityControls.svelte`, the `predictability`
branch of `plotSpec.js`, a facts-and-caveats block in `PlotPanel.svelte`, and
two new test files. 98 API checks and 185 frontend tests pass.

### 8.1 The library is now installed editable — read this first

`venv_dspkit` held a **copy** of dspkit dated 2026-09-02, so library changes
never reached the app. It is now `pip install -e ../DSPkit`, which is what made
this work at all. Consequences worth knowing:

- Editing the library changes the app on the next **backend restart**. No
  reinstall step any more.
- A library edit can now break the app without anything in this repo changing.
- If the app is ever moved or shipped without `../DSPkit` next to it, the
  editable link dangles. Reinstall from the real package there.

### 8.2 The bundled example is a live demonstration of a real defect

`test_2dof.csv` is a 2DOF chain driven by `force1` and `force2`, so predicting
`x1_disp` from both is a case where the true unexplained share is **zero**. It
does not come out that way. The modes sit at 8.6 and 20.8 Hz with about 4.6%
damping, so the sharpest half-power bandwidth is near 0.8 Hz, while the default
nperseg of 1024 at fs = 1024 resolves about 1.5 Hz — roughly eight times coarser
than the classical `Be/Br <= 1/4` criterion.

| nperseg | Be/Br | reported unexplained | true |
|---|---|---|---|
| 1024 (default) | 1.88 | 38.9% | 0 |
| 4096 | 0.47 | 9.0% | 0 |
| 8192 | 0.24 | 1.4% | 0 |

Worse, at the default the **wrong model wins**: `x2_disp` alone reports 8.3%
against the true inputs' 38.9%, and the ordering only rights itself at 8192
(1.4% against 5.8%). A user comparing sensor sets at the default would draw the
opposite of the correct conclusion.

This is `../DSPkit/TODO.md` §7.1 — the library's Welch guardrail only ever
advises *shortening* nperseg — showing up on our own example data. The panel
now warns in both directions and the `?` help carries the numbers above, but
that is documentation covering for a library defect. Fix §7.1.

The record is only 20 s, so resolving the modes costs nearly all the averages
and the bias floor hits 0.5 at 8192. Both errors cannot be made small on this
file; a longer example record would be the real fix, and would make a better
demo besides.

### 8.3 The auto-run race, and why the browser check caught it

The first version auto-ran from `onMount`. The target channel is set by an
`$effect`, which had not run yet, so a **restored session** that came back
already in error mode posted `target_col: null` and the API refused it. Clean
build, all tests passing, invisible — exactly the §3.7 blind spot: nothing in
either suite mounts a component.

It now gates on a `ready` derived value instead of on mount, so the run fires
when the target resolves and the button stays disabled until then. Verified by
reloading the app cold against a restored session: no console errors, no 422.

Worth repeating the lesson rather than the fix: **the screenshot is the test**
for anything with a lifecycle. This is the third reactivity bug in this repo to
pass a green suite.

### 8.4 Left open

- **A longer example file**, per §8.2. The current one cannot demonstrate the
  tab honestly at any single nperseg.
- **A resolution-bandwidth hint in the panel.** The backend knows fs and could
  ask `peaks.peak_bandwidth` for the sharpest peak, then say "your resolution is
  1.5 Hz and the narrowest peak is 0.8 Hz wide" instead of explaining the
  principle in the abstract. Blocked on nothing but §7.1 landing first, so the
  rule lives in one place.
- **Not verified in a browser:** the target dropdown's behaviour when the
  selection changes while a run is in flight, and the tab's parameter
  persistence across a switch away and back.

---

## 9. Comparing two datasets — done 2026-09-10

Pin a second file as a reference and every comparable analysis runs against
both, on one chart. Per the Direction note at the top, this is a general
capability and is not framed as a damage-detection workflow.

Touched: `_reopen`/`session_get` in `main.py` (a `touch` flag), `App.svelte`
(the reference, the column mapping, `runComparison`), `FileUpload.svelte` (a
pin control per recent entry), `plotSpec.js` (`buildComparison`),
`analyses.js` (`COMPARABLE`), `PlotPanel.svelte` (routing and per-dataset
failures), plus `app.css`. Two new test files; 98 API, 46 persistence and 195
frontend checks pass.

### 9.1 The backend was already multi-session

This was the surprise, and it is why the feature was cheap:

| | |
|---|---|
| `_SESSIONS` | parsed arrays in RAM, `_MAX_SESSIONS = 4` |
| session records on disk | `_MAX_RECENT = 12`, pruned oldest-first |
| every analysis endpoint | already takes `session_id` |

So the only backend change needed was the `touch` flag below. Two datasets are
held and analysed concurrently with **no new endpoint**: the same request is
sent twice with the session-scoped fields swapped. `buildFormData` grew an
`override` argument for exactly those five fields, and nothing else moved.

Eviction is not a correctness problem — `get_session` rehydrates from disk —
so a pinned reference that falls out of RAM costs a reparse, not an error. It
was left that way rather than adding pinning to `_evict_ram`, since four slots
comfortably holds two datasets.

### 9.2 Pinning is not opening — the one real backend bug

`GET /api/session/{id}` calls `_reopen`, which calls `_touch_session`, which
stamps `opened_at`. Recents are ordered by that field and **the app reopens the
top entry on launch**. So reading a session to compare against silently made it
the file that came back next time, in place of the one actually being worked
on. `?touch=false` fixes it; `test_persistence.py` pins both directions, since
the default must keep promoting or the restore path breaks instead.

### 9.3 Channels are matched by name, and it refuses rather than guesses

Column *order* agreeing between two files is a coincidence. Comparing `acc1`
against a differently-ordered `acc3` would produce a chart that looks right and
means nothing, so a missing name is reported, never patched. It is checked
twice: at pin time, so the reason is visible when the decision is made, and at
run time, because the channel selection can change afterwards.

Sample rates differing is **not** refused. A spectrum is in Hz either way and
the comparison is still meaningful — it is just no longer like for like at a
given nperseg, since the resolution and the Nyquist both move. That is a
caveat in the banner, not a block. Record lengths differing by more than 25%
gets the same treatment, because it changes the number of averages.

### 9.4 Dash for the dataset, colour for the channel

`buildComparison` has **no per-tab knowledge**: it builds each dataset with the
ordinary `buildPlot` and merges the traces, so every axis title, log scale and
unit the tab already gets right stays right, and a new tab becomes comparable
by being named in `COMPARABLE`. Same trick `runFanout` uses on the request side.

Datasets are told apart by dash. Colour is already spent on the channel, and
matching `acc1` here to `acc1` there is the pairing the chart exists to show —
recolouring by dataset destroys it. There is a test that says so.

`COMPARABLE` deliberately excludes the surfaces (two heatmaps cannot share one
pair of axes), the explorer, the grid, and raw time series — two records are
almost never aligned in time, so an overlay would imply a correspondence that
is not there. `buildComparison` also has a backstop: if any trace is not a
line, it draws the active dataset alone rather than nonsense.

### 9.5 Left open

- **More than two datasets.** The merge already loops, but the channel-mapping
  problem multiplies and the chart stops being readable. Two is where nearly
  all the value is.
- **Per-dataset preprocessing.** The active preprocessing is applied to both,
  which is right for a comparison — comparing a filtered record against an
  unfiltered one compares the filter — but it means a reference cannot carry
  its own trim window.
- **Comparing the dynamic-scope tabs** (`csd`, `coherence`, `cross_correlation`
  in their pair-overlay form). Those produce `{overlay: {...}}` rather than a
  plain result, so they need a merge of a different shape.
- **A difference view.** Two curves invite a third: ratio or dB difference
  against the reference. Cheap now that both results are in hand, and probably
  the next thing worth doing here.
- **Not verified in a browser:** changing the channel selection while a
  comparison is pinned, and whether the reference survives a session restore
  (it is deliberately *not* persisted in UI state, so it should not).

---

## 10. Performance — measured and fixed 2026-09-10

Measured on a synthetic 20 kHz × 60 s file: 1.2M samples, 3 channels, 44 MB of
CSV. Everything below is from that record against a local backend.

### 10.1 What changed

`decimate_xy` in `main.py` thins a series to a point budget before it is
serialised, and `downsampleXY` in `plotSpec.js` was rewritten to match. Three
endpoints take `max_points` (`timeseries`, `fft`, `autocorrelation`), the time
series also takes `include_raw` and a `view_start`/`view_end` window, and the
CSV export re-fetches with `max_points=0`.

| response | before | after |
|---|---|---|
| timeseries | 95.0 MB / 8.4 s | **1.85 MB / 0.25 s** |
| timeseries, resampled to 1 kHz | 52.4 MB / 4.7 s | **2.61 MB / 0.36 s** |
| fft | 89.0 MB / 5.9 s | **3.51 MB / 0.75 s** |
| autocorrelation | 99.5 MB / 6.3 s | **1.95 MB / 0.58 s** |

25x to 50x smaller, 8x to 34x faster. PSD was already 0.18 MB and is untouched:
its output is a spectrum at the chosen `nperseg` rather than something O(N),
which is why it was the odd one out in the first place.

### 10.2 Min and max per bin, never a stride — this was a correctness bug

The old `downsampleXY` took every k-th sample, which *deletes* whatever falls
between the samples it keeps. On the three-tone test file, thinning the 600,001
bin spectrum down to ~23,700:

| channel | true peak | min/max keeps | stride keeps |
|---|---|---|---|
| ch1 @ 137 Hz | 0.99966 | 0.99966 | 0.00227 |
| ch2 @ 419 Hz | 0.99997 | 0.99997 | 0.00238 |
| ch3 @ 1103 Hz | 0.99985 | 0.99985 | 0.00216 |

Stride loses **99.8% of every peak** — the tones would simply not be on the
chart, with nothing on screen to say so. This was live in the app before today
for any spectrum over 50,000 bins. Both decimators now keep the argmin and the
argmax of each bin, emitted in x order so the line still reads left to right.

Channels share one index set, chosen from the union of what each wants to keep.
Decimating them independently would put them on different x grids, and a chart
drawing two channels against slightly different time bases lies about their
relative timing. The cost is that `max_points` is a budget *per channel*: three
noise channels at a budget of 8000 came back as 23,835 points. Erring large is
the right way to be wrong here.

For the FFT only the **amplitudes** choose the indices, via the `drivers`
argument. Phase extremes are arbitrary and would spend the budget on noise;
phase is then sampled wherever amplitude chose, which also keeps the two
aligned — a phase read off a different bin from its magnitude is worse than
useless.

### 10.3 The response is now a picture, not the data

This is the consequence to remember. **Anything that reads a statistic off one
of these endpoints is now reading the thinned series and will be wrong.** It
caught the detrend check in `test_api.py` immediately: the mean of a min/max
thinned series is not the mean of the signal, because the thinning deliberately
keeps the extremes. That test now passes `max_points: 0`, and any future check
of a *value* rather than a *shape* must do the same.

The CSV export had the same problem and it mattered more: it built its rows
from the drawn arrays, so it would have written a picture of the data as
numbers. It now re-fetches with the thinning off, verified in a browser — the
export of the 1.2M-sample FFT came back with 600,001 rows while ~23,700 were on
screen. It is not cached: an export is rare and can afford a round trip, where
holding the full arrays against the chance of one gives back everything the
thinning bought.

### 10.4 Zoom asks the server now

Thinning up front would have made zooming useless — magnifying a thinned curve
just shows bigger steps — so `view_start`/`view_end` restrict the budget to the
visible window and `onViewChange` re-fetches, debounced 250 ms, leaving the old
chart up while the request is in flight. A 50 ms window of the 20 kHz record
comes back as 1003 points at the full 5e-5 s sample interval, with `decimated`
false. Verified by dragging in a real browser, not only through the API.

### 10.5 The ghost trace is optional

`include_raw` drops the untouched copy drawn behind the processed trace, with a
"Show original behind" checkbox on the Time series tab. It only ever applied
when preprocessing is on; with no preprocessing the raw arrays *are* the
plotted trace and are always sent.

### 10.6 Left open

- ~~**`filter` and `instantaneous`**~~ — done in §11.3.
- **`cross_correlation`, `csd`, `coherence`** return O(N) arrays too, though
  the last two are usually short. Worth a look.
- **Gzip.** Still not installed, and now much less interesting: at 2-3 MB the
  2-3x it buys costs ~2 s of CPU. Revisit only alongside §6, serving remotely.
- **`MAX_PLOT_POINTS = 50_000` in the frontend** is now a backstop rather than
  the working limit, since the server sends ~8000. Worth lowering to match, but
  it does no harm.
- **Grid and overlay export do not re-fetch**, so they would write thinned rows
  if they ever saw a thinned payload. They cannot today: all three thinned tabs
  are `multi` scope, while the grid path is only reachable from `single` and the
  overlay path only from `dynamic`. That is a coincidence of the scope table,
  not a guarantee — thinning a `single` or `dynamic` endpoint later (see the
  first bullet: `instantaneous` is `single`) makes it a live bug. Give those two
  paths the same re-fetch before thinning anything outside `multi`.

---

## 11. AR spectra, nperseg advice, and the last of the thinning — done 2026-09-10

Closes §10.6's first bullet and surfaces the two library additions from
`../DSPkit/TODO.md` §8. 133 API checks, 46 persistence and 200 frontend tests
pass.

### 11.1 The PSD tab has a second method

`Method: Welch (averaged) | AR model (Burg)`. The AR branch fits an all-pole
model to the whole record instead of averaging segments, so it separates peaks
Welch cannot on a short record. Order 0 means "choose one" by AIC or BIC;
Yule-Walker is available for comparison.

**The order is named in the legend, and that is not decoration.** Two AR curves
at different orders are different claims about the same record and are otherwise
indistinguishable, so each trace reads `x1_disp (AR 95)`. On `test_2dof.csv` the
criterion picks 95 and 97 for the two displacement channels and 1 and 2 for the
white-noise force channels — the right answer in both cases, and a good sanity
check if this ever looks wrong.

The panel says plainly what the method costs: too low an order merges peaks, too
high invents them, notches come out too shallow because an all-pole model
represents resonances exactly and antiresonances only by cancellation, and any
peak only this method shows should be checked against Welch.

### 11.2 "Check nperseg" answers the question in both directions

A button on the Welch branch calls `/api/spectral/segment_advice`, which returns
a verdict and a sentence. On the bundled example at the default it says:

> **Record too short** — This record cannot satisfy both. Resolving the peak at
> 10 Hz needs nperseg>=3745, which leaves 9 segment(s) of the 20480 samples
> available. About 38.4 s of record would give both, against the 20 s you have.

That is §8.2's problem stated by the app instead of by this file. It is a check,
not an analysis, so it returns to the panel rather than touching `plotData` —
running it does not wipe the plot you are comparing against — and the verdict is
cleared whenever a parameter changes, because a stale one is worse than none.

### 11.3 The last two O(N) endpoints are thinned

`filter/apply` and `instantaneous` now take `max_points` like the other three.
For the instantaneous attributes only the signal and its envelope choose the
sample points; phase and instantaneous frequency ride along on the same ones,
since a phase ramp's extremes are its wrap points and an instantaneous frequency
read at a different instant from its signal is meaningless.

### 11.4 Export integrity, now that a `single`-scope tab is thinned

§10.6 flagged that grid and overlay export do not re-fetch and were safe only
because no thinned tab was reachable from them. `instantaneous` is `single`
scope, so thinning it made that live. Both paths are handled:

- **Grid export** re-runs the fan-out with `max_points=0`, one call per channel.
- **Overlay export** cannot re-fetch yet, so it has a tripwire: if it ever sees
  a thinned response it refuses with an explanation instead of writing a picture
  of the data as numbers. No overlay tab is thinned today, so it never fires.

### 11.5 Left open

- **`cross_correlation`, `csd`, `coherence`** still return everything. They are
  usually short, and thinning them means giving the overlay export a re-fetch
  first (§11.4) — do them together.
- **The AR tab has no order sweep.** Choosing an order by eye means running it
  several times. A small multiples view over a few orders would answer the
  "is this peak real" question directly.
- **Not verified in a browser:** the AR tab on a long record, and the grid
  export re-fetch.

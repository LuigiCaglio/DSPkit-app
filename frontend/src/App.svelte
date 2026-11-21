<script>
  import DspkitLogo        from './lib/DspkitLogo.svelte'
  import AboutDialog       from './lib/AboutDialog.svelte'
  import FileUpload        from './lib/FileUpload.svelte'
  import AnalysisPanel     from './lib/AnalysisPanel.svelte'
  import PlotPanel         from './lib/PlotPanel.svelte'
  import PreprocessPanel   from './lib/PreprocessPanel.svelte'
  import RightSidebar      from './lib/RightSidebar.svelte'
  import ChannelSelect     from './lib/ChannelSelect.svelte'
  import { ALL_CHANNELS, isComparable } from './lib/analyses.js'
  import { exportParams, importParams, resetParams } from './lib/paramStore.svelte.js'
  import { applyState, buildState, debounce, defaultPreproc } from './lib/sessionState.js'
  import { describeRejection, impliedFs } from './lib/detect.js'
  import { resolveUnits, sanitizeUnits } from './lib/units.js'
  import { costPlan, surfaceOf, transformById, surfaceLimits } from './lib/explorer.js'

  // ── session ────────────────────────────────────────────────────────────────
  // The file is uploaded and parsed once; every analysis call then refers to it
  // by session_id rather than re-sending the whole file.
  let file        = $state(null)
  let session     = $state(null)   // response from /api/session/create
  let parseError  = $state(null)
  let parsing     = $state(false)
  let sourcePath  = $state(null)   // where the file lives, when it was opened by path
  let restored    = $state(false)  // this session came back with its settings

  // Suppresses the save effect while a restore is being applied, so the blob
  // being read isn't immediately overwritten by the defaults it replaces.
  let restoring   = $state(false)

  // ── layout (auto-detected, user-overridable) ───────────────────────────────
  let orientation = $state('columns')
  let headerRow   = $state(-1)
  let timeCol     = $state(-1)
  let fsManual    = $state(1000)
  let layoutOpen  = $state(false)   // the override panel stays shut unless needed
  let aboutOpen   = $state(false)

  let isMat = $derived(session?.detected?.format === 'mat')
  const MAT_ROLES = { data: 'Data', fs: 'Sample rate', channel_names: 'Channel names', t0: 'Start time' }

  // ── channel selection ──────────────────────────────────────────────────────
  // signalCols is the single source of truth. focusChannel and pairX/pairY are
  // views onto it for analyses that take fewer channels than are selected; they
  // are surfaced in the controls strip next to the plot, never only in a
  // sidebar, so a result always states which channel it came from.
  let signalCols   = $state([])
  let focusChannel = $state(0)             // index, or ALL_CHANNELS for a grid
  let pairX        = $state(0)
  let pairY        = $state(1)
  // Declared physical unit per column index. Display only — nothing is
  // converted, because the numbers in the file are already in whatever the
  // user says they are in.
  let channelUnits = $state({})

  // ── preprocessing state ────────────────────────────────────────────────────
  let preproc = $state(defaultPreproc())

  // ── preview expand ─────────────────────────────────────────────────────────
  let previewExpanded = $state(false)
  const PREVIEW_DEFAULT = 5

  // ── navigation state ───────────────────────────────────────────────────────
  let activeCategory = $state('inspect')
  let activeTab = $state('timeseries')
  let plotData  = $state(null)
  let plotError = $state(null)
  let loading   = $state(false)

  // ── FDD: singular vectors at frequencies the user picks ───────────────────
  // Kept apart from plotData so asking for a shape never replaces the plot the
  // frequency was picked off.
  let fddPicks   = $state([])      // frequencies [Hz], in the order chosen
  let fddVectors = $state(null)    // response from /api/fdd/vectors
  let fddNVec    = $state(1)
  let fddBusy    = $state(false)
  let fddError   = $state(null)

  // A new file or a different analysis makes the old picks meaningless.
  $effect(() => { const _ = session, __ = activeTab; fddPicks = []; fddVectors = null; fddError = null })

  function fddPick(freq) {
    if (freq == null) return
    // Clicking the same peak twice should not queue it twice; a bin's width is
    // the natural tolerance for "the same frequency".
    const tol = fddVectors?.df ?? 0.5
    if (fddPicks.some(f => Math.abs(f - freq) < tol)) return
    fddPicks = [...fddPicks, freq].sort((a, b) => a - b)
  }
  const fddUnpick = (i) => { fddPicks = fddPicks.filter((_, j) => j !== i) }
  const fddClear  = () => { fddPicks = []; fddVectors = null; fddError = null }

  async function runFddVectors() {
    if (!session || fddPicks.length === 0) return
    fddBusy = true
    fddError = null
    const { data, error } = await post('/api/fdd/vectors', {
      freqs_wanted: JSON.stringify(fddPicks),
      n_vectors: fddNVec,
    })
    if (error) { fddError = error; fddVectors = null }
    else fddVectors = data
    fddBusy = false
  }

  // ── right sidebar ──────────────────────────────────────────────────────────
  let rightOpen = $state(false)

  // ── category → sub-tabs mapping ────────────────────────────────────────────
  const CATEGORIES = [
    { id: 'overview',      label: 'Overview',      tabs: [
      { id: 'overview', label: 'Overview' },
    ]},
    { id: 'inspect',       label: 'Inspect',       tabs: [
      { id: 'timeseries', label: 'Time series' },
      { id: 'datatable', label: 'Data table' },
    ]},
    { id: 'spectral',      label: 'Spectral',      tabs: [
      { id: 'fft', label: 'FFT' }, { id: 'psd', label: 'PSD' },
      { id: 'peaks', label: 'Peaks' }, { id: 'autocorrelation', label: 'Autocorrelation' },
    ]},
    { id: 'crossSignal',   label: 'Cross-Signal',  tabs: [
      { id: 'cross_correlation', label: 'Cross-corr' },
      { id: 'csd', label: 'CSD' },
      { id: 'coherence', label: 'Coherence' },
      { id: 'mutual_info', label: 'Mutual information' },
      { id: 'frf', label: 'FRF' },
    ]},
    { id: 'filtering',     label: 'Filtering',     tabs: [{ id: 'filter', label: 'Filter' }] },
    { id: 'timeFreq',      label: 'Time-Freq',     tabs: [
      { id: 'explorer', label: 'Explorer' },
      { id: 'stft', label: 'STFT' }, { id: 'cwt', label: 'CWT' },
      { id: 'wvd', label: 'WVD' }, { id: 'spwvd', label: 'SPWVD' },
    ]},
    { id: 'decomposition', label: 'Decomposition', tabs: [
      { id: 'instantaneous', label: 'Instantaneous' },
      { id: 'emd', label: 'EMD' }, { id: 'hht', label: 'HHT' },
      { id: 'envelope', label: 'Envelope spectrum' },
    ]},
    { id: 'multiChannel',  label: 'Multi-Ch',      tabs: [
      { id: 'multisensor', label: 'Multi-Sensor' },
      { id: 'predictability', label: 'Coherence (conditioned)' },
      { id: 'fdd', label: 'FDD' },
    ]},
    { id: 'structural',    label: 'Structural',    tabs: [
      { id: 'response_spectrum', label: 'Response spectrum' },
      { id: 'log_decrement', label: 'Log decrement' },
      { id: 'random_decrement', label: 'Random decrement' },
    ]},
    { id: 'statistics',    label: 'Statistics',     tabs: [
      { id: 'statistics', label: 'Distributions' },
      { id: 'indicators', label: 'SHM Indicators' },
    ]},
  ]

  // ── derived ────────────────────────────────────────────────────────────────
  // A restored or path-opened session has no File object behind it, so "has a
  // file" has to mean the session, not the upload that may never have happened.
  let hasFile     = $derived(file !== null || session !== null)
  let hasParsed   = $derived(session !== null)
  let nSignals    = $derived(session ? session.n_columns : 0)
  let effectiveFs = $derived(session?.fs ?? fsManual)
  let columnNames = $derived(session?.column_names ?? [])

  // "Dual" now means two channels are actually *selected*, not merely present —
  // a pairwise analysis needs two things to pair.
  let dualSignal  = $derived(signalCols.length >= 2)

  const channelName = (i) => columnNames[i] ?? `Ch ${i}`

  // Resolved once here rather than in the charts, so plotSpec never has to know
  // what a column index is. Recomputes when the selection, the focus channel or
  // any declared unit changes.
  let plotUnits = $derived(resolveUnits(
    channelUnits, signalCols, { x: pairX, y: pairY }, columnNames, focusChannel))

  /**
   * What preprocessing every result on screen has been through. A high-pass
   * silently shifts PSD levels, FDD peaks and damping estimates, so this is
   * shown in the plot toolbar next to the result rather than only in the
   * sidebar that set it. The conditions mirror buildPreprocUrl exactly, so the
   * chip states what was actually sent, not what the panel merely has toggled.
   */
  let preprocSummary = $derived.by(() => {
    const bits = []
    if (preproc.windowEnabled) {
      const s = preproc.winStart, e = preproc.winEnd
      const has = (v) => v !== null && v !== undefined && v !== ''
      if (has(s) || has(e)) {
        bits.push(`window ${has(s) ? s : 'start'}–${has(e) ? e : 'end'} ${preproc.winUnit}`)
      }
    }
    if (preproc.detrendEnabled) {
      const DT = ['mean removed', 'linear detrend', 'quadratic detrend', 'cubic detrend']
      bits.push(DT[preproc.detrendOrder] ?? `detrend order ${preproc.detrendOrder}`)
    }
    if (preproc.notchEnabled && preproc.notchFreq) {
      bits.push(`notch ${preproc.notchFreq} Hz (Q ${preproc.notchQ})`)
    }
    if (preproc.hpEnabled && preproc.hpCutoff) {
      bits.push(`high-pass ${preproc.hpCutoff} Hz (order ${preproc.hpOrder})`)
    }
    if (preproc.lpEnabled && preproc.lpCutoff) {
      bits.push(`low-pass ${preproc.lpCutoff} Hz (order ${preproc.lpOrder})`)
    }
    if ((preproc.hpEnabled || preproc.lpEnabled || preproc.notchEnabled) && !preproc.zeroPhase) {
      bits.push('causal')
    }
    if (preproc.calculusEnabled && preproc.calculusOrder) {
      const n = Math.abs(preproc.calculusOrder)
      const verb = preproc.calculusOrder < 0
        ? (n === 1 ? 'integrated' : `integrated ${n}x`)
        : (n === 1 ? 'differentiated' : `differentiated ${n}x`)
      const band = [
        preproc.calculusHp ? `hp ${preproc.calculusHp} Hz` : null,
        preproc.calculusLp ? `lp ${preproc.calculusLp} Hz` : null,
      ].filter(Boolean).join(', ')
      const extras = [band, preproc.calculusTaper
        ? `${(preproc.calculusTaper * 100).toFixed(1)}% edge taper` : null].filter(Boolean).join(', ')
      bits.push(extras ? `${verb} (${extras})` : verb)
    }
    if (preproc.resampleEnabled && preproc.targetFs) {
      const down = preproc.targetFs < (session?.fs ?? fsManual)
      bits.push(`resampled to ${preproc.targetFs} Hz` +
        (down ? ` (anti-alias low-pass ${+(0.4 * preproc.targetFs).toFixed(2)} Hz)` : ''))
    }
    return bits
  })

  /** The pass band currently in force, for shading the rejected parts of a PSD. */
  let filterBand = $derived({
    hp: preproc.hpEnabled && preproc.hpCutoff ? Number(preproc.hpCutoff) : null,
    lp: preproc.lpEnabled && preproc.lpCutoff ? Number(preproc.lpCutoff) : null,
  })

  /**
   * The filter's own magnitude response, to draw over the spectrum.
   *
   * Computed on the backend with the same scipy calls dspkit uses, so it is the
   * filter that actually runs — including the squaring that zero-phase implies.
   * Reimplementing the design in JS would risk drawing a curve that disagrees
   * with the data underneath it.
   */
  let filterResponse = $state(null)

  $effect(() => {
    const on = preproc.hpEnabled || preproc.lpEnabled || preproc.notchEnabled
    const fsNow = effectiveFs
    if (!on || !fsNow) { filterResponse = null; return }

    const fd = new FormData()
    fd.append('fs', String(fsNow))
    if (preproc.hpEnabled && preproc.hpCutoff) {
      fd.append('hp_cutoff', String(preproc.hpCutoff))
      fd.append('hp_order', String(preproc.hpOrder))
    }
    if (preproc.lpEnabled && preproc.lpCutoff) {
      fd.append('lp_cutoff', String(preproc.lpCutoff))
      fd.append('lp_order', String(preproc.lpOrder))
    }
    if (preproc.notchEnabled && preproc.notchFreq) {
      fd.append('notch_freq', String(preproc.notchFreq))
      fd.append('notch_q', String(preproc.notchQ))
    }
    fd.append('zero_phase', String(preproc.zeroPhase))

    let stale = false
    fetch('/api/filter/response', { method: 'POST', body: fd })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (!stale) filterResponse = d?.applied ? d : null })
      .catch(() => { if (!stale) filterResponse = null })
    return () => { stale = true }
  })

  /**
   * Set the filter from a frequency range picked on the PSD.
   *
   * Choosing a cutoff means looking at the spectrum, finding the noise and
   * cutting there — so the cutoff should be settable from the spectrum rather
   * than read off by eye and retyped in another tab. A band-pass is just the
   * high-pass and low-pass together, which is how preprocessing already
   * represents it.
   */
  function setFilterFromRange(kind, lo, hi) {
    const round = (v) => Number(v.toPrecision(4))
    if (kind === 'highpass' || kind === 'bandpass') {
      preproc.hpCutoff = round(Math.max(lo, 0))
      preproc.hpEnabled = true
    }
    if (kind === 'lowpass' || kind === 'bandpass') {
      preproc.lpCutoff = round(hi)
      preproc.lpEnabled = true
    }
    rerunActive()
  }

  function clearFilter() {
    preproc.hpEnabled = false
    preproc.lpEnabled = false
    rerunActive()
  }

  /**
   * Recompute whatever is on screen, so a new cutoff shows immediately.
   *
   * Replays the last request rather than remounting the control to re-fire its
   * auto-run: the remount blanked activeTab for a tick, which downstream reads
   * as a tab change and threw away the band the user had just picked.
   */
  function rerunActive() {
    if (!lastRun) return
    const { kind, endpoint, extra, ref } = lastRun
    if (kind === 'overview')     runOverview()
    else if (kind === 'overlay') runPairOverlay(endpoint, extra, ref)
    else                         runAnalysis(endpoint, extra)
  }

  let currentCategory = $derived(CATEGORIES.find(c => c.id === activeCategory))

  // Keep the derived picks pointing at channels that are still selected.
  $effect(() => {
    const sel = signalCols
    if (sel.length === 0) return
    if (focusChannel !== ALL_CHANNELS && !sel.includes(focusChannel)) focusChannel = sel[0]
    if (!sel.includes(pairX)) pairX = sel[0]
    if (!sel.includes(pairY)) pairY = sel[1] ?? sel[0]
  })

  /** Plain-language summary of what the loader worked out on its own. */
  let detectSummary = $derived.by(() => {
    if (!session?.detected) return null
    const d = session.detected
    const bits = []
    bits.push(d.header_row >= 0 ? `header on row ${d.header_row + 1}` : 'no header row')
    bits.push(d.time_col >= 0 && session.column_names[d.time_col]
      ? `time in "${session.column_names[d.time_col]}"`
      : 'no time column')
    if (session.fs) bits.push(`fs ${session.fs.toFixed(2)} Hz`)
    if (d.orientation === 'rows') bits.push('rows = signals')
    return bits.join(' · ')
  })

  /**
   * Why a time column was refused, when one nearly qualified.
   *
   * Only shown while no time column is in use — once one is picked by hand the
   * explanation is spent. Suppressed for a rejection the user has overridden.
   */
  let detectRejection = $derived.by(() => {
    if (!session?.detected || timeCol >= 0) return null
    return describeRejection(session.detected.time_col_rejected, session.column_names)
  })

  function selectCategory(catId) {
    activeCategory = catId
    const cat = CATEGORIES.find(c => c.id === catId)
    // Every category is reachable with a single channel. The four genuinely
    // between-sensor analyses (multi-sensor, FDD, covariance, Mahalanobis) say
    // so in their own panel rather than presenting a dead disabled tab.
    if (cat && cat.tabs.length > 0) switchTab(cat.tabs[0].id)
    // Overview is a summary, not a form — coming back to it should re-run it.
    if (catId === 'overview') runOverview()
  }

  // ── helpers ────────────────────────────────────────────────────────────────
  function buildFormData(extraFields = {}, override = null) {
    const fd = new FormData()
    // `override` swaps the five fields that identify *which* record is being
    // analysed, leaving everything else — including the preprocessing in the
    // query string — untouched. That is what lets the same request be aimed at
    // a second dataset without duplicating the request builder.
    const base = {
      session_id: session.session_id,
      orientation,
      header_row: String(headerRow),
      time_col: String(timeCol),
      fs: String(effectiveFs),
      signal_cols: JSON.stringify(signalCols.map(Number)),
      ...(override ?? {}),
    }
    for (const [k, v] of Object.entries(base)) fd.append(k, String(v))
    for (const [k, v] of Object.entries(extraFields)) {
      if (v !== null && v !== undefined) fd.append(k, String(v))
    }
    return fd
  }

  function buildPreprocUrl(endpoint) {
    const p = new URLSearchParams()
    if (preproc.windowEnabled) {
      if (preproc.winStart !== null && preproc.winStart !== '') p.set('win_start', preproc.winStart)
      if (preproc.winEnd   !== null && preproc.winEnd   !== '') p.set('win_end',   preproc.winEnd)
      p.set('win_unit', preproc.winUnit)
    }
    if (preproc.detrendEnabled && preproc.detrendOrder !== null) {
      p.set('detrend_order', preproc.detrendOrder)
    }
    if (preproc.hpEnabled && preproc.hpCutoff) {
      p.set('hp_cutoff', preproc.hpCutoff)
      p.set('hp_order', preproc.hpOrder)
    }
    if (preproc.lpEnabled && preproc.lpCutoff) {
      p.set('lp_cutoff', preproc.lpCutoff)
      p.set('lp_order', preproc.lpOrder)
    }
    if (preproc.notchEnabled && preproc.notchFreq) {
      p.set('notch_freq', preproc.notchFreq)
      p.set('notch_q', preproc.notchQ)
    }
    // Only worth sending when a filter is actually on.
    if (preproc.hpEnabled || preproc.lpEnabled || preproc.notchEnabled) {
      p.set('zero_phase', String(preproc.zeroPhase))
    }
    if (preproc.calculusEnabled && preproc.calculusOrder) {
      p.set('calculus_order', preproc.calculusOrder)
      if (preproc.calculusHp) p.set('calculus_hp', preproc.calculusHp)
      if (preproc.calculusLp) p.set('calculus_lp', preproc.calculusLp)
      if (preproc.calculusTaper) p.set('calculus_taper', preproc.calculusTaper)
    }
    if (preproc.resampleEnabled && preproc.targetFs) p.set('target_fs', preproc.targetFs)
    const qs = p.toString()
    return qs ? `${endpoint}?${qs}` : endpoint
  }

  /** Default the signal selection to every non-time column. */
  function applySessionDefaults(names, tCol) {
    const nonTime = names.map((_, i) => i).filter(i => i !== tCol)
    // A different record's units are not this record's; start blank rather than
    // carry the last file's over.
    channelUnits = {}
    signalCols   = nonTime
    focusChannel = nonTime[0] ?? 0
    pairX        = nonTime[0] ?? 0
    pairY        = nonTime[1] ?? pairX
  }

  // ── restore ────────────────────────────────────────────────────────────────
  //
  // Everything below exists so that opening the app, or reopening a file,
  // resumes rather than restarts. The settings are stored per session on the
  // backend, because the channels and cutoffs that suit one record are usually
  // wrong for the next — restoring them globally would be worse than not
  // restoring them at all.

  const saveState = debounce((sid, blob) => {
    fetch(`/api/session/${sid}/state`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(blob),
    }).catch(() => { /* a lost save costs a re-setup, not data */ })
  }, 700)

  $effect(() => {
    if (!session || restoring) return
    const blob = buildState({
      orientation, headerRow, timeCol, fsManual,
      signalCols, focusChannel, pairX, pairY,
      units: channelUnits,
      preproc, activeCategory, activeTab,
      params: exportParams(),
    })
    saveState(session.session_id, blob)
  })

  /**
   * Take on a session response, restoring its saved settings when it has any.
   *
   * The one place session state is adopted, so upload, open-by-path and reopen
   * cannot drift apart. Anything the saved blob doesn't cover — or that no
   * longer fits the file — falls back to the same defaults a fresh load gets.
   */
  function adoptSession(data) {
    restoring = true
    session     = data
    orientation = data.orientation
    headerRow   = data.header_row
    timeCol     = data.time_col
    sourcePath  = data.source_path ?? null
    if (data.fs) {
      fsManual = data.fs
    } else {
      // Detection refused the column, but its median interval is still a far
      // better guess than the hardcoded 1000 Hz — for the single-dropout case
      // it is exactly right. The banner says where this number came from.
      const implied = impliedFs(data.detected?.time_col_rejected)
      if (implied) fsManual = Number(implied.toPrecision(9))
    }

    const saved = applyState(data.ui, {
      nColumns: data.n_columns,
      timeCol: data.time_col,
    })
    restored = saved !== null

    if (saved) {
      signalCols   = saved.signalCols
      channelUnits = saved.units ?? {}
      focusChannel = saved.focusChannel
      pairX        = saved.pairX
      pairY        = saved.pairY
      preproc      = saved.preproc
      if (saved.fsManual) fsManual = saved.fsManual
      resetParams()
      importParams(saved.params)
      activeCategory = saved.activeCategory ?? 'overview'
      activeTab      = saved.activeTab ?? 'overview'
    } else {
      applySessionDefaults(data.column_names, data.time_col)
      preproc = defaultPreproc()
      resetParams()
      activeCategory = 'overview'
      activeTab      = 'overview'
    }
    // Let the assignments settle before the save effect starts watching, or the
    // first run would immediately write back what was just read.
    queueMicrotask(() => { restoring = false })
  }

  /** Shared tail of every load: show the data instead of an empty canvas. */
  async function afterLoad() {
    plotData = null
    plotError = null
    if (activeTab === 'overview') await runOverview()
  }

  /** Upload once; the backend detects layout and hands back a session. */
  async function createSession(f) {
    parsing = true
    parseError = null
    session = null
    const fd = new FormData()
    fd.append('file', f)
    try {
      const res  = await fetch('/api/session/create', { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) { parseError = data.detail; return }
      adoptSession(data)
    } catch (e) {
      parseError = e.message
      return
    } finally {
      parsing = false
    }
    await afterLoad()
  }

  /** Open a file already on this machine — no upload, and settings come back. */
  async function openPath(path) {
    parsing = true
    parseError = null
    const fd = new FormData()
    fd.append('path', path)
    try {
      const res  = await fetch('/api/session/open', { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) { parseError = data.detail; return false }
      file = null
      adoptSession(data)
    } catch (e) {
      parseError = e.message
      return false
    } finally {
      parsing = false
    }
    await afterLoad()
    return true
  }

  /** Reopen a session by id, the way the recent-files list and launch do. */
  async function openSession(sessionId) {
    parsing = true
    parseError = null
    try {
      const res  = await fetch(`/api/session/${sessionId}`)
      const data = await res.json()
      if (!res.ok) { parseError = data.detail; return false }
      file = null
      adoptSession(data)
    } catch (e) {
      parseError = e.message
      return false
    } finally {
      parsing = false
    }
    await afterLoad()
    return true
  }

  /**
   * Decide what to show on launch.
   *
   * A file named on the command line wins — that is an explicit request. Failing
   * that, the last session comes back, which is what makes reopening the app
   * feel like it was never closed. A failure here is silent on purpose: it
   * leaves the normal empty state, which is exactly what the user would have
   * seen before any of this existed.
   */
  async function resumeOnLaunch() {
    try {
      const res = await fetch('/api/launch-target')
      const { path } = await res.json()
      if (path && await openPath(path)) return
    } catch { /* fall through to the last session */ }

    try {
      const res = await fetch('/api/session/recent')
      const { recent } = await res.json()
      const last = (recent ?? []).find(r => r.available)
      if (last) await openSession(last.session_id)
    } catch { /* leave the empty state */ }
  }

  resumeOnLaunch()

  /** Go back to the file picker without dropping the session on the backend. */
  function closeSession() {
    saveState.cancel()
    file = null
    session = null
    sourcePath = null
    restored = false
    plotData = null
    plotError = null
    parseError = null
    resetParams()
  }

  /** Re-read the cached file with a layout the user changed by hand. */
  async function reparse() {
    if (!session) return
    parsing = true
    parseError = null
    const fd = new FormData()
    fd.append('session_id', session.session_id)
    fd.append('orientation', orientation)
    fd.append('header_row', String(headerRow))
    fd.append('time_col', String(timeCol))
    fd.append('fs', String(fsManual))
    try {
      const res  = await fetch('/api/session/reparse', { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) { parseError = data.detail; return }
      // Keep the original detection so the banner still explains what it found.
      session = { ...data, detected: session.detected, filename: session.filename }
      applySessionDefaults(data.column_names, timeCol)
      plotData = null
    } catch (e) {
      parseError = e.message
    } finally {
      parsing = false
    }
  }

  function onFileChosen(f) {
    file = f
    plotData = null
    plotError = null
    previewExpanded = false
    layoutOpen = false
    createSession(f)
  }

  // Results can arrive after the user has moved on. Only the newest run wins.
  let runSeq = 0

  // The last request issued, so changing preprocessing can replay it verbatim.
  let lastRun = null

  /**
   * The one way activeTab changes. Switching analysis must not leave the
   * previous chart on screen — payload shapes differ between analyses, so a
   * stale one renders as a wrong or blank plot — and it must invalidate any
   * request still in flight. Done here rather than in an $effect so it can't
   * race the incoming control's auto-run.
   */
  function switchTab(tabId) {
    if (activeTab === tabId) return
    runSeq++
    plotData  = null
    plotError = null
    activeTab = tabId
  }

  /** One POST. Returns {data} or {error} rather than throwing. */
  /**
   * @param queryOverride  replaces the matching preprocessing query params for
   *   this one call. Only the Explorer uses it, to narrow the sample window for
   *   an O(N²) transform without touching the preprocessing panel the user set.
   */
  async function post(endpoint, extraFields = {}, queryOverride = null, sessionOverride = null) {
    try {
      let url = buildPreprocUrl(endpoint)
      if (queryOverride) {
        const [path, qs] = url.split('?')
        const p = new URLSearchParams(qs ?? '')
        for (const [k, v] of Object.entries(queryOverride)) p.set(k, v)
        url = `${path}?${p.toString()}`
      }
      const res  = await fetch(url, {
        method: 'POST', body: buildFormData(extraFields, sessionOverride),
      })
      const data = await res.json()
      if (res.ok) return { data }

      // A 404 here means the route does not exist, not that anything is wrong
      // with the request. That happens when the page has been updated but the
      // Python process behind it is still the one started before the update —
      // it loads its code once, at startup. "Not Found" gives no hint of that.
      if (res.status === 404 && /not found/i.test(String(data.detail ?? ''))) {
        return { error:
          'This analysis needs a newer version of the backend than the one running. ' +
          'Close the DSPkit window and start it again — the browser picks up changes ' +
          'on reload, but the Python process only at startup.' }
      }
      return { error: data.detail }
    } catch (e) {
      // fetch itself failed: the server is not answering at all.
      return { error:
        `Could not reach DSPkit (${e.message}). If the DSPkit window has been ` +
        'closed, start it again.' }
    }
  }

  async function runAnalysis(endpoint, extraFields = {}) {
    if (!session) return
    if (signalCols.length === 0) { plotError = 'Select at least one channel.'; return }
    if (extraFields.signal_col === ALL_CHANNELS) return runFanout(endpoint, extraFields)
    // A pinned reference turns every comparable analysis into a two-dataset
    // one. Tabs outside COMPARABLE ignore it and run normally rather than
    // silently dropping the reference — the banner keeps saying it is pinned.
    if (compareRef && isComparable(activeTab)) return runComparison(endpoint, extraFields)

    lastRun = { kind: 'single', endpoint, extra: extraFields }
    const seq = ++runSeq
    loading = true
    plotData = null
    plotError = null
    const { data, error } = await post(endpoint, extraFields)
    if (seq !== runSeq) return
    if (error) plotError = error
    else plotData = data
    loading = false
  }

  /**
   * Run a single-channel analysis once per selected channel, in parallel, and
   * collect the results into a small-multiples grid. Every endpoint that takes
   * one channel names the field `signal_col`, so this needs no per-analysis
   * knowledge. The session means each call re-uses the already-parsed file.
   */
  async function runFanout(endpoint, extraFields) {
    lastRun = { kind: 'fanout', endpoint, extra: extraFields }
    const seq = ++runSeq
    loading = true
    plotData = null
    plotError = null
    const channels = [...signalCols]
    const results = await Promise.all(channels.map(async (ci) => {
      const { data, error } = await post(endpoint, { ...extraFields, signal_col: ci })
      return { name: channelName(ci), col: ci, data, error }
    }))
    if (seq !== runSeq) return
    // A grid where every cell failed is just an error; show it as one.
    if (results.every(r => r.error)) plotError = results[0].error
    else plotData = { grid: results }
    loading = false
  }

  /**
   * One reference channel against every other selected channel, overlaid on a
   * single axis. Same fan-out as runFanout, but the results belong on one plot
   * rather than in a grid — comparing correlations is the whole point, and
   * separate panels make curves impossible to compare by eye.
   */
  async function runPairOverlay(endpoint, extraFields, refCol) {
    if (!session) return
    lastRun = { kind: 'overlay', endpoint, extra: extraFields, ref: refCol }
    const seq = ++runSeq
    loading = true
    plotData = null
    plotError = null
    // The reference against itself comes first: for cross-correlation that is
    // the autocorrelation, which is the baseline the other curves are read
    // against — how much of the correlation is the channel's own structure.
    const targets = [refCol, ...signalCols.filter(c => c !== refCol)]

    const items = await Promise.all(targets.map(async (ci) => {
      const { data, error } = await post(endpoint, {
        ...extraFields, signal_col_x: refCol, signal_col_y: ci,
      })
      const label = ci === refCol
        ? `${channelName(ci)} (self)`
        : `${channelName(refCol)} → ${channelName(ci)}`
      return { name: label, col: ci, data, error }
    }))
    if (seq !== runSeq) return
    if (items.every(r => r.error)) plotError = items[0].error
    else plotData = { overlay: { ref: channelName(refCol), items } }
    loading = false
  }

  // ── comparing against a second dataset ─────────────────────────────────────
  //
  // The backend was already multi-session — every analysis endpoint takes a
  // session_id and several parsed files stay in memory — so this holds a second
  // session alongside the active one and runs the same analysis twice. No new
  // endpoint, and the reference is never "loaded" in the sense that would
  // disturb the channel selection, preprocessing or tab.
  //
  // Only one reference, deliberately. Two datasets is where nearly all of the
  // value is, and each extra one multiplies the channel-matching problem below
  // while making the chart harder to read, not easier.
  let compareRef = $state(null)   // {session_id, filename, column_names, fs, time_col}

  async function toggleCompare(entry) {
    if (compareRef?.session_id === entry.session_id) { compareRef = null; return }
    if (session && entry.session_id === session.session_id) {
      plotError = 'That is the dataset already open. Pick a different one to compare against.'
      return
    }
    try {
      // touch=false: pinning is not opening. Without it the reference is
      // stamped as the most recently used file and comes back on next launch
      // instead of the dataset actually being worked on.
      const res = await fetch(`/api/session/${entry.session_id}?touch=false`)
      const data = await res.json()
      if (!res.ok) { plotError = data.detail; return }
      const ref = {
        session_id: data.session_id,
        filename: data.filename,
        column_names: data.column_names ?? [],
        n_samples: data.n_samples,
        fs: data.fs,
        time_col: data.time_col ?? -1,
        orientation: data.orientation,
        header_row: data.header_row,
      }
      // Check the names now rather than on the next run. Pinning a file that
      // shares no channel with this one leaves the tab refusing every analysis
      // until the reference is cleared, and the reason for that is much harder
      // to see once it is three clicks behind you.
      const names = new Set(ref.column_names)
      const wanted = signalCols.map(c => session.column_names?.[c])
      if (wanted.length && !wanted.some(n => names.has(n))) {
        plotError =
          `${ref.filename} shares no channel name with ${session.filename} ` +
          `(looking for ${wanted.join(', ')}). Channels are matched by name, so ` +
          `there is nothing to compare. Not pinned.`
        return
      }
      compareRef = ref
      rerunActive()
    } catch (e) {
      plotError = `Could not open that dataset to compare (${e.message}).`
    }
  }

  function clearCompare() {
    compareRef = null
    rerunActive()
  }

  /**
   * Where the active selection's channels live in the reference file.
   *
   * **By name, and it refuses rather than guessing.** Column *order* agreeing
   * between two files is a coincidence, not a guarantee, and silently comparing
   * acc1 against a differently-ordered acc3 would produce a chart that looks
   * fine and means nothing. A name that is missing is a real answer — the two
   * files do not hold the same measurement — so it is reported, not patched.
   */
  function mapColumns(cols) {
    if (!compareRef) return { cols: null, missing: [] }
    const refNames = compareRef.column_names
    const missing = []
    const mapped = cols.map((c) => {
      const wanted = session.column_names?.[c]
      const i = refNames.indexOf(wanted)
      if (i < 0) missing.push(wanted ?? `column ${c}`)
      return i
    })
    return { cols: mapped, missing }
  }

  /**
   * The reference's own fields for a request: its session, its time column, its
   * sample rate, and the active channels translated into its own numbering.
   */
  function compareOverride(extraFields) {
    const { cols, missing } = mapColumns(signalCols.map(Number))
    if (missing.length) return { error:
      `${compareRef.filename} has no ${missing.length > 1 ? 'channels' : 'channel'} ` +
      `named ${missing.join(', ')}. Channels are matched by name between datasets, ` +
      `so the comparison would not be like for like.` }

    const fields = {
      session_id: compareRef.session_id,
      orientation: compareRef.orientation,
      header_row: String(compareRef.header_row),
      time_col: String(compareRef.time_col),
      fs: String(compareRef.fs ?? effectiveFs),
      signal_cols: JSON.stringify(cols),
    }
    // Single-channel analyses name one column, and it needs translating too.
    const extra = { ...extraFields }
    for (const key of ['signal_col', 'signal_col_x', 'signal_col_y', 'target_col']) {
      if (extra[key] !== undefined && extra[key] !== null && extra[key] !== ALL_CHANNELS) {
        const m = mapColumns([Number(extra[key])])
        if (m.missing.length) return { error:
          `${compareRef.filename} has no channel named ${m.missing[0]}.` }
        extra[key] = m.cols[0]
      }
    }
    return { fields, extra }
  }

  /**
   * A caveat when the two records are not really commensurable.
   *
   * Different sample rates are *not* refused: a spectrum is in Hz either way
   * and the comparison is still meaningful, it is just no longer like for like
   * at a given nperseg — the resolution and the Nyquist both move. That is a
   * thing to say, not a thing to block, and saying it beats a refusal that
   * would stop a legitimate comparison.
   */
  let compareCaveat = $derived.by(() => {
    if (!compareRef || !session) return null
    const notes = []
    const a = Number(effectiveFs), b = Number(compareRef.fs)
    if (a && b && Math.abs(a - b) / a > 1e-6) {
      notes.push(
        `sample rates differ (${a.toFixed(2)} Hz here, ${b.toFixed(2)} Hz there), ` +
        `so the same nperseg gives a different frequency resolution in each`)
    }
    if (compareRef.n_samples && session.n_samples &&
        Math.abs(compareRef.n_samples - session.n_samples) /
          Math.max(compareRef.n_samples, session.n_samples) > 0.25) {
      notes.push(
        `record lengths differ substantially (${session.n_samples.toLocaleString()} ` +
        `against ${compareRef.n_samples.toLocaleString()} samples), which changes ` +
        `how many segments each average has`)
    }
    notes.push(
      'preprocessing set here is applied to both, so the reference is filtered ' +
      'and detrended the same way')
    return notes
  })

  /**
   * The same analysis again with the display thinning switched off.
   *
   * Only the CSV export uses this. It is deliberately not cached: an export is
   * rare and can afford a round trip, where holding the full arrays in memory
   * against the chance of one would give back everything the thinning bought.
   */
  async function fetchFullData() {
    if (!lastRun || lastRun.kind !== 'single') return null
    const { data, error } = await post(lastRun.endpoint, {
      ...lastRun.extra, max_points: 0, include_raw: true,
      view_start: null, view_end: null,
    })
    return error ? null : data
  }

  /**
   * Ask the library whether a segment length is a good one, on this record.
   *
   * Not an analysis: it answers a question about the *parameters* rather than
   * producing a chart, so it returns to the caller instead of touching
   * plotData. That keeps a check from wiping the plot the user is comparing
   * against.
   */
  async function checkSegments(extra = {}) {
    if (!session || signalCols.length === 0) return null
    const { data, error } = await post('/api/spectral/segment_advice', extra)
    return error ? { verdict: 'error', advice: error } : data
  }

  /** The fan-out again with the thinning off, for a grid CSV export. */
  async function fetchFullGrid() {
    if (!lastRun || lastRun.kind !== 'fanout') return null
    const channels = [...signalCols]
    return Promise.all(channels.map(async (ci) => {
      const { data, error } = await post(lastRun.endpoint, {
        ...lastRun.extra, signal_col: ci, max_points: 0,
      })
      return { name: channelName(ci), col: ci, data, error }
    }))
  }

  /**
   * Re-fetch the visible window when the chart is zoomed.
   *
   * The series arrives thinned to a point budget, so magnifying it client-side
   * would just show bigger steps. Asking the server for the window spends the
   * same budget on a shorter span, which is what makes a zoom reveal detail —
   * the property `downsample.test.mjs` has always asserted, now paid for over
   * the wire instead of by sending the whole record up front.
   *
   * Deliberately quiet: `plotData` is left in place while the request is in
   * flight, so the chart does not blank on every drag. Debounced, because a
   * drag emits a relayout per frame.
   */
  let viewTimer = null
  function onViewChange(range) {
    if (lastRun?.kind === 'overview') return overviewViewChange(range)
    if (!lastRun || lastRun.kind !== 'single') return
    if (lastRun.endpoint !== '/api/signal/timeseries') return
    clearTimeout(viewTimer)
    viewTimer = setTimeout(async () => {
      const seq = ++runSeq
      const { data, error } = await post(lastRun.endpoint, {
        ...lastRun.extra,
        view_start: range?.[0] ?? null,
        view_end: range?.[1] ?? null,
      })
      if (seq !== runSeq) return
      if (!error && data) plotData = data
    }, 250)
  }

  /**
   * The same for the Overview's time series: only that panel is re-fetched,
   * the PSD and FDD beside it stay as they are. The response echoes the window
   * as `view`, which is what the chart pins its axis to.
   */
  function overviewViewChange(range) {
    clearTimeout(viewTimer)
    viewTimer = setTimeout(async () => {
      const seq = ++runSeq
      const res = await post('/api/signal/timeseries', {
        view_start: range?.[0] ?? null,
        view_end: range?.[1] ?? null,
      })
      if (seq !== runSeq || !plotData?.overview) return
      if (!res.error && res.data) plotData = { overview: { ...plotData.overview, ts: res } }
    }, 250)
  }

  /**
   * Run one analysis against both datasets and put the results on one chart.
   *
   * The reference is fetched with the *active* preprocessing query, which is
   * the point: comparing a filtered record against an unfiltered one would be
   * comparing the filter.
   */
  async function runComparison(endpoint, extraFields) {
    const over = compareOverride(extraFields)
    if (over.error) { plotError = over.error; loading = false; return }

    lastRun = { kind: 'comparison', endpoint, extra: extraFields }
    const seq = ++runSeq
    loading = true
    plotData = null
    plotError = null

    const [mine, theirs] = await Promise.all([
      post(endpoint, extraFields),
      post(endpoint, over.extra, null, over.fields),
    ])
    if (seq !== runSeq) return

    if (mine.error && theirs.error) { plotError = mine.error; loading = false; return }
    plotData = { comparison: { items: [
      { label: session.filename, data: mine.data, error: mine.error },
      { label: compareRef.filename, data: theirs.data, error: theirs.error },
    ] } }
    loading = false
  }

  /**
   * The Time-Frequency Explorer: one surface plus everything that reads it.
   *
   * Composed from the endpoints that already exist — the transform, the time
   * series and the PSD for the same channel under the same preprocessing — so
   * the three panels are guaranteed to be showing the same data. That is the
   * property the whole tab depends on; fetching them independently at different
   * times would quietly break it.
   */
  async function runExplorer(transform, params = {}) {
    if (!session || signalCols.length === 0) return
    lastRun = { kind: 'explorer', transform, extra: params }
    const seq = ++runSeq
    loading = true
    plotData = null
    plotError = null

    const col = focusChannel === ALL_CHANNELS ? signalCols[0] : focusChannel
    const spec = transformById(transform)

    // An O(N^2) transform gets a capped window. It is intersected with whatever
    // preprocessing window is already set rather than replacing it — the user's
    // window is a statement about which part of the record is interesting, and
    // the cap is only about how much of it we can afford.
    const userWin = preprocWindowSamples()
    const plan = costPlan(transform, userWin.count, effectiveFs)
    const capFields = plan.capped
      ? { win_start: userWin.start + plan.start,
          win_end:   userWin.start + plan.start + plan.count,
          win_unit:  'samples' }
      : null

    const [tf, ts, psd] = await Promise.all([
      post(spec.endpoint, { signal_col: col, ...surfaceLimits(), ...params }, capFields),
      post('/api/signal/timeseries', { signal_cols: JSON.stringify([col]) }, capFields),
      post('/api/spectral/psd',
           { signal_cols: JSON.stringify([col]), window: 'hann', nperseg: 1024 }, capFields),
    ])
    if (seq !== runSeq) return

    if (tf.error) { plotError = tf.error; loading = false; return }

    const z = surfaceOf(transform, tf.data)
    if (!z) {
      plotError = `${spec.label} returned no surface.`
      loading = false
      return
    }

    // The side panels are a convenience, not a requirement: a surface with a
    // failed PSD is still worth looking at, so their errors do not sink the tab.
    const tsSig = ts.data?.signals?.[0]
    plotData = {
      explorer: {
        transform,
        tf: { times: tf.data.times, freqs: tf.data.freqs, z },
        ts: tsSig
          ? { times: ts.data.times_proc ?? ts.data.times_raw,
              values: tsSig.signal_proc ?? tsSig.signal_raw,
              name: tsSig.name }
          : null,
        psd: psd.data?.signals?.[0]
          ? { freqs: psd.data.freqs, values: psd.data.signals[0].Pxx }
          : null,
        notice: plan.notice,
        channel: channelName(col),
      },
    }
    loading = false
  }

  /**
   * The preprocessing window as absolute sample indices, so the Explorer's cap
   * can be expressed in the same terms and composed with it.
   */
  function preprocWindowSamples() {
    const n = session?.n_samples ?? 0
    if (!preproc.windowEnabled) return { start: 0, count: n }
    const fs = effectiveFs || 1
    const toSamples = (v) => preproc.winUnit === 'time' ? Math.round(v * fs) : Math.round(v)
    const rawStart = (preproc.winStart !== null && preproc.winStart !== '')
      ? toSamples(Number(preproc.winStart)) : 0
    const rawEnd = (preproc.winEnd !== null && preproc.winEnd !== '')
      ? toSamples(Number(preproc.winEnd)) : n
    const start = Math.max(0, Math.min(rawStart, n))
    const end   = Math.max(start, Math.min(rawEnd, n))
    return { start, count: end - start }
  }

  /**
   * The first look at a file: what the signals do, where their energy sits, and
   * — with 2+ channels — the FDD singular values that suggest candidate modes.
   * Composed from the existing endpoints so it honours preprocessing for free.
   */
  async function runOverview() {
    if (!session || signalCols.length === 0) return
    lastRun = { kind: 'overview' }
    const seq = ++runSeq
    loading = true
    plotData = null
    plotError = null
    const [ts, psd, fdd] = await Promise.all([
      post('/api/signal/timeseries', {}),
      post('/api/spectral/psd', { window: 'hann', nperseg: 1024, scaling: 'density' }),
      signalCols.length >= 2
        ? post('/api/fdd/analyze', {
            window: 'hann', nperseg: 1024, mac_threshold: 0.8, n_crossings: 10,
          })
        : Promise.resolve({ skipped: 'FDD needs at least 2 selected channels.' }),
    ])
    if (seq !== runSeq) return
    if (ts.error && psd.error) plotError = ts.error
    else plotData = { overview: { ts, psd, fdd } }
    loading = false
  }
</script>

<div class="topbar">
  <span class="brand">
    <DspkitLogo size={24} />
    <span>DSPkit <span class="brand-sub">GUI</span></span>
  </span>

  {#if session}
    <div class="status-chips">
      <span class="status-chip ok" title={session.filename ?? file?.name}>
        <span class="dot"></span>{session.filename ?? file?.name}
      </span>
      <span class="status-chip ok">
        <span class="dot"></span>{nSignals} ch · {session.n_samples.toLocaleString()} samples
      </span>
      {#if session.fs}
        <span class="status-chip ok">
          <span class="dot"></span>{session.fs.toFixed(2)} Hz · {session.duration}s
        </span>
      {:else}
        <span class="status-chip">
          <span class="dot"></span>fs {fsManual} Hz (manual)
        </span>
      {/if}
      <!-- Say so when the settings on screen were restored rather than chosen
           now — otherwise a filter left on last week silently shapes today's
           results. -->
      {#if session.detected?.t0}
        <span class="status-chip" title="Start time of the record, as written in the file">
          <span class="dot"></span>start {session.detected.t0}
        </span>
      {/if}
      {#if restored}
        <span class="status-chip" title="Channels, preprocessing and analysis
settings were restored from the last time this file was open.">
          <span class="dot"></span>settings restored
        </span>
      {/if}
    </div>
  {/if}

  <span style="flex:1"></span>
  <button class="topbar-icon-btn" onclick={() => aboutOpen = true}
          title="About DSPkit GUI" aria-label="About DSPkit GUI">
    <!-- Drawn rather than the ⓘ glyph, which most system fonts render thin
         and off-centre at this size. -->
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9.25" stroke="currentColor" stroke-width="1.6" />
      <line x1="12" y1="11" x2="12" y2="16.5" stroke="currentColor"
            stroke-width="1.9" stroke-linecap="round" />
      <circle cx="12" cy="7.6" r="1.2" fill="currentColor" />
    </svg>
  </button>
  <button class="topbar-icon-btn" onclick={() => rightOpen = !rightOpen}
          title={rightOpen ? 'Close settings' : 'Open settings'}>
    {rightOpen ? '✕' : '⚙'}
  </button>
</div>

{#if aboutOpen}
  <AboutDialog onclose={() => aboutOpen = false} />
{/if}

<div class="layout" class:right-open={rightOpen}>
  <!-- ── sidebar (data setup only) ── -->
  <aside class="sidebar">
    <FileUpload
      {hasFile}
      {sourcePath}
      sessionId={session?.session_id ?? null}
      compareId={compareRef?.session_id ?? null}
      filename={session?.filename ?? file?.name}
      onfile={onFileChosen}
      onopen={(entry) => entry.source_path
        ? openPath(entry.source_path)
        : openSession(entry.session_id)}
      oncompare={toggleCompare}
      onclose={closeSession}
    />

    {#if compareRef}
      <div class="compare-banner">
        <div class="compare-title">
          Comparing against
          <button class="compare-clear" onclick={clearCompare}
                  title="Stop comparing">×</button>
        </div>
        <div class="compare-file">{compareRef.filename}</div>
        {#if !isComparable(activeTab)}
          <div class="compare-note">
            This tab shows one dataset at a time. Switch to a spectrum,
            autocorrelation, response spectrum, FDD or conditioned-coherence tab
            to see both.
          </div>
        {:else}
          {#each compareCaveat ?? [] as note}
            <div class="compare-note">{note}</div>
          {/each}
        {/if}
      </div>
    {/if}

    {#if hasParsed}
      <!-- what the loader worked out on its own -->
      {#if detectSummary}
        <div class="detect-banner">
          <div class="detect-title">Detected automatically</div>
          <div>{detectSummary}</div>
        </div>
      {/if}

      <!--
        Why no time column was used. Without this a record with one dropped
        sample is analysed at a made-up rate and looks entirely normal.
      -->
      {#if detectRejection}
        <div class="reject-banner" class:warn={detectRejection.severity === 'warn'}>
          <div class="reject-title">
            {detectRejection.severity === 'warn' ? '⚠' : 'ℹ'}
            {detectRejection.headline}
          </div>
          <div class="reject-detail">{detectRejection.detail}</div>
          <div class="reject-detail">
            Analysing at <strong>{fsManual} Hz</strong>{
              detectRejection.impliedFs ? ' (this file’s median interval)' : ''
            }. Change it under File layout.
          </div>
        </div>
      {/if}

      <div class="info-grid">
        <div class="info-item">
          <div class="label">Samples</div>
          <div class="value">{session.n_samples.toLocaleString()}</div>
        </div>
        <div class="info-item">
          <div class="label">Channels</div>
          <div class="value">{session.n_columns}</div>
        </div>
        {#if session.fs}
          <div class="info-item">
            <div class="label">fs</div>
            <div class="value">{session.fs.toFixed(1)} Hz</div>
          </div>
        {/if}
        {#if session.duration}
          <div class="info-item">
            <div class="label">Duration</div>
            <div class="value">{session.duration.toFixed(2)} s</div>
          </div>
        {/if}
      </div>

      <ChannelSelect
        columnNames={session.column_names}
        {timeCol}
        bind:selected={signalCols}
        bind:units={channelUnits}
      />

      <!-- Layout overrides — only needed when detection guessed wrong -->
      <hr />
      <div style="padding:0 12px">
        <button class="sidebar-btn"
                style="padding:6px 0;width:100%;text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--text-muted);display:flex;justify-content:space-between"
                onclick={() => layoutOpen = !layoutOpen}>
          File layout
          <span>{layoutOpen ? '▲' : '▼'}</span>
        </button>
      </div>
      {#if layoutOpen && isMat}
        <!-- A .mat file names its own axes, rate and channels, so there is no
             layout to override — only the variables it was read from to show. -->
        <div class="parse-opts">
          <div class="detect-note">Read from a MATLAB file. Variables used:</div>
          {#each Object.entries(session.detected.mat_sources ?? {}) as [role, v]}
            <div class="field">
              <span class="mat-role">{MAT_ROLES[role] ?? role}</span>
              <code class="mat-var">{Array.isArray(v) ? v.join(', ') : v}</code>
            </div>
          {/each}
          {#if !session.detected.fs}
            <div class="field">
              <label for="fs-man">Sample rate (Hz) — not in the file</label>
              <input id="fs-man" type="number" bind:value={fsManual} min="0.001" step="1" />
            </div>
          {/if}
        </div>
      {:else if layoutOpen}
        <div class="parse-opts">
          <div class="detect-note">Only change these if the preview looks wrong.</div>
          <div class="field">
            <label for="orient">Orientation</label>
            <select id="orient" bind:value={orientation} onchange={reparse}>
              <option value="columns">Columns = signals</option>
              <option value="rows">Rows = signals</option>
              <option value="rows_labeled">Rows = signals, first cell is the name</option>
            </select>
          </div>
          <div class="field">
            <label for="hdr">Header row (-1 = none)</label>
            <input id="hdr" type="number" bind:value={headerRow} min="-1" step="1"
                   onchange={reparse} style="width:70px" />
          </div>
          <div class="field">
            <label for="tcol">Time column (-1 = none)</label>
            <select id="tcol" bind:value={timeCol} onchange={reparse}>
              <option value={-1}>-- none --</option>
              {#each session.column_names as name, i}
                <option value={i}>{name}</option>
              {/each}
            </select>
          </div>
          {#if timeCol < 0}
            <div class="field">
              <label for="fs-man">Sample rate (Hz)</label>
              <input id="fs-man" type="number" bind:value={fsManual} min="0.001" step="1" />
            </div>
          {/if}
        </div>
      {/if}

      <PreprocessPanel {preproc} fs={session?.fs ?? fsManual} onchange={rerunActive} />
    {/if}
  </aside>

  <!-- ── main ── -->
  <div class="main">
    {#if hasParsed}
      <!-- Category tabs (horizontal bar) -->
      <div class="category-bar">
        {#each CATEGORIES as cat}
          <button
            class="cat-btn"
            class:active={activeCategory === cat.id}
            onclick={() => selectCategory(cat.id)}
          >{cat.label}</button>
        {/each}
      </div>

      <!-- Sub-tabs for selected category -->
      {#if currentCategory && currentCategory.tabs.length > 1}
        <div class="sub-tab-bar">
          {#each currentCategory.tabs as tab}
            <button
              class="sub-tab-btn"
              class:active={activeTab === tab.id}
              onclick={() => switchTab(tab.id)}
            >{tab.label}</button>
          {/each}
        </div>
      {/if}

      <!-- Controls -->
      <AnalysisPanel
        lastBandSweep={plotData?.band_sweep ?? []}
        {activeTab}
        {dualSignal}
        {columnNames}
        selected={signalCols}
        bind:focusChannel
        bind:pairX
        bind:pairY
        {loading}
        {plotError}
        {runAnalysis}
        {checkSegments}
        {runOverview}
        {runPairOverlay}
        {runExplorer}
      />

      <!-- Plot area -->
      <div class="plot-area">
        {#if activeTab === 'datatable' && session?.preview?.length}
          <div class="preview-main">
            <div class="preview-main-header">
              <div class="preview-main-title">
                Data preview — {session.n_samples.toLocaleString()} rows × {session.n_columns} columns
              </div>
              {#if session.preview.length > PREVIEW_DEFAULT}
                <button class="btn-ghost" onclick={() => previewExpanded = !previewExpanded}>
                  {previewExpanded ? 'Show less' : `Show all ${session.preview.length} rows`}
                </button>
              {/if}
            </div>
            <div class="preview-main-wrap">
              <table class="preview-table-main">
                <thead>
                  <tr>
                    {#each session.column_names as name, i}
                      <th class:preview-col-time={i === timeCol}>{name}</th>
                    {/each}
                  </tr>
                </thead>
                <tbody>
                  {#each (previewExpanded ? session.preview : session.preview.slice(0, PREVIEW_DEFAULT)) as row}
                    <tr>{#each row as v}<td>{typeof v === 'number' ? v.toPrecision(6) : v}</td>{/each}</tr>
                  {/each}
                </tbody>
              </table>
            </div>
            <div class="preview-main-hint">
              Showing the first {session.preview.length} of {session.n_samples.toLocaleString()} rows.
              Pick a category above to analyse this data.
            </div>
          </div>
        {:else}
          <PlotPanel
            {activeTab} {plotData} {loading} {plotError}
            {preprocSummary} {filterBand} {filterResponse} {setFilterFromRange} {clearFilter}
            units={plotUnits}
            {fddPicks} {fddVectors} {fddBusy} {fddError}
            bind:fddNVec
            onFddPick={fddPick} onFddUnpick={fddUnpick}
            onFddClear={fddClear} onFddRun={runFddVectors}
            {onViewChange} {fetchFullData} {fetchFullGrid}
          />
        {/if}
      </div>
    {:else if parseError}
      <div class="error">Could not read this file: {parseError}</div>
    {:else if parsing}
      <div class="status">Reading file…</div>
    {:else}
      <div class="empty-state">
        Drop a CSV, TSV, or TXT file on the left to begin — or pick one from
        Recent files.<br />
        Layout and sample rate are detected for you, and your signals plot straight away.
      </div>
    {/if}
  </div>

  <!-- ── right sidebar ── -->
  <RightSidebar bind:open={rightOpen} />
</div>

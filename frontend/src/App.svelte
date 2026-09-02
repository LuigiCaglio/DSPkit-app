<script>
  import DspkitLogo        from './lib/DspkitLogo.svelte'
  import FileUpload        from './lib/FileUpload.svelte'
  import AnalysisPanel     from './lib/AnalysisPanel.svelte'
  import PlotPanel         from './lib/PlotPanel.svelte'
  import PreprocessPanel   from './lib/PreprocessPanel.svelte'
  import RightSidebar      from './lib/RightSidebar.svelte'
  import ChannelSelect     from './lib/ChannelSelect.svelte'
  import { ALL_CHANNELS } from './lib/analyses.js'
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
    ]},
    { id: 'multiChannel',  label: 'Multi-Ch',      tabs: [
      { id: 'multisensor', label: 'Multi-Sensor' },
      { id: 'predictability', label: 'Predictability' },
      { id: 'fdd', label: 'FDD' },
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
    if (preproc.resampleEnabled && preproc.targetFs) bits.push(`resampled to ${preproc.targetFs} Hz`)
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
  function buildFormData(extraFields = {}) {
    const fd = new FormData()
    fd.append('session_id', session.session_id)
    fd.append('orientation', orientation)
    fd.append('header_row', String(headerRow))
    fd.append('time_col', String(timeCol))
    fd.append('fs', String(effectiveFs))
    fd.append('signal_cols', JSON.stringify(signalCols.map(Number)))
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
  async function post(endpoint, extraFields = {}, queryOverride = null) {
    try {
      let url = buildPreprocUrl(endpoint)
      if (queryOverride) {
        const [path, qs] = url.split('?')
        const p = new URLSearchParams(qs ?? '')
        for (const [k, v] of Object.entries(queryOverride)) p.set(k, v)
        url = `${path}?${p.toString()}`
      }
      const res  = await fetch(url, {
        method: 'POST', body: buildFormData(extraFields),
      })
      const data = await res.json()
      return res.ok ? { data } : { error: data.detail }
    } catch (e) {
      return { error: e.message }
    }
  }

  async function runAnalysis(endpoint, extraFields = {}) {
    if (!session) return
    if (signalCols.length === 0) { plotError = 'Select at least one channel.'; return }
    if (extraFields.signal_col === ALL_CHANNELS) return runFanout(endpoint, extraFields)

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
          ? { times: ts.data.preprocessed ? ts.data.times_proc : ts.data.times_raw,
              values: ts.data.preprocessed ? tsSig.signal_proc : tsSig.signal_raw,
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
      {#if restored}
        <span class="status-chip" title="Channels, preprocessing and analysis
settings were restored from the last time this file was open.">
          <span class="dot"></span>settings restored
        </span>
      {/if}
    </div>
  {/if}

  <span style="flex:1"></span>
  <button class="topbar-icon-btn" onclick={() => rightOpen = !rightOpen}
          title={rightOpen ? 'Close settings' : 'Open settings'}>
    {rightOpen ? '✕' : '⚙'}
  </button>
</div>

<div class="layout" class:right-open={rightOpen}>
  <!-- ── sidebar (data setup only) ── -->
  <aside class="sidebar">
    <FileUpload
      {hasFile}
      {sourcePath}
      sessionId={session?.session_id ?? null}
      filename={session?.filename ?? file?.name}
      onfile={onFileChosen}
      onopen={(entry) => entry.source_path
        ? openPath(entry.source_path)
        : openSession(entry.session_id)}
      onclose={closeSession}
    />

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
      {#if layoutOpen}
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

      <PreprocessPanel {preproc} onchange={rerunActive} />
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

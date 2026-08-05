<script>
  import DspkitLogo        from './lib/DspkitLogo.svelte'
  import FileUpload        from './lib/FileUpload.svelte'
  import AnalysisPanel     from './lib/AnalysisPanel.svelte'
  import PlotPanel         from './lib/PlotPanel.svelte'
  import PreprocessPanel   from './lib/PreprocessPanel.svelte'
  import RightSidebar      from './lib/RightSidebar.svelte'
  import ChannelSelect     from './lib/ChannelSelect.svelte'
  import { ALL_CHANNELS } from './lib/analyses.js'

  // ── session ────────────────────────────────────────────────────────────────
  // The file is uploaded and parsed once; every analysis call then refers to it
  // by session_id rather than re-sending the whole file.
  let file        = $state(null)
  let session     = $state(null)   // response from /api/session/create
  let parseError  = $state(null)
  let parsing     = $state(false)

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

  // ── preprocessing state ────────────────────────────────────────────────────
  let preproc = $state({
    windowEnabled:   false,
    winUnit:         'samples',
    winStart:        null,
    winEnd:          null,
    hpEnabled:       false,
    hpCutoff:        10,
    lpEnabled:       false,
    lpCutoff:        500,
    resampleEnabled: false,
    targetFs:        512,
  })

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
      { id: 'stft', label: 'STFT' }, { id: 'cwt', label: 'CWT' },
      { id: 'wvd', label: 'WVD' }, { id: 'spwvd', label: 'SPWVD' },
    ]},
    { id: 'decomposition', label: 'Decomposition', tabs: [
      { id: 'instantaneous', label: 'Instantaneous' },
      { id: 'emd', label: 'EMD' }, { id: 'hht', label: 'HHT' },
    ]},
    { id: 'multiChannel',  label: 'Multi-Ch',      tabs: [
      { id: 'multisensor', label: 'Multi-Sensor' },
      { id: 'fdd', label: 'FDD' },
    ]},
    { id: 'statistics',    label: 'Statistics',     tabs: [
      { id: 'statistics', label: 'Distributions' },
      { id: 'indicators', label: 'SHM Indicators' },
    ]},
  ]

  // ── derived ────────────────────────────────────────────────────────────────
  let hasFile     = $derived(file !== null)
  let hasParsed   = $derived(session !== null)
  let nSignals    = $derived(session ? session.n_columns : 0)
  let effectiveFs = $derived(session?.fs ?? fsManual)
  let columnNames = $derived(session?.column_names ?? [])

  // "Dual" now means two channels are actually *selected*, not merely present —
  // a pairwise analysis needs two things to pair.
  let dualSignal  = $derived(signalCols.length >= 2)

  const channelName = (i) => columnNames[i] ?? `Ch ${i}`

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
    if (preproc.hpEnabled && preproc.hpCutoff) bits.push(`high-pass ${preproc.hpCutoff} Hz`)
    if (preproc.lpEnabled && preproc.lpCutoff) bits.push(`low-pass ${preproc.lpCutoff} Hz`)
    if (preproc.resampleEnabled && preproc.targetFs) bits.push(`resampled to ${preproc.targetFs} Hz`)
    return bits
  })

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
    if (preproc.hpEnabled  && preproc.hpCutoff)  p.set('hp_cutoff', preproc.hpCutoff)
    if (preproc.lpEnabled  && preproc.lpCutoff)  p.set('lp_cutoff', preproc.lpCutoff)
    if (preproc.resampleEnabled && preproc.targetFs) p.set('target_fs', preproc.targetFs)
    const qs = p.toString()
    return qs ? `${endpoint}?${qs}` : endpoint
  }

  /** Default the signal selection to every non-time column. */
  function applySessionDefaults(names, tCol) {
    const nonTime = names.map((_, i) => i).filter(i => i !== tCol)
    signalCols   = nonTime
    focusChannel = nonTime[0] ?? 0
    pairX        = nonTime[0] ?? 0
    pairY        = nonTime[1] ?? pairX
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
      session     = data
      orientation = data.orientation
      headerRow   = data.header_row
      timeCol     = data.time_col
      if (data.fs) fsManual = data.fs
      applySessionDefaults(data.column_names, data.time_col)
    } catch (e) {
      parseError = e.message
      return
    } finally {
      parsing = false
    }
    // Show the data straight away rather than making the user hunt for a button.
    activeCategory = 'overview'
    activeTab = 'overview'
    await runOverview()
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
  async function post(endpoint, extraFields = {}) {
    try {
      const res  = await fetch(buildPreprocUrl(endpoint), {
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
   * The first look at a file: what the signals do, where their energy sits, and
   * — with 2+ channels — the FDD singular values that suggest candidate modes.
   * Composed from the existing endpoints so it honours preprocessing for free.
   */
  async function runOverview() {
    if (!session || signalCols.length === 0) return
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
    <FileUpload {hasFile} filename={file?.name} onfile={onFileChosen} />

    {#if hasParsed}
      <!-- what the loader worked out on its own -->
      {#if detectSummary}
        <div class="detect-banner">
          <div class="detect-title">Detected automatically</div>
          <div>{detectSummary}</div>
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

      <PreprocessPanel {preproc} />
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
          <PlotPanel {activeTab} {plotData} {loading} {plotError} {preprocSummary} />
        {/if}
      </div>
    {:else if parseError}
      <div class="error">Could not read this file: {parseError}</div>
    {:else if parsing}
      <div class="status">Reading file…</div>
    {:else}
      <div class="empty-state">
        Drop a CSV, TSV, or TXT file on the left to begin.<br />
        Layout and sample rate are detected for you, and your signals plot straight away.
      </div>
    {/if}
  </div>

  <!-- ── right sidebar ── -->
  <RightSidebar bind:open={rightOpen} />
</div>

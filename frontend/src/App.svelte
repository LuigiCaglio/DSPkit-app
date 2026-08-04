<script>
  import FileUpload        from './lib/FileUpload.svelte'
  import AnalysisPanel     from './lib/AnalysisPanel.svelte'
  import PlotPanel         from './lib/PlotPanel.svelte'
  import PreprocessPanel   from './lib/PreprocessPanel.svelte'
  import RightSidebar      from './lib/RightSidebar.svelte'

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

  // ── column assignment ──────────────────────────────────────────────────────
  let signalCols = $state([])
  let signalColX = $state(0)
  let signalColY = $state(1)

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
    { id: 'inspect',       label: 'Inspect',       tabs: [
      { id: 'timeseries', label: 'Time series' },
      { id: 'datatable', label: 'Data table' },
    ]},
    { id: 'spectral',      label: 'Spectral',      tabs: [
      { id: 'fft', label: 'FFT' }, { id: 'psd', label: 'PSD' },
      { id: 'peaks', label: 'Peaks' }, { id: 'autocorrelation', label: 'Autocorrelation' },
    ]},
    { id: 'crossSignal',   label: 'Cross-Signal',  tabs: [
      { id: 'cross_correlation', label: 'Cross-corr', dual: true },
      { id: 'csd', label: 'CSD', dual: true },
      { id: 'coherence', label: 'Coherence', dual: true },
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
      { id: 'multisensor', label: 'Multi-Sensor', dual: true },
      { id: 'fdd', label: 'FDD', dual: true },
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
  let dualSignal  = $derived(nSignals >= 2)
  let effectiveFs = $derived(session?.fs ?? fsManual)

  let currentCategory = $derived(CATEGORIES.find(c => c.id === activeCategory))

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
    if (cat && cat.tabs.length > 0) {
      const first = cat.tabs.find(t => !t.dual || dualSignal) ?? cat.tabs[0]
      activeTab = first.id
    }
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
  function applySessionDefaults(columnNames, tCol) {
    const nonTime = columnNames.map((_, i) => i).filter(i => i !== tCol)
    signalCols = nonTime
    signalColX = nonTime[0] ?? 0
    signalColY = nonTime[1] ?? signalColX
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
    activeCategory = 'inspect'
    activeTab = 'timeseries'
    await runAnalysis('/api/signal/timeseries', {})
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

  async function runAnalysis(endpoint, extraFields) {
    if (!session) return
    loading = true
    plotData = null
    plotError = null
    try {
      const url  = buildPreprocUrl(endpoint)
      const res  = await fetch(url, { method: 'POST', body: buildFormData(extraFields) })
      const data = await res.json()
      if (!res.ok) { plotError = data.detail; return }
      plotData = data
    } catch (e) {
      plotError = e.message
    } finally {
      loading = false
    }
  }
</script>

<div class="topbar">
  <span>DSPkit GUI</span>

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

      <div class="col-selectors">
        <div class="field">
          <label for="sig-cols">Signal columns</label>
          <select id="sig-cols" multiple bind:value={signalCols}
                  size={Math.min(nSignals, 5)} style="width:100%">
            {#each session.column_names as name, i}
              {#if i !== timeCol}
                <option value={i}>{name}</option>
              {/if}
            {/each}
          </select>
        </div>

        {#if dualSignal}
          <div class="field">
            <label for="ref-col">Reference (cross)</label>
            <select id="ref-col" bind:value={signalColX}>
              {#each session.column_names as name, i}
                {#if i !== timeCol}<option value={i}>{name}</option>{/if}
              {/each}
            </select>
          </div>
          <div class="field">
            <label for="resp-col">Response (cross)</label>
            <select id="resp-col" bind:value={signalColY}>
              {#each session.column_names as name, i}
                {#if i !== timeCol}<option value={i}>{name}</option>{/if}
              {/each}
            </select>
          </div>
        {/if}
      </div>

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
            disabled={cat.tabs.every(t => t.dual) && !dualSignal}
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
              disabled={tab.dual && !dualSignal}
              onclick={() => activeTab = tab.id}
            >{tab.label}</button>
          {/each}
        </div>
      {/if}

      <!-- Controls -->
      <AnalysisPanel
        {activeTab}
        {dualSignal}
        {signalColX}
        {signalColY}
        {timeCol}
        fsManual={effectiveFs}
        {loading}
        {plotError}
        {runAnalysis}
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
          <PlotPanel {activeTab} {plotData} {loading} {plotError} />
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

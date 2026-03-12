<script>
  import FileUpload        from './lib/FileUpload.svelte'
  import AnalysisPanel     from './lib/AnalysisPanel.svelte'
  import PlotPanel         from './lib/PlotPanel.svelte'
  import PreprocessPanel   from './lib/PreprocessPanel.svelte'
  import RightSidebar      from './lib/RightSidebar.svelte'

  // ── file + parse state ─────────────────────────────────────────────────────
  let file        = $state(null)
  let orientation = $state('columns')
  let headerRow   = $state(-1)
  let parseResult = $state(null)
  let parseError  = $state(null)

  // ── column assignment ──────────────────────────────────────────────────────
  let timeCol    = $state(-1)
  let signalCols = $state([])
  let signalColX = $state(0)
  let signalColY = $state(1)
  let fsManual   = $state(1000)

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

  // ── navigation state ─────────────────────────────────────────────────────
  let activeCategory = $state('inspect')
  let activeTab = $state('timeseries')
  let plotData  = $state(null)
  let plotError = $state(null)
  let loading   = $state(false)

  // ── right sidebar ────────────────────────────────────────────────────────
  let rightOpen = $state(false)

  // ── category → sub-tabs mapping ──────────────────────────────────────────
  const CATEGORIES = [
    { id: 'inspect',       label: 'Inspect',       tabs: [{ id: 'timeseries', label: 'Time series' }] },
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
  let hasFile    = $derived(file !== null)
  let hasParsed  = $derived(parseResult !== null)
  let nSignals   = $derived(parseResult ? parseResult.n_columns : 0)
  let dualSignal = $derived(nSignals >= 2)

  let currentCategory = $derived(CATEGORIES.find(c => c.id === activeCategory))

  function selectCategory(catId) {
    activeCategory = catId
    const cat = CATEGORIES.find(c => c.id === catId)
    if (cat && cat.tabs.length > 0) {
      // pick first enabled tab
      const first = cat.tabs.find(t => !t.dual || dualSignal) ?? cat.tabs[0]
      activeTab = first.id
    }
  }

  // ── helpers ────────────────────────────────────────────────────────────────
  function buildFormData(extraFields = {}) {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('orientation', orientation)
    fd.append('header_row', String(headerRow))
    fd.append('time_col', String(timeCol))
    fd.append('fs', String(fsManual))
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

  async function parseFile() {
    if (!file) return
    parseError = null
    parseResult = null
    const fd = new FormData()
    fd.append('file', file)
    fd.append('orientation', orientation)
    fd.append('header_row', String(headerRow))
    fd.append('time_col', String(timeCol))
    fd.append('fs', String(fsManual))
    try {
      const res  = await fetch('/api/signal/parse', { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) { parseError = data.detail; return }
      parseResult = data
      const nonTime = data.column_names.map((_, i) => i).filter(i => i !== timeCol)
      signalCols = nonTime
      signalColX = nonTime[0] ?? 0
      signalColY = nonTime[1] ?? signalColX
    } catch (e) {
      parseError = e.message
    }
  }

  function onFileChosen(f) {
    file = f
    parseResult = null
    plotData = null
    plotError = null
    previewExpanded = false
    parseFile()
  }

  function onParseOptsChange() {
    if (hasFile) parseFile()
  }

  async function runAnalysis(endpoint, extraFields) {
    if (!file) return
    loading = true
    plotData = null
    plotError = null
    try {
      const url = buildPreprocUrl(endpoint)
      const fd  = buildFormData(extraFields)
      const res  = await fetch(url, { method: 'POST', body: fd })
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
  <span style="flex:1"></span>
  <button class="topbar-icon-btn" onclick={() => rightOpen = !rightOpen}
          title={rightOpen ? 'Close settings' : 'Open settings'}>
    {rightOpen ? '\u2715' : '\u2699'}
  </button>
</div>

<div class="layout" class:right-open={rightOpen}>
  <!-- ── sidebar (data setup only) ── -->
  <aside class="sidebar">
    <FileUpload {hasFile} filename={file?.name} onfile={onFileChosen} />

    {#if hasFile}
      <hr />
      <div class="parse-opts">
        <div class="field">
          <label>Orientation</label>
          <select bind:value={orientation} onchange={onParseOptsChange}>
            <option value="columns">Columns = signals</option>
            <option value="rows">Rows = signals</option>
          </select>
        </div>
        <div class="field">
          <label>Header row (-1 = none)</label>
          <input type="number" bind:value={headerRow} min="-1" step="1"
                 onchange={onParseOptsChange} style="width:70px" />
        </div>
      </div>
    {/if}

    {#if hasParsed}
      <hr />
      <div class="col-selectors">
        <div class="field">
          <label>Time column (-1 = none)</label>
          <select bind:value={timeCol} onchange={onParseOptsChange}>
            <option value={-1}>-- none --</option>
            {#each parseResult.column_names as name, i}
              <option value={i}>{name}</option>
            {/each}
          </select>
        </div>

        {#if timeCol < 0}
          <div class="field">
            <label>Sample rate (Hz)</label>
            <input type="number" bind:value={fsManual} min="0.001" step="1"
                   onchange={onParseOptsChange} />
          </div>
        {/if}

        <div class="field">
          <label>Signal columns</label>
          <select multiple bind:value={signalCols} size={Math.min(nSignals, 5)} style="width:100%">
            {#each parseResult.column_names as name, i}
              {#if i !== timeCol}
                <option value={i}>{name}</option>
              {/if}
            {/each}
          </select>
        </div>

        {#if dualSignal}
          <div class="field">
            <label>Reference (cross)</label>
            <select bind:value={signalColX}>
              {#each parseResult.column_names as name, i}
                {#if i !== timeCol}
                  <option value={i}>{name}</option>
                {/if}
              {/each}
            </select>
          </div>
          <div class="field">
            <label>Response (cross)</label>
            <select bind:value={signalColY}>
              {#each parseResult.column_names as name, i}
                {#if i !== timeCol}
                  <option value={i}>{name}</option>
                {/if}
              {/each}
            </select>
          </div>
        {/if}
      </div>

      <div class="info-grid">
        <div class="info-item">
          <div class="label">Samples</div>
          <div class="value">{parseResult.n_samples.toLocaleString()}</div>
        </div>
        <div class="info-item">
          <div class="label">Channels</div>
          <div class="value">{parseResult.n_columns}</div>
        </div>
        {#if parseResult.fs}
          <div class="info-item">
            <div class="label">fs</div>
            <div class="value">{parseResult.fs.toFixed(1)} Hz</div>
          </div>
        {/if}
        {#if parseResult.duration}
          <div class="info-item">
            <div class="label">Duration</div>
            <div class="value">{parseResult.duration.toFixed(2)} s</div>
          </div>
        {/if}
      </div>

      <!-- Preprocessing -->
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
        {fsManual}
        {loading}
        {plotError}
        {runAnalysis}
      />

      <!-- Plot area -->
      <div class="plot-area">
        {#if !plotData && !loading && !plotError && parseResult?.preview?.length}
          <div class="preview-main">
            <div class="preview-main-header">
              <div class="preview-main-title">
                Data preview -- {parseResult.n_samples.toLocaleString()} rows x {parseResult.n_columns} columns
              </div>
              {#if parseResult.preview.length > PREVIEW_DEFAULT}
                <button class="btn-expand" onclick={() => previewExpanded = !previewExpanded}>
                  {previewExpanded ? `Show less` : `Show all ${parseResult.preview.length} rows`}
                </button>
              {/if}
            </div>
            <div class="preview-main-wrap">
              <table class="preview-table-main">
                <thead>
                  <tr>{#each parseResult.column_names as name}<th>{name}</th>{/each}</tr>
                </thead>
                <tbody>
                  {#each (previewExpanded ? parseResult.preview : parseResult.preview.slice(0, PREVIEW_DEFAULT)) as row}
                    <tr>{#each row as v}<td>{typeof v === 'number' ? v.toPrecision(6) : v}</td>{/each}</tr>
                  {/each}
                </tbody>
              </table>
            </div>
            <div class="preview-main-hint">Select an analysis above and click Run to plot.</div>
          </div>
        {:else}
          <PlotPanel {activeTab} {plotData} {loading} {plotError} />
        {/if}
      </div>
    {:else if hasFile && parseError}
      <div class="error">Parse error: {parseError}</div>
    {:else if hasFile}
      <div class="status">Parsing file...</div>
    {:else}
      <div class="status" style="padding:40px;text-align:center;color:#4b5563">
        Upload a CSV or TXT file to begin.
      </div>
    {/if}
  </div>

  <!-- ── right sidebar ── -->
  <RightSidebar bind:open={rightOpen} />
</div>

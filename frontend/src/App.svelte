<script>
  import FileUpload      from './lib/FileUpload.svelte'
  import AnalysisPanel  from './lib/AnalysisPanel.svelte'
  import PlotPanel      from './lib/PlotPanel.svelte'
  import PreprocessPanel from './lib/PreprocessPanel.svelte'

  // ── file + parse state ─────────────────────────────────────────────────────
  let file        = $state(null)
  let orientation = $state('columns')
  let headerRow   = $state(-1)
  let parseResult = $state(null)
  let parseError  = $state(null)

  // ── column assignment ──────────────────────────────────────────────────────
  let timeCol    = $state(-1)
  let signalColX = $state(0)
  let signalColY = $state(1)
  let fsManual   = $state(1000)

  // ── preprocessing state ────────────────────────────────────────────────────
  let preproc = $state({
    windowEnabled:   false,
    winUnit:         'samples',   // 'samples' | 'time'
    winStart:        null,
    winEnd:          null,
    hpEnabled:       false,
    hpCutoff:        10,
    lpEnabled:       false,
    lpCutoff:        500,
    resampleEnabled: false,
    targetFs:        512,
  })

  // ── active tab + plot state ────────────────────────────────────────────────
  let activeTab = $state('timeseries')
  let plotData  = $state(null)
  let plotError = $state(null)
  let loading   = $state(false)

  // ── derived ────────────────────────────────────────────────────────────────
  let hasFile    = $derived(file !== null)
  let hasParsed  = $derived(parseResult !== null)
  let nSignals   = $derived(parseResult ? parseResult.n_columns : 0)
  let dualSignal = $derived(nSignals >= 2)

  // ── helpers ────────────────────────────────────────────────────────────────
  function buildFormData(extraFields = {}) {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('orientation', orientation)
    fd.append('header_row', String(headerRow))
    fd.append('time_col', String(timeCol))
    fd.append('fs', String(fsManual))
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
    try {
      const res  = await fetch('/api/signal/parse', { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) { parseError = data.detail; return }
      parseResult = data
      signalColX = timeCol >= 0 ? (timeCol === 0 ? 1 : 0) : 0
      signalColY = signalColX + 1 < nSignals ? signalColX + 1 : signalColX
    } catch (e) {
      parseError = e.message
    }
  }

  function onFileChosen(f) {
    file = f
    parseResult = null
    plotData = null
    plotError = null
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

<div class="topbar">DSPkit GUI</div>

<div class="layout">
  <!-- ── sidebar ── -->
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
          <label>Header row (−1 = none)</label>
          <input type="number" bind:value={headerRow} min="-1" step="1"
                 onchange={onParseOptsChange} style="width:70px" />
        </div>
      </div>
    {/if}

    {#if hasParsed}
      <hr />
      <div class="col-selectors">
        <div class="field">
          <label>Time column (−1 = none)</label>
          <select bind:value={timeCol}>
            <option value={-1}>— none —</option>
            {#each parseResult.column_names as name, i}
              <option value={i}>{i}: {name}</option>
            {/each}
          </select>
        </div>

        {#if timeCol < 0}
          <div class="field">
            <label>Sample rate (Hz)</label>
            <input type="number" bind:value={fsManual} min="0.001" step="1" />
          </div>
        {/if}

        <div class="field">
          <label>Signal X</label>
          <select bind:value={signalColX}>
            {#each parseResult.column_names as name, i}
              <option value={i}>{i}: {name}</option>
            {/each}
          </select>
        </div>

        <div class="field">
          <label>Signal Y (dual analyses)</label>
          <select bind:value={signalColY} disabled={!dualSignal}>
            {#each parseResult.column_names as name, i}
              <option value={i}>{i}: {name}</option>
            {/each}
          </select>
        </div>
      </div>

      <div class="info-grid">
        <div class="info-item">
          <div class="label">Samples</div>
          <div class="value">{parseResult.n_samples.toLocaleString()}</div>
        </div>
        <div class="info-item">
          <div class="label">Columns</div>
          <div class="value">{parseResult.n_columns}</div>
        </div>
      </div>

      <!-- Preprocessing -->
      <PreprocessPanel {preproc} />

      <!-- Analysis tabs -->
      <hr />
      <div class="sidebar-section">Inspect</div>
      <button class="sidebar-btn" class:active={activeTab==='timeseries'}
              onclick={() => activeTab='timeseries'}>Time series</button>

      <div class="sidebar-section">Spectral</div>
      <button class="sidebar-btn" class:active={activeTab==='fft'}
              onclick={() => activeTab='fft'}>FFT</button>
      <button class="sidebar-btn" class:active={activeTab==='psd'}
              onclick={() => activeTab='psd'}>PSD</button>
      <button class="sidebar-btn" class:active={activeTab==='autocorrelation'}
              onclick={() => activeTab='autocorrelation'}>Autocorrelation</button>
      <button class="sidebar-btn" class:active={activeTab==='cross_correlation'}
              onclick={() => activeTab='cross_correlation'}
              disabled={!dualSignal}>Cross-correlation</button>
      <button class="sidebar-btn" class:active={activeTab==='csd'}
              onclick={() => activeTab='csd'}
              disabled={!dualSignal}>CSD</button>
      <button class="sidebar-btn" class:active={activeTab==='coherence'}
              onclick={() => activeTab='coherence'}
              disabled={!dualSignal}>Coherence</button>

      <div class="sidebar-section">Filter</div>
      <button class="sidebar-btn" class:active={activeTab==='filter'}
              onclick={() => activeTab='filter'}>Filter</button>

      <div class="sidebar-section">Time-Frequency</div>
      <button class="sidebar-btn" class:active={activeTab==='stft'}
              onclick={() => activeTab='stft'}>STFT</button>
      <button class="sidebar-btn" class:active={activeTab==='cwt'}
              onclick={() => activeTab='cwt'}>CWT</button>
      <button class="sidebar-btn" class:active={activeTab==='wvd'}
              onclick={() => activeTab='wvd'}>WVD</button>
      <button class="sidebar-btn" class:active={activeTab==='spwvd'}
              onclick={() => activeTab='spwvd'}>SPWVD</button>

      <div class="sidebar-section">Other</div>
      <button class="sidebar-btn" class:active={activeTab==='instantaneous'}
              onclick={() => activeTab='instantaneous'}>Instantaneous</button>
      <button class="sidebar-btn" class:active={activeTab==='emd'}
              onclick={() => activeTab='emd'}>EMD</button>
      <button class="sidebar-btn" class:active={activeTab==='hht'}
              onclick={() => activeTab='hht'}>HHT</button>
    {/if}
  </aside>

  <!-- ── main ── -->
  <div class="main">
    {#if hasParsed}
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
      <div class="plot-area">
        <PlotPanel {activeTab} {plotData} {loading} {plotError} />
      </div>
    {:else if hasFile && parseError}
      <div class="error">Parse error: {parseError}</div>
    {:else if hasFile}
      <div class="status">Parsing file…</div>
    {:else}
      <div class="status" style="padding:40px;text-align:center;color:#4b5563">
        Upload a CSV or TXT file to begin.
      </div>
    {/if}
  </div>
</div>

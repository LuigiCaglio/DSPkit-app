<script>
  import PlotCanvas from './PlotCanvas.svelte'
  import ResizablePane from './ResizablePane.svelte'
  import { plotTheme, themeState } from './theme.svelte.js'
  import { buildPlot, buildPhasePlot, isDownsampledFor, MAX_PLOT_POINTS } from './plotSpec.js'
  import { ZOOMABLE } from './analyses.js'

  let { activeTab, plotData, loading, plotError, preprocSummary = [] } = $props()

  // Three shapes arrive here:
  //   {grid: [...]}      a single-channel analysis fanned out per channel
  //   {overview: {...}}  the composed first-look
  //   anything else      one analysis, one chart
  let grid     = $derived(plotData?.grid ?? null)
  let overview = $derived(plotData?.overview ?? null)
  let single   = $derived(plotData && !grid && !overview ? plotData : null)

  // ── display options (local state) ───────────────────────────────────────────
  let showPhase        = $state(false)
  let normalizeSignals = $state(false)
  let yLogScale        = $state(false)

  // Shared row height for the small-multiples grid; every cell binds to it.
  let gridCellH = $state(270)

  // Which half of the cross-correlation lag axis to show.
  let lagSide = $state('both')
  $effect(() => { const _ = activeTab; lagSide = 'both' })

  // ── PSD-specific axis controls ───────────────────────────────────────────────
  let psdYLog = $state(true)   // default: log scale
  let psdXMin = $state('')
  let psdXMax = $state('')
  let psdYMin = $state('')
  let psdYMax = $state('')

  // Reset phase panel when switching tabs
  $effect(() => { const _ = activeTab; showPhase = false })

  // Reset PSD axis controls when switching away from psd tab
  $effect(() => {
    if (activeTab !== 'psd') {
      psdXMin = ''; psdXMax = ''; psdYMin = ''; psdYMax = ''; psdYLog = true
    }
  })

  // ── large-data downsampling ────────────────────────────────────────────────
  let showAllPoints = $state(false)
  $effect(() => { const _ = plotData; showAllPoints = false })

  let isDownsampled = $derived(
    !!single && isDownsampledFor(activeTab, single) && !showAllPoints
  )

  // ── zoom-follows-resolution ────────────────────────────────────────────────
  // A long record is decimated to fit the point budget. When the user zooms in,
  // re-spend that budget on the visible window instead, up to the raw sample
  // rate — the data is already here, so no request is needed.
  let zoomable = $derived(ZOOMABLE.has(activeTab) && !!single)
  let xRange   = $state(null)

  // A new payload or a different analysis invalidates the old window.
  $effect(() => { const _ = plotData, __ = activeTab; xRange = null })

  function onRelayout(e) {
    if (!e) return
    if (e['xaxis.autorange'] || e.autosize) { xRange = null; return }
    const lo = e['xaxis.range[0]'] ?? e['xaxis.range']?.[0]
    const hi = e['xaxis.range[1]'] ?? e['xaxis.range']?.[1]
    if (lo == null || hi == null) return
    // Ignore the echo of our own pinned range, which would loop.
    if (xRange && Math.abs(xRange[0] - lo) < 1e-12 && Math.abs(xRange[1] - hi) < 1e-12) return
    xRange = [lo, hi]
  }

  /** Points actually drawn for the first series, so the gain is visible. */
  let drawnPoints = $derived.by(() => {
    if (!mainSpec?.traces?.length) return 0
    return mainSpec.traces.reduce((m, t) => Math.max(m, t.x?.length ?? 0), 0)
  })
  /** True once the window is small enough to be drawn at full sample rate. */
  let atFullRate = $derived(!!xRange && drawnPoints < MAX_PLOT_POINTS)

  // ── derived ─────────────────────────────────────────────────────────────────
  let canShowPhase = $derived(
    single !== null && (activeTab === 'fft' || activeTab === 'coherence')
  )
  let hasPhaseData = $derived(
    canShowPhase && (
      (activeTab === 'fft'       && single?.signals?.[0]?.phase != null) ||
      (activeTab === 'coherence' && single?.phase_deg != null)
    )
  )

  // ── theme ───────────────────────────────────────────────────────────────────
  // Resolved from the active theme; every colour flows from here so a theme
  // switch repaints the plots without touching this file.
  let T = $derived.by(() => {
    const _ = themeState.id, __ = themeState.custom
    return plotTheme()
  })

  /** Options shared by every chart on screen. */
  let baseOpts = $derived({
    T,
    colors: T.series,
    normalize: normalizeSignals,
    yLog: yLogScale,
    psd: { yLog: psdYLog, xMin: psdXMin, xMax: psdXMax, yMin: psdYMin, yMax: psdYMax },
    downsample: !showAllPoints,
    lagSide,
  })

  let mainSpec = $derived(
    single
      ? buildPlot(activeTab, single, { ...baseOpts, xRange: zoomable ? xRange : null })
      : null
  )
  let phaseSpec = $derived(
    showPhase && hasPhaseData ? buildPhasePlot(activeTab, single, baseOpts) : null
  )

  let gridSpecs = $derived(
    grid
      ? grid.map(r => ({
          name: r.name,
          error: r.error,
          spec: r.data ? buildPlot(activeTab, r.data, { ...baseOpts, cell: true, title: r.name }) : null,
        }))
      : []
  )

  let overviewSpecs = $derived.by(() => {
    if (!overview) return null
    const { ts, psd, fdd } = overview
    return {
      ts:  ts.data  ? buildPlot('timeseries', ts.data, { ...baseOpts, title: 'Time series' }) : null,
      psd: psd.data ? buildPlot('psd', psd.data, { ...baseOpts, title: 'Power spectral density' }) : null,
      fdd: fdd.data
        ? buildPlot('fdd', fdd.data, {
            ...baseOpts,
            title: `FDD — Singular Values (${fdd.data.labels.length} ch: ${fdd.data.labels.join(', ')})`,
          })
        : null,
      tsError: ts.error, psdError: psd.error,
      fddError: fdd.error, fddSkipped: fdd.skipped,
      fddData: fdd.data ?? null,
    }
  })

  // ── CSV export ───────────────────────────────────────────────────────────────
  /** Build [headers, rows] for one analysis payload, or null if unsupported. */
  function csvFor(tab, d) {
    let headers = [], rows = []

    if (tab === 'timeseries') {
      const times = d.preprocessed ? d.times_proc : d.times_raw
      headers = ['time_s', ...d.signals.map(s => s.name)]
      const arr = d.preprocessed ? d.signals.map(s => s.signal_proc) : d.signals.map(s => s.signal_raw)
      for (let i = 0; i < times.length; i++) rows.push([times[i], ...arr.map(a => a[i])])

    } else if (tab === 'fft') {
      headers = ['frequency_Hz', ...d.signals.flatMap(s => [s.name, `${s.name}_phase_deg`])]
      for (let i = 0; i < d.freqs.length; i++)
        rows.push([d.freqs[i], ...d.signals.flatMap(s => [s.amplitude[i], s.phase?.[i] ?? ''])])

    } else if (tab === 'psd') {
      headers = ['frequency_Hz', ...d.signals.map(s => s.name)]
      for (let i = 0; i < d.freqs.length; i++)
        rows.push([d.freqs[i], ...d.signals.map(s => s.Pxx[i])])

    } else if (tab === 'autocorrelation') {
      headers = ['lag_s', ...d.signals.map(s => s.name)]
      for (let i = 0; i < d.lags.length; i++)
        rows.push([d.lags[i], ...d.signals.map(s => s.acf[i])])

    } else if (tab === 'cross_correlation') {
      headers = ['lag_s', 'CCF']
      for (let i = 0; i < d.lags.length; i++) rows.push([d.lags[i], d.ccf[i]])

    } else if (tab === 'csd') {
      headers = ['frequency_Hz', 'magnitude', 'phase_deg']
      for (let i = 0; i < d.freqs.length; i++) rows.push([d.freqs[i], d.magnitude[i], d.phase_deg[i]])

    } else if (tab === 'coherence') {
      headers = ['frequency_Hz', 'coherence', 'phase_deg']
      for (let i = 0; i < d.freqs.length; i++)
        rows.push([d.freqs[i], d.Cxy[i], d.phase_deg?.[i] ?? ''])

    } else if (tab === 'filter') {
      headers = ['time_s', 'raw', 'filtered']
      for (let i = 0; i < d.times.length; i++)
        rows.push([d.times[i], d.signal_raw[i], d.signal_filtered[i]])

    } else if (tab === 'peaks') {
      headers = ['frequency_Hz', 'amplitude', 'prominence', 'bandwidth_Hz', 'Q_factor']
      for (let i = 0; i < d.peak_freqs.length; i++)
        rows.push([d.peak_freqs[i], d.peak_values[i], d.prominences[i], d.bandwidths[i], d.q_factors[i]])

    } else if (tab === 'indicators') {
      headers = ['time_s', 'rms', 'energy', 'dominant_freq_Hz']
      const n = Math.max(d.rms_times.length, d.energy_times.length, d.freq_times.length)
      for (let i = 0; i < n; i++)
        rows.push([d.rms_times[i] ?? '', d.rms_values[i] ?? '', d.energy_values[i] ?? '', d.dominant_freqs[i] ?? ''])

    } else if (tab === 'fdd') {
      headers = ['mode', 'frequency_Hz', 'damping_pct', ...d.labels]
      for (let i = 0; i < d.peak_freqs.length; i++)
        rows.push([i + 1, d.natural_freqs?.[i] ?? d.peak_freqs[i],
          d.damping_ratios?.[i] != null ? d.damping_ratios[i] * 100 : '',
          ...(d.modes[i] ?? [])])

    } else { return null }

    return [headers, rows]
  }

  function download(name, headers, rows) {
    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(new Blob([csv], { type: 'text/csv' })),
      download: name,
    })
    a.click()
    URL.revokeObjectURL(a.href)
  }

  function exportCsv(tab = activeTab, d = single, name = `${activeTab}.csv`) {
    if (!d) return
    const built = csvFor(tab, d)
    if (!built) return
    download(name, built[0], built[1])
  }

  /** Grid export: one file, with a channel column identifying each block. */
  function exportGridCsv() {
    const usable = gridSpecs.filter((_, i) => grid[i].data)
    if (!usable.length) return
    let headers = null
    const rows = []
    for (const cell of grid) {
      if (!cell.data) continue
      const built = csvFor(activeTab, cell.data)
      if (!built) continue
      if (!headers) headers = ['channel', ...built[0]]
      for (const r of built[1]) rows.push([cell.name, ...r])
    }
    if (!headers) return
    download(`${activeTab}_all_channels.csv`, headers, rows)
  }

  let csvSupported = $derived(!!single && csvFor(activeTab, single) !== null)
  let gridCsvSupported = $derived(
    !!grid && grid.some(c => c.data && csvFor(activeTab, c.data) !== null)
  )
</script>

<div class="plot-wrap">

  <!-- toolbar -->
  {#if plotData}
    <div class="plot-toolbar">
      <!-- Provenance first: what is plotted has been through this. -->
      {#if preprocSummary.length}
        <span class="prov-chip on" title="Applied before every analysis">
          ⚙ {preprocSummary.join(' · ')}
        </span>
      {:else}
        <span class="prov-chip">raw data</span>
      {/if}
      <span class="plot-toolbar-sep"></span>
      {#if canShowPhase}
        <label><input type="checkbox" bind:checked={showPhase} /> Phase</label>
      {/if}
      <label><input type="checkbox" bind:checked={normalizeSignals} /> Normalize</label>
      {#if activeTab !== 'psd' && !overview}
        <label><input type="checkbox" bind:checked={yLogScale} /> Log Y</label>
      {/if}
      {#if isDownsampled || showAllPoints}
        <label><input type="checkbox" bind:checked={showAllPoints} /> All points</label>
      {/if}
      {#if activeTab === 'cross_correlation'}
        <span class="plot-toolbar-sep"></span>
        <span class="plot-toolbar-group">
          <span class="plot-toolbar-grouplabel">Lags</span>
          <span class="seg">
            <button class="seg-btn" class:on={lagSide === 'both'}
                    onclick={() => lagSide = 'both'}>Both</button>
            <button class="seg-btn" class:on={lagSide === 'positive'}
                    onclick={() => lagSide = 'positive'}>Positive</button>
            <button class="seg-btn" class:on={lagSide === 'negative'}
                    onclick={() => lagSide = 'negative'}>Negative</button>
          </span>
        </span>
      {/if}
      {#if zoomable && xRange}
        <span class="plot-toolbar-sep"></span>
        <span class="zoom-chip" class:full={atFullRate}>
          {(xRange[1] - xRange[0]).toPrecision(3)} s window ·
          {drawnPoints.toLocaleString()} pts
          {atFullRate ? ' · full rate' : ' · decimated'}
        </span>
        <button class="btn-ghost" onclick={() => xRange = null}>Reset zoom</button>
      {/if}
      {#if activeTab === 'psd' || overview}
        <span class="plot-toolbar-sep"></span>
        <label><input type="checkbox" bind:checked={psdYLog} /> PSD log Y</label>
      {/if}
      {#if activeTab === 'psd'}
        <span class="plot-toolbar-sep"></span>
        <span class="plot-toolbar-group">
          <span class="plot-toolbar-grouplabel">X range</span>
          <input type="number" bind:value={psdXMin} placeholder="min" class="plot-axis-input" />
          <input type="number" bind:value={psdXMax} placeholder="max" class="plot-axis-input" />
        </span>
        <span class="plot-toolbar-group">
          <span class="plot-toolbar-grouplabel">Y range</span>
          <input type="number" bind:value={psdYMin} placeholder="min" class="plot-axis-input" />
          <input type="number" bind:value={psdYMax} placeholder="max" class="plot-axis-input" />
        </span>
      {/if}
      {#if csvSupported}
        <button class="btn-ghost btn-csv" onclick={() => exportCsv()}>↓ CSV</button>
      {:else if gridCsvSupported}
        <button class="btn-ghost btn-csv" onclick={exportGridCsv}>↓ CSV (all channels)</button>
      {/if}
    </div>
  {/if}

  <!-- ── overview: the composed first look ── -->
  {#if overview}
    <div class="stack-scroll">
      {#if loading}
        <div class="plot-overlay"><div class="spinner"></div><div class="plot-overlay-text">Computing…</div></div>
      {/if}

      <section class="ov-block">
        {#if overviewSpecs.ts}
          <ResizablePane id="ov-ts" initial={300} label="Resize time series panel">
            {#snippet children()}<PlotCanvas spec={overviewSpecs.ts} height="100%" />{/snippet}
          </ResizablePane>
        {:else}
          <div class="ov-fail">Time series unavailable: {overviewSpecs.tsError}</div>
        {/if}
      </section>

      <section class="ov-block">
        {#if overviewSpecs.psd}
          <ResizablePane id="ov-psd" initial={320} label="Resize PSD panel">
            {#snippet children()}<PlotCanvas spec={overviewSpecs.psd} height="100%" />{/snippet}
          </ResizablePane>
        {:else}
          <div class="ov-fail">PSD unavailable: {overviewSpecs.psdError}</div>
        {/if}
      </section>

      <section class="ov-block">
        {#if overviewSpecs.fdd}
          <!-- The singular-value plot carries one curve per channel plus the
               peak markers, so it needs materially more room than the others. -->
          <ResizablePane id="ov-fdd" initial={520} label="Resize FDD panel">
            {#snippet children()}<PlotCanvas spec={overviewSpecs.fdd} height="100%" />{/snippet}
          </ResizablePane>
          <!-- Overview runs FDD on whatever is selected, which the user did not
               choose per-analysis. An excitation channel in the mix moves the
               peaks a long way, so say so rather than let it pass as a result. -->
          <div class="ov-note">
            FDD assumes output-only (response) channels. Ran on:
            <strong>{overviewSpecs.fddData.labels.join(', ')}</strong>.
            If any of those are excitation/force inputs, deselect them in the
            sidebar — the mode estimates will change.
          </div>
          {#if overviewSpecs.fddData?.peak_freqs?.length}
            <div class="ov-table-head">
              <span>Candidate modes — first-pass FDD peak picking</span>
              <button class="btn-ghost btn-csv"
                      onclick={() => exportCsv('fdd', overviewSpecs.fddData, 'fdd_overview.csv')}>
                ↓ CSV
              </button>
            </div>
            <div class="results-table-wrap">
              <table class="results-table">
                <thead>
                  <tr><th>Mode</th><th>Freq [Hz]</th><th>Damping [%]</th>
                    {#each overviewSpecs.fddData.labels as lbl}<th>{lbl}</th>{/each}
                  </tr>
                </thead>
                <tbody>
                  {#each overviewSpecs.fddData.peak_freqs as f, i}
                    <tr>
                      <td>{i + 1}</td>
                      <td>{(overviewSpecs.fddData.natural_freqs?.[i] ?? f).toFixed(2)}</td>
                      <td>{overviewSpecs.fddData.damping_ratios?.[i] != null
                            ? (overviewSpecs.fddData.damping_ratios[i] * 100).toFixed(2) : '—'}</td>
                      {#each overviewSpecs.fddData.modes[i] ?? [] as v}<td>{v.toFixed(3)}</td>{/each}
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        {:else if overviewSpecs.fddSkipped}
          <div class="ov-note">{overviewSpecs.fddSkipped}</div>
        {:else}
          <div class="ov-fail">FDD unavailable: {overviewSpecs.fddError}</div>
        {/if}
      </section>
    </div>

  <!-- ── grid: one single-channel analysis, run per channel ── -->
  {:else if grid}
    <div class="stack-scroll">
      {#if loading}
        <div class="plot-overlay"><div class="spinner"></div><div class="plot-overlay-text">Computing…</div></div>
      {/if}
      <div class="plot-grid">
        {#each gridSpecs as cell (cell.name)}
          <!-- Every cell binds the same height, so dragging any one keeps the
               rows aligned instead of leaving a ragged grid. -->
          <ResizablePane id="grid-cell" initial={270} bind:height={gridCellH}
                         label="Resize grid rows">
            {#snippet children()}
              <div class="plot-grid-cell">
                {#if cell.spec}
                  <PlotCanvas spec={cell.spec} height="100%" />
                {:else}
                  <div class="ov-fail">{cell.name}: {cell.error ?? 'no result'}</div>
                {/if}
              </div>
            {/snippet}
          </ResizablePane>
        {/each}
      </div>
    </div>

  <!-- ── single result ── -->
  {:else}
    <!-- Fills the available space until dragged, then holds the height you set. -->
    <ResizablePane id="main-plot" fill initial={420} label="Resize plot">
      {#snippet children()}
        <div class="plot-canvas-wrap">
          {#if loading}
            <div class="plot-overlay">
              <div class="spinner"></div>
              <div class="plot-overlay-text">Computing…</div>
            </div>
          {/if}
          {#if !plotData && !loading && !plotError}
            <div class="plot-placeholder">
              Select an analysis and press Run.
            </div>
          {/if}
          <PlotCanvas spec={mainSpec} onRelayout={zoomable ? onRelayout : null} />
        </div>
      {/snippet}
    </ResizablePane>

    <!-- phase panel -->
    {#if phaseSpec}
      <div class="plot-phase-pane">
        <PlotCanvas spec={phaseSpec} />
      </div>
    {/if}

    <!-- peaks results table -->
    {#if activeTab === 'peaks' && single?.peak_freqs?.length}
      <div class="results-table-wrap">
        <table class="results-table">
          <thead>
            <tr><th>#</th><th>Freq [Hz]</th><th>Amplitude</th><th>Prominence</th><th>BW [Hz]</th><th>Q</th></tr>
          </thead>
          <tbody>
            {#each single.peak_freqs as f, i}
              <tr>
                <td>{i + 1}</td>
                <td>{f.toFixed(2)}</td>
                <td>{single.peak_values[i]?.toPrecision(4)}</td>
                <td>{single.prominences[i]?.toPrecision(3)}</td>
                <td>{single.bandwidths[i]?.toFixed(2) ?? '—'}</td>
                <td>{single.q_factors[i]?.toFixed(1) ?? '—'}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

    <!-- FDD results table + mode shapes -->
    {#if activeTab === 'fdd' && single?.peak_freqs?.length}
      <div class="results-table-wrap">
        <table class="results-table">
          <thead>
            <tr><th>Mode</th><th>Freq [Hz]</th><th>Damping [%]</th>
              {#each single.labels as lbl}<th>{lbl}</th>{/each}
            </tr>
          </thead>
          <tbody>
            {#each single.peak_freqs as f, i}
              <tr>
                <td>{i + 1}</td>
                <td>{(single.natural_freqs?.[i] ?? f).toFixed(2)}</td>
                <td>{single.damping_ratios?.[i] != null ? (single.damping_ratios[i] * 100).toFixed(2) : '—'}</td>
                {#each single.modes[i] ?? [] as v}
                  <td>{v.toFixed(3)}</td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  {/if}

</div>

<style>
  /* Overview and the grid size to their content and let .plot-wrap do the
     scrolling — a nested scroller here would give the page two scrollbars and
     trap the wheel inside the inner one. */
  .stack-scroll {
    position: relative;
    flex: 0 0 auto;
    padding: 4px 2px 12px;
  }
  .ov-block {
    margin-bottom: 14px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 12px;
  }
  .ov-block:last-child { border-bottom: none; margin-bottom: 0; }
  .ov-table-head {
    display: flex; align-items: center; justify-content: space-between;
    font-size: 12px; color: var(--text-secondary);
    margin: 8px 2px 4px;
  }
  .ov-note, .ov-fail {
    font-size: 12px; padding: 14px 10px;
    color: var(--text-muted);
  }
  .ov-fail { color: var(--danger); }

  .plot-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(330px, 1fr));
    gap: 10px;
  }
  .prov-chip {
    font-size: 11px;
    padding: 1px 7px;
    border-radius: 999px;
    border: 1px solid var(--border);
    color: var(--text-muted);
    white-space: nowrap;
  }
  /* Active preprocessing is a caveat on every number read off the plot, so it
     is tinted rather than left to blend into the rest of the toolbar. */
  .prov-chip.on {
    color: var(--warning);
    border-color: var(--warning);
  }

  .seg {
    display: inline-flex;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    overflow: hidden;
  }
  .seg-btn {
    font: inherit;
    font-size: 11px;
    padding: 2px 9px;
    border: none;
    background: transparent;
    color: var(--text-secondary);
    cursor: pointer;
    transition: background var(--transition), color var(--transition);
  }
  .seg-btn + .seg-btn { border-left: 1px solid var(--border); }
  .seg-btn:hover { background: var(--bg-hover); }
  .seg-btn.on { background: var(--accent); color: var(--accent-contrast); }

  .zoom-chip {
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
  }
  .zoom-chip.full { color: var(--success); }

  .plot-grid-cell {
    height: 100%;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    overflow: hidden;
  }
</style>

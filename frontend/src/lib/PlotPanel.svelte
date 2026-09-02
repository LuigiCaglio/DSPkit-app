<script>
  import { onMount } from 'svelte'
  import PlotCanvas from './PlotCanvas.svelte'
  import ResizablePane from './ResizablePane.svelte'
  import { plotTheme, themeState } from './theme.svelte.js'
  import { buildPlot, buildPhasePlot, buildPairOverlay, buildExplorer,
           isDownsampledFor, MAX_PLOT_POINTS, HEATMAP_SCALES, LOG_Y_TABS } from './plotSpec.js'
  import { nearestIndex, spectrumAt, envelopeAt, describeResolution } from './explorer.js'
  import { ZOOMABLE, HEATMAP } from './analyses.js'
  import { describeCriteria, describeEmpty, dominanceLabel } from './fdd.js'
  import { withUnit, psdUnit, csdUnit, squared, product } from './units.js'

  let {
    activeTab, plotData, loading, plotError,
    preprocSummary = [], filterBand = null, filterResponse = null,
    setFilterFromRange = null, clearFilter = null,
    units = {},
    fddPicks = [], fddVectors = null, fddBusy = false, fddError = null,
    fddNVec = $bindable(1),
    onFddPick = null, onFddUnpick = null, onFddClear = null, onFddRun = null,
  } = $props()

  // Three shapes arrive here:
  //   {grid: [...]}      a single-channel analysis fanned out per channel
  //   {overview: {...}}  the composed first-look
  //   anything else      one analysis, one chart
  let grid     = $derived(plotData?.grid ?? null)
  let overview = $derived(plotData?.overview ?? null)
  let explorer = $derived(plotData?.explorer ?? null)
  let overlay  = $derived(plotData?.overlay ?? null)
  let single   = $derived(
    plotData && !grid && !overview && !overlay && !explorer ? plotData : null)

  // ── explorer: the picked time and frequency ────────────────────────────────
  // Slices are taken from the surface already in memory, so picking costs a
  // redraw rather than a request — which is what makes it feel like reading the
  // chart instead of querying it.
  let pickTime = $state(null)
  let pickFreq = $state(null)
  $effect(() => { const _ = plotData; pickTime = null; pickFreq = null })

  let explorerPick = $derived.by(() => {
    if (!explorer?.tf) return {}
    const { times, freqs, z } = explorer.tf
    const ti = pickTime != null ? nearestIndex(times, pickTime) : -1
    const fi = pickFreq != null ? nearestIndex(freqs, pickFreq) : -1
    return {
      time:      ti >= 0 ? times[ti] : null,
      timeIndex: ti >= 0 ? ti : null,
      spectrum:  ti >= 0 ? spectrumAt(z, ti) : null,
      freq:      fi >= 0 ? freqs[fi] : null,
      freqIndex: fi >= 0 ? fi : null,
      envelope:  fi >= 0 ? envelopeAt(z, fi) : null,
    }
  })

  let explorerSpec = $derived(
    explorer ? buildExplorer({ ...explorer, pick: explorerPick }, baseOpts) : null)

  let explorerRes = $derived(
    explorer?.tf ? describeResolution(explorer.tf.times, explorer.tf.freqs) : '')

  // ── FDD shapes: the copyable table ─────────────────────────────────────────
  // Tab-separated, because that is what pastes into a spreadsheet as columns.
  // Real and imaginary parts go alongside magnitude and phase: a shape usually
  // leaves here to be used in something else, and which form that wants is not
  // ours to guess.
  let svCopied = $state(false)

  // Channels down, one column per singular vector, is how a mode shape is
  // normally written and how it pastes into anything that expects shapes as
  // column vectors. The long form is one row per (frequency, vector) and is
  // the better shape for a spreadsheet you intend to filter or pivot.
  let svLayout = $state('byVector')   // 'byVector' | 'long'

  const TAB = '\t'
  const NL  = '\n'

  /** Flattened (frequency, singular vector) pairs — one per output column. */
  let svColumns = $derived.by(() => {
    if (!fddVectors?.points?.length) return []
    const out = []
    for (const pt of fddVectors.points) {
      for (const v of pt.vectors) {
        out.push({
          key: `${pt.freq_used.toPrecision(6)}|${v.sv}`,
          freq: pt.freq_used,
          sv: v.sv,
          sigma: v.singular_value,
          magnitude: v.magnitude,
          phase_deg: v.phase_deg,
          real: v.real,
          imag: v.imag,
        })
      }
    }
    return out
  })

  let svTable = $derived.by(() => {
    if (!fddVectors?.points?.length) return null
    const L = fddVectors.labels

    // What you copy matches what you are looking at.
    if (svLayout === 'byVector') {
      const cols = svColumns
      const head = ['channel', ...cols.map(c => `${c.freq.toPrecision(6)}Hz_SV${c.sv}`)]
      const block = (field) => L.map((lab, ci) =>
        [lab, ...cols.map(c => c[field][ci])].join(TAB))
      return [
        ['# magnitude'].join(TAB),
        head.join(TAB),
        ...block('magnitude'),
        '',
        ['# phase_deg'].join(TAB),
        head.join(TAB),
        ...block('phase_deg'),
      ].join(NL)
    }

    const head = ['freq_Hz', 'sv', 'singular_value',
      ...L.map(l => `${l}_mag`), ...L.map(l => `${l}_phase_deg`),
      ...L.map(l => `${l}_real`), ...L.map(l => `${l}_imag`)]
    const rows = []
    for (const pt of fddVectors.points) {
      for (const v of pt.vectors) {
        rows.push([pt.freq_used, v.sv, v.singular_value,
          ...v.magnitude, ...v.phase_deg, ...v.real, ...v.imag].join('\t'))
      }
    }
    return [head.join('\t'), ...rows].join('\n')
  })

  async function copySvTable() {
    if (!svTable) return
    try {
      await navigator.clipboard.writeText(svTable)
    } catch {
      // Clipboard access can be refused (permissions, or a non-secure origin).
      // Selecting the text is a worse experience but beats a button that does
      // nothing and says nothing.
      const ta = document.createElement('textarea')
      ta.value = svTable
      document.body.appendChild(ta); ta.select()
      try { document.execCommand('copy') } catch { /* nothing else to try */ }
      ta.remove()
    }
    svCopied = true
    setTimeout(() => { svCopied = false }, 1800)
  }

  /** A click anywhere on the FDD plot picks that frequency for a shape. */
  function onFddPlotClick(e) {
    const pt = e?.points?.[0]
    if (pt && onFddPick) onFddPick(pt.x)
  }

  /** A click on the surface sets both slices; a click elsewhere is ignored. */
  function onExplorerClick(e) {
    const pt = e?.points?.[0]
    if (!pt || pt.data?.type !== 'heatmap') return
    pickTime = pt.x
    pickFreq = pt.y
  }
  const clearPick = () => { pickTime = null; pickFreq = null }

  // ── display options (local state) ───────────────────────────────────────────
  let showPhase        = $state(false)
  let normalizeSignals = $state(false)
  let yLogScale        = $state(false)

  // Distributions: which marks to draw. Overlaying several channels' histograms
  // gets busy fast, so being able to drop to curves only is the point.
  let showHist = $state(true)
  let showKde  = $state(true)

  // Shared row height for the small-multiples grid; every cell binds to it.
  let gridCellH = $state(270)

  // Which half of the cross-correlation lag axis to show.
  let lagSide = $state('both')
  $effect(() => { const _ = activeTab; lagSide = 'both' })

  // ── time-frequency surface scaling ─────────────────────────────────────────
  // dB by default: a linear-magnitude spectrogram of real vibration data is one
  // bright ridge on a black field, because the dynamic range is several decades.
  // These are display preferences, so they persist rather than reset per tab.
  const TF_KEY = 'dspkit.tfDisplay'
  let tfDb         = $state(true)
  let tfRangeDb    = $state(60)
  let tfClipPct    = $state(99)
  let tfColorscale = $state('Viridis')
  // A surface is worse than a heatmap for reading a value -- peaks occlude what
  // is behind them and perspective distorts magnitude -- so it is an opt-in
  // view, never the default. It is genuinely better at showing the shape of a
  // ridge, which is why it is here at all.
  let tfSurface3d  = $state(false)
  let tfLoaded     = false

  onMount(() => {
    try {
      const v = JSON.parse(localStorage.getItem(TF_KEY) ?? 'null')
      if (v) {
        tfDb = v.db ?? tfDb
        tfRangeDb = v.rangeDb ?? tfRangeDb
        tfClipPct = v.clipPct ?? tfClipPct
        tfColorscale = HEATMAP_SCALES.includes(v.colorscale) ? v.colorscale : tfColorscale
        tfSurface3d = v.surface3d ?? tfSurface3d
      }
    } catch { /* defaults are fine */ }
    tfLoaded = true
  })

  $effect(() => {
    const v = { db: tfDb, rangeDb: tfRangeDb, clipPct: tfClipPct, colorscale: tfColorscale, surface3d: tfSurface3d }
    if (!tfLoaded) return          // don't overwrite storage before it is read
    try { localStorage.setItem(TF_KEY, JSON.stringify(v)) } catch { /* ignore */ }
  })

  let isHeatmap = $derived(HEATMAP.has(activeTab))

  // Explorer is excluded: its whole point is clicking the surface to slice it,
  // and picking a cell off a rotated 3-D mesh is not a usable gesture.
  let canSurface3d = $derived(isHeatmap && activeTab !== 'explorer')

  // The distribution view is the only stats mode with marks to toggle;
  // joint, covariance and Mahalanobis return other shapes entirely.
  let isDistribution = $derived(activeTab === 'statistics' && !!single?.signals?.[0]?.xi)

  // The joint view uses the same two toggles: the histogram is the heatmap,
  // the KDE is the iso-probability contour set.
  let isJoint = $derived(activeTab === 'statistics' && !!single?.H)

  // Normality returns numbers that need reading, not just a chart, so the
  // interpretation strings the library writes are shown under the plot.
  let normalitySignals = $derived(
    activeTab === 'statistics' && single?.signals?.[0]?.normality ? single.signals : null)

  // ── PSD-specific axis controls ───────────────────────────────────────────────
  let psdYLog = $state(true)   // default: log scale
  let psdXMin = $state('')
  let psdXMax = $state('')
  let psdYMin = $state('')
  let psdYMax = $state('')

  // Reset phase panel when switching tabs
  $effect(() => { const _ = activeTab; showPhase = false })

  // ...and the log-Y flag with it. It used to persist across tabs, so ticking it
  // on FFT left it set on Time series, where it silently truncated the waveform.
  $effect(() => { const _ = activeTab; yLogScale = false })

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
  let zoomable = $derived(ZOOMABLE.has(activeTab) && (!!single || !!grid))

  // Small multiples share one x-range by default: the cells are the same record
  // on a common time axis, so zooming them independently breaks the comparison
  // the grid exists for. Off, each cell keeps its own window.
  let sharedZoom = $state(true)
  let cellRanges = $state({})          // cell name -> [lo, hi], when not shared
  $effect(() => { const _ = plotData, __ = activeTab, ___ = sharedZoom; cellRanges = {} })
  let xRange   = $state(null)

  // ── filter band picking (PSD and FFT) ──────────────────────────────────────
  // Set cutoffs from the spectrum you are looking at. The default drag zooms,
  // which is not a selection and gives no feedback, so picking is an explicit
  // mode that switches Plotly to a horizontal select rectangle. The numbers
  // stay editable — a typed cutoff is often what you actually want.
  let bandPick = $derived(
    (activeTab === 'psd' || activeTab === 'fft') && !!single && !!setFilterFromRange
  )
  let picking = $state(false)
  let bandLo  = $state('')
  let bandHi  = $state('')

  // Only a real tab change discards the picked band. Depending on plotData too
  // meant every re-run — including the one applying the cutoff — wiped the
  // numbers the user had just selected.
  $effect(() => {
    const _ = activeTab
    picking = false; bandLo = ''; bandHi = ''
  })

  function onSelected(e) {
    const r = e?.range?.x
    if (!r) return
    bandLo = Number(Math.max(r[0], 0).toPrecision(4))
    bandHi = Number(Math.max(r[1], 0).toPrecision(4))
    picking = false          // one pick, then back to normal zooming
  }

  let bandReady = $derived(
    bandLo !== '' && bandHi !== '' && Number(bandHi) > Number(bandLo)
  )
  const applyBand = (kind) => setFilterFromRange(kind, Number(bandLo), Number(bandHi))

  // A new payload or a different analysis invalidates the old window.
  $effect(() => { const _ = plotData, __ = activeTab; xRange = null })

  /** Zoom inside one grid cell: drives every cell, or just its own. */
  function onCellRelayout(name, e) {
    if (!e) return
    if (e['xaxis.autorange'] || e.autosize) {
      if (sharedZoom) xRange = null
      else cellRanges = { ...cellRanges, [name]: null }
      return
    }
    const lo = e['xaxis.range[0]'] ?? e['xaxis.range']?.[0]
    const hi = e['xaxis.range[1]'] ?? e['xaxis.range']?.[1]
    if (lo == null || hi == null) return
    if (sharedZoom) {
      if (xRange && Math.abs(xRange[0] - lo) < 1e-12 && Math.abs(xRange[1] - hi) < 1e-12) return
      xRange = [lo, hi]
    } else {
      const cur = cellRanges[name]
      if (cur && Math.abs(cur[0] - lo) < 1e-12 && Math.abs(cur[1] - hi) < 1e-12) return
      cellRanges = { ...cellRanges, [name]: [lo, hi] }
    }
  }

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
    tf: { db: tfDb, rangeDb: tfRangeDb, clipPct: tfClipPct, colorscale: tfColorscale, surface3d: tfSurface3d },
    units,
    showHist,
    showKde,
  })

  let mainSpec = $derived(
    single
      ? buildPlot(activeTab, single, {
          ...baseOpts,
          xRange: zoomable ? xRange : null,
          band: filterBand,
          dragmode: picking ? 'select' : null,
          response: filterResponse,
        })
      : null
  )
  let phaseSpec = $derived(
    showPhase && hasPhaseData ? buildPhasePlot(activeTab, single, baseOpts) : null
  )

  // Several comparisons against one reference, drawn on a single axis.
  let overlaySpec = $derived(
    overlay
      ? buildPairOverlay(activeTab, overlay.items, { ...baseOpts, ref: overlay.ref })
      : null
  )
  let overlayFailures = $derived(overlay ? overlay.items.filter(i => i.error) : [])

  let gridSpecs = $derived(
    grid
      ? grid.map(r => ({
          name: r.name,
          error: r.error,
          spec: r.data ? buildPlot(activeTab, r.data, {
            ...baseOpts, cell: true, title: r.name,
            xRange: zoomable ? (sharedZoom ? xRange : (cellRanges[r.name] ?? null)) : null,
          }) : null,
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

  // The criteria a mode table was produced under, and what to say when nothing
  // met them. Both are derived so an empty result reads as an answer.
  let fddCriteria = $derived(describeCriteria(overviewSpecs?.fddData?.criteria))
  let fddEmpty = $derived(describeEmpty(
    overviewSpecs?.fddData?.criteria, overviewSpecs?.fddData?.labels ?? []))

  // The same, for the standalone FDD tab — where the thresholds are actually
  // tuned, so an empty result there most needs to say what it was measured
  // against.
  let singleFddCriteria = $derived(
    activeTab === 'fdd' ? describeCriteria(single?.criteria) : null)
  let singleFddEmpty = $derived(
    activeTab === 'fdd' ? describeEmpty(single?.criteria, single?.labels ?? []) : null)

  // ── CSV export ───────────────────────────────────────────────────────────────
  //
  // The headers already say `time_s` and `frequency_Hz`, so the amplitude
  // columns being bare was the odd one out — and a table pasted into a report
  // is exactly where nobody can ask what the numbers were in. Channel units go
  // into the header for the same reason they go onto the axis.
  const uName = (name) => withUnit(name, units.byName?.[name] ?? '')

  /** Build [headers, rows] for one analysis payload, or null if unsupported. */
  function csvFor(tab, d) {
    let headers = [], rows = []

    if (tab === 'timeseries') {
      const times = d.preprocessed ? d.times_proc : d.times_raw
      headers = ['time_s', ...d.signals.map(s => uName(s.name))]
      const arr = d.preprocessed ? d.signals.map(s => s.signal_proc) : d.signals.map(s => s.signal_raw)
      for (let i = 0; i < times.length; i++) rows.push([times[i], ...arr.map(a => a[i])])

    } else if (tab === 'fft') {
      headers = ['frequency_Hz', ...d.signals.flatMap(s => [uName(s.name), `${s.name}_phase_deg`])]
      for (let i = 0; i < d.freqs.length; i++)
        rows.push([d.freqs[i], ...d.signals.flatMap(s => [s.amplitude[i], s.phase?.[i] ?? ''])])

    } else if (tab === 'psd') {
      headers = ['frequency_Hz',
                 ...d.signals.map(s => withUnit(s.name, psdUnit(units.byName?.[s.name] ?? '')))]
      for (let i = 0; i < d.freqs.length; i++)
        rows.push([d.freqs[i], ...d.signals.map(s => s.Pxx[i])])

    } else if (tab === 'autocorrelation') {
      headers = ['lag_s', ...d.signals.map(s => d.normalized === false
        ? withUnit(s.name, squared(units.byName?.[s.name] ?? '')) : s.name)]
      for (let i = 0; i < d.lags.length; i++)
        rows.push([d.lags[i], ...d.signals.map(s => s.acf[i])])

    } else if (tab === 'cross_correlation') {
      headers = ['lag_s', withUnit('CCF',
        d.normalized === false ? product(units.x ?? '', units.y ?? '') : '')]
      for (let i = 0; i < d.lags.length; i++) rows.push([d.lags[i], d.ccf[i]])

    } else if (tab === 'csd') {
      headers = ['frequency_Hz', withUnit('magnitude', csdUnit(units.x ?? '', units.y ?? '')), 'phase_deg']
      for (let i = 0; i < d.freqs.length; i++) rows.push([d.freqs[i], d.magnitude[i], d.phase_deg[i]])

    } else if (tab === 'coherence') {
      headers = ['frequency_Hz', 'coherence', 'phase_deg']
      for (let i = 0; i < d.freqs.length; i++)
        rows.push([d.freqs[i], d.Cxy[i], d.phase_deg?.[i] ?? ''])

    } else if (tab === 'filter') {
      headers = ['time_s', withUnit('raw', units.focus ?? ''), withUnit('filtered', units.focus ?? '')]
      for (let i = 0; i < d.times.length; i++)
        rows.push([d.times[i], d.signal_raw[i], d.signal_filtered[i]])

    } else if (tab === 'peaks') {
      headers = ['frequency_Hz', withUnit('amplitude', units.focus ?? ''),
                 'prominence', 'bandwidth_Hz', 'Q_factor']
      for (let i = 0; i < d.peak_freqs.length; i++)
        rows.push([d.peak_freqs[i], d.peak_values[i], d.prominences[i], d.bandwidths[i], d.q_factors[i]])

    } else if (tab === 'indicators') {
      headers = ['time_s', 'rms', 'energy', 'dominant_freq_Hz']
      const n = Math.max(d.rms_times.length, d.energy_times.length, d.freq_times.length)
      for (let i = 0; i < n; i++)
        rows.push([d.rms_times[i] ?? '', d.rms_values[i] ?? '', d.energy_values[i] ?? '', d.dominant_freqs[i] ?? ''])

    } else if (tab === 'fdd') {
      // sv1_sv2_dB travels with the export: a mode list pasted into a report is
      // exactly where the reader can no longer see what was required to make it.
      headers = ['mode', 'frequency_Hz', 'damping_pct', 'sv1_sv2_dB', ...d.labels]
      for (let i = 0; i < d.peak_freqs.length; i++)
        rows.push([i + 1, d.natural_freqs?.[i] ?? d.peak_freqs[i],
          d.damping_ratios?.[i] != null ? d.damping_ratios[i] * 100 : '',
          d.peak_dominance_db?.[i] ?? '',
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

  /** Overlay export: shared x column, one column per compared channel. */
  function exportOverlayCsv() {
    const usable = overlay.items.filter(i => i.data)
    if (!usable.length) return
    const d0 = usable[0].data
    const xName = activeTab === 'cross_correlation' ? 'lag_s' : 'frequency_Hz'
    const xs = activeTab === 'cross_correlation' ? d0.lags : d0.freqs
    const pick = (d) =>
      activeTab === 'cross_correlation' ? d.ccf :
      activeTab === 'coherence'         ? d.Cxy : d.magnitude
    const headers = [xName, ...usable.map(i => i.name)]
    const cols = usable.map(i => pick(i.data))
    const rows = []
    for (let i = 0; i < xs.length; i++) rows.push([xs[i], ...cols.map(c => c[i] ?? '')])
    download(`${activeTab}_vs_all.csv`, headers, rows)
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
      {#if LOG_Y_TABS.has(activeTab) && activeTab !== 'psd' && !overview}
        <label><input type="checkbox" bind:checked={yLogScale} /> Log Y</label>
      {/if}
      {#if isDistribution || isJoint}
        <label><input type="checkbox" bind:checked={showHist} /> Histogram</label>
        <label><input type="checkbox" bind:checked={showKde} /> KDE</label>
      {/if}
      {#if grid && ZOOMABLE.has(activeTab)}
        <span class="plot-toolbar-sep"></span>
        <label title="Zooming one cell zooms them all, so the panels stay comparable">
          <input type="checkbox" bind:checked={sharedZoom} /> Linked zoom
        </label>
        {#if sharedZoom ? xRange : Object.values(cellRanges).some(Boolean)}
          <button class="btn-ghost" onclick={() => { xRange = null; cellRanges = {} }}>
            Reset zoom
          </button>
        {/if}
      {/if}
      {#if isDownsampled || showAllPoints}
        <label><input type="checkbox" bind:checked={showAllPoints} /> All points</label>
      {/if}
      {#if bandPick}
        <span class="plot-toolbar-sep"></span>
        <span class="plot-toolbar-group">
          <span class="plot-toolbar-grouplabel">Filter</span>
          <button class="seg-btn pick-btn" class:on={picking}
                  onclick={() => picking = !picking}
                  title="Then drag across the spectrum to select a frequency band">
            {picking ? '✓ drag across the plot…' : '⌖ Pick from plot'}
          </button>
          <input type="number" bind:value={bandLo} placeholder="from Hz"
                 class="plot-axis-input" min="0" step="any" aria-label="Band lower edge (Hz)" />
          <input type="number" bind:value={bandHi} placeholder="to Hz"
                 class="plot-axis-input" min="0" step="any" aria-label="Band upper edge (Hz)" />
          <span class="seg">
            <button class="seg-btn" disabled={!bandReady} onclick={() => applyBand('highpass')}
                    title="Keep everything above the lower edge">High-pass</button>
            <button class="seg-btn" disabled={!bandReady} onclick={() => applyBand('lowpass')}
                    title="Keep everything below the upper edge">Low-pass</button>
            <button class="seg-btn" disabled={!bandReady} onclick={() => applyBand('bandpass')}
                    title="Keep only this band">Band-pass</button>
          </span>
        </span>
        {#if filterBand?.hp || filterBand?.lp}
          <button class="btn-ghost" onclick={clearFilter}>Remove filter</button>
        {/if}
      {/if}
      {#if isHeatmap}
        <span class="plot-toolbar-sep"></span>
        <label><input type="checkbox" bind:checked={tfDb} /> dB</label>
        {#if tfDb}
          <span class="plot-toolbar-group">
            <span class="plot-toolbar-grouplabel">range</span>
            <input type="number" bind:value={tfRangeDb} min="10" max="160" step="10"
                   class="plot-axis-input" aria-label="Dynamic range below peak (dB)" />
            <span class="plot-toolbar-grouplabel">dB below peak</span>
          </span>
        {:else}
          <span class="plot-toolbar-group">
            <span class="plot-toolbar-grouplabel">clip at</span>
            <input type="number" bind:value={tfClipPct} min="50" max="100" step="1"
                   class="plot-axis-input" aria-label="Upper percentile clip" />
            <span class="plot-toolbar-grouplabel">th pct</span>
          </span>
        {/if}
        <span class="plot-toolbar-group">
          <span class="plot-toolbar-grouplabel">colour</span>
          <select bind:value={tfColorscale} class="plot-axis-input" style="width:auto"
                  aria-label="Colour ramp">
            {#each HEATMAP_SCALES as c}<option value={c}>{c}</option>{/each}
          </select>
        </span>
        {#if canSurface3d}
          <span class="plot-toolbar-sep"></span>
          <label title="Drag to rotate. Good for seeing the shape of a ridge; the flat view is better for reading a value off it, since peaks hide what is behind them.">
            <input type="checkbox" bind:checked={tfSurface3d} /> 3D surface
          </label>
        {/if}
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
      {:else if overlay}
        <button class="btn-ghost btn-csv" onclick={exportOverlayCsv}>↓ CSV (all pairs)</button>
      {:else if gridCsvSupported}
        <button class="btn-ghost btn-csv" onclick={exportGridCsv}>↓ CSV (all channels)</button>
      {/if}
    </div>
  {/if}

  <!-- ── explorer: one surface, and everything that reads it ── -->
  {#if explorer}
    <div class="xp-wrap">
      {#if loading}
        <div class="plot-overlay"><div class="spinner"></div><div class="plot-overlay-text">Computing…</div></div>
      {/if}

      <div class="xp-bar">
        <span class="xp-chip">{explorer.transform.toUpperCase()}</span>
        <span class="xp-chan">{explorer.channel}</span>
        {#if explorerRes}
          <!-- What the chosen window actually bought, rather than making you
               infer it from nperseg. -->
          <span class="xp-res">{explorerRes}</span>
        {/if}
        <span class="xp-spacer"></span>
        {#if explorerPick.time != null || explorerPick.freq != null}
          <span class="xp-pick">
            {#if explorerPick.time != null}t = {explorerPick.time.toPrecision(4)} s{/if}
            {#if explorerPick.freq != null}
              {#if explorerPick.time != null} · {/if}f = {explorerPick.freq.toPrecision(4)} Hz
            {/if}
          </span>
          <button class="btn-ghost xp-clear" onclick={clearPick}>Clear slice</button>
        {:else}
          <span class="xp-hint">Click the surface for the spectrum at that moment
            and the envelope at that frequency.</span>
        {/if}
      </div>

      {#if explorer.notice}
        <div class="xp-notice">{explorer.notice}</div>
      {/if}

      {#if explorerSpec}
        <div class="xp-plot">
          <PlotCanvas spec={explorerSpec} height="100%" onClick={onExplorerClick} />
        </div>
      {:else}
        <div class="ov-fail">This transform returned nothing to draw.</div>
      {/if}
    </div>

  <!-- ── overview: the composed first look ── -->
  {:else if overview}
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
                  <tr><th>Mode</th><th>Freq [Hz]</th><th>Damping [%]</th><th>SV1/SV2</th>
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
                      <!-- How far this peak stands clear of the second singular
                           value: the measure that separates a mode from a
                           prominent piece of noise. -->
                      <td title={dominanceLabel(overviewSpecs.fddData.peak_dominance_db?.[i])}>
                        {overviewSpecs.fddData.peak_dominance_db?.[i] != null
                          ? `${overviewSpecs.fddData.peak_dominance_db[i].toFixed(1)} dB`
                          : '—'}
                      </td>
                      {#each overviewSpecs.fddData.modes[i] ?? [] as v}<td>{v.toFixed(3)}</td>{/each}
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
            {#if fddCriteria}<div class="ov-criteria">{fddCriteria}</div>{/if}
          {:else if fddEmpty}
            <!-- An empty table is a real answer here, not a failure. Say what
                 the bar was and what usually causes nothing to clear it. -->
            <div class="ov-empty">
              <div class="ov-empty-title">{fddEmpty.headline}</div>
              <div>{fddEmpty.detail}</div>
              {#if fddCriteria}<div class="ov-criteria">{fddCriteria}</div>{/if}
            </div>
          {/if}
        {:else if overviewSpecs.fddSkipped}
          <div class="ov-note">{overviewSpecs.fddSkipped}</div>
        {:else}
          <div class="ov-fail">FDD unavailable: {overviewSpecs.fddError}</div>
        {/if}
      </section>
    </div>

  <!-- ── overlay: one reference against several channels, on one axis ── -->
  {:else if overlay}
    <ResizablePane id="main-plot" fill initial={420} label="Resize plot">
      {#snippet children()}
        <div class="plot-canvas-wrap">
          {#if loading}
            <div class="plot-overlay">
              <div class="spinner"></div>
              <div class="plot-overlay-text">Computing…</div>
            </div>
          {/if}
          <PlotCanvas spec={overlaySpec} />
        </div>
      {/snippet}
    </ResizablePane>
    {#if overlayFailures.length}
      <div class="ov-fail">
        {overlayFailures.length} comparison{overlayFailures.length > 1 ? 's' : ''} failed:
        {overlayFailures.map(f => `${f.name} (${f.error})`).join('; ')}
      </div>
    {/if}

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
                  <PlotCanvas spec={cell.spec} height="100%"
                              onRelayout={zoomable ? (e) => onCellRelayout(cell.name, e) : null} />
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
          <PlotCanvas
            spec={mainSpec}
            onRelayout={zoomable ? onRelayout : null}
            onSelected={bandPick ? onSelected : null}
            onClick={activeTab === 'fdd' ? onFddPlotClick : null}
          />
        </div>
      {/snippet}
    </ResizablePane>

    <!-- phase panel -->
    {#if phaseSpec}
      <div class="plot-phase-pane">
        <PlotCanvas spec={phaseSpec} />
      </div>
    {/if}

    <!-- FDD: singular vectors at frequencies picked off the plot -->
  {#if activeTab === 'fdd' && single?.freqs}
    <div class="sv-panel">
      <div class="sv-bar">
        <span class="sv-title">Mode shapes at picked frequencies</span>
        <span class="plot-toolbar-grouplabel">
          click the plot to pick{fddVectors?.df ? ` · resolution ${fddVectors.df.toPrecision(3)} Hz` : ''}
        </span>
        <span class="plot-toolbar-sep"></span>
        <span class="plot-toolbar-grouplabel">vectors</span>
        <input type="number" bind:value={fddNVec} min="1" max="12" class="plot-axis-input"
               aria-label="How many singular vectors" />
        <button class="btn-ghost" onclick={() => onFddRun?.()}
                disabled={fddBusy || fddPicks.length === 0}>
          {fddBusy ? 'Working…' : 'Get shapes'}
        </button>
        {#if fddPicks.length}
          <button class="btn-ghost" onclick={() => onFddClear?.()}>Clear</button>
        {/if}
        {#if fddVectors}
          <span class="plot-toolbar-sep"></span>
          <span class="seg">
            <button class="seg-btn" class:on={svLayout === 'byVector'}
                    onclick={() => svLayout = 'byVector'}
                    title="Channels down the side, one column per singular vector — how a mode shape is normally written">
              Vectors as columns
            </button>
            <button class="seg-btn" class:on={svLayout === 'long'}
                    onclick={() => svLayout = 'long'}
                    title="One row per frequency and vector — easier to filter or pivot in a spreadsheet">
              One row each
            </button>
          </span>
        {/if}
        {#if svTable}
          <button class="btn-ghost" onclick={copySvTable}>{svCopied ? 'Copied' : 'Copy table'}</button>
        {/if}
      </div>

      {#if fddPicks.length}
        <div class="sv-picks">
          {#each fddPicks as f, i}
            <button class="sv-chip" onclick={() => onFddUnpick?.(i)} title="Remove">
              {f.toPrecision(5)} Hz ×
            </button>
          {/each}
        </div>
      {:else}
        <div class="sv-hint">
          No frequencies picked yet. Click anywhere on the singular-value curves —
          a peak, or a frequency the automatic picker missed.
        </div>
      {/if}

      {#if fddError}
        <div class="error">{fddError}</div>
      {/if}

      {#if fddVectors}
        <div class="sv-table-wrap">
          {#if svLayout === 'byVector'}
            <table class="results-table sv-table">
              <thead>
                <tr>
                  <th class="sv-rowhead">Channel</th>
                  {#each svColumns as c}
                    <th>{c.freq.toPrecision(5)} Hz<br /><span class="sv-sub">SV{c.sv}</span></th>
                  {/each}
                </tr>
                <tr>
                  <th class="sv-rowhead sv-sub">&sigma;</th>
                  {#each svColumns as c}
                    <th class="sv-sub">{c.sigma.toExponential(2)}</th>
                  {/each}
                </tr>
              </thead>
              <tbody>
                {#each fddVectors.labels as lab, ci}
                  <tr>
                    <td class="sv-rowhead">{lab}</td>
                    {#each svColumns as c}
                      <td>{c.magnitude[ci].toFixed(4)} ∠{c.phase_deg[ci].toFixed(1)}°</td>
                    {/each}
                  </tr>
                {/each}
              </tbody>
            </table>
          {:else}
            <table class="results-table sv-table">
              <thead>
                <tr>
                  <th>Freq [Hz]</th><th>SV</th><th>&sigma;</th>
                  {#each fddVectors.labels as l}<th>{l}</th>{/each}
                </tr>
              </thead>
              <tbody>
                {#each svColumns as c}
                  <tr>
                    <td>{c.freq.toPrecision(6)}</td>
                    <td>SV{c.sv}</td>
                    <td>{c.sigma.toExponential(3)}</td>
                    {#each c.magnitude as m, ci}
                      <td>{m.toFixed(4)} ∠{c.phase_deg[ci].toFixed(1)}°</td>
                    {/each}
                  </tr>
                {/each}
              </tbody>
            </table>
          {/if}
        </div>
        <div class="sv-hint">
          Magnitude ∠ phase. Each vector is rotated so its largest channel is real
          and positive, so two shapes can be compared rather than differing by an
          arbitrary phase. Copy gives tab-separated text, ready to paste into a
          spreadsheet.
        </div>
      {/if}
    </div>
  {/if}

  <!-- normality indicators, with the library's own interpretation of each -->
  {#if normalitySignals}
    <div class="results-table-wrap" style="max-height:260px">
      {#each normalitySignals as sg}
        <div class="norm-block">
          <div class="norm-head">{sg.name}</div>
          <div class="norm-summary">{sg.normality.summary}</div>
          {#each ['skewness','excess_kurtosis','dagostino_k2','jarque_bera','anderson_darling','shapiro_wilk'] as key}
            {#if sg.normality[key]}
              <div class="norm-row">
                <span class="norm-key">{key.replace(/_/g, ' ')}</span>
                <span class="norm-val">
                  {sg.normality[key].value !== undefined
                    ? Number(sg.normality[key].value).toPrecision(4)
                    : (sg.normality[key].statistic !== undefined
                        ? `stat ${Number(sg.normality[key].statistic).toPrecision(4)}`
                        : '')}
                  {#if sg.normality[key].pvalue !== undefined && sg.normality[key].pvalue !== null}
                    · p {Number(sg.normality[key].pvalue) < 1e-4
                          ? Number(sg.normality[key].pvalue).toExponential(1)
                          : Number(sg.normality[key].pvalue).toFixed(4)}
                  {/if}
                </span>
                <span class="norm-note">{sg.normality[key].interpretation}</span>
              </div>
            {/if}
          {/each}
        </div>
      {/each}
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
            <tr><th>Mode</th><th>Freq [Hz]</th><th>Damping [%]</th><th>SV1/SV2</th>
              {#each single.labels as lbl}<th>{lbl}</th>{/each}
            </tr>
          </thead>
          <tbody>
            {#each single.peak_freqs as f, i}
              <tr>
                <td>{i + 1}</td>
                <td>{(single.natural_freqs?.[i] ?? f).toFixed(2)}</td>
                <td>{single.damping_ratios?.[i] != null ? (single.damping_ratios[i] * 100).toFixed(2) : '—'}</td>
                <td title={dominanceLabel(single.peak_dominance_db?.[i])}>
                  {single.peak_dominance_db?.[i] != null
                    ? `${single.peak_dominance_db[i].toFixed(1)} dB` : '—'}
                </td>
                {#each single.modes[i] ?? [] as v}
                  <td>{v.toFixed(3)}</td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      {#if singleFddCriteria}<div class="ov-criteria">{singleFddCriteria}</div>{/if}
    {:else if activeTab === 'fdd' && singleFddEmpty}
      <div class="ov-empty">
        <div class="ov-empty-title">{singleFddEmpty.headline}</div>
        <div>{singleFddEmpty.detail}</div>
        {#if singleFddCriteria}<div class="ov-criteria">{singleFddCriteria}</div>{/if}
      </div>
    {/if}
  {/if}

</div>

<style>
  /* ── explorer ─────────────────────────────────────────────────────────── */
  /* One tall figure rather than a stack of panes: the panels only mean
     anything next to each other, so they resize together. */
  .xp-wrap { display: flex; flex-direction: column; height: 100%; min-height: 0; position: relative; }
  .xp-plot { flex: 1 1 auto; min-height: 0; }
  .xp-bar {
    display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
    padding: 4px 8px; font-size: 11px; color: var(--text-muted);
    border-bottom: 1px solid var(--border);
  }
  .xp-spacer { flex: 1 1 auto; }
  .xp-chip {
    font-weight: 600; color: var(--accent);
    letter-spacing: .06em;
  }
  .xp-chan { color: var(--text-secondary); }
  .xp-res { font-variant-numeric: tabular-nums; }
  .xp-pick { color: var(--danger); font-variant-numeric: tabular-nums; }
  .xp-hint { font-style: italic; opacity: .8; }
  .xp-clear { font-size: 11px; padding: 1px 8px; }
  .xp-notice {
    padding: 5px 8px; font-size: 11px;
    color: var(--warning); border-bottom: 1px solid var(--border);
  }
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

  /* The bar a mode table was held to. Deliberately attached to the table
     rather than hidden in a settings panel: a list of modes is unreadable
     without knowing what was required to get on it. */
  .ov-criteria {
    font-size: 11px;
    color: var(--text-muted);
    margin: 5px 2px 0;
    font-variant-numeric: tabular-nums;
  }

  /* Nothing qualified — an answer, not a failure, so it is styled as a note
     rather than in the error colour. */
  .ov-empty {
    font-size: 12px;
    color: var(--text-muted);
    padding: 12px 10px;
    background: color-mix(in srgb, var(--text-muted) 6%, transparent);
    border-radius: var(--radius);
    line-height: 1.55;
  }
  .ov-empty-title {
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 3px;
  }

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
  .seg-btn:disabled { opacity: .45; cursor: default; }
  .seg-btn:disabled:hover { background: transparent; }
  /* The pick toggle stands alone rather than inside a .seg group. */
  .pick-btn {
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
  }

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

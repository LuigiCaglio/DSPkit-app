<script>
  import { onMount, onDestroy } from 'svelte'
  import Plotly from 'plotly.js-dist-min'

  let { activeTab, plotData, loading, plotError } = $props()

  let container  = $state(null)
  let container2 = $state(null)

  // ── display options (local state) ───────────────────────────────────────────
  let showPhase        = $state(false)
  let normalizeSignals = $state(false)
  let yLogScale        = $state(false)

  // ── PSD-specific axis controls ───────────────────────────────────────────────
  let psdYLog    = $state(true)   // default: log scale
  let psdXMin    = $state('')
  let psdXMax    = $state('')
  let psdYMin    = $state('')
  let psdYMax    = $state('')

  // Reset phase panel when switching tabs
  $effect(() => { const _ = activeTab; showPhase = false })

  // Reset PSD axis controls when switching away from psd tab
  $effect(() => {
    if (activeTab !== 'psd') {
      psdXMin = ''; psdXMax = ''; psdYMin = ''; psdYMax = ''; psdYLog = true
    }
  })

  // ── derived ─────────────────────────────────────────────────────────────────
  let canShowPhase = $derived(
    plotData !== null && (activeTab === 'fft' || activeTab === 'coherence')
  )
  let hasPhaseData = $derived(
    canShowPhase && (
      (activeTab === 'fft'       && plotData?.signals?.[0]?.phase != null) ||
      (activeTab === 'coherence' && plotData?.phase_deg != null)
    )
  )

  // ── helpers ─────────────────────────────────────────────────────────────────
  const COLORS = ['#6366f1','#f59e0b','#10b981','#ef4444','#8b5cf6','#06b6d4','#f97316','#ec4899']

  const DARK_LAYOUT = {
    paper_bgcolor: '#0f1117',
    plot_bgcolor:  '#13151f',
    font:          { color: '#e2e8f0', size: 12 },
    margin:        { l: 60, r: 20, t: 30, b: 50 },
    xaxis:         { gridcolor: '#2d3148', zerolinecolor: '#2d3148' },
    yaxis:         { gridcolor: '#2d3148', zerolinecolor: '#2d3148' },
    legend:        { bgcolor: '#1a1d27', bordercolor: '#2d3148', borderwidth: 1 },
  }

  const DARK_LAYOUT_COMPACT = { ...DARK_LAYOUT, margin: { l: 60, r: 20, t: 10, b: 50 } }

  function merge(...objs) { return Object.assign({}, ...objs) }

  function norm(arr) {
    if (!normalizeSignals) return arr
    const rms = Math.sqrt(arr.reduce((s, v) => s + v * v, 0) / arr.length)
    return rms > 0 ? arr.map(v => v / rms) : arr
  }

  function line(x, y, name, dash = 'solid', yaxis = 'y', color = undefined) {
    return { x, y, type: 'scatter', mode: 'lines', name,
             line: { dash, ...(color ? { color } : {}) }, yaxis }
  }

  function heatmap(x, y, z) {
    return [{ x, y, z, type: 'heatmap', colorscale: 'Viridis',
              colorbar: { thickness: 14, outlinewidth: 0 } }]
  }

  function yaxisType() { return yLogScale ? 'log' : 'linear' }

  // ── large-data downsampling ────────────────────────────────────────────────
  const MAX_PLOT_POINTS = 50_000
  let showAllPoints = $state(false)

  // Reset showAllPoints when data changes
  $effect(() => { const _ = plotData; showAllPoints = false })

  function downsample(x, y) {
    if (showAllPoints || !x || x.length <= MAX_PLOT_POINTS) return { x, y }
    const step = Math.ceil(x.length / MAX_PLOT_POINTS)
    const xd = [], yd = []
    for (let i = 0; i < x.length; i += step) { xd.push(x[i]); yd.push(y[i]) }
    return { x: xd, y: yd }
  }

  let isDownsampled = $derived(
    plotData && (
      (activeTab === 'timeseries' && (plotData.times_raw?.length > MAX_PLOT_POINTS || plotData.times_proc?.length > MAX_PLOT_POINTS)) ||
      (activeTab === 'filter' && plotData.times?.length > MAX_PLOT_POINTS) ||
      (activeTab === 'instantaneous' && plotData.times?.length > MAX_PLOT_POINTS)
    ) && !showAllPoints
  )

  // ── CSV export ───────────────────────────────────────────────────────────────
  function exportCsv() {
    if (!plotData) return
    let headers = [], rows = []
    const tab = activeTab

    if (tab === 'timeseries') {
      const times = plotData.preprocessed ? plotData.times_proc : plotData.times_raw
      headers = ['time_s', ...plotData.signals.map(s => s.name)]
      const arr = plotData.preprocessed
        ? plotData.signals.map(s => s.signal_proc)
        : plotData.signals.map(s => s.signal_raw)
      for (let i = 0; i < times.length; i++)
        rows.push([times[i], ...arr.map(a => a[i])])

    } else if (tab === 'fft') {
      headers = ['frequency_Hz', ...plotData.signals.flatMap(s => [s.name, `${s.name}_phase_deg`])]
      for (let i = 0; i < plotData.freqs.length; i++)
        rows.push([plotData.freqs[i], ...plotData.signals.flatMap(s => [s.amplitude[i], s.phase?.[i] ?? ''])])

    } else if (tab === 'psd') {
      headers = ['frequency_Hz', ...plotData.signals.map(s => s.name)]
      for (let i = 0; i < plotData.freqs.length; i++)
        rows.push([plotData.freqs[i], ...plotData.signals.map(s => s.Pxx[i])])

    } else if (tab === 'autocorrelation') {
      headers = ['lag_s', ...plotData.signals.map(s => s.name)]
      for (let i = 0; i < plotData.lags.length; i++)
        rows.push([plotData.lags[i], ...plotData.signals.map(s => s.acf[i])])

    } else if (tab === 'cross_correlation') {
      headers = ['lag_s', 'CCF']
      for (let i = 0; i < plotData.lags.length; i++) rows.push([plotData.lags[i], plotData.ccf[i]])

    } else if (tab === 'csd') {
      headers = ['frequency_Hz', 'magnitude', 'phase_deg']
      for (let i = 0; i < plotData.freqs.length; i++)
        rows.push([plotData.freqs[i], plotData.magnitude[i], plotData.phase_deg[i]])

    } else if (tab === 'coherence') {
      headers = ['frequency_Hz', 'coherence', 'phase_deg']
      for (let i = 0; i < plotData.freqs.length; i++)
        rows.push([plotData.freqs[i], plotData.Cxy[i], plotData.phase_deg?.[i] ?? ''])

    } else if (tab === 'filter') {
      headers = ['time_s', 'raw', 'filtered']
      for (let i = 0; i < plotData.times.length; i++)
        rows.push([plotData.times[i], plotData.signal_raw[i], plotData.signal_filtered[i]])

    } else if (tab === 'peaks') {
      headers = ['frequency_Hz', 'amplitude', 'prominence', 'bandwidth_Hz', 'Q_factor']
      for (let i = 0; i < plotData.peak_freqs.length; i++)
        rows.push([plotData.peak_freqs[i], plotData.peak_values[i], plotData.prominences[i], plotData.bandwidths[i], plotData.q_factors[i]])

    } else if (tab === 'indicators') {
      headers = ['time_s', 'rms', 'energy', 'dominant_freq_Hz']
      const n = Math.max(plotData.rms_times.length, plotData.energy_times.length, plotData.freq_times.length)
      for (let i = 0; i < n; i++)
        rows.push([plotData.rms_times[i] ?? '', plotData.rms_values[i] ?? '', plotData.energy_values[i] ?? '', plotData.dominant_freqs[i] ?? ''])

    } else if (tab === 'fdd') {
      headers = ['mode', 'frequency_Hz', 'damping_pct', ...plotData.labels]
      for (let i = 0; i < plotData.peak_freqs.length; i++)
        rows.push([i + 1, plotData.natural_freqs?.[i] ?? plotData.peak_freqs[i],
          plotData.damping_ratios?.[i] != null ? plotData.damping_ratios[i] * 100 : '',
          ...(plotData.modes[i] ?? [])])

    } else { return }

    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(new Blob([csv], { type: 'text/csv' })),
      download: `${tab}.csv`,
    })
    a.click()
    URL.revokeObjectURL(a.href)
  }

  // ── draw main plot ───────────────────────────────────────────────────────────
  function draw() {
    if (!container || !plotData) return
    const tab = activeTab

    if (tab === 'timeseries') {
      const traces = []
      plotData.signals.forEach((sig, i) => {
        const color = COLORS[i % COLORS.length]
        if (plotData.preprocessed) {
          const dr = downsample(plotData.times_raw, norm(sig.signal_raw))
          traces.push({ x: dr.x, y: dr.y,
            type: 'scatter', mode: 'lines', name: `${sig.name} (raw)`,
            opacity: 0.35, line: { color, dash: 'dot' } })
          const dp = downsample(plotData.times_proc, norm(sig.signal_proc))
          traces.push({ x: dp.x, y: dp.y,
            type: 'scatter', mode: 'lines', name: sig.name, line: { color } })
        } else {
          const d = downsample(plotData.times_raw, norm(sig.signal_raw))
          traces.push({ x: d.x, y: d.y,
            type: 'scatter', mode: 'lines', name: sig.name, line: { color } })
        }
      })
      const dsLabel = isDownsampled ? '  (downsampled for display)' : ''
      Plotly.react(container, traces, merge(DARK_LAYOUT, {
        xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
        yaxis: { ...DARK_LAYOUT.yaxis, title: normalizeSignals ? 'Amplitude (norm.)' : 'Amplitude', type: yaxisType() },
        title: { text: `${plotData.n_proc.toLocaleString()} samples  ·  fs = ${plotData.fs_proc.toFixed(2)} Hz${dsLabel}`,
                 font: { color: '#6b7280', size: 11 } },
      }))

    } else if (tab === 'fft') {
      const traces = plotData.signals.map((sig, i) =>
        line(plotData.freqs, norm(sig.amplitude), sig.name, 'solid', 'y', COLORS[i % COLORS.length]))
      Plotly.react(container, traces, merge(DARK_LAYOUT, {
        xaxis: { ...DARK_LAYOUT.xaxis, title: 'Frequency [Hz]' },
        yaxis: { ...DARK_LAYOUT.yaxis, title: normalizeSignals ? 'Amplitude (norm.)' : 'Amplitude', type: yaxisType() },
      }))

    } else if (tab === 'psd') {
      const traces = plotData.signals.map((sig, i) =>
        line(plotData.freqs, norm(sig.Pxx), sig.name, 'solid', 'y', COLORS[i % COLORS.length]))
      const psdXRange = (psdXMin !== '' && psdXMax !== '') ? [parseFloat(psdXMin), parseFloat(psdXMax)] : undefined
      const psdYRange = (psdYMin !== '' && psdYMax !== '') ? [parseFloat(psdYMin), parseFloat(psdYMax)] : undefined
      Plotly.react(container, traces, merge(DARK_LAYOUT, {
        xaxis: { ...DARK_LAYOUT.xaxis, title: 'Frequency [Hz]',
                 ...(psdXRange ? { range: psdXRange, autorange: false } : { autorange: true }) },
        yaxis: { ...DARK_LAYOUT.yaxis, title: 'PSD', type: psdYLog ? 'log' : 'linear',
                 ...(psdYRange ? { range: psdYRange, autorange: false } : { autorange: true }) },
      }))

    } else if (tab === 'autocorrelation') {
      const traces = plotData.signals.map((sig, i) =>
        line(plotData.lags, sig.acf, sig.name, 'solid', 'y', COLORS[i % COLORS.length]))
      Plotly.react(container, traces, merge(DARK_LAYOUT, {
        xaxis: { ...DARK_LAYOUT.xaxis, title: 'Lag [s]' },
        yaxis: { ...DARK_LAYOUT.yaxis, title: 'ACF' },
      }))

    } else if (tab === 'cross_correlation') {
      Plotly.react(container, [line(plotData.lags, plotData.ccf, 'CCF')], merge(DARK_LAYOUT, {
        xaxis: { ...DARK_LAYOUT.xaxis, title: 'Lag [s]' },
        yaxis: { ...DARK_LAYOUT.yaxis, title: 'CCF' },
      }))

    } else if (tab === 'csd') {
      Plotly.react(container,
        [line(plotData.freqs, plotData.magnitude, 'Magnitude'),
         line(plotData.freqs, plotData.phase_deg, 'Phase [°]', 'solid', 'y2')],
        merge(DARK_LAYOUT, {
          xaxis:  { ...DARK_LAYOUT.xaxis, title: 'Frequency [Hz]' },
          yaxis:  { ...DARK_LAYOUT.yaxis, title: '|CSD|' },
          yaxis2: { ...DARK_LAYOUT.yaxis, title: 'Phase [°]', overlaying: 'y', side: 'right' },
        }))

    } else if (tab === 'coherence') {
      Plotly.react(container, [line(plotData.freqs, plotData.Cxy, 'Coherence')], merge(DARK_LAYOUT, {
        xaxis: { ...DARK_LAYOUT.xaxis, title: 'Frequency [Hz]' },
        yaxis: { ...DARK_LAYOUT.yaxis, title: 'Coherence', range: [0, 1] },
      }))

    } else if (tab === 'filter') {
      const dr = downsample(plotData.times, plotData.signal_raw)
      const df = downsample(plotData.times, plotData.signal_filtered)
      Plotly.react(container,
        [line(dr.x, dr.y, 'Raw', 'dash'),
         line(df.x, df.y, 'Filtered', 'solid')],
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Amplitude' },
        }))

    } else if (tab === 'stft' || tab === 'cwt') {
      Plotly.react(container, heatmap(plotData.times, plotData.freqs, plotData.magnitude),
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Frequency [Hz]' },
        }))

    } else if (tab === 'wvd') {
      Plotly.react(container, heatmap(plotData.times, plotData.freqs, plotData.wvd),
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Frequency [Hz]' },
        }))

    } else if (tab === 'spwvd') {
      Plotly.react(container, heatmap(plotData.times, plotData.freqs, plotData.spwvd),
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Frequency [Hz]' },
        }))

    } else if (tab === 'instantaneous') {
      const ds = downsample(plotData.times, plotData.signal)
      const de = downsample(plotData.times, plotData.envelope)
      const di = downsample(plotData.times, plotData.inst_freq)
      Plotly.react(container,
        [line(ds.x, ds.y, 'Signal', 'dash'),
         line(de.x, de.y, 'Envelope', 'solid'),
         line(di.x, di.y, 'Inst. Freq [Hz]', 'solid', 'y2')],
        merge(DARK_LAYOUT, {
          xaxis:  { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
          yaxis:  { ...DARK_LAYOUT.yaxis, title: 'Amplitude' },
          yaxis2: { ...DARK_LAYOUT.yaxis, title: 'Inst. Freq [Hz]', overlaying: 'y', side: 'right' },
        }))

    } else if (tab === 'emd') {
      const traces = plotData.imfs.map((imf, i) => ({
        x: plotData.times, y: imf, type: 'scatter', mode: 'lines', name: `IMF ${i + 1}`,
      }))
      traces.push({ x: plotData.times, y: plotData.residue,
        type: 'scatter', mode: 'lines', name: 'Residue', line: { dash: 'dot' } })
      Plotly.react(container, traces, merge(DARK_LAYOUT, {
        xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
        yaxis: { ...DARK_LAYOUT.yaxis, title: 'Amplitude' },
      }))

    } else if (tab === 'hht') {
      const tfTraces = plotData.inst_freqs.map((fi, i) => ({
        x: plotData.times, y: fi, mode: 'markers',
        marker: { color: plotData.envelopes[i], colorscale: 'Viridis', size: 3,
                  showscale: i === 0, colorbar: { thickness: 12, outlinewidth: 0 } },
        name: `IMF ${i + 1}`, type: 'scatter',
      }))
      Plotly.react(container, tfTraces, merge(DARK_LAYOUT, {
        xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
        yaxis: { ...DARK_LAYOUT.yaxis, title: 'Inst. Freq [Hz]' },
        title: { text: 'HHT time-frequency representation', font: { color: '#a5b4fc' } },
      }))

    } else if (tab === 'peaks') {
      const traces = [
        line(plotData.freqs, plotData.spectrum, 'Spectrum'),
        { x: plotData.peak_freqs, y: plotData.peak_values,
          type: 'scatter', mode: 'markers', name: 'Peaks',
          marker: { symbol: 'triangle-up', size: 10, color: '#ef4444' } },
      ]
      Plotly.react(container, traces, merge(DARK_LAYOUT, {
        xaxis: { ...DARK_LAYOUT.xaxis, title: 'Frequency [Hz]' },
        yaxis: { ...DARK_LAYOUT.yaxis, title: 'Amplitude', type: yaxisType() },
      }))

    } else if (tab === 'indicators') {
      const traces = [
        { x: plotData.rms_times, y: plotData.rms_values,
          type: 'scatter', mode: 'lines', name: 'RMS', line: { color: COLORS[0] }, yaxis: 'y' },
        { x: plotData.energy_times, y: plotData.energy_values,
          type: 'scatter', mode: 'lines', name: 'Energy', line: { color: COLORS[1] }, yaxis: 'y2' },
        { x: plotData.freq_times, y: plotData.dominant_freqs,
          type: 'scatter', mode: 'lines', name: 'Dom. freq', line: { color: COLORS[2] }, yaxis: 'y3' },
      ]
      Plotly.react(container, traces, merge(DARK_LAYOUT, {
        xaxis:  { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
        yaxis:  { ...DARK_LAYOUT.yaxis, title: 'RMS', domain: [0.72, 1.0] },
        yaxis2: { ...DARK_LAYOUT.yaxis, title: 'Energy', domain: [0.36, 0.66], anchor: 'x' },
        yaxis3: { ...DARK_LAYOUT.yaxis, title: 'Freq [Hz]', domain: [0.0, 0.30], anchor: 'x' },
        title: { text: `Entropy: ${plotData.spectral_entropy.toFixed(3)}  |  Kurtosis: ${plotData.kurtosis.toFixed(3)}  |  Skewness: ${plotData.skewness.toFixed(3)}`,
                 font: { color: '#a5b4fc', size: 12 } },
      }))

    } else if (tab === 'multisensor') {
      if (plotData.R) {
        Plotly.react(container, [{
          z: plotData.R, x: plotData.labels, y: plotData.labels,
          type: 'heatmap', colorscale: 'RdBu', zmin: -1, zmax: 1,
          colorbar: { thickness: 14, outlinewidth: 0 },
          text: plotData.R.map(row => row.map(v => v.toFixed(3))),
          texttemplate: '%{text}', textfont: { size: 11 },
        }], merge(DARK_LAYOUT, {
          title: { text: 'Correlation Matrix', font: { color: '#a5b4fc' } },
          yaxis: { ...DARK_LAYOUT.yaxis, autorange: 'reversed' },
        }))
      } else if (plotData.pairs) {
        const traces = plotData.pairs.map((p, i) =>
          line(plotData.freqs, p.Cxy, p.label, 'solid', 'y', COLORS[i % COLORS.length]))
        Plotly.react(container, traces, merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Frequency [Hz]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Coherence', range: [0, 1] },
          title: { text: 'Coherence Matrix', font: { color: '#a5b4fc' } },
        }))
      }

    } else if (tab === 'fdd') {
      const nSv = plotData.S[0]?.length ?? 0
      const traces = []
      for (let sv = 0; sv < nSv; sv++) {
        const vals = plotData.S.map(row => 10 * Math.log10(Math.max(row[sv], 1e-30)))
        traces.push(line(plotData.freqs, vals, `SV${sv + 1}`, 'solid', 'y', COLORS[sv % COLORS.length]))
      }
      if (plotData.peak_freqs?.length) {
        const sv1 = plotData.S.map(row => 10 * Math.log10(Math.max(row[0], 1e-30)))
        const peakVals = plotData.peak_freqs.map(f => {
          const idx = plotData.freqs.reduce((best, freq, i) =>
            Math.abs(freq - f) < Math.abs(plotData.freqs[best] - f) ? i : best, 0)
          return sv1[idx]
        })
        traces.push({
          x: plotData.peak_freqs, y: peakVals,
          type: 'scatter', mode: 'markers', name: 'Peaks',
          marker: { symbol: 'triangle-up', size: 12, color: '#ef4444' },
        })
      }
      Plotly.react(container, traces, merge(DARK_LAYOUT, {
        xaxis: { ...DARK_LAYOUT.xaxis, title: 'Frequency [Hz]' },
        yaxis: { ...DARK_LAYOUT.yaxis, title: 'Singular Value [dB]' },
        title: { text: 'FDD \u2014 Singular Values', font: { color: '#a5b4fc' } },
      }))

    } else if (tab === 'statistics') {
      if (plotData.xi) {
        const traces = [
          { x: plotData.bin_centres, y: plotData.hist_density,
            type: 'bar', name: 'Histogram', marker: { color: 'rgba(99,102,241,0.4)' } },
          line(plotData.xi, plotData.density, 'KDE', 'solid', 'y', '#ef4444'),
        ]
        Plotly.react(container, traces, merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Value' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Density' },
          barmode: 'overlay',
          title: { text: 'Probability Density', font: { color: '#a5b4fc' } },
        }))
      } else if (plotData.H) {
        Plotly.react(container, [{
          x: plotData.x_centres, y: plotData.y_centres, z: plotData.H,
          type: 'heatmap', colorscale: 'Viridis',
          colorbar: { thickness: 14, outlinewidth: 0 },
        }], merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: plotData.xlabel },
          yaxis: { ...DARK_LAYOUT.yaxis, title: plotData.ylabel },
          title: { text: 'Joint Distribution', font: { color: '#a5b4fc' } },
        }))
      } else if (plotData.C) {
        Plotly.react(container, [{
          z: plotData.C, x: plotData.labels, y: plotData.labels,
          type: 'heatmap', colorscale: 'RdBu',
          colorbar: { thickness: 14, outlinewidth: 0 },
          text: plotData.C.map(row => row.map(v => v.toPrecision(3))),
          texttemplate: '%{text}', textfont: { size: 11 },
        }], merge(DARK_LAYOUT, {
          title: { text: 'Covariance Matrix', font: { color: '#a5b4fc' } },
          yaxis: { ...DARK_LAYOUT.yaxis, autorange: 'reversed' },
        }))
      } else if (plotData.distances) {
        const thresh = plotData.threshold
        const colors = plotData.distances.map(d => d > thresh ? '#ef4444' : COLORS[0])
        Plotly.react(container, [{
          x: plotData.times, y: plotData.distances,
          type: 'scatter', mode: 'markers', name: 'Mahalanobis',
          marker: { color: colors, size: 3 },
        }, {
          x: [plotData.times[0], plotData.times[plotData.times.length - 1]],
          y: [thresh, thresh],
          type: 'scatter', mode: 'lines', name: `${plotData.percentile}th pct`,
          line: { color: '#f59e0b', dash: 'dash' },
        }], merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Mahalanobis Distance' },
          title: { text: 'Mahalanobis Distance \u2014 Outlier Detection', font: { color: '#a5b4fc' } },
        }))
      }
    }
  }

  // ── draw phase panel ─────────────────────────────────────────────────────────
  function drawPhase() {
    if (!container2 || !plotData) return
    const tab = activeTab

    if (tab === 'fft') {
      const traces = plotData.signals.map((sig, i) => ({
        x: plotData.freqs, y: sig.phase,
        type: 'scatter', mode: 'lines', name: sig.name,
        line: { color: COLORS[i % COLORS.length] },
      }))
      Plotly.react(container2, traces, merge(DARK_LAYOUT_COMPACT, {
        xaxis: { ...DARK_LAYOUT.xaxis, title: 'Frequency [Hz]' },
        yaxis: { ...DARK_LAYOUT.yaxis, title: 'Phase [°]' },
      }))

    } else if (tab === 'coherence') {
      Plotly.react(container2, [{
        x: plotData.freqs, y: plotData.phase_deg,
        type: 'scatter', mode: 'lines', name: 'Phase',
        line: { color: COLORS[1] },
      }], merge(DARK_LAYOUT_COMPACT, {
        xaxis: { ...DARK_LAYOUT.xaxis, title: 'Frequency [Hz]' },
        yaxis: { ...DARK_LAYOUT.yaxis, title: 'Phase [°]' },
      }))
    }
  }

  // ── effects ──────────────────────────────────────────────────────────────────
  $effect(() => {
    // touch all reactive deps that should trigger a redraw
    const _ = plotData; const __ = activeTab
    const _n = normalizeSignals; const _l = yLogScale; const _s = showAllPoints
    const _pl = psdYLog; const _px1 = psdXMin; const _px2 = psdXMax
    const _py1 = psdYMin; const _py2 = psdYMax
    draw()
  })

  $effect(() => {
    // phase panel: redraw whenever showPhase, plotData, or activeTab changes
    const _ = showPhase; const __ = plotData; const ___ = activeTab
    if (showPhase && hasPhaseData) drawPhase()
    // Resize main plot after DOM updates so flexbox recalculates heights
    requestAnimationFrame(() => { if (container) Plotly.Plots.resize(container) })
  })

  // Initialize container2 when it first appears in the DOM
  $effect(() => {
    if (container2) {
      Plotly.newPlot(container2, [], DARK_LAYOUT_COMPACT, { responsive: true })
      drawPhase()
    }
  })

  onMount(() => {
    if (!container) return
    Plotly.newPlot(container, [], DARK_LAYOUT, { responsive: true })
  })

  onDestroy(() => {
    if (container)  Plotly.purge(container)
    if (container2) Plotly.purge(container2)
  })
</script>

<div style="width:100%;flex:1;min-height:0;display:flex;flex-direction:column">

  <!-- toolbar -->
  {#if plotData}
    <div class="plot-toolbar">
      {#if canShowPhase}
        <label><input type="checkbox" bind:checked={showPhase} /> Phase</label>
      {/if}
      <label><input type="checkbox" bind:checked={normalizeSignals} /> Normalize</label>
      {#if activeTab !== 'psd'}
        <label><input type="checkbox" bind:checked={yLogScale} /> Log Y</label>
      {/if}
      {#if isDownsampled || showAllPoints}
        <label><input type="checkbox" bind:checked={showAllPoints} /> All points</label>
      {/if}
      {#if activeTab === 'psd'}
        <span class="plot-toolbar-sep"></span>
        <label><input type="checkbox" bind:checked={psdYLog} /> Log Y</label>
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
      <button class="btn-csv" onclick={exportCsv}>↓ CSV</button>
    </div>
  {/if}

  <!-- main plot -->
  <div style="flex:1;min-height:0;position:relative">
    {#if loading}
      <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);z-index:10;display:flex;flex-direction:column;align-items:center;gap:10px">
        <div class="spinner"></div>
        <div style="font-size:12px;color:#6b7280">Computing…</div>
      </div>
    {/if}
    {#if !plotData && !loading && !plotError}
      <div style="display:flex;align-items:center;justify-content:center;height:100%;color:#4b5563;font-size:13px">
        Select an analysis and press Run.
      </div>
    {/if}
    <div bind:this={container} style="width:100%;height:100%"></div>
  </div>

  <!-- phase panel -->
  {#if showPhase && hasPhaseData}
    <div style="flex:0 0 35%;min-height:0;border-top:1px solid #2d3148">
      <div bind:this={container2} style="width:100%;height:100%"></div>
    </div>
  {/if}

  <!-- peaks results table -->
  {#if activeTab === 'peaks' && plotData?.peak_freqs?.length}
    <div class="results-table-wrap">
      <table class="results-table">
        <thead>
          <tr><th>#</th><th>Freq [Hz]</th><th>Amplitude</th><th>Prominence</th><th>BW [Hz]</th><th>Q</th></tr>
        </thead>
        <tbody>
          {#each plotData.peak_freqs as f, i}
            <tr>
              <td>{i + 1}</td>
              <td>{f.toFixed(2)}</td>
              <td>{plotData.peak_values[i]?.toPrecision(4)}</td>
              <td>{plotData.prominences[i]?.toPrecision(3)}</td>
              <td>{plotData.bandwidths[i]?.toFixed(2) ?? '—'}</td>
              <td>{plotData.q_factors[i]?.toFixed(1) ?? '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  <!-- FDD results table + mode shapes -->
  {#if activeTab === 'fdd' && plotData?.peak_freqs?.length}
    <div class="results-table-wrap">
      <table class="results-table">
        <thead>
          <tr><th>Mode</th><th>Freq [Hz]</th><th>Damping [%]</th>
            {#each plotData.labels as lbl}<th>{lbl}</th>{/each}
          </tr>
        </thead>
        <tbody>
          {#each plotData.peak_freqs as f, i}
            <tr>
              <td>{i + 1}</td>
              <td>{(plotData.natural_freqs?.[i] ?? f).toFixed(2)}</td>
              <td>{plotData.damping_ratios?.[i] != null ? (plotData.damping_ratios[i] * 100).toFixed(2) : '—'}</td>
              {#each plotData.modes[i] ?? [] as v}
                <td>{v.toFixed(3)}</td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

</div>

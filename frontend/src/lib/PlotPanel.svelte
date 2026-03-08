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

  // Reset phase panel when switching tabs
  $effect(() => { const _ = activeTab; showPhase = false })

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
          traces.push({ x: plotData.times_raw, y: norm(sig.signal_raw),
            type: 'scatter', mode: 'lines', name: `${sig.name} (raw)`,
            opacity: 0.35, line: { color, dash: 'dot' } })
          traces.push({ x: plotData.times_proc, y: norm(sig.signal_proc),
            type: 'scatter', mode: 'lines', name: sig.name, line: { color } })
        } else {
          traces.push({ x: plotData.times_raw, y: norm(sig.signal_raw),
            type: 'scatter', mode: 'lines', name: sig.name, line: { color } })
        }
      })
      Plotly.react(container, traces, merge(DARK_LAYOUT, {
        xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
        yaxis: { ...DARK_LAYOUT.yaxis, title: normalizeSignals ? 'Amplitude (norm.)' : 'Amplitude', type: yaxisType() },
        title: { text: `${plotData.n_proc.toLocaleString()} samples  ·  fs = ${plotData.fs_proc.toFixed(2)} Hz`,
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
      Plotly.react(container, traces, merge(DARK_LAYOUT, {
        xaxis: { ...DARK_LAYOUT.xaxis, title: 'Frequency [Hz]' },
        yaxis: { ...DARK_LAYOUT.yaxis, title: 'PSD', type: yLogScale ? 'linear' : 'log' },
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
      Plotly.react(container,
        [line(plotData.times, plotData.signal_raw,      'Raw',      'dash'),
         line(plotData.times, plotData.signal_filtered, 'Filtered', 'solid')],
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
      Plotly.react(container,
        [line(plotData.times, plotData.signal,    'Signal',          'dash'),
         line(plotData.times, plotData.envelope,  'Envelope',        'solid'),
         line(plotData.times, plotData.inst_freq, 'Inst. Freq [Hz]', 'solid', 'y2')],
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
    const _n = normalizeSignals; const _l = yLogScale
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

<div style="width:100%;height:100%;display:flex;flex-direction:column">

  <!-- toolbar -->
  {#if plotData}
    <div class="plot-toolbar">
      {#if canShowPhase}
        <label><input type="checkbox" bind:checked={showPhase} /> Phase</label>
      {/if}
      <label><input type="checkbox" bind:checked={normalizeSignals} /> Normalize</label>
      <label><input type="checkbox" bind:checked={yLogScale} /> Log Y</label>
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

</div>

<script>
  import { onMount, onDestroy } from 'svelte'
  import Plotly from 'plotly.js-dist-min'

  let { activeTab, plotData, loading, plotError } = $props()

  let container = $state(null)

  const DARK_LAYOUT = {
    paper_bgcolor: '#0f1117',
    plot_bgcolor:  '#13151f',
    font:          { color: '#e2e8f0', size: 12 },
    margin:        { l: 60, r: 20, t: 30, b: 50 },
    xaxis:         { gridcolor: '#2d3148', zerolinecolor: '#2d3148' },
    yaxis:         { gridcolor: '#2d3148', zerolinecolor: '#2d3148' },
    legend:        { bgcolor: '#1a1d27', bordercolor: '#2d3148', borderwidth: 1 },
  }

  const COLORS = ['#6366f1','#f59e0b','#10b981','#ef4444','#8b5cf6','#06b6d4','#f97316','#ec4899']

  function merge(...objs) {
    return Object.assign({}, ...objs)
  }

  function line(x, y, name, dash = 'solid', yaxis = 'y', color = undefined) {
    return { x, y, type: 'scatter', mode: 'lines', name,
             line: { dash, ...(color ? { color } : {}) }, yaxis }
  }

  function heatmap(x, y, z) {
    return [{ x, y, z, type: 'heatmap', colorscale: 'Viridis',
              colorbar: { thickness: 14, outlinewidth: 0 } }]
  }

  function draw() {
    if (!container || !plotData) return

    const tab = activeTab

    if (tab === 'timeseries') {
      const traces = []
      plotData.signals.forEach((sig, i) => {
        const color = COLORS[i % COLORS.length]
        if (plotData.preprocessed) {
          traces.push({
            x: plotData.times_raw, y: sig.signal_raw,
            type: 'scatter', mode: 'lines', name: `${sig.name} (raw)`,
            opacity: 0.35, line: { color, dash: 'dot' },
          })
          traces.push({
            x: plotData.times_proc, y: sig.signal_proc,
            type: 'scatter', mode: 'lines', name: sig.name,
            line: { color },
          })
        } else {
          traces.push({
            x: plotData.times_raw, y: sig.signal_raw,
            type: 'scatter', mode: 'lines', name: sig.name,
            line: { color },
          })
        }
      })
      Plotly.react(container, traces,
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Amplitude' },
          title: { text: `${plotData.n_proc.toLocaleString()} samples  ·  fs = ${plotData.fs_proc.toFixed(2)} Hz`,
                   font: { color: '#6b7280', size: 11 } },
        }))

    } else if (tab === 'fft') {
      const traces = plotData.signals.map((sig, i) =>
        line(plotData.freqs, sig.amplitude, sig.name, 'solid', 'y', COLORS[i % COLORS.length]))
      Plotly.react(container, traces,
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Frequency [Hz]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Amplitude' },
        }))

    } else if (tab === 'psd') {
      const traces = plotData.signals.map((sig, i) =>
        line(plotData.freqs, sig.Pxx, sig.name, 'solid', 'y', COLORS[i % COLORS.length]))
      Plotly.react(container, traces,
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Frequency [Hz]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'PSD', type: 'log' },
        }))

    } else if (tab === 'autocorrelation') {
      const traces = plotData.signals.map((sig, i) =>
        line(plotData.lags, sig.acf, sig.name, 'solid', 'y', COLORS[i % COLORS.length]))
      Plotly.react(container, traces,
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Lag [s]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'ACF' },
        }))

    } else if (tab === 'cross_correlation') {
      Plotly.react(container, [line(plotData.lags, plotData.ccf, 'CCF')],
        merge(DARK_LAYOUT, {
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
      Plotly.react(container, [line(plotData.freqs, plotData.Cxy, 'Coherence')],
        merge(DARK_LAYOUT, {
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
      Plotly.react(container,
        heatmap(plotData.times, plotData.freqs, plotData.magnitude),
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Frequency [Hz]' },
        }))

    } else if (tab === 'wvd') {
      Plotly.react(container,
        heatmap(plotData.times, plotData.freqs, plotData.wvd),
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Frequency [Hz]' },
        }))

    } else if (tab === 'spwvd') {
      Plotly.react(container,
        heatmap(plotData.times, plotData.freqs, plotData.spwvd),
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Frequency [Hz]' },
        }))

    } else if (tab === 'instantaneous') {
      Plotly.react(container,
        [line(plotData.times, plotData.signal,   'Signal',   'dash'),
         line(plotData.times, plotData.envelope, 'Envelope', 'solid'),
         line(plotData.times, plotData.inst_freq, 'Inst. Freq [Hz]', 'solid', 'y2')],
        merge(DARK_LAYOUT, {
          xaxis:  { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
          yaxis:  { ...DARK_LAYOUT.yaxis, title: 'Amplitude' },
          yaxis2: { ...DARK_LAYOUT.yaxis, title: 'Inst. Freq [Hz]', overlaying: 'y', side: 'right' },
        }))

    } else if (tab === 'emd') {
      const traces = plotData.imfs.map((imf, i) => ({
        x: plotData.times, y: imf,
        type: 'scatter', mode: 'lines', name: `IMF ${i + 1}`,
      }))
      traces.push({ x: plotData.times, y: plotData.residue,
        type: 'scatter', mode: 'lines', name: 'Residue', line: { dash: 'dot' } })
      Plotly.react(container, traces,
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Amplitude' },
        }))

    } else if (tab === 'hht') {
      const tfTraces = plotData.inst_freqs.map((fi, i) => ({
        x: plotData.times, y: fi,
        mode: 'markers',
        marker: { color: plotData.envelopes[i], colorscale: 'Viridis', size: 3,
                  showscale: i === 0, colorbar: { thickness: 12, outlinewidth: 0 } },
        name: `IMF ${i + 1}`, type: 'scatter',
      }))
      Plotly.react(container, tfTraces,
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Inst. Freq [Hz]' },
          title: { text: 'HHT time-frequency representation', font: { color: '#a5b4fc' } },
        }))
    }
  }

  $effect(() => {
    const _ = plotData
    const __ = activeTab
    draw()
  })

  onMount(() => {
    if (!container) return
    Plotly.newPlot(container, [], DARK_LAYOUT, { responsive: true })
  })

  onDestroy(() => {
    if (container) Plotly.purge(container)
  })
</script>

<div style="width:100%;height:100%;position:relative">
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
